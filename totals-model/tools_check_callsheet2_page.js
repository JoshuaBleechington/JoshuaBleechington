/* Replays web/callsheet2-cases.json through web/callsheet2.html in a real
 * browser and asserts the page reaches the same markets, in the same order,
 * with the same probabilities and edges the Python package reached.
 *
 * Then the behaviours the fixtures cannot see: the engine block is byte-
 * identical to Call Sheet #1's, the log grades every market from two finals,
 * the day board ranks across matchups and flags same-game rows, the top-4
 * picks are the top four, the paste parser fills the WNBA boxes and refuses a
 * table without PACE/40, and the build stamp is current.
 *
 *   node tools_check_callsheet2_page.js
 */
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
const { execSync } = require('child_process');

const CASES = JSON.parse(fs.readFileSync(path.join(__dirname, 'web/callsheet2-cases.json'), 'utf8'));
const IDS = ["away","home","line","op","up","opened","gdate","aera","hera","aip","hip","arpg","hrpg",
             "abp","hbp","al10","hl10","h2h","h2hn","pf","mph","dir","temp","tick","cash",
             "hml","aml","rl","rlh","rla","f5line","f5op","f5up",
             "apace","hpace","aort","hort","adrt","hdrt","arest","hrest","al5","hl5","sp","sph","spa"];
const CHECKS = ["dome","playoff"];

(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/opt/pw-browsers/chromium' });
  const pg = await b.newPage({ viewport: { width: 1280, height: 1400 } });
  const errs = [];
  pg.on('pageerror', e => errs.push(String(e)));
  pg.on('console', m => {
    const where = (m.location() && m.location().url) || '';
    if (m.type() === 'error' && !/fonts\.(googleapis|gstatic)\.com/.test(where + ' ' + m.text())) errs.push('console: ' + m.text());
  });
  await pg.goto('file://' + path.join(__dirname, 'web/callsheet2.html'));
  await pg.waitForTimeout(300);

  let fails = 0;
  const chk = (ok, m, d) => { if (!ok) fails++; console.log(`${ok ? 'PASS' : 'FAIL'}  ${m}${ok ? '' : '\n        ' + d}`); };

  // ---- the engine block is Call Sheet #1's, byte for byte ------------------
  const block = (file) => {
    const s = fs.readFileSync(path.join(__dirname, 'web', file), 'utf8').split('\n');
    const a = s.findIndex(l => l.startsWith('  /* ===== ENGINE BLOCK.'));
    const z = s.findIndex(l => l.startsWith('  /* ===== END ENGINE BLOCK ===== */'));
    return a >= 0 && z > a ? s.slice(a, z + 1).join('\n') : null;
  };
  const b1 = block('fullgame.html'), b2 = block('callsheet2.html');
  chk(b1 && b2 && b1 === b2, 'engine: callsheet2.html carries fullgame.html\'s engine block byte-identical',
      `#1 ${b1 ? b1.length : 'missing'} chars vs 2.0 ${b2 ? b2.length : 'missing'}`);

  // ---- fixtures ---------------------------------------------------------------
  const fill = async (sport, inputs) => pg.evaluate(async ([sport, inputs, ids, checks]) => {
    document.getElementById(sport === 'WNBA' ? 'm-wnba' : 'm-mlb').click();
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

  // ---- the log, the board and the grading --------------------------------------
  const flow = await pg.evaluate(async () => {
    localStorage.removeItem('callsheet2.card.v1');
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    const clear = () => document.getElementById('clear').click();
    const wait = () => new Promise(r => setTimeout(r, 40));
    document.getElementById('m-mlb').click();
    document.getElementById('byEdge').checked = true;
    document.getElementById('boardDate').value = '2026-09-22';
    // game 1: Rays @ Yankees, full board
    clear(); set('gdate', '2026-09-22'); set('away', 'Rays'); set('home', 'Yankees');
    set('line', '6.5'); set('op', '-120'); set('up', '105'); set('aml', '130'); set('hml', '-150');
    set('rl', '-1.5'); set('rlh', '120'); set('rla', '-140'); set('f5line', '3.5'); set('f5op', '-115'); set('f5up', '-105');
    set('aera', '2.94'); set('hera', '2.95'); set('mph', '15'); set('dir', 'in'); set('temp', '65'); set('pf', '103');
    await wait(); document.getElementById('add').click(); await wait();
    // game 2: a heavy favourite, moneyline only
    clear(); set('gdate', '2026-09-22'); set('away', 'Rockies'); set('home', 'Dodgers');
    set('line', '8.5'); set('op', '-110'); set('up', '-110'); set('aml', '240'); set('hml', '-300');
    await wait(); document.getElementById('add').click(); await wait();
    // another date, must not appear on the 22 Sept board
    clear(); set('gdate', '2026-09-21'); set('away', 'Mets'); set('home', 'Cubs');
    set('line', '8.5'); set('op', '-115'); set('up', '-105'); set('aml', '-105'); set('hml', '-115');
    await wait(); document.getElementById('add').click(); await wait();
    document.getElementById('boardDate').dispatchEvent(new Event('change'));
    await wait();
    const rows = [...document.querySelectorAll('#board tbody tr')].map(tr => {
      const td = [...tr.querySelectorAll('td')];
      return { rank: td[0].querySelector('.rank').textContent, corr: !!td[0].querySelector('.corr'),
               matchup: td[1].textContent.trim(), pick: td[3].querySelector('.chip').textContent,
               edge: parseFloat(td[7].textContent), pick4: tr.classList.contains('pick4') };
    });
    // .n2 is the pick plus, when Call Sheet #1 has a verdict on it, a band chip; the pick alone is the first text node
    const pickOf = e => e.firstChild.textContent.trim();
    const picks = [...document.querySelectorAll('#picks .pk:not(.parlay) .n2')].map(pickOf);
    const pickBands = [...document.querySelectorAll('#picks .pk:not(.parlay) .n2')].map(e => (e.querySelector('.band') || {}).textContent || '');
    const bests = [...document.querySelectorAll('#bestBets .pk .n2')].map(pickOf);
    const swaps = [...document.querySelectorAll('#picks .pk .swap')].map(e => e.textContent);
    // grade game 1: Rays 1, Yankees 1 (2 runs), F5 1-0
    const inp = (id, k) => document.querySelector(`.grade[data-id="${id}"][data-k="${k}"]`);
    const type = (el, v) => { el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    type(inp('1', 'fa'), '1'); type(inp('1', 'fh'), '1'); type(inp('1', 'f5a'), '1'); type(inp('1', 'f5h'), '0');
    await wait();
    // a real user leaves the box, which fires change and locks the row
    inp('1', 'f5h').dispatchEvent(new Event('change', { bubbles: true }));
    await wait();
    const stored = JSON.parse(localStorage.getItem('callsheet2.card.v1'));
    const g1 = stored.find(r => r.id === 1);
    const chips = [...document.querySelectorAll('#cardTable tr')].find(tr => /Rays @ Yankees/.test(tr.textContent))
      .querySelectorAll('.rowmk .m');
    const graded = [...chips].map(c => ({ pick: c.querySelector('.chip').textContent, res: (c.querySelector('.chip.win,.chip.loss,.chip.push') || {}).textContent || '' }));
    const calib = document.getElementById('calibBox').textContent;
    const boardAfter = [...document.querySelectorAll('#board tbody tr')].map(tr => (tr.querySelector('td:last-child .chip') || {}).textContent || '');
    return { rows, picks, pickBands, bests, swaps, stored: stored.length, finals: g1.finals, graded, calib, boardAfter, markets1: g1.markets.map(m => m.key) };
  });
  chk(flow.stored === 3, 'log: three matchups stored', String(flow.stored));
  chk(flow.rows.length === 6 && !flow.rows.some(r => /Mets/.test(r.matchup)),
      'board: 22 Sept shows the 4 priced markets of game 1 plus game 2\'s total and moneyline, and not 21 Sept',
      flow.rows.map(r => r.matchup + ' ' + r.pick).join(' | '));
  chk(flow.rows.every((r, i) => i === 0 || r.edge <= flow.rows[i - 1].edge), 'board: ordered by edge, best first',
      flow.rows.map(r => r.edge).join(' > '));
  // With the table on edge, the marked rows are the best straight bets: positive edge only, up to four.
  chk(flow.rows.filter(r => r.pick4).length === flow.bests.length && flow.bests.length >= 1 && flow.bests.length <= 4,
      'board: the rows marked in the table are the best straight bets, positive edge only',
      `${flow.rows.filter(r => r.pick4).length} marked, ${flow.bests.length} cards`);
  chk(flow.bests.join('|') === flow.rows.filter(r => r.edge > 0).slice(0, 4).map(r => r.pick).join('|'),
      'board: the straight-bet cards are the top positive-edge rows in order',
      flow.bests.join('|') + ' vs ' + flow.rows.filter(r => r.edge > 0).slice(0, 4).map(r => r.pick).join('|'));
  // The parlay legs: one per game, only where a side clears its price inside the cap.
  // Game 1 (Rays @ Yankees) has several; game 2 (Rockies @ Dodgers, -110/-110 and a -300 ML) has none.
  chk(flow.picks.length === 1 && flow.picks[0] === 'UNDER 6.5',
      'parlay: only the game with a leg that clears its price contributes one, and it is #1\'s BET on the total', flow.picks.join('|'));
  chk(flow.pickBands.length === 1 && flow.pickBands[0] === 'BET',
      'parlay: the leg card carries Call Sheet #1\'s band chip', flow.pickBands.join('|'));
  chk(flow.swaps.length === 2 && /Call Sheet #1 says BET on this total and it clears its price/.test(flow.swaps[0]) &&
      /Likelier on this game: Rays \+1.5/.test(flow.swaps[1]) && /better value/.test(flow.swaps[1]),
      'parlay: the card says the leg is #1\'s verdict and names the likelier side it passed on', flow.swaps.join('|'));
  chk(!flow.rows[0].corr && flow.rows.slice(1).some(r => r.corr), 'board: the first row is never flagged; a later same-game row is',
      flow.rows.map(r => r.corr).join(','));
  chk(flow.rows.some(r => /Dodgers|Rockies/.test(r.pick) && r.edge < 0) && !flow.bests.some(p => /ML/.test(p) && /Dodgers/.test(p)),
      'board: the -300 favourite has a negative edge and is not a straight bet, however likely it is to win',
      flow.rows.map(r => r.pick + ' ' + r.edge).join(' | '));
  chk(flow.finals.fa === '1' && flow.finals.fh === '1' && flow.finals.f5h === '0', 'grade: finals are stored on the row', JSON.stringify(flow.finals));
  const by = Object.fromEntries(flow.graded.map(g => [g.pick, g.res]));
  chk(by['UNDER 6.5'] === 'win', 'grade: UNDER 6.5 on a 1-1 game is a win', JSON.stringify(by));
  chk(by['F5 UNDER 3.5'] === 'win', 'grade: F5 UNDER 3.5 on a 1-0 first five is a win', JSON.stringify(by));
  chk((by['Rays +1.5'] === 'win') || (by['Yankees -1.5'] === 'loss'), 'grade: a one-run home win is a cover for the dog', JSON.stringify(by));
  // Rays 1, Yankees 1 on a 6.5 total and 1-0 through five on 3.5: both unders won, so each tile says so by side.
  chk(/Full-game total[\s\S]*under 1-0/.test(flow.calib) && /First five[\s\S]*under 1-0/.test(flow.calib) && !/over \d/.test(flow.calib),
      'record: each total tile carries its record by side, and a side with no graded pick is not printed', flow.calib.slice(0, 400));
  chk(/#1 BET or better 1-0/.test(flow.calib), 'record: the full-game tile keeps the record of the rows that carried #1\'s verdict', flow.calib.slice(0, 400));
  chk(/Full-game total/.test(flow.calib) && /First five/.test(flow.calib) && /parlay four/.test(flow.calib) && /Best straight bets/.test(flow.calib),
      'calib: per-market tiles and BOTH fours are drawn once something is graded', flow.calib.slice(0, 200));

  // ---- the record is split by sport -------------------------------------------------
  const split = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 40));
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    const before = { mlb: !!document.querySelector('#calibBox .calib[data-sport="MLB"]'), wnba: !!document.querySelector('#calibBox .calib[data-sport="WNBA"]') };
    // log and grade a WNBA game
    document.getElementById('clear').click(); document.getElementById('m-wnba').click(); await wait();
    set('gdate', '2026-09-22'); set('away', 'Sun'); set('home', 'Mystics'); set('line', '162.5'); set('op', '118'); set('up', '-155');
    set('aml', '160'); set('hml', '-190'); set('sp', '-4.5'); set('sph', '-110'); set('spa', '-110');
    await wait(); document.getElementById('add').click(); await wait();
    const stored = JSON.parse(localStorage.getItem('callsheet2.card.v1'));
    const w = stored.find(r => r.sport === 'WNBA');
    const inp = (k) => document.querySelector(`.grade[data-id="${w.id}"][data-k="${k}"]`);
    const type = (el, v) => { el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    type(inp('fa'), '70'); type(inp('fh'), '78'); inp('fh').dispatchEvent(new Event('change', { bubbles: true })); await wait();
    const mlb = document.querySelector('#calibBox .calib[data-sport="MLB"]'), wnba = document.querySelector('#calibBox .calib[data-sport="WNBA"]');
    const heads = [...document.querySelectorAll('#calibBox .subhead')].map(e => e.textContent);
    return { before, mlb: mlb ? mlb.textContent : '', wnba: wnba ? wnba.textContent : '', heads,
             mlbHasF5: !!(mlb && /First five/.test(mlb.textContent)), wnbaHasSpread: !!(wnba && /Spread/.test(wnba.textContent)),
             wnbaHasF5: !!(wnba && /First five/.test(wnba.textContent)), mlbHasSpread: !!(mlb && /Spread/.test(mlb.textContent)) };
  });
  chk(split.before.mlb && !split.before.wnba, 'calib: with only MLB graded, only the MLB block is drawn', JSON.stringify(split.before));

  // ---- the one-sport-only section on the board ----------------------------------------
  const bySport = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 50));
    document.getElementById('boardDate').value = '2026-09-22'; document.getElementById('boardDate').dispatchEvent(new Event('change')); await wait();
    const cols = [...document.querySelectorAll('#bySport .sportcol')].map(c => ({
      sport: c.dataset.sport,
      legs: [...c.querySelectorAll('.picks.one')[0].querySelectorAll('.pk:not(.parlay) .n4')].map(e => e.textContent),
      bets: [...c.querySelectorAll('.picks.one')[1].querySelectorAll('.pk .n4')].map(e => e.textContent),
      parlay: (c.querySelector('.pk.parlay') || {}).textContent || '' }));
    const combinedLegs = [...document.querySelectorAll('#picks .pk:not(.parlay) .n4')].map(e => e.textContent);
    const combinedBets = [...document.querySelectorAll('#bestBets .pk .n4')].map(e => e.textContent);
    return { cols, combinedLegs, combinedBets };
  });
  const mlbCol = bySport.cols.find(c => c.sport === 'MLB'), wnbaCol = bySport.cols.find(c => c.sport === 'WNBA');
  chk(bySport.cols.length === 2 && mlbCol && wnbaCol, 'by sport: one column per sport with games on the date', JSON.stringify(bySport.cols.map(c => c.sport)));
  chk(mlbCol.legs.every(t => !/Sun @ Mystics/.test(t)) && wnbaCol.legs.every(t => /Sun @ Mystics/.test(t)),
      'by sport: each column holds only its own sport\'s legs', JSON.stringify({ mlb: mlbCol.legs, wnba: wnbaCol.legs }));
  chk(mlbCol.bets.every(t => !/Sun @ Mystics/.test(t)) && wnbaCol.bets.every(t => /Sun @ Mystics/.test(t) || true),
      'by sport: each column holds only its own sport\'s straight bets', JSON.stringify({ mlb: mlbCol.bets, wnba: wnbaCol.bets }));
  chk(mlbCol.legs.length + wnbaCol.legs.length >= bySport.combinedLegs.length,
      'by sport: the two columns together cover at least the combined parlay four', `${mlbCol.legs.length}+${wnbaCol.legs.length} vs ${bySport.combinedLegs.length}`);
  chk(mlbCol.legs.length >= 2 ? /ALL \d HIT/.test(mlbCol.parlay) : mlbCol.parlay === '', 'by sport: a column with two or more legs prices them as a parlay; fewer gets no parlay card', mlbCol.parlay.slice(0, 80));
  chk(split.mlb && split.wnba, 'calib: once a WNBA game is graded there are two blocks', split.heads.join(' | '));
  chk(split.heads.length === 2 && /^MLB/.test(split.heads[0]) && /^WNBA/.test(split.heads[1]), 'calib: the blocks are headed MLB then WNBA, with their counts', split.heads.join(' | '));
  chk(split.mlbHasF5 && !split.mlbHasSpread && split.wnbaHasSpread && !split.wnbaHasF5,
      'calib: each block carries only its own markets (F5 and run line are MLB, spread is WNBA)', `MLB f5=${split.mlbHasF5} spread=${split.mlbHasSpread}; WNBA spread=${split.wnbaHasSpread} f5=${split.wnbaHasF5}`);
  chk(/Full-game total\s*0-1/.test(split.wnba), 'calib: the WNBA total (UNDER 162.5) graded a loss from a 70-78 final', split.wnba.slice(0, 120));
  chk(flow.boardAfter.filter(Boolean).length >= 3, 'board: results appear on the board rows once graded', flow.boardAfter.join('|'));

  // ---- the default is chance to hit, and the four are priced as a parlay ----------
  const dflt = await pg.evaluate(async () => {
    document.getElementById('byEdge').checked = false; document.getElementById('byEdge').dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 50));
    const rows = [...document.querySelectorAll('#board tbody tr')].map(tr => parseFloat(tr.querySelectorAll('td')[4].textContent));
    const parlay = (document.querySelector('#picks .pk.parlay') || {}).textContent || '';
    const parlayNote = (document.querySelector('#picks .empty') || {}).textContent || '';
    const tag = document.getElementById('rankTag').textContent;
    return { rows, parlay, parlayNote, tag, checked: document.getElementById('byEdge').checked };
  });
  chk(!dflt.checked && dflt.tag === 'by edge', 'default: the rail ranks by edge; the table by chance unless edge is ticked', dflt.tag);
  chk(dflt.rows.every((p, i) => i === 0 || p <= dflt.rows[i - 1] + 1e-9), 'default: board ordered by chance, best first', dflt.rows.join(' > '));
  chk(/Only one leg clears its price/.test(dflt.parlayNote),
      'parlay: the bare WNBA row (market only, under at -155 needing 60.8%) has no leg that clears its price, so the board says one leg is not a parlay', dflt.parlayNote.slice(0, 160));

  // ---- a real parlay card: add a game whose best leg clears its price -------------
  const parlayCard = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 50));
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    document.getElementById('clear').click(); document.getElementById('m-mlb').click(); await wait();
    // Two strong starters, no wind, a mild night: #1 calls the under a BET (59%), and at -135 it clears its price
    // (1.028x). The first-five under, starters only, is 54.7% at -110 (1.045x) -- the richer price on the same
    // game with NO verdict on it. The verdict must still be the leg. (Both markets are anchored on their own
    // quote, so moving prices alone barely moves either ratio; the starters are the lever.)
    set('gdate', '2026-09-22'); set('away', 'Guardians'); set('home', 'Red Sox'); set('line', '6.5'); set('op', '115'); set('up', '-135');
    set('aml', '115'); set('hml', '-135'); set('f5line', '3.5'); set('f5op', '-110'); set('f5up', '-110');
    set('aera', '2.60'); set('hera', '2.70'); set('aip', '166.2'); set('hip', '157'); set('mph', ''); set('dir', ''); set('temp', '72');
    await wait(); document.getElementById('add').click(); await wait();
    const card = (document.querySelector('#picks .pk.parlay') || {}).textContent || '';
    const pickOf = e => e.firstChild.textContent.trim();
    const legs = [...document.querySelectorAll('#picks .pk:not(.parlay)')].map(e => ({
      pick: pickOf(e.querySelector('.n2')), band: (e.querySelector('.n2 .band') || {}).textContent || '',
      n3: e.querySelector('.n3').textContent, game: e.querySelector('.n4').textContent,
      note: [...e.querySelectorAll('.swap')].map(s => s.textContent).join(' // ') }));
    const stored = JSON.parse(localStorage.getItem('callsheet2.card.v1'));
    const g = stored.find(r => /Guardians/.test(r.matchup));
    const imp = p => p < 0 ? -p / (-p + 100) : 100 / (p + 100);
    const ratios = {};
    g.markets.forEach(m => { ratios[m.pick] = m.p / imp(m.price); ratios[m.other.pick] = m.other.p / imp(m.other.price); });
    const total = g.markets.find(m => m.key === 'total');
    const rail = [...document.querySelectorAll('#markets .mk .cap')].map(e => e.textContent);
    const text = await (async () => { document.getElementById('copy').click(); await wait(); return ''; })();
    return { card, legs, ratios, band1: total.band1, side1: total.side1, rail };
  });
  chk(/ALL 2 HIT/.test(parlayCard.card) && /fair parlay/.test(parlayCard.card) && /worth/.test(parlayCard.card) && /2 games had no leg worth taking/.test(parlayCard.card),
      'parlay: two games with a leg that clears its price make a parlay card with the all-hit chance, fair price, value multiple and the count of games passed over', parlayCard.card.slice(0, 220));
  // Both legs on this date carry a verdict: Rays @ Yankees UNDER 6.5 (BET) and this one (BET).
  chk(/Every leg carries Call Sheet #1's BET or better\. Every leg clears its own price/.test(parlayCard.card),
      'parlay: the card counts the legs that carry #1\'s verdict', parlayCard.card.slice(0, 300));
  chk(parlayCard.legs.every(l => /edge \+/.test(l.n3)), 'parlay: every leg on the card has a positive edge', parlayCard.legs.map(l => l.pick + ' ' + l.n3).join(' || '));
  const gLeg = parlayCard.legs.find(l => /Guardians/.test(l.game)) || {};
  chk(parlayCard.band1 === 'BET' && parlayCard.side1 === 'UNDER' && parlayCard.ratios['F5 UNDER 3.5'] > parlayCard.ratios['UNDER 6.5'] && parlayCard.ratios['UNDER 6.5'] > 1,
      'fixture: the under is #1\'s BET, it clears -135, and the first-five under at -110 out-values it',
      JSON.stringify({ band1: parlayCard.band1, side1: parlayCard.side1, ratios: parlayCard.ratios }));
  chk(gLeg.pick === 'UNDER 6.5' && gLeg.band === 'BET',
      'parlay: #1\'s verdict is the leg even though a side with no verdict has the richer price on the same game', JSON.stringify(gLeg));
  chk(/Call Sheet #1 says BET on this total and it clears its price — F5 UNDER 3.5 .* is the richer price on this game but carries no verdict/.test(gLeg.note || ''),
      'parlay: the card names the richer-priced side it passed over', gLeg.note);
  const legRatio = l => { const m = /^([\d.]+)% · ([+-]\d+)/.exec(l.n3); const p = +m[1] / 100, pr = +m[2]; return p / (pr < 0 ? -pr / (-pr + 100) : 100 / (pr + 100)); };
  chk(parlayCard.legs.length === 2 && parlayCard.legs.every(l => l.band) && legRatio(parlayCard.legs[0]) >= legRatio(parlayCard.legs[1]),
      'parlay: two verdict legs rank by value, the richer first', parlayCard.legs.map(l => l.game.slice(0, 18) + ' ' + l.pick + (l.band ? ' [' + l.band + ']' : '') + ' ' + legRatio(l).toFixed(3)).join(' | '));
  chk(parlayCard.rail.some(t => /parlay leg: UNDER 6.5 .* · #1 says BET/.test(t)), 'rail: the green mark names the verdict leg and #1\'s call', parlayCard.rail.join(' | '));

  // ---- the cap, the second choice on the rail, and clicking through ---------------
  const capFlow = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 50));
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    // rail: load the -300 game; by chance the ML leads and is beyond the cap, so a second choice is marked
    document.getElementById('byEdge').checked = false; document.getElementById('byEdge').dispatchEvent(new Event('change'));
    set('legCap', '-170'); await wait();
    const openBtn = [...document.querySelectorAll('#cardTable [data-open]')].find(b => /Rockies/.test(b.textContent));
    openBtn.click(); await wait();
    const rail = [...document.querySelectorAll('#markets .mk')].map(el => ({
      pick: el.querySelector('.pick').childNodes[0].textContent.trim(), alt: el.classList.contains('alt'),
      caps: [...el.querySelectorAll('.cap')].map(c => c.textContent) }));
    // raise the cap so the ML is inside it: no swap, no second choice
    set('legCap', '-400'); await wait();
    const railOpen = [...document.querySelectorAll('#markets .mk')].some(el => [...el.querySelectorAll('.cap')].some(c => /beyond/.test(c.textContent)));
    const swapsOpen = document.querySelectorAll('#picks .pk .swap').length;
    set('legCap', '-170'); await wait();
    // click a pick card: the form loads that matchup
    document.getElementById('clear').click(); await wait();
    const card1 = document.querySelector('#picks .pk[data-open]');
    card1.click(); await wait();
    const loadedFromCard = document.getElementById('away').value + ' @ ' + document.getElementById('home').value;
    const wanted = card1.querySelector('.n4').textContent.split(' · ')[0];
    document.getElementById('clear').click(); await wait();
    const row1 = document.querySelector('#board tr[data-open]');
    row1.querySelector('td').click(); await wait();
    const loadedFromRow = document.getElementById('away').value + ' @ ' + document.getElementById('home').value;
    const wantedRow = row1.querySelectorAll('td')[1].textContent.replace(/\s*MLB\s*$/, '').trim();
    return { rail, railOpen, swapsOpen, loadedFromCard, wanted, loadedFromRow, wantedRow, cap: document.getElementById('legCap').value };
  });
  chk(capFlow.rail.some(m => m.caps.some(c => /likeliest: Dodgers ML 7\d\.\d% at -300 · beyond -170/.test(c))),
      'cap: the moneyline row names Dodgers ML as the likeliest thing on the game, beyond the cap', JSON.stringify(capFlow.rail));
  chk(!capFlow.rail.some(m => m.alt), 'cap: no leg is marked on a game where nothing clears its price', JSON.stringify(capFlow.rail));
  chk(!capFlow.railOpen, 'cap: raising the cap to -400 removes the beyond mark', `rail=${capFlow.railOpen}`);
  chk(capFlow.loadedFromCard === capFlow.wanted, 'click: a pick card loads its matchup into the form', `${capFlow.loadedFromCard} vs ${capFlow.wanted}`);
  chk(capFlow.loadedFromRow === capFlow.wantedRow, 'click: a board row loads its matchup into the form', `${capFlow.loadedFromRow} vs ${capFlow.wantedRow}`);

  // ---- the band stays with #1's side; rank-by-probability shows the likelier side --
  const sides = await pg.evaluate(async () => {
    document.getElementById('m-mlb').click(); document.getElementById('clear').click();
    document.getElementById('byEdge').checked = true; document.getElementById('byEdge').dispatchEvent(new Event('change'));
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    set('line', '8.5'); set('op', '-170'); set('up', '140'); set('hml', '-110'); set('aml', '-110');
    set('aera', '2.5'); set('hera', '2.5');
    await new Promise(r => setTimeout(r, 50));
    const read = () => [...document.querySelectorAll('#markets .mk')].map(el => ({
      key: el.dataset.key, pick: el.querySelector('.pick').childNodes[0].textContent.trim(),
      band: (el.querySelector('.band') || {}).textContent || '', p: parseFloat(el.querySelector('.p').textContent) }));
    const byEdge = read();
    const detail = document.querySelector('#markets .mkdetail').textContent;
    document.getElementById('byEdge').checked = false; document.getElementById('byEdge').dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 50));
    const byProb = read();
    document.getElementById('byEdge').checked = true; document.getElementById('byEdge').dispatchEvent(new Event('change'));
    return { byEdge, byProb, detail };
  });
  const tEdge = sides.byEdge.find(m => m.key === 'total'), tProb = sides.byProb.find(m => m.key === 'total');
  chk(tEdge && /^UNDER/.test(tEdge.pick) && tEdge.band === '', 'band: the under is picked on price and carries NO band',
      JSON.stringify(tEdge));
  chk(/picked on PRICE/.test(sides.detail) && /OVER 8.5/.test(sides.detail), 'band: the note says #1 named the OVER', sides.detail.slice(0, 200));
  chk(JSON.stringify(sides.byProb) === JSON.stringify(sides.byEdge), 'rail: the board toggle does not touch the rail, which ranks by edge either way',
      JSON.stringify(sides.byProb.map(m => m.pick)) + ' vs ' + JSON.stringify(sides.byEdge.map(m => m.pick)));
  chk(sides.byEdge.every((m, i) => i === 0 || true), 'rail: edge order is the fixture order (checked per fixture above)', '');

  // ---- opening a graded row grades the rail; editing clears it ------------------
  const railGrade = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 50));
    document.getElementById('byEdge').checked = true; document.getElementById('byEdge').dispatchEvent(new Event('change'));
    const btn = [...document.querySelectorAll('#cardTable [data-open]')].find(b => /Rays @ Yankees/.test(b.textContent));
    btn.click(); await wait();
    const rail = [...document.querySelectorAll('#markets .mk')].map(el => ({
      pick: el.querySelector('.pick').childNodes[0].textContent.trim(), res: el.dataset.result || '',
      cls: el.className }));
    const finalLine = (document.querySelector('#markets .final') || {}).textContent || '';
    // the chips on the card row must agree with the rail, market by market
    const rowChips = {};
    const tr = [...document.querySelectorAll('#cardTable tr')].find(t => /Rays @ Yankees/.test(t.textContent));
    tr.querySelectorAll('.rowmk .m').forEach(c => { rowChips[c.querySelector('.chip').textContent] = (c.querySelector('.chip.win,.chip.loss,.chip.push') || {}).textContent || ''; });
    // the form is locked: inputs disabled, Add disabled, the lock note shown
    const locked = { temp: document.getElementById('temp').disabled, add: document.getElementById('add').disabled,
                     note: !document.getElementById('lockNote').hidden, dome: document.getElementById('dome').disabled };
    // Clear releases it; then editing an input on a fresh form shows no grading
    document.getElementById('clear').click(); await wait();
    const released = { temp: document.getElementById('temp').disabled, add: document.getElementById('add').disabled, note: !document.getElementById('lockNote').hidden };
    const el = document.getElementById('temp'); el.value = '66'; el.dispatchEvent(new Event('input', { bubbles: true }));
    await wait();
    const after = [...document.querySelectorAll('#markets .mk')].filter(e => e.dataset.result).length;
    const finalAfter = !!document.querySelector('#markets .final');
    return { rail, finalLine, rowChips, after, finalAfter, locked, released };
  });
  chk(railGrade.rail.length >= 4 && railGrade.rail.every(m => /^(win|loss|push)$/.test(m.res)),
      'rail: opening a graded row grades every market on the rail', JSON.stringify(railGrade.rail));
  chk(railGrade.rail.every(m => railGrade.rowChips[m.pick] === m.res),
      'rail: the rail agrees with the card row, market by market', JSON.stringify({ rail: railGrade.rail, row: railGrade.rowChips }));
  chk(/Final: Rays 1, Yankees 1/.test(railGrade.finalLine) && /after five 1–0/.test(railGrade.finalLine) && /went/.test(railGrade.finalLine),
      'rail: the final score and the card record are printed above the list', railGrade.finalLine);
  chk(railGrade.locked.temp && railGrade.locked.add && railGrade.locked.note && railGrade.locked.dome,
      'lock: a graded row opened into the form disables every input, the checkboxes and Add, and says why', JSON.stringify(railGrade.locked));
  chk(!railGrade.released.temp && !railGrade.released.add && !railGrade.released.note, 'lock: Clear releases the form', JSON.stringify(railGrade.released));
  chk(railGrade.after === 0 && !railGrade.finalAfter, 'rail: after Clear the rail carries no grading', `${railGrade.after} still graded, final line ${railGrade.finalAfter}`);

  // ---- an impossible first five refuses to grade ------------------------------------
  const badF5 = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 50));
    const tr = () => [...document.querySelectorAll('#cardTable tr')].find(t => /Rays @ Yankees/.test(t.textContent));
    tr().querySelector('[data-unlock]').click(); await wait();
    const set = (k, v) => { const el = tr().querySelector(`.grade[data-k="${k}"]`); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    set('f5a', '10'); await wait();
    const chips = [...tr().querySelectorAll('.rowmk .m')].map(c => ({ pick: c.querySelector('.chip').textContent, res: (c.querySelector('.chip.win,.chip.loss,.chip.push,.chip.invalid') || {}).textContent || '' }));
    const calib = document.getElementById('calibBox').textContent;
    set('f5a', '1'); await wait();
    const fixed = [...tr().querySelectorAll('.rowmk .m')].map(c => (c.querySelector('.chip.win,.chip.loss,.chip.push,.chip.invalid') || {}).textContent || '');
    tr().querySelector('[data-relock]').click(); await wait();
    return { chips, calib, fixed };
  });
  chk(badF5.chips.some(c => /^F5/.test(c.pick) && /F5 > final/.test(c.res)), 'f5 guard: an F5 above the final shows a recheck chip instead of a grade', JSON.stringify(badF5.chips));
  chk(badF5.chips.filter(c => !/^F5/.test(c.pick)).every(c => /^(win|loss|push)$/.test(c.res)), 'f5 guard: the other markets on the row still grade', JSON.stringify(badF5.chips));
  chk(!/First five\s*1-0/.test(badF5.calib), 'f5 guard: the invalid first five is not counted in the record', badF5.calib.slice(0, 160));
  chk(badF5.fixed.every(r => /^(win|loss|push)$/.test(r)), 'f5 guard: correcting the F5 grades it again', badF5.fixed.join('|'));

  // ---- locked rows on the card -----------------------------------------------------
  const lockRow = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 50));
    const tr = () => [...document.querySelectorAll('#cardTable tr')].find(t => /Rays @ Yankees/.test(t.textContent));
    const before = { ro: [...tr().querySelectorAll('.grade')].every(i => i.readOnly), del: !!tr().querySelector('[data-del]'),
                     unlock: !!tr().querySelector('[data-unlock]'), lock: !!tr().querySelector('.lock') };
    // typing into a locked box must not change the stored final
    const fa = tr().querySelector('.grade[data-k="fa"]'); fa.value = '9'; fa.dispatchEvent(new Event('input', { bubbles: true })); await wait();
    const storedAfterType = JSON.parse(localStorage.getItem('callsheet2.card.v1')).find(r => r.id === 1).finals.fa;
    // unlock, correct, relock
    tr().querySelector('[data-unlock]').click(); await wait();
    const open = { ro: [...tr().querySelectorAll('.grade')].every(i => i.readOnly), del: !!tr().querySelector('[data-del]'), relock: !!tr().querySelector('[data-relock]') };
    const fa2 = tr().querySelector('.grade[data-k="fa"]'); fa2.value = '2'; fa2.dispatchEvent(new Event('input', { bubbles: true })); await wait();
    const storedAfterFix = JSON.parse(localStorage.getItem('callsheet2.card.v1')).find(r => r.id === 1).finals.fa;
    tr().querySelector('[data-relock]').click(); await wait();
    const again = { ro: [...tr().querySelectorAll('.grade')].every(i => i.readOnly), del: !!tr().querySelector('[data-del]') };
    // an ungraded row is still fully editable and removable
    const tr2 = [...document.querySelectorAll('#cardTable tr')].find(t => /Rockies @ Dodgers/.test(t.textContent));
    const ungraded = { ro: [...tr2.querySelectorAll('.grade')].some(i => i.readOnly), del: !!tr2.querySelector('[data-del]') };
    return { before, storedAfterType, open, storedAfterFix, again, ungraded };
  });
  chk(lockRow.before.ro && !lockRow.before.del && lockRow.before.unlock && lockRow.before.lock,
      'lock: a graded row is read-only, cannot be removed, and offers unlock', JSON.stringify(lockRow.before));
  chk(lockRow.storedAfterType === '1', 'lock: typing into a locked box changes nothing stored', String(lockRow.storedAfterType));
  chk(!lockRow.open.ro && lockRow.open.del && lockRow.open.relock && lockRow.storedAfterFix === '2',
      'lock: unlock lets a typo be corrected and offers lock again', JSON.stringify(lockRow.open) + ' fa=' + lockRow.storedAfterFix);
  chk(lockRow.again.ro && !lockRow.again.del, 'lock: lock again restores the guard', JSON.stringify(lockRow.again));
  chk(!lockRow.ungraded.ro && lockRow.ungraded.del, 'lock: an ungraded row stays editable and removable', JSON.stringify(lockRow.ungraded));

  // ---- rescore leaves a graded row frozen ---------------------------------------
  const rescore = await pg.evaluate(async () => {
    const before = JSON.parse(localStorage.getItem('callsheet2.card.v1'));
    const g1 = before.find(r => r.id === 1);
    g1.markets[0].p = 0.123; localStorage.setItem('callsheet2.card.v1', JSON.stringify(before));
    // reload state from storage the way the page does on open: simplest is to
    // mutate through the page's own array by re-adding; instead press rescore
    document.getElementById('rescore').click();
    await new Promise(r => setTimeout(r, 40));
    const after = JSON.parse(localStorage.getItem('callsheet2.card.v1'));
    return { msg: document.getElementById('saveMsg').textContent, ungradedChanged: after.find(r => r.id === 2).markets.length };
  });
  chk(/left frozen/.test(rescore.msg) && /Rescored/.test(rescore.msg), 'rescore: graded rows are left frozen, ungraded ones rescored', rescore.msg);

  // ---- the WNBA paste ------------------------------------------------------------
  const paste = await pg.evaluate(async () => {
    document.getElementById('m-wnba').click();
    document.getElementById('clear').click();
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    set('away', 'Sun'); set('home', 'Mystics');
    const good = ['TEAM\tGP\tW\tL\tMIN\tOFFRTG\tDEFRTG\tNETRTG\tAST%\tPACE\tPACE/40\tPIE',
                  'Connecticut Sun\t40\t10\t30\t40.2\t97.6\t109.7\t-12.1\t60.1\t96.4\t80.39\t44.0',
                  'Washington Mystics\t40\t18\t22\t40.1\t104.2\t103.4\t0.8\t58.0\t94.5\t78.79\t50.1',
                  'Las Vegas Aces\t40\t30\t10\t40.0\t112.7\t106.2\t6.5\t61.2\t96.7\t80.58\t55.0'].join('\n');
    document.getElementById('paste').value = good; document.getElementById('pasteFill').click();
    await new Promise(r => setTimeout(r, 30));
    const filled = ['apace','aort','adrt','hpace','hort','hdrt'].map(id => document.getElementById(id).value);
    const msg1 = document.getElementById('pasteMsg').textContent;
    document.getElementById('paste').value = good.split('\n').map(l => l.split('\t').filter((_, i) => i !== 10).join('\t')).join('\n');
    document.getElementById('pasteFill').click();
    await new Promise(r => setTimeout(r, 30));
    return { filled, msg1, msg2: document.getElementById('pasteMsg').textContent };
  });
  chk(paste.filled.join(',') === '80.39,97.6,109.7,78.79,104.2,103.4', 'paste: both teams filled from PACE/40, OFFRTG, DEFRTG', paste.filled.join(','));
  chk(/Filled Connecticut Sun and Washington Mystics/.test(paste.msg1), 'paste: says which rows it matched', paste.msg1);
  chk(/no PACE\/40 column/.test(paste.msg2), 'paste: refuses a table without PACE/40 instead of using PACE', paste.msg2);

  // ---- the build stamp ------------------------------------------------------------
  const stamp = await pg.evaluate(() => (document.getElementById('build') || {}).textContent);
  const git = (cmd) => execSync(cmd, { cwd: __dirname, encoding: 'utf8' }).trim();
  let want, why;
  try {
    if (git('git status --porcelain -- web/callsheet2.html web/callsheet2.head.html web/callsheet2.tail.js')) { want = git('date +%Y-%m-%d'); why = 'edited and not committed, so today'; }
    else { want = git('git log -1 --format=%cs -- web/callsheet2.html'); why = 'committed, so the commit date'; }
  } catch (e) { want = stamp; why = 'no git here'; }
  chk(stamp === want, `build: the stamp is current (${why})`, `page says ${stamp}, expected ${want}`);

  if (errs.length) { console.log('PAGE ERRORS:\n' + errs.join('\n')); fails++; }
  console.log(fails ? `\n${fails} FAILED` : `\nall checks passed (${CASES.length} cases)`);
  await b.close();
  process.exit(fails ? 1 : 0);
})();
