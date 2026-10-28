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
             "agf","aga","hgf","hga","lgg","angp","hngp","aenc","aens","henc","hens",
             "h1line","h1op","h1up","naort","nhort","nadrt","nhdrt","napace","nhpace","nagp","nhgp","nlrtg","nlpace","narest","nhrest","nbaout","nbaq","nbactx","ncrew","nbarefs","nbalineup","nbaform","nbasim"];
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
  // the page's memory is the store (25 Oct 2026): IndexedDB behind a cache, localStorage for the small keys
  await pg.evaluate(() => smStore.ready.then(() => smStore.clear()));
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
  const nbb = block('callsheet3.html', '  /* ===== NBA BLOCK.', '  /* ===== END NBA BLOCK ===== */');
  const nsrc = fs.readFileSync(path.join(__dirname, 'web/nba.engine.js'), 'utf8').replace(/\n$/, '');
  chk(nbb && nbb === nsrc, 'engine: the NBA block is web/nba.engine.js verbatim and follows the NHL block', `${nbb ? nbb.length : 'missing'} vs ${nsrc.length}`);
  chk(html.indexOf('END NHL BLOCK') < html.indexOf('NBA BLOCK.'), 'engine: the NBA block comes after the NHL block', '');

  // ---- fixtures ---------------------------------------------------------------
  const fill = async (sport, inputs) => pg.evaluate(async ([sport, inputs, ids, checks]) => {
    document.getElementById(sport === 'WNBA' ? 'm-wnba' : sport === 'NHL' ? 'm-nhl' : sport === 'NBA' ? 'm-nba' : 'm-mlb').click();
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
    // the alternate total (19 Oct 2026) is a page-only market built from the odds file; the Python engine has no such row
    const got = (await fill(c.sport, c.inputs)).filter(m => m.key !== 'alt');
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
    await smStore.removeItem('callsheet3.card.v1');
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
    const card = JSON.parse(smStore.getItem('callsheet3.card.v1'));
    const names = card.map(r => r.matchup);
    const boardRows = [...document.querySelectorAll('#board tbody tr')].map(tr => ({ market: tr.querySelectorAll('td')[2].textContent, notPicked: !!tr.querySelector('.chip.dim') && /not picked/.test(tr.querySelectorAll('td')[2].textContent) }));
    const bets = [...document.querySelectorAll('#bestBets .pk .n4')].map(e => e.textContent);
    const legs = [...document.querySelectorAll('#picks .pk:not(.parlay) .n4')].map(e => e.textContent);
    const likeliest = [...document.querySelectorAll('#likeliest .pk')].map(e => ({ n1: e.querySelector('.n1').textContent, pick: e.querySelector('.n2').textContent, n3: e.querySelector('.n3').textContent, n4: e.querySelector('.n4').textContent, agrees: e.classList.contains('agrees') }));
    const twoLegs = [...document.querySelectorAll('#twoLegs .pk')].map(e => ({ n1: e.querySelector('.n1').textContent, n2: (e.querySelector('.n2') || {}).textContent || '', n3: e.querySelector('.n3').textContent }));
    // grade game 1: Bruins 3, Rangers 2 (a shootout), first period 1-1
    const tr = () => [...document.querySelectorAll('#cardTable tr')].find(t => /Rangers @ Bruins/.test(t.textContent));
    const label = tr().querySelector('.finals .l').textContent + '|' + [...tr().querySelectorAll('.finals .l')].map(e => e.textContent).join(',');
    const g = (k, v) => { const el = tr().querySelector(`.grade[data-k="${k}"]`); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); };
    // the period score first: both finals lock the row and its score boxes go read-only
    g('f5a', '1'); g('f5h', '1'); g('fa', '2'); g('fh', '3'); await wait();
    const graded = [...tr().querySelectorAll('.rowmk .m')].map(e => ({ pick: e.querySelector('.chip').textContent, res: (e.querySelector('.chip.win,.chip.loss,.chip.push') || {}).textContent || '' }));
    const calib = document.getElementById('calibBox').innerText;
    const boardTiles = [...document.querySelectorAll('#calibBox .calib[data-sport="BOARD"] > div')].map(d => d.querySelector('.k').textContent + ' ' + d.querySelector('.v').textContent + ' | ' + d.querySelector('.s').textContent);
    const nhlBlock = [...document.querySelectorAll('#calibBox .calib[data-sport="NHL"] > div')].map(d => d.querySelector('.k').textContent + ' ' + d.querySelector('.v').textContent + ' ' + d.querySelector('.s').textContent);
    // open the graded row: the rail says "after one"
    tr().querySelector('[data-open]').click(); await wait();
    const final = (document.querySelector('#markets .final') || {}).textContent || '';
    document.getElementById('clear').click(); await wait();
    return { rail, names, boardRows, bets, legs, likeliest, twoLegs, label, graded, calib, boardTiles, nhlBlock, final, sport1: card[0].sport, keys: card[0].markets.map(m => m.key), forecast, proj: card[0].proj };
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
  chk(!flow.bets.some(t => /Moneyline|Puck line/.test(t)), 'picks: no puck line or moneyline reaches the straight bets', JSON.stringify({ bets: flow.bets }));
  // the parlay four from 19 Oct 2026: the likeliest side on each game at any price, so a moneyline or a puck line can be a leg
  chk(flow.legs.length === 2 && flow.legs.every(t => /Rangers @ Bruins|Maple Leafs @ Canadiens/.test(t)), 'picks: the parlay four takes the likeliest side on each of the two games, whatever market it sits in', JSON.stringify({ legs: flow.legs }));
  chk(/P1/.test(flow.label), 'card: the period score boxes are labelled P1 on a hockey row', flow.label);
  const byPick = Object.fromEntries(flow.graded.map(x => [x.pick, x.res]));
  chk(flow.graded.length === 4 && flow.graded.every(x => x.res), 'grade: all four hockey markets grade from a final and a first period', JSON.stringify(flow.graded));
  const plRes = flow.graded.find(x => /\+1\.5|-1\.5/.test(x.pick));
  chk(plRes && ((/Rangers \+1\.5/.test(plRes.pick) && plRes.res === 'win') || (/Bruins -1\.5/.test(plRes.pick) && plRes.res === 'loss')), 'grade: a 3-2 shootout is a one-goal margin, so +1.5 covers and -1.5 does not', JSON.stringify(plRes));
  const totRes = flow.graded.find(x => /^(OVER|UNDER) 6$/.test(x.pick));
  chk(totRes && totRes.res === 'loss' || (totRes && /UNDER/.test(totRes.pick) && totRes.res === 'win'), 'grade: 3-2 is five goals, under the 6', JSON.stringify(totRes));
  chk(flow.nhlBlock.length >= 4 && flow.nhlBlock.some(t => /First period/.test(t)) && flow.nhlBlock.some(t => /Puck line/.test(t)), 'record: the NHL block has first period and puck line tiles', JSON.stringify(flow.nhlBlock));
  chk(flow.likeliest.length === 2 && flow.likeliest.every(x => /^#\d · the (price agrees|book's price, not an edge)$/.test(x.n1) && /^\d\d\.\d% · [-+]\d+ needs \d\d\.\d%$/.test(x.n3))
      && parseFloat(flow.likeliest[0].n3) >= parseFloat(flow.likeliest[1].n3) && flow.likeliest.some(x => /Rangers @ Bruins/.test(x.n4)) && flow.likeliest.some(x => /Toronto|Maple Leafs/.test(x.n4) && /Moneyline/.test(x.n4)),
      'board: the likeliest side in each game at any price, likeliest first, with what its price needs', JSON.stringify(flow.likeliest));
  chk(flow.twoLegs.length === 1 && /^PARLAY #1 · the (price agrees|book's price, not an edge)$/.test(flow.twoLegs[0].n1) && /^both land \d\d?\.\d% · pays [-+]\d+ \(\d\.\d\d×\) needs \d\d\.\d%$/.test(flow.twoLegs[0].n3) && / \+ /.test(flow.twoLegs[0].n2),
      'board: two priced games make one two-leg parlay, with the chance both land, the parlay price and what it needs', JSON.stringify(flow.twoLegs));
  chk(flow.boardTiles.length === 2 && /^Likeliest at any price 1-0 \| says \d\d\.\d% · does 100\.0%/.test(flow.boardTiles[0]) && /^Two-leg parlays 0-0 \| 1 pair still open$/.test(flow.boardTiles[1]),
      'record: the board\'s likeliest side and the two-leg parlays keep their own tiles; one graded game grades the leg and leaves the pair open', JSON.stringify(flow.boardTiles));
  chk(/NHL/.test(flow.calib) && !/WNBA/.test(flow.calib.split('NHL')[0]), 'record: an NHL block is drawn', flow.calib.slice(0, 200));
  chk(/after one 1–1/.test(flow.final) && /Final: Rangers 2, Bruins 3/.test(flow.final), 'rail: opening a graded hockey row prints the final and the score after one', flow.final);

  // ---- the basketball card (15 Oct 2026): add, pick, who is out, grade with the half, record ----
  const nba = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 60));
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    await smStore.removeItem('callsheet3.card.v1');
    document.getElementById('clear').click(); document.getElementById('m-nba').click(); await wait();
    document.getElementById('boardDate').value = '2027-04-06';
    // the last two weeks: the stage delta puts +2 on the line, the half carries its share, the ratings fade is past fifty games
    set('gdate', '2027-04-06'); set('away', 'Raptors'); set('home', 'Boston'); set('line', '221.5'); set('op', '-110'); set('up', '-110');
    set('sp', '-9.5'); set('sph', '-110'); set('spa', '-110'); set('hml', '-450'); set('aml', '340'); set('h1line', '111.5'); set('h1op', '-110'); set('h1up', '-110');
    set('naort', '113.6'); set('nadrt', '111.2'); set('nhort', '117.7'); set('nhdrt', '110.5'); set('napace', '100.8'); set('nhpace', '97.4'); set('nagp', '77'); set('nhgp', '77');
    set('nbaout', JSON.stringify({ away: [{ id: '1', n: 'Scottie Barnes', st: 'Out', mpg: 34.5, ppg: 20.1, pm: 2.2, note: 'knee' }, { id: '2', n: 'Deep Bench', st: 'Out', mpg: 6.0, ppg: 1.5, pm: -0.5 }],
                                   home: [{ id: '3', n: 'Jaylen Brown', st: 'Questionable', mpg: 33.8, ppg: 24.2, pm: 4.0, note: 'ankle' }] }));
    set('nbactx', JSON.stringify([{ side: 'home', k: 'drt', s: 'faded', t: 'Celtics allow 110.5 per 100, 3rd best in the league (77 games).', tag: 'faded: the market over-moves with early-season ratings; past fifty games shown' },
                                  { side: 'away', k: 'pace', s: 'shown', t: 'Raptors play at 100.8 possessions, 8th slowest.', tag: 'shown: pace alone measured null against the close' }]));
    await wait();
    // the starting five: nothing until the box fills, then the away five with its status, the home side RotoWire has not posted
    const lineup0 = document.getElementById('nbaLineupPanel').innerText;
    set('nbalineup', JSON.stringify({ away: { status: 'expected', five: [['PG', 'Immanuel Quickley'], ['SG', 'RJ Barrett'], ['SF', 'Brandon Ingram'], ['PF', 'Jonathan Mogbo'], ['C', 'Jakob Poeltl']], maybe: [['F', 'Scottie Barnes', 'Out']] }, home: null, src: 'RotoWire' }));
    await wait();
    const lineup1 = document.getElementById('nbaLineupPanel').innerText, lineupBadges = [...document.querySelectorAll('#nbaLineupPanel .lbadge')].map(b => b.className + '|' + b.textContent);
    // recent form: the away side's three games with a close, one without; the home side empty
    const form0 = document.getElementById('nbaFormPanel').innerText;
    set('nbaform', JSON.stringify({ away: [
      { date: '2027-03-30', opp: 'Knicks', home: false, pf: 104, pa: 112, h1f: 51, h1a: 58, end: 'REG', ctot: 221.5, ch1: 110.5, csp: -6.5 },
      { date: '2027-04-01', opp: 'Hornets', home: true, pf: 118, pa: 109, h1f: 60, h1a: 52, end: 'OT', ctot: 224.0, ch1: 111.5, csp: -7.5 },
      { date: '2027-04-03', opp: 'Heat', home: false, pf: 99, pa: 101, h1f: 48, h1a: 50, end: 'REG', ctot: null, ch1: null, csp: null },
      // this very game, without a close: once the row is on the card and graded, the panel borrows the card's line, half and spread
      { date: '2027-04-06', opp: 'Celtics', home: false, pf: 101, pa: 115, h1f: 46, h1a: 54, end: 'REG', ctot: null, ch1: null, csp: null }], home: [] }));
    await wait();
    const form1 = document.getElementById('nbaFormPanel').innerText.replace(/\s+/g, ' ').trim();
    const formChips = [...document.querySelectorAll('#nbaFormPanel tbody tr')].map(tr => [...tr.querySelectorAll('.chip')].map(c => c.className.replace('chip ', '') + ':' + c.textContent).join(','));
    const ctxLines =[...document.querySelectorAll('#nbaCtxPanel ul.ctx li')].map(li => li.className + '|' + li.querySelector('.cbadge').textContent + '|' + li.querySelector('.ctext').textContent);
    const visible = { nba: !document.getElementById('nbaFields').hidden, h1: !document.getElementById('h1Fields').hidden, sp: !document.getElementById('spFields').hidden, nhl: !document.getElementById('nhlFields').hidden, pressed: document.getElementById('m-nba').getAttribute('aria-pressed'), label: document.getElementById('lineLabel').textContent };
    const rail = [...document.querySelectorAll('#markets .mk')].map(el => ({ key: el.dataset.key, pick: el.querySelector('.pick').childNodes[0].textContent.trim(), p: parseFloat(el.querySelector('.p').textContent), chips: [...el.querySelectorAll('.cap')].map(c => c.textContent) }));
    const pick = (() => { const c = document.querySelector('#markets .pickcard'); return c ? { key: c.dataset.key || '', side: c.dataset.side || '', lab: c.querySelector('.lab').textContent, why: c.querySelector('.why').textContent, none: c.classList.contains('none') } : null; })();
    const why = document.getElementById('why').textContent;
    const panel0 = document.getElementById('nbaOutPanel').innerText;
    // tick Brown out: the home minutes go from none to 33.8
    const box = document.querySelector('#nbaOutPanel input[data-q="3"]'); box.checked = true; box.dispatchEvent(new Event('change', { bubbles: true })); await wait();
    const panel1 = document.getElementById('nbaOutPanel').innerText, q = document.getElementById('nbaq').value, why1 = document.getElementById('why').textContent;
    const forecast = document.getElementById('forecastLine').textContent;
    document.getElementById('add').click(); await wait();
    document.getElementById('boardDate').dispatchEvent(new Event('change')); await wait();
    const card = JSON.parse(smStore.getItem('callsheet3.card.v1')).filter(r => r.sport === 'NBA');
    const boardRows = [...document.querySelectorAll('#board tbody tr')].map(tr => ({ market: tr.querySelectorAll('td')[2].textContent, notPicked: !!tr.querySelector('.chip.dim') && /not picked/.test(tr.querySelectorAll('td')[2].textContent) }));
    const bets = [...document.querySelectorAll('#bestBets .pk .n4')].map(e => e.textContent);
    // grade: Celtics 115, Raptors 101; 54-46 at the half
    const tr = () => [...document.querySelectorAll('#cardTable tr')].find(t => /Raptors @ Celtics/.test(t.textContent));
    const label = [...tr().querySelectorAll('.finals .l')].map(e => e.textContent).join(',');
    const g = (k, v) => { const el = tr().querySelector(`.grade[data-k="${k}"]`); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); };
    g('f5a', '46'); g('f5h', '54'); g('fa', '101'); g('fh', '115'); await wait();
    const graded = [...tr().querySelectorAll('.rowmk .m')].map(e => ({ pick: e.querySelector('.chip').textContent, res: (e.querySelector('.chip.win,.chip.loss,.chip.push') || {}).textContent || '' }));
    const calib = document.getElementById('calibBox').innerText;
    const nbaBlock = [...document.querySelectorAll('#calibBox .calib[data-sport="NBA"] > div')].map(d => d.querySelector('.k').textContent + ' ' + d.querySelector('.v').textContent + ' ' + d.querySelector('.s').textContent);
    tr().querySelector('[data-open]').click(); await wait();
    const final = (document.querySelector('#markets .final') || {}).textContent || '';
    const reopened = document.getElementById('nbaOutPanel').innerText, lineupReopened = document.getElementById('nbaLineupPanel').innerText;
    const formReopened = document.getElementById('nbaFormPanel').innerText.replace(/\s+/g, ' ').trim();
    document.getElementById('clear').click(); await wait();
    return { visible, rail, pick, why, panel0, panel1, q, why1, forecast, card: card.map(r => r.sport + ':' + r.matchup), keys: card[0].markets.map(m => m.key), boardRows, bets, label, graded, calib, nbaBlock, final, reopened, proj: card[0].proj, ctxLines, ctxStored: (card[0].inputs.nbactx || '').length > 10,
             lineup0, lineup1, lineupBadges, lineupStored: card[0].inputs.nbalineup || '', lineupReopened, form0, form1, formChips, formStored: (card[0].inputs.nbaform || '').indexOf('Hornets') > 0, formReopened };
  });
  chk(/04-06 @ Celtics L 101–115 46–54 U 111\.5 UNDER 216\/221\.5 \+9\.5 NO/.test(nba.formReopened) && /^Raptors last 4: 1-3, over 1-2, covered 1-2/.test(nba.formReopened) && /04-06 @ Celtics L 101–115 46–54 216 no close —/.test(nba.form1),
      'nba: a form game without a close borrows the card\'s own line, half and spread once the game is on the card, read from the right side', JSON.stringify({ before: nba.form1.slice(-120), after: nba.formReopened.slice(0, 420) }));
  chk(/^No recent games on the row/.test(nba.form0) && /^Raptors last 4: 1-3, over 1-1, covered 1-1, 105\.5 for and 109\.3 against, the half 51\.3–53\.5 \(over 1-1\)\./.test(nba.form1)
      && /Celtics: no finals in the ledger yet\./.test(nba.form1) && /03-30 @ Knicks L 104–112 51–58 U 110\.5 UNDER 216\/221\.5 \+6\.5 NO/.test(nba.form1)
      && /04-01 v Hornets W 118–109 \(OT\) 60–52 O 111\.5 OVER 227\/224 -7\.5 COVERED/.test(nba.form1) && /04-03 @ Heat L 99–101 48–50 200 no close —/.test(nba.form1)
      && nba.formChips.join('|') === 'loss:L,under:U 110.5,under:UNDER,loss:NO|win:W,over:O 111.5,over:OVER,win:COVERED|loss:L|loss:L' && nba.formStored,
      'nba: the recent form card lists each side\'s last five with the half, the total and the spread against the close in colour, a game without a close shows its score alone, and the JSON rides in the row',
      JSON.stringify({ form1: nba.form1.slice(0, 400), chips: nba.formChips }));
  chk(/^No lineup on the row/.test(nba.lineup0) && /Raptors\s+expected/i.test(nba.lineup1) && /PG\s+Immanuel Quickley/.test(nba.lineup1) && /C\s+Jakob Poeltl/.test(nba.lineup1) && /May not play: F Scottie Barnes \(Out\)\./.test(nba.lineup1)
      && /Celtics\s+no lineup/i.test(nba.lineup1) && /RotoWire has not posted this side yet/.test(nba.lineup1) && /Source: RotoWire/.test(nba.lineup1)
      && nba.lineupBadges.join(',') === 'lbadge exp|expected,lbadge none|no lineup' && nba.lineupStored.indexOf('Immanuel Quickley') > 0 && /PG\s+Immanuel Quickley/.test(nba.lineupReopened),
      'nba: the starting five panel says no lineup until the box fills, then lists the five with the status and the may-not-play men, says when a side is not posted, rides in the row and comes back when it is reopened',
      JSON.stringify({ l0: nba.lineup0.slice(0, 40), l1: nba.lineup1, badges: nba.lineupBadges, stored: nba.lineupStored.length }));
  chk(nba.ctxLines.length === 2 && nba.ctxLines[0].startsWith('ctx-faded|faded|Celtics allow 110.5 per 100, 3rd best') && nba.ctxLines[1].startsWith('ctx-shown|shown|Raptors play at 100.8') && nba.ctxStored,
      'nba: the context card lists the slate\'s lines with their badges, faded before shown, and the JSON rides in the row', JSON.stringify(nba.ctxLines));
  chk(nba.visible.nba && nba.visible.h1 && nba.visible.sp && !nba.visible.nhl && nba.visible.pressed === 'true' && nba.visible.label === 'Total (points)', 'nba: the fourth button shows the NBA fields, the half and the spread, and hides hockey', JSON.stringify(nba.visible));
  chk(nba.card.length === 1 && nba.card[0] === 'NBA:Raptors @ Celtics' && nba.keys.join(',') === 'total,h1,ml,spread', 'nba: the row stores total, half, moneyline and spread, Boston canonicalised to the NBA table', JSON.stringify({ card: nba.card, keys: nba.keys }));
  const tot = nba.rail.find(r => r.key === 'total');
  chk(tot && /OVER 221\.5/.test(tot.pick) && tot.p > 53 && tot.p < 56, 'nba: the last two weeks put +2 on the line and the over reads about 54%', JSON.stringify(tot));
  chk(nba.pick && !nba.pick.none && nba.pick.key === 'total' && nba.pick.side === 'OVER' && /an OVER game/.test(nba.pick.lab) && /The book's own number makes it 50\.0%; the sheet's inputs move it to 5[3-5]\.\d%/.test(nba.pick.why),
      'nba: the pick is the total, named an OVER game, with the book\'s number and the sheet\'s in the why', JSON.stringify(nba.pick));
  chk(nba.rail.filter(r => r.key === 'ml' || r.key === 'spread').every(r => r.chips.some(c => /shown, not picked/.test(c))) && nba.boardRows.filter(r => /Moneyline|Spread/.test(r.market)).every(r => r.notPicked) && !nba.bets.some(t => /Moneyline|Spread/.test(t)),
      'nba: the moneyline and the spread are shown, not picked, on the rail and the board, and never reach the straight bets', JSON.stringify({ rail: nba.rail.map(r => r.key + ':' + r.chips.join('|')), board: nba.boardRows, bets: nba.bets }));
  chk(/past 50 games a side the market has the ratings priced/.test(nba.why) && /last two weeks of the season/.test(nba.why), 'nba: the why list says the ratings are shown past fifty games and names the stage',
      (nba.why.match(/[^.]*past 50 games[^.]*\./) || ['no ratings note'])[0] + ' | ' + (nba.why.match(/[^.]*last two weeks[^.]*\./) || ['no stage note'])[0]);
  chk(/Raptors: 2 listed, 35 minutes a game of regulars out/.test(nba.panel0) && /Celtics: 1 listed, 0 minutes a game/.test(nba.panel0) && /Regulars out, minutes a game: away 35\./.test(nba.why) && !/home 34/.test(nba.why),
      'nba: who is out lists each side, sums the regulars\' minutes (a six-minute man does not count) and the why carries it', nba.panel0.slice(0, 200) + ' | ' + (nba.why.match(/Regulars out[^.]*\./) || [''])[0]);
  chk(nba.q === '3' && /Celtics: 1 listed, 34 minutes a game/.test(nba.panel1) && /away 35, home 34/.test(nba.why1), 'nba: ticking a doubtful player out adds his minutes and the tick rides in the row', JSON.stringify({ q: nba.q, panel: nba.panel1.slice(0, 160) }));
  chk(/Forecast · Raptors [0-9.]+ – Celtics [0-9.]+ · total [0-9.]+ points · first half [0-9.]+ · Celtics to win, \d+%/.test(nba.forecast), 'nba: the forecast line reads in points with the half and the winner', nba.forecast.slice(0, 200));
  chk(/1H/.test(nba.label) && nba.graded.length === 4 && nba.graded.every(x => x.res), 'nba: the score boxes are labelled 1H and all four markets grade from a final and a half', JSON.stringify({ label: nba.label, graded: nba.graded }));
  const nbaTot = nba.graded.find(x => /^(OVER|UNDER) 221\.5$/.test(x.pick)), nbaH1 = nba.graded.find(x => /1H (OVER|UNDER) 111\.5/.test(x.pick)), nbaSp = nba.graded.find(x => /-9\.5|\+9\.5/.test(x.pick));
  chk(nbaTot && nbaTot.res === (/OVER/.test(nbaTot.pick) ? 'loss' : 'win') && nbaH1 && nbaH1.res === (/OVER/.test(nbaH1.pick) ? 'loss' : 'win') && nbaSp && nbaSp.res === (/Celtics/.test(nbaSp.pick) ? 'win' : 'loss'),
      'nba: 216 is under 221.5, 100 at the half is under 111.5, and Boston by 14 covers -9.5', JSON.stringify([nbaTot, nbaH1, nbaSp]));
  chk(nba.nbaBlock.length >= 4 && nba.nbaBlock.some(t => /First half/.test(t)) && nba.nbaBlock.some(t => /Spread/.test(t)) && /First half projected/.test(nba.calib), 'nba: the record has an NBA block with first-half and spread tiles and the half in the forecast line', JSON.stringify(nba.nbaBlock));
  chk(/at the half 46–54/.test(nba.final) && /Final: Raptors 101, Celtics 115/.test(nba.final) && /Jaylen Brown/.test(nba.reopened), 'nba: reopening the graded row prints the final with the half-time score and the who-is-out list', nba.final + ' | ' + nba.reopened.slice(0, 80));

  // ---- a void row (17 Oct 2026): postponed, counts nowhere, undo brings it back --------
  const voided = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 60));
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    document.getElementById('clear').click(); document.getElementById('m-mlb').click(); await wait();
    document.getElementById('boardDate').value = '2026-11-30';
    set('gdate', '2026-11-30'); set('away', 'Brewers'); set('home', 'Dodgers'); set('line', '8'); set('op', '-105'); set('up', '-115'); set('hml', '-150'); set('aml', '125'); await wait();
    document.getElementById('add').click(); await wait();
    const tr = () => [...document.querySelectorAll('#cardTable tr')].find(t => /Brewers @ Dodgers/.test(t.textContent) && /Nov 30/.test(t.textContent));
    const g = (k, v) => { const el = tr().querySelector(`.grade[data-k="${k}"]`); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); };
    g('f5a', '4'); g('f5h', '4'); g('fa', '6'); g('fh', '4'); await wait();
    const mlbHead = () => (document.querySelector('#calibBox .subhead[data-sport="MLB"]') || {}).textContent || '';
    const gradedBefore = mlbHead();
    const chipsBefore = [...tr().querySelectorAll('.rowmk .chip.win, .rowmk .chip.loss, .rowmk .chip.push')].length;
    document.getElementById('boardDate').dispatchEvent(new Event('change')); await wait();
    const boardBefore = document.querySelectorAll('#board tbody tr').length;
    tr().querySelector('[data-void]').click(); await wait();
    const rowCls = tr().className, tag = (tr().querySelector('.voidtag') || {}).textContent || '', chipsAfter = [...tr().querySelectorAll('.rowmk .chip.win, .rowmk .chip.loss, .rowmk .chip.push')].length;
    const gradedAfter = mlbHead(), boardAfter = document.querySelectorAll('#board tbody tr').length;
    const stored = JSON.parse(smStore.getItem('callsheet3.card.v1')).find(r => /Brewers @ Dodgers/.test(r.matchup) && r.gdate === '2026-11-30').finals;
    const hasUndo = !!tr().querySelector('[data-unvoid]'), hasInputs = !!tr().querySelector('.grade[data-k="fa"]');
    tr().querySelector('[data-unvoid]').click(); await wait();
    const chipsBack = [...tr().querySelectorAll('.rowmk .chip.win, .rowmk .chip.loss, .rowmk .chip.push')].length, gradedBack = mlbHead(), faBack = tr().querySelector('.grade[data-k="fa"]').value;
    document.getElementById('clear').click(); await wait();
    return { gradedBefore, gradedAfter, gradedBack, chipsBefore, chipsAfter, chipsBack, boardBefore, boardAfter, rowCls, tag, stored, hasUndo, hasInputs, faBack };
  });
  const gradedN = s => { const m = s.match(/(\d+) graded game/); return m ? +m[1] : (/nothing graded/.test(s) ? 0 : -1); };
  chk(voided.chipsBefore > 0 && voided.chipsAfter === 0 && voided.rowCls === 'void' && voided.tag === 'no action · postponed' && voided.stored.void === true && voided.stored.fa === '6' && voided.hasUndo && !voided.hasInputs,
      'void: the row goes grey with VOID on it, its grades vanish, the finals stay stored and an undo button replaces the score boxes', JSON.stringify({ before: voided.chipsBefore, after: voided.chipsAfter, cls: voided.rowCls, tag: voided.tag, stored: voided.stored }));
  chk(gradedN(voided.gradedBefore) - gradedN(voided.gradedAfter) === 1 && voided.boardBefore > voided.boardAfter && gradedN(voided.gradedBack) === gradedN(voided.gradedBefore) && voided.chipsBack === voided.chipsBefore && voided.faBack === '6',
      'void: the record and the board leave the row out, and undo void brings the grades and the typed finals back', JSON.stringify({ gradedBefore: voided.gradedBefore, gradedAfter: voided.gradedAfter, gradedBack: voided.gradedBack, board: [voided.boardBefore, voided.boardAfter], chipsBack: voided.chipsBack }));

  // ---- the hockey upset signal (16 Oct 2026): the dog's backup lifts the dog, the moneyline becomes pickable, the board's upset watch lists it ----
  const upset = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 60));
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    const tick = (id, on) => { const el = document.getElementById(id); el.checked = on; el.dispatchEvent(new Event('change', { bubbles: true })); };
    await smStore.removeItem('callsheet3.card.v1');
    document.getElementById('clear').click(); document.getElementById('m-nhl').click(); await wait();
    document.getElementById('boardDate').value = '2026-11-20';
    set('gdate', '2026-11-20'); set('away', 'Rangers'); set('home', 'Bruins'); set('line', '6'); set('op', '-110'); set('up', '-110'); set('hml', '-150'); set('aml', '130');
    set('agsv', '0.905'); set('hgsv', '0.915'); set('agsh', '900'); set('hgsh', '1800'); set('arest', '0'); set('hrest', '2'); await wait();
    const read = () => { const el = document.querySelector('#markets .mk[data-key="ml"]'); const pick = el.querySelector('.pick').childNodes[0].textContent.trim(); const p = parseFloat(el.querySelector('.p').textContent);
      const uc = document.querySelector('#markets .upsetcard');
      return { pick, p, away: /Rangers/.test(pick) ? p : 100 - p, chips: [...el.querySelectorAll('.cap')].map(c => c.textContent), why: document.getElementById('why').textContent,
               card: uc ? { cls: uc.className, lab: uc.querySelector('.lab').textContent, pick: uc.querySelector('.pick').textContent, p: uc.querySelector('.p').textContent, why: uc.querySelector('.why').textContent } : null }; };
    const before = read();
    tick('agbk', true); await wait();
    const after = read();
    document.getElementById('add').click(); await wait();
    document.getElementById('boardDate').dispatchEvent(new Event('change')); await wait();
    const ups = [...document.querySelectorAll('#upsets .pk')].map(e => ({ cls: e.className, n1: e.querySelector('.n1').textContent, n2: e.querySelector('.n2').textContent, n3: e.querySelector('.n3').textContent, n4: e.querySelector('.n4').textContent }));
    const bets = [...document.querySelectorAll('#bestBets .pk .n2')].map(e => e.textContent);
    const stored = JSON.parse(smStore.getItem('callsheet3.card.v1')).find(r => /Rangers @ Bruins/.test(r.matchup) && r.gdate === '2026-11-20').markets.find(m => m.key === 'ml');
    // the favourite's backup instead: no lift, not pickable
    tick('agbk', false); tick('hgbk', true); await wait();
    const favBk = read();
    document.getElementById('clear').click(); await wait();
    return { before, after, ups, bets, informed: stored.informed, favBk };
  });
  chk(Math.abs(upset.after.away - upset.before.away - 5) < 0.15 && !upset.after.chips.some(c => /shown, not picked/.test(c)) && upset.before.chips.some(c => /shown, not picked/.test(c)) && upset.informed === true,
      'upset: the dog\'s backup lifts the dog five points on the moneyline, which becomes pickable and stores the flag', JSON.stringify({ before: upset.before.away, after: upset.after.away, chips: upset.after.chips, informed: upset.informed }));
  chk(/Upset watch, Rangers at \+130: Rangers start a backup \(scored, \+5 points\); Rangers on a back to back: dogs won \+5\.7 points/.test(upset.after.why) && /UPSET SIGNAL: Rangers start a backup/.test(upset.after.why) === false,
      'upset: the why list names the watch with the scored signal first and the back to back after it', (upset.after.why.match(/Upset watch[^.]*\./) || ['none'])[0]);
  chk(upset.ups.length === 1 && /scored/.test(upset.ups[0].cls) && /^UPSET WATCH · a scored signal · the price agrees$/.test(upset.ups[0].n1) && upset.ups[0].n2 === 'Rangers ML' && /backup in the dog's net \(scored, \+5 points\); dog on a back to back/.test(upset.ups[0].n4)
      && upset.bets.some(t => /^Rangers ML/.test(t)),
      'upset: the board\'s upset watch carries the dog with its signals and the dog reaches the straight bets when its price agrees', JSON.stringify({ ups: upset.ups, bets: upset.bets }));
  chk(Math.abs(upset.favBk.away - upset.before.away) < 0.15 && upset.favBk.chips.some(c => /shown, not picked/.test(c)) && /NOT an upset signal/.test(upset.favBk.why),
      'upset: the favourite\'s backup moves nothing and the why says it is not an upset signal', JSON.stringify({ fav: upset.favBk.away, base: upset.before.away }));
  chk(upset.after.card && /scored/.test(upset.after.card.cls) && upset.after.card.lab === 'Upset watch · a scored signal' && upset.after.card.pick === 'Rangers ML' && upset.after.card.p === '47.1%'
      && /^\+130 needs 43\.5%: the price agrees\. Signals: backup in the dog's net \(scored, \+5 points\); dog on a back to back \(\+5\.7 points, watched\)\./.test(upset.after.card.why)
      && upset.after.chips.some(c => c === 'upset signal: Rangers ML 47.1%')
      && upset.before.card && /watched, not scored/.test(upset.before.card.lab) && !/scored/.test(upset.before.card.cls) && upset.before.chips.some(c => /^upset watch: Rangers ML/.test(c)),
      'upset: the matchup rail carries an upset card under the pick, green when the signal is scored, and a chip on the moneyline row', JSON.stringify({ after: upset.after.card, before: upset.before.card }));

  // ---- the NBA short dog (16 Oct 2026): a dog the book makes 40%+ is lifted four points, pickable, on the upset card ----
  const shortDog = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 60));
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    document.getElementById('clear').click(); document.getElementById('m-nba').click(); await wait();
    document.getElementById('boardDate').value = '2026-11-21';
    set('gdate', '2026-11-21'); set('away', 'Hornets'); set('home', 'Bucks'); set('line', '229.5'); set('op', '-110'); set('up', '-110'); set('hml', '-120'); set('aml', '100'); await wait();
    const read = () => { const el = document.querySelector('#markets .mk[data-key="ml"]'); const pick = el.querySelector('.pick').childNodes[0].textContent.trim(); const p = parseFloat(el.querySelector('.p').textContent);
      const uc = document.querySelector('#markets .upsetcard');
      return { pick, p, away: /Hornets/.test(pick) ? p : 100 - p, chips: [...el.querySelectorAll('.cap')].map(c => c.textContent), why: document.getElementById('why').textContent,
               card: uc ? { cls: uc.className, lab: uc.querySelector('.lab').textContent, pick: uc.querySelector('.pick').textContent, p: uc.querySelector('.p').textContent } : null }; };
    const short = read();
    document.getElementById('add').click(); await wait();
    document.getElementById('boardDate').dispatchEvent(new Event('change')); await wait();
    const ups = [...document.querySelectorAll('#upsets .pk')].map(e => ({ cls: e.className, n2: e.querySelector('.n2').textContent, n4: e.querySelector('.n4').textContent }));
    const bets = [...document.querySelectorAll('#bestBets .pk .n2')].map(e => e.textContent);
    set('hml', '-198'); set('aml', '164'); await wait();
    const long = read();
    document.getElementById('clear').click(); await wait();
    return { short, ups, bets, long };
  });
  chk(Math.abs(shortDog.short.away - 51.8) < 0.3 && !shortDog.short.chips.some(c => /shown, not picked/.test(c)) && shortDog.short.chips.some(c => c === 'upset signal: Hornets ML 51.8%')
      && shortDog.short.card && /scored/.test(shortDog.short.card.cls) && shortDog.short.card.pick === 'Hornets ML' && /Upset watch, Hornets at \+100: Hornets a short dog at 48% \(scored, \+4 points\)/.test(shortDog.short.why),
      'nba short dog: -120/+100 lifts the dog to 51.8%, pickable, with the green upset card and the chip', JSON.stringify({ away: shortDog.short.away, chips: shortDog.short.chips, card: shortDog.short.card }));
  chk(shortDog.ups.some(u => /scored/.test(u.cls) && u.n2 === 'Hornets ML' && /a short dog at 48% \(scored, \+4 points\)/.test(u.n4)) && shortDog.bets.some(t => /^Hornets ML/.test(t)),
      'nba short dog: the board\'s upset watch and the straight bets carry the dog', JSON.stringify({ ups: shortDog.ups, bets: shortDog.bets }));
  chk(Math.abs(shortDog.long.away - 36.3) < 0.3 && shortDog.long.chips.some(c => /shown, not picked/.test(c)) && !shortDog.long.card && !/short dog/.test(shortDog.long.why),
      'nba short dog: a dog at 36% is the book\'s number, not pickable, no card', JSON.stringify({ away: shortDog.long.away, chips: shortDog.long.chips }));

  // ---- the NBA early-season side watch: a note on the why list, nothing moved -------
  const earlySide = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 60));
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    document.getElementById('clear').click(); document.getElementById('m-nba').click(); await wait();
    set('gdate', '2026-11-05'); set('away', 'Hornets'); set('home', 'Bucks'); set('line', '229.5'); set('op', '-110'); set('up', '-110'); set('sp', '-3.5'); set('sph', '-110'); set('spa', '-110');
    set('naort', '110'); set('nadrt', '118'); set('nhort', '118'); set('nhdrt', '110'); set('napace', '100'); set('nhpace', '100'); set('nagp', '15'); set('nhgp', '16'); await wait();
    const read = () => { const el = document.querySelector('#markets .mk[data-key="spread"]'); const lk = document.querySelector('#markets .mk.likely'); const lc = document.querySelector('#markets .likelycard'); return { pick: el.querySelector('.pick').childNodes[0].textContent.trim(), p: parseFloat(el.querySelector('.p').textContent), why: document.getElementById('why').textContent, also: (document.querySelector('#markets .pickcard .also') || {}).textContent || '', card: lc ? lc.querySelector('.pick').textContent + ' ' + lc.querySelector('.p').textContent + ' ' + lc.querySelector('.why').textContent : '', likely: lk ? { key: lk.dataset.key, chip: (lk.querySelector('.cap.likely') || {}).textContent || '', other: (lk.querySelector('.other.likely') || {}).textContent || '' } : null }; };
    const early = read();
    set('nagp', '35'); set('nhgp', '36'); await wait();
    const later = read();
    document.getElementById('clear').click(); await wait();
    return { early, later };
  });
  chk(/Early-season side watch: the ratings' margin projects \+16\.0 against the market's \+3\.5, 12\.5 points toward the Bucks\. WATCHED, NOT SCORED: in a club's first 30 games the ratings' side at 4\+ points of lean went 148-124/.test(earlySide.early.why)
      && Math.abs(earlySide.early.p - 50) < 0.6, 'nba early side: at fifteen games the why names the ratings\' side as a watch and the spread stays the book\'s 50%', JSON.stringify({ p: earlySide.early.p, why: (earlySide.early.why.match(/Early-season[^.]*\./) || ['none'])[0] }));
  chk(!/Early-season side watch/.test(earlySide.later.why) && Math.abs(earlySide.later.p - earlySide.early.p) < 0.01, 'nba early side: at thirty-five games the watch is gone and nothing else changed', (earlySide.later.why.match(/Early-season[^.]*\./) || ['none'])[0]);
  chk((earlySide.early.also === 'Also the likeliest side on the card at any price.' && earlySide.early.card === '')
      || (earlySide.early.also === '' && /^(OVER|UNDER) 229\.5 5\d\.\d% -110 needs 52\.4%: the book's price, not an edge\. A high chance at a steep price is the book knowing it, and you paying for it\.$/.test(earlySide.early.card)),
      'likeliest card: a likelier side under its break-even is named as the book\'s price, not an edge, in its card or on the pick card when it is the pick (the unpriced moneyline is passed over)', JSON.stringify({ also: earlySide.early.also, card: earlySide.early.card }));
  chk(earlySide.early.likely && earlySide.early.likely.key === 'total' && /^likeliest at any price(: (OVER|UNDER) 229\.5 5\d\.\d%)? · -110 needs 52\.4%, the book's price$/.test(earlySide.early.likely.chip),
      'rail: the likeliest side at a steep price is chipped as the book\'s price on its own row', JSON.stringify(earlySide.early.likely));

  // ---- the NBA example: a game-day row with every card filled -----------------------
  const nbaEx = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 60));
    document.getElementById('clear').click(); document.getElementById('m-nba').click(); await wait();
    document.getElementById('gdate').value = '2026-11-10';
    document.getElementById('example').click(); await wait();
    const out = document.getElementById('nbaOutPanel').innerText;
    const lineup = document.getElementById('nbaLineupPanel').innerText;
    const ctx = [...document.querySelectorAll('#nbaCtxPanel ul.ctx li')].map(li => li.querySelector('.cbadge').textContent);
    const why = document.getElementById('why').textContent;
    const rail = [...document.querySelectorAll('#markets .mk')].map(el => el.dataset.key + ':' + el.querySelector('.pick').childNodes[0].textContent.trim());
    const pick = (document.querySelector('#markets .pickcard .lab') || {}).textContent || '';
    const also = (document.querySelector('#markets .pickcard .also') || {}).textContent || '';
    const likelyCard = (() => { const el = document.querySelector('#markets .likelycard'); return el ? { lab: el.querySelector('.lab').textContent, pick: el.querySelector('.pick').textContent, p: el.querySelector('.p').textContent, why: el.querySelector('.why').textContent, afterPick: !!(el.previousElementSibling && el.previousElementSibling.classList.contains('pickcard')) } : null; })();
    const likelyRow = (() => { const el = document.querySelector('#markets .mk.likely'); return el ? { key: el.dataset.key, chip: (el.querySelector('.cap.likely') || {}).textContent || '', other: (el.querySelector('.other.likely') || {}).textContent || '' } : null; })();
    const opened = document.getElementById('opened').value;
    const crewText = () => ((document.querySelector('#nbaCrewPanel .ctext') || {}).textContent || '');
    const crew0 = crewText();
    const crewLi = document.querySelector('#nbaCrewPanel .crewblock');
    const crewBlock = { first: !document.querySelector('#nbaCtxPanel ul.ctx li.ctx-crew') && !/^Crew:/.test(document.getElementById('nbaCtxPanel').innerText), cls: crewLi ? crewLi.className : '', alert: ((crewLi && crewLi.querySelector('.crewalert')) || {}).textContent || '',
                        chips: crewLi ? [...crewLi.querySelectorAll('.refchip')].map(e => e.className + '|' + e.textContent.replace(/\s+/g, ' ').trim()) : [], head: ((crewLi && crewLi.closest('section').querySelector('h2')) || {}).textContent || '',
                        call: ((crewLi && crewLi.querySelector('.crewcall')) || {}).textContent || '' };
    // the crew typed by hand: a surname alone matches when it is unique in the table, an unknown name says so
    const el = document.getElementById('ncrew'); el.value = 'Zarba; Nobody Here'; el.dispatchEvent(new Event('input', { bubbles: true })); await wait();
    const crew1 = crewText();
    el.value = ''; el.dispatchEvent(new Event('input', { bubbles: true })); await wait();
    const crew2 = crewText(), ctxNoCrew = document.querySelectorAll('#nbaCtxPanel ul.ctx li').length;
    document.getElementById('add').click(); await wait();
    const stored = JSON.parse(smStore.getItem('callsheet3.card.v1')).find(r => /76ers @ Knicks/.test(r.matchup));
    document.getElementById('clear').click(); await wait();
    return { out, lineup, ctx, why, rail, pick, also, likelyCard, likelyRow, opened, crew0, crew1, crew2, ctxNoCrew, storedRefs: (stored.inputs.nbarefs || '').length > 10, storedCrew: stored.inputs.ncrew, storedLineup: (stored.inputs.nbalineup || '').indexOf('Tyrese Maxey') > 0, crewBlock };
  });
  chk(nbaEx.crewBlock.first && /^crewblock lean-over$/.test(nbaEx.crewBlock.cls) && nbaEx.crewBlock.alert === 'Crew leans OVER · z +4.4' && /^Referee stats/.test(nbaEx.crewBlock.head)
      && nbaEx.crewBlock.chips.join(' || ') === 'refchip over|Scott Foster 66-41 OVER LEAN · 4-2 this season || refchip even|Tony Brothers 56-54 · 3-3 this season || refchip over|Marc Davis 71-51 OVER LEAN'
      && /^Crew call for tonight: free throws \+0\.7 against the league's 44\.0 \(the one thing a crew predicts, t 7\.3\); points [-−]0\.3 a game by their history; the past table's over rate with these 3 is 56\.9% on 339 games, a soft lean to the OVER\. Shown, not scored/.test(nbaEx.crewBlock.call),
      'nba crew: the crew sits on its own Referee stats card, out of the Context list, highlighted with the crew\'s lean as its badge, each official a chip, and a crew call for tonight with the honest weights', JSON.stringify(nbaEx.crewBlock));
  chk(/76ers\s+expected/i.test(nbaEx.lineup) && /Knicks\s+confirmed/i.test(nbaEx.lineup) && /PG\s+Tyrese Maxey/.test(nbaEx.lineup) && /C\s+Karl-Anthony Towns/.test(nbaEx.lineup)
      && /Joel Embiid \(Out\)/.test(nbaEx.lineup) && /Mitchell Robinson \(Out\)/.test(nbaEx.lineup) && nbaEx.storedLineup,
      'nba example: both starting fives on the card, the 76ers expected and the Knicks confirmed, Embiid and Robinson under may-not-play, and the lineup stored with the row', nbaEx.lineup);
  chk(nbaEx.likelyCard && nbaEx.likelyCard.afterPick && nbaEx.likelyCard.lab === 'Likeliest at any price · not the pick' && nbaEx.likelyCard.pick === 'Knicks ML' && nbaEx.likelyCard.p === '66.6%'
      && /^-198 needs 66\.4%: the price agrees\. It is not the pick because the sheet has not moved it a point off the book's own number/.test(nbaEx.likelyCard.why) && nbaEx.also === '',
      'likeliest card: the likeliest side on the whole card sits in its own card right under the pick, with its chance and what its price needs', JSON.stringify(nbaEx.likelyCard));
  chk(nbaEx.likelyRow && nbaEx.likelyRow.key === 'ml' && nbaEx.likelyRow.chip === 'likeliest at any price · -198 needs 66.4%, the price agrees' && nbaEx.likelyRow.other === '',
      'rail: the likeliest side\'s market row is outlined and chipped with what its price needs', JSON.stringify(nbaEx.likelyRow));
  chk(nbaEx.crew0 === 'Crew: Scott Foster 46.2 free throws and 229.1 points a game (118 games), over the close 66-41 the last two seasons and 4-2 this season; Tony Brothers 43.1 free throws and 226.0 points a game (95 games), over the close 56-54 the last two seasons and 3-3 this season; Marc Davis 44.8 free throws and 230.3 points a game (102 games), over the close 71-51 the last two seasons; the league 44.0 and 228.8.',
      'nba crew: the Referee stats card carries the crew line, each referee\'s free throws, points and record against the close, past seasons and this one', nbaEx.crew0);
  chk(nbaEx.crew1 === 'Crew: Zarba 42.9 free throws and 227.4 points a game (110 games), over the close 58-60 the last two seasons and 2-5 this season; Nobody Here (no games in the ledger); the league 44.0 and 228.8.' && nbaEx.crew2 === '' && nbaEx.ctxNoCrew === 9,
      'nba crew: a typed surname matches the table, an unknown name says so, and an empty box drops the line while the Context list keeps its nine', JSON.stringify({ crew1: nbaEx.crew1, crew2: nbaEx.crew2, n: nbaEx.ctxNoCrew }));
  chk(nbaEx.storedRefs && nbaEx.storedCrew === '', 'nba crew: the referee table rides in the row and the crew box is stored as typed', JSON.stringify({ refs: nbaEx.storedRefs, crew: nbaEx.storedCrew }));
  chk(/76ers: 3 listed, 32 minutes a game of regulars out/.test(nbaEx.out) && /Knicks: 2 listed, 22 minutes a game/.test(nbaEx.out) && /Embiid \(knee\) has been ruled out/.test(nbaEx.out) && /back Nov 10/.test(nbaEx.out) && /last season's line/.test(nbaEx.out),
      'nba example: the who-is-out card lists both sides with the comments, the return dates and the traded man\'s last-season line', nbaEx.out.slice(0, 300));
  chk(nbaEx.ctx.length === 9 && nbaEx.ctx.slice(0, 3).every(b => b === 'faded') && nbaEx.ctx.indexOf('label') > nbaEx.ctx.indexOf('shown'), 'nba example: nine context lines without the crew, faded first, labels last', JSON.stringify(nbaEx.ctx));
  chk(/Ratings, faded/.test(nbaEx.why) && /Early-season side watch/.test(nbaEx.why) && /Back to back for the home side/.test(nbaEx.why) && /Regulars out, minutes a game: away 32, home 22/.test(nbaEx.why) && /The number moved 229\.5 to 231\.5/.test(nbaEx.why),
      'nba example: the why list carries the fade, the side watch, the back to back, the regulars out and the move off the opener', nbaEx.why.slice(0, 400));
  chk(nbaEx.rail.length === 4 && nbaEx.opened === '229.5' && /an? (OVER|UNDER) game|No pick/.test(nbaEx.pick), 'nba example: all four markets on the rail, the opener in its box, a pick card', JSON.stringify({ rail: nbaEx.rail, pick: nbaEx.pick, opened: nbaEx.opened }));

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
    const stored = JSON.parse(smStore.getItem('callsheet3.card.v1')).find(r => /Wild @ Blues/.test(r.matchup));
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
    const stored = JSON.parse(smStore.getItem('callsheet3.card.v1')).find(r => /Kraken @ Canucks/.test(r.matchup));
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
    await smStore.removeItem('callsheet3.card.v1');
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
    const stored = JSON.parse(smStore.getItem('callsheet3.card.v1')).find(r => /Kraken @ Canucks/.test(r.matchup) && r.gdate === '2026-11-09');
    // a later odds file with a moved number: the carded line stays
    await load({ format: 'callsheet2.slate', version: 1, date: '2026-11-09', games: [ Object.assign({}, game, { inputs: { line: '6.5', op: '-115', up: '-105' } }) ] }, 'odds-2026-11-09.json');
    // the backup test left its own Kraken @ Canucks row (12 Nov) on the in-memory card, so find this one by its date
    const mine = r => /Kraken @ Canucks/.test(r.matchup) && r.gdate === '2026-11-09';
    const row1 = JSON.parse(smStore.getItem('callsheet3.card.v1')).find(mine);
    // the grade file with the close attached
    await load({ format: 'callsheet2.slate', version: 1, date: '2026-11-09', games: [ Object.assign({}, game, { finals: { fa: '2', fh: '1', f5a: '1', f5h: '0' }, close: { ctot: '6.5', cf5: '1.5' }, starters: { away: 'S. Skinner', home: 'D. Wolf' } }) ] }, 'nhl-grade-2026-11-09.json');
    await wait();
    const row2 = JSON.parse(smStore.getItem('callsheet3.card.v1')).find(mine);
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
  chk(/not picked/.test(twoDays.boardP1), 'two days: the board marks the first period not picked', JSON.stringify({ board: twoDays.boardP1 }));
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

  // ---- 13 Oct 2026: the why list flags an alternate period number and a Backup tick over a starter ----
  const flags = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 60));
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    document.getElementById('clear').click(); document.getElementById('m-nhl').click(); await wait();
    set('gdate', '2026-10-21'); set('away', 'Wild'); set('home', 'Blues'); set('line', '6'); set('op', '-110'); set('up', '-110');
    set('p1line', '2.5'); set('p1op', '240'); set('p1up', '-325'); await wait();
    const alt = document.getElementById('why').textContent;
    set('p1line', '1.5'); set('p1op', '-155'); set('p1up', '115'); await wait();
    const main = document.getElementById('why').textContent;
    set('ngoalies', JSON.stringify({ away: [{ n: 'Jesper Wallstedt', sv: 0.912, sh: 180, gs: 6, cs: 6, ls: false }], home: [{ n: 'Jordan Binnington', sv: 0.901, sh: 170, gs: 5, cs: 6, ls: false }] }));
    set('agname', 'Jesper Wallstedt'); set('hgname', 'Jordan Binnington');
    document.getElementById('agbk').checked = true; document.getElementById('agbk').dispatchEvent(new Event('change', { bubbles: true })); await wait();
    const tick = document.getElementById('why').textContent;
    document.getElementById('agbk').checked = false; document.getElementById('agbk').dispatchEvent(new Event('change', { bubbles: true })); await wait();
    const untick = document.getElementById('why').textContent;
    document.getElementById('clear').click(); await wait();
    return { alt, main, tick, untick };
  });
  chk(/The first-period line 2\.5 at \+240\/-325 reads as an ALTERNATE number: its two prices sit 47 points of implied chance apart/.test(flags.alt) && /NOT READ/.test(flags.alt) && !/First-period market as a second read/.test(flags.alt),
      'flags: a period line priced +240/-325 is named an alternate number in the why list and is not read into the projection', flags.alt.slice(flags.alt.indexOf('ALTERNATE') - 60, flags.alt.indexOf('ALTERNATE') + 120));
  chk(!/ALTERNATE/.test(flags.main) && /First-period market as a second read/.test(flags.main), 'flags: the widest main period line carded, -155/+115, draws no alternate flag and is read as before', '');
  chk(/Backup in net is ticked for Jesper Wallstedt, who has 6 of the club's 6 starts/.test(flags.tick) && /Untick it unless RotoWire or CBS names a different starter/.test(flags.tick),
      'flags: a Backup tick over the goalie with every start is called out, with the untick instruction', flags.tick.slice(flags.tick.indexOf('Backup in net is ticked') - 20, flags.tick.indexOf('Backup in net is ticked') + 200));
  chk(!/Backup in net is ticked/.test(flags.untick), 'flags: unticked, the call-out goes', '');

  // ---- the slate fills the goalie boxes; a 2.0 backup carries MLB only --------------
  const slate = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 80));
    const slateDoc = { format: 'callsheet2.slate', version: 1, date: '2026-11-07', games: [
      { sport: 'NHL', gdate: '2026-11-07', away: 'Oilers', home: 'Flames', starters: { away: 'Skinner', home: 'Wolf' },
        inputs: { agsv: '0.908', hgsv: '0.916', agsh: '1200', hgsh: '1300', asf: '30.1', hsf: '28.9', app: '25.0', hpp: '19.5', apk: '78.0', hpk: '81.2', al10: '6.4', hl10: '5.9', h2h: '6.0', h2hn: '2', arest: '0', hrest: '1', ap1l10: '1.90', hp1l10: '1.70', axgf: '3.40', axga: '3.10', hxgf: '3.30', hxga: '2.90', xglg: '3.05', agbk: true, hgbk: false, agconf: false, hgconf: true,
                  agname: 'Stuart Skinner', hgname: 'Dustin Wolf',
                  ngoalies: JSON.stringify({ away: [{ n: 'Stuart Skinner', sv: 0.908, sh: 1200, gs: 10, cs: 12, ls: false }, { n: 'Calvin Pickard', sv: 0.897, sh: 450, gs: 2, cs: 12, ls: false }],
                                            home: [{ n: 'Dustin Wolf', sv: 0.916, sh: 1300, gs: 11, cs: 12, ls: false }, { n: 'Devin Cooley', sv: 0.902, sh: 300, gs: 1, cs: 12, ls: false }] }),
                  nhlform: JSON.stringify({ away: [{ date: '2026-10-04', opp: 'Jets', home: false, gf: 2, ga: 5, sf: 24, sa: 38, p1f: 0, p1a: 2, goalie: 'S. Skinner', end: 'REG' }, { date: '2026-10-06', opp: 'Kings', home: true, gf: 3, ga: 4, sf: 27, sa: 36, p1f: 1, p1a: 1, goalie: 'C. Pickard', end: 'OT' }], home: [{ date: '2026-10-05', opp: 'Sharks', home: true, gf: 4, ga: 1, sf: 33, sa: 22, p1f: 2, p1a: 0, goalie: 'D. Wolf', end: 'REG' }] }),
                  nhlctx: JSON.stringify([
                    { side: 'home', k: 'rates', s: 'faded', t: 'Flames allow 3.90 a game, 4th most in the league (12 games).', tag: 'scored, faded: the market over-moves with scoring reputations, so the lean goes on the line at −0.25 a goal, tagged' },
                    { side: 'away', k: 'goalie_backup', s: 'scored', t: 'Stuart Skinner .908 on 1200 shots, 22nd of 40 goalies with 100+ shots.', tag: 'the backup rule: a tagged −0.15 on the line, −0.25 if his line reads cold; the line itself is not scored' },
                    { side: 'home', k: 'special', s: 'shown', t: 'Flames kill at 81.2%, 6th best in the league.', tag: 'shown, not scored: special teams measured the wrong way against the close' },
                    { side: 'away', k: 'rest', s: 'label', t: 'Oilers on a back to back.', tag: 'a label: the goalie line carries a back to back' }]) },
        notes: ['Away back to back: likely the backup in net'] } ] };
    const dt = new DataTransfer(); dt.items.add(new File([JSON.stringify(slateDoc)], 'slate-2026-11-07.json', { type: 'application/json' }));
    const inp = document.getElementById('slateFile'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true })); await wait();
    const list = document.getElementById('slateList').innerText;
    document.querySelector('#slateList [data-slate]').click(); await wait();
    const v = id => document.getElementById(id).value;
    const form = { away: v('away'), home: v('home'), agsv: v('agsv'), hgsh: v('hgsh'), asf: v('asf'), apk: v('apk'), arest: v('arest'), line: v('line'), pressed: document.getElementById('m-nhl').getAttribute('aria-pressed'),
                   agbk: document.getElementById('agbk').checked, hgbk: document.getElementById('hgbk').checked,
                   agconf: document.getElementById('agconf').checked, hgconf: document.getElementById('hgconf').checked,
                   panel: document.getElementById('formPanel').innerText, ap1l10: v('ap1l10'), hp1l10: v('hp1l10'), axgf: v('axgf'), hxga: v('hxga'), xglg: v('xglg'),
                   why: document.getElementById('why').textContent,
                   p1why: [...document.querySelectorAll('#markets .mk[data-key="p1"] .mkdetail')].map(e => e.textContent).join(' '),
                   ctx: [...document.querySelectorAll('#ctxPanel ul.ctx li')].map(li => li.className + '|' + li.querySelector('.cbadge').textContent + '|' + li.querySelector('.ctext').textContent + '|' + (li.querySelector('.ctag') || {}).textContent),
                   ctxStored: v('nhlctx').length > 10 };
    document.getElementById('clear').click(); await wait();
    const ctxCleared = document.getElementById('ctxPanel').textContent;
    document.getElementById('slateClear').click(); document.getElementById('clear').click(); await wait();
    // a 2.0 backup with an MLB row and a WNBA row: both join the card, and loading it twice adds nothing
    const before = JSON.parse(smStore.getItem('callsheet3.card.v1') || '[]');
    const b2 = { format: 'callsheet2.backup', version: 1, card: [
      { id: 1, sport: 'MLB', away: 'Rays', home: 'Yankees', matchup: 'Rays @ Yankees', gdate: '2026-09-22', inputs: { away: 'Rays', home: 'Yankees', line: '6.5', op: '-110', up: '-110', gdate: '2026-09-22' }, markets: [{ key: 'total', label: 'Full-game total 6.5', pick: 'UNDER 6.5', side: 'UNDER', p: 0.52, pPush: 0, price: -110, edge: -0.004, fair: -108, anchored: true, band: 'NO BET', other: { pick: 'OVER 6.5', p: 0.48, price: -110, edge: -0.044 } }], finals: { fa: '2', fh: '3' } },
      { id: 2, sport: 'WNBA', away: 'Sun', home: 'Mystics', matchup: 'Sun @ Mystics', gdate: '2026-09-22', inputs: { away: 'Sun', home: 'Mystics', line: '162.5', gdate: '2026-09-22' }, markets: [], finals: {} } ] };
    const dt2 = new DataTransfer(); dt2.items.add(new File([JSON.stringify(b2)], 'callsheet2-2026-09-30.json', { type: 'application/json' }));
    const inp2 = document.getElementById('restoreFile'); inp2.files = dt2.files; inp2.dispatchEvent(new Event('change', { bubbles: true })); await wait();
    const card = JSON.parse(smStore.getItem('callsheet3.card.v1'));
    const msg = document.getElementById('saveMsg').textContent;
    const dt3 = new DataTransfer(); dt3.items.add(new File([JSON.stringify(b2)], 'callsheet2-2026-09-30.json', { type: 'application/json' }));
    inp2.files = dt3.files; inp2.dispatchEvent(new Event('change', { bubbles: true })); await wait();
    const again = JSON.parse(smStore.getItem('callsheet3.card.v1'));
    const msg2 = document.getElementById('saveMsg').textContent;
    const wnbaBtn = document.getElementById('m-wnba');
    return { list, form, before: before.length, card: card.map(r => r.sport + ':' + r.matchup), ids: card.map(r => r.id), msg,
             again: again.length, msg2, wnbaHidden: wnbaBtn.hidden, wnbaOffset: wnbaBtn.offsetParent !== null, ctxCleared };
  });
  chk(slate.form.ctx.length === 4 && slate.form.ctx[0] === 'ctx-scored|scored|Stuart Skinner .908 on 1200 shots, 22nd of 40 goalies with 100+ shots.|the backup rule: a tagged −0.15 on the line, −0.25 if his line reads cold; the line itself is not scored'
      && slate.form.ctx[1].startsWith('ctx-faded|faded|Flames allow 3.90 a game, 4th most in the league (12 games).|scored, faded') && slate.form.ctx[2].startsWith('ctx-shown|shown|Flames kill at 81.2%') && slate.form.ctx[3].startsWith('ctx-label|label|Oilers on a back to back.') && slate.form.ctxStored,
      'context: the card lists the slate\'s lines scored first, each with its badge and the tag that says what the sheet did with it, and the JSON rides in the form', JSON.stringify(slate.form.ctx));
  chk(/No context on the row/.test(slate.ctxCleared), 'context: Clear empties the card', slate.ctxCleared.slice(0, 80));
  chk(/Oilers @ Flames/.test(slate.list) && /SV 0\.908\/0\.916/.test(slate.list) && /Skinner v Wolf/.test(slate.list) && /likely the backup/.test(slate.list),
      'slate: a hockey game lists with its goalies, save percentages and note', slate.list.slice(0, 200));
  chk(slate.form.pressed === 'true' && slate.form.away === 'Oilers' && slate.form.agsv === '0.908' && slate.form.hgsh === '1300' && slate.form.asf === '30.1' && slate.form.apk === '78.0' && slate.form.arest === '0' && slate.form.line === '',
      'slate: Fill form switches to NHL and fills the goalie, shot, special-teams and rest boxes, never the line', JSON.stringify(slate.form));
  chk(slate.form.ap1l10 === '1.90' && slate.form.hp1l10 === '1.70', 'slate: the first-period last ten fills from the ledger fields', JSON.stringify({ a: slate.form.ap1l10, h: slate.form.hp1l10 }));
  chk(slate.form.agbk === true && slate.form.hgbk === false, 'slate: the Backup in net box is ticked from the slate for the away side only', JSON.stringify({ a: slate.form.agbk, h: slate.form.hgbk }));
  chk(slate.form.agconf === false && slate.form.hgconf === true, 'slate: the Confirmed box is ticked from the slate when RotoWire marks the start confirmed (the home side here), never otherwise', JSON.stringify({ a: slate.form.agconf, h: slate.form.hgconf }));

  // ---- the goalie picker: the slate's lists, a pick fills the line and the backup box, the grade file checks it ----
  const picker = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 80));
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    await smStore.removeItem('callsheet3.card.v1');
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
    const row = JSON.parse(smStore.getItem('callsheet3.card.v1')).find(r => /Oilers @ Flames/.test(r.matchup));
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

  // ---- 14 Oct 2026: colour in the record section, the favourite table and the forecast line ----
  const colour = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 80));
    // twelve graded hockey games with a -250 home favourite: it won eleven by two or more, lost one
    const rows = [];
    for (let i = 0; i < 12; i++) {
      const win = i < 11;
      rows.push({ id: 9001 + i, sport: 'NHL', away: 'Sharks', home: 'Bruins', matchup: 'Sharks @ Bruins', gdate: '2026-09-' + String(5 + i).padStart(2, '0'),
                  inputs: { away: 'Sharks', home: 'Bruins', gdate: '2026-09-' + String(5 + i).padStart(2, '0'), line: '6', op: '-110', up: '-110', hml: '-250', aml: '200', p1line: '1.5' },
                  proj: { t: 6.1, h: 0.7, a: 0.3, q: 1.7, re: false }, markets: [], finals: win ? { fa: '1', fh: '4', f5a: '0', f5h: '2' } : { fa: '3', fh: '2', f5a: '1', f5h: '1' } });
    }
    const doc = { format: 'callsheet2.backup', version: 1, card: rows };
    const dt = new DataTransfer(); dt.items.add(new File([JSON.stringify(doc)], 'callsheet3-2026-09-17.json', { type: 'application/json' }));
    const inp = document.getElementById('restoreFile'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true })); await wait();
    const tr = [...document.querySelectorAll('#calibBox .favs[data-sport="NHL"] tr')].find(t => /−200 or more/.test(t.textContent));
    const cells = tr ? [...tr.querySelectorAll('td')].map(td => (td.className || '-') + ':' + td.textContent) : [];
    const small = [...document.querySelectorAll('#calibBox .favs[data-sport="NHL"] tr')].filter(t => /−149 to −120/.test(t.textContent)).map(t => [...t.querySelectorAll('td.up, td.down')].length);
    const fc = document.querySelector('#calibBox .forecast[data-sport="NHL"]');
    const legend = (document.querySelector('#calibBox .favs[data-sport="NHL"]') || {}).textContent || '';
    return { cells, small, forecastSpans: fc ? fc.querySelectorAll('span.up, span.down').length : -1, forecastText: fc ? fc.textContent : '', legend };
  });
  chk(colour.cells.length === 7 && /^up:9[0-9]\.\d%$/.test(colour.cells[2]) && /^ref:/.test(colour.cells[3]) && /^down:8\.3%$/.test(colour.cells[4]) && /^up:91\.7%$/.test(colour.cells[5]) && /^up:\+/.test(colour.cells[6]),
      'colour: on twelve games the favourite row goes green where it beats the implied chance and the two-season rate, red where it trails, green on a positive return', JSON.stringify(colour.cells));
  chk(colour.small.every(n => n === 0), 'colour: a bucket under ten games stays uncoloured', JSON.stringify(colour.small));
  chk(colour.forecastSpans >= 1 && /projected total lands/.test(colour.forecastText), 'colour: the forecast line tones the sheet\'s figures against the market\'s', colour.forecastText.slice(0, 200));
  chk(/Green beats its reference by 2 points or more, red trails it/.test(colour.legend) && /Colour after 10 games/.test(colour.legend), 'colour: the table says what the colours mean', colour.legend.slice(0, 400));

  // ---- 19 Oct 2026: the Props tab -- a props file lists, a grade file grades, the record tile and the backup carry it ----
  const propsT = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 80));
    await smStore.removeItem('callsheet3.props.v1');
    const propsDoc = { format: 'callsheet3.props', version: 1, date: '2026-10-21', games: [
      { gid: '401909834', away: 'Hawks', home: 'Magic', aab: 'ATL', hab: 'ORL', spread: -4.5, total: 229.5, pace: 99.8, props: [
        { pid: '3037789', name: 'Trae Young', team: 'ATL', opp: 'ORL', home: false, pos: 'PG', mk: 'pts', line: 24.5, op: -110, up: -110, book: 'fanatics', books: { fanatics: [24.5, -110, -110], draftkings: [25.5, -115, -105] },
          proj: 27.2, sd: 9.4, pm: 0.612, pb: 0.5, p: 0.5604, push: 0, side: 'OVER', chance: 0.5604, price: -110, need: 0.5238, edge: 0.0366, band: 'BET', mins: 35.1, rate36: 27.9,
          why: ['27.9 points per 36 this season (3 games, 104 minutes)', '35.1 minutes projected'], log: [['2026-10-15', 'MIA', 0, 34.0, 26], ['2026-10-17', 'CHI', 1, 31.0, 22], ['2026-10-19', 'BOS', 0, 12.5, null]] },
        { pid: '4066261', name: 'Jalen Suggs', team: 'ORL', opp: 'ATL', home: true, pos: 'SG', mk: 'ast', line: 4.5, op: -120, up: -100, book: 'fanatics', books: { fanatics: [4.5, -120, -100] },
          why: ['no history to project from (under 60 minutes with the stat in the ledgers)'], log: [] },
        { pid: '4397020', name: 'Paolo Banchero', team: 'ORL', opp: 'ATL', home: true, pos: 'PF', mk: 'reb', line: 7.5, op: -105, up: -115, book: 'fanatics', books: { fanatics: [7.5, -105, -115] },
          proj: 7.1, sd: 3.5, pm: 0.45, pb: 0.4773, p: 0.468, push: 0, side: 'UNDER', chance: 0.532, price: -115, need: 0.5349, edge: -0.0029, band: 'no edge', mins: 33.0, rate36: 7.7, why: ['7.7 rebounds per 36'], log: [] } ] } ] };
    const load = async (doc, fname) => { const dt = new DataTransfer(); dt.items.add(new File([JSON.stringify(doc)], fname, { type: 'application/json' })); const inp = document.getElementById('slateFile'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true })); await wait(); };
    // a file that projects nothing says why: the run read no ledger
    await load({ format: 'callsheet3.props', version: 1, date: '2026-10-23', ledgers: { folder: 'C:\\Users\\J\\Downloads', this: { season: '2026-27', games: 0, lines: 0 }, last: { season: '2025-26', games: 0, lines: 0 } },
                 games: [{ gid: 'z', away: 'Bulls', home: 'Bucks', aab: 'CHI', hab: 'MIL', props: [{ pid: '1', name: 'Josh Giddey', team: 'CHI', opp: 'MIL', home: false, pos: 'G', mk: 'pts', line: 12.5, op: -135, up: 100, book: 'fanatics', books: {}, why: ['no history to project from (under 60 minutes with the stat in the ledgers)'], log: [] }] }] }, 'nba-props-2026-10-23.json');
    const noneMsg = document.getElementById('propsMsg').innerText.replace(/\s+/g, ' ');
    document.getElementById('propsClear').click(); await wait();
    // a file whose projections rest on this season alone says last season's ledger was not read (25 Oct 2026)
    await load({ format: 'callsheet3.props', version: 1, date: '2026-10-24', ledgers: { folder: 'C:\\Users\\J\\slate', this: { season: '2026-27', games: 16, lines: 400 }, last: { season: '2025-26', games: 0, lines: 0 } },
                 games: [{ gid: 'y', away: 'Heat', home: 'Hornets', aab: 'MIA', hab: 'CHA', props: [
                   { pid: '1', name: 'Bam Adebayo', team: 'MIA', opp: 'CHA', home: false, pos: 'C', mk: 'reb', line: 9.5, op: -105, up: -125, book: 'betmgm', books: {}, proj: 10.8, sd: 3.6, pm: 0.6, pb: 0.5, p: 0.57, push: 0, side: 'OVER', chance: 0.57, price: -105, need: 0.512, edge: 0.058, band: 'LEAN', mins: 31, rate36: 12.5, why: ['12.5 rebounds per 36 this season (2 games, 63 minutes); no last season to blend'], log: [] },
                   { pid: '2', name: 'Naz Reid', team: 'CHA', opp: 'MIA', home: true, pos: 'F', mk: 'pts', line: 14.5, op: -110, up: -110, book: 'betmgm', books: {}, why: ['no history to project from (under 60 minutes with the stat in the ledgers)'], log: [] }] }] }, 'nba-props-2026-10-24.json');
    const thinMsg = document.getElementById('propsMsg').innerText.replace(/\s+/g, ' ');
    document.getElementById('propsClear').click(); await wait();
    // a file written after a game tipped leaves that game's props out
    await load({ format: 'callsheet3.props', version: 1, date: '2026-10-23', generated: '2026-10-24T01:10:00Z', games: [
      { gid: 'a', away: 'Bulls', home: 'Bucks', aab: 'CHI', hab: 'MIL', tip: '2026-10-24T00:00Z', props: [{ pid: '1', name: 'Josh Giddey', team: 'CHI', opp: 'MIL', home: false, pos: 'G', mk: 'pts', line: 12.5, op: -135, up: 100, book: 'fanatics', books: {}, proj: 14.1, sd: 6.9, pm: 0.58, pb: 0.5, p: 0.53, push: 0, side: 'OVER', chance: 0.53, price: -135, need: 0.574, edge: -0.044, band: 'no edge', mins: 30, rate36: 16.9, why: ['x'], log: [] }] },
      { gid: 'b', away: 'Knicks', home: 'Celtics', aab: 'NYK', hab: 'BOS', tip: '2026-10-24T02:30Z', props: [{ pid: '2', name: 'Paul George', team: 'BOS', opp: 'NYK', home: true, pos: 'F', mk: 'pts', line: 17.5, op: -110, up: -110, book: 'fanatics', books: {}, proj: 19.0, sd: 8.1, pm: 0.57, pb: 0.5, p: 0.524, push: 0, side: 'OVER', chance: 0.524, price: -110, need: 0.524, edge: 0.0, band: 'no edge', mins: 32, rate36: 21.4, why: ['x'], log: [] }] }] }, 'nba-props-2026-10-23.json');
    const inPlay = { msg: document.getElementById('propsMsg').innerText.replace(/\s+/g, ' '), names: JSON.parse(smStore.getItem('callsheet3.props.v1')).map(r => r.name) };
    document.getElementById('propsClear').click(); await wait();
    await load(propsDoc, 'nba-props-2026-10-21.json');
    const tabEmpty0 = document.getElementById('propsCalib').innerText.replace(/\s+/g, ' ').trim();
    const viewOn = !document.getElementById('propsView').hidden, colsOff = document.querySelector('.cols').hidden, pressed = document.getElementById('m-props').getAttribute('aria-pressed');
    const best = [...document.querySelectorAll('#propsBest .pk')].map(e => e.innerText.replace(/\s+/g, ' ').trim());
    const rowsOn = document.querySelectorAll('#propsTable tr[data-prop]').length;
    document.getElementById('propsAll').checked = true; document.getElementById('propsAll').dispatchEvent(new Event('change', { bubbles: true })); await wait();
    const rowsAll = document.querySelectorAll('#propsTable tr[data-prop]').length;
    const count = document.getElementById('propsCount').textContent, msg = document.getElementById('propsMsg').textContent;
    document.querySelector('#propsTable tr[data-prop]').click(); await wait();
    const whyOpen = document.getElementById('propDetail').hidden ? [] : [document.getElementById('propDetailBody').innerText.replace(/\s+/g, ' ').trim()];
    const logMarks = [...document.querySelectorAll('#propDetail .pd-log b.lg')].map(b => b.className + '|' + b.textContent);
    document.getElementById('propDetailClose').click(); await wait();
    const tileBefore = !!document.querySelector('#calibBox .calib[data-sport="PROPS"]');
    const gradeDoc = { format: 'callsheet2.slate', version: 1, date: '2026-10-21', games: [
      { sport: 'NBA', gdate: '2026-10-21', away: 'Hawks', home: 'Magic', gameId: '401909834', finals: { fa: '118', fh: '112', f5a: '60', f5h: '55' }, notes: [],
        box: { '3037789': ['Trae Young', 36.2, 28, 3, 11, 4, { pts: ['won by 6', '36 min (his usual 34)', '22 shots (his usual 21 at those minutes)', '10 of 19 from the floor'], reb: ['won by 6', '36 min (his usual 34)', '3 of the club\'s 44 rebounds (his usual 9%)'], ast: ['Dyson Daniels out (30 mpg, a lift for him)', 'won by 6', '11 of the club\'s 27 assists, 41% (his usual 30%)'], tpm: ['won by 6'], pra: ['won by 6'] }], '4397020': ['Paolo Banchero', 34.0, 22, 9, 4, 1] } } ] };
    await load(gradeDoc, 'nba-grade-2026-10-21.json');
    const after = JSON.parse(smStore.getItem('callsheet3.props.v1'));
    // the graded night joins the panel's last games, with his minutes from the box line (25 Oct 2026)
    document.querySelector('#propsTable tr[data-prop]').click(); await wait();
    const thisRow = (document.querySelector('#propDetail .pd-log tr.this') || { innerText: '' }).innerText.replace(/\s+/g, ' ').trim(), thisMark = (document.querySelector('#propDetail .pd-log tr.this b.lg') || { className: '' }).className;
    const thisWhat = (document.querySelector('#propDetail .pd-log tr.this td.pd-what') || { innerText: '' }).innerText.replace(/\s+/g, ' ').trim(), whatHead = [...document.querySelectorAll('#propDetail .pd-log thead th')].map(t => t.textContent.trim()).join('|'), otherWhat = [...document.querySelectorAll('#propDetail .pd-log tbody tr:not(.this) td.pd-what')].map(td => td.textContent.trim());
    const logRows = document.querySelectorAll('#propDetail .pd-log tbody tr').length;
    document.getElementById('propDetailClose').click(); await wait();
    const tile = document.querySelector('#calibBox .calib[data-sport="PROPS"]');
    const tileText = tile ? tile.innerText.replace(/\s+/g, ' ').trim() : '';
    const tabCalib = document.getElementById('propsCalib').innerText.replace(/\s+/g, ' ').trim();
    const tabBlocks = ['PROPS-TAB', 'PROPS-MK', 'PROPS-EDGE', 'PROPS-CENTRE'].map(k => { const b = document.querySelector('#propsCalib .calib[data-sport="' + k + '"]'); return k + ':' + (b ? [...b.querySelectorAll(':scope > div .k')].map(e => e.textContent).join('|') : 'none'); });
    const nights = [...document.querySelectorAll('#propsNights tbody tr')].map(tr => tr.innerText.replace(/\s+/g, ' ').trim());
    const ladder = [...document.querySelectorAll('#propsLadder tbody tr')].map(tr => tr.innerText.replace(/\s+/g, ' ').trim());
    const slateMsg = document.getElementById('saveMsg').textContent;
    const bk = { format: 'callsheet3.backup', version: 1, card: [], props: [after[0]] };
    const dt2 = new DataTransfer(); dt2.items.add(new File([JSON.stringify(bk)], 'the-super-model-2026-10-22.json', { type: 'application/json' }));
    const inp2 = document.getElementById('restoreFile'); inp2.files = dt2.files; inp2.dispatchEvent(new Event('change', { bubbles: true })); await wait();
    const restored = JSON.parse(smStore.getItem('callsheet3.props.v1'));
    // older graded props get their minutes from a second load of the night's grade file, results untouched (25 Oct 2026)
    const bk3 = { format: 'callsheet3.backup', version: 1, card: [], props: after.map(r => { const c = Object.assign({}, r); delete c.amin; return c; }) };
    const dt3 = new DataTransfer(); dt3.items.add(new File([JSON.stringify(bk3)], 'the-super-model-2026-10-22.json', { type: 'application/json' }));
    inp2.files = dt3.files; inp2.dispatchEvent(new Event('change', { bubbles: true })); await wait();
    const stripped = JSON.parse(smStore.getItem('callsheet3.props.v1')).every(r => r.amin === undefined);
    await load(gradeDoc, 'nba-grade-2026-10-21.json');
    const refilled = JSON.parse(smStore.getItem('callsheet3.props.v1'));
    const refill = { stripped, same: refilled.length === after.length && refilled.every((r, i) => r.result === after[i].result && r.actual === after[i].actual),
                     mins: refilled.map(r => r.amin), was: after.map(r => r.amin), msg: document.getElementById('saveMsg').innerText.replace(/\s+/g, ' ') };
    document.getElementById('m-nba').click(); await wait();
    const viewOff = document.getElementById('propsView').hidden, colsBack = !document.querySelector('.cols').hidden, nbaPressed = document.getElementById('m-nba').getAttribute('aria-pressed');
    await smStore.removeItem('callsheet3.props.v1');
    return { viewOn, colsOff, pressed, best, rowsOn, rowsAll, count, msg, whyOpen, logMarks, tileBefore, after: after.map(r => [r.name, r.mk, r.result, r.actual]), tileText, slateMsg, restored: restored.length, viewOff, colsBack, nbaPressed,
             tabCalib, tabBlocks, nights, ladder, tabEmpty0, noneMsg, thinMsg, inPlay, thisRow, thisMark, logRows, refill, thisWhat, whatHead, otherWhat };
  });
  chk(propsT.refill.stripped && propsT.refill.same && JSON.stringify(propsT.refill.mins) === JSON.stringify(propsT.refill.was) && propsT.refill.mins.some(m => typeof m === 'number') && /Minutes filled in on \d+ graded props? from the box lines\./.test(propsT.refill.msg),
      'props: a second load of a night\'s grade file fills the minutes in on props graded before they were kept, leaves every result as it was, and says how many', JSON.stringify(propsT.refill));
  chk(/^10-21 @ [A-Z]+ this game 36\.2 28 won by 6 · 36 min \(his usual 34\) · 22 shots \(his usual 21 at those minutes\) · 10 of 19 from the floor$/.test(propsT.thisRow) && /lg over/.test(propsT.thisMark) && propsT.logRows === 4
      && propsT.whatHead === 'Date|Opp|Min|points|What happened' && propsT.thisWhat === 'won by 6 · 36 min (his usual 34) · 22 shots (his usual 21 at those minutes) · 10 of 19 from the floor' && propsT.otherWhat.length === 3 && propsT.otherWhat.every(t => t === ''),
      'props: a graded prop\'s last games end with the game itself, his minutes from the box line and the stat marked against the line', JSON.stringify({ row: propsT.thisRow, mark: propsT.thisMark, rows: propsT.logRows }));
  chk(/loaded: 2 new.*Last season's ledger, nba-ledger-202526\.json, was not read by this run: 1 of the 1 projections rest on this season's two or three games a player, and 1 prop has no history at all\. Put the file back beside slate\.py, run the props again before tip, and load the new file; it replaces these\./.test(propsT.thinMsg),
      'props: a file whose projections rest on this season alone says last season\'s ledger was not read and what to do', propsT.thinMsg.slice(0, 500));
  chk(/loaded: 1 new, 0 replaced, 0 graded and left as they were, 1 on 1 game already under way left out \(in-play lines; the calls made before tip stand\)/.test(propsT.inPlay.msg) && propsT.inPlay.names.join(',') === 'Paul George',
      'props: a file written after a game tipped leaves that game\'s props out and says so, and keeps the games still to come', JSON.stringify(propsT.inPlay));
  chk(/None of the 1 props has a projection\. The run read 0 games of 2026-27 and 0 of 2025-26 in C:\\Users\\J\\Downloads\. Last season's ledger, nba-ledger-202526\.json, was not read\. With a game or two this season nobody has the sixty minutes a projection needs, so every prop reads no history\. Put that file back in the slate folder beside slate\.py, with this season's ledger beside it, run the props again/.test(propsT.noneMsg),
      'props: a file that projects nothing says last season\'s ledger was not read, names the folder the run saw, and says what to put back', propsT.noneMsg.slice(0, 500));
  chk(/Nothing graded yet/.test(propsT.tabEmpty0) && /^Every prop with a side 1-1 says 54\.6% · does 50\.0%/i.test(propsT.tabCalib) && /BET band 1-0 says 56\.0% · does 100\.0%/i.test(propsT.tabCalib)
      && /^PROPS-TAB:Every prop with a side\|BET band\|No edge: the book's own side(\|Same-game pairs, at the parlay price)?$/.test(propsT.tabBlocks[0]) && propsT.tabBlocks[1] === 'PROPS-MK:points|rebounds|assists' && propsT.tabBlocks[2] === 'PROPS-EDGE:3 to 6 points|no edge'
      && propsT.tabBlocks[3] === 'PROPS-CENTRE:Called at the mean, to 21 Oct' && propsT.nights.length === 1 && /^Oct 21 1-1 1 void 54\.6% 50\.0% [-−]0\.1u 1-0 \+0\.9u$/.test(propsT.nights[0])
      && propsT.ladder.length === 2 && /^50 to 55% 1 53\.2% 0\.0% 50\.0 [-−]1\.0u$/.test(propsT.ladder[0]) && /^55 to 60% 1 56\.0% 100\.0% 50\.0 \+0\.9u$/.test(propsT.ladder[1]) && /Called at the median/.test(propsT.tabCalib) === false,
      'props: the tab\'s own Is it working block: the bands as tiles, by market, by the edge claimed, the centre the chance was read around, night by night and says against does by the chance claimed; empty until something grades',
      JSON.stringify({ blocks: propsT.tabBlocks, nights: propsT.nights, ladder: propsT.ladder, head: propsT.tabCalib.slice(0, 160), empty: propsT.tabEmpty0.slice(0, 60) }));
  chk(propsT.logMarks.join(',') === 'lg over|26,lg under|22,lg|?' && /Last games \(1 of 2 over 24\.5\)/i.test(propsT.whyOpen[0]) && /10-19 @ BOS 12\.5 \?/.test(propsT.whyOpen[0]),
      'props: the last games mark each stat, green over the prop\'s line and red under it, a missing one plain, and tally how many cleared the number', JSON.stringify({ marks: propsT.logMarks, why: propsT.whyOpen }));
  chk(propsT.viewOn && propsT.colsOff && propsT.pressed === 'true', 'props: loading a props file through Load slate opens the Props tab in place of the matchup columns', JSON.stringify({ on: propsT.viewOn, cols: propsT.colsOff, pressed: propsT.pressed }));
  chk(propsT.best.length === 1 && /#1 · BET/.test(propsT.best[0]) && /Trae Young OVER 24\.5 points/.test(propsT.best[0]) && /56\.0% · [-−]110 needs 52\.4% · edge \+3\.7/.test(propsT.best[0]) && /projected 27\.2 \(±9\.4\)/.test(propsT.best[0]),
      'props: the best list carries the one prop that clears its price, with its band, chance, price, need, edge and projection', JSON.stringify(propsT.best));
  chk(propsT.rowsOn === 2 && propsT.rowsAll === 3 && /3 props on .*21/.test(propsT.count) && /3.* new/.test(propsT.msg),
      'props: the table lists the projected props, every prop with the box ticked, and the count names the date', JSON.stringify({ on: propsT.rowsOn, all: propsT.rowsAll, count: propsT.count, msg: propsT.msg }));
  chk(propsT.whyOpen.length === 1 && /27\.9 points per 36/.test(propsT.whyOpen[0]) && /10-15 @ MIA 34 26/.test(propsT.whyOpen[0]) && /fanatics carded 24\.5 [-−]110 [-−]110 draftkings 25\.5 [-−]115 [-−]105/.test(propsT.whyOpen[0]) && !/what happened/i.test(propsT.whyOpen[0]),
      'props: a click on a table row opens the prop\'s panel with the reasons, the last games and every book\'s line; a file from before the what-happened column carries none and the column stays away', JSON.stringify(propsT.whyOpen));
  chk(!propsT.tileBefore, 'props: no record tile before anything is graded', '');
  chk(propsT.after[0][2] === 'win' && propsT.after[0][3] === 28 && propsT.after[2][2] === 'loss' && propsT.after[2][3] === 9 && propsT.after[1][2] === 'void',
      'props: the grade file\'s box grades each prop by its side (28 over 24.5 wins; 9 rebounds beat the under 7.5), and a player with no box line is void', JSON.stringify(propsT.after));
  chk(/Every prop with a side 1-1 says 54\.6% · does 50\.0%/i.test(propsT.tileText) && /BET 1-0 \+0\.9u/.test(propsT.tileText) && /no edge 0-1 [-−]1\.0u/.test(propsT.tileText) && /over 1-0 · under 0-1/.test(propsT.tileText) && /points 1-0/i.test(propsT.tileText) && /rebounds 0-1/i.test(propsT.tileText) && /assists 0-0 pushes only · 1 void/i.test(propsT.tileText),
      'props: the record tile keeps the props by band, side and market, the void counted apart', propsT.tileText.slice(0, 500));
  chk(/3 props graded on the Props tab/.test(propsT.slateMsg), 'props: the slate message says how many props the grade file graded', propsT.slateMsg.slice(-160));
  chk(propsT.restored === 1 && propsT.viewOff && propsT.colsBack && propsT.nbaPressed === 'true', 'props: a backup\'s props restore, and a sport button brings the matchup columns back', JSON.stringify({ restored: propsT.restored, off: propsT.viewOff, cols: propsT.colsBack, nba: propsT.nbaPressed }));
  // the Example button: one game's props computed at build time through the slate's projection, previewed and never saved
  const propsEx = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 80));
    await smStore.removeItem('callsheet3.props.v1');
    document.getElementById('m-props').click(); await wait();
    const before = document.getElementById('propsCount').textContent, tileBefore = !!document.querySelector('#calibBox .calib[data-sport="PROPS"]');
    document.getElementById('propsAll').checked = false; document.getElementById('propsAll').dispatchEvent(new Event('change', { bubbles: true })); await wait();
    document.getElementById('propsExample').click(); await wait();
    const on = !document.getElementById('propsView').hidden, count = document.getElementById('propsCount').textContent, msg = document.getElementById('propsMsg').textContent;
    const best = [...document.querySelectorAll('#propsBest .pk')].map(e => e.innerText.replace(/\s+/g, ' ').trim());
    const rows = document.querySelectorAll('#propsTable tr[data-prop]').length;
    document.getElementById('propsAll').checked = true; document.getElementById('propsAll').dispatchEvent(new Event('change', { bubbles: true })); await wait();
    const rowsAll = document.querySelectorAll('#propsTable tr[data-prop]').length;
    const whys = [];
    for (const tr of [...document.querySelectorAll('#propsTable tr[data-prop]')]) {
      tr.click(); await wait();
      whys.push(document.getElementById('propDetailBody').innerText.replace(/\s+/g, ' ').trim());
      document.getElementById('propDetailClose').click(); await wait();
    }
    // the table's view: a market filter, a column sort, a band filter and a name, then Reset
    const cells = (i) => [...document.querySelectorAll('#propsTable tbody tr[data-prop]')].map(tr => tr.querySelectorAll('td')[i].textContent.trim());
    const sel = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event(id === 'propsQ' ? 'input' : 'change', { bubbles: true })); };
    sel('propsMk', 'reb'); await wait();
    const view1 = { markets: cells(2), shown: document.getElementById('propsShown').textContent };
    sel('propsMk', ''); document.querySelector('#propsTable th[data-sort="chance"]').click(); await wait();
    const view2 = { chances: cells(5), head: document.querySelector('#propsTable th[data-sort="chance"]').textContent, shown: document.getElementById('propsShown').textContent, order: JSON.parse(localStorage.getItem('callsheet3.props.view.v1') || '{}') };
    document.querySelector('#propsTable th[data-sort="chance"]').click(); await wait();
    const view3 = { chances: cells(5) };
    sel('propsBand', 'LEAN'); sel('propsQ', 'maxey'); await wait();
    const view4 = { names: cells(1), bands: cells(10), shown: document.getElementById('propsShown').textContent };
    document.getElementById('propsReset').click(); await wait();
    const view5 = { rows: document.querySelectorAll('#propsTable tbody tr[data-prop]').length, shown: document.getElementById('propsShown').textContent, stored: localStorage.getItem('callsheet3.props.view.v1'), mk: document.getElementById('propsMk').value, q: document.getElementById('propsQ').value };
    const saved = smStore.getItem('callsheet3.props.v1');
    const tileAfter = !!document.querySelector('#calibBox .calib[data-sport="PROPS"]');
    document.getElementById('m-nba').click(); await wait();
    document.getElementById('m-props').click(); await wait();
    const after = document.getElementById('propsCount').textContent;
    document.getElementById('m-nba').click(); await wait();
    return { on, count, msg, best, rows, rowsAll, whys, saved, tileSame: tileBefore === tileAfter, before, after, view1, view2, view3, view4, view5 };
  });
  const pct = (s) => parseFloat(String(s).replace('%', ''));
  chk(propsEx.view1.markets.length >= 1 && propsEx.view1.markets.every(m => m === 'rebounds') && /of 8 shown$/.test(propsEx.view1.shown)
      && propsEx.view2.chances.length === 8 && propsEx.view2.chances.slice(0, 7).every((c, i) => isNaN(pct(c)) ? false : pct(c) >= (isNaN(pct(propsEx.view2.chances[i + 1])) ? -1 : pct(propsEx.view2.chances[i + 1]))) && /Chance ▾/.test(propsEx.view2.head) && /sorted by chance ▾/.test(propsEx.view2.shown) && propsEx.view2.order.sort === 'chance'
      && propsEx.view3.chances.filter(c => !isNaN(pct(c))).every((c, i, a) => i === 0 || pct(c) >= pct(a[i - 1]))
      && propsEx.view4.names.every(n => /Maxey/.test(n)) && propsEx.view4.bands.every(b => b === 'LEAN') && propsEx.view4.names.length >= 1
      && propsEx.view5.rows === 8 && propsEx.view5.shown === '8 shown' && propsEx.view5.stored === null && propsEx.view5.mk === '' && propsEx.view5.q === '',
      'props table: the market filter keeps the rebounds, a click on Chance sorts it high to low and again low to high, the band and name filters narrow it, and Reset view puts it back', JSON.stringify({ v1: propsEx.view1, v2: { head: propsEx.view2.head, shown: propsEx.view2.shown, chances: propsEx.view2.chances }, v3: propsEx.view3, v4: propsEx.view4, v5: propsEx.view5 }));
  chk(propsEx.on && /^EXAMPLE · 8 props on/.test(propsEx.count) && /An example/.test(propsEx.msg) && propsEx.rows === 7 && propsEx.rowsAll === 8,
      'props example: eight props on 76ers @ Knicks, seven projected (Embiid is out), the count says EXAMPLE', JSON.stringify({ count: propsEx.count, rows: propsEx.rows, all: propsEx.rowsAll }));
  chk(propsEx.best.length >= 2 && /#1 · (BET|LEAN)/.test(propsEx.best[0]) && propsEx.best.some(b => /Tyrese Maxey OVER 25\.5 points/.test(b)),
      'props example: the best list ranks the props by edge, Maxey over with Embiid out among them', JSON.stringify(propsEx.best.slice(0, 3)));
  chk(propsEx.whys.some(w => /Joel Embiid out \(31 minutes a game between them\): \+1\.5 minutes and \+0\.58 points per 36, the pooled rule, scored/.test(w)) && propsEx.whys.some(w => /listed Out on ESPN: no projection/.test(w))
      && propsEx.whys.some(w => /Knicks allow 0\.97x the league's points per minute to guards \(this season 0\.95 over 16 games, last season 0\.99\): x0\.978 at 0\.75 weight, measured/.test(w)) && propsEx.whys.some(w => /HashtagBasketball: 76ers allow/.test(w)),
      'props example: the why lines are the slate\'s own, the regulars-out rule, the defence factor, the website\'s rank and the listed-out man', JSON.stringify(propsEx.whys.slice(0, 2)).slice(0, 600));
  chk(propsEx.saved === null && propsEx.tileSame && propsEx.after === propsEx.before, 'props example: nothing is saved or graded, and a sport button puts it away', JSON.stringify({ saved: propsEx.saved, same: propsEx.tileSame, before: propsEx.before, after: propsEx.after }));

  // ---- the prop's own panel (21 Oct 2026): a best-prop card opens it, a table row still folds its why, Escape or Close puts it away
  const propsDlg = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 60));
    document.getElementById('m-props').click(); await wait();
    document.getElementById('propsExample').click(); await wait();
    const dlg = document.getElementById('propDetail'), hidden0 = dlg.hidden;
    const card = [...document.querySelectorAll('#propsBest .pk')].find(e => /Tyrese Maxey/.test(e.textContent)), id = card.getAttribute('data-prop');
    card.click(); await wait();
    const open = !dlg.hidden, text = document.getElementById('propDetailBody').innerText.replace(/\s+/g, ' ').trim();
    const tiles = [...dlg.querySelectorAll('.pd-tiles .pd-tile .k')].map(e => e.textContent);
    // the simulation on the prop (26 Oct 2026): six tiles of its own under What moves it, and the paragraph that says what was scored
    const simTiles = [...dlg.querySelectorAll('.pd-simtiles .pd-tile')].map(e => e.querySelector('.k').textContent + '=' + e.querySelector('.v').textContent + '|' + ((e.querySelector('.s') || {}).textContent || '') + '|' + e.className);
    const simText = ((dlg.querySelector('.pd-sim') || {}).innerText || '').replace(/\s+/g, ' ').trim(), simBeforeWhy = (() => { const s = dlg.querySelector('.pd-sim'); let n = s && s.nextElementSibling; return !!(n && /^H4$/i.test(n.tagName) && /^Why/.test(n.textContent)); })();
    const marks = dlg.querySelectorAll('.pd-log b.lg').length, books = dlg.querySelectorAll('.pd-books tbody tr').length, carded = (dlg.querySelector('.pd-books tr.carded td') || {}).textContent || '';
    const fromCardPos = document.getElementById('propDetailPos').textContent, noscroll = document.body.classList.contains('noscroll');
    const levers = [...dlg.querySelectorAll('.pd-levers .lever')].map(e => e.className + '|' + e.querySelector('.lt').textContent.trim() + '|' + e.querySelector('.lv').textContent);
    const base = (dlg.querySelector('.pd-base') || {}).textContent || '', boldWhy = [...dlg.querySelectorAll('ul.pd-why li.lever-line')].map(e => e.textContent.slice(0, 40));
    const againstWhy = [...dlg.querySelectorAll('ul.pd-why li.lever-against')].map(e => e.textContent.replace(/\s+/g, ' ').trim()), whyHead = ((dlg.querySelector('h4 + ul.pd-why') || {}).previousElementSibling || {}).textContent || '';
    const boldTags = [...dlg.querySelectorAll('ul.pd-why li.lever-line')].map(e => e.textContent.slice(0, 12) + '→' + ((e.querySelector('.tag.helps') || {}).textContent || '') + '|' + getComputedStyle(e).color + '|' + getComputedStyle(e).fontWeight);
    const cardLever = (card.querySelector('.n5') || {}).textContent || '';
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })); await wait();
    const closedEsc = dlg.hidden && !document.body.classList.contains('noscroll');
    card.click(); await wait(); document.getElementById('propDetailClose').click(); await wait();
    const closedBtn = dlg.hidden;
    card.click(); await wait(); document.getElementById('m-nba').click(); await wait();
    const closedSport = dlg.hidden;
    // a row of the Every-prop table opens the same panel, and Previous / Next and the arrow keys walk the table's order
    document.getElementById('m-props').click(); await wait();
    document.getElementById('propsExample').click(); await wait();   // the sport button put the example away
    const trs =[...document.querySelectorAll('#propsTable tr[data-prop]')], rowNames = trs.slice(0, 3).map(t => t.querySelectorAll('td')[1].textContent.trim());
    const h3 = () => ((document.querySelector('#propDetailBody h3') || {}).textContent || '').trim();
    trs[0].click(); await wait();
    const rowOpen = !dlg.hidden, name0 = h3(), pos0 = document.getElementById('propDetailPos').textContent, prevOff0 = document.getElementById('propDetailPrev').disabled, navShown = !document.getElementById('propDetailNav').hidden;
    document.getElementById('propDetailNext').click(); await wait();
    const name1 = h3(), pos1 = document.getElementById('propDetailPos').textContent, prevOff1 = document.getElementById('propDetailPrev').disabled;
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true })); await wait();
    const name2 = h3();
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft', bubbles: true })); await wait();
    const name1b = h3();
    trs[trs.length - 1].click(); await wait();
    const nextOffLast = document.getElementById('propDetailNext').disabled, posLast = document.getElementById('propDetailPos').textContent;
    document.getElementById('propDetailClose').click(); await wait(); document.getElementById('m-nba').click(); await wait();
    return { hidden0, open, text: text.slice(0, 3200), tiles, simTiles, simText, simBeforeWhy, marks, books, carded, fromCardPos, noscroll, closedEsc, closedBtn, closedSport, levers, base, boldWhy, againstWhy, whyHead, boldTags, cardLever,
             n: trs.length, rowNames, rowOpen, name0, pos0, prevOff0, navShown, name1, pos1, prevOff1, name2, name1b, nextOffLast, posLast };
  });
  chk(propsDlg.simTiles.length === 6 && /^PHI points=1[01]\d\|middle half \d+–\d+ · 112\.9 a game by the ratings\|/.test(propsDlg.simTiles[0]) && /^Sim's read=2\d\.\d\|his per 36 at his minutes × 0\.\d\d; [-−+]\d\.\d against the model's 28\.07\|/.test(propsDlg.simTiles[1])
      && /^Matchup lever=[-−]0\.8\|the scored part, at half weight, against the OVER\|pd-tile bad$/.test(propsDlg.simTiles[2]) && /^Blowout=\d+%\|15 or more either way; shown, not scored\|/.test(propsDlg.simTiles[3])
      && /^Overtime=\d\.\d%\|/.test(propsDlg.simTiles[4]) && /^Possessions=9\d\.\d\|the game's pace in the runs\|/.test(propsDlg.simTiles[5])
      && /^SIMULATION · 76ers @ Knicks played 3,000 times /.test(propsDlg.simText) && /What the score takes from the simulation is the matchup lever, [-−]0\.8 here, at half weight/.test(propsDlg.simText)
      && /The blowout chance \(\d+%\) and overtime \(\d\.\d%\) are shown, not scored/.test(propsDlg.simText) && propsDlg.simBeforeWhy,
      'props detail: the Simulation section carries the game\'s runs on the prop: his club\'s points with the middle half against the ratings\' number, the sim\'s full-weight read against the projection, the matchup lever as the scored part in colour, the blowout, overtime and the possessions, shown not scored, before the why',
      JSON.stringify({ tiles: propsDlg.simTiles, text: propsDlg.simText.slice(0, 700), beforeWhy: propsDlg.simBeforeWhy }));
  chk(propsDlg.rowOpen && propsDlg.navShown && propsDlg.name0.indexOf(propsDlg.rowNames[0]) === 0 && propsDlg.pos0 === '1 of ' + propsDlg.n && propsDlg.prevOff0
      && propsDlg.name1.indexOf(propsDlg.rowNames[1]) === 0 && propsDlg.pos1 === '2 of ' + propsDlg.n && !propsDlg.prevOff1 && propsDlg.name2.indexOf(propsDlg.rowNames[2]) === 0 && propsDlg.name1b === propsDlg.name1
      && propsDlg.nextOffLast && propsDlg.posLast === propsDlg.n + ' of ' + propsDlg.n && /^\d+ of \d+$/.test(propsDlg.fromCardPos),
      'props detail: a row of the Every-prop table opens the same panel, Next and the arrow keys walk the table\'s order with the position shown, Previous is off on the first and Next on the last, and a card opened from the best list knows its place too',
      JSON.stringify({ n: propsDlg.n, rows: propsDlg.rowNames, name0: propsDlg.name0, pos0: propsDlg.pos0, name1: propsDlg.name1, pos1: propsDlg.pos1, name2: propsDlg.name2, back: propsDlg.name1b, last: propsDlg.posLast, card: propsDlg.fromCardPos }));
  chk(propsDlg.levers.length === 6 && /^lever helps top\|Regulars out biggest lever\|\+1\.[5-9]$/.test(propsDlg.levers[0]) && propsDlg.levers.some(l => /^lever hurts\|Defence v position\|[-−]0\./.test(l)) && propsDlg.levers.some(l => /^lever hurts\|Pace\|[-−]0\./.test(l))
      && propsDlg.levers.some(l => /^lever hurts\|The matchup, from the simulation\|[-−]0\.[5-9]$/.test(l))
      && /^Starts from 28\.\d+, his 28\.\d+ per 36 at his minutes; the regulars out, pace, the matchup and the defence take it to 28\.07, \+2\.6 against the line\./.test(propsDlg.base)
      && propsDlg.boldWhy.length === 2 && propsDlg.boldWhy.some(w => /^Joel Embiid out/.test(w)) && propsDlg.boldWhy.some(w => /^27\.7 points per 36 this season/.test(w)) && !propsDlg.boldWhy.some(w => /^the matchup|^the game's pace/.test(w))
      && propsDlg.againstWhy.length === 1 && /^(the matchup, from the simulation's profiles|the game's pace)/.test(propsDlg.againstWhy[0]) && /the biggest against the OVER$/.test(propsDlg.againstWhy[0])
      && /the biggest reasons for the OVER in green, the biggest against it in red/.test(propsDlg.whyHead)
      && propsDlg.boldTags.length === 2 && propsDlg.boldTags.some(t => /^Joel Embiid →the biggest for the OVER\|/.test(t)) && propsDlg.boldTags.some(t => /^27\.7 points →the second biggest for the OVER\|/.test(t))
      && propsDlg.boldTags.every(t => /\|rgb\(\d+, \d+, \d+\)\|600$/.test(t)) && new Set(propsDlg.boldTags.map(t => t.split('|')[1])).size === 1 && propsDlg.boldTags[0].split('|')[1] !== 'rgb(0, 0, 0)'
      && /^Moves it: Regulars out \+1\.[5-9] · The matchup, from the simulation [-−]0\.[5-9]$/.test(propsDlg.cardLever),
      'props detail: what moves it ranks each factor\'s push on the projection with a bar, the regulars out the biggest lever on Maxey with Embiid out, the matchup from the simulation, the pace and the defence against; the two biggest toward the OVER (Embiid out, the prior) bold their why lines in green with a tag each, the biggest against it (the matchup) is tagged in red, and the card names the top two by size', JSON.stringify({ levers: propsDlg.levers, base: propsDlg.base, bold: propsDlg.boldWhy, tags: propsDlg.boldTags, against: propsDlg.againstWhy, head: propsDlg.whyHead, card: propsDlg.cardLever }));
  chk(propsDlg.hidden0 && propsDlg.open && propsDlg.noscroll && /^LEAN Tyrese Maxey G PHI( starter)? OVER 25\.5 points 76ers @ Knicks/.test(propsDlg.text) && /on the road at NYK/.test(propsDlg.text) && /Why /i.test(propsDlg.text)
      && propsDlg.tiles.join(',') === 'Chance,Price,Edge,Projection,Minutes,Per 36,Usage' && propsDlg.marks === 10 && propsDlg.books === 3 && /fanatics/.test(propsDlg.carded),
      'props detail: a best-prop card opens the prop on its own panel with the tiles, the why, the marked last games and every book', JSON.stringify(propsDlg).slice(0, 1500));
  chk(propsDlg.closedEsc && propsDlg.closedBtn && propsDlg.closedSport, 'props detail: Escape, the Close button and a sport button each put the panel away', JSON.stringify({ esc: propsDlg.closedEsc, btn: propsDlg.closedBtn, sport: propsDlg.closedSport }));

  // ---- 19 Oct 2026: the alternate total with a verdict -- a market of its own on the rail, the board and the record;
  //      and the parlay four takes the likeliest side on each game, the alternate included ----
  const altT = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 80));
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    await smStore.removeItem('callsheet3.card.v1');
    document.getElementById('clear').click(); document.getElementById('m-nhl').click(); await wait();
    set('gdate', '2026-11-09'); document.getElementById('example').click(); await wait();
    set('gdate', '2026-11-09');
    // the odds file's shop: the main 6 at -110/-110 and the alternates. The example projects 6.04, so the sheet's side is the
    // under; the under 7 at -150 (needs 60.0%, the sheet 70.9%) reads MAX BET with an edge, the under 6.5 at -120 STRONG BET
    // with less, the under 5.5 at +150 no band: the best edge with a verdict is the leg
    set('odds', JSON.stringify({ total: { OVER: [['fanatics', -110, 6]], UNDER: [['fanatics', -110, 6]] },
                                 alt: { OVER: [['fanatics', 115, 7], ['fanatics', -105, 6.5], ['fanatics', -180, 5.5]], UNDER: [['fanatics', -150, 7], ['fanatics', -120, 6.5], ['fanatics', 150, 5.5]] },
                                 book: 'fanatics' })); await wait();
    const side = (document.querySelector('#markets .mk[data-key="total"] .pick') || {}).childNodes;
    const totalSide = side && side.length ? side[0].textContent.trim() : '';
    const altRow = document.querySelector('#markets .mk[data-key="alt"]');
    const alt = altRow ? { pick: altRow.querySelector('.pick').childNodes[0].textContent.trim(), band: (altRow.querySelector('.band') || {}).textContent || '', p: parseFloat(altRow.querySelector('.p').textContent),
                           chips: [...altRow.querySelectorAll('.cap')].map(c => c.textContent), edge: altRow.querySelector('.e').textContent,
                           detail: (altRow.nextElementSibling && altRow.nextElementSibling.classList.contains('mkdetail')) ? altRow.nextElementSibling.textContent : '' } : null;
    const altCard = (document.querySelector('#markets .altcard') || {}).textContent || '';
    const pickKey = (document.querySelector('#markets .pickcard') || {}).getAttribute ? document.querySelector('#markets .pickcard').getAttribute('data-key') : '';
    document.getElementById('add').click(); await wait();
    document.getElementById('boardDate').value = '2026-11-09'; document.getElementById('boardDate').dispatchEvent(new Event('change')); await wait();
    const stored = JSON.parse(smStore.getItem('callsheet3.card.v1'))[0];
    const altMk = stored.markets.find(m => m.key === 'alt');
    const board = [...document.querySelectorAll('#altBets .pk')].map(e => e.innerText.replace(/\s+/g, ' ').trim());
    const headHidden = document.getElementById('altBetsHead').hidden;
    const legs = [...document.querySelectorAll('#picks .pk:not(.parlay)')].map(e => ({ pick: e.querySelector('.n2').childNodes[0].textContent.trim(), n1: e.querySelector('.n1').textContent, swaps: [...e.querySelectorAll('.swap')].map(s => s.textContent) }));
    const parlay = (document.querySelector('#picks .pk.parlay') || {}).textContent || '';
    const tableAlt = [...document.querySelectorAll('#board tbody tr')].map(tr => tr.querySelectorAll('td')[2].textContent).filter(t => /Alternate/.test(t));
    // grade: a 3-2 game -- the under 7 wins
    const tr = () => [...document.querySelectorAll('#cardTable tr')].find(t => /Rangers @ Bruins/.test(t.textContent));
    const g = (k, v) => { const el = tr().querySelector(`.grade[data-k="${k}"]`); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); };
    g('fa', '2'); g('fh', '3'); await wait();
    const after = JSON.parse(smStore.getItem('callsheet3.card.v1'))[0];
    const tile = [...document.querySelectorAll('#calibBox .calib[data-sport="NHL"] > div')].map(d => d.innerText.replace(/\s+/g, ' ').trim()).find(t => /Alternate totals/i.test(t)) || '';
    const boardAfter = [...document.querySelectorAll('#altBets .pk')].map(e => e.innerText.replace(/\s+/g, ' ').trim());
    const text = (() => { return ''; })();
    await smStore.removeItem('callsheet3.card.v1');
    document.getElementById('clear').click(); await wait();
    return { totalSide, alt, altCard, pickKey, altMk: altMk ? { pick: altMk.pick, band: altMk.band, point: altMk.point, book: altMk.book, price: altMk.price } : null, board, headHidden, legs, parlay, tableAlt, tile, boardAfter, keys: stored.markets.map(m => m.key) };
  });
  chk(altT.totalSide === 'UNDER 6' && altT.alt && altT.alt.pick === 'UNDER 7' && altT.alt.band === 'MAX BET' && altT.alt.p > 70 && /edge \+1[01]\./.test(altT.alt.edge) && altT.alt.chips.some(c => /shown, not picked/.test(c)),
      'alternates: the under 7 at -150 lists as its own market with the MAX BET band and a ten-point edge, shown not picked; the under 6.5 with the smaller edge and the bandless under 5.5 do not', JSON.stringify(altT.alt));
  chk(/An alternate number at Fanatics, priced by the same projection of 6\.04 split at 7: UNDER 7 70\.9% against [-−]150, which needs 60\.0%/.test(altT.alt ? altT.alt.detail : '') && /The band is the chance, as on the main number/.test(altT.alt ? altT.alt.detail : ''),
      'alternates: the row\'s note names the book, the projection, the number and the reading of the band', (altT.alt ? altT.alt.detail : '').slice(0, 260));
  chk(/Alternate total · MAX BET · not the pick/.test(altT.altCard) && /UNDER 7/.test(altT.altCard) && /[-−]150 at Fanatics needs 60\.0%: edge \+1[01]\./.test(altT.altCard) && altT.pickKey === 'total',
      'alternates: a card under the pick carries the band, the price and what it needs, and the pick stays on the main number', altT.altCard.slice(0, 200) + ' | pick ' + altT.pickKey);
  chk(altT.altMk && altT.altMk.point === 7 && altT.altMk.book === 'fanatics' && altT.altMk.price === -150 && altT.altMk.band === 'MAX BET' && altT.keys.indexOf('alt') >= 0,
      'alternates: the row stores the alternate as a market with its number, book and band', JSON.stringify(altT.altMk) + ' ' + altT.keys.join(','));
  chk(!altT.headHidden && altT.board.length === 1 && /#1 · MAX BET · the price agrees/.test(altT.board[0]) && /UNDER 7/.test(altT.board[0]) && /Rangers @ Bruins · Alternate total 7 at Fanatics/.test(altT.board[0]) && altT.tableAlt.length === 1,
      'alternates: the board section shows the alternate with its band, and the table lists it', JSON.stringify(altT.board) + ' ' + JSON.stringify(altT.tableAlt));
  chk(altT.legs.length === 1 && altT.legs[0].pick === 'UNDER 7' && altT.legs[0].swaps.some(s => /The likeliest side on this game, an alternate number\. [-−]150 needs 60\.0%: the price agrees\. Call Sheet #1 says MAX BET\./.test(s)) && altT.legs[0].swaps.some(s => /The value on this game was UNDER 6 /.test(s)),
      'the parlay four: the alternate under 7 is the likeliest side on the game and becomes its leg, the card saying so and naming the value side', JSON.stringify(altT.legs));
  chk(altT.boardAfter.length === 1 && /\bwin\b/i.test(altT.boardAfter[0]), 'alternates: a 3-2 final grades the under 7 a win on the board card', JSON.stringify({ board: altT.boardAfter }));
  chk(/Alternate totals 1-0/i.test(altT.tile), 'alternates: the record keeps its own tile', altT.tile.slice(0, 160));

  // ---- an NBA row re-scored while another game sits in the form keeps its own clubs' names (21 Oct 2026) ----
  const relabel = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 60));
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    await smStore.removeItem('callsheet3.card.v1');
    document.getElementById('clear').click(); document.getElementById('m-nba').click(); await wait();
    set('gdate', '2026-10-20'); set('away', 'Celtics'); set('home', 'Pistons'); set('line', '213'); set('op', '-215'); set('up', '170');
    set('sp', '1.5'); set('sph', '-110'); set('spa', '-110'); set('hml', '100'); set('aml', '-120'); await wait();
    document.getElementById('add').click(); await wait();
    // a hockey game in the form while a slate merges into the basketball row on the card
    document.getElementById('clear').click(); document.getElementById('m-nhl').click(); await wait();
    set('gdate', '2026-10-20'); set('away', 'Ducks'); set('home', 'Islanders'); set('line', '6'); set('op', '-110'); set('up', '-110'); await wait();
    const doc = { format: 'callsheet2.slate', version: 1, date: '2026-10-20', games: [{ sport: 'NBA', gdate: '2026-10-20', away: 'Celtics', home: 'Pistons', inputs: { narest: '1', nhrest: '2' }, notes: [] }] };
    const dt = new DataTransfer(); dt.items.add(new File([JSON.stringify(doc)], 'nba-slate-2026-10-20.json', { type: 'application/json' }));
    const inp = document.getElementById('slateFile'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true })); await wait();
    const row = JSON.parse(smStore.getItem('callsheet3.card.v1')).find(r => /Celtics @ Pistons/.test(r.matchup));
    const sides = row.markets.filter(m => m.key === 'ml' || m.key === 'spread').map(m => ({ key: m.key, side: m.side, pick: m.pick, other: (m.other || {}).pick, label: m.label }));
    // a later slate refreshes the starting five on the carded row but leaves a filled box (the rest days) as logged
    const loadDoc = async (games, fname) => { const dt2 = new DataTransfer(); dt2.items.add(new File([JSON.stringify({ format: 'callsheet2.slate', version: 1, date: '2026-10-20', games })], fname, { type: 'application/json' })); inp.files = dt2.files; inp.dispatchEvent(new Event('change', { bubbles: true })); await wait(); };
    // the injury report and the simulation follow too (26 Oct 2026, the user: "will the simulation update when I re-run closer to start?")
    const lineupDoc = (status, rest) => [{ sport: 'NBA', gdate: '2026-10-20', away: 'Celtics', home: 'Pistons', notes: [], inputs: { narest: rest, nbalineup: JSON.stringify({ away: { status, five: [['PG', 'Derrick White']], maybe: [] }, home: null, src: 'RotoWire' }),
      nbaout: JSON.stringify({ away: [{ n: 'Jayson Tatum', st: status === 'expected' ? 'Questionable' : 'Out' }], home: [] }), nbasim: JSON.stringify({ v: 1, runs: status === 'expected' ? 100 : 200 }) } }];
    await loadDoc(lineupDoc('expected', '2'), 'nba-slate-a.json');
    const lu1 = JSON.parse(smStore.getItem('callsheet3.card.v1')).find(r => /Celtics @ Pistons/.test(r.matchup)).inputs;
    await loadDoc(lineupDoc('confirmed', '9'), 'nba-slate-b.json');
    const lu2 = JSON.parse(smStore.getItem('callsheet3.card.v1')).find(r => /Celtics @ Pistons/.test(r.matchup)).inputs;
    const refresh = { lu1: /expected/.test(lu1.nbalineup || ''), rest1: lu1.narest, lu2: /confirmed/.test(lu2.nbalineup || ''), rest2: lu2.narest,
                      out1: /Questionable/.test(lu1.nbaout || ''), out2: /"Out"/.test(lu2.nbaout || ''), sim1: /"runs":100/.test(lu1.nbasim || ''), sim2: /"runs":200/.test(lu2.nbasim || '') };
    // a row the old page wrote: the hockey names on the moneyline and the spread, to be relabelled on load
    const broken = JSON.parse(smStore.getItem('callsheet3.card.v1'));
    broken.forEach(r => r.markets.forEach(m => { if (m.key === 'ml') { m.pick = 'Islanders ML'; m.other.pick = 'Ducks ML'; } if (m.key === 'spread') { m.pick = 'Islanders +1.5'; m.label = 'Spread Islanders: +1.5'; m.other.pick = 'Ducks -1.5'; } }));
    await smStore.setItem('callsheet3.card.v1', JSON.stringify(broken));
    return { merged: row.inputs.narest === '1' && row.inputs.nhrest === '2', sides, formAway: document.getElementById('away').value, refresh };
  });
  chk(relabel.refresh.lu1 && relabel.refresh.rest1 === '1' && relabel.refresh.lu2 && relabel.refresh.rest2 === '1' && relabel.refresh.out1 && relabel.refresh.out2 && relabel.refresh.sim1 && relabel.refresh.sim2,
      'slate reload: a later slate replaces the starting five, the injury report and the simulation on a carded row (expected to confirmed, questionable to out, the newer runs) and leaves the filled boxes as logged', JSON.stringify(relabel.refresh));
  await pg.reload(); await pg.waitForTimeout(300); await pg.evaluate(() => smStore.ready);
  const relabelled = await pg.evaluate(async () => {
    const row = JSON.parse(smStore.getItem('callsheet3.card.v1')).find(r => /Celtics @ Pistons/.test(r.matchup));
    const out = row.markets.filter(m => m.key === 'ml' || m.key === 'spread').map(m => ({ key: m.key, side: m.side, pick: m.pick, other: (m.other || {}).pick, label: m.label }));
    await smStore.removeItem('callsheet3.card.v1');
    return out;
  });
  const ownClubs = (s) => s.length === 2 && s.every(m => (m.side === 'HOME' ? /^Pistons /.test(m.pick) && /^Celtics /.test(m.other) : /^Celtics /.test(m.pick) && /^Pistons /.test(m.other)))
    && s.find(m => m.key === 'spread').label === 'Spread Pistons: +1.5' && /^(Pistons \+1\.5|Celtics -1\.5)$/.test(s.find(m => m.key === 'spread').pick) && /^(Pistons|Celtics) ML$/.test(s.find(m => m.key === 'ml').pick);
  chk(relabel.merged && relabel.formAway === 'Ducks' && ownClubs(relabel.sides),
      'nba: a card row re-scored by a slate while a hockey game sits in the form keeps its own clubs on the moneyline and the spread', JSON.stringify(relabel));
  chk(ownClubs(relabelled), 'nba: a row the old page mislabelled with the form\'s clubs is relabelled by side from its own clubs on load', JSON.stringify(relabelled));

  // ---- the referees as a watch (22 Oct 2026): graded totals against the close by the crew's lean in the frozen table ----
  const refsW = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 60));
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    await smStore.removeItem('callsheet3.card.v1');
    document.getElementById('clear').click(); document.getElementById('m-nba').click(); await wait();
    const empty = (document.querySelector('#calibBox .calib[data-sport="REFS"]') || {}).innerText || '';
    // the NBA example: Foster, Brothers and Davis, a crew leaning over (z 2.4 + 0.2 + 1.8); the game lands 238 against a 231.5 close
    document.getElementById('gdate').value = '2026-11-10'; document.getElementById('example').click(); await wait();
    document.getElementById('add').click(); await wait();
    // a second row with Zarba alone, no lean (58-60): lands 205 against a 220 close
    document.getElementById('clear').click(); document.getElementById('m-nba').click(); await wait();
    set('gdate', '2026-11-10'); set('away', 'Raptors'); set('home', 'Celtics'); set('line', '221.5'); set('op', '-110'); set('up', '-110');
    set('ncrew', 'Zach Zarba'); set('nbarefs', JSON.stringify({ lg: [2462, 44.0, 228.8], r: { 'Zach Zarba': [110, 42.9, 227.4, 58, 60, 2, 5] } })); await wait();
    document.getElementById('add').click(); await wait();
    const rowOf = (re) => [...document.querySelectorAll('#cardTable tr')].find(t => re.test(t.textContent));
    const g = (tr, k, v) => { const el = tr.querySelector(`.grade[data-k="${k}"]`); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); };
    g(rowOf(/76ers @ Knicks/), 'fa', '118'); g(rowOf(/76ers @ Knicks/), 'fh', '120'); g(rowOf(/76ers @ Knicks/), 'ctot', '231.5'); await wait();
    const rowsOf = (id) => [...document.querySelectorAll('#' + id + ' tbody tr')].map(tr => [...tr.querySelectorAll('td')].map(td => td.className + ':' + td.textContent.trim()).join('|'));
    const afterOne = rowsOf('refsLean'), refsOne = rowsOf('refsRefs').concat(rowsOf('refsEven'));
    g(rowOf(/Raptors @ Celtics/), 'fa', '100'); g(rowOf(/Raptors @ Celtics/), 'fh', '105'); g(rowOf(/Raptors @ Celtics/), 'ctot', '220'); await wait();
    const leanRows = rowsOf('refsLean'), refRows = rowsOf('refsRefs').concat(rowsOf('refsEven')), evenFolded = !!document.querySelector('#calibBox details.refsfold #refsEven');
    const verdict = (document.querySelector('#refsLean ~ .verdict') || {}).textContent || '';
    await smStore.removeItem('callsheet3.card.v1'); document.getElementById('clear').click(); await wait();
    return { empty: empty.replace(/\s+/g, ' ').slice(0, 120), afterOne, refsOne, leanRows, refRows, evenFolded, verdict: verdict.slice(0, 200) };
  });
  chk(refsW.empty === '' && refsW.afterOne.length === 3 && /^:OVER LEAN\|:1\|:1-0\|:56\.9%\|over:100\.0%\|dim:50\.0\|over:\+6\.5\|pos:\+0\.91u$/.test(refsW.afterOne[0]) && /^:EVEN\|:0\|dim:nothing graded/.test(refsW.afterOne[1])
      && refsW.refsOne.length === 3 && /^:Scott Foster\|:OVER LEAN\|:66-41 z \+2\.4\|:1-0\|over:100\.0%\|over:\+6\.5$/.test(refsW.refsOne[0]) && /^:Marc Davis\|:OVER LEAN\|:71-51 z \+1\.8\|:1-0\|/.test(refsW.refsOne[1]) && /^:Tony Brothers\|:EVEN\|:56-54 z \+0\.2\|:1-0\|/.test(refsW.refsOne[2]),
      'refs watch: one table by the crew\'s lean and one by official, in colour; the example\'s crew leans over and its 238 against 231.5 counts as an over, Foster and Davis the leaning officials, Brothers even', JSON.stringify({ empty: refsW.empty, lean: refsW.afterOne, refs: refsW.refsOne }));
  chk(/^:EVEN\|:1\|:0-1\|:49\.2%\|under:0\.0%\|dim:50\.0\|under:[-−]15\.0\|dim:no side$/.test(refsW.leanRows[1]) && /^:UNDER LEAN\|:0\|dim:nothing graded/.test(refsW.leanRows[2])
      && refsW.refRows.length === 4 && /^:Zach Zarba\|:EVEN\|:58-60 z [-−]0\.2\|:0-1\|under:0\.0%\|under:[-−]15\.0$/.test(refsW.refRows[3]) && refsW.evenFolded && /An official 1\.5 sigma or more/.test(refsW.verdict),
      'refs watch: Zarba alone has no lean, so his 205 against 220 lands on the even line with no side taken, and he joins the folded no-lean officials last', JSON.stringify({ lean: refsW.leanRows, refs: refsW.refRows, folded: refsW.evenFolded, verdict: refsW.verdict.slice(0, 80) }));

  // ---- 26 Oct 2026: the bets you take -- a Take button on the board, the pick cards and the props; Taking tonight lists them;
  //      the mark rides through a rescore and a reload, a graded row cannot be marked, and What you took grades them ----
  const takeT = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 90));
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    await smStore.removeItem('callsheet3.card.v1'); await smStore.removeItem('callsheet3.props.v1');
    document.getElementById('clear').click(); document.getElementById('m-nhl').click(); await wait();
    set('gdate', '2026-11-12'); document.getElementById('example').click(); await wait(); set('gdate', '2026-11-12');
    document.getElementById('add').click(); await wait();
    document.getElementById('boardDate').value = '2026-11-12'; document.getElementById('boardDate').dispatchEvent(new Event('change')); await wait();
    const head0 = document.getElementById('takingHead').hidden, btns0 = document.querySelectorAll('#board tbody tr .takebtn').length, rows0 = document.querySelectorAll('#board tbody tr').length;
    const tr0 = document.querySelector('#board tbody tr'), pick0 = tr0.querySelectorAll('td')[3].querySelector('.chip').textContent.trim();
    set('line', '5.5'); await wait();   // the form now differs from the row: a row click would put the row's 6 back
    tr0.querySelector('.takebtn').click(); await wait();
    const lineAfter = document.getElementById('line').value;
    const mine = () => JSON.parse(smStore.getItem('callsheet3.card.v1')).filter(r => /Rangers @ Bruins/.test(r.matchup) && r.gdate === '2026-11-12');   // rows from earlier checks sit on the card too
    const stored1 = mine()[0];
    const takes1 = stored1.markets.filter(m => m.take).map(m => m.key + ':' + m.take.side + ':' + m.take.pick + ':' + m.take.price + ':' + (m.take.p > 0 && m.take.p < 1));
    const tr1 = document.querySelector('#board tbody tr'), on1 = tr1.classList.contains('taking') && /Taking/.test(tr1.querySelector('.takebtn').textContent);
    const list1 = [...document.querySelectorAll('#taking .pk')].map(e => e.innerText.replace(/\s+/g, ' ').trim());
    const head1 = document.getElementById('takingHead').hidden, count1 = document.getElementById('takingCount').textContent;
    const cardOn = [...document.querySelectorAll('#picks .pk .takebtn.on, #bestBets .pk .takebtn.on, #likeliest .pk .takebtn.on')].length;
    // a rescore rebuilds every ungraded row's markets: the mark moves over
    document.getElementById('rescore').click(); await wait();
    const takes2 = mine()[0].markets.filter(m => m.take).map(m => m.key + ':' + m.take.side);
    // the same game added again from the form replaces its markets: the mark moves over
    set('line', '6'); await wait(); document.getElementById('add').click(); await wait();
    const takes3 = mine()[0].markets.filter(m => m.take).map(m => m.key + ':' + m.take.side), nRows = mine().length;
    // the copy button speaks, with or without a clipboard
    document.getElementById('takingText').click(); await new Promise(r => setTimeout(r, 250));
    const said = document.getElementById('saveMsg').textContent;
    // grade the game 2-3: the mark grades on its card, the button becomes a TAKEN chip, and What you took keeps the line
    const trc = () => [...document.querySelectorAll('#cardTable tr')].find(t => /Rangers @ Bruins/.test(t.textContent));
    const g = (k, v) => { const el = trc().querySelector(`.grade[data-k="${k}"]`); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); };
    g('fa', '2'); g('fh', '3'); await wait();
    const list3 = [...document.querySelectorAll('#taking .pk')].map(e => e.innerText.replace(/\s+/g, ' ').trim());
    const res3 = (document.querySelector('#taking .pk .chip.win, #taking .pk .chip.loss, #taking .pk .chip.push') || {}).textContent || '';
    const boardRes = (document.querySelector('#board tbody tr.taking td:nth-child(10) .chip') || {}).textContent || '';
    const chip3 = (document.querySelector('#board tbody tr.taking .chip.taken') || {}).textContent || '', btn3 = document.querySelectorAll('#board tbody tr.taking .takebtn').length;
    const took = [...document.querySelectorAll('#calibBox .calib[data-sport="TAKEN"] > div')].map(d => d.innerText.replace(/\s+/g, ' ').trim());
    // a graded row refuses a new mark
    const other = [...document.querySelectorAll('#board tbody tr')].find(t => !t.classList.contains('taking')), otherBtns = other ? other.querySelectorAll('.takebtn').length : -1;
    return { head0, btns0, rows0, pick0, lineAfter, takes1, on1, list1, head1, count1, cardOn, takes2, takes3, nRows, said, list3, res3, boardRes, chip3, btn3, took, otherBtns };
  });
  chk(takeT.head0 && takeT.btns0 === takeT.rows0 && takeT.rows0 > 0 && takeT.lineAfter === '5.5' && takeT.takes1.length === 1 && new RegExp('^(total|p1|ml|pl):(OVER|UNDER|HOME|AWAY):' + takeT.pick0.replace(/[.+\-]/g, '\\$&') + ':[-−]?\\d+:true$').test(takeT.takes1[0])
      && takeT.on1 && !takeT.head1 && takeT.count1 === '1 marked' && takeT.list1.length === 2 && /^TAKING · NHL · marked /.test(takeT.list1[0]) && takeT.list1[0].indexOf(takeT.pick0) > 0 && /Rangers @ Bruins/.test(takeT.list1[0]) && /Taking$/i.test(takeT.list1[0])
      && /^TONIGHT 1 bet marked none graded yet · one unit each 1 on the card, 0 from the simulation, 0 props$/.test(takeT.list1[1]) && takeT.cardOn >= 1,
      'take: a Take button on every priced row of the board marks the pick as shown without opening the row; the row lights, the same market\'s card lights, and Taking tonight lists it with a summary card', JSON.stringify(takeT).slice(0, 1200));
  chk(takeT.takes2.length === 1 && takeT.takes2[0] === takeT.takes1[0].split(':').slice(0, 2).join(':') && takeT.takes3.length === 1 && takeT.takes3[0] === takeT.takes2[0] && takeT.nRows === 1 && /Copied the bets you are taking|the text is below/.test(takeT.said),
      'take: the mark rides through a rescore and through the same game added again, and the copy button speaks', JSON.stringify({ t2: takeT.takes2, t3: takeT.takes3, rows: takeT.nRows, said: takeT.said.slice(0, 80) }));
  chk(takeT.list3.length === 2 && /(WIN|LOSS|PUSH|win|loss|push)/.test(takeT.res3) && takeT.res3.toLowerCase() === takeT.boardRes.toLowerCase() && takeT.chip3 === 'TAKEN' && takeT.btn3 === 0 && takeT.otherBtns === 0
      && takeT.took.length === 1 && new RegExp('^Game bets taken ' + (takeT.res3.toLowerCase() === 'win' ? '1-0' : takeT.res3.toLowerCase() === 'loss' ? '0-1' : '0-0-1') + ' ', 'i').test(takeT.took[0]) && /says \d+\.\d% · does \d+\.\d% \(±\d+\.\d\) · [-−+]\d\.\d\du$/.test(takeT.took[0])
      && new RegExp('graded ' + (takeT.res3.toLowerCase() === 'win' ? '1-0' : takeT.res3.toLowerCase() === 'loss' ? '0-1' : '0-0-1') + ' · ').test(takeT.list3[1]),
      'take: once the game grades the marked bet shows its result on its card and the board, the button becomes a TAKEN chip, no mark can be added to the graded row, and What you took keeps the record at the price marked', JSON.stringify({ list3: takeT.list3, res: takeT.res3, board: takeT.boardRes, chip: takeT.chip3, took: takeT.took, other: takeT.otherBtns }));
  await pg.reload(); await pg.waitForTimeout(300); await pg.evaluate(() => smStore.ready);
  const takeR = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 90));
    document.getElementById('boardDate').value = '2026-11-12'; document.getElementById('boardDate').dispatchEvent(new Event('change')); await wait();
    const list = [...document.querySelectorAll('#taking .pk')].map(e => e.innerText.replace(/\s+/g, ' ').trim()), hidden = document.getElementById('takingHead').hidden;
    // the props: the example's best card, the table row and the panel each carry the button; Taking lists the mark; the board's Taking tonight lists it on the props' date
    document.getElementById('m-props').click(); await wait(); document.getElementById('propsExample').click(); await wait();
    const card = () => [...document.querySelectorAll('#propsBest .pk')].find(e => /Tyrese Maxey/.test(e.textContent)), id = card().getAttribute('data-prop');   // re-found after every re-render
    const pHead0 = document.getElementById('propsTakingHead').hidden, pBtns = document.querySelectorAll('#propsTable tr[data-prop] .takebtn').length, pRows = document.querySelectorAll('#propsTable tr[data-prop]').length;
    card().querySelector('.takebtn').click(); await wait();
    const dlgOpen = !document.getElementById('propDetail').hidden;
    const pList = [...document.querySelectorAll('#propsTaking .pk')].map(e => e.innerText.replace(/\s+/g, ' ').trim());
    const rowTaking = !!document.querySelector('#propsTable tr[data-prop="' + id + '"].taking'), cardOn = card().querySelector('.takebtn').classList.contains('on');
    const pCount = document.getElementById('propsTakingCount').textContent, pHead1 = document.getElementById('propsTakingHead').hidden;
    card().click(); await wait();
    const panelBtn = (document.querySelector('#propDetail .pd-take .takebtn') || {}).textContent || '', panelOn = !!document.querySelector('#propDetail .pd-take .takebtn.on');
    document.querySelector('#propDetail .pd-take .takebtn').click(); await wait();   // unmark from the panel
    const panelOff = !document.querySelector('#propDetail .pd-take .takebtn.on') && !!document.querySelector('#propDetail .pd-take .takebtn'), pList2 = document.querySelectorAll('#propsTaking .pk').length, pHead2 = document.getElementById('propsTakingHead').hidden;
    document.getElementById('propDetailClose').click(); await wait();
    card().querySelector('.takebtn').click(); await wait();   // mark it again from the card
    document.getElementById('propsTakingText').click(); await new Promise(r => setTimeout(r, 250));
    const pSaid = document.getElementById('propsMsg').textContent;
    const today = document.getElementById('propsDate').value;
    document.getElementById('m-nba').click(); await wait();   // the example is put away by a sport button, and its mark with it
    document.getElementById('m-props').click(); await wait();
    const gone = document.querySelectorAll('#propsTaking .pk').length + (document.getElementById('propsTakingHead').hidden ? 0 : 100);
    document.getElementById('m-nba').click(); await wait();
    document.getElementById('boardDate').value = today; document.getElementById('boardDate').dispatchEvent(new Event('change')); await wait();
    const boardProps = [...document.querySelectorAll('#taking .pk')].map(e => e.innerText.replace(/\s+/g, ' ').trim()).filter(t => /NBA PROP/.test(t)).length;
    await smStore.removeItem('callsheet3.card.v1'); await smStore.removeItem('callsheet3.props.v1');
    document.getElementById('clear').click(); await wait();
    return { list, hidden, pHead0, pBtns, pRows, dlgOpen, pList, rowTaking, cardOn, pCount, pHead1, panelBtn, panelOn, panelOff, pList2, pHead2, pSaid, gone, boardProps };
  });
  chk(!takeR.hidden && takeR.list.length === 2 && /^TAKING · NHL/.test(takeR.list[0]), 'take: the mark survives a reload of the page', JSON.stringify({ hidden: takeR.hidden, list: takeR.list }));
  chk(takeR.pHead0 && takeR.pBtns === 7 && takeR.pRows === 7 && !takeR.dlgOpen && takeR.pList.length === 1 && /^TAKING · NBA PROP · LEAN Tyrese Maxey OVER 25\.5 points 5\d\.\d% · [-−]110 needs 52\.4% 76ers @ Knicks · fanatics · projected 28\.07 .*Taking$/i.test(takeR.pList[0])
      && takeR.rowTaking && takeR.cardOn && takeR.pCount === '1 marked' && !takeR.pHead1 && takeR.panelOn && /Taking/.test(takeR.panelBtn) && takeR.panelOff && takeR.pList2 === 0 && takeR.pHead2
      && /Copied the props you are taking|the text is below/.test(takeR.pSaid) && takeR.gone === 0 && takeR.boardProps === 0,
      'take: a prop\'s Take button on the best card marks it without opening the panel; the row lights, Taking lists it with a count, the panel\'s own button shows it on and unmarks it, the copy button speaks, and the example\'s mark goes with the example',
      JSON.stringify(takeR).slice(0, 1200));

  // ---- 26 Oct 2026: the simulation's calls can be taken too -- a Take button under every chip on the NBA Simulation card, greyed until the
  //      game is on the card; the mark lives on the row, lists under Taking tonight as a simulation call, rides through a rescore and grades on its own tile ----
  const simTakeT = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 90));
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    await smStore.removeItem('callsheet3.card.v1');
    document.getElementById('clear').click(); document.getElementById('m-nba').click(); await wait();
    set('gdate', '2026-11-13'); document.getElementById('example').click(); await wait(); set('gdate', '2026-11-13'); await wait();
    const off0 = document.querySelectorAll('#nbaSimPanel .takebtn.off[disabled]').length, on0 = document.querySelectorAll('#nbaSimPanel .takebtn[data-stake]').length;
    const hint = (document.querySelector('#nbaSimPanel .takebtn.off') || {}).title || '';
    document.getElementById('add').click(); await wait();
    document.getElementById('boardDate').value = '2026-11-13'; document.getElementById('boardDate').dispatchEvent(new Event('change')); await wait();
    const live = document.querySelectorAll('#nbaSimPanel .takebtn[data-stake]').length, off1 = document.querySelectorAll('#nbaSimPanel .takebtn.off').length;
    const mine = () => JSON.parse(smStore.getItem('callsheet3.card.v1')).filter(r => /76ers @ Knicks/.test(r.matchup) && r.gdate === '2026-11-13');
    const mlBtn = document.querySelector('#nbaSimPanel .takebtn[data-stake*="|own|ml|"]'), mlSpec = mlBtn.getAttribute('data-stake');
    mlBtn.click(); await wait();
    const t1 = (mine()[0].simTakes || [])[0] || null;
    const btnOn = !!document.querySelector('#nbaSimPanel .takebtn.on[data-stake="' + mlSpec + '"]');
    const list1 = [...document.querySelectorAll('#taking .pk')].map(e => e.innerText.replace(/\s+/g, ' ').trim());
    // a second mark, the total's own-view call, then the first unmarked from the Taking card
    const totBtn = document.querySelector('#nbaSimPanel .takebtn[data-stake*="|own|total|"]'); totBtn.click(); await wait();
    const n2 = (mine()[0].simTakes || []).length, count2 = document.getElementById('takingCount').textContent;
    document.querySelector('#taking .pk.sim .takebtn.on').click(); await wait();
    const after = (mine()[0].simTakes || []).map(t => t.id), list2 = document.querySelectorAll('#taking .pk.sim').length;
    // a rescore keeps the mark; the copy names the simulation
    document.getElementById('rescore').click(); await wait();
    const after3 = (mine()[0].simTakes || []).map(t => t.id);
    document.getElementById('takingText').click(); await new Promise(r => setTimeout(r, 250));
    const said = document.getElementById('saveMsg').textContent;
    // grade: 231 points, the Knicks by ten -- the total's call grades off the final
    const trc = () => [...document.querySelectorAll('#cardTable tr')].find(t => /76ers @ Knicks/.test(t.textContent));
    const g = (k, v) => { const el = trc().querySelector(`.grade[data-k="${k}"]`); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); };
    g('fa', '110'); g('fh', '120'); await wait();
    const t3 = (mine()[0].simTakes || [])[0], list3 = [...document.querySelectorAll('#taking .pk.sim')].map(e => e.innerText.replace(/\s+/g, ' ').trim());
    const took = [...document.querySelectorAll('#calibBox .calib[data-sport="TAKEN"] > div')].map(d => d.innerText.replace(/\s+/g, ' ').trim());
    await smStore.removeItem('callsheet3.card.v1'); document.getElementById('clear').click(); await wait();
    return { off0, on0, hint, live, off1, mlSpec, t1, btnOn, list1, n2, count2, after, list2, after3, said, t3, list3, took };
  });
  chk(simTakeT.off0 >= 7 && simTakeT.on0 === 0 && /Add the game to the card first/.test(simTakeT.hint) && simTakeT.live === simTakeT.off0 && simTakeT.off1 === 0
      && simTakeT.t1 && simTakeT.t1.view === 'own' && simTakeT.t1.key === 'ml' && /^(HOME|AWAY)$/.test(simTakeT.t1.side) && simTakeT.t1.pick === (simTakeT.t1.side === 'HOME' ? 'Knicks ML' : '76ers ML')
      && simTakeT.t1.price === (simTakeT.t1.side === 'HOME' ? -198 : 164) && simTakeT.t1.p > 0.5 && simTakeT.t1.p < 1 && simTakeT.t1.worth > 0.5 && /^(LEAN|BET|STRONG)$/.test(simTakeT.t1.band) && simTakeT.t1.line === null && simTakeT.btnOn
      && simTakeT.list1.length === 2 && /^TAKING · NBA · SIMULATION · marked /.test(simTakeT.list1[0]) && /Knicks ML \d\d% by the sim · worth \d\d% · (LEAN|BET|STRONG) · [-−]198 needs 66\.4% 76ers @ Knicks · the sim's own view/.test(simTakeT.list1[0])
      && /1 bet marked none graded yet · one unit each 0 on the card, 1 from the simulation, 0 props$/.test(simTakeT.list1[1]),
      'sim take: the Simulation card\'s buttons are greyed with a hint until the game is on the card, then a click marks the call on the row as shown (the pick in words, the row\'s price, the sim\'s chance, worth and band) and Taking tonight lists it as a simulation call', JSON.stringify(simTakeT).slice(0, 1400));
  chk(simTakeT.n2 === 2 && simTakeT.count2 === '2 marked' && simTakeT.after.length === 1 && /^own\|total\|(OVER|UNDER)$/.test(simTakeT.after[0]) && simTakeT.list2 === 1 && simTakeT.after3.join() === simTakeT.after.join()
      && /Copied the bets you are taking|the text is below/.test(simTakeT.said),
      'sim take: a second call marks beside the first, the Taking card\'s own button unmarks one, a rescore keeps the mark, and the copy speaks', JSON.stringify({ n2: simTakeT.n2, count: simTakeT.count2, after: simTakeT.after, list2: simTakeT.list2, after3: simTakeT.after3, said: simTakeT.said.slice(0, 60) }));
  chk(simTakeT.t3 && simTakeT.t3.key === 'total' && simTakeT.t3.line === 231.5 && simTakeT.list3.length === 1 && new RegExp(' · ' + (simTakeT.t3.side === 'UNDER' ? 'win' : 'loss') + ' 76ers @ Knicks', 'i').test(simTakeT.list3[0]) && /TAKEN$/.test(simTakeT.list3[0])
      && simTakeT.took.some(t => new RegExp('^Simulation calls taken ' + (simTakeT.t3.side === 'UNDER' ? '1-0' : '0-1') + ' says \\d\\d\\.\\d% · does (100|0)\\.0%', 'i').test(t)),
      'sim take: once the game grades the call shows its result off the final on its card, the button becomes a TAKEN chip, and What you took keeps it on the Simulation calls tile', JSON.stringify({ t3: simTakeT.t3, list3: simTakeT.list3, took: simTakeT.took }));

  // ---- 26 Oct 2026: the levers' tally -- a Levers column counting the factors toward the pick and against, sortable, a filter for the
  //      props where every lever leans the pick's way, the tag on the card and the panel's heading ----
  const leverT = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 90));
    document.getElementById('propsReset').click(); await wait();
    document.getElementById('m-props').click(); await wait(); document.getElementById('propsExample').click(); await wait();
    const card = () => [...document.querySelectorAll('#propsBest .pk')].find(e => /Tyrese Maxey/.test(e.textContent)), id = card().getAttribute('data-prop');
    const cell = (tr) => (tr.querySelector('td.agree') || {}).textContent || '';
    const head = document.querySelector('#propsTable th[data-sort="agree"]').textContent;
    const maxey = document.querySelector('#propsTable tr[data-prop="' + id + '"]'), maxeyCell = cell(maxey), maxeyCls = maxey.querySelector('td.agree').className, maxeyTitle = maxey.querySelector('td.agree').title;
    const tag = (card().querySelector('.n1 .tag') || {}).textContent || '', tagTitle = (card().querySelector('.n1 .tag') || {}).title || '';
    const all = [...document.querySelectorAll('#propsTable tbody tr[data-prop]')].map(cell);
    // sort by the levers: the top row has the most toward less against
    document.querySelector('#propsTable th[data-sort="agree"]').click(); await wait();
    const sorted = [...document.querySelectorAll('#propsTable tbody tr[data-prop]')].map(cell), headOn = document.querySelector('#propsTable th[data-sort="agree"]').textContent;
    const score = (s) => { const m = /^(\d+)▲ (\d+)▼$/.exec(s); return m ? (+m[1] - +m[2]) + (+m[1]) / 10 : -50; };
    // the filters
    const sel = (v) => { const el = document.getElementById('propsAgree'); el.value = v; el.dispatchEvent(new Event('change', { bubbles: true })); };
    sel('all'); await wait();
    const onlyAll = [...document.querySelectorAll('#propsTable tbody tr[data-prop]')].map(cell), shownAll = document.getElementById('propsShown').textContent;
    sel('most'); await wait();
    const onlyMost = [...document.querySelectorAll('#propsTable tbody tr[data-prop]')].map(cell);
    const stored = JSON.parse(localStorage.getItem('callsheet3.props.view.v1') || '{}');
    document.getElementById('propsReset').click(); await wait();
    const after = { rows: document.querySelectorAll('#propsTable tbody tr[data-prop]').length, agree: document.getElementById('propsAgree').value };
    // the panel's heading carries the words
    card().click(); await wait();
    const h4 = ([...document.querySelectorAll('#propDetail h4')].find(h => /What moves it/.test(h.textContent)) || {}).textContent || '';
    document.getElementById('propDetailClose').click(); await wait(); document.getElementById('m-nba').click(); await wait();
    return { head, maxeyCell, maxeyCls, maxeyTitle, tag, tagTitle, all, sorted, headOn, scores: sorted.map(score), onlyAll, shownAll, onlyMost, stored, after, h4 };
  });
  chk(leverT.head === 'Levers' && leverT.maxeyCell === '2▲ 4▼' && /\bneg\b/.test(leverT.maxeyCls) && leverT.maxeyTitle === '2 of 6 levers toward the OVER, 4 against' && leverT.tag === 'levers 2▲ 4▼' && leverT.tagTitle === leverT.maxeyTitle
      && leverT.all.length === 7 && leverT.all.every(s => /^\d+▲ \d+▼$/.test(s)) && /^What moves it · 2 of 6 levers toward the OVER, 4 against$/.test(leverT.h4.replace(/\s+/g, ' ').trim()),
      'levers: the Every-prop table counts each prop\'s levers toward the pick and against, Maxey 2 up 4 down in red, the best card carries the tally as a tag and the panel\'s heading says it in words', JSON.stringify(leverT).slice(0, 900));
  chk(/Levers ▾/.test(leverT.headOn) && leverT.scores.every((s, i, a) => i === 0 || s <= a[i - 1]) && leverT.scores[0] > leverT.scores[leverT.scores.length - 1]
      && leverT.onlyAll.every(s => /^\d+▲ 0▼$/.test(s)) && leverT.onlyAll.length < leverT.all.length && /^\d+ of 7 shown/.test(leverT.shownAll)
      && leverT.onlyMost.length >= leverT.onlyAll.length && leverT.onlyMost.every(s => { const m = /^(\d+)▲ (\d+)▼$/.exec(s); return m && +m[1] > +m[2]; }) && leverT.stored.agree === 'most' && leverT.after.rows === 7 && leverT.after.agree === '',
      'levers: the column sorts with the most agreement first, the filter keeps the props where every lever leans the pick\'s way or more do than not, the view is remembered and Reset view clears it', JSON.stringify({ head: leverT.headOn, scores: leverT.scores, all: leverT.onlyAll, most: leverT.onlyMost, shown: leverT.shownAll, stored: leverT.stored, after: leverT.after }));

  // ---- 26 Oct 2026: usage and role on the prop, the floors, and the same-game pairs ----
  const usageT = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 90));
    document.getElementById('propsReset').click(); await wait();
    document.getElementById('m-props').click(); await wait(); document.getElementById('propsExample').click(); await wait();
    const card = () => [...document.querySelectorAll('#propsBest .pk')].find(e => /Tyrese Maxey/.test(e.textContent));
    card().click(); await wait();
    const dlg = document.getElementById('propDetail');
    const h3 = (dlg.querySelector('h3') || {}).innerText.replace(/\s+/g, ' ').trim(), role = (dlg.querySelector('h3 .tag.role') || {}).title || '';
    const usage = [...dlg.querySelectorAll('.pd-tiles .pd-tile')].map(e => e.querySelector('.k').textContent + '=' + e.querySelector('.v').textContent + '|' + ((e.querySelector('.s') || {}).textContent || '')).find(s => /^Usage=/.test(s)) || '';
    const floorsH = ([...dlg.querySelectorAll('h4')].find(h => /^Floors/.test(h.textContent)) || {}).nextElementSibling, floors = floorsH ? floorsH.innerText.replace(/\s+/g, ' ').trim() : '';
    const why = [...dlg.querySelectorAll('ul.pd-why li')].map(e => e.textContent).find(w => /^usage /.test(w)) || '';
    document.getElementById('propDetailClose').click(); await wait();
    // the filters: usage 24% and up, then the role
    const sel = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('change', { bubbles: true })); };
    const names = () => [...document.querySelectorAll('#propsTable tbody tr[data-prop]')].map(tr => tr.querySelectorAll('td')[1].textContent.trim());
    const heads = [...document.querySelectorAll('#propsTable thead th')].map(t => t.textContent.trim()), tds0 = [...document.querySelector('#propsTable tbody tr[data-prop]').querySelectorAll('td')];
    const aligned = heads.length === tds0.length && tds0[heads.indexOf('Sim')].classList.contains('simc') && tds0[heads.indexOf('Usage')].classList.contains('usgc') && tds0[heads.indexOf('Levers')].classList.contains('agree') && tds0[heads.indexOf('Take')].classList.contains('take');
    const usgCells = [...document.querySelectorAll('#propsTable tbody tr[data-prop]')].map(tr => tr.querySelectorAll('td')[1].textContent.trim().split(' ')[0] + ':' + tr.querySelector('td.usgc').textContent.trim() + ':' + tr.querySelector('td.usgc').className);
    document.querySelector('#propsTable th[data-sort="usage"]').click(); await wait();
    const usgSorted = [...document.querySelectorAll('#propsTable tbody tr[data-prop] td.usgc')].map(td => parseFloat(td.textContent)), usgShown = document.getElementById('propsShown').textContent;
    document.getElementById('propsReset').click(); await wait();
    sel('propsUsage', 'hi'); await wait(); const hi = names();
    sel('propsUsage', ''); sel('propsRole', 'bench'); await wait(); const bench = names();
    document.getElementById('propsReset').click(); await wait();
    const after = { n: names().length, usage: document.getElementById('propsUsage').value, role: document.getElementById('propsRole').value };
    // the pairs
    const pairs = [...document.querySelectorAll('#propsPairs .pk.pair')].map(e => ({ text: e.innerText.replace(/\s+/g, ' ').trim(), agrees: e.classList.contains('agrees') }));
    document.getElementById('m-nba').click(); await wait();
    return { h3, role, usage, floors, why, hi, bench, after, pairs, usgCells, usgSorted, usgShown, aligned };
  });
  chk(/^Tyrese Maxey G PHI starter$/.test(usageT.h3) && usageT.role === "RotoWire's expected five" && /^Usage=29%\|of his club's possessions while on; a starter, the miss read at 0\.91 sigmas \(measured\)$/.test(usageT.usage)
      && /^95% of nights: 1\d\+ · 90%: 1\d\+ · 80%: (19|2\d)\+ points\. Measured on 2025-26: the 95% floors cleared 97\.5% of nights/.test(usageT.floors)
      && /^usage 29\.0% of his club's possessions \(this season\), a starter \(RotoWire's expected five\): a high-usage starting man's miss runs 0\.91 sigmas, measured, so the chance is read narrower$/.test(usageT.why),
      'props: the panel carries his role as a tag, his usage as a tile with the sigma factor, the floors he clears 95, 90 and 80% of nights with the measured record behind them, and the why line', JSON.stringify({ h3: usageT.h3, role: usageT.role, usage: usageT.usage, floors: usageT.floors.slice(0, 200), why: usageT.why }));
  chk(usageT.aligned && usageT.usgCells.length === 7 && usageT.usgCells.some(c => /^Tyrese:29% S:usgc pos$/.test(c)) && usageT.usgCells.some(c => /^Kelly:19% B:usgc$/.test(c)) && usageT.usgCells.every(c => /:\d+(\.\d)?% [SB]:usgc( pos)?$/.test(c))
      && usageT.usgSorted.length === 7 && usageT.usgSorted.every((u, i, a) => i === 0 || u <= a[i - 1]) && /sorted by usage ▾/.test(usageT.usgShown)
      && usageT.hi.length === 3 && usageT.hi.every(n => /Jalen Brunson|Karl-Anthony Towns|Tyrese Maxey/.test(n)) && usageT.bench.length === 1 && /Kelly Oubre/.test(usageT.bench[0]) && usageT.after.n === 7 && usageT.after.usage === '' && usageT.after.role === ''
      && usageT.pairs.length >= 3 && usageT.pairs.every(p => /^PAIR #\d · 76ers @ Knicks · the price (agrees|asks more) .+ \+ .+ both land \d\d\.\d% · pays [-−+]\d+ \(\d\.\d\d×\) needs \d\d\.\d% .+ · (two players|two overs on one club|one man, two markets|one man, his points with his threes), measured ×(0\.95|1\.00|1\.15|1\.50) TAKE$/.test(p.text))
      && usageT.pairs.map(p => parseFloat(/both land (\d\d\.\d)%/.exec(p.text)[1])).every((c, i, a) => i === 0 || c <= a[i - 1]),
      'props: every header of the Every-prop table sits over its own cell; the Usage column carries his share with S or B for his role, green at 24% and up, and sorts highest first; the usage and role filters keep the right men and Reset view clears them, and the same-game pairs list the date\'s tickets likeliest first with the parlay\'s price, what it needs and the measured kind of pair', JSON.stringify({ aligned: usageT.aligned, cells: usageT.usgCells, sorted: usageT.usgSorted, shown: usageT.usgShown, hi: usageT.hi, bench: usageT.bench, after: usageT.after, pairs: usageT.pairs.map(p => p.text.slice(0, 160)) }));

  // ---- 26 Oct 2026: the simulation's stats on the Props page -- a card a game above the picks, the Sim column with its filter and sort, the best cards' last line ----
  const simPropsT = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 90));
    document.getElementById('propsReset').click(); await wait();
    document.getElementById('m-props').click(); await wait(); document.getElementById('propsExample').click(); await wait();
    const strip = [...document.querySelectorAll('#propsSim .pk.simg')].map(e => e.className + '|' + e.innerText.replace(/\s+/g, ' ').trim());
    const head = [...document.querySelectorAll('#propsTable thead th')].map(th => th.textContent.trim());
    const rowOf = tr => { const tds = tr.querySelectorAll('td'), c = tr.querySelector('td.simc'); return { name: tds[1].textContent.trim(), mk: tds[2].textContent.trim(), line: parseFloat(tds[3].textContent), side: tds[4].textContent.trim(), sim: c ? c.textContent.trim() : null, cls: c ? c.className : null, title: c ? c.title : '' }; };
    const rows = [...document.querySelectorAll('#propsTable tbody tr[data-prop]')].map(rowOf);
    const best = [...document.querySelectorAll('#propsBest .pk')].map(e => { const l = e.querySelector('.n5.simline'); return (e.querySelector('.n2') || {}).textContent + '→' + (l ? l.className + '|' + l.textContent.replace(/\s+/g, ' ').trim() : 'none'); });
    const sel = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('change', { bubbles: true })); };
    const cells = () => [...document.querySelectorAll('#propsTable tbody tr[data-prop] td.simc')].map(c => c.className);
    sel('propsSimSel', 'yes'); await wait(); const yes = cells();
    sel('propsSimSel', 'no'); await wait(); const no = cells();
    sel('propsSimSel', ''); await wait();
    document.querySelector('#propsTable th[data-sort="sim"]').click(); await wait();
    const sorted = [...document.querySelectorAll('#propsTable tbody tr[data-prop]')].map(rowOf), shown = document.getElementById('propsShown').textContent;
    document.getElementById('propsReset').click(); await wait();
    const after = { sim: document.getElementById('propsSimSel').value, n: document.querySelectorAll('#propsTable tbody tr[data-prop]').length, shown: document.getElementById('propsShown').textContent };
    document.getElementById('m-nba').click(); await wait();
    return { strip, head, rows, best, yes, no, sorted, shown, after };
  });
  const simGap = r => r.sim === null || r.sim === '' ? null : (r.side === 'UNDER' ? r.line - parseFloat(r.sim) : parseFloat(r.sim) - r.line);
  const simMaxey = simPropsT.rows.find(r => /^Tyrese Maxey/.test(r.name)), simBig = simPropsT.rows.slice().sort((a, b) => simGap(b) - simGap(a))[0];
  chk(simPropsT.strip.length === 1 && /^pk simg\|76ers @ Knicks · played 3,000 times PHI \d{2,3} · NYK \d{2,3} total \d{3} (NYK|PHI) by \d+\.\d · home win \d+(\.\d)?% · total \d{3}( · the book's [\d.]+ \([-−+][\d.]+\))? PHI middle half \d+–\d+ against [\d.]+ a game by the ratings · NYK \d+–\d+ against [\d.]+ blowout of 15 or more \d+(\.\d)?% · overtime \d+(\.\d)?% · [\d.]+ possessions · PHI's regulars out [-−][\d.]+ per 100 on the offence · the sim's read on the pick's side for \d of [67] props$/.test(simPropsT.strip[0])
      && simPropsT.head.slice(-4).join('|') === 'Levers|Sim|Usage|Take' && simPropsT.rows.length === 7 && simPropsT.rows.every(r => /^\d+(\.\d)?$/.test(r.sim) && /^simc( pos| neg)?$/.test(r.cls) && (simGap(r) > 0) === /pos/.test(r.cls) && (simGap(r) < 0) === /neg/.test(r.cls) && /the simulation's own read of the stat/.test(r.title))
      && simMaxey && simMaxey.side === 'OVER' && simMaxey.line === 25.5 && /^2\d\.\d$/.test(simMaxey.sim) && simMaxey.cls === 'simc ' + (parseFloat(simMaxey.sim) > 25.5 ? 'pos' : 'neg'),
      'props: the simulation\'s strip shows the example game played 3,000 times with both clubs\' points and middle halves against the ratings, the total, the margin, the blowout, overtime, the pace and the 76ers\' regulars out, and the Sim column carries the sim\'s own read on every projected prop, green on the pick\'s side of the line', JSON.stringify({ strip: simPropsT.strip, head: simPropsT.head.slice(-4), rows: simPropsT.rows.map(r => r.name + ' ' + r.side + ' ' + r.line + ' sim ' + r.sim + ' ' + r.cls) }));
  chk(simPropsT.best.length >= 4 && simPropsT.best.every(b => /→n5 simline( pos| neg)?\|Sim reads \d+(\.\d)? v the \d+\.5 line, (on the (OVER|UNDER)'s side|against the (OVER|UNDER)|on the line) · (PHI|NYK) \d{2,3} \(\d+–\d+\) · blowout \d+(\.\d)?%$/.test(b))
      && simPropsT.best.filter(b => /on the (OVER|UNDER)'s side/.test(b)).every(b => /simline pos/.test(b)) && simPropsT.best.filter(b => /against the (OVER|UNDER)/.test(b)).every(b => /simline neg/.test(b)) && simPropsT.best.filter(b => /on the line/.test(b)).every(b => /simline\|/.test(b))
      && simPropsT.yes.length >= 1 && simPropsT.yes.every(c => c === 'simc pos') && simPropsT.no.length >= 1 && simPropsT.no.every(c => c === 'simc neg') && simPropsT.yes.length + simPropsT.no.length === simPropsT.rows.filter(r => simGap(r) !== 0).length
      && simPropsT.sorted.length === 7 && simPropsT.sorted[0].name === simBig.name && simPropsT.sorted[0].mk === simBig.mk && simPropsT.sorted.every((r, i, a) => i === 0 || simGap(r) <= simGap(a[i - 1])) && /sorted by sim ▾/.test(simPropsT.shown)
      && simPropsT.after.sim === '' && simPropsT.after.n === 7 && !/sorted/.test(simPropsT.after.shown),
      'props: every best card ends with the sim\'s read against the line in green or red, the simulation filter keeps the props the sim\'s read sides with (or against), the Sim column sorts by the gap toward the pick, and Reset view clears both', JSON.stringify({ best: simPropsT.best.map(b => b.slice(0, 140)), yes: simPropsT.yes, no: simPropsT.no, sorted: simPropsT.sorted.map(r => r.name + ' ' + r.side + ' ' + r.line + ' ' + r.sim), shown: simPropsT.shown, after: simPropsT.after }));

  // ---- 26 Oct 2026: what happened on each of his last games -- the slate writes beside each game what the box says (a regular back or out,
  //      a blowout, his role, then his minutes, shots and shooting against his season's, then overtime and the pace); the panel's Last games table
  //      shows it as a column, the first factor bold, red under the line and green over it ----
  const whatT = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 90));
    document.getElementById('propsReset').click(); await wait();
    document.getElementById('m-props').click(); await wait(); document.getElementById('propsExample').click(); await wait();
    [...document.querySelectorAll('#propsBest .pk')].find(e => /Tyrese Maxey/.test(e.textContent)).click(); await wait();
    const dlg = document.getElementById('propDetail');
    const head = [...dlg.querySelectorAll('.pd-log thead th')].map(t => t.textContent), h4 = ([...dlg.querySelectorAll('h4')].find(h => /^Last games/i.test(h.textContent)) || {}).innerText.replace(/\s+/g, ' ').trim();
    const rows = [...dlg.querySelectorAll('.pd-log tbody tr')].map(tr => { const tds = tr.querySelectorAll('td'), b = tr.querySelector('td.pd-what b'); return { stat: tds[3].textContent.trim(), mark: tds[3].querySelector('b.lg').className, what: tds[4] ? tds[4].textContent.trim() : null, first: b ? b.textContent : '', cls: b ? b.className : '' }; });
    document.getElementById('propDetailClose').click(); await wait();
    // a prop with another market reads its own factors: rebounds take no shots or shooting
    [...document.querySelectorAll('#propsBest .pk')].find(e => /Karl-Anthony Towns/.test(e.textContent)).click(); await wait();
    const rebWhat = [...dlg.querySelectorAll('.pd-log tbody tr td.pd-what')].map(td => td.textContent.trim()).filter(t => t);
    document.getElementById('propDetailClose').click(); await wait();
    // a PRA prop opens each game with the three behind the total (27 Oct 2026)
    [...document.querySelectorAll('#propsTable tr[data-prop]')].find(tr => /Mikal Bridges/.test(tr.textContent)).click(); await wait();
    const praWhat = [...dlg.querySelectorAll('.pd-log tbody tr')].map(tr => (tr.querySelectorAll('td')[3].textContent.trim()) + '=' + tr.querySelector('td.pd-what').textContent.trim());
    document.getElementById('propDetailClose').click(); await wait();
    document.getElementById('m-nba').click(); await wait();
    return { head, h4, rows, rebWhat, praWhat };
  });
  const whatRe = /^((\d+ pts \+ \d+ reb \+ \d+ ast = \d+)|(.+ (back|out) \(\d+ mpg(, (a lift for him|the lift gone))?\))|((won|lost) by \d+(, a blowout)?)|(off the bench)|(a start)|(\d+ min, \d+ (under|over) his usual \d+)|(\d+ min \(his usual \d+\))|(\d+ shots, \d+ (under|over) his usual at those minutes)|(\d+ shots \(his usual \d+ at those minutes\))|(\d+ of \d+ from the floor(, (cold|hot) \(his season \d+%\))?)|(overtime)|(a (slow|fast) game, \d+ possessions against their usual \d+)|(\d+ of the club's \d+ (rebounds|assists)(, \d+% \(his usual \d+%\)| \(his usual \d+%\))?)|(.+ (took|had) \d+ \(his usual \d+(\.\d)?\)))$/;
  chk(whatT.head.join('|') === 'Date|Opp|Min|points|What happened' && /^LAST GAMES \(\d+ of 10 over 25\.5\) · what the box says happened, the biggest factor first$/i.test(whatT.h4) && whatT.rows.length === 10
      && whatT.rows.every(r => r.what && r.what.split(' · ').length >= 3 && r.what.split(' · ').length <= 5 && r.what.split(' · ').every(p => whatRe.test(p)) && /(won|lost) by \d+/.test(r.what) && /\d+ min/.test(r.what) && /\d+ shots/.test(r.what))
      && whatT.rows.every(r => !r.first || (r.first === r.what.split(' · ')[0] && r.cls === (/over/.test(r.mark) ? 'over' : /under/.test(r.mark) ? 'under' : '')))
      && whatT.rows.some(r => /(back|out) \(\d+ mpg, (a lift for him|the lift gone)\)/.test(r.first)) && whatT.rows.some(r => /a blowout/.test(r.what)) && whatT.rows.some(r => /shots, \d+ (under|over) his usual/.test(r.what))
      && whatT.rebWhat.length === 10 && whatT.rebWhat.every(t => !/shots|from the floor/.test(t) && /\d+ min/.test(t) && /(won|lost) by \d+/.test(t) && /of the club's \d+ rebounds/.test(t)) && whatT.rebWhat.some(t => /(Josh Hart|Joel Embiid) took 12 \(his usual 6\.5\)/.test(t))
      && whatT.praWhat.length === 10 && whatT.praWhat.every(t => { const m = /^(\d+)=(\d+) pts \+ (\d+) reb \+ (\d+) ast = (\d+)( · |$)/.exec(t); return !!m && +m[1] === +m[5] && +m[2] + +m[3] + +m[4] === +m[5]; }),
      'props: every one of the panel\'s last games carries the line behind it, the night\'s causes first (a regular back or out, a blowout) then what stood out and the plain box with the margin, the first item bold in the colour of the game\'s mark; a rebounds prop reads no shots or shooting; a PRA prop opens each game with the three behind the total, which add up to the stat', JSON.stringify(whatT).slice(0, 1800));

  // ---- 27 Oct 2026: the combination markets -- points + rebounds, points + assists and rebounds + assists list, filter, grade by the sum and name their tile ----
  const comboT = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 90));
    const txt = e => (e ? e.innerText : '').replace(/\s+/g, ' ').trim();
    await smStore.removeItem('callsheet3.props.v1'); document.getElementById('m-nba').click(); await wait();
    const load = async (doc, fname) => { const dt = new DataTransfer(); dt.items.add(new File([JSON.stringify(doc)], fname, { type: 'application/json' })); const inp = document.getElementById('slateFile'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true })); await wait(); };
    const mk = (pid, name, mkt, line, proj, sd, chance, side) => ({ pid, name, team: 'ATL', opp: 'ORL', home: false, pos: 'G', mk: mkt, line, op: -110, up: -110, book: 'fanatics', books: {}, proj, sd, pm: chance + 0.02, pb: 0.5, p: chance, push: 0, side, chance, price: -110, need: 0.5238, edge: chance - 0.5238, band: chance >= 0.55 && chance - 0.5238 >= 0.03 ? 'BET' : chance > 0.5238 ? 'LEAN' : 'no edge', mins: 35, rate36: 30, why: ['x'], log: [['2026-10-26', 'MIA', 0, 34, 37, ['28 pts + 9 ast = 37', '34 min (his usual 35)']]] });
    await load({ format: 'callsheet3.props', version: 1, date: '2026-10-28', games: [{ gid: '401909901', away: 'Hawks', home: 'Magic', aab: 'ATL', hab: 'ORL', props: [
      mk('3037789', 'Trae Young', 'pa', 35.5, 38.2, 11.4, 0.57, 'OVER'), mk('3037789', 'Trae Young', 'pr', 27.5, 29.1, 9.9, 0.53, 'OVER'), mk('4397020', 'Paolo Banchero', 'ra', 12.5, 11.6, 4.6, 0.56, 'UNDER') ] }] }, 'nba-props-2026-10-28.json');
    const rows = [...document.querySelectorAll('#propsTable tbody tr[data-prop]')].map(tr => { const t = tr.querySelectorAll('td'); return t[1].textContent.trim() + '|' + t[2].textContent.trim() + '|' + t[4].textContent.trim() + '|' + t[3].textContent.trim().split(' ')[0]; });
    const opts = [...document.querySelectorAll('#propsMk option')].map(o => o.value + '=' + o.textContent);
    const sel = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('change', { bubbles: true })); };
    sel('propsMk', 'ra'); await wait(); const onlyRa = [...document.querySelectorAll('#propsTable tbody tr[data-prop]')].map(tr => tr.querySelectorAll('td')[2].textContent.trim());
    document.getElementById('propsReset').click(); await wait();
    [...document.querySelectorAll('#propsTable tr[data-prop]')].find(tr => /pts \+ ast/.test(tr.textContent)).click(); await wait();
    const panel = txt(document.querySelector('#propDetail .pd-pick')) + ' || ' + txt(document.querySelector('#propDetail .pd-log tbody tr td.pd-what'));
    document.getElementById('propDetailClose').click(); await wait();
    await load({ format: 'callsheet2.slate', version: 1, date: '2026-10-28', games: [{ sport: 'NBA', gdate: '2026-10-28', away: 'Hawks', home: 'Magic', gameId: '401909901', finals: { fa: '118', fh: '112', f5a: '60', f5h: '55' }, notes: [],
      box: { '3037789': ['Trae Young', 36.2, 28, 3, 11, 4, { pa: ['28 pts + 11 ast = 39', 'won by 6'], pr: ['28 pts + 3 reb = 31', 'won by 6'] }], '4397020': ['Paolo Banchero', 34.0, 22, 9, 4, 1] } }] }, 'nba-grade-2026-10-28.json');
    const graded = JSON.parse(smStore.getItem('callsheet3.props.v1')).filter(r => r.gdate === '2026-10-28').map(r => r.name + ' ' + r.mk + ' ' + r.side + ' ' + r.line + ' -> ' + r.result + ' ' + r.actual + ' | ' + (r.awhat || []).join(' · '));
    const tile = txt(document.querySelector('#calibBox .calib[data-sport="PROPS"]'));
    document.getElementById('m-nba').click(); await wait(); await smStore.removeItem('callsheet3.props.v1');   // the key goes last: Clear this date saves what it keeps
    return { rows, opts, onlyRa, panel, graded, tile };
  });
  await pg.reload(); await pg.waitForTimeout(300); await pg.evaluate(() => smStore.ready);   // the graded fixture rows are records and stay in memory until a reload
  chk(comboT.rows.length === 3 && comboT.rows.join(';') === 'Trae Young G|pts + ast|OVER|35.5;Paolo Banchero G|reb + ast|UNDER|12.5;Trae Young G|pts + reb|OVER|27.5'
      && comboT.opts.slice(-3).join(',') === 'pr=pts + reb,pa=pts + ast,ra=reb + ast' && comboT.onlyRa.join(',') === 'reb + ast'
      && /^OVER 35\.5 pts \+ ast \|\| 28 pts \+ 9 ast = 37 · 34 min \(his usual 35\)$/.test(comboT.panel)
      && comboT.graded.join(';') === 'Trae Young pa OVER 35.5 -> win 39 | 28 pts + 11 ast = 39 · won by 6;Trae Young pr OVER 27.5 -> win 31 | 28 pts + 3 reb = 31 · won by 6;Paolo Banchero ra UNDER 12.5 -> loss 13 | '
      && /pts \+ ast 1-0/i.test(comboT.tile) && /pts \+ reb 1-0/i.test(comboT.tile) && /reb \+ ast 0-1/i.test(comboT.tile),
      'props: the combination markets list with their labels, filter by market, open their panel with the parts behind each game, grade by the sum of the box (28 + 11 = 39 over 35.5; 9 + 4 = 13 against the under 12.5) and take their own tiles in the record', JSON.stringify(comboT).slice(0, 1500));

  // ---- 27 Oct 2026: the fives and the matchup on the prop -- both clubs' starting fives on the panel with the man marked; a Matchup button on the
  //      panel and the cards, off until the NBA card has the game, then opening it into the form ----
  const goT = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 90));
    const txt = e => (e ? e.innerText : '').replace(/\s+/g, ' ').trim();
    await smStore.removeItem('callsheet3.card.v1'); document.getElementById('clear').click(); await wait();
    document.getElementById('propsReset').click(); await wait();
    document.getElementById('m-props').click(); await wait(); document.getElementById('propsExample').click(); await wait();
    const today = document.getElementById('propsDate').value, dlg = document.getElementById('propDetail');
    const card0 = [...document.querySelectorAll('#propsBest .pk')].find(e => /Tyrese Maxey/.test(e.textContent));
    const cardBtn0 = card0.querySelector('.btn.go[data-pgo]'), cardOff0 = cardBtn0 ? cardBtn0.classList.contains('off') : null, cardTitle0 = cardBtn0 ? cardBtn0.title : '';
    card0.click(); await wait();
    const fives = [...dlg.querySelectorAll('.pd-fives .five')].map(e => txt(e)), me = txt(dlg.querySelector('.pd-fives tr.me')), heads = [...dlg.querySelectorAll('.pd-fives .lbadge')].map(e => e.className + '|' + e.textContent);
    const panelBtn = dlg.querySelector('.pd-go .btn.go[data-pgo]'), panelOff = panelBtn ? panelBtn.classList.contains('off') : null, panelText = txt(panelBtn), takeStill = !!dlg.querySelector('.pd-take .takebtn[data-ptake]');
    panelBtn.click(); await wait();
    const stillOpen = !dlg.hidden, said = txt(document.getElementById('propsMsg'));
    document.getElementById('propDetailClose').click(); await wait();
    // the NBA example on the card for the props' date, then the button is live and opens the game into the form
    document.getElementById('m-nba').click(); await wait();
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    set('gdate', today); document.getElementById('example').click(); await wait(); set('gdate', today); await wait();
    document.getElementById('add').click(); await wait();
    document.getElementById('clear').click(); await wait();
    const awayBefore = document.getElementById('away').value;
    document.getElementById('m-props').click(); await wait(); document.getElementById('propsExample').click(); await wait();
    const card1 = [...document.querySelectorAll('#propsBest .pk')].find(e => /Tyrese Maxey/.test(e.textContent)), cardBtn1 = card1.querySelector('.btn.go[data-pgo]'), cardLive = cardBtn1 && !cardBtn1.classList.contains('off');
    cardBtn1.click(); await wait();
    const propsHidden = document.getElementById('propsView').hidden, dlgHidden = dlg.hidden, away = document.getElementById('away').value, home = document.getElementById('home').value, nbaPressed = document.getElementById('m-nba').getAttribute('aria-pressed');
    const lineupPanel = txt(document.getElementById('nbaLineupPanel')).slice(0, 80);
    await smStore.removeItem('callsheet3.card.v1'); document.getElementById('clear').click(); await wait();
    return { cardOff0, cardTitle0, fives, me, heads, panelOff, panelText, takeStill, stillOpen, said, awayBefore, cardLive, propsHidden, dlgHidden, away, home, nbaPressed, lineupPanel };
  });
  chk(goT.cardOff0 === true && /^The NBA card has no row for 76ers @ Knicks on /.test(goT.cardTitle0) && goT.fives.length === 2 && /^76ers EXPECTED PG Tyrese Maxey THIS PROP SG VJ Edgecombe SF Paul George PF Kelly Oubre Jr\. C Adem Bona May not play: C Andre Drummond \(Questionable\)\.$/i.test(goT.fives[0])
      && /^Knicks CONFIRMED PG Jalen Brunson SG Mikal Bridges SF OG Anunoby PF Josh Hart C Karl-Anthony Towns$/i.test(goT.fives[1]) && /^PG Tyrese Maxey THIS PROP$/i.test(goT.me) && goT.heads.join(',') === 'lbadge exp|expected,lbadge conf|confirmed'
      && goT.panelOff === true && /^open the matchup on the nba card$/i.test(goT.panelText) && goT.takeStill && goT.stillOpen && /^The NBA card has no row for 76ers @ Knicks on .+: load the NBA slate for the date \(Load slate\) and Add the game, and the button opens it\.$/.test(goT.said),
      'props: the panel carries both clubs\' starting fives from the props run with the prop\'s man marked and the status badges, and the Matchup button is off, with the reason, while the NBA card has no row for the game', JSON.stringify(goT).slice(0, 1200));
  chk(goT.awayBefore === '' && goT.cardLive === true && goT.propsHidden && goT.dlgHidden && /76ers/.test(goT.away) && /Knicks/.test(goT.home) && goT.nbaPressed === 'true' && !/No lineup on the row/.test(goT.lineupPanel),
      'props: once the NBA card has the game, Matchup on the card opens it into the form: the props view folds away, the NBA tab is pressed and the form reads the game with its lineup panel', JSON.stringify({ before: goT.awayBefore, live: goT.cardLive, hidden: goT.propsHidden, dlg: goT.dlgHidden, away: goT.away, home: goT.home, nba: goT.nbaPressed, lineup: goT.lineupPanel }));

  // ---- 26 Oct 2026: the pair's own panel -- a same-game pair card opens like a prop: the ticket's numbers, how the chance is made, each leg with a way
  //      into its own panel, Previous / Next across the night's tickets; Take marks the pair on both legs, lists it under Taking and grades it under What you took ----
  const pairT = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 90));
    document.getElementById('propsReset').click(); await wait();
    document.getElementById('m-props').click(); await wait(); document.getElementById('propsExample').click(); await wait();
    const o = {}, dlg = document.getElementById('propDetail'), txt = e => (e ? e.innerText : '').replace(/\s+/g, ' ').trim();
    const cards = [...document.querySelectorAll('#propsPairs .pk.pair')]; o.nCards = cards.length; o.attrs = cards.map(c => c.getAttribute('data-pair'));
    cards[0].click(); await wait();
    o.open = !dlg.hidden; o.band = txt(dlg.querySelector('.pd-band')); o.h3 = txt(dlg.querySelector('h3')); o.pick = txt(dlg.querySelector('.pd-pick')); o.sub = txt(dlg.querySelector('.pd-sub'));
    o.tiles = [...dlg.querySelectorAll('#propDetailBody > .pd-tiles .pd-tile')].map(e => e.querySelector('.k').textContent + '=' + e.querySelector('.v').textContent);
    o.how = txt(([...dlg.querySelectorAll('h4')].find(h => /^How the chance/.test(h.textContent)) || {}).nextElementSibling);
    o.legs = [...dlg.querySelectorAll('.pd-leg')].map(e => txt(e.querySelector('h4')) + ' || ' + [...e.querySelectorAll('.pd-tile .k')].map(k => k.textContent).join(',') + ' || ' + txt(e.querySelector('.pd-base')) + ' || ' + txt(e.querySelector('button[data-prop]')) + ' | ' + !!e.querySelector('.takebtn[data-ptake]'));
    o.nav = { hidden: document.getElementById('propDetailNav').hidden, pos: document.getElementById('propDetailPos').textContent, prevOff: document.getElementById('propDetailPrev').disabled, nextOff: document.getElementById('propDetailNext').disabled };
    o.bigBtn = txt(dlg.querySelector('.pd-take .takebtn[data-ttake]'));
    document.getElementById('propDetailNext').click(); await wait();
    o.h3next = txt(dlg.querySelector('h3')); o.posNext = document.getElementById('propDetailPos').textContent;
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft', bubbles: true })); await wait();
    o.h3back = txt(dlg.querySelector('h3'));
    dlg.querySelector('.pd-take .takebtn[data-ttake]').click(); await wait();   // take the pair from its panel
    o.takeOn = !!dlg.querySelector('.pd-take .takebtn.on[data-ttake]'); o.cardTaking = document.querySelectorAll('#propsPairs .pk.pair.taking').length; o.cardBtnOn = document.querySelectorAll('#propsPairs .pk.pair .takebtn.on[data-ttake]').length;
    o.takingList = [...document.querySelectorAll('#propsTaking .pk')].map(txt); o.takingCount = document.getElementById('propsTakingCount').textContent; o.takingHead = document.getElementById('propsTakingHead').hidden;
    o.stored = JSON.stringify(((window.__props_preview_peek = null), null));
    dlg.querySelector('.pd-leg button[data-prop]').click(); await wait();   // the first leg's own panel from the pair's
    o.legPanel = txt(dlg.querySelector('h3')) + ' | ' + txt(dlg.querySelector('.pd-band')) + ' | ' + document.getElementById('propDetailPos').textContent;
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })); await wait();
    o.closed = dlg.hidden && !document.body.classList.contains('noscroll');
    document.querySelector('#propsTaking .pk.pair').click(); await wait();   // the Taking card opens the pair's panel too
    o.fromTaking = txt(dlg.querySelector('.pd-band')) + ' | ' + txt(dlg.querySelector('h3'));
    document.getElementById('propDetailClose').click(); await wait();
    document.querySelector('#propsPairs .pk.pair .takebtn.on[data-ttake]').click(); await wait();   // unmark from the card's button, without opening it
    o.unmarked = { dlg: dlg.hidden, taking: document.querySelectorAll('#propsPairs .pk.pair.taking').length, list: document.querySelectorAll('#propsTaking .pk').length, head: document.getElementById('propsTakingHead').hidden };
    const today = document.getElementById('propsDate').value;
    // a real file: a pair marked before the game lists on the board, rides through the file loaded again, grades under What you took and in the tab's record
    const load = async (doc, fname) => { const dt = new DataTransfer(); dt.items.add(new File([JSON.stringify(doc)], fname, { type: 'application/json' })); const inp = document.getElementById('slateFile'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true })); await wait(); };
    const pdoc = { format: 'callsheet3.props', version: 1, date: '2026-10-27', games: [
      { gid: '401909900', away: 'Hawks', home: 'Magic', aab: 'ATL', hab: 'ORL', spread: -4.5, total: 229.5, pace: 99.8, props: [
        { pid: '3037789', name: 'Trae Young', team: 'ATL', opp: 'ORL', home: false, pos: 'G', mk: 'pts', line: 24.5, op: -110, up: -110, book: 'fanatics', books: { fanatics: [24.5, -110, -110] }, proj: 27.2, sd: 9.4, pm: 0.63, pb: 0.5, p: 0.6, push: 0, side: 'OVER', chance: 0.6, price: -110, need: 0.5238, edge: 0.0762, band: 'BET', mins: 35.1, rate36: 27.9, why: ['27.9 points per 36'], log: [] },
        { pid: '4397020', name: 'Paolo Banchero', team: 'ORL', opp: 'ATL', home: true, pos: 'F', mk: 'reb', line: 7.5, op: -105, up: -115, book: 'fanatics', books: { fanatics: [7.5, -105, -115] }, proj: 8.9, sd: 3.5, pm: 0.6, pb: 0.5, p: 0.56, push: 0, side: 'OVER', chance: 0.56, price: -105, need: 0.512, edge: 0.048, band: 'LEAN', mins: 33.0, rate36: 9.7, why: ['9.7 rebounds per 36'], log: [] } ] } ] };
    await smStore.removeItem('callsheet3.props.v1'); document.getElementById('m-nba').click(); await wait();
    await load(pdoc, 'nba-props-2026-10-27.json');
    o.filePairs = [...document.querySelectorAll('#propsPairs .pk.pair')].map(txt);
    document.querySelector('#propsPairs .pk.pair .takebtn[data-ttake]').click(); await wait();
    const stored1 = JSON.parse(smStore.getItem('callsheet3.props.v1'));
    o.storedPairs = stored1.map(r => r.name + ':' + JSON.stringify(r.pairs || null));
    document.getElementById('m-nba').click(); await wait();
    document.getElementById('boardDate').value = '2026-10-27'; document.getElementById('boardDate').dispatchEvent(new Event('change')); await wait();
    o.board = [...document.querySelectorAll('#taking .pk')].map(txt);
    document.getElementById('takingText').click(); await new Promise(r => setTimeout(r, 250));
    o.said = document.getElementById('saveMsg').innerText.replace(/\s+/g, ' ').trim();
    await load(pdoc, 'nba-props-2026-10-27.json');   // the same file again: the mark rides through
    const stored2 = JSON.parse(smStore.getItem('callsheet3.props.v1'));
    o.storedPairs2 = stored2.map(r => r.name + ':' + JSON.stringify(r.pairs || null));
    o.tabTaking = [...document.querySelectorAll('#propsTaking .pk')].map(txt);
    await load({ format: 'callsheet2.slate', version: 1, date: '2026-10-27', games: [{ sport: 'NBA', gdate: '2026-10-27', away: 'Hawks', home: 'Magic', gameId: '401909900', finals: { fa: '118', fh: '112', f5a: '60', f5h: '55' }, notes: [],
      box: { '3037789': ['Trae Young', 36.2, 28, 3, 11, 4], '4397020': ['Paolo Banchero', 34.0, 22, 9, 4, 1] } }] }, 'nba-grade-2026-10-27.json');
    o.gradedCards = [...document.querySelectorAll('#propsPairs .pk.pair')].map(e => e.className + ' | ' + txt(e));
    o.tabParts = txt(document.querySelector('#calibBox .calib[data-sport="PROPS"] .sides'));
    const taken = document.querySelector('#calibBox .calib[data-sport="TAKEN"]');
    o.took = taken ? [...taken.querySelectorAll(':scope > div')].map(txt) : [];
    document.getElementById('m-nba').click(); await wait();
    o.boardGraded = [...document.querySelectorAll('#taking .pk')].map(txt);
    await smStore.removeItem('callsheet3.props.v1'); document.getElementById('clear').click(); await wait();
    return o;
  });
  chk(pairT.nCards >= 3 && pairT.attrs.every(a => /^\d+\|\d+$/.test(a)) && pairT.open && /^same-game pair · the price agrees$/i.test(pairT.band) && /^.+ (OVER|UNDER) \d+\.5 \w+ \+ .+ (OVER|UNDER) \d+\.5 \w+$/.test(pairT.h3)
      && /^both land \d\d\.\d% · pays \+\d+ \(\d\.\d\d×\) needs \d\d\.\d%$/.test(pairT.pick) && /^76ers @ Knicks · \w{3} \d{1,2} · (two players|two overs on one club|one man, two markets|one man, his points with his threes), measured ×\d\.\d\d · fanatics$/.test(pairT.sub)
      && pairT.tiles.length === 5 && /^Both land=\d\d\.\d%$/.test(pairT.tiles[0]) && /^Parlay price=\+\d+$/.test(pairT.tiles[1]) && /^Edge=\+\d\.\d$/.test(pairT.tiles[2]) && /^Leg 1=\d\d\.\d%$/.test(pairT.tiles[3]) && /^Leg 2=\d\d\.\d%$/.test(pairT.tiles[4])
      && /lands \d\d\.\d% by the sheet and .+ \d\d\.\d%, each the blended chance on its own panel\. .+ so the product carries ×\d\.\d\d: \d\d\.\d% × \d\d\.\d% × \d\.\d\d = \d\d\.\d%.*\. The ticket pays the two prices multiplied, \d\.\d\d × \d\.\d\d = \d\.\d\d×, \+\d+, which needs \d\d\.\d%: the price agrees by \d+\.\d points\. A pushed leg drops out/.test(pairT.how)
      && pairT.legs.length === 2 && pairT.legs.every(l => /^LEG [12] · .+ (OVER|UNDER) \d+\.5 \w+ · [A-Z] (PHI|NYK) · (starter|bench) \|\| Chance,Price,Edge,Projection,Minutes,Usage \|\| Moves it: .+ \|\| Open this prop \| true$/.test(l))
      && !pairT.nav.hidden && /^1 of \d pairs$/.test(pairT.nav.pos) && pairT.nav.prevOff && !pairT.nav.nextOff && /^take this pair$/i.test(pairT.bigBtn) && pairT.h3next !== pairT.h3 && /^2 of \d pairs$/.test(pairT.posNext) && pairT.h3back === pairT.h3
      && /^.+ \| (LEAN|BET|no edge) \| \d of 7$/i.test(pairT.legPanel) && pairT.closed && pairT.fromTaking.toLowerCase() === ('Same-game pair · the price agrees | ' + pairT.h3).toLowerCase(),
      'pairs: a same-game pair card opens its own panel with the ticket\'s band, both legs, the chance, the parlay price and what it needs, five tiles, the arithmetic of the chance with the measured factor, each leg\'s numbers with a button to its own panel, and Previous / Next across the night\'s tickets', JSON.stringify(pairT).slice(0, 1500));
  chk(pairT.takeOn && pairT.cardTaking === 1 && pairT.cardBtnOn === 1 && pairT.takingList.length === 1 && /^TAKING · SAME-GAME PAIR · 76ers @ Knicks · the price agrees .+ \+ .+ both land \d\d\.\d% · pays \+\d+ .+Taking$/i.test(pairT.takingList[0]) && pairT.takingCount === '1 marked' && !pairT.takingHead
      && pairT.unmarked.dlg && pairT.unmarked.taking === 0 && pairT.unmarked.list === 0 && pairT.unmarked.head
      && pairT.filePairs.length === 1 && /^PAIR #1 · Hawks @ Magic · the price agrees Trae Young OVER 24\.5 points \+ Paolo Banchero OVER 7\.5 rebounds both land 33\.6% · pays \+27\d \(3\.7\d×\) needs 26\.\d% .+two players, measured ×1\.00 TAKE$/.test(pairT.filePairs[0])
      && pairT.storedPairs.join(';') === 'Trae Young:["2026-10-27|4397020|reb"];Paolo Banchero:["2026-10-27|3037789|pts"]' && pairT.storedPairs2.join(';') === pairT.storedPairs.join(';')
      && pairT.board.length === 2 && /^TAKING · SAME-GAME PAIR · Hawks @ Magic · the price agrees Trae Young OVER 24\.5 points \+ Paolo Banchero OVER 7\.5 rebounds both land 33\.6%/.test(pairT.board[0]) && /^TONIGHT 1 bet marked none graded yet · one unit each 0 on the card, 0 from the simulation, 0 props, 1 same-game pair$/.test(pairT.board[1])
      && /Copied the bets you are taking|the text is below/.test(pairT.said) && (!/the text is below/.test(pairT.said) || /1\. SAME-GAME PAIR Trae Young OVER 24\.5 points \+ Paolo Banchero OVER 7\.5 rebounds \+27\d · both land 33\.6% needs 26\.\d% · Hawks @ Magic/.test(pairT.said))
      && pairT.tabTaking.length === 1 && /^TAKING · SAME-GAME PAIR/.test(pairT.tabTaking[0])
      && pairT.gradedCards.length === 1 && /^pk pair agrees win taking \| PAIR #1 .+ WIN .+ TAKEN$/.test(pairT.gradedCards[0]) && /same-game pairs 1-0 \+2\.7u · pairs taken 1-0 \+2\.7u/.test(pairT.tabParts)
      && pairT.took.some(t => /^same-game pairs taken 1-0 says 33\.6% · does 100\.0% \(±50\.0\) · \+2\.7\du$/i.test(t)) && pairT.boardGraded.length === 2 && /WIN/.test(pairT.boardGraded[0]) && /graded 1-0 · \+2\.7\du at one unit each/.test(pairT.boardGraded[1]),
      'pairs: Take on the pair\'s panel marks the ticket on both legs (the card lights, its button is on, Taking lists it with a count, the card\'s button unmarks it without opening); on a real file the mark lists on the board\'s Taking tonight with the summary, copies as text, rides through the file loaded again, and once the night grades the ticket shows WIN with a TAKEN chip, the tab\'s record says pairs taken 1-0 and What you took carries a Same-game pairs taken tile at the parlay price',
      JSON.stringify({ takeOn: pairT.takeOn, cardTaking: pairT.cardTaking, cardBtnOn: pairT.cardBtnOn, takingList: pairT.takingList, count: pairT.takingCount, unmarked: pairT.unmarked, filePairs: pairT.filePairs, stored: pairT.storedPairs, stored2: pairT.storedPairs2, board: pairT.board, said: pairT.said.slice(0, 200), tabTaking: pairT.tabTaking, graded: pairT.gradedCards, parts: pairT.tabParts, took: pairT.took, boardGraded: pairT.boardGraded }).slice(0, 2500));

  // ---- 26 Oct 2026: tonight on your phone -- the Phone QR button makes a code carrying the night's picks; an independent decoder (jsQR,
  //      tools_vendor) reads it back off the drawn modules; the phone sheet m.html renders it, view only ----
  const phoneT = await pg.evaluate(async () => {
    const wait = (ms) => new Promise(r => setTimeout(r, ms || 100));
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    await smStore.removeItem('callsheet3.card.v1'); await smStore.removeItem('callsheet3.props.v1');
    document.getElementById('clear').click(); document.getElementById('m-nba').click(); await wait();
    set('gdate', '2026-11-14'); document.getElementById('example').click(); await wait(); set('gdate', '2026-11-14'); await wait();
    document.getElementById('add').click(); await wait();
    document.getElementById('boardDate').value = '2026-11-14'; document.getElementById('boardDate').dispatchEvent(new Event('change')); await wait();
    document.querySelector('#nbaSimPanel .takebtn[data-stake*="|own|total|"]').click(); await wait();
    document.querySelector('#board tbody tr .takebtn').click(); await wait();
    const hidden0 = document.getElementById('phoneDlg').hidden;
    document.getElementById('phone').click(); await wait(700);
    const open = !document.getElementById('phoneDlg').hidden, link = (document.querySelector('#phoneBody a') || {}).href || '';
    const note = (document.querySelector('#phoneBody .note') || {}).innerText || '', dim = (document.querySelector('#phoneBody .note.dim') || {}).innerText || '';
    const d = (document.querySelector('#phoneBody svg path') || { getAttribute: () => '' }).getAttribute('d') || '';
    const pts = [...d.matchAll(/M(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)[hl]/g)].map(m => [Math.round(((+m[1]) - 6) / 4), Math.round(((+m[2]) - 6) / 4)]);
    const n = pts.length ? Math.max(...pts.map(p => p[0])) + 1 : 0, mods = [];
    for (let r = 0; r < n; r++) { const row = []; for (let c = 0; c < n; c++) row.push(0); mods.push(row); }
    pts.forEach(p => { mods[p[1]][p[0]] = 1; });
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })); await wait();
    const closed = document.getElementById('phoneDlg').hidden && !document.body.classList.contains('noscroll');
    return { hidden0, open, link, note: note.replace(/\s+/g, ' ').trim(), dim, n, mods, closed };
  });
  let decoded = null;
  try {
    const jsQR = require('./tools_vendor/jsQR.js');
    const scale = 4, q = 4, size = (phoneT.n + 2 * q) * scale, data = new Uint8ClampedArray(size * size * 4);
    for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
      const r = Math.floor(y / scale) - q, c = Math.floor(x / scale) - q, dark = r >= 0 && c >= 0 && r < phoneT.n && c < phoneT.n && phoneT.mods[r][c];
      const v = dark ? 0 : 255, i = (y * size + x) * 4; data[i] = v; data[i + 1] = v; data[i + 2] = v; data[i + 3] = 255;
    }
    const res = jsQR(data, size, size); decoded = res ? res.data : null;
  } catch (e) { decoded = 'decoder error: ' + e.message; }
  chk(phoneT.hidden0 && phoneT.open && /\/m\.html#z[A-Za-z0-9_-]+$/.test(phoneT.link) && phoneT.n >= 57 && phoneT.n % 4 === 1 && decoded === phoneT.link
      && /^Point your phone's camera at the code and open the link\. It shows \d+ lines: the bets you are taking, the parlay four, the best straight bets, the likeliest sides, the best props and the simulation's calls, view only\./.test(phoneT.note)
      && /nothing is uploaded/.test(phoneT.note) && /signed in to claude\.ai/.test(phoneT.note) && new RegExp(phoneT.n + ' modules a side').test(phoneT.dim) && phoneT.closed,
      'phone: the Phone QR button draws a code whose link carries the night\'s picks deflated into the hash of m.html, an independent decoder reads the very link back off the drawn modules, the note says what is in it and how it works, and Escape closes it',
      JSON.stringify({ hidden0: phoneT.hidden0, open: phoneT.open, link: phoneT.link.slice(0, 90), n: phoneT.n, decoded: decoded === phoneT.link ? 'matches' : String(decoded).slice(0, 80), note: phoneT.note.slice(0, 160), dim: phoneT.dim, closed: phoneT.closed }));
  // the phone sheet renders the code, view only
  const sheetErrs = [];
  const sheetCtx = await pg.context().browser().newContext({ viewport: { width: 390, height: 844 } }), sheet = await sheetCtx.newPage();
  sheet.on('pageerror', e => sheetErrs.push(e.message));
  await sheet.goto(phoneT.link); await sheet.waitForTimeout(600);
  const sheetT = await sheet.evaluate(() => ({ text: document.body.innerText.replace(/\s+/g, ' ').trim(), cards: document.querySelectorAll('.pk').length, takes: document.querySelectorAll('.pk.take').length, inputs: document.querySelectorAll('input, button, select, textarea').length, wide: document.documentElement.scrollWidth <= 390 }));
  await sheetCtx.close();
  chk(sheetErrs.length === 0 && /^The Super Model Sat, Nov 14 · made \d{1,2}:\d\d [AP]M · view only TAKING TONIGHT 2 TAKING · NBA Knicks ML 66\.6% · [-−]198 needs 66\.4% 76ers @ Knicks · Moneyline TAKING · NBA · SIMULATION Total UNDER 231\.5 7\d\.\d% · worth 5\d% · [-−]110 needs 52\.4% 76ers @ Knicks · the simulation, the sim's own view THE PARLAY FOUR 1 /.test(sheetT.text)
      && /LIKELIEST AT ANY PRICE 1 /.test(sheetT.text) && /THE SIMULATION'S CALLS, BET OR BETTER \d /.test(sheetT.text) && /View only: the card lives in the desktop browser\./.test(sheetT.text) && sheetT.takes === 2 && sheetT.cards >= 5 && sheetT.inputs === 0 && sheetT.wide,
      'phone sheet: m.html unpacks the code on a phone-width screen with no script errors and lists the bets marked Taking first, then the parlay four, the likeliest sides and the simulation\'s calls, with nothing to type into and no sideways scroll', JSON.stringify({ errs: sheetErrs, text: sheetT.text.slice(0, 500), cards: sheetT.cards, takes: sheetT.takes, inputs: sheetT.inputs, wide: sheetT.wide }));
  await pg.evaluate(async () => { await smStore.removeItem('callsheet3.card.v1'); await smStore.removeItem('callsheet3.props.v1'); document.getElementById('clear').click(); });

  // ---- the build stamp ------------------------------------------------------------
  // ---- the simulation (25 Oct 2026): the card on the example, the block stored with the row, the record once graded ----
  await pg.evaluate(async () => { await smStore.removeItem('callsheet3.card.v1'); }); await pg.reload(); await pg.waitForTimeout(300); await pg.evaluate(() => smStore.ready);
  const simT = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 80));
    document.getElementById('clear').click(); document.getElementById('m-nba').click(); await wait();
    document.getElementById('gdate').value = '2026-11-10';
    document.getElementById('example').click(); await wait();
    const panel = document.getElementById('nbaSimPanel').innerText.replace(/\s+/g, ' ').trim();
    const tiles = [...document.querySelectorAll('#nbaSimPanel .simtile')].map(t => t.querySelector('.k').textContent + '=' + t.querySelector('.v').textContent);
    const meta = (document.querySelector('#nbaSimPanel .simmeta') || {}).innerText || '';
    const medians = (document.querySelector('#nbaSimPanel table.simq') || {}).innerText || '';
    const rows = [...document.querySelectorAll('#nbaSimPanel .simtab tbody tr')].map(tr => tr.innerText.replace(/\s+/g, ' ').trim());
    const chips = [...document.querySelectorAll('#nbaSimPanel .simchip')].map(e => e.className + '|' + e.textContent.replace(/\s+/g, ' ').trim());
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    set('line', '245.5'); await wait();
    const moved = document.querySelector('#nbaSimPanel .simtab tbody tr').innerText.replace(/\s+/g, ' ').trim();
    set('line', '231.5'); await wait();
    document.getElementById('add').click(); await wait();
    const stored = JSON.parse(smStore.getItem('callsheet3.card.v1')).find(r => /76ers @ Knicks/.test(r.matchup));
    return { panel: panel.slice(0, 420), tiles, meta: meta.replace(/\s+/g, ' ').trim(), medians: medians.replace(/\s+/g, ' ').trim(), rows, chips, moved, hasSim: !!(stored && stored.inputs.nbasim && stored.inputs.nbasim.length > 1000) };
  });
  // graded, with the book's team totals on the row's odds JSON (26 Oct 2026): the record takes them too
  await pg.evaluate(async () => { const c = JSON.parse(smStore.getItem('callsheet3.card.v1')); c.forEach(r => { if (/76ers @ Knicks/.test(r.matchup)) { r.finals = { fa: '112', fh: '121', f5a: '55', f5h: '60' };
    r.inputs.odds = JSON.stringify({ total: {}, ml: {}, spread: {}, book: 'fanatics', team: { AWAY: { OVER: [['fanatics', -110, 113.5], ['fanatics', 140, 117.5], ['draftkings', -112, 113.5]], UNDER: [['fanatics', -110, 113.5], ['fanatics', -170, 117.5], ['draftkings', -108, 113.5]] },
                                                                                                    HOME: { OVER: [['fanatics', -115, 123.5]], UNDER: [['fanatics', -105, 123.5]] } } }); } }); await smStore.setItem('callsheet3.card.v1', JSON.stringify(c)); });
  await pg.reload(); await pg.waitForTimeout(300); await pg.evaluate(() => smStore.ready);
  const simRec = await pg.evaluate(() => { const rec = document.querySelector('#calibBox .simrec'); return { has: !!rec, text: rec ? rec.innerText.replace(/\s+/g, ' ').trim().slice(0, 300) : '', rows: rec ? [...rec.querySelectorAll('.simrectab:not(.gaptab) tbody tr')].map(tr => tr.innerText.replace(/\s+/g, ' ').trim()) : [],
    gap: rec ? [...rec.querySelectorAll('.gaptab tbody tr')].map(tr => tr.innerText.replace(/\s+/g, ' ').trim()) : [] }; });
  // the gap rule on the card: the Knicks' 123.5 sits 5 above the implied (231.5 + 5.5) / 2 = 118.5, so UNDER by the rule; the 76ers' 113.5 sits half a point over 113, no call
  // (26 Oct 2026: the band comes from the worth now, so the anchored home team total at 123.5 reads a band and the own view's does not; 121 scored, the under wins)
  const gapCard = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 80));
    document.getElementById('m-nba').click(); await wait();
    const row = JSON.parse(smStore.getItem('callsheet3.card.v1')).find(r => /76ers @ Knicks/.test(r.matchup));
    const btn = document.querySelector('#card tr[data-id="' + row.id + '"] button.fill, #card [data-id="' + row.id + '"] .fill, button[data-fill="' + row.id + '"]');
    if (btn) { btn.click(); await wait(); }
    else { document.getElementById('odds').value = row.inputs.odds; document.getElementById('line').value = '231.5'; document.getElementById('sp').value = '-5.5'; document.getElementById('nbasim').value = row.inputs.nbasim; document.getElementById('away').value = '76ers'; document.getElementById('home').value = 'Knicks'; document.getElementById('line').dispatchEvent(new Event('input', { bubbles: true })); await wait(); }
    const rows = [...document.querySelectorAll('#nbaSimPanel .simtab tbody tr')].map(tr => tr.innerText.replace(/\s+/g, ' ').trim());
    document.getElementById('clear').click(); await wait();
    return rows.slice(4);
  });
  await pg.evaluate(async () => { await smStore.removeItem('callsheet3.card.v1'); }); await pg.reload(); await pg.waitForTimeout(300); await pg.evaluate(() => smStore.ready);
  chk(simT.tiles.length === 4 && /^Total=\d+$/.test(simT.tiles[0]) && /^Margin=Knicks by \d+\.\d$/.test(simT.tiles[1]) && /^Knicks wins=\d+%$/.test(simT.tiles[2]) && /^Overtime=\d\.\d%$/.test(simT.tiles[3])
      && /^3,000 games, the sim's own view\. Anchored to DraftKings's 231\.5 \/ -5\.5 for the market view\.$/.test(simT.meta)
      && /^Medians, anchored to the market Q1 Q2 Q3 Q4 1H 2H 76ers Knicks the fourth \d+\.\d% of the game( \d+){8}$/i.test(simT.medians)
      && simT.rows.length === 6 && /^Total 231\.5 (OVER|UNDER) \d+%/.test(simT.rows[0]) && /^First half 115\.5 (OVER|UNDER) \d+%/.test(simT.rows[1]) && /^Spread \(home\) -5\.5 (HOME|AWAY) \d+%/.test(simT.rows[2]) && /^Moneyline (HOME|AWAY) \d+%.*the own view's$/.test(simT.rows[3])
      && /^76ers team total no line on the row \(the odds run brings it\) — —$/.test(simT.rows[4]) && /^Knicks team total no line on the row/.test(simT.rows[5])
      && simT.chips.length === 7 && simT.chips.every(c => /^simchip sim(no|lean|bet|strong)\|(OVER|UNDER|HOME|AWAY) \d+%$/.test(c)) && simT.moved !== simT.rows[0] && /UNDER [89]\d%/.test(simT.moved) && simT.hasSim,
      'nba sim: the Simulation card reads the example\'s runs, lists every market with the own and the anchored chance for the line on the row, follows the line when it is typed, and the block rides with the row', JSON.stringify({ panel: simT.panel, rows: simT.rows, moved: simT.moved, chips: simT.chips.length, has: simT.hasSim }));
  chk(simRec.has && /^SIMULATION · says against does, every call at LEAN or better The sim's own view/.test(simRec.text) && simRec.rows.length >= 1
      && simRec.rows.every(r => /^(Total|First half|Spread|Moneyline|Away team total|Home team total) (STRONG|BET|LEAN) [01]-[01] \d+\.\d% (0|100)\.0% [+-]\d+\.\du$/.test(r))
      && simRec.rows.some(r => /^Home team total (STRONG|BET|LEAN) 1-0 /.test(r)) && /Anchored to the market MARKET BAND RECORD SAYS DOES UNITS Home team total/.test(simRec.text) && !/The sim's own view[^]*Home team total[^]*Anchored/.test(simRec.text)
      && simRec.gap.length === 1 && /^Home team total 1-0 100\.0% \+[01]\.\du 62% under above the number/.test(simRec.gap[0]),
      'nba sim: once the row grades, the record block keeps the calls whose worth reads LEAN or better, says against does by view, market and band, the anchored home team total among them and the own view\'s not, and the gap rule\'s own tally (the Knicks\' 123.5 five above the implied 118.5, under called, 121 scored: a win)', JSON.stringify(simRec));
  chk(gapCard.length === 2 && /^76ers team total 113\.5 fanatics -110\/-110 implied 113, gap \+0\.5 · inside a point, no call/.test(gapCard[0]) && /^Knicks team total 123\.5 fanatics -115\/-105 implied 118\.5, gap \+5 · UNDER by the gap rule/.test(gapCard[1]),
      'nba sim: the Simulation card shows each team total\'s implied number and gap, and the gap rule\'s call when it is a point or more', JSON.stringify(gapCard));

  // ---- the store (25 Oct 2026): the card, the props and the slate live in IndexedDB, past localStorage's 10 MB ----
  await fill(CASES[0].sport, CASES[0].inputs);
  const store1 = await pg.evaluate(async () => {
    await smStore.ready;
    const before = { backend: smStore.backend(), why: smStore.why(), keys: Object.keys(localStorage) };
    document.getElementById('add').click(); await new Promise(r => setTimeout(r, 80));
    const row = smStore.getItem('callsheet3.card.v1');
    // a props list far past the localStorage limit saves through the store
    const big = JSON.stringify(Array.from({ length: 3000 }, (_, i) => ({ id: i + 1, gdate: '2026-10-24', game: 'Heat @ Hornets', away: 'Heat', home: 'Hornets', aab: 'MIA', hab: 'CHA', pid: String(i), name: 'Player ' + i, team: 'MIA', opp: 'CHA', pos: 'G', mk: 'pts', line: 20.5, op: -110, up: -110, book: 'fanatics', books: {}, proj: 22.1, sd: 7, pm: 0.58, pb: 0.5, p: 0.55, push: 0, side: 'OVER', chance: 0.55, price: -110, need: 0.524, edge: 0.026, band: 'LEAN', mins: 30, rate36: 26, why: ['x'.repeat(1800)], log: [] })));
    await smStore.setItem('callsheet3.props.v1', big);
    // the move: the card goes back to where the old page kept it, and the database forgets it
    await smStore.removeItem('callsheet3.card.v1');
    localStorage.setItem('callsheet3.card.v1', row);
    const inLocal = window.localStorage.getItem('callsheet3.props.v1');   // the browser's own store, on purpose: the key must not be there
    return { before, backend: smStore.backend(), why: smStore.why(), rows: JSON.parse(row).length, bigLen: big.length, propsInLocal: inLocal === null ? null : inLocal.length, keys: Object.keys(localStorage) };
  });
  await pg.reload(); await pg.waitForTimeout(300);
  const store2 = await pg.evaluate(async () => {
    await smStore.ready;
    const p = smStore.getItem('callsheet3.props.v1'), c = JSON.parse(smStore.getItem('callsheet3.card.v1') || '[]');
    const lc = window.localStorage.getItem('callsheet3.card.v1'), lp = window.localStorage.getItem('callsheet3.props.v1');   // the browser's own store, on purpose
    return { pLen: p ? p.length : 0, cardRows: c.length, localCard: lc === null ? null : lc.length, localProps: lp === null ? null : lp.length, keys: Object.keys(localStorage), saveState: document.getElementById('saveState').textContent };
  });
  chk(store1.backend === 'indexeddb' && store1.rows >= 1 && store1.propsInLocal === null, 'store: the page keeps the card and the props in IndexedDB, not localStorage', JSON.stringify(store1));
  chk(store2.pLen === store1.bigLen && store2.localProps === null, 'store: a props list far past the localStorage limit saves and comes back after a reload', JSON.stringify({ pLen: store2.pLen, bigLen: store1.bigLen }));
  chk(store2.cardRows === store1.rows && store2.localCard === null && !/not storing/.test(store2.saveState), 'store: a card the old page left in localStorage moves to the database on load and leaves localStorage', JSON.stringify(store2));
  await pg.evaluate(() => smStore.clear()); await pg.reload(); await pg.waitForTimeout(300);

  // ---- 28 Oct 2026: the three voices on the total -- the sim's own view and the crew on the same side, the sheet not against it: BET on the Simulation card and the board, takeable, with its own record line ----
  const agreeT = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 90));
    const txt = e => (e ? e.innerText : '').replace(/\s+/g, ' ').trim();
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    await smStore.removeItem('callsheet3.card.v1'); document.getElementById('clear').click(); document.getElementById('m-nba').click(); await wait();
    const load = async (doc, fname) => { const dt = new DataTransfer(); dt.items.add(new File([JSON.stringify(doc)], fname, { type: 'application/json' })); const inp = document.getElementById('slateFile'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true })); await wait(); };
    const hist = (lo, mean, sd) => { const c = []; for (let v = lo; v <= lo + 100; v++) c.push(Math.round(10000 * Math.exp(-((v - mean) ** 2) / (2 * sd * sd)))); return { lo, c }; };
    const sim = { v: 1, runs: 1000, own: { total: hist(170, 230, 15), h1: hist(80, 115, 10), h2: hist(80, 115, 10), q: [hist(30, 57, 7), hist(30, 57, 7), hist(30, 57, 7), hist(30, 57, 7)], margin: hist(-50, 2, 12), away: hist(80, 114, 11), home: hist(80, 116, 11), ot: 0.04 }, mkt: null, anchor: null, ft_factor: 1.0,
                  shrink: { total: 0.05, h1: 0.1, spread: 0.0, ml: 0.97, team: 1.5, team_away: 0.3, team_own: 0.3, quarter: 0.1 }, bands: [[0.7, 'STRONG'], [0.65, 'BET'], [0.6, 'LEAN']] };
    const refs = { lg: [2462, 44.0, 228.8], r: { 'Scott Foster': [118, 46.2, 229.1, 66, 41, 4, 2], 'Marc Davis': [102, 44.8, 230.3, 71, 51, 0, 0], 'Tony Brothers': [95, 43.1, 226.0, 56, 54, 3, 3] } };
    // the game on the card first (a slate fills a row, it does not add one), then the slate brings the crew, the table and the runs
    set('gdate', '2026-11-12'); set('away', 'Kings'); set('home', 'Spurs'); set('line', '222.5'); set('op', '-110'); set('up', '-110'); await wait();
    document.getElementById('add').click(); await wait();
    await load({ format: 'callsheet2.slate', version: 1, date: '2026-11-12', games: [{ sport: 'NBA', gdate: '2026-11-12', away: 'Kings', home: 'Spurs', notes: [], inputs: { ncrew: 'Scott Foster, Marc Davis, Tony Brothers', nbarefs: JSON.stringify(refs), nbasim: JSON.stringify(sim) } }] }, 'nba-slate-2026-11-12.json');
    document.getElementById('boardDate').value = '2026-11-12'; document.getElementById('boardDate').dispatchEvent(new Event('change')); await wait();
    const headHidden = document.getElementById('agreeHead').hidden;
    const cards = [...document.querySelectorAll('#agree .pk.agree')].map(e => ({ n1: txt(e.querySelector('.n1')), n2: txt(e.querySelector('.n2')), n3: txt(e.querySelector('.n3')), n4: txt(e.querySelector('.n4')).slice(0, 40), take: !!e.querySelector('.takebtn[data-stake$="|agree|total|OVER"]') }));
    // the card opens the row into the form: the Simulation card's block reads BET with a Take of its own
    document.querySelector('#agree .pk.agree .n2').click(); await wait();
    const voices = document.querySelector('#nbaVoices .voices');
    const block = { cls: voices ? voices.className : '', badge: txt(voices && voices.querySelector('.vbadge')), line: txt(voices && voices.querySelector('.vline')), take: !!(voices && voices.querySelector('.vtake .takebtn[data-stake$="|agree|total|OVER"]')),
                    color: voices ? getComputedStyle(voices.querySelector('.vbadge')).backgroundColor : '', simchips: document.querySelectorAll('#nbaSimPanel .simchip').length };
    // taken from the block: the row carries the mark at the row's price, Taking tonight lists it, the board's card shows it taken
    voices.querySelector('.vtake .takebtn').click(); await wait();
    const row = JSON.parse(smStore.getItem('callsheet3.card.v1')).find(r => /Kings @ Spurs/.test(r.matchup));
    const take = (row.simTakes || []).map(t => t.view + '|' + t.key + '|' + t.side + '|' + t.line + '|' + t.price + '|' + t.band + '|' + t.pick + '|' + (t.p === null ? 'null' : (+t.p).toFixed(2)) + '|' + t.worth);
    const taking = txt(document.getElementById('taking')), boardTake = txt(document.querySelector('#agree .pk.agree .n5'));
    // graded: the record keeps the rule's own line, the card shows the result
    await load({ format: 'callsheet2.slate', version: 1, date: '2026-11-12', games: [{ sport: 'NBA', gdate: '2026-11-12', away: 'Kings', home: 'Spurs', finals: { fa: '118', fh: '121', f5a: '58', f5h: '60' }, close: { ctot: '222.5' }, notes: [] }] }, 'nba-grade-2026-11-12.json');
    const rec = txt(document.querySelector('.agreetab')), recHead = txt([...document.querySelectorAll('.simrecview')].find(e => /agreement rule/i.test(e.textContent)));
    const graded = txt(document.querySelector('#agree .pk.agree .n3'));
    // a split: the example's sim leans under while its crew leans over, so no rule, and the words say so
    document.getElementById('clear').click(); document.getElementById('m-nba').click(); await wait();
    document.getElementById('gdate').value = '2026-11-10'; document.getElementById('example').click(); await wait();
    const split = { cls: (document.querySelector('#nbaVoices .voices') || {}).className || '', badge: txt(document.querySelector('#nbaVoices .vbadge')), line: txt(document.querySelector('#nbaVoices .vline')) };
    document.getElementById('clear').click(); await wait();
    await smStore.removeItem('callsheet3.card.v1');
    return { headHidden, cards, block, take, taking, boardTake, rec, recHead, graded, split };
  });
  chk(agreeT.headHidden === false && agreeT.cards.length === 1 && /^AGREEMENT · 2 OF 3 · BET BY THE RULE$/i.test(agreeT.cards[0].n1) && /^TOTAL OVER 222\.5$/i.test(agreeT.cards[0].n2)
      && /^the sheet silent \((OVER|UNDER) 50\.0%, no bet\) · the sim OVER 6\d% · the crew leans OVER \(z \+4\.4\) · -110$/i.test(agreeT.cards[0].n3) && /^Kings @ Spurs · the sim's own view/.test(agreeT.cards[0].n4) && agreeT.cards[0].take
      && agreeT.block.cls === 'voices fires' && /^BET · 2 OF 3$/i.test(agreeT.block.badge) && /2 of 3 on the OVER, none against: BET by the agreement rule\.$/i.test(agreeT.block.line) && agreeT.block.take && agreeT.block.color !== 'rgba(0, 0, 0, 0)' && agreeT.block.simchips === 7
      && agreeT.take.length === 1 && /^agree\|total\|OVER\|222\.5\|-110\|agreement\|Total OVER 222\.5\|0\.6\d\|null$/.test(agreeT.take[0]) && /Total OVER 222\.5 -110 · the simulation, the agreement rule, the sim and the crew: 6\d% · agreement · Kings @ Spurs/i.test(agreeT.taking) && !/worth/i.test(agreeT.taking) && /TAKING/i.test(agreeT.boardTake)
      && /^Voices Record Does Units Two seasons said 2 of 3: the sim and the crew, the sheet silent 1-0 100\.0% \+0\.9u 134-98 \(57\.8%\), \+23\.8u$/i.test(agreeT.rec) && /scored, BET/i.test(agreeT.recHead) && /WIN$/i.test(agreeT.graded)
      && agreeT.split.cls === 'voices' && /^NO RULE$/i.test(agreeT.split.badge) && /the sim UNDER 7\d% · the crew leans OVER \(z \+4\.4\) — (split, 2 on the (OVER|UNDER) with one against: no rule|no two voices on a side: no rule)\.$/i.test(agreeT.split.line),
      'agreement: a basketball total with the sim\'s own view and the crew on the same side and the sheet silent reads BET on the board\'s Agreement section and on the Simulation card\'s three-voices block in green, takes from either (the mark on the row at the row\'s price, listed under Taking tonight without a worth), grades on the rule\'s own record line, and a split (the example: the sim under, the crew over) reads no rule', JSON.stringify(agreeT).slice(0, 1800));

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
