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

const MLB_IDS = ["away","home","line","op","up","opened","gdate","aera","hera","aip","hip","arpg","hrpg",
                 "abp","hbp","al10","hl10","h2h","h2hn","pf","mph","dir","temp","tick","cash"];
const NFL_IDS = ["away","home","line","op","up","gdate","anet","hnet","gp","nopened"];
const ALL = [...new Set([...MLB_IDS, ...NFL_IDS])];
const CHECKS = ["dome", "aqb", "hqb"];

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
      document.getElementById(sport === 'NFL' ? 'm-nfl' : 'm-mlb').click();
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
        projectedCore: parseFloat(call.dataset.projectedCore),
        pCorroborated: parseFloat(call.dataset.pCorroborated),
        bandUngated: call.dataset.bandUngated,
        held: !!document.querySelector('#call .held'),
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
        `${tag}: the struck-through band shows only when held`,
        `held=${got.held} band=${w.band} ungated=${w.band_ungated}`);
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
      band: document.querySelector('#cardTable td:nth-child(7) .chip').textContent.trim(),
      stale: (document.querySelector('#cardTable .chip.stale') || {}).textContent,
      result: document.querySelector('#cardTable .res').textContent.trim(),
    };
    document.getElementById('rescore').click();
    return new Promise(r => setTimeout(() => r({
      before,
      after: document.querySelector('#cardTable td:nth-child(7) .chip').textContent.trim(),
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

    // The box stays ticked across a sport switch; an NFL row must not inherit it.
    document.getElementById('m-nfl').click();
    set('away', 'Jets'); set('home', 'Bills'); set('line', -6.5);
    await add();
    const nfl = first().textContent.trim();

    document.getElementById('m-mlb').click();
    document.getElementById('clear').click();
    set('away', 'Cubs'); set('home', 'Reds'); set('line', 9);
    await add();

    return {
      domed, nfl,
      open: first().textContent.trim(),
      chips: document.querySelectorAll('#cardTable .chip.dome').length,
      count: document.getElementById('cardCount').textContent.trim(),
    };
  });
  chk(/Dome$/.test(roof.domed), 'roof: a game with the roof shut is marked on the card', roof.domed);
  chk(!/Dome/.test(roof.open), 'roof: an open-air game is not marked', roof.open);
  chk(!/Dome/.test(roof.nfl), 'roof: an NFL row does not inherit a left-over tick', roof.nfl);
  chk(roof.chips === 1, 'roof: exactly one row carries the marker', String(roof.chips));
  chk(/1 under a roof/.test(roof.count), 'roof: the header counts the domed games', roof.count);

  // ---- team names are merged to one spelling per club --------------------
  // A free-text box had produced fifty spellings of thirty MLB clubs across
  // the logged card, which manufactures perfect records out of nothing when
  // anything is grouped by team.
  const teams = await pg.evaluate(async () => {
    const shown = (name, sport) => {
      document.getElementById(sport === 'NFL' ? 'm-nfl' : 'm-mlb').click();
      const a = document.getElementById('away'), h = document.getElementById('home'),
            l = document.getElementById('line');
      a.value = name; h.value = 'Rockies';
      l.value = sport === 'NFL' ? '-3.5' : '8.5';
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
      arizona: [shown('Arizona', 'MLB'), shown('Arizona', 'NFL')],
      kc: [shown('Kansas City', 'MLB'), shown('Kansas City', 'NFL')],
      sf: [shown('SF', 'MLB'), shown('SF', 'NFL')],
      // ambiguous or unknown input must survive untouched
      ambiguous: ['Chicago', 'LA', 'NY', 'Some Local Nine'].map(s => shown(s, 'MLB')),
    };
    document.getElementById('m-mlb').click();
    out.mlbList = [...document.getElementById('teamList').options].map(o => o.value);
    document.getElementById('m-nfl').click();
    out.nflList = [...document.getElementById('teamList').options].map(o => o.value);
    document.getElementById('m-mlb').click();
    return out;
  });
  chk(teams.stl.length === 1 && teams.stl[0] === 'Cardinals',
      'teams: six spellings of St Louis collapse to one', teams.stl.join('|'));
  chk(JSON.stringify(teams.typos) ===
      JSON.stringify(['Guardians', 'Astros', 'Red Sox', 'Reds', 'White Sox']),
      'teams: typos and run-together names resolve, and red/sox does not collide',
      teams.typos.join('|'));
  chk(JSON.stringify(teams.arizona) === JSON.stringify(['Diamondbacks', 'Cardinals']),
      'teams: a city maps by sport, not globally', teams.arizona.join('|'));
  chk(JSON.stringify(teams.kc) === JSON.stringify(['Royals', 'Chiefs']),
      'teams: Kansas City is scoped too', teams.kc.join('|'));
  chk(JSON.stringify(teams.sf) === JSON.stringify(['Giants', '49ers']),
      'teams: SF is Giants in MLB and 49ers in NFL', teams.sf.join('|'));
  chk(JSON.stringify(teams.ambiguous) ===
      JSON.stringify(['Chicago', 'LA', 'NY', 'Some Local Nine']),
      'teams: ambiguous and unknown input is left exactly as typed',
      teams.ambiguous.join('|'));
  chk(teams.mlbList.length === 30, 'teams: the MLB list offers all thirty clubs',
      String(teams.mlbList.length));
  chk(teams.nflList.length === 32, 'teams: the NFL list offers all thirty-two clubs',
      String(teams.nflList.length));

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

  if (errs.length) { console.log('PAGE ERRORS:\n' + errs.join('\n')); fails++; }
  console.log(fails ? `\n${fails} FAILED` : `\nall checks passed (${CASES.length} cases)`);
  await b.close();
  process.exit(fails ? 1 : 0);
})();
