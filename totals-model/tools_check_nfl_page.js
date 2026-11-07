/* Replays web/nfl-cases.json through web/fullgame.html in a real browser and
 * asserts the page reaches the same call totals/nfl.py reached.
 *
 * Deliberately separate from tools_check_fullgame_page.js. The two models share
 * a page but not a code path, and a failure here must name the NFL side without
 * ambiguity — one model going wrong must not take the other with it.
 *
 *   node tools_check_nfl_page.js
 */
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const CASES = JSON.parse(fs.readFileSync(path.join(__dirname, 'web/nfl-cases.json'), 'utf8'));
const IDS = ["away", "home", "line", "op", "up", "gdate", "anet", "hnet", "gp", "nopened"];
const CHECKS = ["dome", "aqb", "hqb"];

(async () => {
  const b = await chromium.launch({
    executablePath: process.env.CHROMIUM_PATH || '/opt/pw-browsers/chromium',
  });
  const pg = await b.newPage({ viewport: { width: 1280, height: 1400 } });
  const errs = [];
  pg.on('pageerror', e => errs.push(String(e)));
  pg.on('console', m => {
    const w = (m.location() && m.location().url) || '';
    if (m.type() === 'error' && !/fonts\.(googleapis|gstatic)\.com/.test(w + ' ' + m.text())) {
      errs.push('console: ' + m.text());
    }
  });
  await pg.goto('file://' + path.join(__dirname, 'web/fullgame.html'));
  await pg.waitForTimeout(300);

  let fails = 0;
  const chk = (ok, m, d) => {
    if (!ok) fails++;
    console.log(`${ok ? 'PASS' : 'FAIL'}  ${m}${ok ? '' : '\n        ' + d}`);
  };

  for (const c of CASES) {
    const got = await pg.evaluate(async ([inputs, ids, checks]) => {
      document.getElementById('m-nfl').click();
      ids.forEach(id => { const e = document.getElementById(id); if (e) e.value = ''; });
      checks.forEach(id => { document.getElementById(id).checked = false; });
      for (const [k, v] of Object.entries(inputs)) {
        const el = document.getElementById(k);
        if (!el) continue;
        if (el.type === 'checkbox') el.checked = !!v; else el.value = String(v);
      }
      ids.forEach(id => { const e = document.getElementById(id);
        if (e) e.dispatchEvent(new Event('input', { bubbles: true })); });
      checks.forEach(id => document.getElementById(id)
        .dispatchEvent(new Event('change', { bubbles: true })));
      await new Promise(r => setTimeout(r, 60));
      const call = document.getElementById('call');
      const pick = document.querySelector('#call .pick');
      const why = document.getElementById('why').textContent;
      return {
        band: document.querySelector('#call .band').textContent.trim(),
        side: pick ? pick.textContent.trim().split(' ')[0] : null,
        pResolved: parseFloat(call.dataset.pResolved),
        pPush: parseFloat(call.dataset.pPush),
        projected: parseFloat(call.dataset.projected),
        fair: parseFloat(call.dataset.fair),
        estimates: document.querySelectorAll('#est .erow').length,
        why,
      };
    }, [c.inputs, IDS, CHECKS]);

    const w = c.expect, tag = `NFL · ${c.name}`;
    chk(got.side === w.side, `${tag}: ${w.side}`, `page said ${got.side}`);
    chk(got.band === w.band, `${tag}: ${w.band}`, `page said ${got.band}`);
    chk(Math.abs(got.pResolved - w.p_resolved) < 1e-5,
        `${tag}: resolved ${(w.p_resolved * 100).toFixed(2)}%`,
        `page said ${(got.pResolved * 100).toFixed(4)}%`);
    chk(Math.abs(got.pPush - w.p_push) < 1e-5,
        `${tag}: push ${(w.p_push * 100).toFixed(2)}%`, `page said ${got.pPush}`);
    chk(Math.abs(got.projected - w.projected) < 1e-5,
        `${tag}: location ${w.projected.toFixed(4)}`, `page said ${got.projected}`);
    chk(Math.abs(got.fair - w.fair) < 0.05,
        `${tag}: fair ${w.fair.toFixed(1)}`, `page said ${got.fair}`);
    chk(got.estimates === w.estimates, `${tag}: ${w.estimates} estimates`,
        `page drew ${got.estimates}`);
    // The half point is the reason this model exists, so it is checked to the cent.
    chk(new RegExp(`${Math.round(w.half_point_cents)} cents`).test(got.why),
        `${tag}: half point quoted at ${Math.round(w.half_point_cents)} cents`,
        got.why.slice(0, 200));
    if (c.inputs.hqb || c.inputs.aqb) {
      chk(/NOT scored/.test(got.why), `${tag}: says the quarterback is not scored`,
          got.why.slice(0, 200));
    }
  }

  // ---- an NFL row grades on MARGIN, not on a total ---------------------
  await pg.evaluate(() => {
    const mk = (name, spread, side, final) => ({
      matchup: name, sport: 'NFL', line: spread, projected: '+1.0', side,
      prob: '55.0', band: 'BET', fair: '-122', final, inputs: {},
    });
    localStorage.setItem('callsheet.fullgame.card.v1', JSON.stringify([
      mk('home covers -3', -3, 'HOME', '7'),    // home by 7 beats -3      -> WIN
      mk('home fails -3', -3, 'HOME', '2'),     // home by 2 does not      -> LOSS
      mk('push on the three', -3, 'HOME', '3'), // exactly 3               -> PUSH
      mk('away covers +6', 6, 'AWAY', '-10'),   // away by 10 beats +6     -> WIN
      mk('away fails +6', 6, 'AWAY', '2'),      // home by 2, so away -6 loses -> LOSS
    ]));
  });
  await pg.reload();
  await pg.waitForTimeout(450);
  const grades = await pg.evaluate(() =>
    [...document.querySelectorAll('#cardTable tbody tr')].map(r => [
      r.querySelector('.openbtn').textContent.trim(),
      (r.querySelector('.res') || {}).textContent.trim()]));
  const want = { 'home covers -3': 'WIN', 'home fails -3': 'LOSS',
                 'push on the three': 'PUSH', 'away covers +6': 'WIN',
                 'away fails +6': 'LOSS' };
  for (const [name, got] of grades) {
    chk(got === want[name], `grading: ${name} -> ${want[name]}`, `page said ${got}`);
  }

  await pg.evaluate(() => localStorage.clear());
  if (errs.length) { console.log('PAGE ERRORS:\n' + errs.join('\n')); fails++; }
  console.log(fails ? `\n${fails} FAILED` : `\nall checks passed (${CASES.length} NFL cases)`);
  await b.close();
  process.exit(fails ? 1 : 0);
})();
