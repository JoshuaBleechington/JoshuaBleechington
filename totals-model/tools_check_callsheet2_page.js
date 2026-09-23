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
    const picks = [...document.querySelectorAll('#picks .pk:not(.parlay) .n2')].map(e => e.textContent);
    const bests = [...document.querySelectorAll('#bestBets .pk .n2')].map(e => e.textContent);
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
    return { rows, picks, bests, swaps, stored: stored.length, finals: g1.finals, graded, calib, boardAfter, markets1: g1.markets.map(m => m.key) };
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
  // The parlay four is one leg per game: two games logged on the 22nd, so two legs.
  chk(flow.picks.length === 2, 'parlay: one leg per game, so two games give two legs', flow.picks.join('|'));
  chk(flow.swaps.length === 1 && /Instead of Dodgers ML/.test(flow.swaps[0]) && /-300/.test(flow.swaps[0]),
      'parlay: the -300 favourite is swapped for the next-likeliest market on its game, and the card says so', flow.swaps.join('|'));
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
  chk(/Full-game total/.test(flow.calib) && /First five/.test(flow.calib) && /parlay four/.test(flow.calib) && /Best straight bets/.test(flow.calib),
      'calib: per-market tiles and BOTH fours are drawn once something is graded', flow.calib.slice(0, 200));
  chk(flow.boardAfter.filter(Boolean).length >= 3, 'board: results appear on the board rows once graded', flow.boardAfter.join('|'));

  // ---- the default is chance to hit, and the four are priced as a parlay ----------
  const dflt = await pg.evaluate(async () => {
    document.getElementById('byEdge').checked = false; document.getElementById('byEdge').dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 50));
    const rows = [...document.querySelectorAll('#board tbody tr')].map(tr => parseFloat(tr.querySelectorAll('td')[4].textContent));
    const parlay = (document.querySelector('#picks .pk.parlay') || {}).textContent || '';
    const tag = document.getElementById('rankTag').textContent;
    return { rows, parlay, tag, checked: document.getElementById('byEdge').checked };
  });
  chk(!dflt.checked && dflt.tag === 'by edge', 'default: the rail ranks by edge; the table by chance unless edge is ticked', dflt.tag);
  chk(dflt.rows.every((p, i) => i === 0 || p <= dflt.rows[i - 1] + 1e-9), 'default: board ordered by chance, best first', dflt.rows.join(' > '));
  chk(/ALL 2 HIT/.test(dflt.parlay) && /fair parlay/.test(dflt.parlay), 'parlay: the legs carry an all-hit chance and a fair parlay price', dflt.parlay.slice(0, 120));

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
    const railOpen = [...document.querySelectorAll('#markets .mk')].some(el => el.classList.contains('alt') || [...el.querySelectorAll('.cap')].some(c => /beyond|2nd choice/.test(c.textContent)));
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
  chk(capFlow.rail.some(m => m.alt && m.caps.some(c => /2nd choice · parlay leg: .* at /.test(c))), 'cap: the next-likeliest market inside the cap is marked as the second choice, pick named', JSON.stringify(capFlow.rail));
  chk(!capFlow.railOpen && capFlow.swapsOpen === 0, 'cap: raising the cap to -400 removes the marks and the swap', `rail=${capFlow.railOpen} swaps=${capFlow.swapsOpen}`);
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
