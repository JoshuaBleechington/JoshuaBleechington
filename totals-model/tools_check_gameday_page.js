/* Replays web/gameday-cases.json through web/gameday.html in a real browser
 * and asserts the page reaches the same verdict, net edge, side and bar count
 * the Python package reached for the same inputs.
 *
 * The fixtures are generated from totals/gameday.py, so a failure here means
 * the page's arithmetic has drifted from the model's — the bug this project
 * has shipped more often than any other.
 *
 *   node tools_check_gameday_page.js
 */
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const CASES = JSON.parse(fs.readFileSync(path.join(__dirname, 'web/gameday-cases.json'), 'utf8'));

(async () => {
  // Point at the sandbox's pre-installed Chromium rather than the build the
  // pinned Playwright would go and download.
  const b = await chromium.launch({
    executablePath: process.env.CHROMIUM_PATH || '/opt/pw-browsers/chromium',
  });
  const pg = await b.newPage({ viewport: { width: 1240, height: 1400 } });
  const errs = [];
  pg.on('pageerror', e => errs.push(String(e)));
  pg.on('console', m => {
    // Google Fonts cannot be reached from an offline sandbox; it loads in the
    // published artifact and the page has a real fallback stack either way.
    const where = (m.location() && m.location().url) || '';
    if (m.type() === 'error' && !/fonts\.(googleapis|gstatic)\.com/.test(where + ' ' + m.text())) {
      errs.push('console: ' + m.text());
    }
  });
  await pg.goto('file://' + path.join(__dirname, 'web/gameday.html'));
  await pg.waitForTimeout(300);

  let fails = 0;
  const chk = (ok, m, d) => {
    if (!ok) fails++;
    console.log(`${ok ? 'PASS' : 'FAIL'}  ${m}${ok ? '' : '\n        ' + d}`);
  };

  for (const c of CASES) {
    for (const mode of ['strict', 'trial']) {
      const got = await pg.evaluate(async ([inputs, mode]) => {
        const ids = ["away", "home", "open", "line", "mph", "dir", "temp", "pf",
                     "spa", "spai", "sph", "sphi", "bpa", "bph",
                     "fa", "fh", "fg", "h2h", "h2hn", "tick", "cash"];
        ids.forEach(id => { document.getElementById(id).value = ''; });
        document.getElementById('dome').checked = false;
        document.getElementById(mode === 'trial' ? 'm-trial' : 'm-strict').click();
        for (const [k, v] of Object.entries(inputs)) {
          if (v === null || v === undefined) continue;
          if (k === 'dome') { document.getElementById('dome').checked = !!v; continue; }
          const e = document.getElementById(k);
          if (e) e.value = String(v);
        }
        ids.forEach(id => document.getElementById(id)
          .dispatchEvent(new Event('input', { bubbles: true })));
        document.getElementById('dome').dispatchEvent(new Event('change', { bubbles: true }));
        await new Promise(r => setTimeout(r, 60));

        const pick = document.querySelector('#verdict .pick');
        return {
          band: document.querySelector('#verdict .band').textContent.trim(),
          side: pick ? pick.textContent.trim().split(' ')[0] : null,
          net: parseFloat(document.querySelectorAll('#verdict .nums .v')[0].textContent.trim()),
          bars: document.querySelectorAll('#chart .bar').length,
          go: document.getElementById('verdict').classList.contains('go'),
          greenBand: document.querySelector('#verdict .band').classList.contains('go'),
        };
      }, [c.inputs, mode]);

      const w = c.expect[mode], tag = `${c.name} [${mode}]`;
      chk(got.band === w.verdict, `${tag}: ${w.verdict}`, `page said ${got.band}`);
      chk(Math.abs(got.net - w.net) < 0.011, `${tag}: net ${w.net.toFixed(2)}`, `page said ${got.net}`);
      chk(got.bars === w.items, `${tag}: ${w.items} bars`, `page drew ${got.bars}`);
      if (w.go) chk(got.side === w.side, `${tag}: side ${w.side}`, `page said ${got.side}`);
      // The user's one explicit rule for the graph: green means medium or high.
      chk(got.go === w.go && got.greenBand === w.go,
          `${tag}: green only when it is a call`,
          `go=${got.go} band=${got.greenBand} verdict=${w.verdict}`);
    }
  }

  if (errs.length) { console.log('PAGE ERRORS:\n' + errs.join('\n')); fails++; }
  console.log(fails ? `\n${fails} FAILED` : `\nall checks passed (${CASES.length} cases x 2 modes)`);
  await b.close();
  process.exit(fails ? 1 : 0);
})();
