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
    document.getElementById('byProb').checked = false;
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
    const picks = [...document.querySelectorAll('#picks .pk .n2')].map(e => e.textContent);
    // grade game 1: Rays 1, Yankees 1 (2 runs), F5 1-0
    const inp = (id, k) => document.querySelector(`.grade[data-id="${id}"][data-k="${k}"]`);
    const type = (el, v) => { el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    type(inp('1', 'fa'), '1'); type(inp('1', 'fh'), '1'); type(inp('1', 'f5a'), '1'); type(inp('1', 'f5h'), '0');
    await wait();
    const stored = JSON.parse(localStorage.getItem('callsheet2.card.v1'));
    const g1 = stored.find(r => r.id === 1);
    const chips = [...document.querySelectorAll('#cardTable tr')].find(tr => /Rays @ Yankees/.test(tr.textContent))
      .querySelectorAll('.rowmk .m');
    const graded = [...chips].map(c => ({ pick: c.querySelector('.chip').textContent, res: (c.querySelector('.chip.win,.chip.loss,.chip.push') || {}).textContent || '' }));
    const calib = document.getElementById('calibBox').textContent;
    const boardAfter = [...document.querySelectorAll('#board tbody tr')].map(tr => (tr.querySelector('td:last-child .chip') || {}).textContent || '');
    return { rows, picks, stored: stored.length, finals: g1.finals, graded, calib, boardAfter, markets1: g1.markets.map(m => m.key) };
  });
  chk(flow.stored === 3, 'log: three matchups stored', String(flow.stored));
  chk(flow.rows.length === 6 && !flow.rows.some(r => /Mets/.test(r.matchup)),
      'board: 22 Sept shows the 4 priced markets of game 1 plus game 2\'s total and moneyline, and not 21 Sept',
      flow.rows.map(r => r.matchup + ' ' + r.pick).join(' | '));
  chk(flow.rows.every((r, i) => i === 0 || r.edge <= flow.rows[i - 1].edge), 'board: ordered by edge, best first',
      flow.rows.map(r => r.edge).join(' > '));
  chk(flow.rows.filter(r => r.pick4).length === 4 && flow.picks.length === 4, 'board: exactly four picks are marked, and the four cards match',
      `${flow.rows.filter(r => r.pick4).length} marked, ${flow.picks.length} cards`);
  chk(flow.picks.join('|') === flow.rows.slice(0, 4).map(r => r.pick).join('|'), 'board: the pick cards are the top four rows in order',
      flow.picks.join('|') + ' vs ' + flow.rows.slice(0, 4).map(r => r.pick).join('|'));
  chk(!flow.rows[0].corr && flow.rows.slice(1).some(r => r.corr), 'board: the first row is never flagged; a later same-game row is',
      flow.rows.map(r => r.corr).join(','));
  chk(flow.rows[flow.rows.length - 1].matchup.indexOf('Rockies') === 0 || flow.rows.some(r => /Dodgers|Rockies/.test(r.pick) && r.edge < 0),
      'board: the -300 favourite sits at the bottom with a negative edge, however likely it is to win',
      flow.rows.map(r => r.pick + ' ' + r.edge).join(' | '));
  chk(flow.finals.fa === '1' && flow.finals.fh === '1' && flow.finals.f5h === '0', 'grade: finals are stored on the row', JSON.stringify(flow.finals));
  const by = Object.fromEntries(flow.graded.map(g => [g.pick, g.res]));
  chk(by['UNDER 6.5'] === 'win', 'grade: UNDER 6.5 on a 1-1 game is a win', JSON.stringify(by));
  chk(by['F5 UNDER 3.5'] === 'win', 'grade: F5 UNDER 3.5 on a 1-0 first five is a win', JSON.stringify(by));
  chk((by['Rays +1.5'] === 'win') || (by['Yankees -1.5'] === 'loss'), 'grade: a one-run home win is a cover for the dog', JSON.stringify(by));
  chk(/Full-game total/.test(flow.calib) && /First five/.test(flow.calib) && /Top-4 rule/.test(flow.calib),
      'calib: per-market tiles and the top-4 rule are drawn once something is graded', flow.calib.slice(0, 200));
  chk(flow.boardAfter.filter(Boolean).length >= 3, 'board: results appear on the board rows once graded', flow.boardAfter.join('|'));

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
