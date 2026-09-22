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
const { execSync } = require('child_process');

const CASES = JSON.parse(
  fs.readFileSync(path.join(__dirname, 'web/fullgame-cases.json'), 'utf8'));

const MLB_IDS = ["away","home","line","op","up","opened","gdate","aera","hera","aip","hip","arpg","hrpg",
                 "abp","hbp","al10","hl10","h2h","h2hn","pf","mph","dir","temp","tick","cash"];
const WNBA_IDS = ["away","home","line","op","up","opened","gdate",
                  "apace","hpace","aort","hort","adrt","hdrt","arest","hrest","al5","hl5"];
const ALL = [...new Set([...MLB_IDS, ...WNBA_IDS])];
const CHECKS = ["dome", "playoff"];

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
        band: call.dataset.band,
        side: pick ? pick.textContent.trim().split(' ')[0] : null,
        pct: pct ? parseFloat(pct.textContent) : null,
        pctLevel: pct ? (['lv1', 'lv2', 'lv3'].find(c => pct.classList.contains(c)) || '') : null,
        core: (() => {
          const el = document.querySelector('#call .core');
          return el ? parseFloat(el.textContent.replace(/[^0-9.]/g, '')) : null;
        })(),
        text: call.textContent,
        pOver: parseFloat(call.dataset.pOver),
        pPush: parseFloat(call.dataset.pPush),
        pResolved: parseFloat(call.dataset.pResolved),
        projected: parseFloat(call.dataset.projected),
        projectedCore: parseFloat(call.dataset.projectedCore),
        pCorroborated: parseFloat(call.dataset.pCorroborated),
        bandUngated: call.dataset.bandUngated,
        held: !!document.querySelector('#call .held'),
        fair: parseFloat(call.dataset.fair),
        estimates: document.querySelectorAll('#est .erow').length,
        deltas: document.getElementById('deltaCard').hidden
          ? 0 : document.querySelectorAll('#deltas .drow').length,
        hot: call.classList.contains('hot'),
      };
    }, [c.sport, c.inputs, ALL, CHECKS]);

    const w = c.expect, tag = `${c.sport} · ${c.name}`;
    const confident = w.band !== 'NO BET';
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
    // The corroboration gate: the browser must reach the same held band, the
    // same core projection and the same core probability as the package.
    chk(got.bandUngated === w.band_ungated,
        `${tag}: ungated band ${w.band_ungated}`, `page said ${got.bandUngated}`);
    chk(Math.abs(got.projectedCore - w.projected_core) < 1e-6,
        `${tag}: core projection ${w.projected_core.toFixed(4)}`,
        `page said ${got.projectedCore}`);
    chk(Math.abs(got.pCorroborated - w.p_corroborated) < 1e-4,
        `${tag}: corroborated ${(w.p_corroborated * 100).toFixed(2)}%`,
        `page said ${(got.pCorroborated * 100).toFixed(4)}%`);
    chk(got.held === (w.band !== w.band_ungated),
        `${tag}: the core chip is flagged amber only when the gate bites`,
        `held=${got.held} band=${w.band} ungated=${w.band_ungated}`);
    // The core read replaced the verdict word as the banner's warning, so it
    // has to be on every card, not only the held ones.
    chk(Math.abs(got.core - w.p_corroborated * 100) < 0.051,
        `${tag}: the core chip shows ${(w.p_corroborated * 100).toFixed(1)}%`,
        `chip said ${got.core}`);
    chk(Math.abs(got.fair - w.fair) < 0.05,
        `${tag}: fair ${w.fair.toFixed(1)}`, `page said ${got.fair}`);
    chk(Math.abs(got.pct - got.pResolved * 100) < 0.051,
        `${tag}: the headline percent is the resolved one`,
        `shown ${got.pct}% vs ${(got.pResolved * 100).toFixed(3)}%`);
    chk(got.estimates === w.estimates, `${tag}: ${w.estimates} estimates`,
        `page drew ${got.estimates}`);
    chk(got.deltas === w.deltas, `${tag}: ${w.deltas} deltas`, `page drew ${got.deltas}`);
    chk(got.hot === confident,
        `${tag}: green only when it is confident`, `hot=${got.hot} for ${w.band}`);
    // The verdict word is gone from the banner; the colour of the headline
    // carries it instead, at the same floors the bands have always used.
    const lvl = w.p_resolved >= 0.62 ? 'lv3' : w.p_resolved >= 0.57 ? 'lv2'
              : w.p_resolved >= 0.53 ? 'lv1' : '';
    chk(got.pctLevel === lvl, `${tag}: the headline is tinted ${lvl || 'plain'}`,
        `page used ${got.pctLevel || 'plain'} at ${(w.p_resolved * 100).toFixed(1)}%`);
    chk(!/\bNO BET\b|\bMAX BET\b|\bSTRONG BET\b/.test(got.text),
        `${tag}: the banner does not print a verdict`,
        got.text.slice(0, 120));
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

  // ---- rescoring a card scored by an older build -----------------------
  // The real failure this guards: two pre-gate STRONGs sat in a live card the
  // gate would have refused, because a row keeps the band it was added with.
  const rescore = await pg.evaluate(async () => {
    const inputs = {
      away: 'Tigers', home: 'Guardians', line: '8.0', op: '-120', up: '100',
      aera: '3.24', hera: '3.77', arpg: '4.05', hrpg: '4.12',
      abp: '4.00', hbp: '3.73', al10: '9.0', hl10: '8.9',
      h2h: '6.4', h2hn: '9', pf: '98', mph: '6', dir: 'cross', temp: '76',
      tick: '67', cash: '38', dome: false,
    };
    // Stored as an older build scored it: UNDER, LEAN.
    localStorage.setItem('callsheet.fullgame.card.v1', JSON.stringify([{
      matchup: 'Tigers @ Guardians', sport: 'MLB', line: 8.0, projected: '8.16',
      side: 'UNDER', prob: '54.0', band: 'BET', fair: '-117', final: '12', inputs,
    }]));
  }).then(() => pg.reload()).then(() => pg.waitForTimeout(450)).then(() => pg.evaluate(() => {
    const before = {
      band: document.querySelector('#cardTable td:nth-child(8) .chip').textContent.trim(),
      stale: (document.querySelector('#cardTable .chip.stale') || {}).textContent,
      result: document.querySelector('#cardTable .res').textContent.trim(),
    };
    document.getElementById('rescore').click();
    return new Promise(r => setTimeout(() => r({
      before,
      after: document.querySelector('#cardTable td:nth-child(8) .chip').textContent.trim(),
      stillStale: !!document.querySelector('#cardTable .chip.stale'),
      result: document.querySelector('#cardTable .res').textContent.trim(),
      final: document.querySelector('[data-final="0"]').value,
      msg: document.getElementById('saveMsg').textContent,
    }), 250));
  }));
  chk(rescore.before.band === 'BET', 'rescore: the stored band is shown as stored',
      rescore.before.band);
  chk(/now NO BET/.test(rescore.before.stale || ''),
      'rescore: a row the current model scores differently is marked stale',
      String(rescore.before.stale));
  chk(rescore.after === 'NO BET', 'rescore: pressing it adopts the current model',
      rescore.after);
  chk(!rescore.stillStale, 'rescore: the stale mark clears once rescored',
      String(rescore.stillStale));
  chk(rescore.final === '12' && rescore.result === 'LOSS',
      'rescore: the final and its grade are never touched',
      `final=${rescore.final} result=${rescore.result}`);

  await pg.evaluate(() => localStorage.clear());
  await pg.reload();
  await pg.waitForTimeout(400);

  // ---- the per-band record --------------------------------------------
  // Loads a known card straight into storage and reloads, so the expected
  // win/loss/push per band is arithmetic rather than whatever the engine
  // happens to say for some inputs.
  await pg.evaluate(() => {
    const mk = (band, prob, line, final) =>
      ({ matchup: band + ' ' + final, sport: 'MLB', line, projected: '9.00',
         side: 'OVER', prob, band, fair: '-120', final, inputs: {} });
    localStorage.setItem('callsheet.fullgame.card.v1', JSON.stringify([
      mk('STRONG BET', '58.0', 8.5, '10'),      // over, covered
      mk('STRONG BET', '59.0', 8.5, '10'),      // over, covered
      mk('BET', '54.0', 8.5, '4'),         // under, missed
      mk('BET', '55.0', 8.5, '12'),        // over, covered
      mk('NO BET', '51.0', 8.5, '2'),    // under, missed
      mk('NO BET', '52.0', 8, '8'),      // push
    ]));
  });
  await pg.reload();
  await pg.waitForTimeout(400);
  const bands = await pg.evaluate(() => ({
    table: [...document.querySelectorAll('#calibBox table tbody tr')].map(
      r => [...r.querySelectorAll('td')].map(c => c.textContent.trim())),
  }));
  const row = n => (bands.table.find(r => r[0] === n) || []);
  chk(row('STRONG BET')[1] === '2-0', 'bands: STRONG BET covered 2, missed 0', JSON.stringify(row('STRONG BET')));
  chk(row('BET')[1] === '1-1', 'bands: BET covered 1, missed 1', JSON.stringify(row('BET')));
  chk(row('NO BET')[1] === '0-1',
      'bands: NO BET covered 0, missed 1 — the push is not counted as either',
      JSON.stringify(row('NO BET')));
  chk(row('NO BET')[5] === '1', 'bands: the push is reported in its own column',
      JSON.stringify(row('NO BET')));
  chk(row('STRONG BET')[2] === '100%' && row('BET')[2] === '50%',
      'bands: the hit rate matches the record', JSON.stringify(bands.table));

  // The card reads the way the banner does: the probability carries the colour,
  // at the band floors, so the eye finds the likely games without the verdict.
  const tint = await pg.evaluate(() =>
    [...document.querySelectorAll('#cardTable tbody tr')].map(r => {
      const el = r.querySelector('.plv');
      return el ? el.textContent.trim() + ':' +
        (['lv1', 'lv2', 'lv3'].find(c => el.classList.contains(c)) || 'plain') : 'none';
    }));
  chk(JSON.stringify(tint) === JSON.stringify(
        ['58.0%:lv2', '59.0%:lv2', '54.0%:lv1', '55.0%:lv1', '51.0%:plain', '52.0%:plain']),
      'card: the probability column is tinted at the band floors', JSON.stringify(tint));
  chk(!row('MAX BET').length, 'bands: a band with no graded games is left out',
      JSON.stringify(bands.table));

  await pg.evaluate(() => localStorage.clear());
  await pg.reload();
  await pg.waitForTimeout(400);

  // ---- the roof marker -------------------------------------------------
  // Runs last: it adds rows, so it must not disturb the counts asserted above.
  const roof = await pg.evaluate(async () => {
    const set = (id, v) => {
      const el = document.getElementById(id);
      el.value = String(v);
      el.dispatchEvent(new Event('input', { bubbles: true }));
    };
    const add = async () => {
      await new Promise(r => setTimeout(r, 50));
      document.getElementById('add').click();
      await new Promise(r => setTimeout(r, 60));
    };
    const first = () => document.querySelector('#cardTable tbody tr .openbtn');

    document.getElementById('m-mlb').click();
    document.getElementById('clear').click();
    set('away', 'Rays'); set('home', 'Astros'); set('line', 8.5);
    document.getElementById('dome').checked = true;
    document.getElementById('dome').dispatchEvent(new Event('change', { bubbles: true }));
    await add();
    const domed = first().textContent.trim();

    // The box stays ticked across a sport switch; a WNBA row must not inherit
    // it -- a basketball game has no roof to shut.
    document.getElementById('m-wnba').click();
    set('away', 'Aces'); set('home', 'Lynx'); set('line', 161.5);
    await add();
    const wnba = first().textContent.trim();

    document.getElementById('m-mlb').click();
    document.getElementById('clear').click();
    set('away', 'Cubs'); set('home', 'Reds'); set('line', 9);
    await add();

    return {
      domed, wnba,
      open: first().textContent.trim(),
      chips: document.querySelectorAll('#cardTable .chip.dome').length,
      count: document.getElementById('cardCount').textContent.trim(),
    };
  });
  // Matches the CHIP, not a string suffix. It used to assert /Dome$/, which
  // broke the moment a second chip (missing inputs) could follow it on the
  // same row -- the assertion was over-specific, not the page wrong.
  chk(/\bDome\b/.test(roof.domed), 'roof: a game with the roof shut is marked on the card', roof.domed);
  chk(!/Dome/.test(roof.open), 'roof: an open-air game is not marked', roof.open);
  chk(!/Dome/.test(roof.wnba), 'roof: a WNBA row does not inherit a left-over tick', roof.wnba);
  chk(roof.chips === 1, 'roof: exactly one row carries the marker', String(roof.chips));
  chk(/1 under a roof/.test(roof.count), 'roof: the header counts the domed games', roof.count);

  // ---- team names are merged to one spelling per club --------------------
  // A free-text box had produced fifty spellings of thirty MLB clubs across
  // the logged card, which manufactures perfect records out of nothing when
  // anything is grouped by team.
  const teams = await pg.evaluate(async () => {
    const shown = (name, sport) => {
      document.getElementById(sport === 'WNBA' ? 'm-wnba' : 'm-mlb').click();
      const a = document.getElementById('away'), h = document.getElementById('home'),
            l = document.getElementById('line');
      a.value = name; h.value = 'Rockies';
      l.value = sport === 'WNBA' ? '161.5' : '8.5';
      [a, h, l].forEach(e => e.dispatchEvent(new Event('input', { bubbles: true })));
      const el = document.querySelector('.cline b');
      return el ? el.textContent.split(' @ ')[0] : null;
    };
    const spellings = ['St Louis Cardinals', 'St Louis', 'ST louis Cardinals',
                       'Cardinals', 'St Louis Cardninals', 'Cardinals '];
    const out = {
      stl: [...new Set(spellings.map(s => shown(s, 'MLB')))],
      typos: [shown('Cleveland Gaurdians', 'MLB'), shown('Houston Astro', 'MLB'),
              shown('Boston RedSox', 'MLB'), shown('Cincinnati Red', 'MLB'),
              shown('Chicago WhiteSox', 'MLB')],
      // the same city is a different club in each league
      chicago: [shown('Chicago Cubs', 'MLB'), shown('Chicago Sky', 'WNBA')],
      lv: [shown('Las Vegas', 'WNBA'), shown('Seattle', 'WNBA')],
      gs: [shown('Golden State', 'WNBA'), shown('Connecticut', 'WNBA')],
      // ambiguous or unknown input must survive untouched
      ambiguous: ['Chicago', 'LA', 'NY', 'Some Local Nine'].map(s => shown(s, 'MLB')),
    };
    document.getElementById('m-mlb').click();
    out.mlbList = [...document.getElementById('teamList').options].map(o => o.value);
    document.getElementById('m-wnba').click();
    out.wnbaList = [...document.getElementById('teamList').options].map(o => o.value);
    document.getElementById('m-mlb').click();
    return out;
  });
  chk(teams.stl.length === 1 && teams.stl[0] === 'Cardinals',
      'teams: six spellings of St Louis collapse to one', teams.stl.join('|'));
  chk(JSON.stringify(teams.typos) ===
      JSON.stringify(['Guardians', 'Astros', 'Red Sox', 'Reds', 'White Sox']),
      'teams: typos and run-together names resolve, and red/sox does not collide',
      teams.typos.join('|'));
  chk(JSON.stringify(teams.chicago) === JSON.stringify(['Cubs', 'Sky']),
      'teams: a city maps by sport, not globally', teams.chicago.join('|'));
  chk(JSON.stringify(teams.lv) === JSON.stringify(['Aces', 'Storm']),
      'teams: the WNBA roster resolves by city', teams.lv.join('|'));
  chk(JSON.stringify(teams.gs) === JSON.stringify(['Valkyries', 'Sun']),
      'teams: including the expansion side', teams.gs.join('|'));
  chk(JSON.stringify(teams.ambiguous) ===
      JSON.stringify(['Chicago', 'LA', 'NY', 'Some Local Nine']),
      'teams: ambiguous and unknown input is left exactly as typed',
      teams.ambiguous.join('|'));
  chk(teams.mlbList.length === 30, 'teams: the MLB list offers all thirty clubs',
      String(teams.mlbList.length));
  chk(teams.wnbaList.length === 13, 'teams: the WNBA list offers all thirteen clubs',
      String(teams.wnbaList.length));

  // ---- the one-time backfill of rows logged before normalisation ---------
  // It must rewrite the NAME and nothing else. A migration that moved a final
  // or a grade would make the calibration panel unfalsifiable.
  await pg.evaluate(() => {
    localStorage.setItem('callsheet.fullgame.card.v1', JSON.stringify([
      { matchup: 'St Louis Cardninals @ Cincinnati Red', sport: 'MLB', line: 8.5,
        projected: '9.10', side: 'OVER', prob: '55.5', band: 'BET', fair: '-125',
        final: '11', inputs: { away: 'St Louis Cardninals', home: 'Cincinnati Red',
                               line: '8.5', op: '-110', up: '-110' } },
      { matchup: 'Some Local Nine @ Chicago', sport: 'MLB', line: 7.5,
        projected: '8.00', side: 'UNDER', prob: '52.0', band: 'NO BET', fair: '-104',
        final: '6', inputs: { away: 'Some Local Nine', home: 'Chicago',
                              line: '7.5', op: '-110', up: '-110' } },
    ]));
  });
  await pg.reload();
  await pg.waitForTimeout(400);
  const mig = await pg.evaluate(() => {
    const rows = JSON.parse(localStorage.getItem('callsheet.fullgame.card.v1') || '[]');
    return {
      matchups: rows.map(r => r.matchup),
      finals: rows.map(r => r.final),
      bands: rows.map(r => r.band),
      probs: rows.map(r => r.prob),
      grades: [...document.querySelectorAll('#cardTable .res')].map(e => e.textContent.trim()),
    };
  });
  chk(mig.matchups[0] === 'Cardinals @ Reds',
      'backfill: a messy stored row is merged to canonical names', mig.matchups[0]);
  chk(mig.matchups[1] === 'Some Local Nine @ Chicago',
      'backfill: a row it cannot resolve is left untouched', mig.matchups[1]);
  chk(JSON.stringify(mig.finals) === JSON.stringify(['11', '6']),
      'backfill: the finals are not touched', mig.finals.join('|'));
  chk(JSON.stringify(mig.bands) === JSON.stringify(['BET', 'NO BET']),
      'backfill: the stored bands are not touched', mig.bands.join('|'));
  chk(JSON.stringify(mig.probs) === JSON.stringify(['55.5', '52.0']),
      'backfill: the stored probabilities are not touched', mig.probs.join('|'));
  chk(JSON.stringify(mig.grades) === JSON.stringify(['WIN', 'WIN']),
      'backfill: the grades still read the same', mig.grades.join('|'));

  // ---- the guard is measured, not remembered -----------------------------
  // It replaced a hardcoded OVERCONFIDENCE = 3.0 whose comment claimed a live
  // measurement that had since gone stale.
  const seed = async (rows) => {
    await pg.evaluate((rows) => {
      localStorage.setItem('callsheet.fullgame.card.v1', JSON.stringify(rows));
    }, rows);
    await pg.reload();
    await pg.waitForTimeout(300);
    return pg.evaluate(() => {
      const g = document.getElementById('guardNote'), s = document.getElementById('spreadNote');
      return {
        guard: g ? g.textContent : null,
        spread: s ? s.textContent : null,
        margin: (document.querySelectorAll('.cline')[1] || {}).textContent || '',
      };
    });
  };
  const mk = (prob, line, final) => ({
    matchup: 'Reds @ Cubs', sport: 'MLB', line, projected: '9.0', side: 'OVER',
    prob: String(prob), band: 'BET', fair: '-120', final: String(final),
    inputs: { away: 'Reds', home: 'Cubs', line: String(line), op: '-110', up: '-110' },
  });

  // an ungraded card cannot establish any margin
  const none = await seed([{ ...mk(55, 8.5, 9), final: null }]);
  chk(none.guard === null, 'guard: an ungraded card prints no measured guard',
      String(none.guard));

  // a perfectly calibrated long card: bias 0, guard is pure noise and small
  const calm = [];
  for (let i = 0; i < 400; i++) calm.push(mk(55, 8.5, i % 100 < 55 ? 9 : 8));
  const good = await seed(calm);
  chk(/Margin guard: 2\.5 points/.test(good.guard),
      'guard: 400 calibrated calls give a 2.5-point guard, all of it noise',
      good.guard);
  chk(/overconfidence 0\.0 points/i.test(good.guard),
      'guard: beating your stated number does not earn a thinner bet', good.guard);

  // an overconfident card carries the bias on top of the noise
  const hot = [];
  for (let i = 0; i < 400; i++) hot.push(mk(70, 8.5, i % 100 < 45 ? 9 : 8));
  const bad = await seed(hot);
  chk(/overconfidence 2[45]\.\d points/i.test(bad.guard),
      'guard: a measured overconfidence is carried in full', bad.guard);
  chk(parseFloat(bad.guard.match(/Margin guard: ([\d.]+)/)[1]) > 25,
      'guard: and the guard exceeds it once noise is added', bad.guard);

  // the dispersion check reports, and flags when the constant is outside
  chk(/assumes 4\.39/.test(bad.spread), 'spread: it names the constant in use', bad.spread);
  const tight = [];
  for (let i = 0; i < 200; i++) tight.push(mk(55, 8.5, i % 2 ? 9 : 8));
  const narrow = await seed(tight);
  chk(/outside/i.test(narrow.spread),
      'spread: a spread far from 4.39 is flagged rather than silently refitted',
      narrow.spread);
  chk(/assumes 4\.39/.test(narrow.spread),
      'spread: and the constant is still 4.39 — it reports, it never refits',
      narrow.spread);

  // ---- the date column ---------------------------------------------------
  // It must never be a day early. `new Date("2026-09-17")` parses as UTC
  // midnight and renders as the 16th anywhere west of Greenwich, so the page
  // splits the string instead of constructing a Date. This runs the browser in
  // a US Pacific timezone, where that bug WOULD show.
  const tzPage = await b.newPage({ timezoneId: 'America/Los_Angeles' });
  await tzPage.goto('file://' + path.join(__dirname, 'web/fullgame.html'));
  await tzPage.waitForTimeout(300);
  const dates = await tzPage.evaluate(async () => {
    const iso = d => d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') +
                     '-' + String(d.getDate()).padStart(2, '0');
    const today = iso(new Date());
    localStorage.setItem('callsheet.fullgame.card.v1', JSON.stringify([
      { matchup: 'Reds @ Cubs', sport: 'MLB', line: 8.5, projected: '9.0', side: 'OVER',
        prob: '55.0', band: 'BET', fair: '-120', final: null,
        inputs: { away: 'Reds', home: 'Cubs', line: '8.5', gdate: '2026-08-01' } },
      { matchup: 'Rays @ Jays', sport: 'MLB', line: 7.5, projected: '8.0', side: 'OVER',
        prob: '54.0', band: 'BET', fair: '-118', final: null,
        inputs: { away: 'Rays', home: 'Blue Jays', line: '7.5', gdate: today } },
      { matchup: 'Mets @ Phillies', sport: 'MLB', line: 8.5, projected: '9.0', side: 'OVER',
        prob: '53.0', band: 'BET', fair: '-113', final: null,
        inputs: { away: 'Mets', home: 'Phillies', line: '8.5', gdate: '' } },
    ]));
    location.reload();
    return null;
  });
  await tzPage.waitForTimeout(600);
  const dcol = await tzPage.evaluate(() => ({
    header: [...document.querySelectorAll('#cardTable th')].map(t => t.textContent.trim()),
    cells: [...document.querySelectorAll('#cardTable .gdate')].map(e => ({
      text: e.textContent.trim(), title: e.getAttribute('title'),
      today: e.classList.contains('today'),
    })),
  }));
  chk(dcol.header[1] === 'Date', 'date: the column sits next to the game',
      dcol.header.join('|'));
  chk(dcol.cells[0] && dcol.cells[0].text === 'Aug 1',
      'date: 2026-08-01 renders as Aug 1 in a US Pacific browser, not Jul 31',
      dcol.cells[0] && dcol.cells[0].text);
  chk(dcol.cells[0] && dcol.cells[0].title === '2026-08-01',
      'date: the full date is on the tooltip', dcol.cells[0] && dcol.cells[0].title);
  chk(dcol.cells[1] && dcol.cells[1].today === true,
      "date: today's game is marked", JSON.stringify(dcol.cells[1]));
  chk(dcol.cells[0] && dcol.cells[0].today === false,
      'date: another day is not marked as today', JSON.stringify(dcol.cells[0]));
  chk(dcol.cells[2] && dcol.cells[2].text === '\u2014',
      'date: a row with no date shows a dash rather than a wrong day',
      dcol.cells[2] && dcol.cells[2].text);
  await tzPage.close();

  // ---- the missing-input chip -------------------------------------------
  // A blank field does not warn you: the estimate just vanishes from the blend
  // and the row looks complete. Two rows sat blank through three re-saves.
  const seedRows = async (rows) => {
    await pg.evaluate((rows) => {
      localStorage.setItem('callsheet.fullgame.card.v1', JSON.stringify(rows));
    }, rows);
    await pg.reload();
    await pg.waitForTimeout(350);
    return pg.evaluate(() => ({
      count: document.getElementById('cardCount').textContent.trim(),
      rows: [...document.querySelectorAll('#cardTable tbody tr')].map(tr => {
        const c = tr.querySelector('.chip.gap');
        return { chip: c ? c.textContent.trim() : null,
                 why: c ? c.getAttribute('title') : null };
      }),
    }));
  };
  const gapRow = (name, extra) => ({
    matchup: name, sport: 'MLB', line: 8.5, projected: '9.0', side: 'OVER',
    prob: '55.0', band: 'BET', fair: '-120', final: null,
    inputs: Object.assign({
      away: 'Reds', home: 'Cubs', line: '8.5', gdate: '2026-08-01',
      op: '-115', up: '-105', aera: '3.9', hera: '4.1', abp: '3.8', hbp: '4.2',
      al10: '9.0', hl10: '9.2', arpg: '4.4', hrpg: '4.5', pf: '99',
      tick: '60', cash: '55',
    }, extra),
  });

  const gap = await seedRows([
    gapRow('Complete row', {}),
    gapRow('No runs per game', { arpg: '', hrpg: '' }),
    gapRow('One last ten', { al10: '' }),
    gapRow('Bad percentage', { cash: '925' }),
    gapRow('One price only', { up: '' }),
    gapRow('No prices at all', { op: '', up: '' }),
    gapRow('Optional stuff blank', { pf: '', tick: '', cash: '' }),
  ]);
  chk(gap.rows[0].chip === null, 'gaps: a complete row is not flagged', gap.rows[0].chip);
  chk(/a runs\/game/.test(gap.rows[1].why || ''), 'gaps: both runs/game blank is flagged',
      gap.rows[1].why);
  chk(/a last-10 total/.test(gap.rows[2].why || ''),
      'gaps: one last-10 blank is flagged, because the pair drops as a unit',
      gap.rows[2].why);
  chk(/bad percentage \(925\)/.test(gap.rows[3].why || ''),
      'gaps: a percentage over 100 is flagged as a typo', gap.rows[3].why);
  chk(gap.rows[4].chip === null,
      'gaps: ONE price is not flagged — the other side is reconstructed',
      gap.rows[4].why);
  chk(/both prices/.test(gap.rows[5].why || ''),
      'gaps: both prices missing IS flagged', gap.rows[5].why);
  chk(gap.rows[6].chip === null,
      'gaps: park and the public split are optional and are not flagged',
      gap.rows[6].why);
  chk(/4 with missing inputs/.test(gap.count),
      'gaps: the header counts the flagged rows', gap.count);

  // ---- the money split is shown and never scored ------------------------
  // It moved the projection a flat 0.30 runs on a 20-point gap. Over 172 logged
  // games that pointed the right way 27 of the 58 times it fired. It is a note
  // now, and the browser must agree with the package that it moves nothing.
  const split = await pg.evaluate(async () => {
    const base = { away: 'Reds', home: 'Cubs', line: '8.5', op: '-115', up: '-105',
                   aera: '3.9', hera: '4.1', abp: '3.8', hbp: '4.2',
                   arpg: '4.4', hrpg: '4.5' };
    const read = async (tick, cash) => {
      const all = Object.assign({}, base, { tick, cash });
      ['away','home','line','op','up','aera','hera','abp','hbp','arpg','hrpg','tick','cash',
       'al10','hl10','h2h','h2hn','pf','mph','temp','opened','gdate','aip','hip']
        .forEach(id => {
          const el = document.getElementById(id);
          el.value = all[id] === undefined ? '' : all[id];
          el.dispatchEvent(new Event('input', { bubbles: true }));
        });
      await new Promise(r => setTimeout(r, 40));
      const c = document.getElementById('call');
      return {
        proj: c.dataset.projected, p: c.dataset.pResolved, band: c.dataset.band,
        deltas: document.getElementById('deltaCard').hidden
          ? 0 : document.querySelectorAll('#deltas .drow').length,
        why: document.getElementById('why').textContent,
      };
    };
    return { none: await read('', ''), heavyUnder: await read('90', '30'),
             heavyOver: await read('30', '90'), quiet: await read('60', '55') };
  });
  chk(split.heavyUnder.proj === split.none.proj && split.heavyOver.proj === split.none.proj,
      'split: a 60-point gap either way moves the projection by exactly nothing',
      `none=${split.none.proj} under=${split.heavyUnder.proj} over=${split.heavyOver.proj}`);
  chk(split.heavyUnder.p === split.none.p && split.heavyUnder.band === split.none.band,
      'split: and it cannot move the probability or the band',
      `${split.heavyUnder.p}/${split.heavyUnder.band} vs ${split.none.p}/${split.none.band}`);
  chk(split.heavyUnder.deltas === split.none.deltas,
      'split: it is not a tonight-only adjustment any more',
      `${split.heavyUnder.deltas} vs ${split.none.deltas}`);
  chk(/60-point gap/.test(split.heavyUnder.why) && /NOT scored/.test(split.heavyUnder.why),
      'split: but a real gap is still reported, and says it was not scored',
      split.heavyUnder.why.slice(0, 160));
  chk(/big money on the under/.test(split.heavyUnder.why)
      && /big money on the over/.test(split.heavyOver.why),
      'split: the direction reads the right way round');
  chk(!/of tickets but/.test(split.quiet.why),
      'split: a gap under the threshold says nothing at all', split.quiet.why.slice(0, 120));

  // ---- what this total looks like ---------------------------------------
  // Replaced the alternate-line ladder. The chart is read off the same negative
  // binomial the banner's probability comes from, so the two must agree exactly
  // -- a picture that disagreed with the number above it would be worse than no
  // picture at all.
  const shape = await pg.evaluate(async () => {
    const fill = async (vals) => {
      ['away','home','line','op','up','aera','hera','abp','hbp','arpg','hrpg',
       'al10','hl10','h2h','h2hn','pf','mph','temp','tick','cash','opened','gdate','aip','hip']
        .forEach(id => {
          const el = document.getElementById(id);
          el.value = vals[id] === undefined ? '' : vals[id];
          el.dispatchEvent(new Event('input', { bubbles: true }));
        });
      await new Promise(r => setTimeout(r, 60));
      const c = document.getElementById('call');
      const rows = [...document.querySelectorAll('#shape .srow')].map(r => ({
        k: r.querySelector('.sk').textContent.trim(),
        p: parseFloat(r.querySelector('.sp').textContent) / 100,
        side: r.classList.contains('o') ? 'o'
            : r.classList.contains('push') ? 'push' : 'u',
        mark: r.querySelector('.sm').textContent.trim(),
      }));
      const sum = s => rows.filter(r => r.side === s)
                           .reduce((a, r) => a + r.p, 0);
      return {
        rows, over: sum('o'), under: sum('u'), push: sum('push'),
        pOver: parseFloat(c.dataset.pOver), pPush: parseFloat(c.dataset.pPush),
        lines: document.querySelectorAll('#shape .sline').length,
        read: document.getElementById('shapeRead').textContent,
        track: document.getElementById('trackRecord').textContent,
        hidden: document.getElementById('shapeCard').hidden,
      };
    };
    const base = { away: 'Braves', home: 'Astros', op: '100', up: '-130',
                   aera: '3.07', hera: '3.43', arpg: '3.87', hrpg: '4.79',
                   abp: '3.58', hbp: '4.20' };
    return { half: await fill(Object.assign({}, base, { line: '8.5' })),
             whole: await fill(Object.assign({}, base, { line: '9' })),
             // A card whose median lands ON a whole-number line, which is the
             // only case that is a push. Raising the line alone cannot do it:
             // the market anchor moves with the line, so the median follows.
             atLine: await fill({ away: 'Cubs', home: 'Reds', line: '9',
                                  op: '-110', up: '-110', aera: '3.90', hera: '4.60',
                                  arpg: '4.8', hrpg: '5.1', abp: '4.10', hbp: '4.80',
                                  al10: '5.1', hl10: '5.4', pf: '104', temp: '78' }) };
  });
  chk(shape.half.hidden === false, 'shape: the panel is drawn for an MLB card');
  // These sums are of the PRINTED percentages, each rounded to a tenth of a
  // point, so the tolerance has to be the accumulated rounding and nothing
  // tighter -- half a tenth per row. A fixed 0.002 failed at 23 rows and the
  // page was right.
  const slack = n => n * 0.0005 + 1e-9;
  chk(Math.abs(shape.half.over - shape.half.pOver) < slack(shape.half.rows.length),
      'shape: the bars above the line sum to the page\'s own OVER probability',
      `chart ${(shape.half.over * 100).toFixed(2)}% vs ${(shape.half.pOver * 100).toFixed(2)}%`);
  chk(Math.abs(shape.half.over + shape.half.under + shape.half.push - 1)
        < slack(shape.half.rows.length),
      'shape: and the whole chart sums to one',
      String(shape.half.over + shape.half.under + shape.half.push));
  chk(shape.half.push === 0 && shape.half.lines === 1,
      'shape: a half-run line has no push row and is drawn between two scores',
      `push=${shape.half.push} lines=${shape.half.lines}`);
  chk(Math.abs(shape.whole.push - shape.whole.pPush) < 0.001 && shape.whole.lines === 0,
      'shape: a whole-number line gets a push row matching the banner, and no rule',
      `push ${(shape.whole.push * 100).toFixed(2)}% vs ${(shape.whole.pPush * 100).toFixed(2)}%`);
  chk(shape.whole.rows.filter(r => r.mark === 'push').length === 1,
      'shape: the push row is labelled');
  chk(shape.half.rows.filter(r => r.mark === 'likeliest').length === 1,
      'shape: exactly one score is marked the likeliest');
  // The lesson the panel exists to teach: mean above median, and the crossing.
  chk(/9\.04/.test(shape.half.read),
      'shape: it names the projection the over needs on an 8.5 line',
      shape.half.read.slice(0, 200));
  chk(/10\.04/.test(shape.whole.read) === false && /9\.54/.test(shape.whole.read),
      'shape: and line + 0.543 on a 9', shape.whole.read.slice(0, 200));
  // The third tile is the crossing, not the modal score. The modal score
  // decides nothing and read as a contradiction on a card calling the over.
  chk(/Over needs/.test(shape.half.read) && !/Likeliest score/.test(shape.half.read),
      'shape: the third tile is the projection the over needs, not the modal score',
      shape.half.read.slice(0, 120));
  chk(/every score above the line added together/.test(shape.half.read),
      'shape: and it says in words that the over is a sum, not one bar',
      shape.half.read.slice(0, 200));
  chk(/Typical game\s*8\s*an under/i.test(shape.half.read.replace(/\s+/g, ' ')),
      'shape: the typical game is labelled with the side it falls on',
      shape.half.read.replace(/\s+/g, ' ').slice(0, 200));
  // The median lands ON a line of 8 here, which is a push and not an under --
  // the 9 fixture's median is 8, a genuine under, so it cannot test this.
  chk(/Typical game\s*9\s*a push/i.test(shape.atLine.read.replace(/\s+/g, ' ')),
      'shape: a median sitting on a whole-number line is called a push',
      shape.atLine.read.replace(/\s+/g, ' ').slice(0, 200));
  chk(/Typical game\s*8\s*an under/i.test(shape.whole.read.replace(/\s+/g, ' ')),
      'shape: and a median below the line is still an under',
      shape.whole.read.replace(/\s+/g, ' ').slice(0, 200));
  chk(/0 graded calls/.test(shape.half.track),
      'shape: with an empty card the track record says so rather than inventing one',
      shape.half.track.slice(0, 120));

  // and it fills in once the card has graded calls in that bucket
  await pg.evaluate(async () => {
    const mk = (prob, line, side, final) =>
      ({ matchup: 'x', sport: 'MLB', line, projected: '9.0', side, prob,
         band: 'BET', fair: '-120', final, inputs: {} });
    localStorage.setItem('callsheet.fullgame.card.v1', JSON.stringify([
      mk('54.0', 8.5, 'OVER', '10'),   // won
      mk('55.0', 8.5, 'OVER', '10'),   // won
      mk('56.0', 8.5, 'UNDER', '2'),   // won
      mk('54.5', 8.5, 'OVER', '3'),    // lost
      mk('53.5', 8.5, 'OVER', '4'),    // lost
      mk('55.5', 9.0, 'OVER', '9'),    // push -- must not count either way
      mk('59.0', 8.5, 'OVER', '3'),    // a different bucket
    ]));
  });
  await pg.reload();
  await pg.waitForTimeout(400);
  const filled = await pg.evaluate(async () => {
    // Every field, not just the ones being set -- an earlier case left park and
    // temperature behind and quietly moved this card into the next bucket.
    const v = { away: 'Braves', home: 'Astros', line: '8.5', op: '100', up: '-130',
                aera: '3.07', hera: '3.43', abp: '3.58', hbp: '4.20',
                arpg: '3.87', hrpg: '4.79' };
    ['away','home','line','op','up','aera','hera','abp','hbp','arpg','hrpg',
     'al10','hl10','h2h','h2hn','pf','mph','dir','temp','tick','cash','opened','gdate','aip','hip']
      .forEach(id => {
        const el = document.getElementById(id);
        el.value = v[id] === undefined ? '' : v[id];
        el.dispatchEvent(new Event('input', { bubbles: true }));
      });
    await new Promise(r => setTimeout(r, 80));
    return document.getElementById('trackRecord').textContent;
  });
  chk(/3-2/.test(filled),
      'track: the 53-57% bucket reports 3-2 from the seeded card', filled.slice(0, 200));
  chk(/over 5 graded calls/.test(filled),
      'track: the push is excluded and the other bucket is not counted',
      filled.slice(0, 200));
  chk(/inside the noise/.test(filled),
      'track: a 5-call gap is reported as unresolved, not as a finding',
      filled.slice(0, 220));

  // ---- the unders-first lens --------------------------------------------
  // Asked for as "have it hunt unders". It is a VIEW: it must reorder and hide
  // rows and must never touch a probability. The check that matters is the
  // last one -- the stored card is identical before and after.
  await pg.evaluate(() => { localStorage.clear(); });
  await pg.reload();
  await pg.waitForTimeout(300);
  const lens = await pg.evaluate(async () => {
    const mk = (m, side, prob) => ({ matchup: m, sport: 'WNBA', line: 161.5,
      projected: '160.0', side, prob, band: 'BET', fair: '-120', final: null, inputs: {} });
    localStorage.setItem('callsheet.fullgame.card.v1', JSON.stringify([
      mk('Wings @ Dream', 'OVER', '53.8'),
      mk('Aces @ Lynx', 'UNDER', '58.2'),
      mk('Sky @ Mercury', 'UNDER', '51.3'),
      mk('Sun @ Storm', 'OVER', '61.0'),
    ]));
    return true;
  });
  await pg.reload();
  await pg.waitForTimeout(350);
  const names = () => pg.evaluate(() =>
    [...document.querySelectorAll('#cardTable tbody tr .openbtn')]
      .map(b => b.textContent.trim().split(' ')[0]));
  const cardBefore = await pg.evaluate(() => localStorage.getItem('callsheet.fullgame.card.v1'));
  const plain = await names();
  const tick = (id, on) => pg.evaluate(([id, on]) => {
    const e = document.getElementById(id);
    e.checked = on; e.dispatchEvent(new Event('change', { bubbles: true }));
  }, [id, on]);
  await tick('underFirst', true);
  await pg.waitForTimeout(150);
  const sorted = await names();
  await tick('underOnly', true);
  await pg.waitForTimeout(150);
  const only = await names();
  const count = await pg.evaluate(() =>
    document.getElementById('cardCount').textContent.trim());
  await pg.reload();
  await pg.waitForTimeout(350);
  const persisted = await pg.evaluate(() => ({
    first: document.getElementById('underFirst').checked,
    only: document.getElementById('underOnly').checked,
  }));
  const cardAfter = await pg.evaluate(() => localStorage.getItem('callsheet.fullgame.card.v1'));

  chk(JSON.stringify(plain) === JSON.stringify(['Wings', 'Aces', 'Sky', 'Sun']),
      'lens: off, the card is in the order it was entered', plain.join('|'));
  // P(under) is 58.2, 51.3 for the two unders and 46.2, 39.0 for the two overs
  chk(JSON.stringify(sorted) === JSON.stringify(['Aces', 'Sky', 'Wings', 'Sun']),
      'lens: unders first ranks the whole slate by P(under), overs included',
      sorted.join('|'));
  chk(JSON.stringify(only) === JSON.stringify(['Aces', 'Sky']),
      'lens: unders only hides the overs', only.join('|'));
  chk(/2 of 4 games/.test(count), 'lens: and the header says what it is hiding', count);
  chk(persisted.first && persisted.only, 'lens: the choice survives a reload',
      JSON.stringify(persisted));
  // The whole point: a lens, not a thumb on the scale.
  chk(cardBefore === cardAfter, 'lens: it does not touch a single stored probability');

  // ---- the alternate ladder ---------------------------------------------
  // Restored probability-first. The check that matters is the last one: it must
  // run off the MARKET estimate, never the blend. If it ever starts using the
  // projection, the one panel here that does not need the model to be right
  // silently starts needing it.
  const alt = await pg.evaluate(async () => {
    const fill = async (vals, sport) => {
      document.getElementById(sport === 'WNBA' ? 'm-wnba' : 'm-mlb').click();
      ['away','home','line','op','up','aera','hera','abp','hbp','arpg','hrpg',
       'al10','hl10','h2h','h2hn','pf','mph','dir','temp','tick','cash','opened','gdate',
       'aip','hip','apace','hpace','aort','hort','adrt','hdrt','arest','hrest','al5','hl5',
       'altLine','altPrice'].forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        el.value = vals[id] === undefined ? '' : vals[id];
        el.dispatchEvent(new Event('input', { bubbles: true }));
      });
      await new Promise(r => setTimeout(r, 60));
      return [...document.querySelectorAll('#altLadder tbody tr')].map(tr => {
        const td = [...tr.querySelectorAll('td')].map(c => c.textContent.trim());
        return { line: td[0], under: parseFloat(td[1]), over: parseFloat(td[3]),
                 main: /main/.test(td[0]) };
      });
    };
    const base = { away: 'Cubs', home: 'Reds', line: '9', op: '-150', up: '115' };
    const plain = await fill(base, 'MLB');
    // Inputs that move the BLEND but leave the two main-line prices alone.
    const loaded = await fill(Object.assign({}, base, {
      aera: '6.50', hera: '6.50', abp: '6.00', hbp: '6.00',
      arpg: '6.00', hrpg: '6.00', al10: '13.0', hl10: '13.0' }), 'MLB');
    const wnba = await fill({ away: 'Dream', home: 'Liberty', line: '179.5',
                              op: '100', up: '-130' }, 'WNBA');
    document.getElementById('m-mlb').click();
    return { plain, loaded, wnba };
  });

  chk(alt.plain.length === 13, 'alt: an MLB ladder is 13 rungs at half a run',
      String(alt.plain.length));
  chk(alt.wnba.length === 11, 'alt: a WNBA ladder is 11 rungs at two points',
      String(alt.wnba.length));
  chk(alt.plain.filter(r => r.main).length === 1 &&
      alt.wnba.filter(r => r.main).length === 1,
      'alt: exactly one rung is marked as the main number');
  chk(alt.plain.every((r, i) => i === 0 || r.under >= alt.plain[i - 1].under),
      'alt: the chance of the under rises as the line does',
      alt.plain.map(r => r.under).join('>'));
  chk(alt.plain.every(r => Math.abs(r.under + r.over - 100) < 0.15),
      'alt: under and over sum to one at every rung (push sits outside)',
      alt.plain.map(r => (r.under + r.over).toFixed(1)).join('|'));
  // The one that pins the design decision.
  chk(JSON.stringify(alt.plain) === JSON.stringify(alt.loaded),
      'alt: the ladder is priced off the MARKET, so loading the blend moves nothing',
      'plain ' + alt.plain.map(r => r.under).join(',') +
      ' vs loaded ' + alt.loaded.map(r => r.under).join(','));

  // ---- the wind resolver -------------------------------------------------
  // Only the component along the home-to-centre axis carries a ball. The
  // browser must resolve it the same way the package does, and the dropdown
  // must actually offer the new directions.
  const windUi = await pg.evaluate(() =>
    [...document.querySelectorAll('#dir option')].map(o => o.value));
  chk(JSON.stringify(windUi) ===
      JSON.stringify(['', 'out', 'quarter-out', 'cross', 'quarter-in', 'in']),
      'wind: the dropdown offers quartering in both directions, ordered out-to-in',
      windUi.join('|'));

  // ---- the copy must not drift from the constants --------------------------
  // The WNBA pace constant was corrected 80.59 <- 83.1 and the placeholders and
  // the prose were left saying 83.1, so the page told the reader to enter a
  // number the model was no longer calibrated against. Nothing tied the two
  // together, so nothing caught it. This does.
  const copy = await pg.evaluate(() => ({
    apace: document.getElementById('apace').placeholder,
    hpace: document.getElementById('hpace').placeholder,
    aort: document.getElementById('aort').placeholder,
    hort: document.getElementById('hort').placeholder,
    adrt: document.getElementById('adrt').placeholder,
    hdrt: document.getElementById('hdrt').placeholder,
    text: document.getElementById('wnbaFields').textContent,
  }));
  const PACE = '80.59', RATING = '107.5';
  chk(copy.apace === PACE && copy.hpace === PACE,
      `wnba: the pace placeholders are the constant in use (${PACE})`,
      `${copy.apace} / ${copy.hpace}`);
  chk([copy.aort, copy.hort, copy.adrt, copy.hdrt].every(v => v === RATING),
      `wnba: the rating placeholders are the constant in use (${RATING})`,
      [copy.aort, copy.hort, copy.adrt, copy.hdrt].join('/'));
  chk(copy.text.includes(PACE) && copy.text.includes(RATING),
      'wnba: the prose quotes both live constants', 'prose is missing one of them');
  // 83.1 may appear ONLY as the history of the bug, never as an instruction.
  chk(!/League average on that column is [^.]*83\.1/.test(copy.text) &&
      !/104\.9/.test(copy.text),
      'wnba: no superseded constant is presented as a number to enter',
      copy.text.slice(0, 200));
  chk(/PACE\/40/.test(copy.text),
      'wnba: the prose names the exact column to read', 'PACE/40 not mentioned');

  // ---- the held note names the inputs it actually deleted -----------------
  // Reported from the page: a held WNBA card told the reader to delete "last
  // ten, head to head and the money split". The gate's arithmetic was right --
  // it deletes whatever is tagged -- but the sentence was three MLB names typed
  // in by hand, and they went stale twice over. The names are read off the same
  // flag the gate reads now, so the sentence cannot describe a different blend.
  const held = await pg.evaluate(async () => {
    const fill = async (vals, sport) => {
      document.getElementById(sport === 'WNBA' ? 'm-wnba' : 'm-mlb').click();
      ['away','home','line','op','up','aera','hera','abp','hbp','arpg','hrpg',
       'al10','hl10','h2h','h2hn','pf','mph','dir','temp','tick','cash','opened','gdate',
       'aip','hip','apace','hpace','aort','hort','adrt','hdrt','arest','hrest','al5','hl5']
        .forEach(id => {
          const el = document.getElementById(id);
          if (!el) return;
          el.value = vals[id] === undefined ? '' : vals[id];
          el.dispatchEvent(new Event('input', { bubbles: true }));
        });
      const roof = document.getElementById('dome');
      roof.checked = !!vals.dome;
      roof.dispatchEvent(new Event('change', { bubbles: true }));
      await new Promise(r => setTimeout(r, 60));
      const c = document.getElementById('call');
      return { why: document.getElementById('why').textContent,
               band: c.dataset.band, ungated: c.dataset.bandUngated };
    };
    // Sparks @ Aces, 22 Sept, exactly as logged -- the card in the report.
    const wnba = await fill({ away: 'Sparks', home: 'Aces', line: '181.5',
      op: '110', up: '-145', apace: '82.66', hpace: '80.58', aort: '105.7',
      hort: '112.7', adrt: '110.5', hdrt: '106.2', arest: '1', hrest: '1',
      al5: '169.5', hl5: '175.4' }, 'WNBA');
    // One tagged input on its own: the sentence must read as a name, not a list.
    const lone = await fill({ away: 'Sparks', home: 'Aces', line: '161.5',
      op: '-110', up: '-110', arest: '0', hrest: '0' }, 'WNBA');
    // Braves @ Astros, 20 Sept -- the live MLB card the gate still holds.
    const mlb = await fill({ away: 'Braves', home: 'Astros', line: '8.5',
      op: '100', up: '-130', aera: '3.07', hera: '3.43', aip: '137.2', hip: '97.0',
      arpg: '3.87', hrpg: '4.79', abp: '3.58', hbp: '4.20', al10: '9.9', hl10: '7.8',
      h2h: '8.5', h2hn: '2', pf: '99', temp: '91', tick: '96', cash: '96',
      dome: true }, 'MLB');
    document.getElementById('m-mlb').click();
    return { wnba, lone, mlb };
  });
  chk(/Held at/.test(held.wnba.why) && held.wnba.band === 'NO BET',
      'held: the Sparks card is held in the browser too',
      `${held.wnba.band} from ${held.wnba.ungated}`);
  chk(/Delete Last 5 and Rest/.test(held.wnba.why),
      'held: a WNBA card names the two inputs that sport actually tags',
      (held.wnba.why.match(/Held at[^.]*\./) || [''])[0]);
  chk(!/head to head|Head to head|money split|last ten|Last 10|Starters/
        .test((held.wnba.why.match(/Held at[\s\S]*?other side\./) || [''])[0]),
      'held: and never names an input the WNBA model does not have',
      (held.wnba.why.match(/Held at[\s\S]*?other side\./) || [''])[0]);
  chk(/Delete Rest — measured null/.test(held.lone.why),
      'held: one tagged input reads as a name, not a one-item list',
      (held.lone.why.match(/Held at[^.]*\./) || [''])[0]);
  chk(/Delete Starters, Last 10 and Head to head/.test(held.mlb.why),
      'held: an MLB card names the starters the hand-written sentence forgot',
      (held.mlb.why.match(/Held at[^.]*\./) || [''])[0]);
  chk(!/money split/.test((held.mlb.why.match(/Held at[\s\S]*?on their own\./) || [''])[0]),
      'held: and no longer names the money split, which nothing scores any more');
  chk(!/Head to head \(/.test((held.mlb.why.match(/Held at[^.]*\./) || [''])[0]),
      'held: the meeting count is dropped from the sentence',
      (held.mlb.why.match(/Held at[^.]*\./) || [''])[0]);

  // ---- the build stamp ----------------------------------------------------
  // Twice now a fix has landed and the page kept showing the old text, and
  // there was no way to tell a bug in the fix from a cached copy of the file.
  // The stamp answers that in one glance -- but only if it is current, so it is
  // enforced rather than trusted: with the page edited and not yet committed it
  // must read today; with the page committed it must match the date of the
  // commit that last touched it.
  const stamp = await pg.evaluate(() => {
    const el = document.getElementById('build');
    return el ? el.textContent.trim() : null;
  });
  const git = (cmd) => execSync(cmd, { cwd: __dirname, encoding: 'utf8' }).trim();
  let want, why;
  try {
    if (git('git status --porcelain -- web/fullgame.html')) {
      want = git("date +%Y-%m-%d");
      why = 'the page is edited and not committed, so the stamp must read today';
    } else {
      want = git('git log -1 --format=%cs -- web/fullgame.html');
      why = 'the page is committed, so the stamp must match that commit';
    }
  } catch (e) { want = stamp; why = 'no git here, stamp left unchecked'; }
  chk(stamp === want, `build: the stamp is current (${why})`,
      `page says ${stamp}, expected ${want}`);

  if (errs.length) { console.log('PAGE ERRORS:\n' + errs.join('\n')); fails++; }
  console.log(fails ? `\n${fails} FAILED` : `\nall checks passed (${CASES.length} cases)`);
  await b.close();
  process.exit(fails ? 1 : 0);
})();
