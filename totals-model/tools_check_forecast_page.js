/* Replays web/forecast-cases.json through web/forecast.html in a real browser
 * and asserts the page reaches the same call the Python package reached.
 *
 * The fixtures come from totals/forecast.py, so a failure here means the
 * page's arithmetic has drifted from the model's — the bug this project has
 * shipped more often than any other, and the reason both sides get checked
 * rather than just the one with unit tests.
 *
 * The probability tolerance is 1e-4. Python uses math.erf; the browser uses
 * Abramowitz & Stegun 7.1.26, whose worst-case error is 1.5e-7. Anything
 * larger than that is a real disagreement, not floating point.
 *
 *   node tools_check_forecast_page.js
 */
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const CASES = JSON.parse(
  fs.readFileSync(path.join(__dirname, 'web/forecast-cases.json'), 'utf8'));

const MLB_IDS = ["away", "home", "line", "gdate", "aera", "hera", "arpg", "hrpg",
                 "al5", "hl5", "h2h", "h2hn", "pf", "mph", "dir", "temp"];
const WNBA_IDS = ["away", "home", "line", "gdate", "al10", "hl10", "wh2h", "wh2hn",
                  "aout", "hout"];
const ALL = [...new Set([...MLB_IDS, ...WNBA_IDS])];
const CHECKS = ["dome", "alead", "hlead"];

(async () => {
  // The sandbox's pre-installed Chromium, rather than the build the pinned
  // Playwright would go and download.
  const b = await chromium.launch({
    executablePath: process.env.CHROMIUM_PATH || '/opt/pw-browsers/chromium',
  });
  const pg = await b.newPage({ viewport: { width: 1280, height: 1400 } });
  const errs = [];
  pg.on('pageerror', e => errs.push(String(e)));
  pg.on('console', m => {
    // Google Fonts cannot be reached offline; it loads in the published
    // artifact and the page has a real fallback stack either way.
    const where = (m.location() && m.location().url) || '';
    if (m.type() === 'error' && !/fonts\.(googleapis|gstatic)\.com/.test(where + ' ' + m.text())) {
      errs.push('console: ' + m.text());
    }
  });
  await pg.goto('file://' + path.join(__dirname, 'web/forecast.html'));
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
      await new Promise(r => setTimeout(r, 60));

      const pick = document.querySelector('#call .pick');
      const pct = document.querySelector('#call .pct');
      const proj = document.querySelectorAll('#call .nums .v')[0];
      const call = document.getElementById('call');
      return {
        band: document.querySelector('#call .band').textContent.trim(),
        side: pick ? pick.textContent.trim().split(' ')[0] : null,
        pct: pct ? parseFloat(pct.textContent) : null,
        // exact values, not the rounded display
        pOver: call.dataset.pOver === undefined ? null : parseFloat(call.dataset.pOver),
        projected: call.dataset.projected === undefined ? null : parseFloat(call.dataset.projected),
        shownProjected: proj ? parseFloat(proj.textContent) : null,
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
    const pSideOnPage = w.side === 'OVER' ? got.pOver : 1 - got.pOver;

    chk(got.side === w.side, `${tag}: ${w.side}`, `page said ${got.side}`);
    chk(got.band === w.band, `${tag}: ${w.band}`, `page said ${got.band}`);
    chk(Math.abs(pSideOnPage - w.p_side) < 1e-4,
        `${tag}: ${(w.p_side * 100).toFixed(1)}%`,
        `page said ${(pSideOnPage * 100).toFixed(4)}%`);
    chk(Math.abs(got.projected - w.projected) < 1e-6,
        `${tag}: projected ${w.projected.toFixed(4)}`, `page said ${got.projected}`);
    // and the rounded headline still has to match what it claims
    chk(Math.abs(got.pct - pSideOnPage * 100) < 0.051,
        `${tag}: the headline percent matches the exact one`,
        `shown ${got.pct}% vs ${(pSideOnPage * 100).toFixed(4)}%`);
    chk(got.estimates === w.estimates, `${tag}: ${w.estimates} estimates`,
        `page drew ${got.estimates}`);
    chk(got.deltas === w.deltas, `${tag}: ${w.deltas} deltas`, `page drew ${got.deltas}`);
    // Green means confident, and only that.
    chk(got.hot === confident && got.bandHot === confident,
        `${tag}: green only when it is confident`,
        `hot=${got.hot} band=${got.bandHot} for ${w.band}`);
  }

  // The card has to survive a reload and click back into the form, which is
  // what makes it a record rather than a scrollback.
  const round = await pg.evaluate(async () => {
    document.getElementById('m-wnba').click();
    const set = (id, v) => {
      const el = document.getElementById(id);
      el.value = String(v);
      el.dispatchEvent(new Event('input', { bubbles: true }));
    };
    set('away', 'Storm'); set('home', 'Dream'); set('line', 158.5);
    set('al10', 166.0); set('hl10', 169.5);
    await new Promise(r => setTimeout(r, 60));
    document.getElementById('add').click();
    const stored = JSON.parse(localStorage.getItem('callsheet.card.v1') || '[]');

    // wipe the form, then click the row back open
    document.getElementById('clear').click();
    await new Promise(r => setTimeout(r, 60));
    const blank = document.getElementById('al10').value;
    document.querySelector('[data-open="0"]').click();
    await new Promise(r => setTimeout(r, 80));
    return {
      rows: stored.length,
      matchup: stored[0] && stored[0].matchup,
      side: stored[0] && stored[0].side,
      blank,
      restoredLine: document.getElementById('line').value,
      restoredForm: document.getElementById('al10').value,
      sportRestored: document.getElementById('m-wnba').getAttribute('aria-pressed'),
    };
  });
  chk(round.rows === 1, 'card: the game was stored', JSON.stringify(round));
  chk(round.matchup === 'Storm @ Dream', 'card: matchup kept', round.matchup);
  chk(round.blank === '', 'card: clear really emptied the form', `got ${round.blank}`);
  chk(round.restoredLine === '158.5' && round.restoredForm === '166',
      'card: clicking a row loads the game back in',
      `line=${round.restoredLine} form=${round.restoredForm}`);
  chk(round.sportRestored === 'true', 'card: the row restores its own sport',
      round.sportRestored);

  // The draft has to survive a reload. This is the failure a user is most
  // likely to hit — close the tab half way through entering a game — and the
  // reason the form is written to storage on every keystroke.
  const draft = await pg.evaluate(async () => {
    document.getElementById('m-mlb').click();
    const set = (id, v) => {
      const el = document.getElementById(id);
      el.value = String(v);
      el.dispatchEvent(new Event('input', { bubbles: true }));
    };
    set('away', 'Cubs'); set('home', 'Reds'); set('line', 4.5); set('aera', 3.33);
    await new Promise(r => setTimeout(r, 60));
    return JSON.parse(localStorage.getItem('callsheet.draft.v1') || 'null');
  });
  chk(draft && draft.inputs && draft.inputs.away === 'Cubs' && draft.inputs.aera === '3.33',
      'draft: half-typed inputs are written to storage', JSON.stringify(draft));
  chk(draft && draft.sport === 'MLB_F5', 'draft: the sport is stored with it',
      draft && draft.sport);

  await pg.reload();
  await pg.waitForTimeout(400);
  const afterReload = await pg.evaluate(() => ({
    away: document.getElementById('away').value,
    aera: document.getElementById('aera').value,
    line: document.getElementById('line').value,
    mlb: document.getElementById('m-mlb').getAttribute('aria-pressed'),
    band: document.querySelector('#call .band').textContent.trim(),
    cardRows: document.querySelectorAll('#cardTable tbody tr').length,
  }));
  chk(afterReload.away === 'Cubs' && afterReload.aera === '3.33' && afterReload.line === '4.5',
      'draft: it all comes back after a reload', JSON.stringify(afterReload));
  chk(afterReload.mlb === 'true', 'draft: the sport comes back too', afterReload.mlb);
  chk(afterReload.cardRows === 1, 'card: it survived the reload as well',
      String(afterReload.cardRows));

  // A backup has to round-trip, and loading one must not wipe what is already
  // on the machine.
  const backup = await pg.evaluate(async () => {
    const before = JSON.parse(localStorage.getItem('callsheet.card.v1') || '[]');
    // build a backup by hand in the same shape the page writes
    const blob = JSON.stringify({
      format: 'callsheet.backup', version: 1, savedAt: new Date().toISOString(),
      card: [{ matchup: 'Aces @ Liberty', sport: 'WNBA', line: 164.5, projected: '167.0',
               side: 'OVER', prob: '58.0', band: 'STRONG', inputs: {} }],
      draft: { sport: 'WNBA', inputs: {} },
    });
    const file = new File([blob], 'backup.json', { type: 'application/json' });
    const dt = new DataTransfer();
    dt.items.add(file);
    const input = document.getElementById('restoreFile');
    input.files = dt.files;
    input.dispatchEvent(new Event('change', { bubbles: true }));
    await new Promise(r => setTimeout(r, 250));
    return {
      before: before.length,
      after: JSON.parse(localStorage.getItem('callsheet.card.v1') || '[]').length,
      msg: document.getElementById('saveMsg').textContent,
    };
  });
  chk(backup.after === backup.before + 1,
      'backup: loading one merges rather than replaces',
      `${backup.before} -> ${backup.after}`);
  chk(/added to the card/.test(backup.msg), 'backup: it says what it did', backup.msg);

  const junk = await pg.evaluate(async () => {
    const before = JSON.parse(localStorage.getItem('callsheet.card.v1') || '[]').length;
    const file = new File(['not json at all'], 'x.json', { type: 'application/json' });
    const dt = new DataTransfer();
    dt.items.add(file);
    const input = document.getElementById('restoreFile');
    input.files = dt.files;
    input.dispatchEvent(new Event('change', { bubbles: true }));
    await new Promise(r => setTimeout(r, 250));
    return {
      before,
      after: JSON.parse(localStorage.getItem('callsheet.card.v1') || '[]').length,
      msg: document.getElementById('saveMsg').textContent,
    };
  });
  chk(junk.after === junk.before, 'backup: a junk file changes nothing',
      `${junk.before} -> ${junk.after}`);
  chk(/not a Call Sheet backup/.test(junk.msg), 'backup: it says the file was wrong', junk.msg);

  if (errs.length) { console.log('PAGE ERRORS:\n' + errs.join('\n')); fails++; }
  console.log(fails ? `\n${fails} FAILED` : `\nall checks passed (${CASES.length} cases)`);
  await b.close();
  process.exit(fails ? 1 : 0);
})();
