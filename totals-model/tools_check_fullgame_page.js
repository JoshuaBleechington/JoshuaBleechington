/* Replays web/fullgame-cases.json through web/fullgame.html in a real browser
 * and asserts the page reaches the same call the Python package reached.
 *
 * The fixtures come from totals/fullgame.py, so a failure here means the
 * page's arithmetic has drifted from the model's — the bug this project has
 * shipped more often than any other.
 *
 * Tolerances: probabilities to 1e-4 (Python uses math.erf and math.lgamma; the
 * browser uses Abramowitz & Stegun 7.1.26 and a Lanczos log-gamma, whose
 * errors are ~1e-7 and ~1e-13), projections to 1e-6.
 *
 *   node tools_check_fullgame_page.js
 */
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const CASES = JSON.parse(
  fs.readFileSync(path.join(__dirname, 'web/fullgame-cases.json'), 'utf8'));

const MLB_IDS = ["away","home","line","op","up","opened","gdate","aera","hera","arpg","hrpg",
                 "abp","hbp","al10","hl10","h2h","h2hn","pf","mph","dir","temp","tick","cash"];
const WNBA_IDS = ["away","home","line","op","up","opened","gdate","wal10","whl10",
                  "wh2h","wh2hn","aout","hout"];
const ALL = [...new Set([...MLB_IDS, ...WNBA_IDS])];
const CHECKS = ["dome", "alead", "hlead"];

(async () => {
  const b = await chromium.launch({
    executablePath: process.env.CHROMIUM_PATH || '/opt/pw-browsers/chromium',
  });
  const pg = await b.newPage({ viewport: { width: 1280, height: 1400 } });
  const errs = [];
  pg.on('pageerror', e => errs.push(String(e)));
  pg.on('console', m => {
    const where = (m.location() && m.location().url) || '';
    if (m.type() === 'error' && !/fonts\.(googleapis|gstatic)\.com/.test(where + ' ' + m.text())) {
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
    const got = await pg.evaluate(async ([sport, inputs, ids, checks]) => {
      document.getElementById(sport === 'WNBA' ? 'm-wnba' : 'm-mlb').click();
      ids.forEach(id => { document.getElementById(id).value = ''; });
      checks.forEach(id => { document.getElementById(id).checked = false; });
      for (const [k, v] of Object.entries(inputs)) {
        if (v === null || v === undefined) continue;
        const el = document.getElementById(k);
        if (!el) continue;
        if (el.type === 'checkbox') el.checked = !!v; else el.value = String(v);
      }
      ids.forEach(id => document.getElementById(id)
        .dispatchEvent(new Event('input', { bubbles: true })));
      checks.forEach(id => document.getElementById(id)
        .dispatchEvent(new Event('change', { bubbles: true })));
      await new Promise(r => setTimeout(r, 50));
      const call = document.getElementById('call');
      const pick = document.querySelector('#call .pick');
      const pct = document.querySelector('#call .pct');
      return {
        band: document.querySelector('#call .band').textContent.trim(),
        side: pick ? pick.textContent.trim().split(' ')[0] : null,
        pct: pct ? parseFloat(pct.textContent) : null,
        pOver: parseFloat(call.dataset.pOver),
        pPush: parseFloat(call.dataset.pPush),
        pResolved: parseFloat(call.dataset.pResolved),
        projected: parseFloat(call.dataset.projected),
        fair: parseFloat(call.dataset.fair),
        estimates: document.querySelectorAll('#est .erow').length,
        deltas: document.getElementById('deltaCard').hidden
          ? 0 : document.querySelectorAll('#deltas .drow').length,
        hot: call.classList.contains('hot'),
        bandHot: (() => {
          const el = document.querySelector('#call .band');
          return el.classList.contains('hot') || el.classList.contains('max');
        })(),
      };
    }, [c.sport, c.inputs, ALL, CHECKS]);

    const w = c.expect, tag = `${c.sport} · ${c.name}`;
    const confident = w.band !== 'COIN FLIP';
    chk(got.side === w.side, `${tag}: ${w.side}`, `page said ${got.side}`);
    chk(got.band === w.band, `${tag}: ${w.band}`, `page said ${got.band}`);
    chk(Math.abs(got.pResolved - w.p_resolved) < 1e-4,
        `${tag}: resolved ${(w.p_resolved * 100).toFixed(2)}%`,
        `page said ${(got.pResolved * 100).toFixed(4)}%`);
    chk(Math.abs(got.pPush - w.p_push) < 1e-4,
        `${tag}: push ${(w.p_push * 100).toFixed(2)}%`,
        `page said ${(got.pPush * 100).toFixed(4)}%`);
    chk(Math.abs(got.projected - w.projected) < 1e-6,
        `${tag}: projected ${w.projected.toFixed(4)}`, `page said ${got.projected}`);
    chk(Math.abs(got.fair - w.fair) < 0.05,
        `${tag}: fair ${w.fair.toFixed(1)}`, `page said ${got.fair}`);
    chk(Math.abs(got.pct - got.pResolved * 100) < 0.051,
        `${tag}: the headline percent is the resolved one`,
        `shown ${got.pct}% vs ${(got.pResolved * 100).toFixed(3)}%`);
    chk(got.estimates === w.estimates, `${tag}: ${w.estimates} estimates`,
        `page drew ${got.estimates}`);
    chk(got.deltas === w.deltas, `${tag}: ${w.deltas} deltas`, `page drew ${got.deltas}`);
    chk(got.hot === confident && got.bandHot === confident,
        `${tag}: green only when it is confident`,
        `hot=${got.hot} band=${got.bandHot} for ${w.band}`);
  }

  // ---- the card: store, grade, calibrate, reload -----------------------
  const card = await pg.evaluate(async () => {
    const set = (id, v) => {
      const el = document.getElementById(id);
      el.value = String(v);
      el.dispatchEvent(new Event('input', { bubbles: true }));
    };
    document.getElementById('m-mlb').click();
    document.getElementById('clear').click();
    set('away', 'Orioles'); set('home', 'Rockies'); set('line', 11.5);
    set('mph', 20); set('dir', 'out');
    await new Promise(r => setTimeout(r, 50));
    document.getElementById('add').click();
    await new Promise(r => setTimeout(r, 50));

    // grade it a loser: 8 runs on a line of 11.5 with an OVER call
    const g = document.querySelector('[data-final="0"]');
    g.value = '8';
    g.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise(r => setTimeout(r, 60));
    const loss = document.querySelector('#cardTable .res').textContent.trim();

    // now a push: line 8, final 8
    document.getElementById('clear').click();
    set('away', 'Push'); set('home', 'Game'); set('line', 8);
    await new Promise(r => setTimeout(r, 50));
    document.getElementById('add').click();
    await new Promise(r => setTimeout(r, 50));
    const g2 = document.querySelector('[data-final="0"]');
    g2.value = '8';
    g2.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise(r => setTimeout(r, 60));
    return {
      first: loss,
      push: document.querySelectorAll('#cardTable .res')[0].textContent.trim(),
      calib: document.getElementById('calibBox').textContent,
      rows: JSON.parse(localStorage.getItem('callsheet.fullgame.card.v1') || '[]').length,
    };
  });
  chk(card.first === 'LOSS', 'card: an over that missed grades as a loss', card.first);
  chk(card.push === 'PUSH', 'card: a final on the number grades as a push', card.push);
  chk(card.rows === 2, 'card: both games stored', String(card.rows));
  chk(/push\(es\) excluded|correctly excluded/.test(card.calib),
      'calibration: the push is excluded rather than counted either way', card.calib.slice(0, 160));
  chk(/not enough to judge/.test(card.calib),
      'calibration: a short run refuses to judge', card.calib.slice(0, 160));

  await pg.reload();
  await pg.waitForTimeout(400);
  const after = await pg.evaluate(() => ({
    away: document.getElementById('away').value,
    rows: document.querySelectorAll('#cardTable tbody tr').length,
    graded: [...document.querySelectorAll('#cardTable .res')].map(e => e.textContent.trim()),
  }));
  chk(after.away === 'Push', 'draft: the half-typed game survived a reload', after.away);
  chk(after.rows === 2, 'card: it survived a reload', String(after.rows));
  chk(after.graded.includes('PUSH') && after.graded.includes('LOSS'),
      'card: the grades survived too', after.graded.join(','));

  if (errs.length) { console.log('PAGE ERRORS:\n' + errs.join('\n')); fails++; }
  console.log(fails ? `\n${fails} FAILED` : `\nall checks passed (${CASES.length} cases)`);
  await b.close();
  process.exit(fails ? 1 : 0);
})();
