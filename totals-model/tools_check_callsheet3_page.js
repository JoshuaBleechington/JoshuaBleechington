/* Replays web/callsheet3-cases.json through web/callsheet3.html in a real
 * browser and asserts the page reaches the same markets, in the same order,
 * with the same probabilities and edges the Python package reached -- the
 * MLB cases through Call Sheet #1's engine block (byte-identical to
 * fullgame.html's) and the NHL cases through the NHL block (ported from
 * totals/nhl.py).
 *
 * Then what the fixtures cannot see: the hockey card grades from a final
 * and a first-period score, a shootout is a one-goal margin, the puck line
 * and moneyline are shown, not picked, the record has an NHL block in goals,
 * the slate fills the goalie boxes, a 2.0 backup carries only its MLB rows
 * over, the NHL team table canonicalises, and the build stamp is current.
 *
 *   node tools_check_callsheet3_page.js
 */
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
const { execSync } = require('child_process');

const CASES = JSON.parse(fs.readFileSync(path.join(__dirname, 'web/callsheet3-cases.json'), 'utf8'));
const IDS = ["away","home","line","op","up","opened","gdate","aera","hera","aip","hip","arpg","hrpg",
             "abp","hbp","al10","hl10","h2h","h2hn","pf","mph","dir","temp","tick","cash",
             "hml","aml","rl","rlh","rla","f5line","f5op","f5up","al5era","hl5era","al5ip","hl5ip",
             "apace","hpace","aort","hort","adrt","hdrt","arest","hrest","al5","hl5","sp","sph","spa",
             "agsv","hgsv","agsh","hgsh","asf","hsf","app","hpp","apk","hpk","pl","plh","pla","p1line","p1op","p1up",
             "ntick","ncash","ap1l10","hp1l10","axgf","axga","hxgf","hxga","xglg","nhlform",
             "ngoalies","agname","hgname","agstart","hgstart","agok","hgok",
             "agf","aga","hgf","hga","lgg","angp","hngp"];
const CHECKS = ["dome","playoff","agconf","hgconf","agbk","hgbk"];

(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/opt/pw-browsers/chromium' });
  const pg = await b.newPage({ viewport: { width: 1280, height: 1400 } });
  const errs = [];
  pg.on('pageerror', e => errs.push(String(e)));
  pg.on('console', m => {
    const where = (m.location() && m.location().url) || '';
    if (m.type() === 'error' && !/fonts\.(googleapis|gstatic)\.com/.test(where + ' ' + m.text())) errs.push('console: ' + m.text());
  });
  await pg.goto('file://' + path.join(__dirname, 'web/callsheet3.html'));
  await pg.waitForTimeout(300);
  await pg.evaluate(() => { localStorage.clear(); });
  await pg.reload();
  await pg.waitForTimeout(300);

  let fails = 0;
  const chk = (ok, m, d) => { if (!ok) fails++; console.log(`${ok ? 'PASS' : 'FAIL'}  ${m}${ok ? '' : '\n        ' + d}`); };

  // ---- the engine block is Call Sheet #1's, byte for byte; the NHL block sits after it ----
  const block = (file, open, close) => {
    const s = fs.readFileSync(path.join(__dirname, 'web', file), 'utf8').split('\n');
    const a = s.findIndex(l => l.startsWith(open));
    const z = s.findIndex(l => l.startsWith(close));
    return a >= 0 && z > a ? s.slice(a, z + 1).join('\n') : null;
  };
  const b1 = block('fullgame.html', '  /* ===== ENGINE BLOCK.', '  /* ===== END ENGINE BLOCK ===== */');
  const b3 = block('callsheet3.html', '  /* ===== ENGINE BLOCK.', '  /* ===== END ENGINE BLOCK ===== */');
  chk(b1 && b3 && b1 === b3, 'engine: callsheet3.html carries fullgame.html\'s engine block byte-identical', `#1 ${b1 ? b1.length : 'missing'} vs 3.0 ${b3 ? b3.length : 'missing'}`);
  const nb = block('callsheet3.html', '  /* ===== NHL BLOCK.', '  /* ===== END NHL BLOCK ===== */');
  const src = fs.readFileSync(path.join(__dirname, 'web/nhl.engine.js'), 'utf8').replace(/\n$/, '');
  chk(nb && nb === src, 'engine: the NHL block is web/nhl.engine.js verbatim and follows the engine block', `${nb ? nb.length : 'missing'} vs ${src.length}`);
  const html = fs.readFileSync(path.join(__dirname, 'web/callsheet3.html'), 'utf8');
  chk(html.indexOf('END ENGINE BLOCK') < html.indexOf('NHL BLOCK.'), 'engine: the NHL block comes after the engine block', '');

  // ---- fixtures ---------------------------------------------------------------
  const fill = async (sport, inputs) => pg.evaluate(async ([sport, inputs, ids, checks]) => {
    document.getElementById(sport === 'WNBA' ? 'm-wnba' : sport === 'NHL' ? 'm-nhl' : 'm-mlb').click();
    document.getElementById('byEdge').checked = true;
    ids.forEach(id => { document.getElementById(id).value = ''; });
    checks.forEach(id => { document.getElementById(id).checked = false; });
    for (const [k, v] of Object.entries(inputs)) {
      if (v === null || v === undefined) continue;
      const el = document.getElementById(k); if (!el) continue;
      if (el.type === 'checkbox') el.checked = !!v; else el.value = String(v);
    }
    ids.forEach(id => document.getElementById(id).dispatchEvent(new Event('input', { bubbles: true })));
    checks.forEach(id => document.getElementById(id).dispatchEvent(new Event('change', { bubbles: true })));
    await new Promise(r => setTimeout(r, 40));
    return [...document.querySelectorAll('#markets .mk')].map(el => {
      const e = el.querySelector('.e').textContent;
      const edge = /edge ([+-][0-9.]+)/.exec(e);
      return { key: el.dataset.key, pick: el.querySelector('.pick').childNodes[0].textContent.trim(),
               p: parseFloat(el.querySelector('.p').textContent), edge: edge ? parseFloat(edge[1]) : null,
               derived: !!el.querySelector('.derived'), band: (el.querySelector('.band') || {}).textContent || '' };
    });
  }, [sport, inputs, IDS, CHECKS]);

  for (const c of CASES) {
    const got = await fill(c.sport, c.inputs);
    const w = c.expect, tag = `${c.sport} · ${c.name}`;
    chk(got.length === w.markets.length, `${tag}: ${w.markets.length} markets`, `page drew ${got.length}`);
    chk(got.map(m => m.key).join('>') === w.markets.map(m => m.key).join('>'),
        `${tag}: ranked ${w.markets.map(m => m.key).join(' > ')}`, `page ranked ${got.map(m => m.key).join(' > ')}`);
    w.markets.forEach((m, i) => {
      const g = got[i]; if (!g) return;
      chk(g.pick === m.pick, `${tag}: #${i + 1} ${m.pick}`, `page said ${g.pick}`);
      chk(Math.abs(g.p - m.p * 100) < 0.051, `${tag}: #${i + 1} ${(m.p * 100).toFixed(1)}%`, `page said ${g.p}%`);
      if (m.edge === null) chk(g.edge === null, `${tag}: #${i + 1} has no price`, `page printed an edge ${g.edge}`);
      else chk(Math.abs(g.edge - m.edge * 100) < 0.051, `${tag}: #${i + 1} edge ${(m.edge * 100).toFixed(1)}`, `page said ${g.edge}`);
      chk(g.derived === !m.anchored, `${tag}: #${i + 1} ${m.anchored ? 'anchored' : 'derived'}`, `derived=${g.derived}`);
      if (m.key === 'total') chk(g.band === m.band, `${tag}: total carries #1's band ${m.band}`, `page said ${g.band}`);
    });
  }

  // ---- the hockey card: add, grade, record ---------------------------------------
  const flow = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 60));
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    localStorage.removeItem('callsheet3.card.v1');
    document.getElementById('clear').click(); document.getElementById('m-nhl').click(); await wait();
    document.getElementById('boardDate').value = '2026-11-07';
    // game 1: Rangers @ Bruins, full board, the example
    set('gdate', '2026-11-07'); document.getElementById('example').click(); await wait();
    set('gdate', '2026-11-07'); await wait();
    const rail = [...document.querySelectorAll('#markets .mk')].map(el => ({ key: el.dataset.key, chips: [...el.querySelectorAll('.cap')].map(c => c.textContent) }));
    const forecast = document.getElementById('forecastLine').textContent;
    document.getElementById('add').click(); await wait();
    // game 2: a second hockey game, moneyline only
    document.getElementById('clear').click(); await wait();
    set('gdate', '2026-11-07'); set('away', 'Toronto'); set('home', 'Montreal'); set('line', '6.5'); set('op', '-115'); set('up', '-105'); set('aml', '-120'); set('hml', '100');
    await wait(); document.getElementById('add').click(); await wait();
    document.getElementById('boardDate').dispatchEvent(new Event('change')); await wait();
    const card = JSON.parse(localStorage.getItem('callsheet3.card.v1'));
    const names = card.map(r => r.matchup);
    const boardRows = [...document.querySelectorAll('#board tbody tr')].map(tr => ({ market: tr.querySelectorAll('td')[2].textContent, notPicked: !!tr.querySelector('.chip.dim') && /not picked/.test(tr.querySelectorAll('td')[2].textContent) }));
    const bets = [...document.querySelectorAll('#bestBets .pk .n4')].map(e => e.textContent);
    const legs = [...document.querySelectorAll('#picks .pk:not(.parlay) .n4')].map(e => e.textContent);
    // grade game 1: Bruins 3, Rangers 2 (a shootout), first period 1-1
    const tr = () => [...document.querySelectorAll('#cardTable tr')].find(t => /Rangers @ Bruins/.test(t.textContent));
    const label = tr().querySelector('.finals .l').textContent + '|' + [...tr().querySelectorAll('.finals .l')].map(e => e.textContent).join(',');
    const g = (k, v) => { const el = tr().querySelector(`.grade[data-k="${k}"]`); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); };
    // the period score first: both finals lock the row and its score boxes go read-only
    g('f5a', '1'); g('f5h', '1'); g('fa', '2'); g('fh', '3'); await wait();
    const graded = [...tr().querySelectorAll('.rowmk .m')].map(e => ({ pick: e.querySelector('.chip').textContent, res: (e.querySelector('.chip.win,.chip.loss,.chip.push') || {}).textContent || '' }));
    const calib = document.getElementById('calibBox').innerText;
    const nhlBlock = [...document.querySelectorAll('#calibBox .calib[data-sport="NHL"] > div')].map(d => d.querySelector('.k').textContent + ' ' + d.querySelector('.v').textContent + ' ' + d.querySelector('.s').textContent);
    // open the graded row: the rail says "after one"
    tr().querySelector('[data-open]').click(); await wait();
    const final = (document.querySelector('#markets .final') || {}).textContent || '';
    document.getElementById('clear').click(); await wait();
    return { rail, names, boardRows, bets, legs, label, graded, calib, nhlBlock, final, sport1: card[0].sport, keys: card[0].markets.map(m => m.key), forecast, proj: card[0].proj };
  });
  chk(/Forecast · Rangers [0-9.]+ – Bruins [0-9.]+ · total [0-9.]+ goals · first period [0-9.]+ · (Rangers|Bruins) to win, \d+%/.test(flow.forecast),
      'forecast: the rail says what the sheet expects — each side\'s goals, the total, the first period and the winner\'s chance', flow.forecast.slice(0, 200));
  chk(flow.proj && typeof flow.proj.t === 'number' && typeof flow.proj.h === 'number' && typeof flow.proj.a === 'number' && typeof flow.proj.q === 'number' && typeof flow.proj.ph === 'number' && !flow.proj.re,
      'forecast: the row stores the projection (total, sides, period, home chance) when it is added', JSON.stringify(flow.proj));
  chk(/Forecast · 1 graded game: the projected total lands [0-9.]+ goals from the final on average, the market's line [0-9.]+;/.test(flow.calib) && /Winner called [01] of 1/.test(flow.calib) && /First period projected/.test(flow.calib),
      'forecast: the record keeps the projection\'s accuracy against the line, the favourite and the period line', flow.calib.slice(flow.calib.indexOf('Forecast'), flow.calib.indexOf('Forecast') + 300));
  chk(flow.names.length === 2 && flow.names[0] === 'Rangers @ Bruins' && flow.names[1] === 'Maple Leafs @ Canadiens', 'card: two NHL games logged, with Toronto and Montreal canonicalised to the NHL table', JSON.stringify(flow.names));
  chk(flow.sport1 === 'NHL' && flow.keys.join(',') === 'total,ml,pl,p1', 'card: an NHL row stores total, ml, pl and p1', flow.keys.join(','));
  chk(flow.rail.filter(r => r.key === 'ml' || r.key === 'pl').every(r => r.chips.some(c => /shown, not picked/.test(c))), 'rail: the moneyline and puck line carry the shown-not-picked chip', JSON.stringify(flow.rail));
  chk(flow.boardRows.filter(r => /Moneyline|Puck line/.test(r.market)).every(r => r.notPicked) && flow.boardRows.filter(r => /total|period/i.test(r.market)).every(r => !r.notPicked),
      'board: moneyline and puck line are marked not picked; the total and first period are not', JSON.stringify(flow.boardRows));
  chk(!flow.bets.some(t => /Moneyline|Puck line/.test(t)) && !flow.legs.some(t => /Moneyline|Puck line/.test(t)), 'picks: no puck line or moneyline reaches the straight bets or the parlay legs', JSON.stringify({ bets: flow.bets, legs: flow.legs }));
  chk(/P1/.test(flow.label), 'card: the period score boxes are labelled P1 on a hockey row', flow.label);
  const byPick = Object.fromEntries(flow.graded.map(x => [x.pick, x.res]));
  chk(flow.graded.length === 4 && flow.graded.every(x => x.res), 'grade: all four hockey markets grade from a final and a first period', JSON.stringify(flow.graded));
  const plRes = flow.graded.find(x => /\+1\.5|-1\.5/.test(x.pick));
  chk(plRes && ((/Rangers \+1\.5/.test(plRes.pick) && plRes.res === 'win') || (/Bruins -1\.5/.test(plRes.pick) && plRes.res === 'loss')), 'grade: a 3-2 shootout is a one-goal margin, so +1.5 covers and -1.5 does not', JSON.stringify(plRes));
  const totRes = flow.graded.find(x => /^(OVER|UNDER) 6$/.test(x.pick));
  chk(totRes && totRes.res === 'loss' || (totRes && /UNDER/.test(totRes.pick) && totRes.res === 'win'), 'grade: 3-2 is five goals, under the 6', JSON.stringify(totRes));
  chk(flow.nhlBlock.length >= 4 && flow.nhlBlock.some(t => /First period/.test(t)) && flow.nhlBlock.some(t => /Puck line/.test(t)), 'record: the NHL block has first period and puck line tiles', JSON.stringify(flow.nhlBlock));
  chk(/NHL/.test(flow.calib) && !/WNBA/.test(flow.calib.split('NHL')[0]), 'record: an NHL block is drawn', flow.calib.slice(0, 200));
  chk(/after one 1–1/.test(flow.final) && /Final: Rangers 2, Bruins 3/.test(flow.final), 'rail: opening a graded hockey row prints the final and the score after one', flow.final);

  // ---- a hockey verdict lists only when it clears its price ------------------------
  const thinNhl = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 60));
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    document.getElementById('clear').click(); document.getElementById('m-nhl').click(); await wait();
    // two cold goalies on long samples, the over priced -140: #1's band says BET (58.0%), the price needs 58.3%
    set('gdate', '2026-11-07'); set('away', 'Flames'); set('home', 'Kraken'); set('line', '6'); set('op', '-140'); set('up', '110');
    set('agsv', '0.875'); set('hgsv', '0.875'); set('agsh', '1800'); set('hgsh', '1800'); await wait();
    const railBand = (document.querySelector('#markets .mk[data-key="total"] .band') || {}).textContent || '';
    const railP = (document.querySelector('#markets .mk[data-key="total"] .p') || {}).textContent || '';
    const railEdge = (document.querySelector('#markets .mk[data-key="total"] .e') || {}).textContent || '';
    document.getElementById('add').click(); await wait();
    document.getElementById('boardDate').value = '2026-11-07'; document.getElementById('boardDate').dispatchEvent(new Event('change')); await wait();
    const betsThin = [...document.querySelectorAll('#bestBets .pk')].map(e => e.querySelector('.n4').textContent.split(' · ')[0]);
    // the same row at -120 (needs 54.5%, the sheet says 56.1%) clears its price and lists with its chip
    set('op', '-120'); set('up', '100'); await wait(); document.getElementById('add').click(); await wait();
    const betsClear = [...document.querySelectorAll('#bestBets .pk')].map(e => e.querySelector('.n4').textContent.split(' · ')[0] + ' ' + ((e.querySelector('.n2 .band') || {}).textContent || ''));
    document.getElementById('clear').click(); await wait();
    return { railBand, railP, railEdge, betsThin, betsClear };
  });
  chk(/BET/.test(thinNhl.railBand) && /edge -/.test(thinNhl.railEdge), 'hockey verdict: the fixture reads BET on the over with the price steeper than the chance', JSON.stringify(thinNhl));
  chk(!thinNhl.betsThin.some(t => /Flames @ Kraken/.test(t)), 'hockey verdict: a thin hockey verdict is NOT on the straight bets (no record behind it)', JSON.stringify(thinNhl.betsThin));
  chk(thinNhl.betsClear.some(t => /Flames @ Kraken/.test(t) && /BET/.test(t)), 'hockey verdict: the same row lists once its price clears', JSON.stringify(thinNhl.betsClear));

  // ---- the crowd: a label on the hockey total with its own record line -------------
  const crowd = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 60));
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    document.getElementById('clear').click(); document.getElementById('m-nhl').click(); await wait();
    // the under is the pick (-102 is the better price on an even number); 78% of the money is on the over
    set('gdate', '2026-11-07'); set('away', 'Wild'); set('home', 'Blues'); set('line', '6'); set('op', '-118'); set('up', '-102'); set('ntick', '71'); set('ncash', '78'); await wait();
    const pick = document.querySelector('#markets .mk[data-key="total"] .pick').childNodes[0].textContent.trim();
    const chips = [...document.querySelectorAll('#markets .mk[data-key="total"] .cap')].map(c => c.textContent);
    const why = document.getElementById('why').textContent;
    document.getElementById('add').click(); await wait();
    const stored = JSON.parse(localStorage.getItem('callsheet3.card.v1')).find(r => /Wild @ Blues/.test(r.matchup));
    const tr = [...document.querySelectorAll('#cardTable tr')].find(x => /Wild @ Blues/.test(x.textContent));
    const g = (k, v) => { const el = tr.querySelector(`.grade[data-k="${k}"]`); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); };
    g('f5a', '1'); g('f5h', '0'); g('fa', '2'); g('fh', '1'); await wait();
    const tile = [...document.querySelectorAll('#calibBox .calib[data-sport="NHL"] > div')].find(d => /Full-game total/.test(d.textContent));
    document.getElementById('clear').click(); await wait();
    return { pick, chips, why, ncash: stored.inputs.ncash, tile: tile ? tile.textContent : '' };
  });
  chk(/UNDER 6/.test(crowd.pick) && crowd.chips.some(c => /against the crowd/.test(c)), 'crowd: an under against 78% of the money is chipped against the crowd', JSON.stringify(crowd));
  chk(!/Over holds 71% of tickets/.test(crowd.why), 'crowd: a 7-point ticket/money gap is below the 20-point note threshold, so the why list says nothing', crowd.why.slice(0, 200));
  chk(crowd.ncash === '78', 'crowd: the money box is stored on the row', crowd.ncash);
  chk(/against the crowd 1-0/.test(crowd.tile), 'record: the hockey total tile keeps the crowd line (2-1 is under 6, the pick won against the crowd)', crowd.tile.slice(0, 300));

  // ---- a backup in net: a tagged delta on the under, a chip, a record line ----------
  const backup = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 60));
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    const tick = (id, on) => { const el = document.getElementById(id); el.checked = on; el.dispatchEvent(new Event('change', { bubbles: true })); };
    const read = () => { const el = document.querySelector('#markets .mk[data-key="total"]'); const pick = el.querySelector('.pick').childNodes[0].textContent.trim(); const p = parseFloat(el.querySelector('.p').textContent); return { pick, under: /UNDER/.test(pick) ? p : 100 - p, band: (el.querySelector('.band') || {}).textContent || '', why: document.getElementById('why').textContent, chips: [...el.querySelectorAll('.cap')].map(c => c.textContent) }; };
    document.getElementById('clear').click(); document.getElementById('m-nhl').click(); await wait();
    set('gdate', '2026-11-12'); set('away', 'Kraken'); set('home', 'Canucks'); set('line', '6'); set('op', '-110'); set('up', '-110');
    set('agsv', '0.905'); set('hgsv', '0.912'); set('agsh', '900'); set('hgsh', '1800'); set('app', '21.0'); set('hpp', '19.0'); set('apk', '80.0'); set('hpk', '79.0'); await wait();
    const none = read();
    tick('agbk', true); await wait();
    const one = read();
    tick('hgbk', true); await wait();
    const two = read();
    tick('hgbk', false); await wait();
    document.getElementById('add').click(); await wait();
    const stored = JSON.parse(localStorage.getItem('callsheet3.card.v1')).find(r => /Kraken @ Canucks/.test(r.matchup));
    const tr = [...document.querySelectorAll('#cardTable tr')].find(x => /Kraken @ Canucks/.test(x.textContent));
    const g = (k, v) => { const el = tr.querySelector(`.grade[data-k="${k}"]`); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); };
    g('f5a', '0'); g('f5h', '1'); g('fa', '2'); g('fh', '1'); await wait();
    const tile = [...document.querySelectorAll('#calibBox .calib[data-sport="NHL"] > div')].find(d => /Full-game total/.test(d.textContent));
    const rowChips = tr.textContent;
    document.getElementById('clear').click(); await wait();
    return { none, one, two, agbk: stored.inputs.agbk, hgbk: stored.inputs.hgbk, tile: tile ? tile.textContent : '', rowChips };
  });
  chk(backup.one.under > backup.none.under + 1 && /Backup in net for the away side/.test(backup.one.why) && !/Backup in net/.test(backup.none.why),
      'backup: ticking one Backup box moves the total toward the under and the why list says so', JSON.stringify({ none: backup.none.under, one: backup.one.under }));
  chk(backup.one.chips.some(c => /backup in net/.test(c)) && !backup.none.chips.some(c => /backup in net/.test(c)), 'backup: the total is chipped "backup in net"', JSON.stringify(backup.one.chips));
  // with a backup in either net the goalie lines are not scored, so two backups leave the market alone: 50.0 at -110/-110
  chk(Math.abs(backup.two.under - 50) < 0.3 && /both/.test(backup.two.why) && /Goalies are NOT SCORED with a backup/.test(backup.two.why) && !backup.two.chips.some(c => /backup in net/.test(c)),
      'backup: two backups carry no delta and no chip, say so, and the goalie lines are not scored', JSON.stringify({ none: backup.none.under, two: backup.two.under }));
  chk(/Goalies are NOT SCORED with a backup/.test(backup.one.why) && !/Goalies are NOT SCORED/.test(backup.none.why),
      'backup: one backup also takes the goalie lines out of scoring; two regular starters keep them', backup.one.why.slice(0, 200));
  chk(/Special teams are SHOWN, NOT SCORED/.test(backup.none.why) && !/Special teams.*on the line/.test(backup.none.why), 'special teams: shown, not scored, in the why list', backup.none.why.slice(0, 300));
  chk(backup.agbk === true && !backup.hgbk, 'backup: the boxes are stored on the row', JSON.stringify({ a: backup.agbk, h: backup.hgbk }));
  chk(/backup in net, the under 1-0/.test(backup.tile), 'record: the hockey total tile keeps the backup line (2-1 is under 6)', backup.tile.slice(0, 300));

  // ---- the odds file: lines fill, merge with the slate, the best price, the close ------
  const oddsT = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 80));
    const load = async (doc, name) => { const dt = new DataTransfer(); dt.items.add(new File([JSON.stringify(doc)], name, { type: 'application/json' })); const inp = document.getElementById('slateFile'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true })); await wait(); };
    localStorage.removeItem('callsheet3.card.v1');
    document.getElementById('slateClear').click(); document.getElementById('clear').click(); await wait();
    const game = { sport: 'NHL', gdate: '2026-11-09', away: 'Kraken', home: 'Canucks' };   // its own matchup: the row stays on the card for later tests
    await load({ format: 'callsheet2.slate', version: 1, date: '2026-11-09', games: [ Object.assign({}, game, { starters: { away: 'Stuart Skinner', home: 'Dustin Wolf' }, inputs: { agsv: '0.908', hgsv: '0.916', agsh: '1200', hgsh: '1300', agname: 'Stuart Skinner', hgname: 'Dustin Wolf' }, notes: ['from the slate'] }) ] }, 'nhl-slate-2026-11-09.json');
    const shop = JSON.stringify({ book: 'fanatics', total: { OVER: [['fanatics', -110, 6], ['draftkings', -102, 6], ['betmgm', -105, 6.5]], UNDER: [['fanatics', -110, 6], ['betmgm', -118, 6]] }, ml: { HOME: [['fanatics', 110, null], ['caesars', 118, null]], AWAY: [['fanatics', -130, null]] },
      alt: { OVER: [['fanatics', -150, 5.5], ['fanatics', 125, 6.5]], UNDER: [['fanatics', 125, 5.5], ['fanatics', -150, 6.5]] },
      team: { AWAY: { OVER: [['fanatics', -115, 2.5]] }, HOME: { OVER: [['betmgm', -110, 3.5], ['fanatics', -105, 3.5]], UNDER: [['fanatics', -115, 3.5]] } } });
    const sharp = JSON.stringify({ book: 'pinnacle', line: 6.5, op: -125, up: 105, hml: 105, aml: -125 });   // a 30-cent shade on the over
    await load({ format: 'callsheet2.slate', version: 1, date: '2026-11-09', games: [ Object.assign({}, game, { inputs: { line: '6', op: '-110', up: '-110', opened: '6.5', hml: '110', aml: '-130', pl: '1.5', plh: '-180', pla: '150', p1line: '1.5', p1op: '-125', p1up: '105', odds: shop, sharp: sharp }, notes: ['from the odds file'] }) ] }, 'odds-2026-11-09.json');
    const pending = [...document.querySelectorAll('#slateList [data-slate]')].length;
    document.querySelector('#slateList [data-slate]').click(); await wait();
    const v = id => document.getElementById(id).value;
    const form = { agsv: v('agsv'), line: v('line'), op: v('op'), opened: v('opened'), hml: v('hml'), pl: v('pl'), p1line: v('p1line'), odds: v('odds').length > 10, sharp: v('sharp').length > 10 };
    const chips = [...document.querySelectorAll('#markets .mk[data-key="total"] .cap')].map(c => c.textContent);
    const listed = document.querySelector('#markets .mk[data-key="total"] .pick').childNodes[0].textContent.trim();
    const why = document.getElementById('why').textContent;
    document.getElementById('add').click(); await wait();
    const stored = JSON.parse(localStorage.getItem('callsheet3.card.v1')).find(r => /Kraken @ Canucks/.test(r.matchup) && r.gdate === '2026-11-09');
    // a later odds file with a moved number: the carded line stays
    await load({ format: 'callsheet2.slate', version: 1, date: '2026-11-09', games: [ Object.assign({}, game, { inputs: { line: '6.5', op: '-115', up: '-105' } }) ] }, 'odds-2026-11-09.json');
    // the backup test left its own Kraken @ Canucks row (12 Nov) on the in-memory card, so find this one by its date
    const mine = r => /Kraken @ Canucks/.test(r.matchup) && r.gdate === '2026-11-09';
    const row1 = JSON.parse(localStorage.getItem('callsheet3.card.v1')).find(mine);
    // the grade file with the close attached
    await load({ format: 'callsheet2.slate', version: 1, date: '2026-11-09', games: [ Object.assign({}, game, { finals: { fa: '2', fh: '1', f5a: '1', f5h: '0' }, close: { ctot: '6.5', cf5: '1.5' }, starters: { away: 'S. Skinner', home: 'D. Wolf' } }) ] }, 'nhl-grade-2026-11-09.json');
    await wait();
    const row2 = JSON.parse(localStorage.getItem('callsheet3.card.v1')).find(mine);
    // graded 2-1 (three goals under the carded 6): Pinnacle's 30-cent shade on the over lost, on its own record line
    const tileO = [...document.querySelectorAll('#calibBox .calib[data-sport="NHL"] > div')].find(d => /Full-game total/.test(d.textContent));
    const tileOText = tileO ? tileO.textContent : '';
    document.getElementById('slateClear').click(); document.getElementById('clear').click(); await wait();
    return { pending, form, chips, listed, why, kept: { odds: (stored.inputs.odds || '').length > 10, sharp: (stored.inputs.sharp || '').length > 10 }, line1: row1.inputs.line, close: row2.close, agok: row2.inputs.agok, tile: tileOText };
  });
  chk(oddsT.form.sharp && oddsT.kept.odds && oddsT.kept.sharp, 'odds: the sharp box fills from the file, and the shop and the sharp line are stored on the hockey row', JSON.stringify({ form: oddsT.form.sharp, kept: oddsT.kept }));
  chk(oddsT.chips.some(c => c === 'sharp line 6.5 (-125/+105), here 6') && oddsT.chips.some(c => c === 'Pinnacle shades OVER by 6.8 points'),
      'odds: Pinnacle\'s number is chipped beside the carded line when it differs, and its 3+ point shade names the side (-125/+105 is 6.8 points)', JSON.stringify(oddsT.chips));
  chk(oddsT.chips.filter(c => /^alt (OVER|UNDER) (5\.5|6\.5) [+-]\d+ at Fanatics · sheet \d+\.\d% · edge [+-]\d+\.\d$/.test(c)).length === 2, 'odds: the two nearest alternates on the listed side are priced by the sheet\'s projection, best price per number', JSON.stringify(oddsT.chips));
  chk(oddsT.chips.some(c => c === "book's split: Kraken 2.5 (o -115) · Canucks 3.5 (o -105)"), 'odds: the book\'s split rides as a chip, the carded book\'s number first', JSON.stringify(oddsT.chips));
  chk(/Pinnacle, the sharp book: 6\.5 \(-125\/\+105\), moneyline -125\/\+105, above the carded 6/.test(oddsT.why) && /It shades the over by 6\.8 points: on the 2025-26 history that side went 56\.3%/.test(oddsT.why) && /Alternates on the (over|under), priced by the sheet's projection of \d\.\d\d, shown, not picked: (5\.5|6\.5) at/.test(oddsT.why) && /The book's split, shown, not scored: Kraken 2\.5 \(over -115\), Canucks 3\.5 \(over -105\)\./.test(oddsT.why),
      'odds: the why list names the sharp line, the alternates and the split as shown, not scored', oddsT.why.slice(-700));
  chk(oddsT.pending === 1 && oddsT.form.agsv === '0.908' && oddsT.form.line === '6' && oddsT.form.op === '-110' && oddsT.form.opened === '6.5' && oddsT.form.hml === '110' && oddsT.form.pl === '1.5' && oddsT.form.p1line === '1.5' && oddsT.form.odds,
      'odds: the odds file merges into the slate\'s pending game, and Fill form carries the goalies, the lines, the prices, the opener and the shop', JSON.stringify(oddsT.form));
  chk(/OVER/.test(oddsT.listed) ? oddsT.chips.some(c => /^best -102 at DraftKings · edge there [+-][0-9.]+$/.test(c)) : !oddsT.chips.some(c => /^best /.test(c)),
      'odds: the rail names the best price on the listed side at the same number only (-102 at 6 counts, -105 at 6.5 does not; the under has no better price)', JSON.stringify({ listed: oddsT.listed, chips: oddsT.chips }));
  chk(oddsT.line1 === '6', 'odds: a later odds file never moves a line already on the row', oddsT.line1);
  chk(oddsT.close && oddsT.close.ctot === '6.5' && oddsT.close.cf5 === '1.5' && oddsT.agok === 'yes', 'odds: the grade file\'s close fills the CLOSE box, beside the starter check', JSON.stringify({ close: oddsT.close, agok: oddsT.agok }));
  chk(/Pinnacle's shade, 3\+ points 0-1/.test(oddsT.tile), 'odds: the total tile keeps Pinnacle\'s shade on its own record line (the over lost at 2-1)', oddsT.tile.slice(0, 400));

  // ---- 12-13 Oct: the hockey book picks the full-game total only ---------------------
  const twoDays = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 60));
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    const read = () => { const p1 = document.querySelector('#markets .mk[data-key="p1"]'); return { chips: [...p1.querySelectorAll('.cap')].map(c => c.textContent), title: (p1.querySelector('.cap[title]') || {}).title || '' }; };
    document.getElementById('clear').click(); document.getElementById('m-nhl').click(); await wait();
    set('gdate', '2026-10-12'); set('away', 'Kings'); set('home', 'Sharks'); set('line', '6'); set('op', '-110'); set('up', '-110'); set('p1line', '1.5'); set('p1op', '-105'); set('p1up', '-115');
    set('aml', '-130'); set('hml', '110'); set('pl', '1.5'); set('plh', '-180'); set('pla', '150');
    set('nhlform', JSON.stringify({ away: [{ date: '2026-10-04', opp: 'Jets', home: false, gf: 2, ga: 5 }, { date: '2026-10-06', opp: 'Kings', home: true, gf: 3, ga: 4 }, { date: '2026-10-08', opp: 'Ducks', home: true, gf: 1, ga: 2 }], home: [{ date: '2026-10-05', opp: 'Stars', home: true, gf: 4, ga: 1 }] }));
    await wait();
    const railKeys = [...document.querySelectorAll('#markets .mk')].map(el => el.dataset.key);
    const rankTag = document.getElementById('rankTag').textContent;
    const totalWhy = (document.querySelector('#markets .mk[data-key="total"] .mkdetail') || {}).textContent || ('NO RAIL: ' + document.getElementById('markets').textContent.slice(0, 200));
    const whyText = document.getElementById('why').textContent;
    const d12 = (() => { const p1 = document.querySelector('#markets .mk[data-key="p1"]'); return p1 ? read() : { chips: ['shown, not picked (row hidden)'], title: '11 and 12 Oct (row hidden)' }; })();
    const totalRow = document.querySelector('#markets .mk[data-key="total"]');
    const callChip = [...totalRow.querySelectorAll('.cap')].map(c => c.textContent).find(c => /the call/.test(c)) || '';
    const band12 = (totalRow.querySelector('.band') || {}).textContent || '';
    document.getElementById('add').click(); await wait();
    document.getElementById('boardDate').value = '2026-10-12'; document.getElementById('boardDate').dispatchEvent(new Event('change')); await wait();
    const boardP1 = [...document.querySelectorAll('#board tbody tr')].map(tr => tr.querySelectorAll('td')[2].textContent).find(t => /First period/.test(t)) || '';
    const legs = [...document.querySelectorAll('#picks .pk:not(.parlay) .n4')].map(e => e.textContent).join(' | ');
    const bets = [...document.querySelectorAll('#bestBets .pk')].map(e => e.textContent);
    const fav = [...document.querySelectorAll('#bestBets .pk.fav')].map(e => e.textContent.replace(/\s+/g, ' '));
    // grade it 2-1: the call's own record line appears on the total tile
    const tr = [...document.querySelectorAll('#cardTable tr')].find(x => /Kings @ Sharks/.test(x.textContent));
    const g = (k, v) => { const el = tr.querySelector(`.grade[data-k="${k}"]`); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); };
    g('f5a', '0'); g('f5h', '1'); g('fa', '2'); g('fh', '1'); await wait();
    const tile = [...document.querySelectorAll('#calibBox .calib[data-sport="NHL"] > div')].find(d => /Full-game total/.test(d.textContent));
    const tileText = tile ? tile.textContent : '';
    const favText = (document.querySelector('#calibBox .favs[data-sport="NHL"]') || {}).textContent || '';
    document.getElementById('clear').click(); await wait();
    set('gdate', '2026-10-20'); set('away', 'Wild'); set('home', 'Blues'); set('line', '6'); set('op', '-110'); set('up', '-110'); set('p1line', '1.5'); set('p1op', '-105'); set('p1up', '-115'); await wait();
    const d14 = read();
    // from 13 Oct the hockey rail shows the pick block with the other markets folded under it
    const pick20 = (() => { const c = document.querySelector('#markets .pickcard'), o = document.querySelector('#markets details.others');
      return { has: !!c, none: !!(c && c.classList.contains('none')), key: c ? c.dataset.key || '' : '', lab: c ? c.querySelector('.lab').textContent : '', why: c ? c.querySelector('.why').textContent : '',
               tag: document.getElementById('rankTag').textContent, others: !!o, open: o ? o.open : null, rows: [...document.querySelectorAll('#markets .mk')].map(e => e.dataset.key) }; })();
    document.getElementById('clear').click(); await wait();
    return { d12, boardP1, legs, d14, callChip, band12, bets, tileText, favText, fav, railKeys, rankTag, totalWhy, why: whyText, pick20 };
  });
  chk(twoDays.railKeys.join(',') === 'total' && /the total only, 11-12 Oct/.test(twoDays.rankTag), 'the week: a hockey matchup\'s list is the full-game total alone, and the tag says so', JSON.stringify({ keys: twoDays.railKeys, tag: twoDays.rankTag }));
  chk(/First-period market/.test(twoDays.why) && /for sixty minutes against the market/.test(twoDays.why), 'the week: the first-period market is read as a second estimate of the game, tagged, in the why list', twoDays.why.slice(twoDays.why.indexOf('First-period market'), twoDays.why.indexOf('First-period market') + 200));
  chk(/Last five: Kings games averaged 5\.7 \(2 of 3 over tonight's 6\); Sharks games averaged 5\.0 \(0 of 1 over tonight's 6\)/.test(twoDays.why), 'the week: the last five from the form panel are read against tonight\'s line as a trend', twoDays.why.slice(twoDays.why.indexOf('Last five'), twoDays.why.indexOf('Last five') + 160));
  chk(/A big road favourite/.test(twoDays.why) === false, 'the week: a +110 home side is not a big road favourite, so no watched note', '');
  chk(twoDays.bets.every(t => !/Kings @ Sharks/.test(t) || /Why (this side|the sheet likes this one most tonight)/.test(t)), 'the week: every hockey call carries a why', JSON.stringify(twoDays.bets).slice(0, 200));
  chk(twoDays.fav.length === 1 && /Kings @ Sharks/.test(twoDays.fav[0]) && /LIKES MOST/.test(twoDays.fav[0]) && /Why the sheet likes this one most tonight: projected [0-9.]+ against 6/.test(twoDays.fav[0]) && /the market's own fair number is [0-9.]+ against the 6 line/.test(twoDays.fav[0]),
      'the one it likes most: exactly one hockey call carries the colour, the label and a why built from the row\'s own inputs', (twoDays.fav[0] || '').slice(0, 300));
  chk(/the call: (OVER|UNDER) 6 [0-9.]+%/.test(twoDays.callChip) && (twoDays.band12 === 'NO BET' || twoDays.band12 === ''),
      'the call: on 12 Oct a coin-flip hockey total still names a side on the rail', JSON.stringify({ chip: twoDays.callChip, band: twoDays.band12 }));
  chk(twoDays.bets.some(t => /Kings @ Sharks/.test(t) && /CALL/.test(t) && /The call/.test(t)), 'the call: the straight bets list it under its own CALL label with the note', JSON.stringify(twoDays.bets).slice(0, 300));
  chk(/the call, 11-12 Oct [01]-[01]/.test(twoDays.tileText), 'the call: the total tile keeps the calls\' own record', twoDays.tileText.slice(0, 300));
  // Kings -130 on the road won 2-1: the favourite by price table counts it in the -149 to -120 row (won, dog +1.5 covered), beside the two-season baseline
  chk(/The favourite, by price/.test(twoDays.favText) && /−149 to −120\s*[1-9]\d*\s*\d+\.\d%\s*\d+\.\d%\s*\d+\.\d%\s*\d+\.\d%\s*[+-]\d+\.\d%/.test(twoDays.favText) && /two seasons at the close\s*828\s*54\.0%\s*57\.1%\s*68\.6%\s*31\.4%\s*-5\.5%/.test(twoDays.favText),
      'the favourite by price: the record section tables the favourite\'s record, the dog +1.5 and the return by price, with the two-season baseline in grey', twoDays.favText.slice(0, 600));
  chk(twoDays.d12.chips.some(c => /shown, not picked/.test(c)) && /11 and 12 Oct/.test(twoDays.d12.title), 'the week: on 12 Oct the first period is shown, not picked, and the chip says why', JSON.stringify(twoDays.d12));
  chk(/not picked/.test(twoDays.boardP1) && !/First period/.test(twoDays.legs), 'two days: the board marks the first period not picked and no first-period leg is offered', JSON.stringify({ board: twoDays.boardP1, legs: twoDays.legs }));
  chk(!twoDays.d14.chips.some(c => /shown, not picked/.test(c)), 'the week: on 20 Oct the first period picks as before', JSON.stringify(twoDays.d14));
  chk(twoDays.pick20.has && twoDays.pick20.others && twoDays.pick20.rows.indexOf('total') >= 0 && twoDays.pick20.rows.indexOf('p1') >= 0 &&
      (twoDays.pick20.none ? (/book/.test(twoDays.pick20.why) && twoDays.pick20.open === true && twoDays.pick20.tag === 'no pick yet')
                            : (/^The pick · an? (OVER|UNDER) game/.test(twoDays.pick20.lab) && /^Why: Projected/.test(twoDays.pick20.why) && twoDays.pick20.open === false && /the pick, then the rest by edge/.test(twoDays.pick20.tag))),
      'the pick: on 20 Oct a hockey matchup shows the pick block (or says nothing separates the sides) with the markets folded under it', JSON.stringify(twoDays.pick20).slice(0, 400));

  // ---- the pick: one side per matchup, the likeliest on the board, with its kind of game and its why ----
  const pickT = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 60));
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    const read = () => { const c = document.querySelector('#markets .pickcard'), o = document.querySelector('#markets details.others'), ml = document.querySelector('#markets .mk[data-key="ml"]');
      return { has: !!c, none: !!(c && c.classList.contains('none')), key: c ? c.dataset.key || '' : '', side: c ? c.dataset.side || '' : '', pick: c ? c.querySelector('.pick').textContent : '',
               lab: c ? c.querySelector('.lab').textContent : '', p: c && c.querySelector('.p') ? parseFloat(c.querySelector('.p').textContent) : null, why: c ? c.querySelector('.why').textContent : '',
               open: o ? o.open : null, summary: o ? o.querySelector('summary').textContent : '', rows: [...document.querySelectorAll('#markets .mk')].map(e => e.dataset.key),
               mlP: ml ? parseFloat(ml.querySelector('.p').textContent) : null, mlChips: ml ? [...ml.querySelectorAll('.cap')].map(x => x.textContent) : [] }; };
    document.getElementById('clear').click(); document.getElementById('m-mlb').click(); await wait();
    set('gdate', '2026-10-20'); set('away', 'Rays'); set('home', 'Yankees'); set('line', '8.5'); set('op', '-110'); set('up', '-110'); await wait();
    const bare = read();
    set('aera', '2.10'); set('hera', '2.30'); set('aip', '180'); set('hip', '175'); set('abp', '2.90'); set('hbp', '3.00'); await wait();
    const totalPick = read();
    set('aml', '210'); set('hml', '-250'); await wait();
    const mlPick = read();
    document.getElementById('clear').click(); await wait();
    return { bare, totalPick, mlPick };
  });
  chk(pickT.bare.has && pickT.bare.none && /^No pick yet$/.test(pickT.bare.pick) && /Nothing on the card moves a number off the book's/.test(pickT.bare.why) && pickT.bare.open === true,
      'the pick: a line and two prices alone give no pick, because nothing on the card moves a number off the book\'s', JSON.stringify(pickT.bare).slice(0, 400));
  chk(pickT.totalPick.has && !pickT.totalPick.none && pickT.totalPick.key === 'total' && pickT.totalPick.side === 'UNDER' && /^The pick · an UNDER game$/.test(pickT.totalPick.lab) &&
      /^Why: Projected [0-9.]+ runs against the 8\.5 line, so the under at [0-9.]+%\. Behind it: the market's own fair number/.test(pickT.totalPick.why) &&
      /The book's own number makes it 50\.0%; the sheet's inputs move it to [0-9.]+%, a [0-9.]+-point lean toward the under\./.test(pickT.totalPick.why) &&
      pickT.totalPick.open === false && /other markets/.test(pickT.totalPick.summary) && pickT.totalPick.rows.indexOf('total') >= 0,
      'the pick: two aces against an 8.5 make it an UNDER game; the why carries the total\'s lean and the book\'s number against the sheet\'s; the other markets fold under it', JSON.stringify(pickT.totalPick).slice(0, 600));
  // the moneyline row lists its better-priced side, which on -250/+210 is the dog, so its chance reads under 40 rather than over 60
  chk(pickT.mlPick.key === 'total' && pickT.mlPick.side === 'UNDER' && pickT.mlPick.mlP !== null && (pickT.mlPick.mlP > 60 || pickT.mlPick.mlP < 40) && pickT.mlPick.mlChips.some(c => /shown, not picked/.test(c)) && pickT.mlPick.rows.indexOf('ml') >= 0,
      'the pick: a -250 favourite does NOT take the pick from the under, because the sheet has no information on the sides; the moneyline row sits folded, shown not picked',
      JSON.stringify({ key: pickT.mlPick.key, side: pickT.mlPick.side, mlP: pickT.mlPick.mlP, mlChips: pickT.mlPick.mlChips, rows: pickT.mlPick.rows }));

  // ---- October: the seasonal delta, tagged ------------------------------------------
  const octo = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 60));
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    const read = () => { const el = document.querySelector('#markets .mk[data-key="total"]'); const pick = el.querySelector('.pick').childNodes[0].textContent.trim(); const p = parseFloat(el.querySelector('.p').textContent); return { pick, over: /OVER/.test(pick) ? p : 100 - p, band: (el.querySelector('.band') || {}).textContent || '', why: document.getElementById('why').textContent }; };
    document.getElementById('clear').click(); document.getElementById('m-nhl').click(); await wait();
    set('gdate', '2026-11-20'); set('away', 'Wild'); set('home', 'Blues'); set('line', '6'); set('op', '-110'); set('up', '-110'); await wait();
    const nov = read();
    set('gdate', '2026-10-20'); await wait();
    const oct = read();
    document.getElementById('clear').click(); await wait();
    return { nov, oct };
  });
  chk(Math.abs(octo.oct.over - octo.nov.over) < 0.05 && /October: NO seasonal delta since 11 Oct 2026/.test(octo.oct.why) && !/October/.test(octo.nov.why),
      'october: since 11 Oct a game dated in October carries no delta, only a note; November says nothing', JSON.stringify({ nov: octo.nov.over, oct: octo.oct.over }));
  chk(octo.oct.band === 'NO BET' || octo.oct.band === '', 'october: the delta alone cannot buy a band', octo.oct.band);

  // ---- the slate fills the goalie boxes; a 2.0 backup carries MLB only --------------
  const slate = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 80));
    const slateDoc = { format: 'callsheet2.slate', version: 1, date: '2026-11-07', games: [
      { sport: 'NHL', gdate: '2026-11-07', away: 'Oilers', home: 'Flames', starters: { away: 'Skinner', home: 'Wolf' },
        inputs: { agsv: '0.908', hgsv: '0.916', agsh: '1200', hgsh: '1300', asf: '30.1', hsf: '28.9', app: '25.0', hpp: '19.5', apk: '78.0', hpk: '81.2', al10: '6.4', hl10: '5.9', h2h: '6.0', h2hn: '2', arest: '0', hrest: '1', ap1l10: '1.90', hp1l10: '1.70', axgf: '3.40', axga: '3.10', hxgf: '3.30', hxga: '2.90', xglg: '3.05', agbk: true, hgbk: false,
                  agname: 'Stuart Skinner', hgname: 'Dustin Wolf',
                  ngoalies: JSON.stringify({ away: [{ n: 'Stuart Skinner', sv: 0.908, sh: 1200, gs: 10, cs: 12, ls: false }, { n: 'Calvin Pickard', sv: 0.897, sh: 450, gs: 2, cs: 12, ls: false }],
                                            home: [{ n: 'Dustin Wolf', sv: 0.916, sh: 1300, gs: 11, cs: 12, ls: false }, { n: 'Devin Cooley', sv: 0.902, sh: 300, gs: 1, cs: 12, ls: false }] }),
                  nhlform: JSON.stringify({ away: [{ date: '2026-10-04', opp: 'Jets', home: false, gf: 2, ga: 5, sf: 24, sa: 38, p1f: 0, p1a: 2, goalie: 'S. Skinner', end: 'REG' }, { date: '2026-10-06', opp: 'Kings', home: true, gf: 3, ga: 4, sf: 27, sa: 36, p1f: 1, p1a: 1, goalie: 'C. Pickard', end: 'OT' }], home: [{ date: '2026-10-05', opp: 'Sharks', home: true, gf: 4, ga: 1, sf: 33, sa: 22, p1f: 2, p1a: 0, goalie: 'D. Wolf', end: 'REG' }] }) },
        notes: ['Away back to back: likely the backup in net'] } ] };
    const dt = new DataTransfer(); dt.items.add(new File([JSON.stringify(slateDoc)], 'slate-2026-11-07.json', { type: 'application/json' }));
    const inp = document.getElementById('slateFile'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true })); await wait();
    const list = document.getElementById('slateList').innerText;
    document.querySelector('#slateList [data-slate]').click(); await wait();
    const v = id => document.getElementById(id).value;
    const form = { away: v('away'), home: v('home'), agsv: v('agsv'), hgsh: v('hgsh'), asf: v('asf'), apk: v('apk'), arest: v('arest'), line: v('line'), pressed: document.getElementById('m-nhl').getAttribute('aria-pressed'),
                   agbk: document.getElementById('agbk').checked, hgbk: document.getElementById('hgbk').checked,
                   panel: document.getElementById('formPanel').innerText, ap1l10: v('ap1l10'), hp1l10: v('hp1l10'), axgf: v('axgf'), hxga: v('hxga'), xglg: v('xglg'),
                   why: document.getElementById('why').textContent,
                   p1why: [...document.querySelectorAll('#markets .mk[data-key="p1"] .mkdetail')].map(e => e.textContent).join(' ') };
    document.getElementById('slateClear').click(); document.getElementById('clear').click(); await wait();
    // a 2.0 backup with an MLB row and a WNBA row: both join the card, and loading it twice adds nothing
    const before = JSON.parse(localStorage.getItem('callsheet3.card.v1') || '[]');
    const b2 = { format: 'callsheet2.backup', version: 1, card: [
      { id: 1, sport: 'MLB', away: 'Rays', home: 'Yankees', matchup: 'Rays @ Yankees', gdate: '2026-09-22', inputs: { away: 'Rays', home: 'Yankees', line: '6.5', op: '-110', up: '-110', gdate: '2026-09-22' }, markets: [{ key: 'total', label: 'Full-game total 6.5', pick: 'UNDER 6.5', side: 'UNDER', p: 0.52, pPush: 0, price: -110, edge: -0.004, fair: -108, anchored: true, band: 'NO BET', other: { pick: 'OVER 6.5', p: 0.48, price: -110, edge: -0.044 } }], finals: { fa: '2', fh: '3' } },
      { id: 2, sport: 'WNBA', away: 'Sun', home: 'Mystics', matchup: 'Sun @ Mystics', gdate: '2026-09-22', inputs: { away: 'Sun', home: 'Mystics', line: '162.5', gdate: '2026-09-22' }, markets: [], finals: {} } ] };
    const dt2 = new DataTransfer(); dt2.items.add(new File([JSON.stringify(b2)], 'callsheet2-2026-09-30.json', { type: 'application/json' }));
    const inp2 = document.getElementById('restoreFile'); inp2.files = dt2.files; inp2.dispatchEvent(new Event('change', { bubbles: true })); await wait();
    const card = JSON.parse(localStorage.getItem('callsheet3.card.v1'));
    const msg = document.getElementById('saveMsg').textContent;
    const dt3 = new DataTransfer(); dt3.items.add(new File([JSON.stringify(b2)], 'callsheet2-2026-09-30.json', { type: 'application/json' }));
    inp2.files = dt3.files; inp2.dispatchEvent(new Event('change', { bubbles: true })); await wait();
    const again = JSON.parse(localStorage.getItem('callsheet3.card.v1'));
    const msg2 = document.getElementById('saveMsg').textContent;
    const wnbaBtn = document.getElementById('m-wnba');
    return { list, form, before: before.length, card: card.map(r => r.sport + ':' + r.matchup), ids: card.map(r => r.id), msg,
             again: again.length, msg2, wnbaHidden: wnbaBtn.hidden, wnbaOffset: wnbaBtn.offsetParent !== null };
  });
  chk(/Oilers @ Flames/.test(slate.list) && /SV 0\.908\/0\.916/.test(slate.list) && /Skinner v Wolf/.test(slate.list) && /likely the backup/.test(slate.list),
      'slate: a hockey game lists with its goalies, save percentages and note', slate.list.slice(0, 200));
  chk(slate.form.pressed === 'true' && slate.form.away === 'Oilers' && slate.form.agsv === '0.908' && slate.form.hgsh === '1300' && slate.form.asf === '30.1' && slate.form.apk === '78.0' && slate.form.arest === '0' && slate.form.line === '',
      'slate: Fill form switches to NHL and fills the goalie, shot, special-teams and rest boxes, never the line', JSON.stringify(slate.form));
  chk(slate.form.ap1l10 === '1.90' && slate.form.hp1l10 === '1.70', 'slate: the first-period last ten fills from the ledger fields', JSON.stringify({ a: slate.form.ap1l10, h: slate.form.hp1l10 }));
  chk(slate.form.agbk === true && slate.form.hgbk === false, 'slate: the Backup in net box is ticked from the slate for the away side only', JSON.stringify({ a: slate.form.agbk, h: slate.form.hgbk }));

  // ---- the goalie picker: the slate's lists, a pick fills the line and the backup box, the grade file checks it ----
  const picker = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 80));
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    localStorage.removeItem('callsheet3.card.v1');
    document.getElementById('slateClear').click(); document.getElementById('clear').click(); await wait();
    const slateDoc = { format: 'callsheet2.slate', version: 1, date: '2026-11-08', games: [
      { sport: 'NHL', gdate: '2026-11-08', away: 'Oilers', home: 'Flames', starters: { away: 'Stuart Skinner', home: 'Dustin Wolf' },
        inputs: { agsv: '0.908', hgsv: '0.916', agsh: '1200', hgsh: '1300', arest: '1', hrest: '1', agname: 'Stuart Skinner', hgname: 'Dustin Wolf',
                  ngoalies: JSON.stringify({ away: [{ n: 'Stuart Skinner', sv: 0.908, sh: 1200, gs: 10, cs: 12, ls: false }, { n: 'Calvin Pickard', sv: 0.897, sh: 450, gs: 2, cs: 12, ls: false }],
                                            home: [{ n: 'Dustin Wolf', sv: 0.916, sh: 1300, gs: 11, cs: 12, ls: false }, { n: 'Devin Cooley', sv: 0.902, sh: 300, gs: 1, cs: 12, ls: false }] }) }, notes: [] } ] };
    const dt = new DataTransfer(); dt.items.add(new File([JSON.stringify(slateDoc)], 'slate-2026-11-08.json', { type: 'application/json' }));
    const inp = document.getElementById('slateFile'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true })); await wait();
    document.querySelector('#slateList [data-slate]').click(); await wait();
    set('line', '6'); set('op', '-110'); set('up', '-110'); await wait();
    const sel = document.getElementById('agpick'), hsel = document.getElementById('hgpick');
    const before = { options: [...sel.options].map(o => o.textContent), value: sel.value, hvalue: hsel.value, summary: document.getElementById('goalieSummary').textContent };
    sel.value = 'Calvin Pickard'; sel.dispatchEvent(new Event('change', { bubbles: true })); await wait();
    const after = { agsv: document.getElementById('agsv').value, agsh: document.getElementById('agsh').value, agname: document.getElementById('agname').value, agbk: document.getElementById('agbk').checked, hgbk: document.getElementById('hgbk').checked, summary: document.getElementById('goalieSummary').textContent };
    document.getElementById('add').click(); await wait();
    // the grade file: Skinner started after all, Wolf as carded
    const gradeDoc = { format: 'callsheet2.slate', version: 1, date: '2026-11-08', games: [ { sport: 'NHL', gdate: '2026-11-08', away: 'Oilers', home: 'Flames', finals: { fa: '2', fh: '1', f5a: '1', f5h: '0' }, starters: { away: 'S. Skinner', home: 'D. Wolf' }, notes: [] } ] };
    const dt2 = new DataTransfer(); dt2.items.add(new File([JSON.stringify(gradeDoc)], 'nhl-grade-2026-11-08.json', { type: 'application/json' }));
    inp.files = dt2.files; inp.dispatchEvent(new Event('change', { bubbles: true })); await wait();
    const row = JSON.parse(localStorage.getItem('callsheet3.card.v1')).find(r => /Oilers @ Flames/.test(r.matchup));
    const tr = [...document.querySelectorAll('#cardTable tr')].find(x => /Oilers @ Flames/.test(x.textContent));
    const tile = [...document.querySelectorAll('#calibBox .calib[data-sport="NHL"] > div')].find(d => /Full-game total/.test(d.textContent));
    tr.querySelector('[data-open]').click(); await wait();
    const opened = document.getElementById('goalieSummary').textContent;
    document.getElementById('slateClear').click(); document.getElementById('clear').click(); await wait();
    return { before, after, agok: row.inputs.agok, hgok: row.inputs.hgok, agstart: row.inputs.agstart, rowText: tr.textContent, tile: tile ? tile.textContent : '', opened };
  });
  chk(picker.before.options.length === 3 && /Calvin Pickard — 0\.897 on 450 \(2 of 12 starts\)/.test(picker.before.options[2]) && picker.before.value === 'Stuart Skinner' && picker.before.hvalue === 'Dustin Wolf',
      'picker: each side lists the club\'s goalies with his line and starts, and the slate\'s named starter is selected', JSON.stringify(picker.before.options));
  chk(/Away Stuart Skinner 0\.908 on 1200/.test(picker.before.summary), 'picker: the summary names whose line is on the card', picker.before.summary.slice(0, 160));
  chk(picker.after.agsv === '0.897' && picker.after.agsh === '450' && picker.after.agname === 'Calvin Pickard' && picker.after.agbk === true && picker.after.hgbk === false,
      'picker: picking the other goalie fills his line, writes his name, and ticks Backup by the rule (2 of 12 starts)', JSON.stringify(picker.after));
  chk(picker.agok === 'no' && picker.hgok === 'yes' && picker.agstart === 'S. Skinner', 'grade: the grade file\'s starters are matched by last name against the carded names', JSON.stringify({ a: picker.agok, h: picker.hgok, st: picker.agstart }));
  chk(/goalie line wrong/.test(picker.rowText) && /goalie line wrong [01]-[01]/.test(picker.tile), 'record: the row is chipped and the total tile keeps the goalie-line record', picker.tile.slice(0, 300));
  chk(/S\. Skinner started, not this line/.test(picker.opened), 'picker: the opened row says who started instead', picker.opened.slice(0, 200));
  chk(slate.form.axgf === '3.40' && slate.form.hxga === '2.90' && slate.form.xglg === '3.05', 'slate: the expected-goals boxes and the table\'s league mean fill', JSON.stringify({ a: slate.form.axgf, h: slate.form.hxga, lg: slate.form.xglg }));
  chk(/Expected goals/.test(slate.form.why) || slate.form.why === '', 'slate: with a line typed the why list would name expected goals (no line yet here)', slate.form.why.slice(0, 120));
  chk(/First-period last ten: 1\.90 and 1\.70 a game, average 1\.80, from the league ledger/.test(slate.form.p1why) || slate.form.p1why === '',
      'slate: with a first-period line typed the period notes name the ledger form (no line yet here, so the note waits)', slate.form.p1why.slice(0, 200));
  chk(/Oilers last 2: 0-2, 7\.0 goals a game, first period 2\.0 \(0\.5 for, 1\.5 against\), shots 25\.5 for \/ 37\.0 against, in net S\. Skinner and C\. Pickard/.test(slate.form.panel) &&
      /giving up 37\.0 shots a night; two goalies used/.test(slate.form.panel) && /OTL \(OT\) 3–4/.test(slate.form.panel) && /Flames last 1: 1-0/.test(slate.form.panel),
      'form: the panel reads each side\'s last five from the slate — record, goals, first period, shots, goalies, and the flags', slate.form.panel.slice(0, 400));
  chk(slate.card.length === slate.before + 2 && slate.card.includes('MLB:Rays @ Yankees') && slate.card.includes('WNBA:Sun @ Mystics') && /Brought 2 matchups over from the 2.0 backup/.test(slate.msg),
      'backup: a 2.0 backup brings its MLB and WNBA rows over and keeps what was already on the card', JSON.stringify({ before: slate.before, card: slate.card, msg: slate.msg }));
  chk(new Set(slate.ids).size === slate.ids.length, 'backup: rows brought over take ids that collide with nothing on the card', slate.ids.join(','));
  chk(slate.again === slate.card.length && /Brought 0 matchups over/.test(slate.msg2) && /2 already here were left as they are/.test(slate.msg2),
      'backup: loading the same 2.0 backup again adds nothing and says so', `${slate.again} vs ${slate.card.length} · ${slate.msg2}`);
  chk(!slate.wnbaHidden && slate.wnbaOffset, 'sport: the WNBA button is on the page', `hidden=${slate.wnbaHidden} shown=${slate.wnbaOffset}`);

  // ---- the team tables are scoped by sport ---------------------------------------------
  const teams = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 60));
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    document.getElementById('clear').click(); document.getElementById('m-nhl').click(); await wait();
    set('away', 'vegas'); set('home', 'NY Rangers'); set('line', '6'); await wait();
    const nhl = document.querySelector('#markets .mk .lab') ? [...document.querySelectorAll('#markets .mk')].map(e => e.querySelector('.pick').childNodes[0].textContent.trim()) : [];
    const h1 = (document.querySelector('#rankTag') || {}).textContent;
    const matchNhl = document.getElementById('why').textContent;
    document.getElementById('m-mlb').click(); await wait();
    set('away', 'texas'); set('home', 'NY'); set('line', '8.5'); await wait();
    const dl = [...document.querySelectorAll('#teamList option')].map(o => o.value);
    document.getElementById('m-nhl').click(); await wait();
    const dlNhl = [...document.querySelectorAll('#teamList option')].map(o => o.value);
    document.getElementById('clear').click(); await wait();
    return { nhlCount: nhl.length, dlHasAstros: dl.includes('Astros'), dlNhlHasBruins: dlNhl.includes('Bruins'), dlNhlHasAstros: dlNhl.includes('Astros'), dlNhlLen: dlNhl.length };
  });
  chk(teams.dlNhlHasBruins && !teams.dlNhlHasAstros && teams.dlNhlLen === 32 && teams.dlHasAstros, 'teams: the NHL datalist holds the 32 clubs and the MLB one its 30', JSON.stringify(teams));

  // ---- the build stamp ------------------------------------------------------------
  const stamp = await pg.evaluate(() => (document.getElementById('build') || {}).textContent);
  const git = (cmd) => execSync(cmd, { cwd: __dirname, encoding: 'utf8' }).trim();
  let want, why;
  try {
    if (git('git status --porcelain -- web/callsheet3.html web/nhl.engine.js web/callsheet3.nhl-fields.html tools_build_callsheet3.py')) { want = git('date +%Y-%m-%d'); why = 'edited and not committed, so today'; }
    else { want = git('git log -1 --format=%cs -- web/callsheet3.html'); why = 'committed, so the commit date'; }
  } catch (e) { want = stamp; why = 'no git here'; }
  chk(stamp === want, `build: the stamp is current (${why})`, `page says ${stamp}, expected ${want}`);

  if (errs.length) { console.log('PAGE ERRORS:\n' + errs.join('\n')); fails++; }
  console.log(fails ? `\n${fails} FAILED` : `\nall checks passed (${CASES.length} cases)`);
  await b.close();
  process.exit(fails ? 1 : 0);
})();
