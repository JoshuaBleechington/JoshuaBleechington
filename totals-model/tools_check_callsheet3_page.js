/* Replays web/callsheet3-cases.json through web/callsheet3.html in a real
 * browser and asserts the page reaches the same markets, in the same order,
 * with the same probabilities and edges the Python package reached -- the
 * MLB cases through Call Sheet #1's engine block (byte-identical to
 * fullgame.html's) and the NBA cases through the NBA block (ported from
 * totals/nba.py); the hockey book came off the page on 30 Oct 2026.
 *
 * Then what the fixtures cannot see: the basketball card and its slate, the
 * props, the simulation, the takes, the middles and the window, the store,
 * a void row, and the build stamp is current.
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
             "h1line","h1op","h1up","naort","nhort","nadrt","nhdrt","napace","nhpace","nagp","nhgp","nlrtg","nlpace","narest","nhrest","nbaout","nbaq","nbactx","ncrew","nbarefs","nbalineup","nbaform","nbasim"];
const CHECKS = ["dome","playoff"];

(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/opt/pw-browsers/chromium' });
  const pg = await b.newPage({ viewport: { width: 1280, height: 1400 } });
  // 11 Nov 2026: three-leg tickets sit under the BETs by default; the blocks written before read the LEAN cards there, so every load
  // puts the LEANs back unless a block frees the choice
  let belowFree = false;
  const leansBelow = async () => { if (belowFree) return; await pg.evaluate(async () => { await window.smStore.ready; const el = document.getElementById('propsBelow'); if (el && el.value !== 'leans') { el.value = 'leans'; el.dispatchEvent(new Event('change', { bubbles: true })); } }); };
  const reloaded = async () => {
    await pg.reload();
    try { await pg.waitForFunction(() => window.smStore && window.smStore.ready, null, { timeout: 60000 }); }
    catch (e) {   // 2 Nov 2026: a reload stalled 30 s once under load; say what the page looks like before giving up
      const state = await pg.evaluate(() => ({ ready: document.readyState, store: typeof window.smStore, url: location.href.slice(-40), scripts: document.scripts.length })).catch(err => String(err));
      console.log('reload stalled:', JSON.stringify(state), 'page errors so far:', JSON.stringify(errs.slice(-5)));
      throw e;
    }
    await pg.waitForTimeout(300);
    await leansBelow();
  };   // a reload waits for the store, not a fixed 300 ms (30 Oct 2026: the harness raced the page under load)
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
  const belowDefault = await pg.evaluate(async () => { await window.smStore.ready; return (document.getElementById('propsBelow') || {}).value; });   // the choice on a first visit
  const legsDefault = await pg.evaluate(() => (document.getElementById('propsLegs') || {}).value);   // and the legs a ticket
  await leansBelow();

  let fails = 0;
  const chk = (ok, m, d) => { if (!ok) fails++; console.log(`${ok ? 'PASS' : 'FAIL'}  ${m}${ok ? '' : '\n        ' + d}`); };

  // ---- the engine block is Call Sheet #1's, byte for byte; the NBA block sits after it ----
  const block = (file, open, close) => {
    const s = fs.readFileSync(path.join(__dirname, 'web', file), 'utf8').split('\n');
    const a = s.findIndex(l => l.startsWith(open));
    const z = s.findIndex(l => l.startsWith(close));
    return a >= 0 && z > a ? s.slice(a, z + 1).join('\n') : null;
  };
  const b1 = block('fullgame.html', '  /* ===== ENGINE BLOCK.', '  /* ===== END ENGINE BLOCK ===== */');
  const b3 = block('callsheet3.html', '  /* ===== ENGINE BLOCK.', '  /* ===== END ENGINE BLOCK ===== */');
  chk(b1 && b3 && b1 === b3, 'engine: callsheet3.html carries fullgame.html\'s engine block byte-identical', `#1 ${b1 ? b1.length : 'missing'} vs 3.0 ${b3 ? b3.length : 'missing'}`);
  const html = fs.readFileSync(path.join(__dirname, 'web/callsheet3.html'), 'utf8');
  chk(html.indexOf('NHL BLOCK.') < 0 && html.indexOf('id="m-nhl"') < 0 && html.indexOf('id="nhlFields"') < 0, 'engine: the hockey block, button and fields are off the page (30 Oct 2026)', '');
  const nbb = block('callsheet3.html', '  /* ===== NBA BLOCK.', '  /* ===== END NBA BLOCK ===== */');
  const nsrc = fs.readFileSync(path.join(__dirname, 'web/nba.engine.js'), 'utf8').replace(/\n$/, '');
  chk(nbb && nbb === nsrc, 'engine: the NBA block is web/nba.engine.js verbatim and follows the engine block', `${nbb ? nbb.length : 'missing'} vs ${nsrc.length}`);
  chk(html.indexOf('END ENGINE BLOCK') < html.indexOf('NBA BLOCK.'), 'engine: the NBA block comes after the engine block', '');

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
    const visible = { nba: !document.getElementById('nbaFields').hidden, h1: !document.getElementById('h1Fields').hidden, sp: !document.getElementById('spFields').hidden, pressed: document.getElementById('m-nba').getAttribute('aria-pressed'), label: document.getElementById('lineLabel').textContent };
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
  chk(nba.visible.nba && nba.visible.h1 && nba.visible.sp && nba.visible.pressed === 'true' && nba.visible.label === 'Total (points)', 'nba: the fourth button shows the NBA fields, the half and the spread, and hides hockey', JSON.stringify(nba.visible));
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

  // ---- 19 Oct 2026: the Props tab -- a props file lists, a grade file grades, the record tile and the backup carry it ----
  const propsT = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 80));
    await smStore.removeItem('callsheet3.props.v1');
    const propsDoc = { format: 'callsheet3.props', version: 1, date: '2026-10-21', games: [
      { gid: '401909834', away: 'Hawks', home: 'Magic', aab: 'ATL', hab: 'ORL', spread: -4.5, total: 229.5, pace: 99.8, props: [
        { pid: '3037789', name: 'Trae Young', team: 'ATL', opp: 'ORL', home: false, pos: 'PG', mk: 'pts', line: 24.5, op: -110, up: -110, book: 'fanatics', books: { fanatics: [24.5, -110, -110], draftkings: [25.5, -115, -105] },
          proj: 27.2, sd: 9.4, pm: 0.612, pb: 0.5, p: 0.5604, push: 0, side: 'OVER', chance: 0.5604, price: -110, need: 0.5238, edge: 0.0366, band: 'BET', mins: 35.1, rate36: 27.9,
          kal: { r: [[19.5, 0.70, 0.72, 0.71, 100], [24.5, 0.46, 0.48, 0.47, 500], [29.5, 0.24, 0.26, 0.25, 50]], team: 'ATL' },   // a ladder a file from 4 Nov 2026 still carries: ignored from 5 Nov (Kalshi is off the props)
          form: { vals: [20, 21, 30], over: 1, on: 0, avg: 23.7 },   // the slate's block (7 Nov 2026): the log below has two games with the stat, so the card's form line can only come off the block
          why: ['27.9 points per 36 this season (3 games, 104 minutes)', '35.1 minutes projected'],
          log: [['2026-10-15', 'MIA', 0, 34.0, 26, ['won by 3', '34 min (his usual 33)'], 'tries: 20 from the floor (his usual 19 at those minutes) · 3 of 8 from three · 5 of 6 from the line'], ['2026-10-17', 'CHI', 1, 31.0, 22], ['2026-10-19', 'BOS', 0, 12.5, null]] },   // the first game carries the factors and the tries (7 Nov 2026)
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
    const formBlock = (() => { const c = [...document.querySelectorAll('#propsBest .pk')].find(e => /Trae Young/.test(e.textContent)), fl = c && c.querySelector('.n5.formline'); return fl ? fl.textContent.replace(/\s+/g, ' ').trim() + '|' + fl.className : ''; })();
    const formStored = await (async () => { try { const raw = (window.smStore ? await smStore.getItem('callsheet3.props.v1') : null) || localStorage.getItem('callsheet3.props.v1') || '[]'; const r = JSON.parse(raw).find(x => x.pid === '3037789'); return r && r.form ? JSON.stringify(r.form) : ''; } catch (e) { return 'err ' + e; } })();
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
        box: { '3037789': ['Trae Young', 36.2, 28, 3, 11, 4, { pts: ['won by 6', '36 min (his usual 34)', '22 shots (his usual 21 at those minutes)', '10 of 19 from the floor'], reb: ['won by 6', '36 min (his usual 34)', '3 of the club\'s 44 rebounds (his usual 9%)'], ast: ['Dyson Daniels out (30 mpg, a lift for him)', 'won by 6', '11 of the club\'s 27 assists, 41% (his usual 30%)'], tpm: ['won by 6'], pra: ['won by 6'] }, { pts: 'tries: 19 from the floor (his usual 18 at those minutes) · 3 of 7 from three · 6 of 7 from the line', tpm: 'tries: 3 of 7 from three (his usual 6.5 at those minutes) · 19 from the floor · 6 of 7 from the line' }], '4397020': ['Paolo Banchero', 34.0, 22, 9, 4, 1] } } ] };   // the tries eighth (7 Nov 2026)
    await load(gradeDoc, 'nba-grade-2026-10-21.json');
    const after = JSON.parse(smStore.getItem('callsheet3.props.v1'));
    // the graded night joins the panel's last games, with his minutes from the box line (25 Oct 2026)
    document.querySelector('#propsTable tr[data-prop]').click(); await wait();
    const thisRow = (document.querySelector('#propDetail .pd-log tr.this') || { innerText: '' }).innerText.replace(/\s+/g, ' ').trim(), thisMark = (document.querySelector('#propDetail .pd-log tr.this b.lg') || { className: '' }).className;
    const thisWhat = (document.querySelector('#propDetail .pd-log tr.this td.pd-what') || { innerText: '' }).innerText.replace(/\s+/g, ' ').trim(), whatHead = [...document.querySelectorAll('#propDetail .pd-log thead th')].map(t => t.textContent.trim()).join('|'), otherWhat = [...document.querySelectorAll('#propDetail .pd-log tbody tr:not(.this) td.pd-what')].map(td => td.textContent.trim());
    const logRows = document.querySelectorAll('#propDetail .pd-log tbody tr').length;
    const triesCells = [...document.querySelectorAll('#propDetail .pd-log tbody tr')].map(tr => { const s = tr.querySelector('td.pd-what .tries'); return (tr.classList.contains('this') ? 'this:' : '') + (s ? s.className + '|' + s.textContent.trim() : ''); });
    const lastH4 = [...document.querySelectorAll('#propDetail h4')].find(h => /^Last games/.test(h.textContent.trim())) || document.createElement('h4');
    const headDim = [...lastH4.querySelectorAll('.dim')].find(d => /what the box says/.test(d.textContent)) || document.createElement('span');   // the tally's own dim span comes first
    const triesHead = (headDim.textContent || '').replace(/\s+/g, ' ').trim(), triesHeadCls = ((headDim.querySelector('.tries') || {}).className || '');
    const triesStored = (after.find(r => r.pid === '3037789' && r.mk === 'pts') || {}).atries || '';
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
    return { viewOn, colsOff, pressed, best, formBlock, formStored, rowsOn, rowsAll, count, msg, whyOpen, logMarks, tileBefore, after: after.map(r => [r.name, r.mk, r.result, r.actual]), tileText, slateMsg, restored: restored.length, viewOff, colsBack, nbaPressed,
             tabCalib, tabBlocks, nights, ladder, tabEmpty0, noneMsg, thinMsg, inPlay, thisRow, thisMark, logRows, refill, thisWhat, whatHead, otherWhat, triesCells, triesHead, triesHeadCls, triesStored };
  });
  chk(propsT.formBlock === 'His last 3: 20 · 21 · 30 against 24.5 · 1 of 3 over, against the OVER|n5 formline neg' && propsT.formStored === '{"vals":[20,21,30],"over":1,"on":0,"avg":23.7}',
      'props file: the slate\'s form block lands on the row and the card\'s form line reads it (7 Nov 2026; the seeded log has two games with the stat, so the line can only come off the block)', JSON.stringify({ card: propsT.formBlock, stored: propsT.formStored }));
  chk(propsT.refill.stripped && propsT.refill.same && JSON.stringify(propsT.refill.mins) === JSON.stringify(propsT.refill.was) && propsT.refill.mins.some(m => typeof m === 'number') && /Minutes filled in on \d+ graded props? from the box lines\./.test(propsT.refill.msg),
      'props: a second load of a night\'s grade file fills the minutes in on props graded before they were kept, leaves every result as it was, and says how many', JSON.stringify(propsT.refill));
  chk(/^10-21 @ [A-Z]+ this game 36\.2 28 won by 6 · 36 min \(his usual 34\) · 22 shots \(his usual 21 at those minutes\) · 10 of 19 from the floor tries: 19 from the floor \(his usual 18 at those minutes\) · 3 of 7 from three · 6 of 7 from the line$/.test(propsT.thisRow) && /lg over/.test(propsT.thisMark) && propsT.logRows === 4
      && propsT.whatHead === 'Date|Opp|Min|points|What happened' && propsT.thisWhat === 'won by 6 · 36 min (his usual 34) · 22 shots (his usual 21 at those minutes) · 10 of 19 from the floor tries: 19 from the floor (his usual 18 at those minutes) · 3 of 7 from three · 6 of 7 from the line'
      && propsT.otherWhat.length === 3 && propsT.otherWhat[0] === 'won by 3 · 34 min (his usual 33) tries: 20 from the floor (his usual 19 at those minutes) · 3 of 8 from three · 5 of 6 from the line' && propsT.otherWhat.slice(1).every(t => t === ''),
      'props: a graded prop\'s last games end with the game itself, his minutes from the box line and the stat marked against the line', JSON.stringify({ row: propsT.thisRow, mark: propsT.thisMark, rows: propsT.logRows, other: propsT.otherWhat }));
  chk(JSON.stringify(propsT.triesCells) === JSON.stringify(['tries|tries: 20 from the floor (his usual 19 at those minutes) · 3 of 8 from three · 5 of 6 from the line', '', '', 'this:tries|tries: 19 from the floor (his usual 18 at those minutes) · 3 of 7 from three · 6 of 7 from the line'])
      && propsT.triesHead === '· what the box says happened, the biggest factor first, the tries in their own colour' && propsT.triesHeadCls === 'tries' && propsT.triesStored === 'tries: 19 from the floor (his usual 18 at those minutes) · 3 of 7 from three · 6 of 7 from the line',
      'props: the tries (7 Nov 2026): a game\'s seventh element and the grade file\'s eighth land in the what-happened cell in their own class after the factors, the heading says so, and the graded night\'s tries are kept on the row for the market', JSON.stringify({ cells: propsT.triesCells, head: propsT.triesHead, cls: propsT.triesHeadCls, stored: propsT.triesStored }));
  chk(/loaded: 2 new.*Last season's ledger, nba-ledger-202526\.json, was not read by this run: 1 of the 1 projections rest on this season's two or three games a player, and 1 prop has no history at all\. The run was started in C:\\Users\\J\\slate: copy the file into that folder, beside slate\.py, run the props again before tip, and load the new file; it replaces these\./.test(propsT.thinMsg),
      'props: a file whose projections rest on this season alone says last season\'s ledger was not read, names the folder the run was started in (12 Nov 2026) and says what to do', propsT.thinMsg.slice(0, 600));
  chk(/loaded: 1 new, 0 replaced, 0 graded and left as they were, 1 on 1 game already under way left out \(in-play lines; the calls made before tip stand\)/.test(propsT.inPlay.msg) && propsT.inPlay.names.join(',') === 'Paul George',
      'props: a file written after a game tipped leaves that game\'s props out and says so, and keeps the games still to come', JSON.stringify(propsT.inPlay));
  chk(/None of the 1 props has a projection\. The run read 0 games of 2026-27 and 0 of 2025-26 in C:\\Users\\J\\Downloads\. Last season's ledger, nba-ledger-202526\.json, was not read\. With a game or two this season nobody has the sixty minutes a projection needs, so every prop reads no history\. Put that file back in the slate folder beside slate\.py, with this season's ledger beside it, run the props again/.test(propsT.noneMsg),
      'props: a file that projects nothing says last season\'s ledger was not read, names the folder the run saw, and says what to put back', propsT.noneMsg.slice(0, 500));
  chk(/Nothing graded yet/.test(propsT.tabEmpty0) && /^Every prop with a side 1-1 says 54\.6% · does 50\.0%/i.test(propsT.tabCalib) && /BET band 1-0 says 56\.0% · does 100\.0%/i.test(propsT.tabCalib)
      && /^PROPS-TAB:Every prop with a side\|BET band\|BET band, one bet a man a night\|No edge: the book's own side(\|Same-game pairs, at the parlay price)?\|His last three against the pick \(shown, not scored\)$/.test(propsT.tabBlocks[0])   // the one-a-man tile beside the band (10 Nov 2026)   // the form tile off Trae Young's block (7 Nov 2026): his last three ran 1 of 3 over, against his OVER && propsT.tabBlocks[1] === 'PROPS-MK:points|rebounds|assists' && propsT.tabBlocks[2] === 'PROPS-EDGE:3 to 6 points|no edge'
      && propsT.tabBlocks[3] === 'PROPS-CENTRE:Called at the mean, to 21 Oct' && propsT.nights.length === 1 && /^Oct 21 1-1 1 void 54\.6% 50\.0% [-−]0\.1u 1-0 \+0\.9u —$/.test(propsT.nights[0])
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
  chk(propsT.whyOpen.length === 1 && /27\.9 points per 36/.test(propsT.whyOpen[0]) && /10-15 @ MIA 34 26 won by 3 · 34 min \(his usual 33\) tries: 20 from the floor/.test(propsT.whyOpen[0]) && /fanatics carded 24\.5 [-−]110 [-−]110 draftkings 25\.5 [-−]115 [-−]105/.test(propsT.whyOpen[0]) && /what happened/i.test(propsT.whyOpen[0]),
      'props: a click on a table row opens the prop\'s panel with the reasons, the last games and every book\'s line; the what-happened column shows because one seeded game carries the factors and the tries (7 Nov 2026)', JSON.stringify(propsT.whyOpen));
  chk(!propsT.tileBefore, 'props: no record tile before anything is graded', '');
  chk(propsT.after[0][2] === 'win' && propsT.after[0][3] === 28 && propsT.after[2][2] === 'loss' && propsT.after[2][3] === 9 && propsT.after[1][2] === 'void',
      'props: the grade file\'s box grades each prop by its side (28 over 24.5 wins; 9 rebounds beat the under 7.5), and a player with no box line is void', JSON.stringify(propsT.after));
  chk(/Every prop with a side 1-1 says 54\.6% · does 50\.0%/i.test(propsT.tileText) && /BET 1-0 \+0\.9u/.test(propsT.tileText) && /no edge 0-1 [-−]1\.0u/.test(propsT.tileText) && /over 1-0 · under 0-1/.test(propsT.tileText) && /points 1-0/i.test(propsT.tileText) && /rebounds 0-1/i.test(propsT.tileText) && /assists 0-0 pushes only · 1 void/i.test(propsT.tileText),
      'props: the record tile keeps the props by band, side and market, the void counted apart', propsT.tileText.slice(0, 500));
  chk(/3 props graded on the Props tab/.test(propsT.slateMsg), 'props: the slate message says how many props the grade file graded', propsT.slateMsg.slice(-160));
  chk(propsT.restored === 1 && propsT.viewOff && propsT.colsBack && propsT.nbaPressed === 'true', 'props: a backup\'s props restore, and a sport button brings the matchup columns back', JSON.stringify({ restored: propsT.restored, off: propsT.viewOff, cols: propsT.colsBack, nba: propsT.nbaPressed }));
  chk(propsT.best.length >= 1 && !/Kalshi/i.test(propsT.best[0]) && propsT.whyOpen.length === 1 && !/Kalshi/i.test(propsT.whyOpen[0]),
      'props: Kalshi is off the props (5 Nov 2026): a prop that still carries a ladder from a 4 Nov file shows no crowd line on the best card and no crowd tile on its panel', JSON.stringify({ best: (propsT.best[0] || '').slice(-200), panel: (propsT.whyOpen[0] || '').slice(0, 200) }));
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
    const sides = [...document.querySelectorAll('#propsTable tr[data-prop]')].map(tr => tr.querySelectorAll('td')[1].textContent.trim().replace(/\s+[A-Z]$/, '') + ' ' + tr.querySelectorAll('td')[4].textContent.trim());
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
    sel('propsBand', 'LEAN'); sel('propsQ', 'george'); await wait();
    const view4 = { names: cells(1), bands: cells(10), shown: document.getElementById('propsShown').textContent };
    document.getElementById('propsReset').click(); await wait();
    const view5 = { rows: document.querySelectorAll('#propsTable tbody tr[data-prop]').length, shown: document.getElementById('propsShown').textContent, stored: localStorage.getItem('callsheet3.props.view.v1'), mk: document.getElementById('propsMk').value, q: document.getElementById('propsQ').value };
    const saved = smStore.getItem('callsheet3.props.v1');
    const tileAfter = !!document.querySelector('#calibBox .calib[data-sport="PROPS"]');
    document.getElementById('m-nba').click(); await wait();
    document.getElementById('m-props').click(); await wait();
    const after = document.getElementById('propsCount').textContent;
    document.getElementById('m-nba').click(); await wait();
    return { on, count, msg, best, rows, rowsAll, sides, whys, saved, tileSame: tileBefore === tileAfter, before, after, view1, view2, view3, view4, view5 };
  });
  const pct = (s) => parseFloat(String(s).replace('%', ''));
  chk(propsEx.view1.markets.length >= 1 && propsEx.view1.markets.every(m => m === 'rebounds') && /of 8 shown$/.test(propsEx.view1.shown)
      && propsEx.view2.chances.length === 8 && propsEx.view2.chances.slice(0, 7).every((c, i) => isNaN(pct(c)) ? false : pct(c) >= (isNaN(pct(propsEx.view2.chances[i + 1])) ? -1 : pct(propsEx.view2.chances[i + 1]))) && /Chance ▾/.test(propsEx.view2.head) && /sorted by chance ▾/.test(propsEx.view2.shown) && propsEx.view2.order.sort === 'chance'
      && propsEx.view3.chances.filter(c => !isNaN(pct(c))).every((c, i, a) => i === 0 || pct(c) >= pct(a[i - 1]))
      && propsEx.view4.names.every(n => /George/.test(n)) && propsEx.view4.bands.every(b => b === 'LEAN') && propsEx.view4.names.length >= 1
      && propsEx.view5.rows === 8 && propsEx.view5.shown === '8 shown' && propsEx.view5.stored === null && propsEx.view5.mk === '' && propsEx.view5.q === '',
      'props table: the market filter keeps the rebounds, a click on Chance sorts it high to low and again low to high, the band and name filters narrow it, and Reset view puts it back', JSON.stringify({ v1: propsEx.view1, v2: { head: propsEx.view2.head, shown: propsEx.view2.shown, chances: propsEx.view2.chances }, v3: propsEx.view3, v4: propsEx.view4, v5: propsEx.view5 }));
  chk(propsEx.on && /^EXAMPLE · 8 props on/.test(propsEx.count) && /An example/.test(propsEx.msg) && propsEx.rows === 7 && propsEx.rowsAll === 8,
      'props example: eight props on 76ers @ Knicks, seven projected (Embiid is out), the count says EXAMPLE', JSON.stringify({ count: propsEx.count, rows: propsEx.rows, all: propsEx.rowsAll }));
  chk(propsEx.best.length === 2 && /#1 · LEAN .*Karl-Anthony Towns UNDER 11\.5 rebounds 53\.2% · [-−]105 needs 51\.2% · edge \+2\.0/.test(propsEx.best[0]) && /#2 · LEAN .*Paul George UNDER 2\.5 threes 55\.4% · [-−]115 needs 53\.5% · edge \+1\.9/.test(propsEx.best[1])
      && !propsEx.best.some(b => /OG Anunoby|Tyrese Maxey|Mikal Bridges|Kelly Oubre|Jalen Brunson/.test(b))
      && propsEx.sides.length === 8 && propsEx.sides.filter(s => / OVER$/.test(s)).length === 2 && propsEx.sides.some(s => /^Jalen Brunson OVER$/.test(s)) && propsEx.sides.some(s => /^Tyrese Maxey OVER$/.test(s)) && propsEx.sides.filter(s => / UNDER$/.test(s)).length === 5 && propsEx.sides.filter(s => /Joel Embiid listed Out/.test(s)).length === 1,
      'props example: with the over\'s shade off and the model a fifth of the say (5 Nov 2026) the sheet chooses on the prop\'s own evidence again, both ways: Brunson\'s and Maxey\'s points read OVER in the table, five props UNDER, Embiid\'s row says he is out, and the best list holds the two that clear their price, Towns\' under first (the books a point under the carded line) and George\'s under at -115 second; Brunson\'s over, level with its price until the levers were corrected, sits 0.3 under it (13 Nov 2026); no prop reaches the BET band', JSON.stringify({ best: propsEx.best.map(b => b.slice(0, 90)), sides: propsEx.sides }));
  chk(propsEx.whys.some(w => /who is out against his last 5: newly out: Joel Embiid \(31 mpg, with him in 4 of his last 5\); back: Jared McCain \(28 mpg, missed 3 of his last 5\): [-−]1\.4 minutes \(0\.00 a 30 mpg newly out and 2\.52 off a 30 mpg back for a man who started all of them on 36\.6 minutes/.test(w))
      && propsEx.whys.some(w => /his club's regulars out tonight run 31 minutes a game against the league's 21 on the day's report: \+1\.2% on his points rate \(3\.5% a 30 mpg\), \+0\.33 points per 36/.test(w))
      && propsEx.whys.some(w => /Josh Hart is Day-To-Day: counted 45% out \(a regular so listed played 46 nights in 76 on the graded nights\)/.test(w)) && !propsEx.whys.some(w => /the pooled rule|not counted as out/.test(w))
      && propsEx.whys.some(w => /the game's pace 97\.0 \(their 99\.5, Knicks's 98\.0, the league's 100\.5\) against their own: x0\.975, carried at 65% beside the defence's table/.test(w) && /: x0\.984/.test(w))
      && propsEx.whys.some(w => /blended with last season's 27\.7 \(1000 of 1909 minutes at a quarter, weight 250, last season's 28\.5 at x0\.970, how the men with both seasons are running this season\): 27\.7 per 36/.test(w))
      && propsEx.whys.some(w => /listed Out on ESPN: no projection/.test(w))
      && propsEx.whys.some(w => /Knicks allow 0\.97x the league's points per minute to guards \(this season 0\.95 over 16 games, last season 0\.99\): x0\.978 at 0\.75 weight, measured/.test(w)) && propsEx.whys.some(w => /HashtagBasketball: 76ers allow/.test(w)),
      'props example: the why lines are the slate\'s own, as the levers were corrected (13 Nov 2026): who is out against his last five (Embiid newly out, a regular back) and against the league\'s night, a man listed day-to-day by his chance, pace at its share, last season\'s rate at this season\'s level, the defence factor, the website\'s rank and the listed-out man', JSON.stringify(propsEx.whys.slice(0, 2)).slice(0, 600));
  chk(propsEx.saved === null && propsEx.tileSame && propsEx.after === propsEx.before, 'props example: nothing is saved or graded, and a sport button puts it away', JSON.stringify({ saved: propsEx.saved, same: propsEx.tileSame, before: propsEx.before, after: propsEx.after }));

  // ---- the prop's own panel (21 Oct 2026): a best-prop card opens it, a table row still folds its why, Escape or Close puts it away
  const propsDlg = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 60));
    document.getElementById('m-props').click(); await wait();
    document.getElementById('propsExample').click(); await wait();
    const dlg = document.getElementById('propDetail'), hidden0 = dlg.hidden;
    const card = [...document.querySelectorAll('#propsBest .pk')].find(e => /Paul George/.test(e.textContent)), id = card.getAttribute('data-prop');
    card.click(); await wait();
    const open = !dlg.hidden, text = document.getElementById('propDetailBody').innerText.replace(/\s+/g, ' ').trim();
    const tiles = [...dlg.querySelectorAll('.pd-tiles .pd-tile .k')].map(e => e.textContent);
    // recent form (5 Nov 2026): his last three against the line on the card and the panel, shown, not scored
    const formCard = ((card.querySelector('.n5.formline') || {}).textContent || ''), formCardCls = ((card.querySelector('.n5.formline') || {}).className || ''), formPanel = ((dlg.querySelector('.pd-form') || {}).textContent || '').replace(/\s+/g, ' ').trim(), formPanelCls = ((dlg.querySelector('.pd-form') || {}).className || '');
    const formWhy = ([...dlg.querySelectorAll('ul.pd-why li')].map(e => e.textContent.replace(/\s+/g, ' ').trim()).find(t => /^his last 3 games/.test(t)) || '');
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
             n: trs.length, rowNames, rowOpen, name0, pos0, prevOff0, navShown, name1, pos1, prevOff1, name2, name1b, nextOffLast, posLast, formCard, formCardCls, formPanel, formPanelCls, formWhy };
  });
  chk(/^His last 3: \d+ · \d+ · \d+ against 2\.5 · [0-3] of 3 over(, [1-3] on it)?(, with the UNDER|, against the UNDER|, split)$/.test(propsDlg.formCard) && /^n5 formline( pos| neg)?$/.test(propsDlg.formCardCls)
      && ((/, with the UNDER$/.test(propsDlg.formCard) && /formline pos$/.test(propsDlg.formCardCls)) || (/, against the UNDER$/.test(propsDlg.formCard) && /formline neg$/.test(propsDlg.formCardCls)) || (/, split$/.test(propsDlg.formCard) && propsDlg.formCardCls === 'n5 formline'))
      && propsDlg.formPanel.indexOf(propsDlg.formCard) === 0 && /· shown, not scored: it did not help the bet as a lever walk-forward \(5 Nov 2026\), so it is measured on the record tile's own line$/.test(propsDlg.formPanel) && propsDlg.formPanelCls.replace('note ', '').replace('pd-form', 'n5 formline') === propsDlg.formCardCls
      && /^his last 3 games: \d+, \d+, \d+ against 2\.5 \([0-3] of 3 over(, [1-3] on it)?\): shown, not scored \(5 Nov 2026: read as a push on the projection or on the book's chance it did not help the bet walk-forward on seven nights of logs; its own line on the record tile is the measure\)/.test(propsDlg.formWhy),
      'props detail: recent form (5 Nov 2026) reads his last three games against the line on George\'s card and his panel, green with the pick and red against it, split when neither side has two, with the why line saying it is shown, not scored', JSON.stringify({ card: propsDlg.formCard, cls: propsDlg.formCardCls, panel: propsDlg.formPanel, pcls: propsDlg.formPanelCls, why: propsDlg.formWhy }));
  chk(propsDlg.simTiles.length === 4 && /^The books=2\.5\|3 post it · fanatics 2\.5, with them\|pd-tile$/.test(propsDlg.simTiles[0]) && /^PHI points=113\|implied by the book's total and spread · 112\.9 a game by the ratings \(×1\.001, shown: measured null as a lever\)\|pd-tile$/.test(propsDlg.simTiles[1])
      && /^Expected margin=10\.9\|off the spread · a starter's minutes follow it \(the game script, scored\)\|pd-tile$/.test(propsDlg.simTiles[2]) && /^Blowout=27%\|15 or more either way, off the spread\|pd-tile$/.test(propsDlg.simTiles[3])
      && /^THE MARKET ON THIS GAME · the books' numbers in the simulation's old place; the consensus is the scored part /i.test(propsDlg.simText) && /The simulation came off the props on 5 Nov 2026/.test(propsDlg.simText)
      && /What the score takes from the market now is the books' consensus/.test(propsDlg.simText) && propsDlg.simBeforeWhy,
      'props detail: the market on the game takes the simulation\'s old place on the panel (5 Nov 2026): the books\' consensus with the carded line level with it on George\'s threes (so no lever tile), his club\'s points implied by the total and spread against the ratings\' number, the expected margin that sets the game script, the blowout chance off the spread, and the paragraph that says what came off and what is scored, before the why',
      JSON.stringify({ tiles: propsDlg.simTiles, text: propsDlg.simText.slice(0, 700), beforeWhy: propsDlg.simBeforeWhy }));
  chk(propsDlg.rowOpen && propsDlg.navShown && propsDlg.name0.indexOf(propsDlg.rowNames[0]) === 0 && propsDlg.pos0 === '1 of ' + propsDlg.n && propsDlg.prevOff0
      && propsDlg.name1.indexOf(propsDlg.rowNames[1]) === 0 && propsDlg.pos1 === '2 of ' + propsDlg.n && !propsDlg.prevOff1 && propsDlg.name2.indexOf(propsDlg.rowNames[2]) === 0 && propsDlg.name1b === propsDlg.name1
      && propsDlg.nextOffLast && propsDlg.posLast === propsDlg.n + ' of ' + propsDlg.n && /^\d+ of \d+$/.test(propsDlg.fromCardPos),
      'props detail: a row of the Every-prop table opens the same panel, Next and the arrow keys walk the table\'s order with the position shown, Previous is off on the first and Next on the last, and a card opened from the best list knows its place too',
      JSON.stringify({ n: propsDlg.n, rows: propsDlg.rowNames, name0: propsDlg.name0, pos0: propsDlg.pos0, name1: propsDlg.name1, pos1: propsDlg.pos1, name2: propsDlg.name2, back: propsDlg.name1b, last: propsDlg.posLast, card: propsDlg.fromCardPos }));
  chk(propsDlg.levers.length === 4 && /^lever helps top\|Who is out biggest lever\|[-−]0\.1$/.test(propsDlg.levers[0]) && propsDlg.levers.some(l => /^lever helps\|Pace\|[-−]0\.0$/.test(l)) && propsDlg.levers.some(l => /^lever (hurts|helps)\|Defence v position\|[-−+]0\.0$/.test(l))
      && propsDlg.levers.some(l => /^lever (hurts|helps)\|The game script, from the spread\|[-−+]0\.0$/.test(l)) && !propsDlg.levers.some(l => /matchup|prior|Minutes/.test(l))
      && /^Starts from 2\.05, his 2\.17 per 36 at his minutes; the regulars out, the game script, pace and the defence take it to 1\.97, [-−]0\.5 against the line\. Green pushes toward the UNDER, red away from it: the measured levers only \(5 Nov 2026\)\. Inside the start, not a lever: Last season's prior on his rate \+0\.1 · Minutes, his last 5 against the season \+0\.0\.$/.test(propsDlg.base)
      && propsDlg.boldWhy.length === 1 && /^who is out against his last 5: newly out/.test(propsDlg.boldWhy[0]) && !propsDlg.boldWhy.some(w => /^the game's pace|^2\.0 threes/.test(w))
      && propsDlg.againstWhy.length === 0   // nothing against the under is big enough to tag: the defence and the script each move it 0.02 or less
      && /the biggest reason for the UNDER in green$/.test(propsDlg.whyHead.trim()) && !/against it in red/.test(propsDlg.whyHead)   // the heading names only what the list tags
      && propsDlg.boldTags.length === 1 && /^who is out a→the biggest for the UNDER\|/.test(propsDlg.boldTags[0])
      && propsDlg.boldTags.every(t => /\|rgb\(\d+, \d+, \d+\)\|600$/.test(t)) && propsDlg.boldTags[0].split('|')[1] !== 'rgb(0, 0, 0)'
      && /^Moves it: Who is out [-−]0\.1 · Pace [-−]0\.0$/.test(propsDlg.cardLever),
      'props detail: what moves it keeps the measured levers only (5 Nov 2026): the regulars out, the game script off the spread, pace and the defence on George\'s threes, with last season\'s prior and the minutes trend named as what sits inside the start and no matchup lever; the biggest lever toward the UNDER (who is out, 13 Nov 2026: Embiid newly out gives a 34-minute starter nothing and McCain back takes 1.2 minutes) bolds its why line in green with a tag, nothing against it is big enough to tag in red, and the card names the top two levers by size', JSON.stringify({ levers: propsDlg.levers, base: propsDlg.base, bold: propsDlg.boldWhy, tags: propsDlg.boldTags, against: propsDlg.againstWhy, head: propsDlg.whyHead, card: propsDlg.cardLever }));
  chk(propsDlg.hidden0 && propsDlg.open && propsDlg.noscroll && /^LEAN Paul George F PHI( starter)? UNDER 2\.5 threes 76ers @ Knicks/.test(propsDlg.text) && /on the road at NYK/.test(propsDlg.text) && /Why /i.test(propsDlg.text)
      && propsDlg.tiles.join(',') === 'Chance,Price,Edge,Projection,Minutes,Per 36,Usage' && propsDlg.marks === 10 && propsDlg.books === 3 && /fanatics/.test(propsDlg.carded),
      'props detail: a best-prop card opens the prop on its own panel with the tiles, the why, the marked last games and every book', JSON.stringify(propsDlg).slice(0, 1500));
  chk(propsDlg.closedEsc && propsDlg.closedBtn && propsDlg.closedSport, 'props detail: Escape, the Close button and a sport button each put the panel away', JSON.stringify({ esc: propsDlg.closedEsc, btn: propsDlg.closedBtn, sport: propsDlg.closedSport }));

  // ---- an NBA row re-scored while another game sits in the form keeps its own clubs' names (21 Oct 2026) ----
  const relabel = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 60));
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    await smStore.removeItem('callsheet3.card.v1');
    document.getElementById('clear').click(); document.getElementById('m-nba').click(); await wait();
    set('gdate', '2026-10-20'); set('away', 'Celtics'); set('home', 'Pistons'); set('line', '213'); set('op', '-215'); set('up', '170');
    set('sp', '1.5'); set('sph', '-110'); set('spa', '-110'); set('hml', '100'); set('aml', '-120'); await wait();
    document.getElementById('add').click(); await wait();
    // another sport's game in the form while a slate merges into the basketball row on the card (hockey until 30 Oct 2026, baseball since)
    document.getElementById('clear').click(); document.getElementById('m-mlb').click(); await wait();
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
    // a row the old page wrote: another game's names on the moneyline and the spread, to be relabelled on load
    const broken = JSON.parse(smStore.getItem('callsheet3.card.v1'));
    broken.forEach(r => r.markets.forEach(m => { if (m.key === 'ml') { m.pick = 'Islanders ML'; m.other.pick = 'Ducks ML'; } if (m.key === 'spread') { m.pick = 'Islanders +1.5'; m.label = 'Spread Islanders: +1.5'; m.other.pick = 'Ducks -1.5'; } }));
    await smStore.setItem('callsheet3.card.v1', JSON.stringify(broken));
    return { merged: row.inputs.narest === '1' && row.inputs.nhrest === '2', sides, formAway: document.getElementById('away').value, refresh };
  });
  chk(relabel.refresh.lu1 && relabel.refresh.rest1 === '1' && relabel.refresh.lu2 && relabel.refresh.rest2 === '1' && relabel.refresh.out1 && relabel.refresh.out2 && relabel.refresh.sim1 && relabel.refresh.sim2,
      'slate reload: a later slate replaces the starting five, the injury report and the simulation on a carded row (expected to confirmed, questionable to out, the newer runs) and leaves the filled boxes as logged', JSON.stringify(relabel.refresh));
  await reloaded(); await pg.evaluate(() => smStore.ready);
  const relabelled = await pg.evaluate(async () => {
    const row = JSON.parse(smStore.getItem('callsheet3.card.v1')).find(r => /Celtics @ Pistons/.test(r.matchup));
    const out = row.markets.filter(m => m.key === 'ml' || m.key === 'spread').map(m => ({ key: m.key, side: m.side, pick: m.pick, other: (m.other || {}).pick, label: m.label }));
    await smStore.removeItem('callsheet3.card.v1');
    return out;
  });
  const ownClubs = (s) => s.length === 2 && s.every(m => (m.side === 'HOME' ? /^Pistons /.test(m.pick) && /^Celtics /.test(m.other) : /^Celtics /.test(m.pick) && /^Pistons /.test(m.other)))
    && s.find(m => m.key === 'spread').label === 'Spread Pistons: +1.5' && /^(Pistons \+1\.5|Celtics -1\.5)$/.test(s.find(m => m.key === 'spread').pick) && /^(Pistons|Celtics) ML$/.test(s.find(m => m.key === 'ml').pick);
  chk(relabel.merged && relabel.formAway === 'Ducks' && ownClubs(relabel.sides),
      'nba: a card row re-scored by a slate while another game sits in the form keeps its own clubs on the moneyline and the spread', JSON.stringify(relabel));
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
    document.getElementById('clear').click(); document.getElementById('m-mlb').click(); await wait();   // the baseball example since 30 Oct 2026 (the hockey one until then)
    set('gdate', '2026-11-12'); document.getElementById('example').click(); await wait(); set('gdate', '2026-11-12');
    document.getElementById('add').click(); await wait();
    document.getElementById('boardDate').value = '2026-11-12'; document.getElementById('boardDate').dispatchEvent(new Event('change')); await wait();
    const head0 = document.getElementById('takingHead').hidden, btns0 = document.querySelectorAll('#board tbody tr .takebtn').length, rows0 = document.querySelectorAll('#board tbody tr').length;
    const tr0 = document.querySelector('#board tbody tr'), pick0 = tr0.querySelectorAll('td')[3].querySelector('.chip').textContent.trim();
    set('line', '6'); await wait();   // the form now differs from the row: a row click would put the row's 6.5 back
    tr0.querySelector('.takebtn').click(); await wait();
    const lineAfter = document.getElementById('line').value;
    const mine = () => JSON.parse(smStore.getItem('callsheet3.card.v1')).filter(r => /Rays @ Yankees/.test(r.matchup) && r.gdate === '2026-11-12');   // rows from earlier checks sit on the card too
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
    set('line', '6.5'); await wait(); document.getElementById('add').click(); await wait();
    const takes3 = mine()[0].markets.filter(m => m.take).map(m => m.key + ':' + m.take.side), nRows = mine().length;
    // the copy button speaks, with or without a clipboard
    document.getElementById('takingText').click(); await new Promise(r => setTimeout(r, 250));
    const said = document.getElementById('saveMsg').textContent;
    // grade the game 2-3: the mark grades on its card, the button becomes a TAKEN chip, and What you took keeps the line
    const trc = () => [...document.querySelectorAll('#cardTable tr')].find(t => /Rays @ Yankees/.test(t.textContent));
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
  chk(takeT.head0 && takeT.btns0 === takeT.rows0 && takeT.rows0 > 0 && takeT.lineAfter === '6' && takeT.takes1.length === 1 && new RegExp('^(total|f5|ml|rl):(OVER|UNDER|HOME|AWAY):' + takeT.pick0.replace(/[.+\-]/g, '\\$&') + ':[-−]?\\d+:true$').test(takeT.takes1[0])
      && takeT.on1 && !takeT.head1 && takeT.count1 === '1 marked' && takeT.list1.length === 2 && /^TAKING · MLB · marked /.test(takeT.list1[0]) && takeT.list1[0].indexOf(takeT.pick0) > 0 && /Rays @ Yankees/.test(takeT.list1[0]) && /Taking$/i.test(takeT.list1[0])
      && /^TONIGHT 1 bet marked none graded yet · one unit each 1 on the card, 0 from the simulation, 0 props$/.test(takeT.list1[1]) && takeT.cardOn >= 1,
      'take: a Take button on every priced row of the board marks the pick as shown without opening the row; the row lights, the same market\'s card lights, and Taking tonight lists it with a summary card', JSON.stringify(takeT).slice(0, 1200));
  chk(takeT.takes2.length === 1 && takeT.takes2[0] === takeT.takes1[0].split(':').slice(0, 2).join(':') && takeT.takes3.length === 1 && takeT.takes3[0] === takeT.takes2[0] && takeT.nRows === 1 && /Copied the bets you are taking|the text is below/.test(takeT.said),
      'take: the mark rides through a rescore and through the same game added again, and the copy button speaks', JSON.stringify({ t2: takeT.takes2, t3: takeT.takes3, rows: takeT.nRows, said: takeT.said.slice(0, 80) }));
  chk(takeT.list3.length === 2 && /(WIN|LOSS|PUSH|win|loss|push)/.test(takeT.res3) && takeT.res3.toLowerCase() === takeT.boardRes.toLowerCase() && takeT.chip3 === 'TAKEN' && takeT.btn3 === 0 && takeT.otherBtns === 0
      && takeT.took.length === 1 && new RegExp('^Game bets taken ' + (takeT.res3.toLowerCase() === 'win' ? '1-0' : takeT.res3.toLowerCase() === 'loss' ? '0-1' : '0-0-1') + ' ', 'i').test(takeT.took[0]) && /says \d+\.\d% · does \d+\.\d% \(±\d+\.\d\) · [-−+]\d\.\d\du$/.test(takeT.took[0])
      && new RegExp('graded ' + (takeT.res3.toLowerCase() === 'win' ? '1-0' : takeT.res3.toLowerCase() === 'loss' ? '0-1' : '0-0-1') + ' · ').test(takeT.list3[1]),
      'take: once the game grades the marked bet shows its result on its card and the board, the button becomes a TAKEN chip, no mark can be added to the graded row, and What you took keeps the record at the price marked', JSON.stringify({ list3: takeT.list3, res: takeT.res3, board: takeT.boardRes, chip: takeT.chip3, took: takeT.took, other: takeT.otherBtns }));
  await reloaded(); await pg.evaluate(() => smStore.ready);
  const takeR = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 90));
    document.getElementById('boardDate').value = '2026-11-12'; document.getElementById('boardDate').dispatchEvent(new Event('change')); await wait();
    const list = [...document.querySelectorAll('#taking .pk')].map(e => e.innerText.replace(/\s+/g, ' ').trim()), hidden = document.getElementById('takingHead').hidden;
    // the props: the example's best card, the table row and the panel each carry the button; Taking lists the mark; the board's Taking tonight lists it on the props' date
    document.getElementById('m-props').click(); await wait(); document.getElementById('propsExample').click(); await wait();
    const card = () => [...document.querySelectorAll('#propsBest .pk')].find(e => /Paul George/.test(e.textContent)), id = card().getAttribute('data-prop');   // re-found after every re-render
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
  chk(!takeR.hidden && takeR.list.length === 2 && /^TAKING · MLB/.test(takeR.list[0]), 'take: the mark survives a reload of the page', JSON.stringify({ hidden: takeR.hidden, list: takeR.list }));
  chk(takeR.pHead0 && takeR.pBtns === 7 && takeR.pRows === 7 && !takeR.dlgOpen && takeR.pList.length === 1 && /^TAKING · NBA PROP · LEAN · marked \d{1,2}:\d\d [AP]M Paul George UNDER 2\.5 threes 5\d\.\d% · [-−]115 needs 53\.5% 76ers @ Knicks · fanatics · projected \d\.\d\d .*Taking$/i.test(takeR.pList[0])
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
    const card = () => [...document.querySelectorAll('#propsBest .pk')].find(e => /Paul George/.test(e.textContent)), id = card().getAttribute('data-prop');
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
  chk(leverT.head === 'Levers' && leverT.maxeyCell === '1▲ 0▼' && !/\b(neg|pos)\b/.test(leverT.maxeyCls) && /\bagree\b/.test(leverT.maxeyCls) && leverT.maxeyTitle === '1 of 1 lever toward the UNDER' && leverT.tag === 'levers 1▲ 0▼' && leverT.tagTitle === leverT.maxeyTitle
      && leverT.all.length === 7 && leverT.all.every(s => /^\d+▲ \d+▼$/.test(s)) && leverT.all.some(s => s === '3▲ 2▼') && /^What moves it · 1 of 1 lever toward the UNDER$/.test(leverT.h4.replace(/\s+/g, ' ').trim()),
      'levers: the Every-prop table counts the measured levers toward the pick and against (George 1 up and none down: who is out, a regular back, with the prior and the minutes trend read as what sits inside the start, 5 Nov 2026, and the pace, the defence and the script too small to count, 13 Nov 2026; Towns\' under 3 up 2 down with the books\' consensus a lever of its own), the best card carries the tally as a tag and the panel\'s heading says it in words', JSON.stringify(leverT).slice(0, 900));
  chk(/Levers ▾/.test(leverT.headOn) && leverT.scores.every((s, i, a) => i === 0 || s <= a[i - 1]) && leverT.scores[0] > leverT.scores[leverT.scores.length - 1]
      && leverT.onlyAll.every(s => /^\d+▲ 0▼$/.test(s)) && leverT.onlyAll.length < leverT.all.length && /^\d+ of 7 shown/.test(leverT.shownAll)
      && leverT.onlyMost.length >= leverT.onlyAll.length && leverT.onlyMost.every(s => { const m = /^(\d+)▲ (\d+)▼$/.exec(s); return m && +m[1] > +m[2]; }) && leverT.stored.agree === 'most' && leverT.after.rows === 7 && leverT.after.agree === '',
      'levers: the column sorts with the most agreement first, the filter keeps the props where every lever leans the pick\'s way or more do than not, the view is remembered and Reset view clears it', JSON.stringify({ head: leverT.headOn, scores: leverT.scores, all: leverT.onlyAll, most: leverT.onlyMost, shown: leverT.shownAll, stored: leverT.stored, after: leverT.after }));

  // ---- 26 Oct 2026: usage and role on the prop, the floors, and the same-game pairs ----
  const usageT = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 90));
    document.getElementById('propsReset').click(); await wait();
    document.getElementById('m-props').click(); await wait(); document.getElementById('propsExample').click(); await wait();
    const card = () => [...document.querySelectorAll('#propsBest .pk')].find(e => /Paul George/.test(e.textContent));
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
  chk(/^Paul George F PHI starter$/.test(usageT.h3) && usageT.role === "RotoWire's expected five" && /^Usage=22\.5%\|of his club's possessions while on; a starter$/.test(usageT.usage)
      && usageT.floors === ''
      && /^usage 22\.5% of his club's possessions \(this season\), a starter \(RotoWire's expected five\): a mid-usage starting man's miss runs 1\.00 sigmas, measured, so the chance is read as it is$/.test(usageT.why),
      'props: the panel carries his role as a tag, his usage as a tile (a mid-usage starter on threes: the miss read as it is, no floors on a threes line), and the why line', JSON.stringify({ h3: usageT.h3, role: usageT.role, usage: usageT.usage, floors: usageT.floors.slice(0, 200), why: usageT.why }));
  chk(usageT.aligned && usageT.usgCells.length === 7 && usageT.usgCells.some(c => /^Tyrese:29% S:usgc pos$/.test(c)) && usageT.usgCells.some(c => /^Kelly:19% B:usgc$/.test(c)) && usageT.usgCells.every(c => /:\d+(\.\d)?% [SB]:usgc( pos)?$/.test(c))
      && usageT.usgSorted.length === 7 && usageT.usgSorted.every((u, i, a) => i === 0 || u <= a[i - 1]) && /sorted by usage ▾/.test(usageT.usgShown)
      && usageT.hi.length === 3 && usageT.hi.every(n => /Jalen Brunson|Karl-Anthony Towns|Tyrese Maxey/.test(n)) && usageT.bench.length === 1 && /Kelly Oubre/.test(usageT.bench[0]) && usageT.after.n === 7 && usageT.after.usage === '' && usageT.after.role === ''
      && usageT.pairs.length >= 3 && usageT.pairs.every(p => /^PAIR #\d · 76ers @ Knicks · at (Fanatics|DraftKings|FanDuel|BetMGM) · the price (agrees|asks more) .+ \+ .+ both land \d\d\.\d% · pays [-−+]\d+ \(\d\.\d\d×\) needs \d\d\.\d% .+ · (two players|two overs on one club|one man, two markets|one man, his points with his threes), measured ×(0\.95|1\.00|1\.15|1\.50) TAKE$/.test(p.text))
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
    const best = [...document.querySelectorAll('#propsBest .pk')].map(e => { const l = e.querySelector('.n5.shopline') || e.querySelector('.n5.simline'); return (e.querySelector('.n2') || {}).textContent + '→' + (l ? l.className + '|' + l.textContent.replace(/\s+/g, ' ').trim() : 'none'); });
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
  chk(simPropsT.strip.length === 1 && /^pk simg mkt\|76ers @ Knicks · the market PHI 113 \(112\.9 a game\) · NYK 118\.5 \(115\.6 a game\) total 231\.5 · spread -5\.5 each club's points implied by the book's total and spread, against its points a game by the ratings · shown, not scored expected margin 10\.9 · blowout of 15 or more 27%, off the spread · the carded line sits off the books' consensus on 5 of 7 props$/.test(simPropsT.strip[0])
      && simPropsT.head.slice(-5).join('|') === 'Levers|Sim|Usage|Spike|Take' && simPropsT.rows.length === 7 && simPropsT.rows.every(r => /^\d+(\.\d)?$/.test(r.sim) && /^simc( pos| neg)?$/.test(r.cls) && (simGap(r) > 0) === /pos/.test(r.cls) && (simGap(r) < 0) === /neg/.test(r.cls) && /the books' consensus line across 3 books/.test(r.title))
      && simMaxey && simMaxey.side === 'OVER' && simMaxey.line === 25.5 && simMaxey.sim === '24.5' && simMaxey.cls === 'simc neg',
      'props: the market\'s strip takes the simulation\'s place above the picks (5 Nov 2026): each club\'s points implied by the book\'s total and spread against the ratings\' number, the expected margin and the blowout off the spread, and how many carded lines sit off the books\' consensus; the Sim column carries the consensus line on every projected prop, green when the carded line sits off it the pick\'s way and red against it (Maxey\'s over at 25.5 with the books at 24.5, red)', JSON.stringify({ strip: simPropsT.strip, head: simPropsT.head.slice(-4), rows: simPropsT.rows.map(r => r.name + ' ' + r.side + ' ' + r.line + ' sim ' + r.sim + ' ' + r.cls) }));
  chk(simPropsT.best.length === 2 && simPropsT.best.every(b => /→n5 shopline( pos| neg)?\|The books: 3 post \d+(\.\d)? · fanatics \d+(\.\d)? sits (with them|1 (above|below) them, (the (UNDER|OVER)'s way|against the (UNDER|OVER)) · the book's chance read [-−+]\d\.\d on the over, measured)$/.test(b))
      && simPropsT.best.filter(b => /the (UNDER|OVER)'s way/.test(b)).every(b => /shopline pos/.test(b)) && simPropsT.best.filter(b => /against the (UNDER|OVER)/.test(b)).every(b => /shopline neg/.test(b)) && simPropsT.best.filter(b => /sits with them/.test(b)).every(b => /shopline\|/.test(b))
      && simPropsT.best.filter(b => /the UNDER's way/.test(b)).length === 1 && simPropsT.best.filter(b => /the OVER's way/.test(b)).length === 0 && simPropsT.best.filter(b => /against the/.test(b)).length === 0 && simPropsT.best.filter(b => /sits with them/.test(b)).length === 1
      && simPropsT.yes.length === 2 && simPropsT.yes.every(c => c === 'simc pos') && simPropsT.no.length === 3 && simPropsT.no.every(c => c === 'simc neg') && simPropsT.yes.length + simPropsT.no.length === simPropsT.rows.filter(r => simGap(r) !== 0).length
      && simPropsT.sorted.length === 7 && simPropsT.sorted[0].name === simBig.name && simPropsT.sorted[0].mk === simBig.mk && simPropsT.sorted.every((r, i, a) => i === 0 || simGap(r) <= simGap(a[i - 1])) && /sorted by sim ▾/.test(simPropsT.shown)
      && simPropsT.after.sim === '' && simPropsT.after.n === 7 && !/sorted/.test(simPropsT.after.shown),
      'props: every best card ends with the books\' consensus against the carded line, green when it sits the pick\'s way and red against it (Towns\' under lifted, George\'s level; Brunson\'s over, lifted too, is off the list since the levers were corrected, 13 Nov 2026), the filter keeps the props the consensus sides with (or against), the column sorts by the gap toward the pick, and Reset view clears both', JSON.stringify({ best: simPropsT.best.map(b => b.slice(0, 140)), yes: simPropsT.yes, no: simPropsT.no, sorted: simPropsT.sorted.map(r => r.name + ' ' + r.side + ' ' + r.line + ' ' + r.sim), shown: simPropsT.shown, after: simPropsT.after }));

  // ---- 26 Oct 2026: what happened on each of his last games -- the slate writes beside each game what the box says (a regular back or out,
  //      a blowout, his role, then his minutes, shots and shooting against his season's, then overtime and the pace); the panel's Last games table
  //      shows it as a column, the first factor bold, red under the line and green over it ----
  const whatT = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 90));
    document.getElementById('propsReset').click(); await wait();
    document.getElementById('m-props').click(); await wait(); document.getElementById('propsExample').click(); await wait();
    [...document.querySelectorAll('#propsTable tr[data-prop]')].find(e => /Kelly Oubre/.test(e.textContent)).click(); await wait();   // off the best list since 5 Nov 2026 (his under clears no price at the new blend): the table row opens the same panel
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
  chk(whatT.head.join('|') === 'Date|Opp|Min|points|What happened' && /^LAST GAMES \(\d+ of 10 over 14\.5\) · what the box says happened, the biggest factor first$/i.test(whatT.h4) && whatT.rows.length === 10
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
  await reloaded(); await pg.evaluate(() => smStore.ready);   // the graded fixture rows are records and stay in memory until a reload
  chk(comboT.rows.length === 3 && comboT.rows.join(';') === 'Trae Young G|pts + ast|OVER|35.5;Paolo Banchero G|reb + ast|UNDER|12.5;Trae Young G|pts + reb|OVER|27.5'
      && comboT.opts.slice(-3).join(',') === 'pr=pts + reb,pa=pts + ast,ra=reb + ast' && comboT.onlyRa.join(',') === 'reb + ast'
      && /^OVER 35\.5 pts \+ ast \|\| 28 pts \+ 9 ast = 37 · 34 min \(his usual 35\)$/.test(comboT.panel)
      && comboT.graded.join(';') === 'Trae Young pa OVER 35.5 -> win 39 | 28 pts + 11 ast = 39 · won by 6;Trae Young pr OVER 27.5 -> win 31 | 28 pts + 3 reb = 31 · won by 6;Paolo Banchero ra UNDER 12.5 -> loss 13 | '
      && /pts \+ ast 1-0/i.test(comboT.tile) && /pts \+ reb 1-0/i.test(comboT.tile) && /reb \+ ast 0-1/i.test(comboT.tile),
      'props: the combination markets list with their labels, filter by market, open their panel with the parts behind each game, grade by the sum of the box (28 + 11 = 39 over 35.5; 9 + 4 = 13 against the under 12.5) and take their own tiles in the record', JSON.stringify(comboT).slice(0, 1500));

  // ---- 27 Oct 2026: the fives and the matchup on the prop -- both clubs' starting fives on the panel with the man marked; a Matchup button on the
  //      panel and the cards, off until the NBA card has the game, then opening it into the form ----
  // an empty card in memory first (10 Nov 2026): earlier blocks add the example game dated 2026-11-10, and on that day the props example,
  // dated today, found the row; removing the stored card and loading the page again leaves none whatever the date
  await pg.evaluate(async () => { await smStore.removeItem('callsheet3.card.v1'); }); await reloaded(); await pg.evaluate(() => smStore.ready);
  const goT = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 90));
    const txt = e => (e ? e.innerText : '').replace(/\s+/g, ' ').trim();
    await smStore.removeItem('callsheet3.card.v1'); document.getElementById('clear').click(); await wait();
    document.getElementById('propsReset').click(); await wait();
    document.getElementById('m-props').click(); await wait(); document.getElementById('propsExample').click(); await wait();
    const today = document.getElementById('propsDate').value, dlg = document.getElementById('propDetail');
    const card0 = [...document.querySelectorAll('#propsBest .pk')].find(e => /Paul George/.test(e.textContent));
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
    // the crowd on the row (4 Nov 2026): the Knicks by 5.25 at even money on the ladders (57% by 3.5, 49% by 5.5), the total 229.25, the Knicks to win 69.5%
    const rung = (x, mid, vol) => [x, +(mid - 0.01).toFixed(2), +(mid + 0.01).toFixed(2), +mid.toFixed(2), vol];
    set('nbakalshi', JSON.stringify({ at: '2026-11-14T20:00:00Z', ev: 'KXNBAGAME-26NOV14PHINYK', fee: 0.07, a: { bid: 0.30, ask: 0.31, last: 0.31, vol: 5000, oi: 4000 }, h: { bid: 0.69, ask: 0.70, last: 0.70, vol: 9000, oi: 8000 },
      sp: { h: [rung(1.5, 0.66, 100), rung(3.5, 0.57, 100), rung(5.5, 0.49, 100), rung(7.5, 0.41, 100)], a: [rung(1.5, 0.26, 10), rung(3.5, 0.2, 10)] }, tot: [rung(227.5, 0.57, 100), rung(229.5, 0.49, 100), rung(231.5, 0.42, 100)],
      tt: { a: [rung(106.5, 0.58, 50), rung(108.5, 0.49, 50), rung(110.5, 0.40, 50)], h: [rung(116.5, 0.60, 50), rung(118.5, 0.52, 50), rung(120.5, 0.43, 50)] } })); await wait();   // the team totals: the 76ers 108.3 and the Knicks 118.9 at even money
    document.getElementById('add').click(); await wait();
    document.getElementById('clear').click(); await wait();
    const awayBefore = document.getElementById('away').value;
    document.getElementById('m-props').click(); await wait(); document.getElementById('propsExample').click(); await wait();
    const card1 = [...document.querySelectorAll('#propsBest .pk')].find(e => /Paul George/.test(e.textContent)), cardBtn1 = card1.querySelector('.btn.go[data-pgo]'), cardLive = cardBtn1 && !cardBtn1.classList.contains('off');
    card1.click(); await wait();
    const kalLine = dlg.querySelector('.pd-kalshi') ? txt(dlg.querySelector('.pd-kalshi')) : '', kalStrip = [...document.querySelectorAll('#propsSim .pk .kalshi-strip')].map(txt), panelKal = /Kalshi/i.test(txt(dlg)), stripKal = /Kalshi/i.test(txt(document.getElementById('propsSim')));
    document.getElementById('propDetailClose').click(); await wait();
    cardBtn1.click(); await wait();
    const propsHidden = document.getElementById('propsView').hidden, dlgHidden = dlg.hidden, away = document.getElementById('away').value, home = document.getElementById('home').value, nbaPressed = document.getElementById('m-nba').getAttribute('aria-pressed');
    const lineupPanel = txt(document.getElementById('nbaLineupPanel')).slice(0, 80);
    await smStore.removeItem('callsheet3.card.v1'); document.getElementById('clear').click(); await wait();
    return { cardOff0, cardTitle0, fives, me, heads, panelOff, panelText, takeStill, stillOpen, said, awayBefore, cardLive, propsHidden, dlgHidden, away, home, nbaPressed, lineupPanel, kalLine, kalStrip, panelKal, stripKal };
  });
  chk(goT.kalLine === '' && goT.kalStrip.length === 0 && goT.panelKal === false && goT.stripKal === false,
      'props: Kalshi is off the props (5 Nov 2026): with the crowd\'s block on the NBA card\'s row for the game, the prop\'s panel and the game\'s strip carry no crowd line (the crowd stays on the NBA card)', JSON.stringify({ line: goT.kalLine, strip: goT.kalStrip, panel: goT.panelKal, stripKal: goT.stripKal }));
  chk(goT.cardOff0 === true && /^The NBA card has no row for 76ers @ Knicks on /.test(goT.cardTitle0) && goT.fives.length === 2 && /^76ers EXPECTED PG Tyrese Maxey SG VJ Edgecombe SF Paul George THIS PROP PF Kelly Oubre Jr\. C Adem Bona May not play: C Andre Drummond \(Questionable\)\.$/i.test(goT.fives[0])
      && /^Knicks CONFIRMED PG Jalen Brunson SG Mikal Bridges SF OG Anunoby PF Josh Hart C Karl-Anthony Towns$/i.test(goT.fives[1]) && /^SF Paul George THIS PROP$/i.test(goT.me) && goT.heads.join(',') === 'lbadge exp|expected,lbadge conf|confirmed'
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
      && /^both land \d\d\.\d% · pays \+\d+ \(\d\.\d\d×\) needs \d\d\.\d%$/.test(pairT.pick) && /^76ers @ Knicks · \w{3} \d{1,2} · (two players|two overs on one club|one man, two markets|one man, his points with his threes), measured ×\d\.\d\d · both at (Fanatics|DraftKings|FanDuel|BetMGM)$/.test(pairT.sub)
      && pairT.tiles.length === 5 && /^Both land=\d\d\.\d%$/.test(pairT.tiles[0]) && /^Parlay price=\+\d+$/.test(pairT.tiles[1]) && /^Edge=\+\d\.\d$/.test(pairT.tiles[2]) && /^Leg 1=\d\d\.\d%$/.test(pairT.tiles[3]) && /^Leg 2=\d\d\.\d%$/.test(pairT.tiles[4])
      && /lands \d\d\.\d% by the sheet and .+ \d\d\.\d%, each the blended chance on its own panel\. .+ so the product carries ×\d\.\d\d: \d\d\.\d% × \d\d\.\d% × \d\.\d\d = \d\d\.\d%.*\. The ticket pays the two prices multiplied, \d\.\d\d × \d\.\d\d = \d\.\d\d×, \+\d+, which needs \d\d\.\d%: the price agrees by \d+\.\d points\. A pushed leg drops out/.test(pairT.how)
      && pairT.legs.length === 2 && pairT.legs.every(l => /^LEG [12] · .+ (OVER|UNDER) \d+\.5 [\w +]+? · [A-Z] (PHI|NYK) · (starter|bench) \|\| Chance,Price,Edge,Projection,Minutes,Usage \|\| Moves it: .+ \|\| Open this prop \| true$/.test(l))
      && !pairT.nav.hidden && /^1 of \d pairs$/.test(pairT.nav.pos) && pairT.nav.prevOff && !pairT.nav.nextOff && /^take this pair$/i.test(pairT.bigBtn) && pairT.h3next !== pairT.h3 && /^2 of \d pairs$/.test(pairT.posNext) && pairT.h3back === pairT.h3
      && /^.+ \| (LEAN|BET|no edge) \| \d of 7$/i.test(pairT.legPanel) && pairT.closed && pairT.fromTaking.toLowerCase() === ('Same-game pair · the price agrees | ' + pairT.h3).toLowerCase(),
      'pairs: a same-game pair card opens its own panel with the ticket\'s band, both legs, the chance, the parlay price and what it needs, five tiles, the arithmetic of the chance with the measured factor, each leg\'s numbers with a button to its own panel, and Previous / Next across the night\'s tickets', JSON.stringify(pairT).slice(0, 1500));
  chk(pairT.takeOn && pairT.cardTaking === 1 && pairT.cardBtnOn === 1 && pairT.takingList.length === 1 && /^TAKING · SAME-GAME PAIR · 76ers @ Knicks · at (Fanatics|DraftKings|FanDuel|BetMGM) · the price agrees .+ \+ .+ both land \d\d\.\d% · pays \+\d+ .+Taking$/i.test(pairT.takingList[0]) && pairT.takingCount === '1 marked' && !pairT.takingHead
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
  const qrRead = (n, mods) => {   // the drawn modules through an independent decoder (jsQR, tools_vendor): what a phone's camera reads
    try {
      const jsQR = require('./tools_vendor/jsQR.js');
      const scale = 4, q = 4, size = (n + 2 * q) * scale, data = new Uint8ClampedArray(size * size * 4);
      for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
        const r = Math.floor(y / scale) - q, c = Math.floor(x / scale) - q, dark = r >= 0 && c >= 0 && r < n && c < n && mods[r][c];
        const v = dark ? 0 : 255, i = (y * size + x) * 4; data[i] = v; data[i + 1] = v; data[i + 2] = v; data[i + 3] = 255;
      }
      const res = jsQR(data, size, size); return res ? res.data : null;
    } catch (e) { return 'decoder error: ' + e.message; }
  };
  const decoded = qrRead(phoneT.n, phoneT.mods);
  chk(phoneT.hidden0 && phoneT.open && /\/m\.html#z[A-Za-z0-9_-]+$/.test(phoneT.link) && phoneT.n >= 57 && phoneT.n % 4 === 1 && decoded === phoneT.link
      && /^Point your phone's camera at the code and open the link\. It shows \d+ lines: the bets you are taking, the parlay four, the best straight bets, the likeliest sides, the best props, the night's tickets and the simulation's calls, view only\./.test(phoneT.note)
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
  chk(sheetErrs.length === 0 && /^The Super Model Sat, Nov 14 · made \d{1,2}:\d\d [AP]M · view only TAKING TONIGHT 2 TAKING · NBA Knicks ML 66\.6% · [-−]198 needs 66\.4% 76ers @ Knicks · Moneyline TAKING · NBA · SIMULATION Total UNDER 231\.5 [6-9]\d\.\d% · worth 5\d% · [-−]110 needs 52\.4% 76ers @ Knicks · the simulation, the sim's own view THE PARLAY FOUR 1 /.test(sheetT.text)
      && /LIKELIEST AT ANY PRICE 1 /.test(sheetT.text) && /THE SIMULATION'S CALLS, BET OR BETTER \d /.test(sheetT.text) && /View only: the card lives in the desktop browser\./.test(sheetT.text) && sheetT.takes === 2 && sheetT.cards >= 5 && sheetT.inputs === 0 && sheetT.wide,
      'phone sheet: m.html unpacks the code on a phone-width screen with no script errors and lists the bets marked Taking first, then the parlay four, the likeliest sides and the simulation\'s calls, with nothing to type into and no sideways scroll', JSON.stringify({ errs: sheetErrs, text: sheetT.text.slice(0, 500), cards: sheetT.cards, takes: sheetT.takes, inputs: sheetT.inputs, wide: sheetT.wide }));
  await pg.evaluate(async () => { await smStore.removeItem('callsheet3.card.v1'); await smStore.removeItem('callsheet3.props.v1'); document.getElementById('clear').click(); });

  // ---- the build stamp ------------------------------------------------------------
  // ---- the simulation (25 Oct 2026): the card on the example, the block stored with the row, the record once graded ----
  await pg.evaluate(async () => { await smStore.removeItem('callsheet3.card.v1'); }); await reloaded(); await pg.evaluate(() => smStore.ready);
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
    return { panel: panel.slice(0, 420), tiles, meta: meta.replace(/\s+/g, ' ').trim(), medians: medians.replace(/\s+/g, ' ').trim(), rows, chips, moved, hasSim: !!(stored && stored.inputs.nbasim && stored.inputs.nbasim.length > 1000),
             teamShrink: stored ? ((JSON.parse(stored.inputs.nbasim).shrink || {}).team) : null };
  });
  // graded, with the book's team totals on the row's odds JSON (26 Oct 2026): the record takes them too
  // (11 Nov 2026: and with the 1.5 a slate written before that day stored for the anchored home team total, which the page no longer takes from the row)
  await pg.evaluate(async () => { const c = JSON.parse(smStore.getItem('callsheet3.card.v1')); c.forEach(r => { if (/76ers @ Knicks/.test(r.matchup)) { r.finals = { fa: '112', fh: '121', f5a: '55', f5h: '60' };
    const sb = JSON.parse(r.inputs.nbasim); sb.shrink.team = 1.5; r.inputs.nbasim = JSON.stringify(sb);
    r.inputs.odds = JSON.stringify({ total: {}, ml: {}, spread: {}, book: 'fanatics', team: { AWAY: { OVER: [['fanatics', -110, 113.5], ['fanatics', 140, 117.5], ['draftkings', -112, 113.5]], UNDER: [['fanatics', -110, 113.5], ['fanatics', -170, 117.5], ['draftkings', -108, 113.5]] },
                                                                                                    HOME: { OVER: [['fanatics', -115, 123.5]], UNDER: [['fanatics', -105, 123.5]] } } }); } }); await smStore.setItem('callsheet3.card.v1', JSON.stringify(c)); });
  await reloaded(); await pg.evaluate(() => smStore.ready);
  const simRec = await pg.evaluate(() => { const rec = document.querySelector('#calibBox .simrec'); return { has: !!rec, text: rec ? rec.innerText.replace(/\s+/g, ' ').trim().slice(0, 300) : '', gapHead: rec ? ((e) => e ? e.innerText.replace(/\s+/g, ' ').trim() : '')([...rec.querySelectorAll('.simrecview')].find(e => /team-total gap/i.test(e.textContent))) : '', rows: rec ? [...rec.querySelectorAll('.simrectab:not(.gaptab):not(.boosttab) tbody tr')].map(tr => tr.innerText.replace(/\s+/g, ' ').trim()) : [],
    gap: rec ? [...rec.querySelectorAll('.gaptab tbody tr')].map(tr => tr.innerText.replace(/\s+/g, ' ').trim()) : [],
    gapTh: rec ? [...rec.querySelectorAll('.gaptab thead th')].map(th => th.textContent.replace(/\s+/g, ' ').trim()).join(' | ') : '',
    // 11 Nov 2026: the anchored home team total's 1.5 is withdrawn; what it would have called is a watch row of its own, and the note says why
    boost: rec ? [...rec.querySelectorAll('.boosttab tbody tr')].map(tr => tr.innerText.replace(/\s+/g, ' ').trim()) : [],
    boostHead: rec ? ((e) => e ? e.innerText.replace(/\s+/g, ' ').trim() : '')([...rec.querySelectorAll('.simrecview')].find(e => /anchored home team total/i.test(e.textContent))) : '',
    anchoredTab: rec ? [...rec.querySelectorAll('.simrecview')].some(e => /^Anchored to the market$/i.test(e.textContent.trim())) : null,
    note: rec ? ((e) => e ? e.innerText.replace(/\s+/g, ' ').trim() : '')(rec.querySelector('.note')) : '',
    storedTeam: (() => { try { const r = JSON.parse(smStore.getItem('callsheet3.card.v1')).find(x => /76ers @ Knicks/.test(x.matchup)); return JSON.parse(r.inputs.nbasim).shrink.team; } catch (e) { return null; } })() }; });
  // the gap on the card: the Knicks' 123.5 sits 5 above the implied (231.5 + 5.5) / 2 = 118.5, so UNDER by the gap; the 76ers' 113.5 sits half a point over 113, inside a point
  // (26 Oct 2026: the band comes from the worth, so the anchored home team total at 123.5 read a band at its 1.5; 121 scored, the under wins)
  // (11 Nov 2026: the gap is a watch and the 1.5 is withdrawn. The re-test showed the two seasons behind both read a line the season pull had kept wrong. The gap's chip is a dashed
  //  outline that says "a watch, not scored"; the anchored home team total's 67% is worth 55% at 0.3, no band, on a row whose slate stored 1.5; the record keeps both as watches)
  const gapCardT = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 80));
    document.getElementById('m-nba').click(); await wait();
    const row = JSON.parse(smStore.getItem('callsheet3.card.v1')).find(r => /76ers @ Knicks/.test(r.matchup));
    const btn = document.querySelector('#card tr[data-id="' + row.id + '"] button.fill, #card [data-id="' + row.id + '"] .fill, button[data-fill="' + row.id + '"]');
    if (btn) { btn.click(); await wait(); }
    else { document.getElementById('odds').value = row.inputs.odds; document.getElementById('line').value = '231.5'; document.getElementById('sp').value = '-5.5'; document.getElementById('nbasim').value = row.inputs.nbasim; document.getElementById('away').value = '76ers'; document.getElementById('home').value = 'Knicks'; document.getElementById('line').dispatchEvent(new Event('input', { bubbles: true })); await wait(); }
    const rows = [...document.querySelectorAll('#nbaSimPanel .simtab tbody tr')].map(tr => tr.innerText.replace(/\s+/g, ' ').trim());
    const chips = [...document.querySelectorAll('#nbaSimPanel .simtab tbody tr')].slice(4).map(tr => [...tr.querySelectorAll('.simchip')].map(e => e.className + '|' + e.textContent.replace(/\s+/g, ' ').trim()));
    const sig = [...document.querySelectorAll('#signals a.sig')].map(a => a.className + '|' + a.innerText.replace(/\s+/g, ' ').trim());
    document.getElementById('clear').click(); await wait();
    return { rows: rows.slice(4), chips, sig };
  });
  const gapCard = gapCardT.rows;
  await pg.evaluate(async () => { await smStore.removeItem('callsheet3.card.v1'); }); await reloaded(); await pg.evaluate(() => smStore.ready);
  chk(simT.tiles.length === 4 && /^Total=\d+$/.test(simT.tiles[0]) && /^Margin=Knicks by \d+\.\d$/.test(simT.tiles[1]) && /^Knicks wins=\d+%$/.test(simT.tiles[2]) && /^Overtime=\d\.\d%$/.test(simT.tiles[3])
      && /^3,000 games, the sim's own view\. Anchored to DraftKings's 231\.5 \/ -5\.5 for the market view\.( The ratings ride the league's level of the last fortnight, [\d.]+ per 100 at [\d.]+ possessions \(30 Oct 2026\)\.)?( Engine 2: score effects, the market's shape \(30 Oct 2026\)\.)?$/.test(simT.meta)
      && /^Medians, anchored to the market Q1 Q2 Q3 Q4 1H 2H 76ers Knicks the fourth \d+\.\d% of the game( \d+){8}$/i.test(simT.medians)
      && simT.rows.length === 6 && /^Total 231\.5 (OVER|UNDER) \d+%/.test(simT.rows[0]) && /^First half 115\.5 (OVER|UNDER) \d+%/.test(simT.rows[1]) && /^Spread \(home\) -5\.5 (HOME|AWAY) \d+%/.test(simT.rows[2]) && /^Moneyline (HOME|AWAY) \d+%.*the own view's$/.test(simT.rows[3])
      && /^76ers team total no line on the row \(the odds run brings it\) — —$/.test(simT.rows[4]) && /^Knicks team total no line on the row/.test(simT.rows[5])
      && simT.chips.length === 7 && simT.chips.every(c => /^simchip sim(no|lean|bet|strong)\|(OVER|UNDER|HOME|AWAY) \d+%$/.test(c)) && simT.moved !== simT.rows[0] && /UNDER [89]\d%/.test(simT.moved) && simT.hasSim,
      'nba sim: the Simulation card reads the example\'s runs, lists every market with the own and the anchored chance for the line on the row, follows the line when it is typed, and the block rides with the row', JSON.stringify({ panel: simT.panel, rows: simT.rows, moved: simT.moved, chips: simT.chips.length, has: simT.hasSim }));
  chk(simRec.has && /^SIMULATION · says against does, every call at LEAN or better The sim's own view/.test(simRec.text) && simRec.rows.length >= 1
      && simRec.rows.every(r => /^(Total|First half|Spread|Moneyline|Away team total|Home team total) (STRONG|BET|LEAN) [01]-[01] \d+\.\d% (0|100)\.0% [+-]\d+\.\du$/.test(r))
      && simRec.gap.length === 1 && /^Home team total 1-0 100\.0% \+[01]\.\du 212-210 \(50\.2%\), [-−]22\.3u at the apps against the book's own number; 176-190, [-−]34\.8u against the other books'$/.test(simRec.gap[0]) && /The re-test said, two seasons/i.test(simRec.gapTh)
      && /^The team-total gap, a watch the book's line a point or more off the number the game's total and spread imply · shown, not scored, from 11 Nov 2026 · the two seasons behind the rule read one book's line, and the season pull had kept that book's alternate points with another point's prices: 61% on those, a coin less the price on the books' own lines$/i.test(simRec.gapHead)
      && !/scored, two seasons|under re-test/i.test(simRec.gapHead),
      'nba sim: once the row grades, the record block keeps the calls whose worth reads LEAN or better, says against does by view, market and band, and the gap\'s own tally as a watch (the Knicks\' 123.5 five above the implied 118.5, under called, 121 scored: a win): its heading says shown, not scored, from 11 Nov 2026 and why, and the column beside the tally carries what the re-test read on the books\' own lines over the two seasons (212-210 at home at the apps)', JSON.stringify(simRec));
  chk(simT.teamShrink === 0.3 && simRec.storedTeam === 1.5 && simRec.anchoredTab === false && !simRec.rows.some(r => /^Home team total (STRONG|BET|LEAN) 1-0 6\d\.\d% /.test(r))
      && simRec.boost.length === 1 && /^1 1-0 6\d\.\d% 100\.0% \+[01]\.\du$/.test(simRec.boost[0])
      && /^The anchored home team total at its old weight, a watch the sim's chance times 1\.5, the weight the same replay gave it · withdrawn 11 Nov 2026 with the gap rule: it reads at 0\.3 now, like the away side, and calls nothing here until a replay on the books' own lines says otherwise$/i.test(simRec.boostHead)
      && /The team totals were scored until 11 Nov 2026 on a replay whose lines were not the book's: the season pull had kept, for the one book it read, an alternate point with another point's prices\. On the books' own lines the gap between a team total and the number the game's total and spread imply reads a coin less the price, so the gap and the anchored home team total are watches now, counted above and scored nowhere\.$/.test(simRec.note)
      && !/the one inefficiency/i.test(simRec.note),
      'nba sim: the anchored home team total\'s 1.5 is withdrawn: a block built today carries 0.3, and a row whose slate stored 1.5 with it reads at 0.3 all the same: its 67% under 123.5 is worth 55% and no call, so no anchored table opens for it; the record keeps what the old weight would have called as a watch of its own (one call, a win) and the note under the record says the team totals were scored on lines that were not the book\'s', JSON.stringify({ built: simT.teamShrink, stored: simRec.storedTeam, anchoredTab: simRec.anchoredTab, rows: simRec.rows, boost: simRec.boost, boostHead: simRec.boostHead, note: simRec.note.slice(-420) }));
  chk(gapCard.length === 2 && /^76ers team total 113\.5 fanatics -110\/-110 implied 113, gap \+0\.5 · inside a point (OVER|UNDER) \d+% worth \d+% (OVER|UNDER) \d+% worth \d+%$/.test(gapCard[0])
      && /^Knicks team total 123\.5 fanatics -115\/-105 implied 118\.5, gap \+5 · UNDER by the gap a watch, not scored UNDER \d+% (LEAN · |BET · |STRONG · )?worth \d+% UNDER 6\d% worth 5[45]%$/.test(gapCard[1])
      && gapCardT.chips.length === 2 && gapCardT.chips[0].every(c => !/gaprule/.test(c)) && gapCardT.chips[1][0] === 'simchip simwatch gaprule|UNDER by the gap' && /^simchip simno\|UNDER 6\d%$/.test(gapCardT.chips[1][2])
      && !gapCardT.chips[1].some(c => /simbet gaprule/.test(c))
      && gapCardT.sig.some(c => /^sig watch\|GAP WATCH Knicks team total UNDER 123\.5 · gap \+5 · not scored$/i.test(c)) && !gapCardT.sig.some(c => /^sig go\|GAP/i.test(c)) && !gapCardT.sig.some(c => /gap rule/i.test(c)),
      'nba sim: the Simulation card shows each team total\'s implied number and gap, and the side the gap points to when it is a point or more as a watch: a dashed chip that says not scored where the green BET chip was, the anchored home team total beside it reading no band at its new weight, and the signal on the rail gold, not green', JSON.stringify(gapCardT));

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
  await reloaded();
  const store2 = await pg.evaluate(async () => {
    await smStore.ready;
    const p = smStore.getItem('callsheet3.props.v1'), c = JSON.parse(smStore.getItem('callsheet3.card.v1') || '[]');
    const lc = window.localStorage.getItem('callsheet3.card.v1'), lp = window.localStorage.getItem('callsheet3.props.v1');   // the browser's own store, on purpose
    return { pLen: p ? p.length : 0, cardRows: c.length, localCard: lc === null ? null : lc.length, localProps: lp === null ? null : lp.length, keys: Object.keys(localStorage), saveState: document.getElementById('saveState').textContent };
  });
  chk(store1.backend === 'indexeddb' && store1.rows >= 1 && store1.propsInLocal === null, 'store: the page keeps the card and the props in IndexedDB, not localStorage', JSON.stringify(store1));
  chk(store2.pLen === store1.bigLen && store2.localProps === null, 'store: a props list far past the localStorage limit saves and comes back after a reload', JSON.stringify({ pLen: store2.pLen, bigLen: store1.bigLen }));
  chk(store2.cardRows === store1.rows && store2.localCard === null && !/not storing/.test(store2.saveState), 'store: a card the old page left in localStorage moves to the database on load and leaves localStorage', JSON.stringify(store2));
  await pg.evaluate(() => smStore.clear()); await reloaded();

  // ---- 2 Nov 2026: the save trimmed -- a prop on a night older than the last seven keeps its record and loses the panel's detail; the backup writes a prop a line ----
  await pg.evaluate(async () => {
    await smStore.ready;
    const heavy = (id, gdate, name, mk, side, result) => ({ id, gdate, game: 'Heat @ Hornets', away: 'Heat', home: 'Hornets', aab: 'MIA', hab: 'CHA', pid: String(id), name, team: 'MIA', opp: 'CHA', pos: 'G', mk, line: 20.5, op: -110, up: -110, book: 'fanatics',
      books: { fanatics: [20.5, -110, -110], draftkings: [20.5, -112, -108] }, proj: 22.1, sd: 7, pm: 0.58, pb: 0.475, p: 0.49, push: 0, side, chance: side === 'OVER' ? 0.49 : 0.51, price: -110, need: 0.524, edge: side === 'OVER' ? -0.034 : -0.014, band: 'no edge', mins: 30, rate36: 26, base: 25, med: 21.5, usg: 25, sdf: 0.93, starter: true, start_src: 'RotoWire',
      why: ['26.0 points per 36 this season', 'the chance read around the median 21.5 (' + 'x'.repeat(400) + ')'], log: [['2026-10-15', 'MIA', 0, 34.0, 26], ['2026-10-17', 'CHI', 1, 31.0, 22, ['won by 6', '31 min']]], parts: [{ k: 'pace', t: 'Pace', eff: 0.4, i: 0 }],
      sim: { runs: 10000, team_pts: 115, team_lo: 106, team_hi: 124, read: 21.0, blowout: 0.3, ot: 0.04, poss: 100 }, gsim: { runs: 10000, a: [115, 106, 124, 116], h: [110, 101, 119, 111], t: 225, m: -5, hw: 0.4, ot: 0.04, bo: 0.3, poss: 100, out: [0, 0] },
      fives: { away: { status: 'confirmed', five: [['G', name]] }, home: null }, awhat: ['won by 6'], actual: result === 'win' ? (side === 'UNDER' ? 18 : 24) : (side === 'UNDER' ? 24 : 18), amin: 33, result });
    const dates = ['2026-10-20', '2026-10-21', '2026-10-22', '2026-10-23', '2026-10-24', '2026-10-25', '2026-10-26', '2026-10-27', '2026-10-28'];
    const rows = []; dates.forEach((d, i) => { rows.push(heavy(i * 2 + 1, d, 'Tyler Herro', 'pts', 'UNDER', 'win')); rows.push(heavy(i * 2 + 2, d, 'Bam Adebayo', 'reb', 'OVER', 'loss')); });
    rows.push(Object.assign(heavy(99, '2026-10-29', 'Norman Powell', 'pts', 'UNDER', null), { result: null, actual: null, amin: null }));   // tonight's, ungraded: the tenth night on the tab
    // three of Herro's unders marked Taking (3 Nov 2026: your picks), one on a night the trim takes, and a LEAN on the sheet's own side on the 28th for the comparison
    rows.filter(r => r.name === 'Tyler Herro' && ['2026-10-20', '2026-10-23', '2026-10-28'].indexOf(r.gdate) >= 0).forEach(r => { r.take = true; });
    rows.filter(r => r.name === 'Bam Adebayo' && r.gdate === '2026-10-28').forEach(r => { r.band = 'LEAN'; r.edge = 0.012; });
    await smStore.setItem('callsheet3.props.v1', JSON.stringify(rows));
  });
  await reloaded();
  const trimT = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 90));
    const txt = e => (e ? e.innerText : '').replace(/\s+/g, ' ').trim();
    await smStore.ready;
    const stored = JSON.parse(smStore.getItem('callsheet3.props.v1'));
    const byDate = {}; stored.forEach(r => { (byDate[r.gdate] = byDate[r.gdate] || []).push(r); });
    const dates = Object.keys(byDate).sort();
    const trimmed = dates.filter(d => byDate[d].every(r => r.trim)), whole = dates.filter(d => byDate[d].every(r => !r.trim && r.why && r.log && r.books && r.sim && r.gsim && r.fives && r.parts && r.awhat));
    const old = stored.filter(r => r.trim);
    const gone = old.length > 0 && old.every(r => ['why', 'log', 'parts', 'sim', 'gsim', 'fives', 'awhat'].every(k => r[k] === undefined) && r.books !== undefined);   // the books stay (5 Nov 2026): the pairs are rebuilt at one app from them
    const kept = old.every(r => r.result && r.chance && r.price && r.band && r.side && r.mk && r.gdate && r.name && r.centre === 'median' && r.actual !== undefined && r.amin === 33 && r.med === 21.5 && /^\d{4}-\d{2}-\d{2}$/.test(r.trim));
    // the tab: the record counts every graded night, a trimmed night's strip and panel say so, a whole night's panel keeps its detail
    document.getElementById('m-props').click(); await wait();
    const tile = txt(document.querySelector('#propsCalib .calib[data-sport="PROPS-TAB"]')), nights = document.querySelectorAll('#propsNights tbody tr').length;
    const sel = document.getElementById('propsDate'); sel.value = '2026-10-20'; sel.dispatchEvent(new Event('change')); await wait();
    const strip = txt(document.getElementById('propsSim'));
    document.getElementById('propsAll').checked = true; document.getElementById('propsAll').dispatchEvent(new Event('change', { bubbles: true })); await wait();
    document.querySelector('#propsTable tr[data-prop]').click(); await wait();
    const panel = txt(document.getElementById('propDetailBody')), h4s = [...document.querySelectorAll('#propDetailBody h4')].map(h => h.textContent.trim().split(' ')[0]);
    const thisRow = txt(document.querySelector('#propDetail .pd-log tr.this'));
    document.getElementById('propDetailClose').click(); await wait();
    sel.value = '2026-10-28'; sel.dispatchEvent(new Event('change')); await wait();
    document.querySelector('#propsTable tr[data-prop]').click(); await wait();
    const wholePanel = txt(document.getElementById('propDetailBody')), wholeStrip = txt(document.getElementById('propsSim'));
    document.getElementById('propDetailClose').click(); await wait();
    // the backup: a prop a line, compact, the trimmed rows without their detail; the file parses as a backup
    let blob = null; const mkURL = URL.createObjectURL, click = HTMLAnchorElement.prototype.click;
    URL.createObjectURL = b => { blob = b; return 'blob:x'; }; HTMLAnchorElement.prototype.click = function () {};
    document.getElementById('backup').click(); await wait(); await wait();
    URL.createObjectURL = mkURL; HTMLAnchorElement.prototype.click = click;
    const text = blob ? await blob.text() : '', parsed = text ? JSON.parse(text) : null;
    const backup = parsed ? { format: parsed.format, props: parsed.props.length, propLines: text.slice(text.indexOf('"props": [')).split('\n').filter(l => /^    \{"id":/.test(l)).length, trimmedInFile: parsed.props.filter(r => r.trim).length, whyInFile: parsed.props.filter(r => r.why).length, card: Array.isArray(parsed.card), draft: !!parsed.draft, msg: txt(document.getElementById('saveMsg')) } : null;
    // your picks (3 Nov 2026): the night table's You took column, the Taken filter, and the record's night-by-night, the props' cuts and the list
    const youTook = [...document.querySelectorAll('#propsNights tbody tr')].map(tr => { const td = tr.querySelectorAll('td'); return td[0].textContent.trim() + '|' + td[6].textContent.trim() + '|' + td[6].className; });
    sel.value = '2026-10-23'; sel.dispatchEvent(new Event('change')); await wait();
    const takenSel = document.getElementById('propsTakenSel'); takenSel.value = 'yes'; takenSel.dispatchEvent(new Event('change', { bubbles: true })); await wait();
    const onlyTaken = [...document.querySelectorAll('#propsTable tbody tr[data-prop]')].map(tr => tr.querySelectorAll('td')[1].textContent.trim()), takenShown = txt(document.getElementById('propsShown')), takenStored = JSON.parse(localStorage.getItem('callsheet3.props.view.v1') || '{}').taken;
    document.getElementById('propsReset').click(); await wait();
    const afterReset = { n: document.querySelectorAll('#propsTable tbody tr[data-prop]').length, taken: document.getElementById('propsTakenSel').value };
    document.getElementById('m-nba').click(); await wait();
    const fold = document.querySelector('.takenlist'); if (fold) fold.open = true;   // the list sits folded; innerText reads nothing from a closed fold
    const yourNights = [...document.querySelectorAll('#takenNights tbody tr')].map(tr => txt(tr)), yourProps = [...document.querySelectorAll('#takenProps tbody tr')].map(tr => txt(tr)), yourList = [...document.querySelectorAll('#takenList tbody tr')].map(tr => txt(tr)), yourSummary = txt(document.querySelector('.takenlist summary'));
    await smStore.removeItem('callsheet3.props.v1');
    return { trimmed, whole, gone, kept, tile: tile.slice(0, 160), nights, strip: strip.slice(0, 200), panel: panel.slice(0, 700), h4s, thisRow, wholeHas: /what moves it/i.test(wholePanel) && /\bwhy\b/i.test(wholePanel) && /every book/i.test(wholePanel) && /simulation · Heat @ Hornets played 10,000 times/i.test(wholePanel) && !/trimmed from the save/.test(wholePanel), wholeStrip: wholeStrip.slice(0, 120), backup,
             youTook, onlyTaken, takenShown, takenStored, afterReset, yourNights, yourProps, yourList, yourSummary };
  });
  chk(JSON.stringify(trimT.trimmed) === JSON.stringify(['2026-10-20', '2026-10-21', '2026-10-22']) && JSON.stringify(trimT.whole) === JSON.stringify(['2026-10-23', '2026-10-24', '2026-10-25', '2026-10-26', '2026-10-27', '2026-10-28', '2026-10-29']) && trimT.gone && trimT.kept,
      'trim: on load, a prop on a night older than the last seven on the tab loses the panel\'s detail (the why, the last games, the levers, the simulation, the fives, what happened) and keeps its record (the call, the price, the chance, the band, the result, his minutes, the median, the centre) and every book\'s line (5 Nov 2026, for the pairs at one app), stamped with the day; the last seven nights stay whole, tonight\'s ungraded one among them',
      JSON.stringify({ trimmed: trimT.trimmed, whole: trimT.whole, gone: trimT.gone, kept: trimT.kept }));
  chk(/every prop with a side 9-9/i.test(trimT.tile) && trimT.nights === 9 && /trimmed from the save with the night's detail/.test(trimT.strip) && /was trimmed from the save on [A-Z][a-z]{2} \d{1,2} to keep the backup small/.test(trimT.panel) && JSON.stringify(trimT.h4s) === JSON.stringify(['Floors', 'Last', 'Every']) && /this game 33 18/.test(trimT.thisRow)
      && trimT.wholeHas && /played 10,000 times/.test(trimT.wholeStrip),
      'trim: the record still counts every graded night (9-9 over nine), a trimmed night\'s strip and panel say the detail was trimmed and when, the panel keeps the floors, the graded game\'s own line and every book\'s line, and a whole night keeps its why, levers, books, simulation and strip',
      JSON.stringify({ tile: trimT.tile, nights: trimT.nights, strip: trimT.strip, panel: trimT.panel.slice(0, 320), h4s: trimT.h4s, thisRow: trimT.thisRow, wholeHas: trimT.wholeHas, wholeStrip: trimT.wholeStrip }));
  chk(trimT.backup && trimT.backup.format === 'callsheet3.backup' && trimT.backup.card && trimT.backup.draft && trimT.backup.props === 19 && trimT.backup.propLines === 19 && trimT.backup.trimmedInFile === 6 && trimT.backup.whyInFile === 13 && /Backup saved as/.test(trimT.backup.msg),
      'trim: the backup file writes a prop a line, compact, the trimmed rows without their detail, and parses as a backup with the card and the draft', JSON.stringify(trimT.backup));
  chk(trimT.youTook.length === 9 && trimT.youTook.filter(s => /\|1-0 \+0\.9u\|pos$/.test(s)).length === 3 && trimT.youTook.filter(s => /\|—\|$/.test(s)).length === 6 && /^Oct 28\|1-0/.test(trimT.youTook[0]) && /^Oct 20\|1-0/.test(trimT.youTook[8])
      && JSON.stringify(trimT.onlyTaken) === JSON.stringify(['Tyler Herro G']) && /^1 of 2 shown$/.test(trimT.takenShown) && trimT.takenStored === 'yes' && trimT.afterReset.n === 2 && trimT.afterReset.taken === '',
      'your picks: the Props tab\'s night table carries a You took column (the marked props\' record that night, a dash on a night with none, a trimmed night counted too), and the Taken filter keeps only the props you marked until Reset view', JSON.stringify({ youTook: trimT.youTook, onlyTaken: trimT.onlyTaken, shown: trimT.takenShown, stored: trimT.takenStored, after: trimT.afterReset }));
  chk(trimT.yourNights.length === 3 && /^Oct 28 1 1 prop 1-0 51\.0% 100\.0% \+0\.9u 0-1 · 0\.0% · [-−]1\.0u$/.test(trimT.yourNights[0]) && /^Oct 23 1 1 prop 1-0 51\.0% 100\.0% \+0\.9u —$/.test(trimT.yourNights[1]) && /^Oct 20 1 1 prop 1-0 51\.0% 100\.0% \+0\.9u —$/.test(trimT.yourNights[2])
      && trimT.yourProps.length === 4 && /^Unders 3-0 51\.0% 100\.0% \+2\.7u$/.test(trimT.yourProps[0]) && /^No edge: the book's own side 3-0/.test(trimT.yourProps[1]) && /^points 3-0/.test(trimT.yourProps[2]) && /^[-−]120 to \+100 3-0/.test(trimT.yourProps[3])
      && trimT.yourList.length === 3 && /^Oct 28 Tyler Herro UNDER 20\.5 points · Heat @ Hornets prop 51\.0% [-−]110 WIN \+0\.91u$/.test(trimT.yourList[0]) && /^Oct 20 /.test(trimT.yourList[2]) && /^Every pick you marked, newest night first · 3 graded$/.test(trimT.yourSummary),
      'your picks: What you took goes on to your picks night by night with the sheet\'s own BET and LEAN props beside each night (the 28th\'s lean lost, the other nights had none), your props by side, band, market and price, and every pick newest first', JSON.stringify({ nights: trimT.yourNights, props: trimT.yourProps, list: trimT.yourList, summary: trimT.yourSummary }));

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
    // the two gates (the user's Spurs row of 27 Oct 2026, an alternate 225.5 at -208 against a market number of 232): the price, then an alternate line
    set('op', '-208'); set('up', '165'); await wait();
    const priced = { cls: (document.querySelector('#nbaVoices .voices') || {}).className || '', badge: txt(document.querySelector('#nbaVoices .vbadge')), line: txt(document.querySelector('#nbaVoices .vline')), take: !!document.querySelector('#nbaVoices .vtake') };
    set('op', '-110'); set('up', '-110'); await wait();
    set('odds', JSON.stringify({ book: 'fanatics', total: { OVER: [['fanatics', -110, 229.5], ['draftkings', -108, 229.5]], UNDER: [['fanatics', -110, 229.5], ['draftkings', -112, 229.5]] } })); set('line', '222.5'); await wait();
    const alt = { badge: txt(document.querySelector('#nbaVoices .vbadge')), line: txt(document.querySelector('#nbaVoices .vline')), take: !!document.querySelector('#nbaVoices .vtake') };
    set('odds', ''); await wait();
    // a split: the example's sim leans under while its crew leans over, so no rule, and the words say so
    document.getElementById('clear').click(); document.getElementById('m-nba').click(); await wait();
    document.getElementById('gdate').value = '2026-11-10'; document.getElementById('example').click(); await wait();
    const split = { cls: (document.querySelector('#nbaVoices .voices') || {}).className || '', badge: txt(document.querySelector('#nbaVoices .vbadge')), line: txt(document.querySelector('#nbaVoices .vline')) };
    document.getElementById('clear').click(); await wait();
    await smStore.removeItem('callsheet3.card.v1');
    return { headHidden, cards, block, take, taking, boardTake, rec, recHead, graded, priced, alt, split };
  });
  chk(agreeT.priced.cls === 'voices' && /^[23] OF 3 · NO BET$/i.test(agreeT.priced.badge) && /[23] of 3 on the OVER, but at -208 it needs 67\.5%, more than the rule's 59\.2%: the book's price, not a bet\.$/i.test(agreeT.priced.line) && !agreeT.priced.take
      && /^2 OF 3 · NO BET$/i.test(agreeT.alt.badge) && /2 of 3 on the OVER, but the row's line 222\.5 is an alternate \(the market's number is 229\.5\): the rule was measured on the main line, no bet\.$/i.test(agreeT.alt.line) && !agreeT.alt.take,
      'agreement gates: the same voices at -208 read the book\'s price, not a bet (the over needs 67.5%, the rule measured 59.2%), and a row line seven off the market\'s number reads an alternate outside the measurement; neither carries a Take', JSON.stringify({ priced: agreeT.priced, alt: agreeT.alt }));
  chk(agreeT.headHidden === false && agreeT.cards.length === 1 && /^AGREEMENT · 2 OF 3 · BET BY THE RULE$/i.test(agreeT.cards[0].n1) && /^TOTAL OVER 222\.5$/i.test(agreeT.cards[0].n2)
      && /^the sheet silent \((OVER|UNDER) 50%, no bet\) · the sim OVER 6\d% · the crew leans OVER \(z \+4\.4\) · -110$/i.test(agreeT.cards[0].n3) && /^Kings @ Spurs · the sim's own view/.test(agreeT.cards[0].n4) && agreeT.cards[0].take
      && agreeT.block.cls === 'voices fires' && /^BET · 2 OF 3$/i.test(agreeT.block.badge) && /2 of 3 on the OVER, none against: BET by the agreement rule\.$/i.test(agreeT.block.line) && agreeT.block.take && agreeT.block.color !== 'rgba(0, 0, 0, 0)' && agreeT.block.simchips === 2
      && agreeT.take.length === 1 && /^agree\|total\|OVER\|222\.5\|-110\|agreement\|Total OVER 222\.5\|0\.6\d\|null$/.test(agreeT.take[0]) && /Total OVER 222\.5 6\d% by the sim · agreement · -110 needs 52\.4% Kings @ Spurs · the agreement rule, the sim and the crew/i.test(agreeT.taking) && !/worth/i.test(agreeT.taking) && /TAKING/i.test(agreeT.boardTake)
      && /^Voices Record Does Units Two seasons said 2 of 3: the sim and the crew, the sheet silent 1-0 100\.0% \+0\.9u 134-98 \(57\.8%\), \+23\.8u$/i.test(agreeT.rec) && /scored, BET/i.test(agreeT.recHead) && /WIN$/i.test(agreeT.graded)
      && agreeT.split.cls === 'voices' && /^NO RULE$/i.test(agreeT.split.badge) && /the sim UNDER [6-9]\d% · the crew leans OVER \(z \+4\.4\) — (split, 2 on the (OVER|UNDER) with one against: no rule|no two voices on a side: no rule)\.$/i.test(agreeT.split.line),
      'agreement: a basketball total with the sim\'s own view and the crew on the same side and the sheet silent reads BET on the board\'s Agreement section and on the Simulation card\'s three-voices block in green, takes from either (the mark on the row at the row\'s price, listed under Taking tonight without a worth), grades on the rule\'s own record line, and a split (the example: the sim under, the crew over) reads no rule', JSON.stringify(agreeT).slice(0, 1800));

  // ---- 28 Oct 2026: middles on the total -- the apps' numbers on the row, a leg held, the number runs, the watch names the second leg, a take, the pair on the record ----
  const midT = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 220));
    const txt = e => (e ? e.innerText : '').replace(/\s+/g, ' ').trim();
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    await smStore.removeItem('callsheet3.card.v1'); document.getElementById('clear').click(); document.getElementById('m-nba').click(); await wait();
    const load = async (doc, fname) => { const dt = new DataTransfer(); dt.items.add(new File([JSON.stringify(doc)], fname, { type: 'application/json' })); const inp = document.getElementById('slateFile'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true })); await wait(); };
    const odds = (pt) => JSON.stringify({ book: 'fanatics', total: { OVER: [['fanduel', -108, pt], ['betmgm', -110, pt], ['draftkings', -112, pt + 0.5], ['fanatics', -110, pt], ['pinnacle', -105, pt]], UNDER: [['fanduel', -112, pt], ['betmgm', -110, pt], ['draftkings', -108, pt + 0.5], ['fanatics', -110, pt], ['pinnacle', -115, pt]] },
                                           alt: { OVER: [['fanduel', -135, pt - 2], ['draftkings', -150, pt - 3]], UNDER: [['fanduel', -135, pt + 2], ['draftkings', -150, pt + 3]] }, ml: {}, spread: {}, period: {}, team: {} });
    const game = (extra) => Object.assign({ sport: 'NBA', gdate: '2026-11-13', away: 'Jazz', home: 'Nuggets', notes: [] }, extra);
    set('gdate', '2026-11-13'); set('away', 'Jazz'); set('home', 'Nuggets'); set('line', '230.5'); set('op', '-110'); set('up', '-110'); await wait();
    document.getElementById('add').click(); await wait();
    await load({ format: 'callsheet2.slate', version: 1, date: '2026-11-13', generated: '2026-11-13T15:00:00Z', games: [game({ inputs: { odds: odds(230.5) } })] }, 'odds-2026-11-13.json');
    const row0 = JSON.parse(smStore.getItem('callsheet3.card.v1')).find(r => /Jazz @ Nuggets/.test(r.matchup)), ti = row0.markets.findIndex(m => m.key === 'total');
    document.getElementById('boardDate').value = '2026-11-13'; document.getElementById('boardDate').dispatchEvent(new Event('change')); await wait();
    const panel0 = txt(document.getElementById('nbaMidPanel'));
    // hold the sheet's over: the same mark the board's Take button makes (the board lists the pick's side, which at 50% is either)
    const tb = document.createElement('button'); tb.setAttribute('data-take', row0.id + '|' + ti + '|OVER'); document.body.appendChild(tb); tb.click(); tb.remove(); await wait();
    const before = { head: document.getElementById('midHead').hidden, cards: document.querySelectorAll('#mid .pk.mid').length, text: txt(document.getElementById('mid')) };
    // the number runs: a later odds run posts 234.5 at the apps and 235 at DraftKings
    await load({ format: 'callsheet2.slate', version: 1, date: '2026-11-13', generated: '2026-11-13T22:30:00Z', games: [game({ inputs: { odds: odds(234.5) } })] }, 'odds-2026-11-13b.json');
    const row1 = JSON.parse(smStore.getItem('callsheet3.card.v1')).find(r => /Jazz @ Nuggets/.test(r.matchup));
    const stored = { logged: /230\.5/.test(row1.inputs.odds) && !/234\.5/.test(row1.inputs.odds), now: /234\.5/.test(row1.inputs.oddsNow || ''), at: row1.inputs.oddsAt, line: row1.inputs.line, markets: row1.markets.filter(m => m.key === 'total').map(m => m.label).join() };
    const card = document.querySelector('#mid .pk.mid');
    const after = { head: document.getElementById('midHead').hidden, n: document.querySelectorAll('#mid .pk.mid').length, n1: txt(card && card.querySelector('.n1')), n2: txt(card && card.querySelector('.n2')), n3: txt(card && card.querySelector('.n3')), take: !!(card && card.querySelector('.takebtn[data-stake*="|middle|total|UNDER|235|-108|draftkings|sheet"]')) };
    // the rail: the row opens, the Middles panel shows the apps now, the watch, the pairs; the calculator prices a typed pair
    card.querySelector('.n2').click(); await wait();
    const now = txt(document.querySelector('#nbaMidPanel .midnow')), watch = { cls: (document.querySelector('#nbaMidPanel .midwatch') || {}).className || '', text: txt(document.querySelector('#nbaMidPanel .midwatch')) };
    const pairs = [...document.querySelectorAll('#nbaMidPanel .midtab tbody tr')].map(tr => tr.className + '|' + txt(tr)), note = txt(document.querySelector('#nbaMidPanel .midnote'));
    const fit = (() => { const t = document.querySelector('#nbaMidPanel .midtab'), s = document.getElementById('nbaMidPanel'); return !!t && t.getBoundingClientRect().width <= s.clientWidth + 1 && s.scrollWidth <= s.clientWidth + 1; })();   // the table fits the card (29 Oct 2026)
    set('midOverLine', '226.5'); set('midOverPrice', '-110'); set('midUnderLine', '234.5'); set('midUnderPrice', '-110'); await wait();
    const calc = txt(document.getElementById('midCalcOut'));
    set('midUnderLine', '228.5'); await wait();
    const calc2 = txt(document.getElementById('midCalcOut'));
    // the second leg taken from the panel: the mark on the row with the app, the leg it pairs with, Taking tonight lists it
    document.querySelector('#nbaMidPanel .midwatch .takebtn').click(); await wait();
    const row2 = JSON.parse(smStore.getItem('callsheet3.card.v1')).find(r => /Jazz @ Nuggets/.test(r.matchup));
    const take = (row2.simTakes || []).map(t => t.view + '|' + t.side + '|' + t.line + '|' + t.price + '|' + t.book + '|' + (t.with ? t.with.side + ' ' + t.with.line + ' ' + t.with.price : '') + '|' + (t.pair ? t.pair.gap : '') + '|' + t.pick);
    const taking = txt(document.getElementById('taking')), stillOpen = txt(document.querySelector('#mid .pk.mid .n5'));
    // graded between the numbers: both legs win, the record's Middles line
    await load({ format: 'callsheet2.slate', version: 1, date: '2026-11-13', games: [game({ finals: { fa: '116', fh: '117', f5a: '58', f5h: '60' }, close: { ctot: '234.5' } })] }, 'nba-grade-2026-11-13.json');
    const rec = txt(document.querySelector('.midrectab')), recHead = txt([...document.querySelectorAll('.simrecview')].find(e => /Middles on the total/i.test(e.textContent)));
    document.getElementById('clear').click(); await wait();
    await smStore.removeItem('callsheet3.card.v1');
    return { panel0, before, stored, after, now, watch, pairs, fit, note, calc, calc2, take, taking, stillOpen, rec, recHead };
  });
  chk(/(The apps now|No odds on the row)/.test(midT.panel0) && midT.before.head === false && midT.before.cards === 0 && /1 total held on this date, no window open/.test(midT.before.text)
      && midT.stored.logged && midT.stored.now && midT.stored.at === '2026-11-13T22:30:00Z' && midT.stored.line === '230.5' && /230\.5/.test(midT.stored.markets)
      && midT.after.head === false && midT.after.n === 1 && /^MIDDLE OPEN · A 4\.5-POINT WINDOW · PAYS \+[4-6]\.\d% OF THE STAKE$/i.test(midT.after.n1) && /^TOTAL UNDER 235 AT DRAFTKINGS -108$/i.test(midT.after.n2)
      && /^with your OVER 230\.5 -110 \(the sheet's pick\) · both win [89]\.\d%, needs 4\.[0-9]% · the market's number 234\.5$/i.test(midT.after.n3) && midT.after.take
      && /^The apps now \(the odds run of 2026-11-13 22:30 UTC\), the market's number 234\.5: FanDuel 234\.5 \(-108\/-112\) · BetMGM 234\.5 \(-110\/-110\) · DraftKings 235 \(-112\/-108\) · Fanatics 234\.5 \(-110\/-110\)$/.test(midT.now)
      && midT.watch.cls === 'midwatch pays' && /MIDDLE OPEN · a 4\.5-point window · pays \+[4-6]\.\d% of the stake You hold OVER 230\.5 at -110 \(the sheet's pick\); the market's number is 234\.5, so that leg alone is 5[6-9]\.\d% to win\. The best under now: DraftKings 235 at -108\. Both win [89]\.\d% \(the pair needs 4\.[0-9]%\)/i.test(midT.watch.text)
      && midT.pairs.length === 6 && midT.pairs.every(p => /\|(FanDuel|BetMGM|DraftKings|Fanatics)( alt)? \d+(\.5)? -\d+/.test(p)) && midT.fit === true && /^\d+ pairs across the apps' main and alternate numbers, the best six shown; none pays at these prices/.test(midT.note)
      && /^Pays: a 8-point window, both win 1[5-9]\.\d%, the pair needs 4\.8% at these prices: \+\d+\.\d% of the stake expected/.test(midT.calc) && /^(The book's price|Positive, but under a three-point gap): a 2-point window, both win [234]\.\d%/.test(midT.calc2)
      && midT.take.length === 1 && /^middle\|UNDER\|235\|-108\|draftkings\|OVER 230\.5 -110\|4\.5\|Total UNDER 235 at DraftKings \(the middle with OVER 230\.5\)$/.test(midT.take[0])
      && /Total UNDER 235 at DraftKings \(the middle with OVER 230\.5\) 50% by the sim · middle · -108 needs 51\.9% Jazz @ Nuggets · the middle's second leg/i.test(midT.taking) && /TAKING/i.test(midT.stillOpen)
      && /^Pairs Both won One pushed Split Said both The pair The first leg alone 1 1 \(100\.0%\) 0 0 [89]\.\d% \+1\.8[0-9]u \+0\.91u$/i.test(midT.rec) && /the pair graded together/.test(midT.recHead),
      'middles: the Middles card prices every over/under pair the four apps post off the sheet\'s normal and says none pays on an ordinary night; a total taken on the row is watched, and when a later odds run moves the number 4.5 points the board and the panel name the best second leg at its app with the pair\'s chance and what it pays; the apps\' numbers follow the newest run while the logged line stays; the calculator prices a typed pair; the second leg takes from the panel with the leg it pairs with, lists under Taking tonight, and the graded pair lands on the record\'s Middles line beside what the first leg alone did', JSON.stringify(midT).slice(0, 2600));

  // ---- the window on the total (29 Oct 2026): one ticket over the low number and under the high, priced off the sim ----
  const winT = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 260));
    const txt = e => (e ? e.innerText : '').replace(/\s+/g, ' ').trim();
    await smStore.removeItem('callsheet3.card.v1'); document.getElementById('clear').click(); document.getElementById('m-nba').click(); await wait();
    document.getElementById('example').click(); await wait();
    const CARD = () => JSON.parse(smStore.getItem('callsheet3.card.v1') || '[]').filter(r => r.sport === 'NBA' && /76ers @ Knicks/.test(r.matchup));
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    const block = document.querySelector('#nbaSimPanel .simwin');
    const head = txt(block), out0 = txt(document.getElementById('winOut')), ph = ['winLo', 'winHi', 'winPrice'].map(id => document.getElementById(id).placeholder);
    const sim = JSON.parse(document.getElementById('nbasim').value), V = sim.mkt || sim.own;
    const q = (h, p) => { const n = h.c.reduce((a, b) => a + b, 0); let acc = 0; for (let i = 0; i < h.c.length; i++) { acc += h.c[i]; if (acc >= p * n) return h.lo + i; } return h.lo + h.c.length - 1; };
    const lo = q(V.total, 0.25) - 0.5, hi = q(V.total, 0.75) + 0.5;
    const inside = (h, a, b) => { let n = 0, k = 0; h.c.forEach((c, i) => { n += c; const v = h.lo + i; if (v > a && v < b) k += c; }); return k / n; };
    const pDefault = inside(V.total, lo, hi);
    set('winLo', String(lo + 2)); set('winHi', String(hi - 2)); await wait();
    const out1 = txt(document.getElementById('winOut')), pTyped = inside(V.total, lo + 2, hi - 2);
    set('winPrice', '+120'); await wait();
    const out2 = txt(document.getElementById('winOut'));
    const btnOff = !!document.querySelector('#nbaSimPanel .simwin .takebtn[disabled]');
    document.getElementById('add').click(); await wait();
    const btn = document.querySelector('#nbaSimPanel .simwin .takebtn[data-stake]'); const stake = btn ? btn.getAttribute('data-stake') : '';
    if (btn) btn.click(); await wait();
    const row = CARD()[0], taken = row && (row.simTakes || [])[0];
    const btnOn = txt(document.querySelector('#nbaSimPanel .simwin .takebtn, #nbaSimPanel .simwin .chip'));
    // the finals land inside the window: the ticket wins
    const c = JSON.parse(smStore.getItem('callsheet3.card.v1')); c.forEach(r => { if (/76ers @ Knicks/.test(r.matchup)) r.finals = { fa: String(Math.floor((lo + hi) / 2) - 110), fh: '110', f5a: '55', f5h: '60' }; }); await smStore.setItem('callsheet3.card.v1', JSON.stringify(c));
    return { head, out0, ph, lo, hi, pDefault, out1, pTyped, out2, btnOff, stake, taken, btnOn, rowId: row && row.id };
  });
  await reloaded(); await pg.evaluate(() => smStore.ready);
  const winRec = await pg.evaluate(() => { const rec = document.querySelector('#calibBox .simrec'); const t = rec ? rec.innerText.replace(/\s+/g, ' ').trim() : ''; const i = t.indexOf('Windows on the total'); return i >= 0 ? t.slice(i, i + 260) : t.slice(0, 200); });
  const pc = p => (100 * p).toFixed(1) + '%';
  chk(/^The window · one ticket, over the low number and under the high, a same-game parlay · the boxes start at the middle half anchored to the market/.test(winT.head) && winT.ph[0] === 'over ' + winT.lo && winT.ph[1] === 'under ' + winT.hi && winT.ph[2] === 'parlay price'
      && winT.out0.indexOf('Over ' + winT.lo + ' and under ' + winT.hi + ', a ' + (winT.hi - winT.lo) + '-point window: lands inside ' + pc(winT.pDefault) + ' anchored to the market (the sim\'s own view ') === 0 && /· fair [+-]\d+ · type the app's parlay price and the edge reads here$/.test(winT.out0),
      'window: the block starts at the anchored middle half on half-point numbers, with the chance inside, the own view beside it and the fair price', JSON.stringify({ head: winT.head.slice(0, 160), out0: winT.out0, ph: winT.ph, lo: winT.lo, hi: winT.hi }));
  chk(winT.out1.indexOf('Over ' + (winT.lo + 2) + ' and under ' + (winT.hi - 2) + ', a ' + (winT.hi - winT.lo - 4) + '-point window: lands inside ' + pc(winT.pTyped)) === 0
      && new RegExp('at \\+120 the ticket needs 45\\.5%: (PAYS, \\+\\d+\\.\\d points over the price|the app\'s price, -\\d+\\.\\d points)$').test(winT.out2) && ((winT.pTyped > 0.4545) === /PAYS/.test(winT.out2)),
      'window: typed numbers reprice as you type, and the app\'s parlay price turns into the need and the edge', JSON.stringify({ out1: winT.out1, out2: winT.out2, p: winT.pTyped }));
  chk(winT.btnOff === true && /\|window\|total\|WINDOW [0-9.]+-[0-9.]+$/.test(winT.stake) && winT.taken && winT.taken.view === 'window' && winT.taken.lo === winT.lo + 2 && winT.taken.hi === winT.hi - 2 && winT.taken.price === 120
      && Math.abs(winT.taken.p - winT.pTyped) < 0.001 && winT.taken.band === 'window' && winT.taken.pick === 'Total window ' + (winT.lo + 2) + '-' + (winT.hi - 2) + ' (over the low, under the high), one ticket' && /taking/i.test(winT.btnOn),
      'window: the Take wakes with the row, and the ticket keeps the two numbers, the price and the anchored chance', JSON.stringify({ off: winT.btnOff, stake: winT.stake, taken: winT.taken, btn: winT.btnOn }));
  chk(/^Windows on the total .*? TICKETS RECORD SAYS DOES UNITS 1 1-0 \d\d\.\d% 100\.0% \+1\.20u/.test(winRec), 'window: the record grades the ticket inside or out on its own line', winRec);
  await pg.evaluate(async () => { await smStore.removeItem('callsheet3.card.v1'); }); await reloaded(); await pg.evaluate(() => smStore.ready);

  const stamp = await pg.evaluate(() => (document.getElementById('build') || {}).textContent);
  // ---- 5 Nov 2026: the simulation off the props, the market and the books' consensus in its place -- the strip, the best cards' last line, the panel's tiles, the column, the filter and the record's line, on a seeded night ----
  await pg.evaluate(async () => {
    await smStore.ready;
    const books = (cons, line) => ({ fanatics: [line, -110, -110], draftkings: [cons, -112, -108], fanduel: [cons, -110, -110], pinnacle: [cons, -112, -112] });
    const row = (id, name, team, mk, side, line, cons, edge, band, chance, result, shift) => ({ id, gdate: '2026-11-05', game: '76ers @ Knicks', away: '76ers', home: 'Knicks', aab: 'PHI', hab: 'NYK', pid: String(id), name, team, opp: team === 'PHI' ? 'NYK' : 'PHI', athome: team === 'NYK', pos: 'G', mk, line, op: -110, up: -110, book: 'fanatics',
      books: books(cons, line), proj: line + (side === 'OVER' ? 1.2 : -1.2), sd: 6, pm: side === 'OVER' ? 0.58 : 0.42, pb: 0.5, p: side === 'OVER' ? 0.5 + chance - 0.5 : 0.5 - (chance - 0.5), push: 0, side, chance, price: -110, need: 0.524, edge, band, mins: 33, rate36: 24, base: 22, med: line, usg: 26, sdf: 0.95, starter: true, start_src: "RotoWire's confirmed five",
      total: 229.5, spread: -5.5, why: ['24.0 points per 36 this season', "the books' consensus " + cons + ' across 4 books (Pinnacle ' + cons + ') against fanatics\'s ' + line], log: [], parts: [{ k: 'pace', t: 'Pace', eff: 0.3, i: 0 }, { k: 'cons', t: "The books' consensus, on the market's number", eff: shift * 6 / 0.4, i: 1 }],
      mkt: { tt: team === 'PHI' ? 112.0 : 117.5, ppg: team === 'PHI' ? 110.0 : 115.0, f: team === 'PHI' ? 1.018 : 1.022, em: 10.9, blow: 0.274 }, cons: { line: cons, n: 4, gap: Math.round((cons - line) * 100) / 100, pin: cons, shift },
      actual: result === 'win' ? (side === 'UNDER' ? line - 3 : line + 3) : result === 'loss' ? (side === 'UNDER' ? line + 3 : line - 3) : null, amin: result ? 34 : null, result });
    const rows = [row(1, 'Tyrese Maxey', 'PHI', 'pts', 'UNDER', 25.5, 24.5, 0.04, 'BET', 0.564, null, -0.015), row(2, 'Jalen Brunson', 'NYK', 'ast', 'OVER', 6.5, 5.5, 0.02, 'LEAN', 0.544, null, -0.03),
                  row(3, 'Joel Embiid', 'PHI', 'reb', 'OVER', 10.5, 11.5, 0.015, 'LEAN', 0.539, 'win', 0.03), row(4, 'Karl-Anthony Towns', 'NYK', 'pts', 'OVER', 22.5, 21.5, 0.01, 'LEAN', 0.534, 'loss', -0.015)];
    rows[2].parts.push({ k: 'minutes', t: 'Minutes, his last 5 against the season', eff: 0.5, i: 2 });   // a minutes spike (6 Nov 2026), for the record's own line
    rows[1].med = 7.5; rows[1].edge = 0.005; rows[1].books.draftkings = [5.5, 100, -120];   // the best app (6 Nov 2026): Brunson's over a point lower and at even money at DraftKings, his centre above the line so the re-read chance there clears the carded edge
    // the tells (7 Nov 2026): a pool of graded picks on an earlier night, so the spike's over reads green (40-20 before Embiid's win), the favourite's over red (20-40 before Towns' loss) and the spike's under too few (10)
    let pid = 100;
    const pool = (n, w, side, spikeEff, fav, mk) => { const out = []; for (let i = 0; i < n; i++) { const r = row(++pid, 'Pool Man ' + pid, fav ? 'NYK' : 'PHI', mk, side, 20.5, 20.5, 0.01, 'LEAN', 0.53, i < w ? 'win' : 'loss', 0); r.gdate = '2026-11-03'; r.cons = null; r.log = []; r.parts = spikeEff ? [{ k: 'minutes', t: 'Minutes, his last 5 against the season', eff: spikeEff, i: 0 }] : []; out.push(r); } return out; };
    rows.push(...pool(60, 40, 'OVER', 0.8, false, 'pts'), ...pool(60, 20, 'OVER', 0, true, 'reb'), ...pool(10, 6, 'UNDER', 0.6, false, 'ast'));
    await smStore.setItem('callsheet3.props.v1', JSON.stringify(rows));
  });
  await reloaded();
  const mktT = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 90));
    const txt = e => (e ? e.innerText : '').replace(/\s+/g, ' ').trim();
    await smStore.ready;
    document.getElementById('propsReset').click(); await wait();
    document.getElementById('m-props').click(); await wait();
    const strip = [...document.querySelectorAll('#propsSim .pk.simg')].map(e => e.className + '|' + txt(e));
    const best = [...document.querySelectorAll('#propsBest .pk')].map(e => { const l = e.querySelector('.n5.shopline') || e.querySelector('.n5.simline'); return txt(e.querySelector('.n2')) + '→' + (l ? l.className + '|' + txt(l) : 'none'); });
    const card = [...document.querySelectorAll('#propsBest .pk')].find(e => /Tyrese Maxey/.test(e.textContent));
    // the BET band in front, the best app and the close (6 Nov 2026)
    const betCard = txt(card), betCls = card.className, betN1 = txt(card.querySelector('.n1')), betWhy = txt(card.querySelector('.n5.betwhy')), leanCls = [...document.querySelectorAll('#propsBest .pk')].filter(e => !/Tyrese Maxey/.test(e.textContent)).map(e => e.className);
    const divider = txt(document.querySelector('#propsBest .pk-divider')), dividerAt = [...document.getElementById('propsBest').children].findIndex(e => e.classList.contains('pk-divider'));
    const bestApp = [...document.querySelectorAll('#propsBest .pk')].map(e => txt(e.querySelector('.n2')) + '→' + txt(e.querySelector('.n5.bestapp')));
    // the tells (7 Nov 2026): the chips on the cards, the filter and the panel's line
    const tells = [...document.querySelectorAll('#propsBest .pk')].map(e => txt(e.querySelector('.n2')) + '→' + [...e.querySelectorAll('.n5.tells .tell')].map(t => t.className + '|' + txt(t)).join(' ; '));
    const selT = (v) => { const el = document.getElementById('propsTells'); el.value = v; el.dispatchEvent(new Event('change', { bubbles: true })); };
    selT('green'); await wait(); const tellsGreen = [...document.querySelectorAll('#propsBest .pk .n2')].map(txt), tellsGreenDiv = txt(document.querySelector('#propsBest .pk-divider'));
    selT('red'); await wait(); const tellsRed = [...document.querySelectorAll('#propsBest .pk .n2')].map(txt);
    selT(''); await wait();
    const embiidCard = [...document.querySelectorAll('#propsBest .pk')].find(e => /Joel Embiid/.test(e.textContent)); embiidCard.click(); await wait();
    const panelTells = [...document.querySelectorAll('#propDetail .pd-tells .tell')].map(t => t.className + '|' + txt(t)), panelTellsDim = txt(document.querySelector('#propDetail .pd-tells .dim'));
    document.getElementById('propDetailClose').click(); await wait();
    const load = async (doc, fname) => { const dt = new DataTransfer(); dt.items.add(new File([JSON.stringify(doc)], fname, { type: 'application/json' })); const inp = document.getElementById('slateFile'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true })); await wait(); await wait(); };
    await load({ format: 'callsheet3.props.close', version: 1, date: '2026-11-05', generated: '2026-11-05T23:30:00Z', games: [{ gid: 'x', away: '76ers', home: 'Knicks', aab: 'PHI', hab: 'NYK', spread: -5.5, total: 229.5, props: [
      { pid: '1', name: 'Tyrese Maxey', team: 'PHI', opp: 'NYK', home: false, mk: 'pts', line: 24.5, op: -110, up: -110, book: 'fanatics', books: { fanatics: [24.5, -110, -110] } },
      { pid: '2', name: 'Jalen Brunson', team: 'NYK', opp: 'PHI', home: true, mk: 'ast', line: 6.5, op: -125, up: 105, book: 'fanatics', books: { fanatics: [6.5, -125, 105] } },
      { pid: '9', name: 'Nobody Here', team: 'NYK', opp: 'PHI', home: true, mk: 'pts', line: 10.5, op: -110, up: -110, book: 'fanatics', books: {} }] }] }, 'nba-props-close-2026-11-05.json');
    const closeMsg = txt(document.getElementById('propsMsg'));
    const clvCards = [...document.querySelectorAll('#propsBest .pk')].map(e => txt(e.querySelector('.n2')) + '→' + ((e.querySelector('.n5.clvline') || {}).className || '') + '|' + txt(e.querySelector('.n5.clvline')));
    const storedClose = JSON.parse(smStore.getItem('callsheet3.props.v1')).map(r => r.name + ':' + JSON.stringify(r.close || null));
    const card2 = [...document.querySelectorAll('#propsBest .pk')].find(e => /Tyrese Maxey/.test(e.textContent));
    card2.click(); await wait();
    const dlg = document.getElementById('propDetail');
    const panelBetWhy = txt(dlg.querySelector('.pd-betwhy')), panelClv = txt(dlg.querySelector('.pd-clv')), panelClvCls = (dlg.querySelector('.pd-clv') || {}).className || '';
    const tiles = [...dlg.querySelectorAll('.pd-mkt .pd-simtiles .pd-tile')].map(e => e.querySelector('.k').textContent + '=' + e.querySelector('.v').textContent + '|' + ((e.querySelector('.s') || {}).textContent || '').slice(0, 60) + '|' + e.className);
    const head = ((dlg.querySelector('.pd-mkt h4') || {}).textContent || '').replace(/\s+/g, ' ').trim(), simBlock = !!dlg.querySelector('.pd-sim:not(.pd-mkt)');
    const levers = [...dlg.querySelectorAll('.pd-levers .lever')].map(e => e.className + '|' + e.querySelector('.lt').textContent.trim());
    document.getElementById('propDetailClose').click(); await wait();
    const cells = [...document.querySelectorAll('#propsTable tbody tr[data-prop]')].map(tr => { const tds = tr.querySelectorAll('td'), c = tr.querySelector('td.simc'); return tds[1].textContent.trim() + '|' + (c ? c.textContent.trim() + '|' + c.className + '|' + c.title.slice(0, 50) : 'none'); });
    const sel = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('change', { bubbles: true })); };
    sel('propsSimSel', 'yes'); await wait(); const yes = [...document.querySelectorAll('#propsTable tbody tr[data-prop] td:nth-child(2)')].map(td => td.textContent.trim());
    sel('propsSimSel', 'no'); await wait(); const no = [...document.querySelectorAll('#propsTable tbody tr[data-prop] td:nth-child(2)')].map(td => td.textContent.trim());
    sel('propsSimSel', ''); await wait();
    // the Spike column and the tells filter on the table (9 Nov 2026)
    const nm = () => [...document.querySelectorAll('#propsTable tbody tr[data-prop] td:nth-child(2)')].map(td => td.textContent.trim().split(' ').slice(0, 2).join(' '));
    const spikeCells = [...document.querySelectorAll('#propsTable tbody tr[data-prop]')].map(tr => { const td = tr.querySelector('td.spikec'); return tr.querySelectorAll('td')[1].textContent.trim().split(' ').slice(0, 2).join(' ') + '|' + (td ? td.className + '|' + td.textContent.trim() + '|' + td.title.slice(0, 110) : 'none'); });
    const spikeHead = ((document.querySelector('#propsTable th[data-sort="spike"]') || {}).textContent || '').trim();
    sel('propsTellSel', 'spike'); await wait(); const tellSpike = nm();
    sel('propsTellSel', 'fav'); await wait(); const tellFav = nm();
    sel('propsTellSel', 'green'); await wait(); const tellGreen = nm();
    sel('propsTellSel', 'red'); await wait(); const tellRed = nm();
    sel('propsTellSel', ''); await wait();
    document.querySelector('#propsTable th[data-sort="spike"]').click(); await wait(); const spikeSorted = nm(), spikeHeadOn = document.querySelector('#propsTable th[data-sort="spike"]').textContent.trim();
    document.getElementById('propsReset').click(); await wait();
    const record = txt(document.getElementById('propsCalib'));
    // the same-game pairs at one app (5 Nov 2026): the card names the app, the panel reads the same ticket at each of the four apps
    const pairs = [...document.querySelectorAll('#propsPairs .pk')].map(e => txt(e).slice(0, 220));
    const pairCard = document.querySelector('#propsPairs .pk'); let pairApps = [], pairSub = '', pairHow = '';
    if (pairCard) { pairCard.click(); await wait(); pairApps = [...dlg.querySelectorAll('.pd-apps tbody tr')].map(tr => txt(tr).slice(0, 120)); pairSub = txt(dlg.querySelector('.pd-sub')); pairHow = txt([...dlg.querySelectorAll('.pd-base')].find(p => /Both legs are read at|No single app posts/.test(p.textContent))).slice(-200); document.getElementById('propDetailClose').click(); await wait(); }
    const selLabel = txt([...document.querySelectorAll('#propsView .propsctl label')].find(l => l.querySelector('#propsSimSel')));
    const subhead = txt([...document.querySelectorAll('#propsView .subhead')].find(e => /the market on the games/i.test(e.textContent)));
    const cardTile = txt(document.querySelector('#calibBox .calib[data-sport="PROPS"] .sides'));
    document.getElementById('propsReset').click(); await wait(); document.getElementById('m-nba').click(); await wait();
    await smStore.removeItem('callsheet3.props.v1');
    return { strip, best, tiles, head, simBlock, levers, cells, yes, no, record, selLabel, subhead, pairs, pairApps, pairSub, pairHow, betCard, betCls, betN1, betWhy, leanCls, divider, dividerAt, bestApp, closeMsg, clvCards, storedClose, panelBetWhy, panelClv, panelClvCls, cardTile,
             tells, tellsGreen, tellsGreenDiv, tellsRed, panelTells, panelTellsDim, spikeCells, spikeHead, tellSpike, tellFav, tellGreen, tellRed, spikeSorted, spikeHeadOn };
  });
  chk(/^pk scored bet$/.test(mktT.betCls) && /^BET #1 · BET · 3 to 5 points of edge levers/.test(mktT.betN1) && mktT.leanCls.length === 3 && mktT.leanCls.every(c => c === 'pk lean')
      && /^Why a BET: 56\.4% clears the 52\.4% that [-−]110 needs by 4\.0 points · the model says 58% at a fifth of the say, the book 50% · the books' consensus with it \([-−]1\.5 on the over\) · the top lever Pace \+0\.3, against it\.$/.test(mktT.betWhy) && mktT.panelBetWhy === mktT.betWhy
      && mktT.dividerAt === 1 && /^LEANs below: information, not a measured edge \(the band says 55% and does 52% over 1,300 graded picks\); the BETs above are the bets\.$/.test(mktT.divider),
      'props: the BET band in front (6 Nov 2026): the BET card carries the badge, its edge tier and a why line in words from its own numbers, the panel the same line, and the LEANs sit quieter under a divider that says what the record says of them', JSON.stringify({ cls: mktT.betCls, n1: mktT.betN1, why: mktT.betWhy, lean: mktT.leanCls, divider: mktT.divider, at: mktT.dividerAt }));
  chk(mktT.bestApp.some(b => /^Jalen Brunson OVER 6\.5 assists→Best app: DraftKings 5\.5 at \+100 · 5\d\.\d% there, edge \+\d\.\d against \+0\.5 at fanatics$/.test(b)) && mktT.bestApp.some(b => /^Tyrese Maxey UNDER 25\.5 points→$/.test(b)),
      'props: the best app for a single pick (6 Nov 2026): Brunson\'s over reads a point lower and at even money at DraftKings, so the card names it with the chance re-read there and the edge against the carded book; Maxey\'s under has no better line among the apps, so no line', JSON.stringify(mktT.bestApp));
  chk(/^The close nba-props-close-2026-11-05\.json attached to 2 props; 1 in the file had no prop loaded for the morning \(load the morning's props first; the close adds none\)\. Every pick now reads against the close/.test(mktT.closeMsg)
      && mktT.clvCards.some(c => /^Tyrese Maxey UNDER 25\.5 points→n5 clvline pos\|The close: 24\.5 at [-−]110 · the line moved the pick's way · beat the close by \d+\.\d points of edge$/.test(c))
      && mktT.clvCards.some(c => /^Jalen Brunson OVER 6\.5 assists→n5 clvline pos\|The close: 6\.5 at [-−]125 · the price moved the pick's way · beat the close by \d+\.\d points of edge$/.test(c))
      && mktT.clvCards.some(c => /^Joel Embiid OVER 10\.5 rebounds→\|$/.test(c)) && mktT.storedClose.some(s => /^Tyrese Maxey:\{"line":24\.5,"op":-110,"up":-110,"book":"fanatics","at":"2026-11-05T23:30:00Z"\}$/.test(s)) && mktT.storedClose.some(s => /^Joel Embiid:null$/.test(s))
      && /^The close: 24\.5 at [-−]110 · the line moved the pick's way · beat the close by \d+\.\d points of edge · the chance re-read at the closing line/.test(mktT.panelClv) && /pd-clv pos$/.test(mktT.panelClvCls)
      && /against the close: BET beat it 1 of 1 \(\+\d+\.\d pts a pick\) · LEAN 1 of 1 \(\+\d+\.\d\) · no edge 0 of 0/.test(mktT.cardTile) && /Against the close · closing line value 2 of 2 \+\d+\.\d points of edge a pick kept against the close · BET 1 of 1 \(\+\d+\.\d\) · LEAN 1 of 1 \(\+\d+\.\d\) · no edge 0 of 0/i.test(mktT.record),
      'props: the closing-line file (6 Nov 2026) attaches each prop\'s close to its row and adds none, the card and the panel read the pick against the close (Maxey\'s under beat it, the line moving its way; Brunson\'s over beat it on price), the record keeps how many picks beat the close by band and the points a pick', JSON.stringify({ msg: mktT.closeMsg, cards: mktT.clvCards, stored: mktT.storedClose, panel: mktT.panelClv, pcls: mktT.panelClvCls, tile: mktT.cardTile.slice(0, 600), record: mktT.record.replace(/^[\s\S]*?(Against the close)/, '$1').slice(0, 300) }));
  chk(/a man on a club favoured by 5 or more: unders 0-0 · overs 20-41 [-−]\d+\.\du \(shown, not scored\)/.test(mktT.cardTile) && /a minutes spike \(his last five above his season\): unders 6-4 \+\d\.\du · overs 41-20 \+\d+\.\du \(shown, not scored\)/.test(mktT.cardTile)
      && /A favourite's man \(5\+\), the under \(shown, not scored\) 0-0/i.test(mktT.record) && /A favourite's man \(5\+\), the over 20-41/i.test(mktT.record) && /A minutes spike, the under \(shown, not scored\) 6-4/i.test(mktT.record) && /A minutes spike, the over 41-20/i.test(mktT.record),
      'props: two lines that measure themselves (6 Nov 2026): a man on a club favoured by five or more (Towns on the Knicks at -5.5, the over, lost, after a seeded pool of 60) and a minutes spike (Embiid\'s last five above his season, the over, won, after a pool of 60; ten unders), by the side the sheet took, on the card\'s tile and as tiles on the tab', JSON.stringify({ tile: mktT.cardTile.slice(0, 900) }));
  chk(mktT.tells.some(t => /^Tyrese Maxey UNDER 25\.5 points→$/.test(t)) && mktT.tells.some(t => /^Joel Embiid OVER 10\.5 rebounds→tell green\|Minutes spike \+0\.5 · the over on a spike man not on a favourite does 67\.2%, claimed 53\.0%, on 61 BET and LEAN picks$/.test(t))
      && mktT.tells.some(t => /^Karl-Anthony Towns OVER 22\.5 points→tell red\|His club favoured by 5\.5 · the over on a favourite's man does 32\.8%, claimed 53\.0%, on 61 picks$/.test(t)) && mktT.tells.some(t => /^Jalen Brunson OVER 6\.5 assists→tell red\|His club favoured by 5\.5 · the over on a favourite's man does 32\.8%, claimed 53\.0%, on 61 picks$/.test(t))
      && JSON.stringify(mktT.tellsGreen) === '["Joel Embiid OVER 10.5 rebounds"]' && /^No BET among these\. LEANs below: information, not a measured edge/.test(mktT.tellsGreenDiv) && JSON.stringify(mktT.tellsRed.slice().sort()) === '["Jalen Brunson OVER 6.5 assists","Karl-Anthony Towns OVER 22.5 points"]'
      && mktT.panelTells.length === 1 && /^tell green\|Minutes spike \+0\.5 · the over on a spike man not on a favourite does 67\.2%, claimed 53\.0%, on 61 BET and LEAN picks$/.test(mktT.panelTells[0]) && /^· the tells \(7 Nov 2026\), shown, not scored: the favourite's chip reads every graded pick on this side, the spike's chip the BET and LEAN picks on a spike man not on a favourite \(10 Nov 2026: on a favourite's man the spike swings by the night and carries no colour\), the even-money chip the BET and LEAN picks at \+100 or longer since the blend changed on 5 Nov \(12 Nov 2026: a test\); green where the line has done at least what it claimed on 50 picks or more, red where less$/.test(mktT.panelTellsDim),
      'props: the tells (7 Nov 2026): a minutes spike and a favourite\'s man ride on the best cards as chips coloured live off the record on the pick\'s side (Embiid\'s spike green at 67% on 61 picks, Brunson\'s and Towns\' favourite\'s over red at 33%, Maxey none), the panel carries the same chip and its note, and the tells filter keeps the picks with a green tell and no red, or with a red one', JSON.stringify({ tells: mktT.tells, green: mktT.tellsGreen, div: mktT.tellsGreenDiv, red: mktT.tellsRed, panel: mktT.panelTells, dim: mktT.panelTellsDim }));
  chk(mktT.spikeHead === 'Spike' && mktT.spikeCells.some(c => /^Joel Embiid\|spikec pos\|\+0\.5\|Minutes, his last 5 against the season: \+0\.5 rebounds at his minutes; a spike at \+0\.3/.test(c)) && mktT.spikeCells.some(c => /^Tyrese Maxey\|spikec\|\|no minutes lever on this prop$/.test(c)) && mktT.spikeCells.length === 4
      && JSON.stringify(mktT.tellSpike) === '["Joel Embiid"]' && JSON.stringify(mktT.tellFav.slice().sort()) === '["Jalen Brunson","Karl-Anthony Towns"]' && JSON.stringify(mktT.tellGreen) === '["Joel Embiid"]' && JSON.stringify(mktT.tellRed.slice().sort()) === '["Jalen Brunson","Karl-Anthony Towns"]'
      && mktT.spikeSorted[0] === 'Joel Embiid' && mktT.spikeSorted.length === 4 && /^Spike ▾$/.test(mktT.spikeHeadOn),
      'props: the Spike column and the tells filter on the table (9 Nov 2026): the minutes lever\'s push in its own column, green at +0.3 and up with the words in the title, blank where a prop has no minutes lever, sortable with the spikes first, and the tells filter keeps the spikes, the favourites\' men, or the picks with a green or a red chip', JSON.stringify({ head: mktT.spikeHead, cells: mktT.spikeCells, spike: mktT.tellSpike, fav: mktT.tellFav, green: mktT.tellGreen, red: mktT.tellRed, sorted: mktT.spikeSorted, headOn: mktT.spikeHeadOn }));
  chk(mktT.pairs.length >= 3 && mktT.pairs.every(p => /^PAIR #\d · 76ers @ Knicks · at (Fanatics|DraftKings|FanDuel|BetMGM) · the price (agrees|asks more) /.test(p))
      && mktT.pairApps.length === 4 && mktT.pairApps.some(r => /chosen/.test(r)) && mktT.pairApps.some(r => /^BetMGM — — does not post both legs$/.test(r)) && mktT.pairApps.filter(r => /^(Fanatics|DraftKings|FanDuel)( chosen)? \d+(\.\d)? [-−+]\d+ \d+(\.\d)? [-−+]\d+ \d\d\.\d% [-−+]\d+ \d\d\.\d% [-−+]\d+\.\d$/.test(r)).length === 3
      && / · both at (Fanatics|DraftKings|FanDuel)$/.test(mktT.pairSub) && /Both legs are read at (Fanatics|DraftKings|FanDuel), (at the carded lines|the chance re-read at its line where it differs from the carded one), so the ticket goes into one app as it reads here\.$/.test(mktT.pairHow),
      'pairs: from 5 Nov 2026 every same-game pair is one app\'s ticket, both legs at that app\'s line and price with the best edge chosen, the card names the app, and the pair\'s panel reads the same ticket at each of the four apps with the chosen one marked and an app that posts only one leg said so',
      JSON.stringify({ pairs: mktT.pairs.slice(0, 3), apps: mktT.pairApps, sub: mktT.pairSub, how: mktT.pairHow }));
  chk(mktT.strip.length === 1 && /^pk simg mkt\|76ers @ Knicks · the market PHI 112 \(110 a game\) · NYK 117\.5 \(115 a game\) total 229\.5 · spread -5\.5 each club's points implied by the book's total and spread, against its points a game by the ratings · shown, not scored expected margin 10\.9 · blowout of 15 or more 27%, off the spread · the carded line sits off the books' consensus on 4 of 4 props$/.test(mktT.strip[0])
      && mktT.best.length === 4 && /^Tyrese Maxey UNDER 25\.5 points→n5 shopline pos\|The books: 4 post 24\.5 \(Pinnacle 24\.5\) · fanatics 25\.5 sits 1 above them, the UNDER's way · the book's chance read -1\.5 on the over, measured$/.test(mktT.best[0])
      && mktT.best.some(b => /^Jalen Brunson OVER 6\.5 assists→n5 shopline neg\|The books: 4 post 5\.5 \(Pinnacle 5\.5\) · fanatics 6\.5 sits 1 above them, against the OVER · the book's chance read -3\.0 on the over, measured$/.test(b))
      && mktT.best.some(b => /^Joel Embiid OVER 10\.5 rebounds→n5 shopline pos\|The books: 4 post 11\.5 \(Pinnacle 11\.5\) · fanatics 10\.5 sits 1 below them, the OVER's way · the book's chance read \+3\.0 on the over, measured/.test(b)),
      'props: with the simulation off, the strip above the picks carries the market on the game (each club\'s points implied by the total and spread against its average, the expected margin and the blowout off the spread, how many carded lines sit off the books\' consensus), and every best card ends with the books\' consensus against the carded line, green when it sits the pick\'s way', JSON.stringify({ strip: mktT.strip, best: mktT.best }));
  chk(/^The market on this game/.test(mktT.head) && !mktT.simBlock && mktT.tiles.length === 5
      && /^The books=24\.5\|4 post it · Pinnacle 24\.5 · fanatics 25\.5, 1 above\|pd-tile good$/.test(mktT.tiles[0]) && /^Consensus lever=-1\.5 pts\|on the book's over chance: half the measured slope, capped at six\|pd-tile good$/.test(mktT.tiles[1])
      && /^PHI points=112\|implied by the book's total and spread · 110 a game by the ratings \(×1\.018/.test(mktT.tiles[2]) && /^Expected margin=10\.9\|off the spread · a starter's minutes follow it/.test(mktT.tiles[3]) && /^Blowout=27%\|15 or more either way, off the spread/.test(mktT.tiles[4])
      && mktT.levers.some(l => /The books' consensus, on the market's number/.test(l))
      && mktT.cells.length === 4 && /^Tyrese Maxey\|24\.5\|simc pos\|the books' consensus line across 4 books/.test(mktT.cells.find(c => /^Tyrese Maxey/.test(c))) && /^Jalen Brunson\|5\.5\|simc neg\|/.test(mktT.cells.find(c => /^Jalen Brunson/.test(c)))
      && mktT.yes.join('|') === 'Tyrese Maxey|Joel Embiid' && mktT.no.slice().sort().join('|') === 'Jalen Brunson|Karl-Anthony Towns'
      && /the books' consensus with the pick 1-0 \+0\.9u · against it 0-1 -1\.0u/.test(mktT.record) && /THE BOOKS' CONSENSUS WITH THE PICK, HALF A POINT OR MORE 1-0/i.test(mktT.record) && /THE BOOKS' CONSENSUS AGAINST THE PICK 0-1/i.test(mktT.record)
      && /^the books the books' consensus on the pick's side$/i.test(mktT.selLabel.replace(/\s+all.*$/i, '').replace(/^the books\s+/i, 'the books ').slice(0, 9) + mktT.selLabel.slice(9).replace(/^.*?(the books' consensus on the pick's side).*$/i, ' $1')) || /the books/i.test(mktT.selLabel)
      && /^The market on the games in the simulation's place from 5 Nov 2026/i.test(mktT.subhead),
      'props: the prop\'s panel carries the market in the simulation\'s old place (the books with the carded line\'s gap, the consensus lever, the club\'s implied points, the expected margin, the blowout) and no simulation block, the levers list names the consensus, the table\'s column shows the consensus line green when it sits the pick\'s way, the filter keeps the props the consensus sides with (or against), and the record keeps the consensus\'s own line', JSON.stringify({ head: mktT.head, tiles: mktT.tiles, levers: mktT.levers, cells: mktT.cells, yes: mktT.yes, no: mktT.no, record: mktT.record.slice(0, 700), sel: mktT.selLabel, sub: mktT.subhead.slice(0, 80) }));

  // ---- 10 Nov 2026: one bet a man a night -- the note above the best list, the line on a man's several BET cards and on the panel, the record's tile and its line on the card's tile ----
  await pg.evaluate(async () => {
    await smStore.ready;
    const row = (id, gdate, pid, name, team, mk, side, line, edge, chance, result) => ({ id, gdate, game: 'Pelicans @ Warriors', away: 'Pelicans', home: 'Warriors', aab: 'NOP', hab: 'GSW', pid: String(pid), name, team, opp: team === 'GSW' ? 'NOP' : 'GSW', athome: team === 'GSW', pos: 'G', mk, line, op: -115, up: -115, book: 'betmgm',
      books: { betmgm: [line, -115, -115] }, proj: line + (side === 'OVER' ? 6 : -6), sd: 8, pm: side === 'OVER' ? 0.8 : 0.2, pb: 0.5, p: side === 'OVER' ? chance : 1 - chance, push: 0, side, chance, price: -115, need: 0.535, edge, band: 'BET', mins: 34, rate36: 30, base: 28, med: line + (side === 'OVER' ? 5.5 : -5.5), usg: 30, sdf: 0.9, starter: true, start_src: "RotoWire's expected five",
      total: 232.5, spread: -9.5, why: ['30.0 per 36 this season'], log: [], parts: [{ k: 'pace', t: 'Pace', eff: 1.0, i: 0 }], mkt: null, cons: null,
      actual: result === 'win' ? (side === 'UNDER' ? line - 3 : line + 3) : result === 'loss' ? (side === 'UNDER' ? line + 3 : line - 3) : null, amin: result ? 30 : null, result });
    const rows = [
      // a graded night: Curry's three BETs (the one with the most edge lost, one of the others won) and one BET on a Pelican, the dog
      row(1, '2026-11-08', 201, 'Stephen Curry', 'GSW', 'pra', 'OVER', 37.5, 0.047, 0.582, 'loss'), row(2, '2026-11-08', 201, 'Stephen Curry', 'GSW', 'pa', 'OVER', 33.5, 0.045, 0.58, 'loss'), row(3, '2026-11-08', 201, 'Stephen Curry', 'GSW', 'pts', 'OVER', 28.5, 0.038, 0.573, 'win'),
      row(4, '2026-11-08', 202, 'Dejounte Murray', 'NOP', 'ast', 'UNDER', 7.5, 0.04, 0.575, 'win'),
      // the night on the tab: Curry's three BETs again and one on Podziemski, all in one game
      row(5, '2026-11-09', 201, 'Stephen Curry', 'GSW', 'pra', 'OVER', 37.5, 0.047, 0.582, null), row(6, '2026-11-09', 201, 'Stephen Curry', 'GSW', 'pa', 'OVER', 33.5, 0.045, 0.58, null), row(7, '2026-11-09', 201, 'Stephen Curry', 'GSW', 'pts', 'OVER', 28.5, 0.038, 0.573, null),
      row(8, '2026-11-09', 203, 'Brandin Podziemski', 'GSW', 'pra', 'OVER', 24.5, 0.036, 0.571, null)];
    await smStore.setItem('callsheet3.props.v1', JSON.stringify(rows));
  });
  await reloaded();
  const oneT = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 90));
    const txt = e => (e ? e.innerText : '').replace(/\s+/g, ' ').trim();
    await smStore.ready;
    document.getElementById('propsReset').click(); await wait();
    document.getElementById('m-props').click(); await wait();
    const best = document.getElementById('propsBest');
    const note = txt(best.querySelector('.pk-note')), noteAt = [...best.children].findIndex(e => e.classList.contains('pk-note'));
    const cards = [...best.querySelectorAll('.pk')].map(e => txt(e.querySelector('.n2')) + '→' + txt(e.querySelector('.n5.onebet')));
    const card2 = [...best.querySelectorAll('.pk')].find(e => /Stephen Curry OVER 33\.5/.test(e.textContent)); card2.click(); await wait();
    const panel = txt(document.querySelector('#propDetail .pd-onebet'));
    document.getElementById('propDetailClose').click(); await wait();
    const record = txt(document.getElementById('propsCalib'));
    const cardTile = txt(document.querySelector('#calibBox .calib[data-sport="PROPS"] .sides'));
    document.getElementById('propsReset').click(); await wait(); document.getElementById('m-nba').click(); await wait();
    await smStore.removeItem('callsheet3.props.v1');
    return { note, noteAt, cards, panel, record, cardTile };
  });
  chk(oneT.note === "The 4 BETs on this date sit on 2 men in 1 game: a man's BETs land or miss together, so that is 2 bets, not 4; and one game carries them all, so a blowout or a slow night hits every one." && oneT.noteAt === 0
      && oneT.cards.length === 4 && oneT.cards[0] === 'Stephen Curry OVER 37.5 pts + reb + ast→One bet, not 3: he holds 3 BETs on this date (pts + reb + ast, pts + ast, points) and they land or miss together. This is the one with the most edge.'
      && oneT.cards[1] === 'Stephen Curry OVER 33.5 pts + ast→The same bet as his OVER 37.5 pts + reb + ast: one outcome, so take one of his 3 BETs, not all 3.' && oneT.cards[2] === 'Stephen Curry OVER 28.5 points→The same bet as his OVER 37.5 pts + reb + ast: one outcome, so take one of his 3 BETs, not all 3.'
      && oneT.cards[3] === 'Brandin Podziemski OVER 24.5 pts + reb + ast→' && oneT.panel === 'The same bet as his OVER 37.5 pts + reb + ast: one outcome, so take one of his 3 BETs, not all 3.',
      'props: one bet a man (10 Nov 2026): the best list opens with how many men and games the date\'s BETs sit on, the card with the most edge says it is the one of his three, his other two say they are the same bet, a man with one BET carries no line, and the panel says the same', JSON.stringify({ note: oneT.note, at: oneT.noteAt, cards: oneT.cards, panel: oneT.panel }));
  chk(/BET band 2-2 says 5\d\.\d% · does 50\.0%/i.test(oneT.record) && /BET band, one bet a man a night 1-1 says 5\d\.\d% · does 50\.0% \(±35\.4\) · [-−]0\.13u the over on a favourite's man 0-1 [-−]1\.0u · every other 1-0 \+0\.9u/i.test(oneT.record)
      && /BET, one a man a night 1-1 [-−]0\.1u \(the over on a favourite's man 0-1\)/.test(oneT.cardTile),
      'props: the record reads the BET band one bet a man a night beside the count by cards (10 Nov 2026): Curry\'s three BETs on the graded night count once, as the one with the most edge, which lost, the Pelican\'s under won, and the over on a favourite\'s man keeps its own count on the tile and on the card\'s line', JSON.stringify({ record: oneT.record.replace(/^[\s\S]*?(BET band)/i, '$1').slice(0, 420), tile: oneT.cardTile.slice(0, 500) }));

  // ---- 10 Nov 2026: the spike's chip split by the favourite -- read off the BET and LEAN picks, coloured off a favourite, plain on one ----
  await pg.evaluate(async () => {
    await smStore.ready;
    const row = (id, gdate, pid, name, team, side, band, edge, chance, result, spk) => ({ id, gdate, game: 'Pelicans @ Warriors', away: 'Pelicans', home: 'Warriors', aab: 'NOP', hab: 'GSW', pid: String(pid), name, team, opp: team === 'GSW' ? 'NOP' : 'GSW', athome: team === 'GSW', pos: 'G', mk: 'pts', line: 20.5, op: -110, up: -110, book: 'betmgm',
      books: { betmgm: [20.5, -110, -110] }, proj: 22.5, sd: 7, pm: 0.6, pb: 0.5, p: side === 'OVER' ? chance : 1 - chance, push: 0, side, chance, price: -110, need: 0.524, edge, band, mins: 30, rate36: 24, base: 20, med: 22, usg: 24, sdf: 1, starter: true, start_src: "RotoWire's expected five",
      total: 232.5, spread: -9.5, why: ['24.0 per 36 this season'], log: [], parts: spk ? [{ k: 'minutes', t: 'Minutes, his last 5 against the season', eff: spk, i: 0 }] : [], mkt: null, cons: null,
      actual: result === 'win' ? (side === 'UNDER' ? 17 : 24) : result === 'loss' ? (side === 'UNDER' ? 24 : 17) : null, amin: result ? 30 : null, result });
    const rows = []; let id = 0;
    const pool = (n, w, team, band, spk) => { for (let i = 0; i < n; i++) { id++; rows.push(row(id, '2026-11-08', 300 + id, 'Pool Man ' + id, team, 'OVER', band, band === 'no edge' ? -0.01 : 0.01, 0.53, i < w ? 'win' : 'loss', spk)); } };
    pool(60, 40, 'NOP', 'LEAN', 0.8);      // a spike, not on a favourite, in the bet bands: 40-20, green
    pool(60, 20, 'GSW', 'LEAN', 0.8);      // a spike on a favourite's man, in the bet bands: 20-40, no colour of its own; the favourite's over reads 20-40 off the same men
    pool(30, 0, 'NOP', 'no edge', 0.8);    // spike picks with no edge, every one lost: outside the chip's pools, inside the tile's
    rows.push(row(901, '2026-11-09', 901, 'Jeremiah Fears', 'NOP', 'OVER', 'LEAN', 0.02, 0.544, null, 0.6), row(902, '2026-11-09', 902, 'Stephen Curry', 'GSW', 'OVER', 'LEAN', 0.015, 0.539, null, 0.6), row(903, '2026-11-09', 903, 'Zion Williamson', 'NOP', 'OVER', 'LEAN', 0.01, 0.534, null, 0));
    await smStore.setItem('callsheet3.props.v1', JSON.stringify(rows));
  });
  await reloaded();
  const splitT = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 90));
    const txt = e => (e ? e.innerText : '').replace(/\s+/g, ' ').trim();
    await smStore.ready;
    document.getElementById('propsReset').click(); await wait();
    document.getElementById('m-props').click(); await wait();
    const all = [...document.querySelectorAll('#propsBest .pk')].map(e => txt(e.querySelector('.n2')).split(' OVER')[0] + '→' + [...e.querySelectorAll('.n5.tells .tell')].map(t => t.className + '|' + txt(t)).join(' ; '));
    const selT = (v) => { const el = document.getElementById('propsTells'); el.value = v; el.dispatchEvent(new Event('change', { bubbles: true })); };
    const names = () => [...document.querySelectorAll('#propsBest .pk .n2')].map(e => txt(e).split(' OVER')[0]);
    selT('green'); await wait(); const green = names();
    selT('red'); await wait(); const red = names();
    selT(''); await wait();
    const record = txt(document.getElementById('propsCalib')), cardTile = txt(document.querySelector('#calibBox .calib[data-sport="PROPS"] .sides'));
    document.getElementById('propsReset').click(); await wait(); document.getElementById('m-nba').click(); await wait();
    await smStore.removeItem('callsheet3.props.v1');
    return { all, green, red, record, cardTile };
  });
  chk(splitT.all.length === 3 && splitT.all[0] === 'Jeremiah Fears→tell green|Minutes spike +0.6 · the over on a spike man not on a favourite does 66.7%, claimed 53.0%, on 60 BET and LEAN picks'
      && splitT.all[1] === "Stephen Curry→tell plain|Minutes spike +0.6 · on a favourite's man the spike carries no colour: the over there is 20-40 on the BET and LEAN picks and swings by the night, so the favourite's chip is the read ; tell red|His club favoured by 9.5 · the over on a favourite's man does 33.3%, claimed 53.0%, on 60 picks"
      && splitT.all[2] === 'Zion Williamson→' && JSON.stringify(splitT.green) === '["Jeremiah Fears"]' && JSON.stringify(splitT.red) === '["Stephen Curry"]',
      'props: the spike\'s chip split by the favourite (10 Nov 2026): on a spike man not on a favourite it reads the BET and LEAN picks and takes their colour (40-20, green; thirty no-edge losses stay out of the pool), on a favourite\'s man it carries no colour and names the favourite\'s chip as the read, a man with neither carries nothing, and the tells filter follows', JSON.stringify({ all: splitT.all, green: splitT.green, red: splitT.red }));
  chk(/A minutes spike, the over 60-90 .*?the chip reads the BET and LEAN picks: not on a favourite 40-20 \(66\.7%\) · on a favourite 20-40 \(33\.3%\), no colour/i.test(splitT.record)
      && /the chip reads the BET and LEAN picks: the over off a favourite 40-20, on one 20-40/.test(splitT.cardTile),
      'props: the spike\'s tile keeps every band\'s count and says under it what the chip reads, off a favourite and on one, and the card\'s line the same (10 Nov 2026)', JSON.stringify({ record: splitT.record.replace(/^[\s\S]*?(A minutes spike, the over)/i, '$1').slice(0, 330), tile: splitT.cardTile.slice(-260) }));

  // ---- 11 Nov 2026: three-leg tickets under the BETs -- the legs' test, one app a ticket, three games before a shared one, a man in one ticket, the three modes, the copy, the take through a reload, the day board, the list kept at grading and the record ----
  belowFree = true;
  const t3Keep = await pg.evaluate(async () => { await smStore.ready; const k = { card: await smStore.getItem('callsheet3.card.v1'), slate: await smStore.getItem('callsheet3.slate.v1') }; await smStore.removeItem('callsheet3.props.v1'); return k; });
  await reloaded();
  const t3T = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 110));
    const txt = e => (e ? e.innerText : '').replace(/\s+/g, ' ').trim();
    await smStore.ready;
    const copies = []; try { Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: t => { copies.push(String(t)); return Promise.resolve(); } } }); } catch (e) {}
    const load = async (doc, name) => { const dt = new DataTransfer(); dt.items.add(new File([JSON.stringify(doc)], name, { type: 'application/json' })); const inp = document.getElementById('slateFile'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true })); await wait(); await wait(); };
    const G = [['Hawks', 'Magic', 'ATL', 'ORL', -2.5], ['Bulls', 'Bucks', 'CHI', 'MIL', -2.5], ['Heat', 'Jazz', 'MIA', 'UTA', -2.5], ['Suns', 'Kings', 'PHX', 'SAC', -7.5]];
    const ov = L => [L + 2, L - 2, L + 3, L - 1, L + 1, L + 2, L + 4, L - 3, L + 1, L + 2], un = L => [L - 2, L + 2, L - 3, L + 1, L - 1, L - 2, L - 4, L + 3, L - 1, L - 2];   // four of the last five and seven of the last ten the pick's way
    const up = [{ k: 'pace', t: 'Pace', eff: 0.4, i: 0 }, { k: 'dvp', t: 'Defence v position', eff: 0.6, i: 0 }], dn = [{ k: 'pace', t: 'Pace', eff: -0.4, i: 0 }, { k: 'dvp', t: 'Defence v position', eff: -0.6, i: 0 }];
    const man = (pid, name, team, gi, mk, side, line, chance, vals, parts, books) => ({ gi, pid: String(pid), name, team, opp: team === G[gi][2] ? G[gi][3] : G[gi][2], home: team === G[gi][3], pos: 'G', mk, line, op: -110, up: -110, book: books ? Object.keys(books)[0] : 'fanduel',
      books: books || { fanduel: [line, -110, -110], draftkings: [line, -115, -115] }, proj: line + (side === 'OVER' ? 2 : -2), sd: 6, pm: side === 'OVER' ? 0.7 : 0.3, pb: 0.5, p: side === 'OVER' ? chance : Math.round((1 - chance) * 10000) / 10000, push: 0, side, chance, price: -110, need: 0.5238,
      edge: Math.round((chance - 0.5238) * 10000) / 10000, band: 'LEAN', mins: 32, rate36: 20, base: 18, med: line + (side === 'OVER' ? 1.5 : -1.5), usg: 22, sdf: 1, starter: true, start_src: "RotoWire's expected five", why: ['x'],
      log: vals.map((v, i) => ['2026-10-' + String(20 + i), 'OPP', i % 2, 32, v, ['won by 3']]), parts });
    const men = () => [man(1, 'Man One', 'ATL', 0, 'pts', 'OVER', 20.5, 0.60, ov(20.5), up), man(2, 'Man Two', 'CHI', 1, 'reb', 'OVER', 7.5, 0.59, ov(7.5), up), man(3, 'Man Three', 'MIA', 2, 'ast', 'UNDER', 5.5, 0.58, un(5.5), dn),
      man(7, 'Man Seven', 'ORL', 0, 'tpm', 'UNDER', 4.5, 0.57, un(4.5), dn, { fanduel: [4.5, -110, -110], draftkings: [3.5, -170, 140] }),   // DraftKings posts him a point lower at a price with an edge: three of his last five under it, so no leg there
      man(8, 'Man Eight', 'MIL', 1, 'pts', 'OVER', 12.5, 0.56, ov(12.5), up), man(9, 'Man Nine', 'MIL', 1, 'reb', 'OVER', 6.5, 0.55, ov(6.5), up),
      man(4, 'Cold Hand', 'ATL', 0, 'pts', 'OVER', 15.5, 0.60, [17.5, 17.5, 18.5, 16.5, 16.5, 13.5, 14.5, 17.5, 12.5, 16.5], up),   // two of his last five: no leg
      man(5, 'Wrong Levers', 'CHI', 1, 'ast', 'OVER', 4.5, 0.60, ov(4.5), dn),                                                    // the levers against the over: no leg
      man(6, 'Other App', 'MIA', 2, 'pts', 'OVER', 18.5, 0.60, ov(18.5), up, { betmgm: [18.5, -110, -110] }),                      // a leg at BetMGM alone: no three there
      man(10, 'Big Fav', 'SAC', 3, 'pts', 'OVER', 22.5, 0.62, ov(22.5), up)];                                                      // the over on a favourite's man: out until its record reads green
    const doc = (list) => ({ format: 'callsheet3.props', version: 1, date: '2026-11-12', games: G.map((g, gi) => ({ gid: 't3' + gi, away: g[0], home: g[1], aab: g[2], hab: g[3], spread: g[4], total: 225.5, props: list.filter(m => m.gi === gi) })) });
    await load(doc(men()), 'nba-props-2026-11-12.json');
    if (document.getElementById('propsView').hidden) { document.getElementById('m-props').click(); await wait(); }
    document.getElementById('propsReset').click(); await wait();
    const sel = (v) => { const el = document.getElementById('propsBelow'); el.value = v; el.dispatchEvent(new Event('change', { bubbles: true })); };
    const best = document.getElementById('propsBest');
    const tix = (root) => [...(root || best).querySelectorAll('.pk.t3')].map(e => ({ n1: txt(e.querySelector('.n1')), pay: txt(e.querySelector('.t3pay')), legs: [...e.querySelectorAll('.leg')].map(txt), pips: [...e.querySelectorAll('.leg .pips')].map(p => [...p.querySelectorAll('i')].map(i => i.className.replace(' g5', '|')).join('')).join(','), stats: txt(e.querySelector('.t3stats')), n4: txt(e.querySelector('.n4')), n6: txt(e.querySelector('.n6')), cls: e.className }));
    const opts = [...document.querySelectorAll('#propsBelow option')].map(o => o.value + '=' + o.textContent), legOpts = [...document.querySelectorAll('#propsLegs option')].map(o => o.value + '=' + o.textContent);
    const selLegs = (v) => { const el = document.getElementById('propsLegs'); el.value = v; el.dispatchEvent(new Event('change', { bubbles: true })); };
    const tabsOf = (c) => [...c.querySelectorAll('.t3apps .t3app')].map(a => txt(a) + (a.classList.contains('on') ? '*' : a.classList.contains('off') ? ' (off)' : ''));
    const brief = (t) => t.n1 + ' :: ' + t.legs.map(l => l.split(' ').slice(1, 3).join(' ')).join(' + ') + ' :: ' + t.stats.toLowerCase() + ' :: ' + t.cls;
    // two legs a ticket, the default: the best pair first, on two games, by the same leg rule
    sel('t3'); selLegs('2'); await wait();
    const twoL = tix(), twoDiv = txt(best.querySelector('.pk-divider.t3d')), twoTabs = [...best.querySelectorAll('.pk.t3')].map(tabsOf), twoWhys = [...best.querySelectorAll('.pk.t3')].map(c => txt(c.querySelector('.t3why'))), twoLabel = txt(best.querySelector('.pk.t3 .t3apl')), storedLegs = await smStore.getItem('callsheet3.props.legs.v1');
    sel('t3o'); await wait(); const twoO = tix().map(brief);
    sel('t3u'); await wait(); const twoU = tix().map(brief);
    sel('t3'); await wait();
    copies.length = 0; best.querySelector('.pk.t3 [data-t3copy]').click(); await wait(); await wait(); const twoCopy = copies.slice();
    selLegs('3'); await wait();
    const either = tix(), divider = txt(best.querySelector('.pk-divider.t3d')), others = best.querySelectorAll('.pk:not(.t3)').length, inGrid = best.querySelectorAll('.t3grid > .pk.t3').length, pipTitle = (best.querySelector('.pk.t3 .pips i') || {}).title, pipAria = best.querySelector('.pk.t3 .pips') ? best.querySelector('.pk.t3 .pips').getAttribute('aria-label') : '';
    sel('t3o'); await wait(); const overs = tix(), dividerO = txt(best.querySelector('.pk-divider.t3d'));
    sel('t3u'); await wait(); const unders = tix(), none = txt(best.querySelector('.empty.t3none'));
    sel('leans'); await wait(); const leans = [...best.querySelectorAll('.pk')].map(e => txt(e.querySelector('.n2'))), leansT3 = best.querySelectorAll('.pk.t3').length, leansDiv = txt(best.querySelector('.pk-divider'));
    sel('t3'); await wait();
    const stored0 = await smStore.getItem('callsheet3.props.below.v1');
    // the same three at another app: the tabs, the ticket shown there, the copy and the take there, and back
    const cards0 = [...best.querySelectorAll('.pk.t3')], tabs = cards0.map(tabsOf), whys = cards0.map(c => txt(c.querySelector('.t3why'))), tabLabel = txt(cards0[0].querySelector('.t3apl'));
    cards0[0].querySelector('button.t3app:not(.on)').click(); await wait();
    const atDK = tix()[0], tabsDK = tabsOf(best.querySelector('.pk.t3')), secondStays = tix()[1].n1;
    copies.length = 0; best.querySelector('.pk.t3 [data-t3copy]').click(); await wait(); await wait();
    const copiedDK = copies.slice();
    best.querySelector('.pk.t3 [data-t3take]').click(); await wait();
    const dkTaking = tix(document.getElementById('propsTaking')).map(t => t.n1), dkTabs = tabsOf(best.querySelector('.pk.t3')), dkSpec = ((JSON.parse(await smStore.getItem('callsheet3.props.v1')).find(r => r.pid === '1') || {}).t3 || []).map(sp => sp.id + (sp.take ? '/take' : ''));
    best.querySelector('.pk.t3 [data-t3take]').click(); await wait();
    const dkUntaken = tix(document.getElementById('propsTaking')).length + '|' + (((JSON.parse(await smStore.getItem('callsheet3.props.v1')).find(r => r.pid === '1') || {}).t3 || []).length);
    [...best.querySelector('.pk.t3').querySelectorAll('button.t3app')].find(a => /FanDuel/.test(a.textContent)).click(); await wait();
    const backAtFD = tix()[0].n1;
    // a leg opens his panel; Copy puts the ticket in words and opens nothing; Take marks it and the strip carries it
    best.querySelector('.pk.t3 .leg').click(); await wait();
    const legPanel = document.getElementById('propDetail').hidden ? '' : txt(document.querySelector('#propDetailBody h3'));
    document.getElementById('propDetailClose').click(); await wait();
    copies.length = 0; best.querySelector('.pk.t3 [data-t3copy]').click(); await wait(); await wait();
    const copied = copies.slice(), copySay = txt(document.getElementById('propsMsg')), panelAfterCopy = !document.getElementById('propDetail').hidden;
    best.querySelector('.pk.t3 [data-t3take]').click(); await wait();
    const taking = tix(document.getElementById('propsTaking')), takingCount = txt(document.getElementById('propsTakingCount')), takeBtn = txt(document.querySelector('#propsBest .pk.t3 [data-t3take]')), bestCls = best.querySelector('.pk.t3').className;
    const spec0 = (JSON.parse(await smStore.getItem('callsheet3.props.v1')).find(r => r.pid === '1') || {}).t3 || [];
    // the file loaded again with Man Two's pick turned to the under at a moved line: the ticket taken keeps its own legs, lines and sides
    const again = men(), two = again.find(m => m.pid === '2'); two.side = 'UNDER'; two.line = 8.5; two.chance = 0.55; two.p = 0.45; two.edge = 0.0262; two.books = { fanduel: [8.5, -110, -110], draftkings: [8.5, -115, -115] };
    await load(doc(again), 'nba-props-2026-11-12.json');
    if (document.getElementById('propsView').hidden) { document.getElementById('m-props').click(); await wait(); }
    const msg2 = txt(document.getElementById('propsMsg')).slice(0, 90), taking2 = tix(document.getElementById('propsTaking')), live2 = tix();
    // the day board carries the ticket, and its text
    document.getElementById('m-nba').click(); await wait();
    const bd = document.getElementById('boardDate'); bd.value = '2026-11-12'; bd.dispatchEvent(new Event('change')); await wait();
    const board = tix(document.getElementById('taking')), boardSum = txt(document.querySelector('#taking .pk.taking.sum')), boardCount = txt(document.getElementById('takingCount'));
    copies.length = 0; document.getElementById('takingText').click(); await wait(); await wait();
    const boardText = copies.slice();
    document.getElementById('m-props').click(); await wait();
    // the grade: the list is kept on the rows before the results land, then each ticket is graded on its own lines and sides
    const box = (pid, name, pts, reb, ast, tpm) => [pid, [name, 32, pts, reb, ast, tpm]];
    const gdoc = { format: 'callsheet2.slate', version: 1, date: '2026-11-12', games: [
      { sport: 'NBA', gdate: '2026-11-12', away: 'Hawks', home: 'Magic', gameId: 't3a', finals: { fa: '110', fh: '105', f5a: '55', f5h: '50' }, notes: [], box: Object.fromEntries([box('1', 'Man One', 25, 4, 4, 2), box('7', 'Man Seven', 12, 3, 2, 6), box('4', 'Cold Hand', 10, 2, 2, 1)]) },
      { sport: 'NBA', gdate: '2026-11-12', away: 'Bulls', home: 'Bucks', gameId: 't3b', finals: { fa: '100', fh: '111', f5a: '50', f5h: '56' }, notes: [], box: Object.fromEntries([box('2', 'Man Two', 14, 9, 3, 1), box('8', 'Man Eight', 10, 4, 2, 1), box('9', 'Man Nine', 8, 8, 1, 0), box('5', 'Wrong Levers', 9, 2, 6, 0)]) },
      { sport: 'NBA', gdate: '2026-11-12', away: 'Heat', home: 'Jazz', gameId: 't3c', finals: { fa: '104', fh: '99', f5a: '52', f5h: '49' }, notes: [], box: Object.fromEntries([box('3', 'Man Three', 11, 3, 3, 1), box('6', 'Other App', 22, 5, 3, 2)]) },
      { sport: 'NBA', gdate: '2026-11-12', away: 'Suns', home: 'Kings', gameId: 't3d', finals: { fa: '101', fh: '120', f5a: '50', f5h: '61' }, notes: [], box: Object.fromEntries([box('10', 'Big Fav', 30, 5, 3, 2)]) }] };
    await load(gdoc, 'nba-grade-2026-11-12.json');
    if (document.getElementById('propsView').hidden) { document.getElementById('m-props').click(); await wait(); }
    const after = tix(), afterDiv = txt(best.querySelector('.pk-divider.t3d')), afterTaking = tix(document.getElementById('propsTaking'));
    const rowsNow = JSON.parse(await smStore.getItem('callsheet3.props.v1')), specs = rowsNow.filter(r => r.t3).map(r => r.name + ':' + r.t3.map(sp => sp.app + '/' + sp.m + '/' + sp.ks.length + (sp.listed ? '/listed' + sp.n : '') + (sp.c ? '/c' + sp.c : '') + (sp.take ? '/take' : '')).join(',')).join(';');
    const twoRow = rowsNow.find(r => r.pid === '2');
    const record = txt(document.getElementById('propsCalib')), cardTile = txt(document.querySelector('#calibBox .calib[data-sport="PROPS"] .sides')), took = txt(document.querySelector('#calibBox .calib[data-sport="TAKEN"]'));
    selLegs('2'); await wait(); const afterTwo = tix().map(brief), afterTwoDiv = txt(best.querySelector('.pk-divider.t3d')); selLegs('3'); await wait();
    sel('t3o'); await wait(); const afterO = tix(), afterODiv = txt(best.querySelector('.pk-divider.t3d'));
    sel('t3'); await wait();
    await load(gdoc, 'nba-grade-2026-11-12.json');   // the grade loaded again leaves the list as it was kept
    const specs2 = JSON.parse(await smStore.getItem('callsheet3.props.v1')).filter(r => r.t3).map(r => r.name + ':' + r.t3.length).join(',');
    selLegs('2'); sel('leans'); await wait();
    if (!document.getElementById('propsView').hidden) { document.getElementById('propsReset').click(); await wait(); } document.getElementById('m-nba').click(); await wait();
    return { legOpts, two: twoL, twoDiv, twoTabs, twoWhys, twoLabel, storedLegs, twoO, twoU, twoCopy, afterTwo, afterTwoDiv, tabs, whys, tabLabel, atDK, tabsDK, secondStays, copiedDK, dkTaking, dkTabs, dkSpec, dkUntaken, backAtFD, opts, either, divider, others, inGrid, pipTitle, pipAria, overs, dividerO, unders, none, leans, leansT3, leansDiv, stored0, legPanel, copied, copySay, panelAfterCopy, taking, takingCount, takeBtn, bestCls, spec0, msg2, taking2, live2, board, boardSum, boardCount, boardText, after, afterDiv, afterTaking, specs, twoRow: [twoRow.side, twoRow.line, twoRow.result, twoRow.actual], record, cardTile, took, afterO, afterODiv, specs2 };
  });
  await pg.evaluate(async (k) => { await smStore.removeItem('callsheet3.props.v1'); if (k.card === null || k.card === undefined) await smStore.removeItem('callsheet3.card.v1'); else await smStore.setItem('callsheet3.card.v1', k.card); if (k.slate === null || k.slate === undefined) await smStore.removeItem('callsheet3.slate.v1'); else await smStore.setItem('callsheet3.slate.v1', k.slate); }, t3Keep);
  belowFree = false;
  await reloaded();
  const lc = v => String(v || '').toLowerCase(), legOf = (t, i) => lc(t && t.legs[i]);
  const t3Leg = (n, name, pick, price, pct, where, avg) => `${n} ${name} ${pick} ${price} · ${pct}% last 5: 4 of 5 · last 10: 7 of 10 ${where} · averaging ${avg} his last five · levers 2▲ 0▼`.toLowerCase();
  chk(legsDefault === '2' && t3T.legOpts.join('|') === '2=2 legs|3=3 legs' && t3T.storedLegs === '2' && t3T.two.length === 2
      && t3T.twoDiv === "No BET on this date. Two-leg tickets below, to test, in the LEANs' place: two men at one app on two games, each a pick with an edge whose last five games went his way four times or more and his last ten at least half, more levers toward the pick than against and no red chip. A card is one app throughout; where the same two also pass at another app, a tab on the card shows the ticket there. Replayed on the eleven nights that keep the logs and the levers, exactly as built here: such legs went 45-28 one at a time (the overs 20-7, the unders 25-21) and the tickets 7 of 20 for +2.8 units, where three legs went 2 of 12 for +0.7. A test, not a measured edge: its record builds in Is it working, and the LEANs are one choice away."
      && t3T.two[0].n1 === '2 LEGS #1 · at FanDuel · two games' && t3T.two[0].pay === '+264 3.64×' && t3T.two[0].legs.length === 2 && legOf(t3T.two[0], 0) === t3Leg(1, 'Man One', 'OVER 20.5 points', '-110', '60.0', 'ATL @ ORL', '21.7') && legOf(t3T.two[0], 1) === t3Leg(2, 'Man Two', 'OVER 7.5 rebounds', '-110', '59.0', 'CHI @ MIL', '8.7')
      && lc(t3T.two[0].stats) === 'both land 35.4% needs 27.4% edge +8.0 a unit wins 2.64u' && t3T.two[0].n4 === '' && lc(t3T.two[0].n6) === 'take copy ticket'
      && t3T.two[1].n1 === '2 LEGS #2 · at FanDuel · two games' && t3T.two[1].legs.map(l => l.split(' ').slice(1, 3).join(' ')).join(',') === 'Man Three,Man Seven' && lc(t3T.two[1].stats) === 'both land 33.1% needs 27.4% edge +5.6 a unit wins 2.64u'
      && /^the same two at$/i.test(t3T.twoLabel) && JSON.stringify(t3T.twoTabs) === '[["DraftKings +250 35.4%","FanDuel +264 35.4%*"],["DraftKings × (off)","FanDuel +264 33.1%*"]]' && t3T.twoWhys[1] === "Not at DraftKings: Man Seven's line is 3.5 there, 3 of his last 5 under it."
      && t3T.twoO.length === 1 && /^2 LEGS #1 · at FanDuel · two games :: Man One \+ Man Two :: both land 35\.4%/.test(t3T.twoO[0]) && t3T.twoU.length === 1 && /^2 LEGS #1 · at FanDuel · two games :: Man Three \+ Man Seven :: both land 33\.1%/.test(t3T.twoU[0])
      && t3T.twoCopy.length === 1 && t3T.twoCopy[0] === '2-leg ticket at FanDuel · pays +264 (3.64x) · both land 35.4%, needs 27.4%\n1. Man One OVER 20.5 points -110 · last 5: 4 of 5, last 10: 7 of 10 · Hawks @ Magic\n2. Man Two OVER 7.5 rebounds -110 · last 5: 4 of 5, last 10: 7 of 10 · Bulls @ Bucks'
      && !/Cold Hand|Wrong Levers|Other App|Big Fav|Man Eight|Man Nine/i.test(JSON.stringify(t3T.two)),
      'two-leg tickets (11 Nov 2026, the user: what about instead of the 3, we do 2 legs, the absolute best 2 men pairs): two legs are the default on a first visit and the choice is kept; the same leg rule, the best pair first by expected value, two men on two games at one app, a man in one ticket; the two men left on one game make no ticket (a same-game two is the pairs\' own section); the card reads both land, the tabs the same two at another app, the overs and the unders alone their own pair, and Copy the two-leg ticket in words', JSON.stringify({ def: legsDefault, opts: t3T.legOpts, stored: t3T.storedLegs, two: t3T.two, div: t3T.twoDiv.slice(0, 140), tabs: t3T.twoTabs, whys: t3T.twoWhys, label: t3T.twoLabel, overs: t3T.twoO, unders: t3T.twoU, copy: t3T.twoCopy }));
  chk(belowDefault === 't3' && t3T.opts.join('|') === 't3=tickets, either side|t3o=tickets, overs|t3u=tickets, unders|t3c=tickets, best chance|plus=even money or better|leans=the LEANs one by one' && t3T.stored0 === 't3'
      && t3T.either.length === 2 && t3T.inGrid === 2 && t3T.others === 0
      && t3T.divider === "No BET on this date. Three-leg tickets below, to test, in the LEANs' place: three men at one app, each a pick with an edge whose last five games went his way four times or more and his last ten at least half, more levers toward the pick than against and no red chip. A card is one app throughout; where the same three also pass at another app, a tab on the card shows the ticket there. Replayed on the eleven nights that keep the logs and the levers, exactly as built here: such legs went 45-28 one at a time (the overs 20-7, the unders 25-21) and the tickets 2 of 12 for +0.7 units, where two legs went 7 of 20 for +2.8. A test, not a measured edge: its record builds in Is it working, and the LEANs are one choice away."
      && t3T.either[0].n1 === '3 LEGS #1 · at FanDuel · three games' && t3T.either[0].pay === '+596 6.96×' && t3T.either[0].legs.length === 3
      && legOf(t3T.either[0], 0) === t3Leg(1, 'Man One', 'OVER 20.5 points', '-110', '60.0', 'ATL @ ORL', '21.7') && legOf(t3T.either[0], 1) === t3Leg(2, 'Man Two', 'OVER 7.5 rebounds', '-110', '59.0', 'CHI @ MIL', '8.7')
      && legOf(t3T.either[0], 2) === t3Leg(3, 'Man Three', 'UNDER 5.5 assists', '-110', '58.0', 'MIA @ UTA', '4.3') && t3T.either[0].pips === 'hmhmhh|hmhh,hmhmhh|hmhh,hmhmhh|hmhh'
      && lc(t3T.either[0].stats) === 'all three land 20.5% needs 14.4% edge +6.2 a unit wins 5.96u' && t3T.either[0].n4 === '' && lc(t3T.either[0].n6) === 'take copy ticket'
      && t3T.pipTitle === '10-20 @ OPP: 22.5, his way' && t3T.pipAria === "his last 10 games, oldest first: 7 went the pick's way",
      'three-leg tickets (11 Nov 2026): under the BETs on a first visit, either side, in their own grid with the LEAN cards away; a leg is a pick with an edge, four of his last five and half of his last ten his way and the levers toward him, three men at one app on three games with the most expected value first; the card carries the price, each leg\'s chip, price and chance, his last ten as pips with the last five set apart, the counts, his last five\'s average and the levers, and the ticket\'s chance, what it needs, the edge and what a unit wins', JSON.stringify({ def: belowDefault, opts: t3T.opts, either: t3T.either[0], divider: t3T.divider, others: t3T.others, inGrid: t3T.inGrid, pip: [t3T.pipTitle, t3T.pipAria] }));
  chk(t3T.either.length === 2 && t3T.either[1].n1 === '3 LEGS #2 · at FanDuel · two games' && legOf(t3T.either[1], 0) === t3Leg(1, 'Man Seven', 'UNDER 4.5 threes', '-110', '57.0', 'ORL v ATL', '3.3')
      && legOf(t3T.either[1], 1) === t3Leg(2, 'Man Eight', 'OVER 12.5 points', '-110', '56.0', 'MIL v CHI', '13.7') && legOf(t3T.either[1], 2) === t3Leg(3, 'Man Nine', 'OVER 6.5 rebounds', '-110', '55.0', 'MIL v CHI', '7.7')
      && lc(t3T.either[1].stats) === 'all three land 16.7% needs 14.4% edge +2.3 a unit wins 5.96u'
      && t3T.either[1].n4 === 'Two legs share a game: the app prices same-game legs its own way, usually a little under the product shown; two overs on one club carry the measured ×0.95.'
      && !/Cold Hand|Wrong Levers|Other App|Big Fav/i.test(JSON.stringify([t3T.either, t3T.overs])),
      'three-leg tickets: a man sits in one ticket, so the second is built from the three left; with no three games among them two legs share a game, the card says so and two overs on one club carry the measured 0.95; the cold hand, the man with the levers against him, the man posted at another app alone and the over on a favourite\'s man with no record yet make no leg', JSON.stringify({ second: t3T.either[1] }));
  chk(t3T.overs.length === 1 && t3T.overs[0].n1 === '3 LEGS #1 · at FanDuel · two games' && t3T.overs[0].legs.map(l => l.split(' ').slice(1, 3).join(' ')).join(',') === 'Man One,Man Two,Man Eight'
      && lc(t3T.overs[0].stats) === 'all three land 19.8% needs 14.4% edge +5.5 a unit wins 5.96u' && t3T.overs[0].n4 === 'Two legs share a game: the app prices same-game legs its own way, usually a little under the product shown.'
      && /and no red chip, the overs only\. A card is one app throughout; where the same three also pass at another app, a tab on the card shows the ticket there\. Replayed on the eleven nights/.test(t3T.dividerO)
      && t3T.unders.length === 0 && t3T.none === 'No three legs on this date pass the test at one app among the unders.'
      && t3T.leansT3 === 0 && t3T.leans.length === 10 && t3T.leans[0] === 'Big Fav OVER 22.5 points' && /^No BET on this date\. LEANs below/.test(t3T.leansDiv),
      'three-leg tickets: the overs alone make one ticket, on two games for want of a third, with the note on the app\'s own price and no factor where the two share no club; the unders alone make none and say so; the LEANs one by one bring the ten cards back with no ticket', JSON.stringify({ overs: t3T.overs, dividerO: t3T.dividerO.slice(260, 380), unders: t3T.unders, none: t3T.none, leans: t3T.leans, leansT3: t3T.leansT3, leansDiv: t3T.leansDiv }));
  chk(/^the same three at$/i.test(t3T.tabLabel) && JSON.stringify(t3T.tabs) === '[["DraftKings +553 20.5%","FanDuel +596 20.5%*"],["DraftKings × (off)","FanDuel +596 16.7%*"]]'
      && t3T.whys[0] === '' && t3T.whys[1] === "Not at DraftKings: Man Seven's line is 3.5 there, 3 of his last 5 under it."
      && t3T.atDK.n1 === '3 LEGS #1 · at DraftKings · three games' && t3T.atDK.pay === '+553 6.53×' && legOf(t3T.atDK, 0) === t3Leg(1, 'Man One', 'OVER 20.5 points', '-115', '60.0', 'ATL @ ORL', '21.7') && legOf(t3T.atDK, 2) === t3Leg(3, 'Man Three', 'UNDER 5.5 assists', '-115', '58.0', 'MIA @ UTA', '4.3')
      && lc(t3T.atDK.stats) === 'all three land 20.5% needs 15.3% edge +5.2 a unit wins 5.53u' && JSON.stringify(t3T.tabsDK) === '["DraftKings +553 20.5%*","FanDuel +596 20.5%"]' && t3T.secondStays === '3 LEGS #2 · at FanDuel · two games'
      && t3T.copiedDK.length === 1 && /^3-leg ticket at DraftKings · pays \+553 \(6\.53x\) · all three land 20\.5%, needs 15\.3%\n1\. Man One OVER 20\.5 points -115 /.test(t3T.copiedDK[0])
      && JSON.stringify(t3T.dkTaking) === '["TAKING · 3 LEGS · at DraftKings · three games"]' && JSON.stringify(t3T.dkTabs) === '["✓ DraftKings +553 20.5%*","FanDuel +596 20.5%"]' && JSON.stringify(t3T.dkSpec) === '["t3|2026-11-12|draftkings|1:pts|2:reb|3:ast/take"]'
      && t3T.dkUntaken === '0|0' && t3T.backAtFD === '3 LEGS #1 · at FanDuel · three games',
      'three-leg tickets: a card is one app throughout, and the same three at another app are a tab away (11 Nov 2026): the apps that post all three sit under the band with what the ticket pays and the chance it lands there, the app shown marked; the tab shows the ticket at that app\'s own lines and prices and leaves the other cards alone, Copy and Take act on the version shown, a ticket taken there is marked on its tab and unmarks clean; where all three are posted and one does not pass, the app is crossed and the card says which man and why', JSON.stringify({ label: t3T.tabLabel, tabs: t3T.tabs, whys: t3T.whys, atDK: t3T.atDK, tabsDK: t3T.tabsDK, second: t3T.secondStays, copied: t3T.copiedDK, taking: t3T.dkTaking, dkTabs: t3T.dkTabs, spec: t3T.dkSpec, untaken: t3T.dkUntaken, back: t3T.backAtFD }));
  chk(/^Man One/.test(t3T.legPanel) && t3T.panelAfterCopy === false && t3T.copySay === 'Copied the ticket.' && t3T.copied.length === 1
      && t3T.copied[0] === '3-leg ticket at FanDuel · pays +596 (6.96x) · all three land 20.5%, needs 14.4%\n1. Man One OVER 20.5 points -110 · last 5: 4 of 5, last 10: 7 of 10 · Hawks @ Magic\n2. Man Two OVER 7.5 rebounds -110 · last 5: 4 of 5, last 10: 7 of 10 · Bulls @ Bucks\n3. Man Three UNDER 5.5 assists -110 · last 5: 4 of 5, last 10: 7 of 10 · Heat @ Jazz'
      && t3T.taking.length === 1 && t3T.taking[0].n1 === 'TAKING · 3 LEGS · at FanDuel · three games' && /^1 marked$/i.test(t3T.takingCount) && /taking/i.test(t3T.takeBtn) && /\btaking\b/.test(t3T.bestCls) && lc(t3T.taking[0].n6) === '✓ taking copy ticket'
      && JSON.stringify(t3T.spec0) === '[{"id":"t3|2026-11-12|fanduel|1:pts|2:reb|3:ast","app":"fanduel","m":"t3","ks":["2026-11-12|1|pts","2026-11-12|2|reb","2026-11-12|3|ast"],"at":[[20.5,-110,0.6,"OVER"],[7.5,-110,0.59,"OVER"],[5.5,-110,0.58,"UNDER"]],"take":true}]',
      'three-leg tickets: a leg opens his panel, Copy puts the ticket in words for the app and opens nothing, Take marks the ticket on its first leg\'s row with the app and what each leg read there (line, price, chance, side), and the Taking strip carries it', JSON.stringify({ panel: t3T.legPanel, copied: t3T.copied, say: t3T.copySay, taking: t3T.taking, count: t3T.takingCount, btn: t3T.takeBtn, spec: t3T.spec0 }));
  chk(/0 new, 10 replaced/.test(t3T.msg2) && t3T.taking2.length === 1 && legOf(t3T.taking2[0], 0) === t3Leg(1, 'Man One', 'OVER 20.5 points', '-110', '60.0', 'ATL @ ORL', '21.7')
      && legOf(t3T.taking2[0], 1) === "2 man two over 7.5 rebounds -110 · 59.0% last 5: 4 of 5 · last 10: 7 of 10 chi @ mil · averaging 8.7 his last five · 7.5 on the ticket, the card's 8.5" && lc(t3T.taking2[0].stats) === 'all three land 20.5% needs 14.4% edge +6.2 a unit wins 5.96u'
      && t3T.live2.length === 1 && t3T.live2[0].n1 === '3 LEGS #1 · at FanDuel · three games' && t3T.live2[0].legs.map(l => l.split(' ').slice(1, 3).join(' ')).join(',') === 'Man One,Man Three,Man Eight' && lc(t3T.live2[0].stats) === 'all three land 19.5% needs 14.4% edge +5.1 a unit wins 5.96u' && lc(t3T.live2[0].n6) === 'take copy ticket'
      && t3T.board.length === 1 && t3T.board[0].n1 === 'TAKING · 3 LEGS · at FanDuel · three games' && /^TONIGHT 1 bet marked none graded yet · one unit each 0 on the card, 0 from the simulation, 0 props, 1 three-leg ticket$/.test(t3T.boardSum) && /^1 marked$/i.test(t3T.boardCount)
      && t3T.boardText.length === 1 && /\n1\. 3-LEG TICKET at FanDuel: Man One OVER 20\.5 points -110 \+ Man Two OVER 7\.5 rebounds -110 \+ Man Three UNDER 5\.5 assists -110 · pays \+596 · all three land 20\.5% needs 14\.4%$/.test(t3T.boardText[0]),
      'three-leg tickets: the props file loaded again, a pick turned to the other side at a moved line, leaves the ticket taken with its own legs, lines and sides and says where the card now differs, while the list is rebuilt from the rows as they stand; the day board\'s Taking strip carries the ticket and its text', JSON.stringify({ msg: t3T.msg2, taking: t3T.taking2, live: t3T.live2, board: t3T.board, sum: t3T.boardSum, count: t3T.boardCount, text: t3T.boardText }));
  chk(t3T.after.length === 1 && /pk t3 agrees loss/.test(t3T.after[0].cls) && t3T.after[0].n1 === '3 LEGS #1 · at FanDuel · three games LOSS' && / win · 25$/.test(legOf(t3T.after[0], 0)) && / win · 3$/.test(legOf(t3T.after[0], 1)) && / loss · 10$/.test(legOf(t3T.after[0], 2))
      && lc(t3T.after[0].stats) === 'all three land 19.5% needs 14.4% edge +5.1 result -1.00u' && lc(t3T.after[0].n6) === 'copy ticket' && t3T.afterDiv.endsWith('and the LEANs are one choice away. This list was kept before the games and is in the record.')
      && t3T.afterTaking.length === 1 && /pk t3 agrees win taking/.test(t3T.afterTaking[0].cls) && t3T.afterTaking[0].n1 === 'TAKING · 3 LEGS · at FanDuel · three games WIN' && /7\.5 on the ticket, the card's 8\.5 win · 9$/.test(legOf(t3T.afterTaking[0], 1))
      && lc(t3T.afterTaking[0].stats) === 'all three land 20.5% needs 14.4% edge +6.2 result +5.96u' && lc(t3T.afterTaking[0].n6) === 'taken copy ticket'
      && t3T.specs === 'Man One:fanduel/t3/3/take,fanduel/t3/2/listed1,fanduel/t3c/2/c1,fanduel/t3/3/listed1,fanduel/t3c/3/c1;Man Seven:fanduel/t3/2/listed2;Cold Hand:fanduel/t3c/2/c2' && JSON.stringify(t3T.twoRow) === '["UNDER",8.5,"loss",9]' && t3T.specs2 === 'Man One:5,Man Seven:1,Cold Hand:1'
      && t3T.afterTwo.length === 2 && t3T.afterTwo[0] === '2 LEGS #1 · at FanDuel · two games WIN :: Man One + Man Three :: both land 34.8% needs 27.4% edge +7.4 result +2.64u :: pk t3 agrees win'
      && t3T.afterTwo[1] === '2 LEGS #2 · at FanDuel · two games LOSS :: Man Seven + Man Eight :: both land 31.9% needs 27.4% edge +4.5 result -1.00u :: pk t3 agrees loss' && t3T.afterTwoDiv.endsWith('This list was kept before the games and is in the record.'),
      'three-leg tickets: the grade keeps the date\'s lists on the rows before the results land, the two-leg list and the three-leg one, whichever the tab showed (the lists as the rows then stood, not the ticket taken earlier), grades each ticket on its own lines and sides (the ticket taken wins on the over it was taken on, though the card\'s row had turned to the under and lost), the cards carry the results, and a second load of the grade lists nothing more', JSON.stringify({ after: t3T.after, div: t3T.afterDiv.slice(-100), taking: t3T.afterTaking, specs: t3T.specs, two: t3T.twoRow, specs2: t3T.specs2, afterTwo: t3T.afterTwo, afterTwoDiv: t3T.afterTwoDiv.slice(-70) }));
  chk(/Two-leg tickets as listed, to test 1-1 says 33\.4% · does 50\.0% \(±35\.4\) · \+1\.64u at the product of the two legs' prices; a void or pushed leg drops out Three-leg tickets as listed, to test 0-1 says 19\.5% · does 0\.0% \(±50\.0\) · -1\.00u at the product of the three legs' prices; a void or pushed leg drops out Two-leg tickets by best chance, as listed, to test 1-1 says 35\.4% · does 50\.0% \(±35\.4\) · \+1\.64u the two picks likeliest to land together, each on its own game, at the product of their prices; a void or pushed leg drops out Three-leg tickets by best chance, as listed, to test 1-0 says 20\.9% · does 100\.0% \(±50\.0\) · \+5\.96u the three picks likeliest to land together, each on its own game, at the product of their prices; a void or pushed leg drops out Three-leg tickets you took 1-0 says 20\.5% · does 100\.0% \(±50\.0\) · \+5\.96u/i.test(t3T.record)
      && /two-leg tickets as listed 1-1 \+1\.6u · three-leg tickets as listed 0-1 -1\.0u · two-leg tickets by best chance 1-1 \+1\.6u · three-leg tickets by best chance 1-0 \+6\.0u · three-leg tickets taken 1-0 \+6\.0u/.test(t3T.cardTile) && /Three-leg tickets taken 1-0 says 20\.5% · does 100\.0% \(±50\.0\) · \+5\.96u/i.test(t3T.took)
      && t3T.afterO.length === 1 && /pk t3 agrees loss/.test(t3T.afterO[0].cls) && t3T.afterO[0].legs.map(l => l.split(' ').slice(1, 3).join(' ')).join(',') === 'Man One,Man Eight,Man Nine' && t3T.afterODiv.endsWith("and the LEANs are one choice away. Rebuilt from the night's rows after the games: for study, not in the record."),
      'three-leg tickets: the record keeps the two-leg tickets as listed, the three-leg ones and the ones taken on tiles of their own, on the card\'s line and under What you took; a list asked for after the games in another mode is rebuilt for study, says so and stays out of the record', JSON.stringify({ record: t3T.record.replace(/^[\s\S]*?(Two-leg tickets as listed)/i, '$1').slice(0, 1100), tile: (t3T.cardTile.match(/two-leg tickets[^·]*·[^·]*·[^·]*·[^·]*·[^·]*/i) || [''])[0], took: t3T.took.replace(/^[\s\S]*?(Three-leg tickets taken)/i, '$1').slice(0, 110), afterO: t3T.afterO, div: t3T.afterODiv.slice(-120) }));

  // ---- 11 Nov 2026: is the page finding the best tickets? (the user: "thoroughly test multiple times to make sure the algorithm is finding the best pairs") -- a short seeded sample of the brute-force checker, tools_check_tickets.js: random nights, every valid ticket enumerated apart from the page's code, the page's ticket at each step worth exactly what the best one left is worth ----
  belowFree = true;
  await pg.evaluate(async () => { await smStore.ready; await smStore.removeItem('callsheet3.props.v1'); });
  await reloaded();
  const tkTool = require('./tools_check_tickets.js');
  const tkA = await tkTool.checkNights(pg, 14, 31, false, '2027-01-01'), tkB = await tkTool.checkNights(pg, 6, 9100, true, '2027-03-01');
  await pg.evaluate(async () => {
    await smStore.ready; const wait = () => new Promise(r => setTimeout(r, 110));
    const set = (id, v) => { const el = document.getElementById(id); if (el && el.value !== v) { el.value = v; el.dispatchEvent(new Event('change', { bubbles: true })); } };
    set('propsLegs', '2'); set('propsBelow', 'leans'); await wait();
    if (!document.getElementById('propsView').hidden) { document.getElementById('propsReset').click(); await wait(); } document.getElementById('m-nba').click(); await wait();
    await smStore.removeItem('callsheet3.props.v1');
  });
  belowFree = false;
  await reloaded();
  chk(tkA.fails.length === 0 && tkB.fails.length === 0 && tkA.nights === 14 && tkB.nights === 6 && tkA.checks === 84 && tkB.checks === 36
      && tkA.tickets[2] >= 20 && tkA.tickets[3] >= 10 && tkA.empties >= 5 && tkB.tickets[2] >= 60 && tkB.tickets[3] >= 60 && tkB.sizes.slice().sort((a, b) => b - a)[0] >= 1000,
      'the tickets are the best ones (11 Nov 2026): on fourteen ordinary random nights and six busy ones, every two-leg and three-leg ticket the page lists, either side, the overs and the unders, is a valid ticket worth exactly what the best one left is worth by brute force over every pair and three at every app, a man in one ticket, two legs never on one game, and a list ends only when nothing valid is left or at six',
      JSON.stringify({ ordinary: tkTool.report(tkA), busy: tkTool.report(tkB), fails: tkA.fails.concat(tkB.fails).slice(0, 6) }));

  // ---- 11 Nov 2026: the phone sheet through the page's own store on claude.ai (the user: "I saved the log for today for what I am betting and then took the
  //      picture with my phone and it brings up the model but nothing in it"; then: "what if I want to share the QR or have someone else see it too without
  //      changing" anything). On claude.ai the page is private and framed by the viewer: the code's link to m.html lands on the main page with a phone's empty
  //      storage. So where the viewer gives the page a store, the button saves the night's sheet there, the code carries the page's address, a phone-width or
  //      bare view opens the sheet by itself, and someone the page is shared with gets the sheet and nothing else. The viewer here is a stand-in:
  //      window.claude.use("db" | "user") over an in-memory store, every call logged, set() refusing on demand with the store's own codes ----
  const claudeMock = (o) => {
    o = o || {};
    const M = window.__mock = { docs: JSON.parse(JSON.stringify(o.docs || {})), calls: [], fail: (o.fail || []).slice(), subs: [] };
    const has = (path) => Object.prototype.hasOwnProperty.call(M.docs, path);
    const snap = (path) => ({ id: path.split('/').pop(), exists: has(path), data: () => (has(path) ? Object.freeze(JSON.parse(JSON.stringify(M.docs[path]))) : undefined), metadata: { fromCache: false, hasPendingWrites: false } });
    const put = (path, body) => { M.docs[path] = JSON.parse(JSON.stringify(body)); M.subs.filter(x => x.path === path).forEach(x => setTimeout(() => x.next(snap(path)), 0)); };
    M.put = put;
    const db = Object.freeze({
      doc(path) {
        if (path.split('/').length % 2) throw new TypeError('a document path has an even number of segments: ' + path);
        return { id: path.split('/').pop(), path,
          get() { M.calls.push('get ' + path); return Promise.resolve(snap(path)); },
          set(data) {
            M.calls.push('set ' + path);
            if (M.fail.length) { const code = M.fail.shift(); return Promise.reject({ code, message: 'stand-in ' + code }); }
            if (!data || typeof data !== 'object' || Array.isArray(data) || JSON.stringify(data) !== JSON.stringify(JSON.parse(JSON.stringify(data)))) return Promise.reject({ code: 'invalid_argument', message: 'the body is not a plain JSON object' });
            put(path, data); return Promise.resolve();
          },
          onSnapshot(next) { M.calls.push('sub ' + path); const x = { path, next }; M.subs.push(x); setTimeout(() => next(snap(path)), 0); return () => { M.subs = M.subs.filter(y => y !== x); }; } };
      },
      collection(path) { throw new Error('the page keeps one document, not a collection: ' + path); },
    });
    const user = Object.freeze({ isOwner: () => { M.calls.push('isOwner'); return Promise.resolve(!!o.owner); } });
    const downloads = Object.freeze({ save(req) { M.calls.push('save ' + req.filename); if (M.dlFail) return Promise.reject({ code: M.dlFail, message: 'stand-in ' + M.dlFail }); M.saved = { filename: req.filename, data: String(req.data) }; return Promise.resolve({ status: 'saved' }); } });
    window.claude = { use(name) { M.calls.push('use ' + name); return Promise.resolve(name === 'db' ? (o.db === false ? null : db) : name === 'user' ? (o.owner === null ? null : user) : name === 'downloads' ? downloads : null); } };
  };
  const PH_URL = 'https://claude.ai/artifact/TESTtestTEST0123456789';
  belowFree = true;
  await pg.evaluate(async () => { await smStore.ready; await smStore.removeItem('callsheet3.props.v1'); });
  await reloaded();
  const phS = await pg.evaluate(async ({ src, url }) => {
    const wait = (ms) => new Promise(r => setTimeout(r, ms || 110));
    const txt = e => (e ? e.innerText : '').replace(/\s+/g, ' ').trim();
    await smStore.ready;
    const copies = []; try { Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: t => { copies.push(String(t)); return Promise.resolve(); } } }); } catch (e) {}
    const load = async (doc, name) => { const dt = new DataTransfer(); dt.items.add(new File([JSON.stringify(doc)], name, { type: 'application/json' })); const inp = document.getElementById('slateFile'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true })); await wait(); await wait(); };
    const G = [['Hawks', 'Magic', 'ATL', 'ORL', -2.5], ['Bulls', 'Bucks', 'CHI', 'MIL', -2.5], ['Heat', 'Jazz', 'MIA', 'UTA', -2.5]];
    const ov = L => [L + 2, L - 2, L + 3, L - 1, L + 1, L + 2, L + 4, L - 3, L + 1, L + 2], un = L => [L - 2, L + 2, L - 3, L + 1, L - 1, L - 2, L - 4, L + 3, L - 1, L - 2];
    const up = [{ k: 'pace', t: 'Pace', eff: 0.4, i: 0 }, { k: 'dvp', t: 'Defence v position', eff: 0.6, i: 0 }], dn = [{ k: 'pace', t: 'Pace', eff: -0.4, i: 0 }, { k: 'dvp', t: 'Defence v position', eff: -0.6, i: 0 }];
    const man = (pid, name, team, gi, mk, side, line, chance, vals, parts) => ({ gi, pid: String(pid), name, team, opp: team === G[gi][2] ? G[gi][3] : G[gi][2], home: team === G[gi][3], pos: 'G', mk, line, op: -110, up: -110, book: 'fanduel',
      books: { fanduel: [line, -110, -110], draftkings: [line, -115, -115] }, proj: line + (side === 'OVER' ? 2 : -2), sd: 6, pm: side === 'OVER' ? 0.7 : 0.3, pb: 0.5, p: side === 'OVER' ? chance : Math.round((1 - chance) * 10000) / 10000, push: 0, side, chance, price: -110, need: 0.5238,
      edge: Math.round((chance - 0.5238) * 10000) / 10000, band: 'LEAN', mins: 32, rate36: 20, base: 18, med: line + (side === 'OVER' ? 1.5 : -1.5), usg: 22, sdf: 1, starter: true, start_src: "RotoWire's expected five", why: ['x'],
      log: vals.map((v, i) => ['2026-10-' + String(20 + i), 'OPP', i % 2, 32, v, ['won by 3']]), parts });
    const men = [man(1, 'Man One', 'ATL', 0, 'pts', 'OVER', 20.5, 0.60, ov(20.5), up), man(2, 'Man Two', 'CHI', 1, 'reb', 'OVER', 7.5, 0.59, ov(7.5), up), man(3, 'Man Three', 'MIA', 2, 'ast', 'UNDER', 5.5, 0.58, un(5.5), dn), man(8, 'Man Eight', 'MIL', 1, 'pts', 'OVER', 12.5, 0.56, ov(12.5), up)];
    await load({ format: 'callsheet3.props', version: 1, date: '2026-11-12', games: G.map((g, gi) => ({ gid: 'ph' + gi, away: g[0], home: g[1], aab: g[2], hab: g[3], spread: g[4], total: 225.5, props: men.filter(m => m.gi === gi) })) }, 'nba-props-2026-11-12.json');
    if (document.getElementById('propsView').hidden) { document.getElementById('m-props').click(); await wait(); }
    document.getElementById('propsReset').click(); await wait();
    const pick = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('change', { bubbles: true })); };
    pick('propsLegs', '2'); pick('propsBelow', 't3'); await wait();
    const best = document.getElementById('propsBest'), listed = best.querySelectorAll('.pk.t3').length;
    best.querySelector('.pk.t3 [data-t3take]').click(); await wait();
    document.getElementById('m-nba').click(); await wait();
    const bd = document.getElementById('boardDate'), day = (v) => { bd.value = v; bd.dispatchEvent(new Event('change')); };
    day('2026-11-12'); await wait();
    const body = document.getElementById('phoneBody'), dlg = document.getElementById('phoneDlg'), esc = async () => { document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })); await wait(); };
    const notes = () => [...body.querySelectorAll('.note')].map(txt), press = async (ms) => { document.getElementById('phone').click(); await wait(ms || 500); };
    const mods = (cell, margin) => {
      const d = (body.querySelector('svg path') || { getAttribute: () => '' }).getAttribute('d') || '';
      const pts = [...d.matchAll(/M(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)[hl]/g)].map(m => [Math.round(((+m[1]) - margin) / cell), Math.round(((+m[2]) - margin) / cell)]);
      const n = pts.length ? Math.max(...pts.map(q => q[0])) + 1 : 0, out = [];
      for (let r = 0; r < n; r++) { const row = []; for (let c = 0; c < n; c++) row.push(0); out.push(row); }
      pts.forEach(q => { out[q[1]][q[0]] = 1; });
      return { n, mods: out };
    };
    // a) no viewer: the code carries the picks to m.html, the ticket taken and the night's tickets with them
    await press(700);
    const code = { link: (body.querySelector('a') || {}).href || '', note: notes()[0] || '' };
    await esc();
    // b) the viewer, its store unavailable once: one more try, and the sheet is saved whole
    const mock = (0, eval)('(' + src + ')');
    mock({ docs: { 'phone/config': { url } }, owner: true, fail: ['unavailable'] });
    await press(1800);
    const saved = { notes: notes(), calls: window.__mock.calls.slice(), doc: JSON.parse(JSON.stringify(window.__mock.docs['phone/latest'] || null)), qr: mods(6, 4), links: [...body.querySelectorAll('a')].map(a => a.id + '|' + a.getAttribute('href')), tag: txt(body.querySelector('h3')) };
    document.getElementById('phonePreview').click(); await wait();
    const sh = document.getElementById('phoneSheet');
    const preview = { open: !!(sh && !sh.hidden), how: sh.dataset.how, btn: txt(sh.querySelector('[data-pshclose]')), text: txt(sh), heads: [...sh.querySelectorAll('h2')].map(txt), takes: sh.querySelectorAll('.pshk.take').length, cards: sh.querySelectorAll('.pshk').length };
    // (11 Nov 2026) a card with detail opens it over the sheet: the ticket's two legs, each the prop's own panel as the computer draws it
    const tapCards = [...sh.querySelectorAll('.pshk.tap')], ticketCard = tapCards.find(c => /2-LEG TICKET/i.test(c.innerText));
    ticketCard.click(); await wait(350);
    const pp = document.getElementById('phonePanel'), ppb = document.getElementById('phonePanelBody');
    const panel = { open: !!(pp && !pp.hidden), legs: ppb.querySelectorAll('.pp-leg').length, heads: [...ppb.querySelectorAll('.pp-legn')].map(txt), names: [...ppb.querySelectorAll('h3')].map(txt), picks: [...ppb.querySelectorAll('.pd-pick')].map(txt),
      tiles: ppb.querySelectorAll('.pd-tile').length, logs: ppb.querySelectorAll('.pd-log tbody tr').length, books: ppb.querySelectorAll('.pd-books tbody tr').length, levers: ppb.querySelectorAll('.pd-levers .lever').length,
      controls: ppb.querySelectorAll('button, a, input, select, textarea').length, data: (ppb.innerHTML.match(/\sdata-[a-z-]+=/g) || []).length, taps: tapCards.length, plain: sh.querySelectorAll('.pshk:not(.tap)').length, tip: txt(sh.querySelector('.psh-tip')) };
    const single = tapCards.find(c => /#1 · NBA PROP/i.test(c.innerText)); single.click(); await wait(350);
    panel.single = { legs: ppb.querySelectorAll('.pp-leg').length, heads: ppb.querySelectorAll('.pp-legn').length, name: txt(ppb.querySelector('h3')) };
    await esc();
    const afterEsc0 = { panel: pp.hidden, sheet: sh.hidden };
    await esc();
    const afterEsc = { sheet: sh.hidden, dlg: !dlg.hidden, noscroll: document.body.classList.contains('noscroll') };
    document.getElementById('phoneCopy').click(); await wait();
    const copied = { text: copies[copies.length - 1] || '', said: txt(document.getElementById('phoneSaid')) };
    // the sheet as a file to send: saved through the viewer's own save, a still copy with the detail folded under each pick
    document.getElementById('phoneFile').click(); await wait(400);
    const filed = { name: (window.__mock.saved || {}).filename || '', data: (window.__mock.saved || {}).data || '', said: txt(document.getElementById('phoneSaid')), calls: window.__mock.calls.filter(c => /^(use downloads|save )/.test(c)) };
    window.__mock.dlFail = 'declined'; document.getElementById('phoneFile').click(); await wait(300);
    const declined = txt(document.getElementById('phoneSaid')); window.__mock.dlFail = null;
    await esc();
    const closed = dlg.hidden && !document.body.classList.contains('noscroll');
    // c) the store refuses the write: said in the dialog, no code drawn, the last sheet left as it was
    window.__mock.fail = ['invalid_argument']; window.__mock.calls.length = 0;
    await press(500);
    const refused = { notes: notes(), qr: !!body.querySelector('svg'), calls: window.__mock.calls.slice(), same: JSON.stringify(window.__mock.docs['phone/latest']) === JSON.stringify(saved.doc) };
    await esc();
    // d) the viewer gives the page no store: said, and no code that would land on an empty page
    mock({ docs: {}, owner: true, db: false });
    await press(400);
    const nostore = { notes: notes(), qr: !!body.querySelector('svg'), link: !!body.querySelector('a'), calls: window.__mock.calls.slice() };
    await esc();
    // e) a date with nothing on the board: nothing is written
    mock({ docs: {}, owner: true });
    day('2027-01-01'); await wait();
    await press(400);
    const empty = { notes: notes(), wrote: Object.keys(window.__mock.docs), calls: window.__mock.calls.slice() };
    await esc();
    // f) the store with no address beside the sheet: saved all the same, and the words stand in for the code
    day('2026-11-12'); await wait();
    await press(500);
    const noUrl = { notes: notes(), qr: !!body.querySelector('svg'), wrote: Object.keys(window.__mock.docs) };
    await esc();
    delete window.claude; delete window.__mock;
    day(''); pick('propsBelow', 'leans'); await wait();
    return { listed, code, saved, preview, panel, afterEsc0, afterEsc, copied, filed, declined, closed, refused, nostore, empty, noUrl };
  }, { src: claudeMock.toString(), url: PH_URL });
  const phQr = qrRead(phS.saved.qr.n, phS.saved.qr.mods);
  // the views that open the page with the sheet in the store: the owner's phone, a guest's, a guest at a desk, and the two with nothing to show
  const phView = async (opts, vp, steps) => {
    const c = await pg.context().browser().newContext({ viewport: vp }), p = await c.newPage(), e2 = [];
    p.on('pageerror', e => e2.push(e.message));
    await p.addInitScript(claudeMock, opts);
    if (opts.later) await p.addInitScript((d) => { window.__later = d; }, opts.later);
    await p.goto('file://' + path.join(__dirname, 'web/callsheet3.html'));
    await p.waitForFunction(() => window.smStore && window.smStore.ready, null, { timeout: 60000 }); await p.waitForTimeout(700);
    if (steps === 'card') {   // a view with a card of its own: add the example, load again, and see what it asked of the viewer
      await p.evaluate(async () => { const wait = () => new Promise(r => setTimeout(r, 110)); document.getElementById('m-nba').click(); await wait(); document.getElementById('example').click(); await wait(); document.getElementById('add').click(); await wait(); await wait(); });
      await p.reload(); await p.waitForFunction(() => window.smStore && window.smStore.ready, null, { timeout: 60000 }); await p.waitForTimeout(700);
    }
    const r = await p.evaluate(async (steps) => {
      const wait = (ms) => new Promise(r => setTimeout(r, ms || 140)), txt = e => (e ? e.innerText : '').replace(/\s+/g, ' ').trim();
      const s = document.getElementById('phoneSheet'), o = { open: !!(s && !s.hidden), how: s ? s.dataset.how : '', btn: s ? txt(s.querySelector('[data-pshclose]')) : '', text: txt(s), heads: s ? [...s.querySelectorAll('h2')].map(txt) : [],
        takes: s ? s.querySelectorAll('.pshk.take').length : 0, cards: s ? s.querySelectorAll('.pshk').length : 0, controls: s ? s.querySelectorAll('input, button, select, textarea, a').length : 0,
        fits: document.documentElement.scrollWidth <= window.innerWidth && (!s || s.scrollWidth <= s.clientWidth), calls: window.__mock.calls.slice(),
        hint: (h => (h && !h.hidden ? txt(h.querySelector('span')) : ''))(document.getElementById('phoneHint')) };
      if (steps === 'arrives') {   // nothing saved when the phone opened the page; then the computer saves one
        window.__mock.put('phone/latest', steps && window.__later); await wait(300);
        const s2 = document.getElementById('phoneSheet'), h2 = document.getElementById('phoneHint');
        o.arrived = !!(s2 && !s2.hidden); o.arrivedTakes = s2 ? s2.querySelectorAll('.pshk.take').length : 0; o.hintAfter = !!(h2 && !h2.hidden);
        return o;
      }
      if (!s) return o;
      const tap = [...s.querySelectorAll('.pshk.tap')], tk = tap.find(c => /2-LEG TICKET/i.test(c.innerText));
      o.taps = tap.length; o.tip = txt(s.querySelector('.psh-tip'));
      if (tk) {
        tk.click(); await wait(450);
        const pp = document.getElementById('phonePanel'), ppb = document.getElementById('phonePanelBody');
        o.panel = { open: !!(pp && !pp.hidden), legs: ppb.querySelectorAll('.pp-leg').length, names: [...ppb.querySelectorAll('h3')].map(txt), tiles: ppb.querySelectorAll('.pd-tile').length, logs: ppb.querySelectorAll('.pd-log tbody tr').length,
          controls: ppb.querySelectorAll('button, a, input, select, textarea').length, shut: pp.querySelectorAll('[data-ppclose]').length, fits: pp.scrollWidth <= pp.clientWidth + 1 };
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })); await wait();
        o.panelShut = pp.hidden; o.sheetStays = !s.hidden;
      }
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })); await wait();
      o.escShut = s.hidden;
      if (steps === 'newer') {   // shut by hand, the same sheet again stays shut, a newer one opens
        const d = JSON.parse(JSON.stringify(window.__mock.docs['phone/latest']));
        window.__mock.put('phone/latest', d); await wait(); o.sameStaysShut = s.hidden && !document.body.classList.contains('noscroll');
        d.at = '2026-11-12T23:59:00.000Z'; d.sheet.at = d.at; d.sheet.take = []; window.__mock.put('phone/latest', d); await wait();
        o.newerOpens = !s.hidden; o.newerTakes = s.querySelectorAll('.pshk.take').length; o.subs = window.__mock.calls.filter(x => /^sub /.test(x)).length;
      }
      return o;
    }, steps);
    await c.close(); r.errs = e2; return r;
  };
  const phDocs = { 'phone/latest': phS.saved.doc, 'phone/config': { url: PH_URL } };
  const phOwner = await phView({ docs: phDocs, owner: true }, { width: 390, height: 844 }, 'newer');
  const phGuest = await phView({ docs: phDocs, owner: false }, { width: 390, height: 844 });
  const phGuestDesk = await phView({ docs: phDocs, owner: false }, { width: 1280, height: 900 });
  const phOwnDesk = await phView({ docs: phDocs, owner: true }, { width: 1280, height: 900 }, 'card');
  const phNone = await phView({ docs: {}, owner: true, later: phS.saved.doc }, { width: 390, height: 844 }, 'arrives');
  const phGuestNone = await phView({ docs: {}, owner: false }, { width: 390, height: 844 });
  const phNoStore = await phView({ docs: phDocs, owner: true, db: false }, { width: 390, height: 844 });
  // m.html with the code's link: the same night as the store's sheet, line for line
  const mCtx = await pg.context().browser().newContext({ viewport: { width: 390, height: 844 } }), mPage = await mCtx.newPage(), mErrs = [];
  mPage.on('pageerror', e => mErrs.push(e.message));
  await mPage.goto(phS.code.link); await mPage.waitForTimeout(600);
  const mText = await mPage.evaluate(() => document.body.innerText.replace(/\s+/g, ' ').trim());
  await mCtx.close();
  const phFilePath = path.join(require('os').tmpdir(), 'cs3-harness-' + process.pid + '-sheet.html');
  fs.writeFileSync(phFilePath, phS.filed.data || '<!doctype html><title>nothing saved</title>');
  const fCtx = await pg.context().browser().newContext({ viewport: { width: 390, height: 844 }, javaScriptEnabled: false }), fPage = await fCtx.newPage(), fReqs = [];
  fPage.on('request', q => { if (!/^(file|data):/.test(q.url())) fReqs.push(q.url()); });
  await fPage.goto('file://' + phFilePath); await fPage.waitForTimeout(400);
  const fFolds = await fPage.locator('details.pfd').count(), fOpen0 = await fPage.locator('details.pfd[open]').count();
  if (fFolds) { await fPage.locator('details.pfd > summary').first().click(); await fPage.waitForTimeout(200); }
  const fOpen1 = await fPage.locator('details.pfd[open]').count();
  const fText = (await fPage.locator('body').innerText()).replace(/\s+/g, ' ').trim();
  const fBox = fOpen1 ? await fPage.locator('details.pfd[open] .pdlg-box').first().boundingBox() : null;
  const fPanel = { tiles: await fPage.locator('details.pfd[open] .pd-tile').count(), legs: await fPage.locator('details.pfd[open] .pp-leg').count(), wide: await fPage.evaluate(() => document.documentElement.scrollWidth) };
  await fCtx.close(); try { fs.unlinkSync(phFilePath); } catch (e) {}
  await pg.evaluate(async () => { await smStore.ready; await smStore.removeItem('callsheet3.props.v1'); });
  belowFree = false;
  await reloaded();
  const phLines = (t) => { const a = t.search(/TAKING TONIGHT/i), b = t.search(/View only:/i); return a >= 0 && b > a ? t.slice(a, b).trim().toLowerCase() : ''; };
  const phSheet = (phS.saved.doc || {}).sheet || {}, phTake = (phSheet.take || [])[0] || {};
  chk(phS.listed === 2 && /\/m\.html#z[A-Za-z0-9_-]+$/.test(phS.code.link) && /the best props, the night's tickets and the simulation's calls, view only\./.test(phS.code.note) && /nothing is uploaded/.test(phS.code.note)
      && mErrs.length === 0 && /TAKING TONIGHT 1 TAKING · NBA · 2-LEG TICKET Man One OVER 20\.5 Points \+ Man Two OVER 7\.5 Rebounds 3[0-9]\.\d% · \+26\d needs 27\.\d% Hawks @ Magic · Bulls @ Bucks · at FanDuel/i.test(mText)
      && /TWO-LEG TICKETS, TO TEST 2 TICKET #1 Man One OVER 20\.5 Points \+ Man Two OVER 7\.5 Rebounds/i.test(mText),
      'phone, off claude.ai: with no viewer the button draws the code as before, its link carrying the night to m.html, and the night now includes the ticket marked Taking (two legs at FanDuel, the games, the chance both land and the parlay price) and the night\'s two tickets under the best props',
      JSON.stringify({ listed: phS.listed, link: phS.code.link.slice(0, 80), note: phS.code.note.slice(0, 260), m: mText.slice(0, 420), errs: mErrs }));
  chk(JSON.stringify(phS.saved.calls) === JSON.stringify(['use db', 'set phone/latest', 'set phone/latest', 'get phone/config'])
      && phS.saved.doc && phS.saved.doc.v === 4 && phS.saved.doc.d === '2026-11-12' && phS.saved.doc.at === phSheet.at && Object.keys(phS.saved.doc).join() === 'v,d,at,sheet,panels,games' && phS.saved.doc.games === 0 && !Object.keys(phSheet).some(k => Array.isArray(phSheet[k]) && phSheet[k].some(x => x.gid !== undefined)) && /^z[A-Za-z0-9_-]{400,}$/.test(phS.saved.doc.panels)
      && phTake.ids.length === 2 && phSheet.props.every(x => x.ids && x.ids.length === 1) && phSheet.t3.every(x => x.ids.length === 2) && JSON.stringify(phS.saved.doc).length < 200000
      && phSheet.take.length === 1 && phTake.k === 'ticket' && phTake.n === 2 && phTake.p === 'Man One OVER 20.5 points + Man Two OVER 7.5 rebounds' && phTake.m === 'at FanDuel' && phTake.g === 'Hawks @ Magic · Bulls @ Bucks' && phTake.pr >= 260 && phTake.pr <= 269 && phTake.c > 30 && phTake.c < 40
      && phSheet.t3.length === 2 && phSheet.t3[0].n === 2 && phSheet.props.length === 4 && !('cut' in phSheet)
      && /^Saved for your phone at \d{1,2}:\d\d [AP]M: \d+ lines, the bets and tickets you are taking first, then the parlay four, the best straight bets, the likeliest sides, the best props, the night's tickets and the simulation's calls\. Tap a prop, a ticket or a pair on the phone and its detail opens as it reads here: 4 props\.$/.test(phS.saved.notes[0])
      && /^Point your phone's camera at the code, or open The Super Model in the Claude app on your phone\. Tonight's sheet opens by itself, view only\./.test(phS.saved.notes[1])
      && phQr === PH_URL && phS.saved.qr.n >= 25 && !phS.saved.links.some(l => /m\.html/.test(l)) && phS.saved.links.join() === 'phoneFile|#,phoneCopy|#,phonePreview|#',
      'phone, on claude.ai: where the viewer gives the page its store, the button saves the night\'s sheet there whole (one document, the ticket you are taking in it, nothing trimmed), tries once more when the store is unavailable, says it is saved and how many lines, and the code it draws is the page\'s own address from the store, read back off the drawn modules by an independent decoder, with no link to m.html',
      JSON.stringify({ calls: phS.saved.calls, keys: phS.saved.doc && Object.keys(phS.saved.doc), take: phTake, t3: (phSheet.t3 || []).length, props: (phSheet.props || []).length, notes: phS.saved.notes.map(n => n.slice(0, 150)), qr: phQr, n: phS.saved.qr.n, links: phS.saved.links }));
  chk(/^For someone else to see it: share this page with them from the Share menu on claude\.ai \(Viewer is enough\)\. Signed in to Claude, they scan the same code and get tonight's sheet with the detail behind each pick, the games' cards with it, and nothing else, view only: only you can save over it, and your card never leaves this browser\. For someone with no Claude account, save the sheet as a file to send \(the detail is folded under each pick, and it opens on any phone\), or copy it as text\./.test(phS.saved.notes[2])
      && /readable by you and by anyone you share the page with, and each save replaces the last\./.test(phS.saved.notes[3])
      && phS.preview.open && phS.preview.how === 'preview' && phS.preview.btn === 'Close' && phS.preview.takes === 1 && phS.preview.cards === 8
      && phS.preview.heads.join('|').toLowerCase() === 'taking tonight 1|best props 4|two-leg tickets, to test 2|same-game pairs 1'
      && phS.afterEsc.sheet && phS.afterEsc.dlg && phS.afterEsc.noscroll && phS.closed
      && /^The Super Model · Thu, Nov 12 · view only\n\nTAKING TONIGHT\n1\. Man One OVER 20\.5 points \+ Man Two OVER 7\.5 rebounds · 3\d\.\d% · \+26\d needs 27\.\d% · Hawks @ Magic · Bulls @ Bucks · at FanDuel\n\nBEST PROPS\n#1 Man One OVER 20\.5 points \[LEAN\]/.test(phS.copied.text)
      && /\n\nTWO-LEG TICKETS, TO TEST\n#1 /.test(phS.copied.text) && /\n\nSAME-GAME PAIRS\n#1 /.test(phS.copied.text) && phS.copied.said === 'Copied the sheet as text.',
      'phone, sharing: the dialog says how someone else sees the sheet (share the page from the Share menu, Viewer is enough; they get the sheet and nothing else, and only the owner saves over it) and who can read the store; the sheet opens as the phone shows it over the dialog and Escape shuts it first, the dialog after; and the sheet copies as plain text for someone with no account',
      JSON.stringify({ notes: phS.saved.notes.slice(2).map(n => n.slice(0, 200)), preview: { open: phS.preview.open, how: phS.preview.how, btn: phS.preview.btn, heads: phS.preview.heads, takes: phS.preview.takes, cards: phS.preview.cards }, afterEsc: phS.afterEsc, closed: phS.closed, copied: phS.copied.text.slice(0, 330), said: phS.copied.said }));
  chk(phS.panel.open && phS.panel.taps === 8 && phS.panel.plain === 0 && phS.panel.tip === 'Tap a prop, a ticket or a pair for its detail.'
      && phS.panel.legs === 2 && phS.panel.heads.join('|').toLowerCase() === 'leg 1 of 2|leg 2 of 2' && /^Man One/.test(phS.panel.names[0]) && /^Man Two/.test(phS.panel.names[1])
      && /^OVER 20\.5 points/i.test(phS.panel.picks[0]) && /^OVER 7\.5 rebounds/i.test(phS.panel.picks[1]) && phS.panel.tiles >= 12 && phS.panel.logs === 20 && phS.panel.books === 4 && phS.panel.levers >= 4
      && phS.panel.controls === 0 && phS.panel.data === 0 && phS.panel.single.legs === 1 && phS.panel.single.heads === 0 && /^Man One/.test(phS.panel.single.name)
      && phS.afterEsc0.panel && !phS.afterEsc0.sheet,
      'phone, the detail behind a pick (11 Nov 2026, the user: "see the prop cards when I select it so I can see the graphs and info too"): every card that stands on a prop carries a mark and opens the prop\'s own panel as the computer draws it, over the sheet (the tiles, the levers, his last games, every book); a ticket opens its two legs one under the other, a single prop one panel with no leg heading; the buttons and every attribute that would act are out of the markup; and Escape shuts the detail and leaves the sheet',
      JSON.stringify({ open: phS.panel.open, taps: phS.panel.taps, plain: phS.panel.plain, tip: phS.panel.tip, legs: phS.panel.legs, heads: phS.panel.heads, names: phS.panel.names, picks: phS.panel.picks, tiles: phS.panel.tiles, logs: phS.panel.logs, books: phS.panel.books, levers: phS.panel.levers, controls: phS.panel.controls, data: phS.panel.data, single: phS.panel.single, afterEsc0: phS.afterEsc0 }));
  const fd = phS.filed.data || '';
  chk(phS.filed.name === 'super-model-2026-11-12.html' && JSON.stringify(phS.filed.calls) === JSON.stringify(['use downloads', 'save super-model-2026-11-12.html'])
      && /^Saved super-model-2026-11-12\.html\. Send it as it is: it opens on any phone, view only, with the detail under each pick\.$/.test(phS.filed.said) && phS.declined === 'Not saved.'
      && /^<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport"/.test(fd) && !/<script|<button|<a\b|<input|<select|<textarea|<iframe|<img|\son[a-z]+\s*=|\sdata-[a-z-]+=|https?:\/\//i.test(fd)
      && fFolds === 8 && fOpen0 === 0 && fOpen1 === 1 && fReqs.length === 0 && fPanel.legs === 2 && fPanel.tiles >= 12 && fPanel.wide <= 390 && fBox && fBox.x >= 0 && fBox.x + fBox.width <= 391
      && /^The Super Model Thu, Nov 12 · made \d{1,2}:\d\d [AP]M · view only a copy Tap a prop, a ticket or a pair for its detail\. TAKING TONIGHT 1 TAKING · NBA · 2-LEG TICKET Man One OVER 20\.5 points \+ Man Two OVER 7\.5 rebounds/i.test(fText)
      && /Leg 1 of 2 .*Man One .*Leg 2 of 2 .*Man Two /i.test(fText) && /View only: a copy of the sheet as it stood on [^.]*\. Nothing in this file changes anything\./.test(fText),
      'phone, the sheet as a file to send (the user: "share my picks for the day with someone, and have them see the details behind the pick without them changing" anything "but able to see from their phone"): the dialog saves the sheet through the viewer\'s own save as one .html file, a still copy with the detail folded under each pick; it holds no script, button, link, field, handler or outside address, opens with scripts off and nothing fetched on a phone-width screen with no sideways scroll, and a tap opens a pick\'s detail; a save the viewer declines is said and nothing more',
      JSON.stringify({ name: phS.filed.name, calls: phS.filed.calls, said: phS.filed.said, declined: phS.declined, bytes: fd.length, head: fd.slice(0, 90), folds: fFolds, open0: fOpen0, open1: fOpen1, reqs: fReqs.slice(0, 3), panel: fPanel, box: fBox && [Math.round(fBox.x), Math.round(fBox.x + fBox.width)], text: fText.slice(0, 260) }));
  chk(/^The sheet could not be saved for the phone: the store refused it: only the page's owner saves the sheet\. Press the button again in a moment\./.test(phS.refused.notes[0] || '') && !phS.refused.qr && phS.refused.same && JSON.stringify(phS.refused.calls) === JSON.stringify(['use db', 'set phone/latest'])
      && /^The sheet could not be saved for the phone: this view was not given the page's store on claude\.ai\./.test(phS.nostore.notes[0] || '') && !phS.nostore.qr && !phS.nostore.link && JSON.stringify(phS.nostore.calls) === JSON.stringify(['use db'])
      && /^Nothing on the board for .*2027.* yet|^Nothing on the board for /.test(phS.empty.notes[0] || '') && phS.empty.wrote.length === 0 && JSON.stringify(phS.empty.calls) === JSON.stringify(['use db'])
      && /^Saved for your phone/.test(phS.noUrl.notes[0] || '') && !phS.noUrl.qr && /^Open The Super Model in the Claude app on your phone, or in its browser signed in to claude\.ai\./.test(phS.noUrl.notes[1] || '') && phS.noUrl.wrote.join() === 'phone/latest',
      'phone, when it cannot: a write the store refuses is said in the dialog with no code drawn and the last sheet left as it was; a viewer that gives the page no store is said too, with no code that would land on an empty page; a date with nothing on the board writes nothing; and a store with no address beside the sheet still saves it and says where to open it in words',
      JSON.stringify({ refused: phS.refused, nostore: phS.nostore, empty: phS.empty, noUrl: { notes: phS.noUrl.notes.map(n => n.slice(0, 120)), qr: phS.noUrl.qr, wrote: phS.noUrl.wrote } }));
  chk(phOwner.errs.length === 0 && phOwner.open && phOwner.how === 'auto' && phOwner.btn === 'Open the full model' && phOwner.takes === 1 && phOwner.cards === 8 && phOwner.fits
      && phOwner.taps === 8 && phOwner.panel && phOwner.panel.open && phOwner.panel.legs === 2 && /^Man One/.test(phOwner.panel.names[0]) && phOwner.panel.tiles >= 12 && phOwner.panel.logs === 20 && phOwner.panel.controls === 0 && phOwner.panel.shut === 1 && phOwner.panel.fits && phOwner.panelShut && phOwner.sheetStays
      && /^The Super Model Thu, Nov 12 · made \d{1,2}:\d\d [AP]M · view only Open the full model Tap a prop, a ticket or a pair for its detail\. (This sheet is for Thu, Nov 12\. Press Phone QR on the day board of the computer for tonight's\. )?TAKING TONIGHT 1 TAKING · NBA · 2-LEG TICKET Man One OVER 20\.5 Points \+ Man Two OVER 7\.5 Rebounds/i.test(phOwner.text)
      && JSON.stringify(phOwner.calls) === JSON.stringify(['use db', 'use user', 'isOwner', 'sub phone/latest']) && phOwner.escShut && phOwner.sameStaysShut && phOwner.newerOpens && phOwner.newerTakes === 0 && phOwner.subs === 1
      && phLines(phOwner.text) === phLines(mText) && phLines(mText).length > 300,
      'phone, the owner\'s: a view the width of a phone with nothing of its own asks the store once and opens the night\'s sheet over the page by itself, the ticket you are taking first, line for line what m.html draws from the code, with no sideways scroll and no script error; a tap on the ticket unpacks the detail the store holds and opens its two legs over the sheet, inside the screen\'s width, and Escape shuts the detail and leaves the sheet; a button opens the model behind it, a sheet shut by hand stays shut, and a newer one saved from the computer opens on the one subscription',
      JSON.stringify({ errs: phOwner.errs, open: phOwner.open, how: phOwner.how, btn: phOwner.btn, takes: phOwner.takes, cards: phOwner.cards, fits: phOwner.fits, taps: phOwner.taps, panel: phOwner.panel, panelShut: phOwner.panelShut, sheetStays: phOwner.sheetStays, text: phOwner.text.slice(0, 300), calls: phOwner.calls, escShut: phOwner.escShut, same: phOwner.sameStaysShut, newer: phOwner.newerOpens, newerTakes: phOwner.newerTakes, subs: phOwner.subs, lines: phLines(phOwner.text) === phLines(mText), len: phLines(mText).length }));
  chk(phGuest.errs.length === 0 && phGuest.open && phGuest.how === 'guest' && phGuest.btn === '' && phGuest.controls === 0 && phGuest.escShut === false && phGuest.takes === 1 && phGuest.fits && /view only SHARED WITH YOU/i.test(phGuest.text)
      && /View only: this is the owner's sheet for the night, and it follows when they save a new one\./.test(phGuest.text) && phLines(phGuest.text) === phLines(phOwner.text)
      && phGuestDesk.errs.length === 0 && phGuestDesk.open && phGuestDesk.how === 'guest' && phGuestDesk.controls === 0 && phGuestDesk.escShut === false
      && phGuest.taps === 8 && phGuest.panel && phGuest.panel.open && phGuest.panel.legs === 2 && phGuest.panel.tiles >= 12 && phGuest.panel.controls === 0 && phGuest.panel.fits && phGuest.panelShut && phGuest.sheetStays
      && phGuestDesk.panel && phGuestDesk.panel.open && phGuestDesk.panel.controls === 0,
      'phone, someone the page is shared with: they get the same sheet, marked shared with you, with no button, field or link in it and no way past it (Escape leaves it up), on a phone and at a desk alike; a pick opens the detail behind it for them as it does for the owner, with nothing in the detail to press but Close; the store\'s rule, read by all the page is shared with and written by its owner alone, is declared at the publish',
      JSON.stringify({ phone: { errs: phGuest.errs, open: phGuest.open, how: phGuest.how, btn: phGuest.btn, controls: phGuest.controls, esc: phGuest.escShut, taps: phGuest.taps, panel: phGuest.panel, panelShut: phGuest.panelShut, sheetStays: phGuest.sheetStays, text: phGuest.text.slice(0, 160) }, desk: { open: phGuestDesk.open, how: phGuestDesk.how, controls: phGuestDesk.controls, esc: phGuestDesk.escShut, panel: phGuestDesk.panel } }));
  chk(phOwnDesk.errs.length === 0 && !phOwnDesk.open && phOwnDesk.calls.length === 0
      && phOwnDesk.hint === '' && phOwner.hint === '' && phGuest.hint === ''
      && phNone.errs.length === 0 && !phNone.open && JSON.stringify(phNone.calls) === JSON.stringify(['use db', 'use user', 'isOwner', 'sub phone/latest'])
      && phNone.hint === 'No sheet saved for the phone yet. On the computer, press Phone QR on the day board and it opens here by itself.' && phNone.arrived && phNone.arrivedTakes === 1 && !phNone.hintAfter
      && phGuestNone.errs.length === 0 && !phGuestNone.open && phGuestNone.hint === 'The owner has not saved a sheet yet. It opens here by itself when they do.'
      && phNoStore.errs.length === 0 && !phNoStore.open && JSON.stringify(phNoStore.calls) === JSON.stringify(['use db'])
      && phNoStore.hint === "Tonight's sheet is kept in this page's store on claude.ai, and this view was not given it. Open the page in your phone's browser signed in to claude.ai, and allow it if a box asks.",
      'phone, when there is nothing to open: a view with a card of its own asks the viewer nothing at load, so the computer sees no prompt it did not ask for; a phone with no sheet in the store says so across the top and what to press, and the sheet opens there by itself when the computer saves one; a guest is told the owner has not saved one; and a phone whose view gives the page no store is told to open it in the browser signed in, with no script error anywhere',
      JSON.stringify({ desk: { open: phOwnDesk.open, calls: phOwnDesk.calls, errs: phOwnDesk.errs, hint: phOwnDesk.hint }, none: { open: phNone.open, calls: phNone.calls, hint: phNone.hint, arrived: phNone.arrived, takes: phNone.arrivedTakes, hintAfter: phNone.hintAfter }, guestNone: { open: phGuestNone.open, hint: phGuestNone.hint }, nostore: { open: phNoStore.open, calls: phNoStore.calls, hint: phNoStore.hint } }));

  // ---- 11 Nov 2026: a game line opens its game's card on the phone (the user: "can you have it so the game lines open as well like the props? I really like this
  //      to view on the go or show someone on the fly"). At the save each game on the sheet is put in the form, drawn by the page's own render and read off, and
  //      the form is put back as it stood; the cards ride in a document of their own beside the sheet, phone/games, written first and stamped with the sheet's time.
  //      Every line of a game opens the same card under the line that was pressed: a bet you are taking, a parlay leg, a likeliest side, a simulation call ----
  const phGKeep = await pg.evaluate(async () => { await smStore.ready; const k = {}; for (const x of ['callsheet3.card.v1', 'callsheet3.props.v1', 'callsheet3.draft.v1']) k[x] = await smStore.getItem(x); await smStore.removeItem('callsheet3.card.v1'); await smStore.removeItem('callsheet3.props.v1'); return k; });
  await reloaded();
  const phG = await pg.evaluate(async ({ src, url }) => {
    const wait = (ms) => new Promise(r => setTimeout(r, ms || 110)), txt = e => (e ? e.innerText : '').replace(/\s+/g, ' ').trim();
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    await smStore.ready;
    document.getElementById('clear').click(); document.getElementById('m-nba').click(); await wait();
    // a game of the night before, graded: it is opened in the form, locked, for one of the presses below
    set('gdate', '2026-11-12'); document.getElementById('example').click(); await wait(); set('gdate', '2026-11-12'); await wait();
    document.getElementById('add').click(); await wait();
    const C = JSON.parse(smStore.getItem('callsheet3.card.v1')).find(x => x.gdate === '2026-11-12');
    const grade = (k, v) => { const el = document.querySelector('#cardTable .grade[data-id="' + C.id + '"][data-k="' + k + '"]'); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); };
    grade('fa', '110'); grade('fh', '120'); await wait();
    document.getElementById('clear').click(); document.getElementById('m-nba').click(); await wait();
    set('gdate', '2026-11-13'); document.getElementById('example').click(); await wait(); set('gdate', '2026-11-13'); await wait();
    document.getElementById('add').click(); await wait();
    set('away', 'Celtics'); set('home', 'Lakers'); set('line', '219.5'); set('sp', '-3.5'); await wait();
    document.getElementById('add').click(); await wait();
    const bd = document.getElementById('boardDate'); bd.value = '2026-11-13'; bd.dispatchEvent(new Event('change')); await wait();
    const rows = () => JSON.parse(smStore.getItem('callsheet3.card.v1')).filter(x => x.gdate === '2026-11-13');
    const A = rows().find(x => /76ers @ Knicks/.test(x.matchup)), B = rows().find(x => /Celtics @ Lakers/.test(x.matchup));
    // a bet on the second game from the board, a simulation call on the first from its own card
    const brow = [...document.querySelectorAll('#board tbody tr')].find(t => /Celtics @ Lakers/.test(t.innerText) && t.querySelector('.takebtn')); brow.querySelector('.takebtn').click(); await wait();
    document.querySelector('#cardTable [data-open="' + A.id + '"]').click(); await wait();
    document.querySelector('#nbaSimPanel .takebtn[data-stake*="|own|total|"]').click(); await wait();
    // the form holds a draft of a third game when the button is pressed, with a fold standing open in the rail
    document.getElementById('clear').click(); await wait(); document.getElementById('m-nba').click(); await wait();
    set('away', 'Bulls'); set('home', 'Heat'); set('line', '230.5'); set('op', '-110'); set('up', '-110'); set('hml', '-150'); set('aml', '130'); set('gdate', '2026-11-13'); await wait();
    const foldOf = () => document.querySelector('#markets details.mknotes') || document.querySelector('#markets details'); if (foldOf()) foldOf().open = true;
    const state = () => {
      const vals = {}; document.querySelectorAll('input, select, textarea').forEach((e, i) => { vals[e.id || ('#' + i)] = e.type === 'checkbox' ? e.checked : e.value; });
      const html = {}; ['signals', 'forecastLine', 'markets', 'why', 'nbaOutPanel', 'nbaLineupPanel', 'nbaFormPanel', 'nbaSimPanel', 'nbaMidPanel', 'nbaCrewPanel', 'nbaKalshiPanel', 'nbaCtxPanel', 'rankTag', 'secSimLive', 'secOutLive', 'secKalshiLive', 'secCrewLive', 'secMidLive', 'nbaNav', 'eyebrow', 'picks', 'bestBets', 'likeliest', 'board', 'cardTable', 'taking', 'saveState', 'lockNote']
        .forEach(k => { const e = document.getElementById(k); html[k] = e ? e.innerHTML + '|' + e.hidden : null; });
      return JSON.stringify({ vals, html, open: [...document.querySelectorAll('details')].map(d => d.open ? 1 : 0).join(''), dis: [...document.querySelectorAll('input, select, textarea, button')].map(e => e.disabled ? 1 : 0).join(''),
        pressed: ['m-mlb', 'm-nba', 'm-wnba'].map(id => document.getElementById(id).getAttribute('aria-pressed')).join(), store: ['callsheet3.card.v1', 'callsheet3.draft.v1', 'callsheet3.props.v1', 'callsheet3.slate.v1'].map(k => smStore.getItem(k)) });
    };
    const body = document.getElementById('phoneBody'), esc = async () => { document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })); await wait(); };
    const notes = () => [...body.querySelectorAll('.note')].map(txt), press = async (ms) => { document.getElementById('phone').click(); await wait(ms || 900); };
    const mock = (0, eval)('(' + src + ')'); mock({ docs: { 'phone/config': { url } }, owner: true });
    const before = state(), fold0 = !!(foldOf() && foldOf().open);
    await press(1000);
    const after = state(), diff = [];
    if (before !== after) { const X = JSON.parse(before), Y = JSON.parse(after); for (const k of Object.keys(X)) { if (X[k] && typeof X[k] === 'object') { for (const j of Object.keys(X[k])) if (X[k][j] !== Y[k][j]) diff.push(k + '.' + j); } else if (X[k] !== Y[k]) diff.push(k); } }
    const doc = JSON.parse(JSON.stringify(window.__mock.docs['phone/latest'] || null)), gdoc = JSON.parse(JSON.stringify(window.__mock.docs['phone/games'] || null));
    const gids = k => ((doc.sheet || {})[k] || []).map(x => x.gid === undefined ? '-' : x.gid === String(A.id) ? 'A' : x.gid === String(B.id) ? 'B' : '?').join('');
    const saved = { notes: notes(), calls: window.__mock.calls.slice(), same: before === after, diff, fold0, fold1: !!(foldOf() && foldOf().open), v: doc.v, keys: Object.keys(doc).join(), games: doc.games, gkeys: gdoc ? Object.keys(gdoc).join() : '', gv: gdoc && gdoc.v, gd: gdoc && gdoc.d,
      gat: !!gdoc && gdoc.at === doc.at, gz: !!gdoc && /^z[A-Za-z0-9_-]{2000,}$/.test(gdoc.panels), gbytes: gdoc ? JSON.stringify(gdoc).length : 0, bytes: JSON.stringify(doc).length,
      gid: { take: gids('take'), four: gids('four'), likely: gids('likely'), sim: gids('sim') }, take: doc.sheet.take.map(x => x.k + ':' + x.p), ids: ['take', 'four', 'bets', 'likely', 'sim'].some(k => (doc.sheet[k] || []).some(x => x.ids)) };
    // the sheet as the phone shows it: a game line opens its game's card over the sheet, under the line that was pressed
    document.getElementById('phonePreview').click(); await wait();
    const sh = document.getElementById('phoneSheet'), pp = () => document.getElementById('phonePanel'), ppb = () => document.getElementById('phonePanelBody');
    const cardOf = re => [...sh.querySelectorAll('[data-pgid]')].find(c => re.test(c.innerText));
    const read = () => { const p = ppb(); return { open: !pp().hidden, line: txt(p.querySelector('.pp-line')), head: txt(p.querySelector('.pgame h3')), band: txt(p.querySelector('.pgame .pd-band')), sigs: p.querySelectorAll('.signals .sig').length, sigLinks: p.querySelectorAll('.signals a').length,
      fc: /^Forecast/.test(txt(p.querySelector('.pg-fc'))), mks: p.querySelectorAll('.mk').length, others: !!(p.querySelector('details.others') || {}).open, pick: txt(p.querySelector('.pickcard .lab')), split: !!p.querySelector('.split'),
      secs: [...p.querySelectorAll('details.pg-sec')].map(d => txt(d.querySelector('.pg-t')) + (d.open ? '*' : '')), simRows: p.querySelectorAll('.simtab tbody tr').length, tiles: p.querySelectorAll('.simtile').length, taking: [...p.querySelectorAll('.simtab .chip.taken')].map(txt),
      why: p.querySelectorAll('ul.why li').length, controls: p.querySelectorAll('button, a, input, select, textarea').length, data: (p.innerHTML.match(/\sdata-[a-z-]+=/g) || []).length, ids: (p.innerHTML.match(/\sid=/g) || []).length, titles: (p.innerHTML.match(/\stitle=/g) || []).length,
      words: /Press Clear|Type the inputs|type the app's parlay price|into the form/.test(p.innerText) }; };
    const preview = { tip: txt(sh.querySelector('.psh-tip')), gtaps: sh.querySelectorAll('[data-pgid]').length, ptaps: sh.querySelectorAll('[data-pids]').length, plain: sh.querySelectorAll('.pshk:not(.tap)').length, heads: [...sh.querySelectorAll('h2')].map(txt) };
    cardOf(/TAKING · NBA(?! · SIM)/).click(); await wait(350); preview.bet = read();
    await esc(); preview.afterEsc = { panel: pp().hidden, sheet: sh.hidden };
    cardOf(/TAKING · NBA · SIMULATION/).click(); await wait(350); preview.simTake = read();
    await esc(); await esc();
    // the file to send: the game's card folded under each of its lines
    document.getElementById('phoneFile').click(); await wait(500);
    const filed = { name: (window.__mock.saved || {}).filename || '', data: (window.__mock.saved || {}).data || '' };
    await esc();
    // the games' document refused by a full store: the sheet is saved all the same, its game lines plain, and the dialog says so
    window.__mock.fail = ['quota_exceeded']; window.__mock.calls.length = 0;
    await press(1000);
    const d2 = window.__mock.docs['phone/latest'];
    const noGames = { note: notes()[0] || '', calls: window.__mock.calls.slice(), games: d2.games, gid: ['take', 'four', 'bets', 'likely', 'sim'].map(k => (d2.sheet[k] || []).filter(x => x.gid !== undefined).length).join() };
    document.getElementById('phonePreview').click(); await wait();
    noGames.taps = sh.querySelectorAll('.pshk.tap').length; noGames.cards = sh.querySelectorAll('.pshk').length; noGames.tip = !!sh.querySelector('.psh-tip'); await esc(); await esc();
    // a graded game open in the form, locked, when the button is pressed: the rail's grading and the lock stand after it
    document.querySelector('#cardTable [data-open="' + C.id + '"]').click(); await wait();
    const before3 = state(), final3 = txt(document.querySelector('#markets .final'));
    window.__mock.calls.length = 0; await press(1000);
    const graded = { same: before3 === state(), final0: final3, final1: txt(document.querySelector('#markets .final')), lock: !document.getElementById('lockNote').hidden, dis: document.getElementById('line').disabled, games: window.__mock.docs['phone/latest'].games };
    await esc();
    // the store unavailable once on the games' document: one more try, then the sheet. The form is on another sport for this press, a baseball game in it and the
    // NBA card out of sight, and the page is read before and after it again
    document.getElementById('clear').click(); await wait(); document.getElementById('m-mlb').click(); await wait(); document.getElementById('example').click(); await wait();
    if (foldOf()) foldOf().open = true;
    const before2 = state(), fold2 = !!(foldOf() && foldOf().open), sport2 = ['m-mlb', 'm-nba', 'm-wnba'].map(id => document.getElementById(id).getAttribute('aria-pressed')).join();
    window.__mock.fail = ['unavailable']; window.__mock.calls.length = 0;
    await press(2200);
    const after2 = state(), diff2 = [];
    if (before2 !== after2) { const X = JSON.parse(before2), Y = JSON.parse(after2); for (const k of Object.keys(X)) { if (X[k] && typeof X[k] === 'object') { for (const j of Object.keys(X[k])) if (X[k][j] !== Y[k][j]) diff2.push(k + '.' + j); } else if (X[k] !== Y[k]) diff2.push(k); } }
    const again = { calls: window.__mock.calls.slice(), games: window.__mock.docs['phone/latest'].games, gat: window.__mock.docs['phone/games'].at === window.__mock.docs['phone/latest'].at, note: notes()[0] || '',
      same: before2 === after2, diff: diff2, fold0: fold2, fold1: !!(foldOf() && foldOf().open), sport: sport2, away: document.getElementById('away').value + ' @ ' + document.getElementById('home').value, rail: txt(document.querySelector('#markets .pickcard .lab')) };
    await esc();
    const docs = JSON.parse(JSON.stringify(window.__mock.docs));
    delete window.claude; delete window.__mock;
    document.getElementById('clear').click(); await wait(); document.getElementById('m-nba').click(); await wait();
    bd.value = ''; bd.dispatchEvent(new Event('change')); await wait();
    return { saved, preview, filed, noGames, graded, again, docs };
  }, { src: claudeMock.toString(), url: PH_URL });
  const phGView = async (opts) => {
    const c = await pg.context().browser().newContext({ viewport: { width: 390, height: 844 } }), p = await c.newPage(), e2 = [];
    p.on('pageerror', e => e2.push(e.message));
    await p.addInitScript(claudeMock, opts);
    await p.goto('file://' + path.join(__dirname, 'web/callsheet3.html'));
    await p.waitForFunction(() => window.smStore && window.smStore.ready, null, { timeout: 60000 }); await p.waitForTimeout(800);
    const r = await p.evaluate(async () => {
      const wait = (ms) => new Promise(r => setTimeout(r, ms || 140)), txt = e => (e ? e.innerText : '').replace(/\s+/g, ' ').trim();
      const s = document.getElementById('phoneSheet'); if (!s || s.hidden) return { open: false, calls: window.__mock.calls.slice() };
      const g = [...s.querySelectorAll('[data-pgid]')], o = { open: true, how: s.dataset.how, gtaps: g.length, cards: s.querySelectorAll('.pshk').length, tip: txt(s.querySelector('.psh-tip')), controls: s.querySelectorAll('input, button, select, textarea, a').length, atOpen: window.__mock.calls.slice(), right: 0, wrong: 0, none: 0, fits: true, pcontrols: 0, shut: 0 };
      for (const c of g) {
        c.click(); await wait(220);
        const pp = document.getElementById('phonePanel'), p = document.getElementById('phonePanelBody'), h = txt(p.querySelector('.pgame h3')), m = txt(c.querySelector('.a4'));
        if (!h) o.none++; else if (m.indexOf(h) === 0 && txt(p.querySelector('.pp-line')) === txt(c)) o.right++; else o.wrong++;
        o.last = txt(p).slice(0, 200); o.fits = o.fits && pp.scrollWidth <= pp.clientWidth + 1; o.pcontrols += p.querySelectorAll('button, a, input, select, textarea').length; o.shut = pp.querySelectorAll('[data-ppclose]').length;
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })); await wait(60);
      }
      o.sheetStays = !s.hidden; o.calls = window.__mock.calls.slice(); o.pageFits = document.documentElement.scrollWidth <= window.innerWidth;
      return o;
    });
    await c.close(); r.errs = e2; return r;
  };
  const phGDocs = phG.docs || {};
  const phGOwner = await phGView({ docs: phGDocs, owner: true });
  const phGGuest = await phGView({ docs: phGDocs, owner: false });
  const phGStale = await phGView({ docs: Object.assign({}, phGDocs, { 'phone/games': Object.assign({}, phGDocs['phone/games'], { at: '2026-01-01T00:00:00.000Z' }) }), owner: true });
  const phGGone = await phGView({ docs: { 'phone/latest': phGDocs['phone/latest'], 'phone/config': phGDocs['phone/config'] }, owner: false });
  const phGFilePath = path.join(require('os').tmpdir(), 'cs3-harness-' + process.pid + '-games.html');
  fs.writeFileSync(phGFilePath, phG.filed.data || '<!doctype html><title>nothing saved</title>');
  const gCtx = await pg.context().browser().newContext({ viewport: { width: 390, height: 844 }, javaScriptEnabled: false }), gPage = await gCtx.newPage(), gReqs = [];
  gPage.on('request', q => { if (!/^(file|data):/.test(q.url())) gReqs.push(q.url()); });
  await gPage.goto('file://' + phGFilePath); await gPage.waitForTimeout(400);
  const gFolds = await gPage.locator('details.pfd').count(), gGameFolds = await gPage.locator('details.pfd:has(.pgame)').count();
  const gTip = gFolds ? (await gPage.locator('.psh-tip').innerText()).replace(/\s+/g, ' ').trim() : '';
  if (gGameFolds) { await gPage.locator('details.pfd:has(.pgame) > summary').first().click(); await gPage.waitForTimeout(200); }
  const gOpen = await gPage.locator('details.pfd[open]').count();
  const gHead = gOpen ? (await gPage.locator('details.pfd[open] .pgame h3').first().innerText()).trim() : '', gUnder = gOpen ? (await gPage.locator('details.pfd[open] > summary .a4').first().innerText()).trim() : '';
  const gSecs0 = await gPage.locator('details.pfd[open] details.pg-sec[open]').count();
  if (gOpen) { await gPage.locator('details.pfd[open] details.pg-sec:not([open]) > summary').first().click(); await gPage.waitForTimeout(200); }
  const gSecs1 = await gPage.locator('details.pfd[open] details.pg-sec[open]').count(), gWide = await gPage.evaluate(() => document.documentElement.scrollWidth);
  await gCtx.close(); try { fs.unlinkSync(phGFilePath); } catch (e) {}
  await pg.evaluate(async (k) => { for (const x of Object.keys(k)) { if (k[x] === null || k[x] === undefined) await smStore.removeItem(x); else await smStore.setItem(x, k[x]); } }, phGKeep);
  await reloaded();
  const phGs = phG.saved, gfd = phG.filed.data || '';
  chk(JSON.stringify(phGs.calls) === JSON.stringify(['use db', 'set phone/games', 'set phone/latest', 'get phone/config'])
      && phGs.v === 4 && phGs.keys === 'v,d,at,sheet,panels,games' && phGs.games === 2 && phGs.gkeys === 'v,d,at,panels' && phGs.gv === 1 && phGs.gd === '2026-11-13' && phGs.gat && phGs.gz && phGs.gbytes < 200000 && phGs.bytes < 200000
      && phGs.gid.take === 'BA' && phGs.gid.four.split('').sort().join('') === 'AB' && phGs.gid.likely.split('').sort().join('') === 'AB' && /^[AB]+$/.test(phGs.gid.sim) && !phGs.ids
      && /^card:Lakers ML$/.test(phGs.take[0]) && /^sim:Total (OVER|UNDER) 231\.5$/.test(phGs.take[1])
      && /^Saved for your phone at \d{1,2}:\d\d [AP]M: \d+ lines, .* and the simulation's calls\. Tap a game line and its game's card opens, the signals, the pick, every market and the simulation: 2 games\.$/.test(phGs.notes[0] || '')
      && /they scan the same code and get tonight's sheet with the detail behind each pick, the games' cards with it, and nothing else, view only/.test(phGs.notes[2] || ''),
      'phone, the games\' cards at the save (11 Nov 2026, the user: "have it so the game lines open as well like the props"): with games on the board the button writes the games\' cards to a document of their own first (phone/games, packed, stamped with the sheet\'s date and time), then the sheet, which says how many it carries; every game line of the sheet, the bet and the simulation call you are taking, the parlay legs, the likeliest sides and the simulation\'s calls, carries its own game\'s mark; and the dialog says a game line opens its game\'s card and how many games',
      JSON.stringify({ calls: phGs.calls, v: phGs.v, keys: phGs.keys, games: phGs.games, gkeys: phGs.gkeys, gv: phGs.gv, gd: phGs.gd, gat: phGs.gat, gz: phGs.gz, gbytes: phGs.gbytes, bytes: phGs.bytes, gid: phGs.gid, ids: phGs.ids, take: phGs.take, notes: phGs.notes.map(n => n.slice(0, 330)) }));
  chk(phGs.same && phGs.diff.length === 0 && phGs.fold0 && phGs.fold1
      && phG.again.same && phG.again.diff.length === 0 && phG.again.fold0 && phG.again.fold1 && phG.again.sport === 'true,false,false' && /^Rays @ Yankees$/.test(phG.again.away) && /^THE PICK/i.test(phG.again.rail)
      && phG.graded.same && /^Final: 76ers 110, Knicks 120 /.test(phG.graded.final0) && /this card went \d+-\d+/.test(phG.graded.final0) && phG.graded.final1 === phG.graded.final0 && phG.graded.lock && phG.graded.dis && phG.graded.games === 2,
      'phone, the page after the save: drawing the games\' cards puts each game through the form, and when the button has done the form is as it stood, a draft of a third game in it: every box and tick, the rail and every section of the NBA card, the board, the card table, the bets marked Taking, which sport is pressed, what is disabled, the fold that stood open in the rail, and everything in the page\'s storage, the draft included; the same with a graded game of the night before open in the form, its final and its record still on the rail and the form still locked; and the same with the form on another sport, a baseball game in it and the NBA card out of sight, which holds after the save what it held before',
      JSON.stringify({ same: phGs.same, diff: phGs.diff.slice(0, 12), fold0: phGs.fold0, fold1: phGs.fold1, graded: phG.graded, mlb: { same: phG.again.same, diff: phG.again.diff.slice(0, 12), fold0: phG.again.fold0, fold1: phG.again.fold1, sport: phG.again.sport, away: phG.again.away, rail: phG.again.rail } }));
  const gBet = phG.preview.bet || {}, gSim = phG.preview.simTake || {};
  chk(phG.preview.tip === "Tap a game line for its game's card." && phG.preview.gtaps === 8 && phG.preview.ptaps === 0 && phG.preview.plain === 0
      && phG.preview.heads.join('|').toLowerCase() === "taking tonight 2|the parlay four 2|likeliest at any price 2|the simulation's calls, bet or better 2"
      && gBet.open && /^TAKING · NBA Lakers ML \d/.test(gBet.line) && / Celtics @ Lakers · Moneyline$/.test(gBet.line) && gBet.head === 'Celtics @ Lakers' && /^NBA · NOV 13$/i.test(gBet.band)
      && gBet.sigs >= 2 && gBet.sigLinks === 0 && gBet.fc && gBet.mks === 4 && gBet.others && /^THE PICK/i.test(gBet.pick) && gBet.split && gBet.secs[0] === 'SIMULATION*' && gBet.secs[gBet.secs.length - 1] === 'WHY' && gBet.secs.slice(1).every(s => !/\*$/.test(s)) && gBet.secs.length >= 4
      && gBet.simRows === 6 && gBet.tiles === 4 && gBet.taking.length === 0 && gBet.why >= 3 && gBet.controls === 0 && gBet.data === 0 && gBet.ids === 0 && gBet.titles === 0 && !gBet.words
      && phG.preview.afterEsc.panel && !phG.preview.afterEsc.sheet
      && gSim.open && /^TAKING · NBA · SIMULATION Total (OVER|UNDER) 231\.5 /.test(gSim.line) && / 76ers @ Knicks · the simulation, the sim's own view$/.test(gSim.line) && gSim.head === '76ers @ Knicks' && gSim.mks === 4 && gSim.simRows === 6
      && gSim.taking.join() === 'TAKING' && gSim.controls === 0 && gSim.data === 0 && gSim.ids === 0 && gSim.titles === 0 && !gSim.words,
      'phone, a game line opens its game\'s card: every line of a game on the sheet carries the mark and none is left plain; a press opens that game\'s card over the sheet under the line that was pressed, as the computer draws the game: tonight\'s signals as chips (no link in them), the forecast, the pick and its why, the four markets standing open with their numbers, the split, the simulation standing open with its tiles and its table, and the rest of the NBA card and the why folded under their headings; the simulation call you are taking is marked in its table on its own game and not on the other; no button, field, link, id, hover note or handler is in it, nor a word telling the reader to press something on the computer; and Escape shuts the card and leaves the sheet',
      JSON.stringify({ tip: phG.preview.tip, gtaps: phG.preview.gtaps, ptaps: phG.preview.ptaps, plain: phG.preview.plain, heads: phG.preview.heads, bet: gBet, afterEsc: phG.preview.afterEsc, sim: gSim }));
  const gCalls = ['use db', 'use user', 'isOwner', 'sub phone/latest', 'get phone/games'];
  chk(phGOwner.errs.length === 0 && phGOwner.open && phGOwner.how === 'auto' && phGOwner.gtaps === 8 && phGOwner.cards === 8 && phGOwner.right === 8 && phGOwner.wrong === 0 && phGOwner.none === 0 && phGOwner.fits && phGOwner.pageFits && phGOwner.pcontrols === 0 && phGOwner.shut === 1 && phGOwner.sheetStays
      && JSON.stringify(phGOwner.atOpen) === JSON.stringify(gCalls) && JSON.stringify(phGOwner.calls) === JSON.stringify(gCalls) && phGOwner.tip === "Tap a game line for its game's card."
      && phGGuest.errs.length === 0 && phGGuest.open && phGGuest.how === 'guest' && phGGuest.controls === 0 && phGGuest.gtaps === 8 && phGGuest.right === 8 && phGGuest.wrong === 0 && phGGuest.none === 0 && phGGuest.fits && phGGuest.pcontrols === 0 && phGGuest.sheetStays
      && JSON.stringify(phGGuest.calls) === JSON.stringify(gCalls),
      'phone, the games\' cards on the owner\'s phone and a guest\'s: the sheet that lands says games\' cards ride beside it, so the phone reads that document once as the sheet opens and never again; each of the eight game lines opens its own game\'s card under its own line, inside the screen\'s width, with nothing in it to press but Close, and Escape leaves the sheet; someone the page is shared with gets the same, with no control anywhere on the sheet, and no script error on either',
      JSON.stringify({ owner: { errs: phGOwner.errs, open: phGOwner.open, how: phGOwner.how, gtaps: phGOwner.gtaps, cards: phGOwner.cards, right: phGOwner.right, wrong: phGOwner.wrong, none: phGOwner.none, fits: phGOwner.fits, pageFits: phGOwner.pageFits, pcontrols: phGOwner.pcontrols, shut: phGOwner.shut, atOpen: phGOwner.atOpen, calls: phGOwner.calls, tip: phGOwner.tip },
        guest: { errs: phGGuest.errs, open: phGGuest.open, how: phGGuest.how, controls: phGGuest.controls, gtaps: phGGuest.gtaps, right: phGGuest.right, wrong: phGGuest.wrong, none: phGGuest.none, fits: phGGuest.fits, pcontrols: phGGuest.pcontrols, calls: phGGuest.calls } }));
  chk(phGStale.errs.length === 0 && phGStale.open && phGStale.gtaps === 8 && phGStale.none === 8 && phGStale.right === 0 && phGStale.wrong === 0 && / The detail of this one is not in the save\. Press Phone QR on the computer again, or open it there\.$/.test(phGStale.last || '') && phGStale.sheetStays
      && phGGone.errs.length === 0 && phGGone.open && phGGone.gtaps === 8 && phGGone.none === 8 && phGGone.right === 0 && / The detail of this one is not in the save\./.test(phGGone.last || '')
      && /^Saved for your phone at .* and the simulation's calls\. The games' cards did not save \(the page's store is full\), so a game line does not open tonight; press the button again for them\.$/.test(phG.noGames.note)
      && JSON.stringify(phG.noGames.calls) === JSON.stringify(['use db', 'set phone/games', 'set phone/latest', 'get phone/config']) && phG.noGames.games === 0 && phG.noGames.gid === '0,0,0,0,0' && phG.noGames.taps === 0 && phG.noGames.cards === 8 && !phG.noGames.tip
      && JSON.stringify(phG.again.calls) === JSON.stringify(['use db', 'set phone/games', 'set phone/games', 'set phone/latest', 'get phone/config']) && phG.again.games === 2 && phG.again.gat && /: 2 games\.$/.test(phG.again.note),
      'phone, when a game\'s card is not there: games\' cards stamped with another save\'s time are not this sheet\'s and are not shown, and a sheet whose games\' document is gone says the same under the line that was pressed, with no script error; a full store that refuses the games\' document still gets the sheet, saved with its game lines plain and the dialog saying the games\' cards did not save and why; and a store unavailable once on the games\' document is tried once more before the sheet is written',
      JSON.stringify({ stale: { errs: phGStale.errs, open: phGStale.open, gtaps: phGStale.gtaps, none: phGStale.none, right: phGStale.right, wrong: phGStale.wrong, last: (phGStale.last || '').slice(-120) }, gone: { errs: phGGone.errs, gtaps: phGGone.gtaps, none: phGGone.none, last: (phGGone.last || '').slice(-120) }, noGames: phG.noGames, again: { calls: phG.again.calls, games: phG.again.games, gat: phG.again.gat, note: phG.again.note.slice(-60) } }));
  chk(phG.filed.name === 'super-model-2026-11-13.html' && /^<!doctype html><html lang="en">/.test(gfd) && !/<script|<button|<a\b|<input|<select|<textarea|<iframe|<img|\son[a-z]+\s*=|\sdata-[a-z-]+=|\sid=|https?:\/\//i.test(gfd)
      && gFolds === 8 && gGameFolds === 8 && gTip === "Tap a game line for its game's card." && gOpen === 1 && /^(76ers @ Knicks|Celtics @ Lakers)$/.test(gHead) && gUnder.indexOf(gHead) === 0 && gSecs0 === 1 && gSecs1 === 2 && gWide <= 390 && gReqs.length === 0,
      'phone, the file to send with the games in it: each game line of the saved file folds its game\'s card under it, a still copy with no script, button, link, field, id, handler or outside address; opened with scripts off on a phone-width screen a tap on a line opens that game\'s card, a tap on a heading inside it opens that section, nothing is fetched and nothing runs off the side',
      JSON.stringify({ name: phG.filed.name, bytes: gfd.length, folds: gFolds, gameFolds: gGameFolds, tip: gTip, open: gOpen, head: gHead, under: gUnder.slice(0, 60), secs0: gSecs0, secs1: gSecs1, wide: gWide, reqs: gReqs.slice(0, 3) }));

  // ---- 11 Nov 2026: the Kalshi card reads the sheet's chances of the game on the form. It read them off the page's last result, and the card is drawn before the
  //      forecast it sits in has finished, so a game opened from the board carried the "by the sheet" chances of the game drawn before it until something redrew
  //      the form (found while the games' cards were being drawn for the phone, each of which is one draw). Two games here, priced apart, opened one after the other ----
  const kalLagKeep = await pg.evaluate(async () => { await smStore.ready; const k = {}; for (const x of ['callsheet3.card.v1', 'callsheet3.draft.v1']) k[x] = await smStore.getItem(x); await smStore.removeItem('callsheet3.card.v1'); return k; });
  await reloaded();
  const kalLag = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 120));
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    await smStore.ready;
    const rung = (x, mid, vol) => [x, +(mid - 0.01).toFixed(2), +(mid + 0.01).toFixed(2), +mid.toFixed(2), vol];
    const kal = { at: '2026-11-14T20:00:00Z', ev: 'KXNBAGAME-26NOV14', fee: 0.07, a: { bid: 0.57, ask: 0.58, last: 0.58, vol: 149511, oi: 136925 }, h: { bid: 0.42, ask: 0.43, last: 0.43, vol: 140051, oi: 115254 },
      sp: { a: [rung(1.5, 0.56, 900), rung(2.5, 0.51, 1200), rung(3.5, 0.47, 800), rung(4.5, 0.41, 500)], h: [rung(1.5, 0.33, 40), rung(3.5, 0.25, 0)] }, tot: [rung(230.5, 0.57, 1500), rung(232.5, 0.49, 8000), rung(234.5, 0.41, 300)] };
    const game = async (away, home, op, up, sph, spa) => {
      document.getElementById('clear').click(); document.getElementById('m-nba').click(); await wait();
      set('gdate', '2026-11-14'); set('away', away); set('home', home); set('line', '232.5'); set('op', op); set('up', up); set('hml', '140'); set('aml', '-165'); set('sp', '2.5'); set('sph', sph); set('spa', spa); set('nbakalshi', JSON.stringify(kal)); await wait();
      document.getElementById('add').click(); await wait();
    };
    await game('Hawks', 'Wizards', '-110', '-110', '-110', '-110');
    await game('Kings', 'Spurs', '-135', '115', '-130', '110');
    document.getElementById('clear').click(); await wait();
    const ids = JSON.parse(smStore.getItem('callsheet3.card.v1')).filter(r => r.gdate === '2026-11-14').map(r => [r.matchup, r.id]);
    const card = () => { const t = document.getElementById('nbaKalshiPanel').innerText.replace(/\s+/g, ' '), sp = /covers [\d.]+% by the crowd, ([\d.]+)% by the sheet/.exec(t), to = /the over [\d.]+% by the crowd, ([\d.]+)% by the sheet/.exec(t); return [sp ? sp[1] : '', to ? to[1] : ''].join('/'); };
    const own = (home) => { const one = (k, mine) => { const m = document.querySelector('#markets .mk[data-key="' + k + '"]'); if (!m) return ''; const p = parseFloat(m.querySelector('.nums .p').textContent), name = m.querySelector('.pick').childNodes[0].textContent; return (mine(name) ? p : 100 - p).toFixed(1); };
      return [one('spread', n => n.indexOf(home) === 0), one('total', n => /^OVER/.test(n))].join('/'); };
    const seen = [];
    for (const [m, id, home] of [[ids[0][0], ids[0][1], 'Wizards'], [ids[1][0], ids[1][1], 'Spurs'], [ids[0][0], ids[0][1], 'Wizards'], [ids[1][0], ids[1][1], 'Spurs']]) {
      document.querySelector('#cardTable [data-open="' + id + '"]').click(); await wait();   // one draw of the form: what a click on a card gives
      seen.push({ game: m, card: card(), own: own(home) });
    }
    document.getElementById('clear').click(); await wait();
    return { seen };
  });
  await pg.evaluate(async (k) => { for (const x of Object.keys(k)) { if (k[x] === null || k[x] === undefined) await smStore.removeItem(x); else await smStore.setItem(x, k[x]); } }, kalLagKeep);
  await reloaded();
  chk(kalLag.seen.length === 4 && kalLag.seen.every(x => /^\d+\.\d\/\d+\.\d$/.test(x.card) && x.card === x.own) && kalLag.seen[0].card === '50.0/50.0' && kalLag.seen[1].card !== kalLag.seen[0].card && kalLag.seen[2].card === kalLag.seen[0].card && kalLag.seen[3].card === kalLag.seen[1].card
      && /Hawks @ Wizards/.test(kalLag.seen[0].game) && /Kings @ Spurs/.test(kalLag.seen[1].game),
      'kalshi, the sheet\'s own game: a game opened from the card shows, on the crowd\'s card, the sheet\'s chance at the book\'s spread and total for that game on the first draw, the same figures its own market rows carry, and not the figures of the game that was drawn before it; two games priced apart, opened in turn and again, each read their own',
      JSON.stringify(kalLag.seen));

  // ---- 12 Nov 2026: a mark keeps what was marked. A prop's mark was a flag and a pair's the other leg's key, so a props file loaded after the mark re-read the
  //      bet at the newer run's line, side and price: on 11 Nov the user's Caleb Wilson UNDER 6.5 rebounds (five rebounds, a win) was recorded as OVER 5.5, a loss,
  //      and two of his pairs were rebuilt and read the wrong way. Here a prop and a pair are marked, the page is loaded again, a later run moves the lines and
  //      turns the picks, and the night is graded: the bets stay as marked. A mark with nothing kept (one made before this) is kept as the rows stand before the
  //      later file replaces them. And a date whose props were made without last season's ledger says so on the tab for as long as the date is shown ----
  const fzKeep = await pg.evaluate(async () => { await smStore.ready; const k = {}; for (const x of ['callsheet3.card.v1', 'callsheet3.props.v1', 'callsheet3.draft.v1']) k[x] = await smStore.getItem(x); await smStore.removeItem('callsheet3.card.v1'); await smStore.removeItem('callsheet3.props.v1'); return k; });
  await reloaded();
  const fzMen = () => {
    const G = [['Spurs', 'Bulls', 'SAS', 'CHI', -2.5]];
    const need = (price) => price < 0 ? -price / (-price + 100) : 100 / (price + 100);
    const man = (pid, name, team, mk, side, line, chance, price, why, o) => Object.assign({ gi: 0, pid: String(pid), name, team, opp: team === 'SAS' ? 'CHI' : 'SAS', home: team === 'CHI', pos: 'F', mk, line, op: side === 'OVER' ? price : 100, up: side === 'UNDER' ? price : 100, book: 'betmgm',
      books: { betmgm: [line, side === 'OVER' ? price : 100, side === 'UNDER' ? price : 100], draftkings: [line, -115, -105] }, proj: line + (side === 'OVER' ? 1.5 : -1.5), sd: 3, pm: side === 'OVER' ? 0.7 : 0.3, pb: 0.5, p: side === 'OVER' ? chance : Math.round((1 - chance) * 10000) / 10000, push: 0, side, chance, price, need: Math.round(need(price) * 10000) / 10000,
      edge: Math.round((chance - need(price)) * 10000) / 10000, band: chance - need(price) > 0.012 ? 'LEAN' : 'no edge', mins: 30, rate36: 8, base: 7, med: line, usg: 15, sdf: 1, starter: true, start_src: "RotoWire's expected five",
      why: [why], log: [6, 5, 7, 4, 6, 5, 8, 5, 6, 4].map((v, i) => ['2026-10-' + String(20 + i), 'OPP', i % 2, 30, v, ['won by 3']]), parts: [{ k: 'pace', t: 'Pace', eff: side === 'OVER' ? 0.3 : -0.3, i: 0 }] }, o || {});
    const file = (men, gen) => ({ format: 'callsheet3.props', version: 1, date: '2026-11-20', generated: gen, games: G.map((g, gi) => ({ gid: 'fz' + gi, away: g[0], home: g[1], aab: g[2], hab: g[3], spread: g[4], total: 225.5, props: men })) });
    const WITH = "7.0 rebounds per 36 this season (9 games, 250 minutes), blended with last season's 6.5 (900 of 900 minutes at a quarter, weight 225): 6.8 per 36", NONE = '7.0 rebounds per 36 this season (9 games, 250 minutes); no last season to blend';
    const crowd = (why) => { const out = []; for (let i = 0; i < 22; i++) out.push(man(100 + i, 'Bench Man ' + (i + 1), i % 2 ? 'CHI' : 'SAS', 'pts', 'UNDER', 8.5, 0.5, -110, why)); return out; };
    return { man, file, WITH, NONE, crowd };
  };
  const fz1 = await pg.evaluate(async (src) => {
    const wait = (ms) => new Promise(r => setTimeout(r, ms || 130)), txt = e => (e ? e.innerText : '').replace(/\s+/g, ' ').trim();
    await smStore.ready;
    const { man, file, WITH, crowd } = (0, eval)('(' + src + ')')();
    const load = async (doc, name) => { const dt = new DataTransfer(); dt.items.add(new File([JSON.stringify(doc)], name, { type: 'application/json' })); const inp = document.getElementById('slateFile'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true })); await wait(); await wait(); };
    // the morning's run, made with last season's ledger: Wilson UNDER 6.5 rebounds at -155, Fox OVER 0.5 threes and UNDER 6.5 assists
    await load(file([man(11, 'Caleb Wilson', 'CHI', 'reb', 'UNDER', 6.5, 0.622, -155, WITH), man(12, "De'Aaron Fox", 'SAS', 'tpm', 'OVER', 0.5, 0.668, -120, WITH), man(12, "De'Aaron Fox", 'SAS', 'ast', 'UNDER', 6.5, 0.64, -155, WITH), man(13, 'Old Mark', 'CHI', 'pts', 'OVER', 10.5, 0.60, -120, WITH),
      man(14, 'Old Mate', 'SAS', 'reb', 'UNDER', 7.5, 0.60, -120, WITH), man(15, 'Old Pal', 'CHI', 'ast', 'OVER', 3.5, 0.58, -110, WITH)].concat(crowd(WITH)), '2026-11-20T15:00:00Z'), 'nba-props-2026-11-20.json');
    if (document.getElementById('propsView').hidden) { document.getElementById('m-props').click(); await wait(); }
    const stored = () => JSON.parse(smStore.getItem('callsheet3.props.v1')).filter(x => x.gdate === '2026-11-20'), row = (name, mk) => stored().find(x => x.name === name && x.mk === mk);
    const warn0 = document.getElementById('propsWarn').hidden;
    document.querySelector('#propsTable tr[data-prop="' + row('Caleb Wilson', 'reb').id + '"] .takebtn').click(); await wait();
    const pairCard = [...document.querySelectorAll('#propsPairs .pk.pair')].find(c => /Fox .* \+ De'Aaron Fox/.test(c.innerText) && c.querySelector('.takebtn'));
    const pairText0 = txt(pairCard).replace(/ Take$/i, ''); pairCard.querySelector('.takebtn').click(); await wait();
    const w = row('Caleb Wilson', 'reb'), sp = (row("De'Aaron Fox", 'tpm').pairsAt || []).concat(row("De'Aaron Fox", 'ast').pairsAt || []);
    // unmarking takes what was kept with it; marking again keeps it again
    document.querySelector('#propsTaking .pk[data-prop="' + w.id + '"] .takebtn').click(); await wait();
    const off = { take: !!row('Caleb Wilson', 'reb').take, took: row('Caleb Wilson', 'reb').took === undefined };
    document.querySelector('#propsTable tr[data-prop="' + w.id + '"] .takebtn').click(); await wait();
    [...document.querySelectorAll('#propsTaking .pk.pair .takebtn')][0].click(); await wait();
    const pairOff = { pairs: !row("De'Aaron Fox", 'tpm').pairs && !row("De'Aaron Fox", 'ast').pairs, kept: !row("De'Aaron Fox", 'tpm').pairsAt && !row("De'Aaron Fox", 'ast').pairsAt };
    [...document.querySelectorAll('#propsPairs .pk.pair')].find(c => /Fox .* \+ De'Aaron Fox/.test(c.innerText) && c.querySelector('.takebtn')).querySelector('.takebtn').click(); await wait();
    const o = { warn0, pairText0, took: w.took, specs: sp, off, pairOff, tookAgain: row('Caleb Wilson', 'reb').took, specsAgain: (row("De'Aaron Fox", 'tpm').pairsAt || []).concat(row("De'Aaron Fox", 'ast').pairsAt || []).length,
      taking: [...document.querySelectorAll('#propsTaking .pk')].map(txt) };
    // a mark from before the marks kept anything: a flag and nothing else. Written after the last click of this visit, so nothing the page saves writes over it
    { const all = JSON.parse(smStore.getItem('callsheet3.props.v1')); all.find(x => x.name === 'Old Mark').take = true;
      all.find(x => x.name === 'Old Mate').pairs = ['2026-11-20|15|ast']; all.find(x => x.name === 'Old Pal').pairs = ['2026-11-20|14|reb']; await smStore.setItem('callsheet3.props.v1', JSON.stringify(all)); }
    o.oldMark = (m => ({ take: m.take, took: m.took === undefined }))(row('Old Mark', 'pts'));
    o.oldPair = { a: row('Old Mate', 'reb').pairs, b: row('Old Pal', 'ast').pairs, kept: row('Old Mate', 'reb').pairsAt === undefined && row('Old Pal', 'ast').pairsAt === undefined };
    return o;
  }, fzMen.toString());
  await reloaded();
  const fz2 = await pg.evaluate(async ({ src, mockSrc, url }) => {
    const wait = (ms) => new Promise(r => setTimeout(r, ms || 130)), txt = e => (e ? e.innerText : '').replace(/\s+/g, ' ').trim();
    await smStore.ready;
    const { man, file, NONE, crowd } = (0, eval)('(' + src + ')')();
    const load = async (doc, name) => { const dt = new DataTransfer(); dt.items.add(new File([JSON.stringify(doc)], name, { type: 'application/json' })); const inp = document.getElementById('slateFile'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true })); await wait(); await wait(); };
    // the page as it comes back: the flag-only mark lists as its row stands, with no time of its own
    if (document.getElementById('propsView').hidden) { document.getElementById('m-props').click(); await wait(); }
    { const pd = document.getElementById('propsDate'); pd.value = '2026-11-20'; pd.dispatchEvent(new Event('change', { bubbles: true })); await wait(); }
    const back = { taking: [...document.querySelectorAll('#propsTaking .pk')].map(txt), flag: (m => ({ take: m.take, took: m.took === undefined }))(JSON.parse(smStore.getItem('callsheet3.props.v1')).find(x => x.name === 'Old Mark')) };
    // the afternoon's run, started in a folder with no last-season ledger: the lines have moved and the picks have turned
    await load(file([man(11, 'Caleb Wilson', 'CHI', 'reb', 'OVER', 5.5, 0.518, -135, NONE), man(12, "De'Aaron Fox", 'SAS', 'tpm', 'OVER', 0.5, 0.668, -210, NONE), man(12, "De'Aaron Fox", 'SAS', 'ast', 'OVER', 5.5, 0.512, -125, NONE), man(13, 'Old Mark', 'CHI', 'pts', 'UNDER', 9.5, 0.55, -110, NONE),
      man(14, 'Old Mate', 'SAS', 'reb', 'OVER', 6.5, 0.53, -115, NONE), man(15, 'Old Pal', 'CHI', 'ast', 'OVER', 4.5, 0.55, -110, NONE)].concat(crowd(NONE)), '2026-11-20T20:00:00Z'), 'nba-props-2026-11-20b.json');
    if (document.getElementById('propsView').hidden) { document.getElementById('m-props').click(); await wait(); }
    const stored = () => JSON.parse(smStore.getItem('callsheet3.props.v1')).filter(x => x.gdate === '2026-11-20'), row = (name, mk) => stored().find(x => x.name === name && x.mk === mk);
    const o = { back, wilson: (w => ({ side: w.side, line: w.line, price: w.price, take: w.take, took: w.took }))(row('Caleb Wilson', 'reb')), oldMark: (w => ({ side: w.side, line: w.line, took: w.took }))(row('Old Mark', 'pts')),
      specs: (row("De'Aaron Fox", 'tpm').pairsAt || []).concat(row("De'Aaron Fox", 'ast').pairsAt || []).length, taking: [...document.querySelectorAll('#propsTaking .pk')].map(txt),
      oldPair: (row('Old Mate', 'reb').pairsAt || []).concat(row('Old Pal', 'ast').pairsAt || []),
      warn: txt(document.getElementById('propsWarn')), warnShown: !document.getElementById('propsWarn').hidden, said: txt(document.getElementById('propsMsg')) };
    document.querySelector('#propsTaking .pk[data-prop="' + row('Caleb Wilson', 'reb').id + '"]').click(); await wait();
    o.panel = { pick: txt(document.querySelector('#propDetailBody .pd-pick')), took: txt(document.querySelector('#propDetailBody .pd-took')) };
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })); await wait();
    [...document.querySelectorAll('#propsTaking .pk.pair')][0].click(); await wait();
    o.pairPanel = { head: txt(document.querySelector('#propDetailBody h3')), pick: txt(document.querySelector('#propDetailBody .pd-pick')), took: txt(document.querySelector('#propDetailBody .pd-took')) };
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })); await wait();
    // the board's Taking tonight, its copy, and the sheet for the phone
    const copies = []; try { Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: t => { copies.push(String(t)); return Promise.resolve(); } } }); } catch (e) {}
    document.getElementById('m-nba').click(); await wait();
    const bd = document.getElementById('boardDate'); bd.value = '2026-11-20'; bd.dispatchEvent(new Event('change')); await wait();
    o.board = [...document.querySelectorAll('#taking .pk')].map(txt);
    document.getElementById('takingText').click(); await wait(250); o.copied = copies[copies.length - 1] || '';
    const mock = (0, eval)('(' + mockSrc + ')'); mock({ docs: { 'phone/config': { url } }, owner: true });
    document.getElementById('phone').click(); await wait(900);
    o.sheet = ((window.__mock.docs['phone/latest'] || {}).sheet || { take: [] }).take.map(x => x.k + ': ' + x.p + ' | ' + x.c + ' | ' + x.pr + (x.ids ? ' | ids ' + x.ids.length : ''));
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })); await wait();
    delete window.claude; delete window.__mock;
    // the grade: Wilson five rebounds, Fox two threes and nine assists, Old Mark ten points, Old Mate seven rebounds, Old Pal four assists
    await load({ format: 'callsheet2.slate', version: 1, date: '2026-11-20', games: [{ sport: 'NBA', gdate: '2026-11-20', away: 'Spurs', home: 'Bulls', finals: { fa: '110', fh: '100', f5a: '50', f5h: '48' }, notes: [],
      box: { '11': ['Caleb Wilson', 15, 2, 5, 1, 0], '12': ["De'Aaron Fox", 31, 20, 3, 9, 2], '13': ['Old Mark', 30, 10, 4, 2, 1], '14': ['Old Mate', 28, 8, 7, 3, 0], '15': ['Old Pal', 26, 9, 2, 4, 1] } }] }, 'nba-grade-2026-11-20.json');
    await wait(300);
    if (document.getElementById('propsView').hidden) { document.getElementById('m-props').click(); await wait(); }
    o.rows = stored().filter(x => !/^Bench Man/.test(x.name)).map(x => [x.name, x.mk, x.side, x.line, x.actual, x.result].join(' '));
    o.graded = [...document.querySelectorAll('#propsTaking .pk')].map(txt);
    o.tiles = [...document.querySelectorAll('#calibBox .calib[data-sport="TAKEN"] > div')].map(txt);
    o.list = [...document.querySelectorAll('#takenList tbody tr')].map(e => e.textContent.replace(/\s+/g, ' ').trim());
    o.recordLine = (txt(document.getElementById('calibBox')).match(/taken \d+-\d+ [^·]+· same-game pairs[^·]*· pairs taken [^·]+/) || [''])[0].trim();
    o.warnGraded = txt(document.getElementById('propsWarn'));
    // the backup carries what the marks kept
    const blob = JSON.parse(smStore.getItem('callsheet3.props.v1'));
    o.kept = { took: blob.filter(x => x.took).length, pairsAt: blob.filter(x => x.pairsAt).length };
    return o;
  }, { src: fzMen.toString(), mockSrc: claudeMock.toString(), url: PH_URL });
  await pg.evaluate(async (k) => { for (const x of Object.keys(k)) { if (k[x] === null || k[x] === undefined) await smStore.removeItem(x); else await smStore.setItem(x, k[x]); } }, fzKeep);
  await reloaded();
  const fzSp = (fz1.specs || [])[0] || {};
  chk(fz1.warn0 && fz1.took && fz1.took.side === 'UNDER' && fz1.took.line === 6.5 && fz1.took.price === -155 && fz1.took.chance === 0.622 && fz1.took.band === 'LEAN' && fz1.took.book === 'betmgm' && /^\d{4}-\d\d-\d\dT/.test(fz1.took.at || '')
      && fz1.specs.length === 1 && fzSp.ks.join() === '2026-11-20|12|tpm,2026-11-20|12|ast' && /^(fanatics|draftkings|fanduel|betmgm)$/.test(fzSp.app) && fzSp.at.length === 2 && fzSp.at[0][3] === 'OVER' && fzSp.at[1][3] === 'UNDER' && fzSp.at[0][4] === 0.5 && fzSp.at[1][4] === 6.5 && /^\d{4}-/.test(fzSp.at0 || '')
      && fz1.off.take === false && fz1.off.took && fz1.pairOff.pairs && fz1.pairOff.kept && fz1.tookAgain && fz1.tookAgain.line === 6.5 && fz1.specsAgain === 1 && fz1.oldMark.take === true && fz1.oldMark.took
      && fz1.oldPair.a.join() === '2026-11-20|15|ast' && fz1.oldPair.b.join() === '2026-11-20|14|reb' && fz1.oldPair.kept
      && fz2.back.taking.some(t => /^TAKING · SAME-GAME PAIR · Spurs @ Bulls · at [A-Za-z]+ · .* (Old Mate UNDER 7\.5 rebounds \+ Old Pal OVER 3\.5 assists|Old Pal OVER 3\.5 assists \+ Old Mate UNDER 7\.5 rebounds) both land /.test(t) && !/As you marked|moved/.test(t))
      && fz2.back.flag.take === true && fz2.back.flag.took && fz2.back.taking.length === 4 && fz2.back.taking.some(t => /^TAKING · NBA PROP · LEAN Old Mark OVER 10\.5 points 60\.0% · -120 needs 54\.5% Spurs @ Bulls · betmgm · projected 12 /.test(t) && !/marked|moved/.test(t))
      && fz2.back.taking.some(t => /^TAKING · NBA PROP · LEAN · marked \d{1,2}:\d\d [AP]M Caleb Wilson UNDER 6\.5 rebounds 62\.2% · -155 /.test(t) && !/moved/.test(t))
      && fz1.taking.length === 2 && fz1.taking.some(t => t.indexOf(fz1.pairText0.replace(/^PAIR #\d+/, 'TAKING · SAME-GAME PAIR')) === 0 && / As you marked it at \d{1,2}:\d\d [AP]M\. /.test(t))
      && fz1.taking.some(t => /^TAKING · NBA PROP · LEAN · marked \d{1,2}:\d\d [AP]M Caleb Wilson UNDER 6\.5 rebounds 62\.2% · -155 needs 60\.8% Spurs @ Bulls · betmgm · projected 5 /.test(t) && !/moved/.test(t)),
      'marks, what a mark keeps: marking a prop keeps its side, line, price, chance, band, book and the time on the row, and marking a pair keeps the ticket on one of its two rows (the app, and each leg\'s line, price and chance there, its side and the card\'s line); the Taking cards read as the cards did and say when they were marked; unmarking takes what was kept with it and marking again keeps it again; and when the page is loaded again the marks read the same, and a mark that kept nothing, as every mark did before (a flag on a prop, the other leg\'s key on a pair), lists as its rows stand with no time of its own',
      JSON.stringify({ back: { flag: fz2.back.flag, taking: fz2.back.taking.map(t => t.slice(0, 200)) }, oldPair: fz1.oldPair, warn0: fz1.warn0, took: fz1.took, specs: fz1.specs, off: fz1.off, pairOff: fz1.pairOff, specsAgain: fz1.specsAgain, oldMark: fz1.oldMark, pairText0: fz1.pairText0.slice(0, 200), taking: fz1.taking.map(t => t.slice(0, 260)) }));
  chk(fz2.wilson.side === 'OVER' && fz2.wilson.line === 5.5 && fz2.wilson.take === true && fz2.wilson.took && fz2.wilson.took.side === 'UNDER' && fz2.wilson.took.line === 6.5 && fz2.wilson.took.price === -155
      && fz2.oldMark.side === 'UNDER' && fz2.oldMark.took && fz2.oldMark.took.side === 'OVER' && fz2.oldMark.took.line === 10.5 && fz2.oldMark.took.price === -120 && fz2.oldMark.took.at === undefined && fz2.specs === 1
      && fz2.oldPair.length === 1 && fz2.oldPair[0].at0 === undefined && fz2.oldPair[0].ks.slice().sort().join() === '2026-11-20|14|reb,2026-11-20|15|ast' && fz2.oldPair[0].at.map(x => x[3] + ' ' + x[4]).sort().join() === 'OVER 3.5,UNDER 7.5'
      && fz2.taking.some(t => /^TAKING · SAME-GAME PAIR · Spurs @ Bulls · at [A-Za-z]+ · .* (Old Mate UNDER 7\.5 rebounds \+ Old Pal OVER 3\.5 assists|Old Pal OVER 3\.5 assists \+ Old Mate UNDER 7\.5 rebounds) both land .* As you marked it: the card has moved since \(.*Old Mate OVER 6\.5 at [-+]\d+.*Old Pal OVER 4\.5 at [-+]\d+.* now\)\. Your ticket stays as marked\./.test(t) || /^TAKING · SAME-GAME PAIR · Spurs @ Bulls · at [A-Za-z]+ · .* (Old Mate UNDER 7\.5 rebounds \+ Old Pal OVER 3\.5 assists|Old Pal OVER 3\.5 assists \+ Old Mate UNDER 7\.5 rebounds) both land .* As you marked it: the card has moved since \(.*Old Pal OVER 4\.5 at [-+]\d+.*Old Mate OVER 6\.5 at [-+]\d+.* now\)\. Your ticket stays as marked\./.test(t))
      && fz2.taking.length === 4 && fz2.taking.some(t => t.indexOf(fz1.pairText0.replace(/^PAIR #\d+/, 'TAKING · SAME-GAME PAIR')) === 0 && /As you marked it at \d{1,2}:\d\d [AP]M: the card has moved since \(.*De'Aaron Fox OVER 5\.5 at [-+]\d+ now\)\. Your ticket stays as marked\./.test(t))
      && fz2.taking.some(t => /^TAKING · NBA PROP · LEAN · marked \d{1,2}:\d\d [AP]M Caleb Wilson UNDER 6\.5 rebounds 62\.2% · -155 needs 60\.8% Spurs @ Bulls · betmgm · projected 5 The card has moved since you marked it: OVER 5\.5 at -135 now \(no edge\)\. Your bet stays as marked\./.test(t))
      && fz2.taking.some(t => /^TAKING · NBA PROP · LEAN Old Mark OVER 10\.5 points 60\.0% · -120 needs 54\.5% .* The card has moved since you marked it: UNDER 9\.5 at -110 now/.test(t))
      && /^OVER 5\.5 rebounds/.test(fz2.panel.pick) && /^You marked UNDER 6\.5 at -155 \(62\.2%, LEAN\) at \d{1,2}:\d\d [AP]M\. The card has moved since and reads as above; your bet is listed and graded as you marked it\.$/.test(fz2.panel.took)
      && fz2.pairPanel.head === "De'Aaron Fox OVER 0.5 threes + De'Aaron Fox UNDER 6.5 assists" && /^As you marked it at .*: the card has moved since .* Your ticket stays as marked\. The ticket above is the one you marked, graded on its own lines; each leg's panel reads as the card stands now\.$/.test(fz2.pairPanel.took)
      && fz2.board.some(t => /Caleb Wilson UNDER 6\.5 rebounds 62\.2% · -155/.test(t)) && fz2.board.some(t => /De'Aaron Fox OVER 0\.5 threes \+ De'Aaron Fox UNDER 6\.5 assists/.test(t)) && /TONIGHT 4 bets marked/.test(fz2.board[fz2.board.length - 1] || '') && fz2.board.some(t => /(Old Mate UNDER 7\.5 rebounds \+ Old Pal OVER 3\.5 assists|Old Pal OVER 3\.5 assists \+ Old Mate UNDER 7\.5 rebounds)/.test(t))
      && /\d\. Caleb Wilson UNDER 6\.5 rebounds -155 · 62\.2% needs 60\.8% · Spurs @ Bulls/.test(fz2.copied) && /\d\. Old Mark OVER 10\.5 points -120/.test(fz2.copied) && /SAME-GAME PAIR De'Aaron Fox OVER 0\.5 threes \+ De'Aaron Fox UNDER 6\.5 assists/.test(fz2.copied) && /SAME-GAME PAIR (Old Mate UNDER 7\.5 rebounds \+ Old Pal OVER 3\.5 assists|Old Pal OVER 3\.5 assists \+ Old Mate UNDER 7\.5 rebounds)/.test(fz2.copied)
      && fz2.sheet.some(s => /^prop: Caleb Wilson UNDER 6\.5 rebounds \| 62\.2 \| -155 \| ids 1$/.test(s)) && fz2.sheet.some(s => /^prop: Old Mark OVER 10\.5 points \| 60 \| -120 \| ids 1$/.test(s)) && fz2.sheet.some(s => /^pair: De'Aaron Fox OVER 0\.5 threes \+ De'Aaron Fox UNDER 6\.5 assists \| [\d.]+ \| \d+ \| ids 2$/.test(s)) && fz2.sheet.some(s => /^pair: (Old Mate UNDER 7\.5 rebounds \+ Old Pal OVER 3\.5 assists|Old Pal OVER 3\.5 assists \+ Old Mate UNDER 7\.5 rebounds) \| [\d.]+ \| \d+ \| ids 2$/.test(s)),
      'marks, through a later run: the page is loaded again and a later props file moves the lines and turns the picks (Wilson to OVER 5.5, Fox\'s assists to OVER 5.5); the marked prop still reads UNDER 6.5 at -155 with the chance and the band it had, and says the card has moved and to what; the marked pair still reads as it was marked, at its app\'s prices, and says which legs have moved; the marks that had kept nothing (the flag on a prop, the keys of a pair) are kept as their rows stood before the later file replaced them, with no time; the prop\'s own panel shows the card as it stands and says what was marked; and the board\'s list, its copy and the sheet for the phone carry the bets as marked',
      JSON.stringify({ wilson: fz2.wilson, oldMark: fz2.oldMark, oldPair: fz2.oldPair, specs: fz2.specs, taking: fz2.taking.map(t => t.slice(0, 420)), panel: fz2.panel, pairPanel: fz2.pairPanel, board: fz2.board.map(t => t.slice(0, 120)), copied: fz2.copied.slice(0, 500), sheet: fz2.sheet }));
  chk(fz2.rows.join(' | ') === "Caleb Wilson reb OVER 5.5 5 loss | De'Aaron Fox tpm OVER 0.5 2 win | De'Aaron Fox ast OVER 5.5 9 win | Old Mark pts UNDER 9.5 10 loss | Old Mate reb OVER 6.5 7 win | Old Pal ast OVER 4.5 4 loss"
      && fz2.graded.some(t => /Caleb Wilson UNDER 6\.5 rebounds 62\.2% · -155 needs 60\.8% WIN · 5 /.test(t)) && fz2.graded.some(t => /Old Mark OVER 10\.5 points 60\.0% · -120 needs 54\.5% LOSS · 10 /.test(t))
      && fz2.graded.some(t => /De'Aaron Fox OVER 0\.5 threes \+ De'Aaron Fox UNDER 6\.5 assists LOSS /.test(t)) && fz2.graded.some(t => /(Old Mate UNDER 7\.5 rebounds \+ Old Pal OVER 3\.5 assists|Old Pal OVER 3\.5 assists \+ Old Mate UNDER 7\.5 rebounds) WIN /.test(t))
      && /^PROPS TAKEN 1-1 says 61\.1% · does 50\.0% \(±35\.4\) · -0\.35u$/i.test(fz2.tiles.find(t => /^PROPS TAKEN/i.test(t)) || '') && /^SAME-GAME PAIRS TAKEN 1-1 says \d\d\.\d% · does 50\.0% \(±35\.4\) · \+\d\.\d\du$/i.test(fz2.tiles.find(t => /^SAME-GAME PAIRS TAKEN/i.test(t)) || '')
      && fz2.list.some(l => /Caleb Wilson UNDER 6\.5 rebounds · Spurs @ Bullsprop62\.2%-155WIN\+0\.65u$/.test(l)) && fz2.list.some(l => /Old Mark OVER 10\.5 points · Spurs @ Bullsprop60\.0%-120LOSS-1\.00u$/.test(l))
      && fz2.list.some(l => /De'Aaron Fox OVER 0\.5 threes \+ De'Aaron Fox UNDER 6\.5 assists · Spurs @ Bullssame-game pair\d\d\.\d%\+\d+LOSS-1\.00u$/.test(l))
      && fz2.list.some(l => /(Old Mate UNDER 7\.5 rebounds \+ Old Pal OVER 3\.5 assists|Old Pal OVER 3\.5 assists \+ Old Mate UNDER 7\.5 rebounds) · Spurs @ Bullssame-game pair\d\d\.\d%\+\d+WIN\+\d\.\d\du$/.test(l))
      && /^taken 1-1 -0\.4u · same-game pairs .* pairs taken 1-1 \+\d\.\du$/.test(fz2.recordLine) && fz2.kept.took === 2 && fz2.kept.pairsAt === 2,
      'marks, at the grade: the rows grade on the later run\'s lines (Wilson OVER 5.5 a loss on five rebounds, Fox\'s assists OVER 5.5 a win on nine), and the bets grade as they were marked: Wilson UNDER 6.5 a win at -155, the flag-only mark a loss on the line it had, the pair a loss on Fox UNDER 6.5 assists, and the pair marked the old way a win on the two lines it had where the later run\'s would have lost; What you took, the list of every pick and the props record\'s own line count them so, at the prices and chances marked; and what the marks kept is in the saved props, so a backup carries it',
      JSON.stringify({ rows: fz2.rows, graded: fz2.graded.map(t => t.slice(0, 200)), tiles: fz2.tiles, list: fz2.list, recordLine: fz2.recordLine, kept: fz2.kept }));
  chk(fz1.warn0 && fz2.warnShown && /^The props on this date were made without last season's ledger\. 28 of the 28 projections rest on this season's games alone, with nothing from last season behind them, .* The run did not find last season's ledger file, nba-ledger-202526\.json, in the folder it was started in\. Copy that file into the folder you run the props from, beside slate\.py \(a copy costs nothing and nothing is pulled again\), run the props again before tip and load the new file: it replaces these, and a bet you have marked stays as you marked it\.$/.test(fz2.warn)
      && /The night is graded as it was made\.$/.test(fz2.warnGraded) && /Last season's ledger, nba-ledger-202526\.json, was not read by this run: 28 of the 28 projections .* Put the file back beside slate\.py, run the props again before tip, and load the new file; it replaces these\./.test(fz2.said),
      'props, a date made without last season\'s ledger: a file whose projections were blended with last season shows no warning; a later file for the same date in which more than half of the projections read no last season to blend puts a standing warning on the tab, above the lists, for as long as the date is shown, with the count, the cause (last season\'s ledger file, named for the season before the date\'s own, was not in the folder the run was started in) and what to do (copy the file, not pull it again, and run the props again; a marked bet stays as marked); once the night is graded it says the night is graded as it was made',
      JSON.stringify({ warn0: fz1.warn0, shown: fz2.warnShown, warn: fz2.warn, graded: fz2.warnGraded.slice(-120), said: fz2.said.slice(0, 400) }));

  // ---- 12 Nov 2026: tickets by best chance (the user: "put together the best two and three guys that have a good chance to each hit to complete the parlay ...
  //      keep them as we have but add the new option as well"). A leg is a pick with an edge on its card and at the app's own line and price that the sheet gives
  //      58% or more there; an over in a game with a spread of five or more is left out, and an over on a man whose minutes swing; a ticket is the picks
  //      likeliest to land together, each on its own game. Nobody here passes the last-five test, so the last-five lists stay empty beside it ----
  const tcKeep = await pg.evaluate(async () => { await smStore.ready; const k = {}; for (const x of ['callsheet3.card.v1', 'callsheet3.props.v1', 'callsheet3.draft.v1']) k[x] = await smStore.getItem(x); await smStore.removeItem('callsheet3.card.v1'); await smStore.removeItem('callsheet3.props.v1'); return k; });
  await reloaded();
  const tc = await pg.evaluate(async () => {
    const wait = (ms) => new Promise(r => setTimeout(r, ms || 120)), txt = e => (e ? e.innerText : '').replace(/\s+/g, ' ').trim();
    await smStore.ready;
    const load = async (doc, name) => { const dt = new DataTransfer(); dt.items.add(new File([JSON.stringify(doc)], name, { type: 'application/json' })); const inp = document.getElementById('slateFile'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true })); await wait(); await wait(); };
    const G = [['Hawks', 'Magic', 'ATL', 'ORL', -2.5], ['Bulls', 'Bucks', 'CHI', 'MIL', 3.5], ['Heat', 'Jazz', 'MIA', 'UTA', -1.5], ['Suns', 'Kings', 'PHX', 'SAC', -7.5]];
    const need = (price) => price < 0 ? -price / (-price + 100) : 100 / (price + 100);
    const cold = L => [L + 2, L - 2, L + 3, L - 1, L + 1, L - 2, L + 2, L - 3, L + 1, L - 1];   // two or three of his last five either way: nobody passes the last-five test
    const steady = [31, 33, 32, 30, 34, 32, 31, 33, 32, 30], swing = [12, 38, 14, 36, 15, 37, 13, 39, 16, 35];
    const man = (pid, name, team, gi, mk, side, line, chance, price, mins, books) => ({ gi, pid: String(pid), name, team, opp: team === G[gi][2] ? G[gi][3] : G[gi][2], home: team === G[gi][3], pos: 'G', mk, line,
      op: side === 'OVER' ? price : 100, up: side === 'UNDER' ? price : 100, book: 'fanduel', books: books || { fanduel: [line, side === 'OVER' ? price : 100, side === 'UNDER' ? price : 100] },
      proj: line + (side === 'OVER' ? 2 : -2), sd: 6, pm: side === 'OVER' ? 0.7 : 0.3, pb: 0.5, p: side === 'OVER' ? chance : Math.round((1 - chance) * 10000) / 10000, push: 0, side, chance, price, need: Math.round(need(price) * 10000) / 10000,
      edge: Math.round((chance - need(price)) * 10000) / 10000, band: chance - need(price) > 0 ? 'LEAN' : 'no edge', mins: 32, rate36: 20, base: 18, med: line + (side === 'OVER' ? 1.5 : -1.5), usg: 22, sdf: 1, starter: true, start_src: "RotoWire's expected five", why: ['x'],
      log: cold(line).map((v, i) => ['2026-11-' + String(10 + i), 'OPP', i % 2, (mins || steady)[i], v, ['won by 3']]), parts: [{ k: 'pace', t: 'Pace', eff: side === 'OVER' ? 0.4 : -0.4, i: 0 }] });
    const men = [man(1, 'Top Under', 'ATL', 0, 'tpm', 'UNDER', 1.5, 0.70, -180, null, { fanduel: [1.5, 100, -180], betmgm: [1.5, 100, -200], draftkings: [1.5, 100, -260] }),   // BetMGM posts him at a price with an edge still, DraftKings at one with none
      man(2, 'Second Under', 'CHI', 1, 'ast', 'UNDER', 4.5, 0.66, -160, null, { fanduel: [4.5, 100, -160], betmgm: [4.5, 100, -175], draftkings: [4.5, 100, -165] }), man(3, 'Third Over', 'MIA', 2, 'pts', 'OVER', 10.5, 0.62, -130), man(4, 'Fourth Under', 'ORL', 0, 'reb', 'UNDER', 6.5, 0.61, -125),
      man(5, 'Lop Over', 'PHX', 3, 'pts', 'OVER', 22.5, 0.69, -150),          // an over in a game with a spread of 7.5, on the dog's man: out as on the favourite's
      man(6, 'Lop Under', 'SAC', 3, 'reb', 'UNDER', 8.5, 0.60, -120),         // an under there is a leg
      man(11, 'Fifth Under', 'ATL', 0, 'ast', 'UNDER', 2.5, 0.585, -120),     // a leg with nobody left on another game to stand beside: a pick under 58% would be, were it let in
      man(7, 'Swing Over', 'MIL', 1, 'pts', 'OVER', 14.5, 0.68, -150, swing), // an over on minutes that swing: out
      man(8, 'Swing Under', 'UTA', 2, 'reb', 'UNDER', 5.5, 0.59, -115, swing),// an under on them is a leg
      man(9, 'Short Chance', 'MIA', 2, 'ast', 'OVER', 3.5, 0.575, -105),      // an edge, and under the 58% a leg asks: out
      man(10, 'No Edge', 'CHI', 1, 'reb', 'UNDER', 9.5, 0.67, -220)];         // 67% at a price that asks 68.8%: no edge, out
    await load({ format: 'callsheet3.props', version: 1, date: '2026-11-21', games: G.map((g, gi) => ({ gid: 'tc' + gi, away: g[0], home: g[1], aab: g[2], hab: g[3], spread: g[4], total: 225.5, props: men.filter(m => m.gi === gi) })) }, 'nba-props-2026-11-21.json');
    if (document.getElementById('propsView').hidden) { document.getElementById('m-props').click(); await wait(); }
    document.getElementById('propsReset').click(); await wait();
    const pick = async (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('change', { bubbles: true })); await wait(); };
    const best = document.getElementById('propsBest');
    const cards = () => [...best.querySelectorAll('.pk.t3')].map(c => ({ n1: txt(c.querySelector('.n1')), pay: txt(c.querySelector('.t3pay')), who: [...c.querySelectorAll('.leg .lname')].map(e => e.textContent).join(' + '), legs: [...c.querySelectorAll('.leg')].map(l => txt(l.querySelector('.l1'))),
      stats: txt(c.querySelector('.t3stats')), tabs: txt(c.querySelector('.t3apps')), cls: c.className }));
    const o = {};
    await pick('propsLegs', '2'); await pick('propsBelow', 't3'); o.form2 = cards().length; o.formNone = txt(best.querySelector('.empty.t3none'));
    await pick('propsBelow', 't3c'); o.two = cards(); o.div2 = txt(best.querySelector('.pk-divider.t3d')); o.stored = localStorage.getItem('callsheet3.props.below.v1');
    await pick('propsLegs', '3'); o.three = cards(); o.div3 = txt(best.querySelector('.pk-divider.t3d'));
    await pick('propsLegs', '2');
    // a best-chance ticket taken and unmarked: the spec says which rule built it, and goes with the mark
    const stored = () => JSON.parse(smStore.getItem('callsheet3.props.v1')).filter(r => r.gdate === '2026-11-21');
    const specs = () => stored().filter(r => r.t3).map(r => r.name + ':' + r.t3.map(sp => sp.app + '/' + sp.m + '/' + sp.ks.length + (sp.listed ? '/listed' + sp.n : '') + (sp.c ? '/c' + sp.c : '') + (sp.take ? '/take' : '')).join(',')).join(';');
    best.querySelector('.pk.t3 [data-t3take]').click(); await wait(); o.taken = specs(); o.taking = [...document.querySelectorAll('#propsTaking .pk.t3 .n1')].map(txt);
    document.querySelector('#propsTaking .pk.t3 [data-t3take]').click(); await wait(); o.untaken = specs();
    best.querySelector('.pk.t3 [data-t3take]').click(); await wait();
    // the same two at another app: a tab where both pass there, the reason where one does not; the tab shows the ticket at that app
    o.tabs = txt(best.querySelector('.pk.t3 .t3apps'));
    best.querySelector('.pk.t3 button.t3app[data-t3app="betmgm"]').click(); await wait(); o.atMgm = cards()[0];
    best.querySelector('.pk.t3 button.t3app[data-t3app="fanduel"]').click(); await wait(); o.backFd = cards()[0].n1;
    // the grade: Top Under 1 three, Second Under 6 assists, Third Over 14, Fourth Under 5, Lop Under 7, Swing Under 4
    await load({ format: 'callsheet2.slate', version: 1, date: '2026-11-21', games: G.map((g, gi) => ({ sport: 'NBA', gdate: '2026-11-21', away: g[0], home: g[1], finals: { fa: '110', fh: '104', f5a: '55', f5h: '50' }, notes: [],
      box: Object.fromEntries(men.filter(m => m.gi === gi).map(m => [m.pid, [m.name, 30, m.name === 'Third Over' ? 14 : 9, ({ 'Fourth Under': 5, 'Lop Under': 7, 'Swing Under': 4 })[m.name] || 12, m.name === 'Second Under' ? 6 : 2, m.name === 'Top Under' ? 1 : 3]])) })) }, 'nba-grade-2026-11-21.json');
    await wait(300);
    if (document.getElementById('propsView').hidden) { document.getElementById('m-props').click(); await wait(); }
    { const pd = document.getElementById('propsDate'); pd.value = '2026-11-21'; pd.dispatchEvent(new Event('change', { bubbles: true })); await wait(); }
    o.kept = specs();
    await pick('propsBelow', 't3c'); await pick('propsLegs', '2'); o.after2 = cards(); o.afterDiv = txt(best.querySelector('.pk-divider.t3d')).slice(-90);
    await pick('propsLegs', '3'); o.after3 = cards();
    await pick('propsLegs', '2'); await pick('propsBelow', 't3'); o.afterForm = cards().length;
    const rec = txt(document.getElementById('propsCalib'));
    o.tiles = (rec.match(/Two-leg tickets by best chance, as listed, to test[\s\S]*?drops out Three-leg tickets by best chance, as listed, to test[\s\S]*?drops out/i) || [''])[0];
    o.formTile = /Two-leg tickets as listed, to test/i.test(rec); o.tookTile = (rec.match(/Two-leg tickets you took [^T]*?u\b/i) || [''])[0];
    o.line = (txt(document.getElementById('calibBox')).match(/two-leg tickets by best chance [^·]+· three-leg tickets by best chance [^·]+/) || [''])[0].trim();
    return o;
  });
  await pg.evaluate(async (k) => { for (const x of Object.keys(k)) { if (k[x] === null || k[x] === undefined) await smStore.removeItem(x); else await smStore.setItem(x, k[x]); } localStorage.setItem('callsheet3.props.below.v1', 't3'); localStorage.setItem('callsheet3.props.legs.v1', '2'); }, tcKeep);
  await reloaded();
  chk(tc.form2 === 0 && /^No two legs on this date pass the test at one app on two games\.$/.test(tc.formNone) && tc.stored === 't3c' && tc.two.length === 3
      && tc.two.map(c => c.n1 + ' :: ' + c.who + ' :: ' + c.stats).join(' | ') === '2 LEGS #1 · at FanDuel · two games :: Top Under + Second Under :: BOTH LAND 46.2% NEEDS 39.6% EDGE +6.6 A UNIT WINS 1.53u | 2 LEGS #2 · at FanDuel · two games :: Third Over + Fourth Under :: BOTH LAND 37.8% NEEDS 31.4% EDGE +6.4 A UNIT WINS 2.18u | 2 LEGS #3 · at FanDuel · two games :: Lop Under + Swing Under :: BOTH LAND 35.4% NEEDS 29.2% EDGE +6.2 A UNIT WINS 2.43u'
      && tc.two[0].legs.join(' | ').toLowerCase() === '1 top under under 1.5 threes -180 · 70.0% | 2 second under under 4.5 assists -160 · 66.0%'
      && !tc.two.concat(tc.three).some(c => /Lop Over|Swing Over|Short Chance|No Edge/.test(c.who))
      && /^No BET on this date\. Two-leg tickets by best chance below, to test, in the LEANs' place: the two picks likeliest to land together at one app, each on its own game\. A leg is a pick with an edge on its card and at the app's own line and price that the sheet gives 58% or more there; an over in a game with a spread of 5 or more is left out, and an over on a man whose minutes swing\. A card is one app throughout; where the same two also pass at another app, a tab on the card shows the ticket there\. Replayed on the fourteen nights that keep the logs and the levers: such legs landed 208-128 one at a time, and the tickets 31 of 71 at two legs for \+11\.0 units \(the sheet said 41\.3%, the prices asked 37\.8%; 16 of 38 then 15 of 33 by half\), where the last-five rule's two legs landed 8 of 25\. A test, not a measured edge: its record builds in Is it working beside the last-five tickets'\.$/.test(tc.div2),
      'tickets by best chance (12 Nov 2026): the choice sits beside the last-five tickets and is kept; a leg is a pick with an edge at the app\'s own line and price that the sheet gives 58% or more; an over in a lopsided game, an over on swinging minutes, a pick under 58% and a pick with no edge are left out, where an under in a lopsided game and an under on swinging minutes are legs; the two likeliest to land together come first, each on its own game, a man in one ticket; and the note above them says the rule and what the replay found',
      JSON.stringify({ form2: tc.form2, none: tc.formNone, stored: tc.stored, two: tc.two.map(c => c.n1 + ' :: ' + c.who + ' :: ' + c.stats), legs: tc.two[0] && tc.two[0].legs, div: tc.div2 }));
  chk(tc.three.length === 2 && tc.three.map(c => c.n1 + ' :: ' + c.who + ' :: ' + c.stats).join(' | ') === '3 LEGS #1 · at FanDuel · three games :: Top Under + Second Under + Third Over :: ALL THREE LAND 28.6% NEEDS 22.4% EDGE +6.3 A UNIT WINS 3.47u | 3 LEGS #2 · at FanDuel · three games :: Fourth Under + Lop Under + Swing Under :: ALL THREE LAND 21.6% NEEDS 16.2% EDGE +5.4 A UNIT WINS 5.17u'
      && /^No BET on this date\. Three-leg tickets by best chance below, to test, .* and the tickets 10 of 55 at three legs, under the 25\.7% the sheet gave them, where two legs landed 31 of 71 for \+11\.0 units\. A test, not a measured edge: its record builds in Is it working beside the last-five tickets'\.$/.test(tc.div3)
      && tc.taken === 'Top Under:fanduel/t3c/2/take' && tc.taking.length === 1 && tc.taking[0] === 'TAKING · 2 LEGS · at FanDuel · two games' && tc.untaken === ''
      && /^the same two at DraftKings × (?:✓ )?FanDuel \+153 46\.2% BetMGM \+136 46\.2% Not at DraftKings: Top Under has no edge at -260 there\.$/i.test(tc.tabs)
      && tc.atMgm.n1 === '2 LEGS #1 · at BetMGM · two games' && tc.atMgm.pay === '+136 2.36×' && tc.atMgm.who === 'Top Under + Second Under' && /^BOTH LAND 46\.2% NEEDS 42\.4% EDGE \+3\.8 /.test(tc.atMgm.stats) && tc.backFd === '2 LEGS #1 · at FanDuel · two games',
      'tickets by best chance, three legs, the take and the other apps: three legs are the three likeliest on three games, then the next three; Take marks the ticket with the rule that built it and unmarking takes the spec away, as with the last-five tickets; where the same two also pass the best-chance test at another app a tab shows the ticket there at its own prices, and an app where one leg has no edge says so',
      JSON.stringify({ three: tc.three.map(c => c.n1 + ' :: ' + c.who + ' :: ' + c.stats), div3: tc.div3.slice(-230), taken: tc.taken, taking: tc.taking, untaken: tc.untaken, tabs: tc.tabs, atMgm: tc.atMgm, back: tc.backFd }));
  chk(tc.kept === 'Top Under:fanduel/t3c/2/c1/take,fanduel/t3c/3/c1;Fourth Under:fanduel/t3c/3/c2;Third Over:fanduel/t3c/2/c2;Lop Under:fanduel/t3c/2/c3'
      && tc.after2.map(c => c.n1 + ' :: ' + c.who).join(' | ') === '2 LEGS #1 · at FanDuel · two games LOSS :: Top Under + Second Under | 2 LEGS #2 · at FanDuel · two games WIN :: Third Over + Fourth Under | 2 LEGS #3 · at FanDuel · two games WIN :: Lop Under + Swing Under'
      && tc.after3.map(c => c.n1 + ' :: ' + c.who).join(' | ') === '3 LEGS #1 · at FanDuel · three games LOSS :: Top Under + Second Under + Third Over | 3 LEGS #2 · at FanDuel · three games WIN :: Fourth Under + Lop Under + Swing Under'
      && tc.afterDiv.endsWith('This list was kept before the games and is in the record.') && tc.afterForm === 0 && tc.formTile === false
      && /^Two-leg tickets by best chance, as listed, to test 2-1 says 39\.8% · does 66\.7% \(±28\.9\) · \+3\.61u the two picks likeliest to land together, each on its own game, at the product of their prices; a void or pushed leg drops out Three-leg tickets by best chance, as listed, to test 1-1 says 25\.1% · does 50\.0% \(±35\.4\) · \+4\.17u the three picks likeliest to land together, each on its own game, at the product of their prices; a void or pushed leg drops out$/i.test(tc.tiles)
      && /^Two-leg tickets you took 0-1 says 46\.2% · does 0\.0% \(±50\.0\) · -1\.00u$/i.test(tc.tookTile) && tc.line === 'two-leg tickets by best chance 2-1 +3.6u · three-leg tickets by best chance 1-1 +4.2u',
      'tickets by best chance, at the grade: the best-chance lists are kept on the rows before the results land, two legs and three, each with its rank, whichever the tab showed; the cards carry the results and say the list is in the record; the record keeps them on tiles of their own and on the card\'s line, apart from the last-five tickets (none listed here) and from the ticket taken',
      JSON.stringify({ kept: tc.kept, after2: tc.after2.map(c => c.n1 + ' :: ' + c.who), after3: tc.after3.map(c => c.n1 + ' :: ' + c.who), div: tc.afterDiv, form: tc.afterForm, formTile: tc.formTile, tiles: tc.tiles, took: tc.tookTile, line: tc.line }));

  // ---- 12 Nov 2026: the sharp book's price shade is off the NBA card (the user, told it had pointed the wrong way: "Take care of these bro"). It is a hockey measure,
  //      where the sharp book moves its price before its number; on an NBA total a shade of three points is rare and the shaded side went 29-27 at last season's last
  //      snapshot, 15-26 at its opener and 8-22 on this season's rows. The chip on the total, the line in tonight's signals and the sentence in the why are gone on
  //      basketball and stay on the other sports; the record keeps counting the shade on its own line and says it is off the card ----
  const shKeep = await pg.evaluate(async () => { await smStore.ready; const k = {}; for (const x of ['callsheet3.card.v1', 'callsheet3.props.v1', 'callsheet3.draft.v1']) k[x] = await smStore.getItem(x); await smStore.removeItem('callsheet3.card.v1'); await smStore.removeItem('callsheet3.props.v1'); return k; });
  await reloaded();
  const shRead = async (c) => { await fill(c.sport, c.inputs); return pg.evaluate(async () => {
    const wait = (ms) => new Promise(r => setTimeout(r, ms || 120)), txt = e => (e ? e.innerText : '').replace(/\s+/g, ' ').trim();
    const line = +document.getElementById('line').value, sh = document.getElementById('sharp');
    sh.value = JSON.stringify({ book: 'pinnacle', line, op: -125, up: 105 }); sh.dispatchEvent(new Event('input', { bubbles: true })); await wait();
    const o = { line, chips: [...document.querySelectorAll('#markets .mk[data-key="total"] .cap')].map(txt).filter(t => /pinnacle|sharp/i.test(t)), signals: document.getElementById('signals').textContent.replace(/\s+/g, ' '),
      why: [...document.querySelectorAll('#why li')].map(txt).filter(t => /Pinnacle, the sharp book/.test(t)).join(' ') };
    sh.value = ''; sh.dispatchEvent(new Event('input', { bubbles: true })); await wait();
    return o; }); };
  const shNba = await shRead(CASES.find(c => c.sport === 'NBA')), shMlb = await shRead(CASES.find(c => c.sport === 'MLB'));
  const shRec = await pg.evaluate(async () => {
    const wait = (ms) => new Promise(r => setTimeout(r, ms || 100)), txt = e => (e ? e.innerText : '').replace(/\s+/g, ' ').trim();
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    await smStore.ready;
    document.getElementById('clear').click(); document.getElementById('m-nba').click(); await wait();
    const f = { gdate: '2026-11-25', away: 'Suns', home: 'Kings', line: '229.5', op: '-110', up: '-110', hml: '-190', aml: '160', sharp: JSON.stringify({ book: 'pinnacle', line: 229.5, op: -125, up: 105 }) };
    Object.keys(f).forEach(k => set(k, f[k])); await wait(); document.getElementById('add').click(); await wait();
    const r = JSON.parse(smStore.getItem('callsheet3.card.v1')).find(x => x.gdate === '2026-11-25' && x.away === 'Suns');
    for (const [k, v] of [['fa', 110], ['fh', 115]]) { const el = document.querySelector('#cardTable .grade[data-id="' + r.id + '"][data-k="' + k + '"]'); el.value = String(v); el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); }
    await wait(160);
    return [...document.querySelectorAll('#calibBox .calib > div')].map(txt).filter(t => /Pinnacle's shade/.test(t)).map(t => (t.match(/Pinnacle's shade, 3\+ points [^·]*/) || [''])[0].trim());
  });
  await pg.evaluate(async (k) => { for (const x of Object.keys(k)) { if (k[x] === null || k[x] === undefined) await smStore.removeItem(x); else await smStore.setItem(x, k[x]); } }, shKeep);
  await reloaded();
  chk(shNba.chips.length === 1 && new RegExp('^Pinnacle agrees at ' + String(shNba.line).replace('.', '\\.') + ' \\(-125/\\+105\\)$', 'i').test(shNba.chips[0]) && !/shades/i.test(shNba.signals) && /Pinnacle, the sharp book: [\d.]+ \(-125\/\+105\)/.test(shNba.why) && !/shades/i.test(shNba.why),
      'the shade off the NBA card (12 Nov 2026): on a basketball game whose sharp book prices the over 6.8 points shorter than the under, the total carries the sharp line\'s chip and no shade chip, tonight\'s signals carry no Pinnacle line and the why names the sharp book\'s number and prices with no sentence about a shade',
      JSON.stringify(shNba));
  chk(shMlb.chips.length === 2 && /^Pinnacle agrees at /i.test(shMlb.chips[0]) && /^Pinnacle shades OVER by 6\.8 points$/i.test(shMlb.chips[1]) && /shades the OVER by 6\.8 points/i.test(shMlb.signals) && /It shades the over by 6\.8 points/.test(shMlb.why),
      'the shade stays on the other sports: the same sharp prices on a baseball game carry the shade\'s chip on the total, its line in the signals and its sentence in the why',
      JSON.stringify(shMlb));
  chk(shRec.length === 1 && shRec[0] === "Pinnacle's shade, 3+ points 0-1 (off the card here: a hockey measure)",
      'the shade\'s record line is kept on basketball: a graded NBA game whose sharp book shaded the over, which lost, counts 0-1 on the total tile\'s own line, and the line says the shade is off the card here',
      JSON.stringify(shRec));

  // ---- 12 Nov 2026: the pick at even money or better, a list of its own (the user, told the sheet's plus-money sides had gone 83-58: "Take care of these bro"). Under
  //      the BETs a choice lists every pick with an edge whose price pays +100 or longer; each such pick carries a chip coloured by its own record, read from the
  //      day the blend changed and grey under fifty graded picks; the record keeps a tile for it. Shown, not scored ----
  const pmKeep = await pg.evaluate(async () => { await smStore.ready; const k = {}; for (const x of ['callsheet3.card.v1', 'callsheet3.props.v1', 'callsheet3.draft.v1']) k[x] = await smStore.getItem(x); k.below = localStorage.getItem('callsheet3.props.below.v1'); await smStore.removeItem('callsheet3.card.v1'); await smStore.removeItem('callsheet3.props.v1'); return k; });
  await reloaded();
  const pm = await pg.evaluate(async () => {
    const wait = (ms) => new Promise(r => setTimeout(r, ms || 120)), txt = e => (e ? e.innerText : '').replace(/\s+/g, ' ').trim();
    await smStore.ready;
    const load = async (doc, name) => { const dt = new DataTransfer(); dt.items.add(new File([JSON.stringify(doc)], name, { type: 'application/json' })); const inp = document.getElementById('slateFile'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true })); await wait(); await wait(); };
    const need = (price) => price < 0 ? -price / (-price + 100) : 100 / (price + 100);
    const man = (pid, name, mk, side, line, chance, price, band) => { const other = price >= 100 ? -125 : 100, op = side === 'OVER' ? price : other, up = side === 'UNDER' ? price : other;
      return { pid: String(pid), name, team: 'ATL', opp: 'ORL', home: false, pos: 'G', mk, line, op, up, book: 'fanduel', books: { fanduel: [line, op, up] }, proj: line + (side === 'OVER' ? 2 : -2), sd: 6, pm: side === 'OVER' ? 0.75 : 0.25, pb: 0.46,
        p: side === 'OVER' ? chance : Math.round((1 - chance) * 10000) / 10000, push: 0, side, chance, price, need: Math.round(need(price) * 10000) / 10000, edge: Math.round((chance - need(price)) * 10000) / 10000, band, mins: 32, rate36: 20, base: 18, med: line + (side === 'OVER' ? 1.5 : -1.5),
        usg: 22, sdf: 1, starter: true, start_src: "RotoWire's expected five", why: ['x'], log: [12, 9, 11, 8, 13, 10, 9, 12, 11, 10].map((v, i) => ['2026-11-' + String(10 + i), 'OPP', i % 2, 32, v, ['won by 3']]), parts: [{ k: 'pace', t: 'Pace', eff: side === 'OVER' ? 0.4 : -0.4, i: 0 }] }; };
    const file = (date, men) => ({ format: 'callsheet3.props', version: 1, date, games: [{ gid: 'pm' + date, away: 'Hawks', home: 'Magic', aab: 'ATL', hab: 'ORL', spread: -2.5, total: 225.5, props: men }] });
    const grade = (date, men, win) => ({ format: 'callsheet2.slate', version: 1, date, games: [{ sport: 'NBA', gdate: date, away: 'Hawks', home: 'Magic', finals: { fa: '110', fh: '104', f5a: '55', f5h: '50' }, notes: [],
      box: Object.fromEntries(men.map(m => [m.pid, [m.name, 30, (win(m) ? m.side === 'OVER' : m.side !== 'OVER') ? 14 : 8, 5, 5, 2]])) }] });
    // tonight: two BETs (one of them at plus money), an under at +105, an over at +100, a lean at -110 and a plus-money side with no edge
    const D = '2026-11-26';
    await load(file(D, [man(1, 'Big Bet', 'pts', 'UNDER', 20.5, 0.60, -120, 'BET'), man(2, 'Plus Bet', 'ast', 'UNDER', 3.5, 0.56, 102, 'BET'), man(3, 'Plus Under', 'reb', 'UNDER', 5.5, 0.52, 105, 'LEAN'), man(4, 'Even Over', 'ast', 'OVER', 2.5, 0.515, 100, 'LEAN'),
      man(5, 'Minus Lean', 'pts', 'UNDER', 8.5, 0.55, -110, 'LEAN'), man(6, 'Plus No Edge', 'tpm', 'OVER', 1.5, 0.45, 110, 'no edge')]), 'nba-props-2026-11-26.json');
    if (document.getElementById('propsView').hidden) { document.getElementById('m-props').click(); await wait(); }
    document.getElementById('propsReset').click(); await wait();
    const pick = async (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('change', { bubbles: true })); await wait(); };
    const day = async (d) => { const pd = document.getElementById('propsDate'); pd.value = d; pd.dispatchEvent(new Event('change', { bubbles: true })); await wait(); };
    const best = document.getElementById('propsBest');
    const cards = () => [...best.querySelectorAll('.pk[data-prop]')].map(c => ({ who: txt(c.querySelector('.n2')), band: /scored bet/.test(c.className) ? 'BET' : 'LEAN', tell: [...c.querySelectorAll('.n5.tells .tell')].filter(t => /even money/i.test(t.textContent)).map(t => t.className.replace('tell ', '') + ' | ' + txt(t)).join(' ## ') }));
    const o = { options: [...document.getElementById('propsBelow').options].map(x => x.value + '=' + x.textContent).join(' | ') };
    await pick('propsBelow', 'leans'); o.leans = cards();
    await pick('propsBelow', 'plus'); o.plus = cards(); o.div = txt(best.querySelector('.pk-divider.plusd')); o.stored = localStorage.getItem('callsheet3.props.below.v1'); o.none0 = !!best.querySelector('.plusnone');
    // the chip on the prop's own panel: on the pick at +105, not on the plus-money side with no edge, not on the lean at -110
    const panelTells = async (name) => { const tr = [...document.querySelectorAll('#propsTable tr[data-prop]')].find(r => r.textContent.indexOf(name) >= 0); if (!tr) return -1; tr.click(); await wait();
      const n = document.getElementById('propDetail').hidden ? -2 : [...document.querySelectorAll('#propDetailBody .pd-tells .tell')].filter(x => /even money/i.test(x.textContent)).length;
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })); await wait(); return n; };
    o.panel = [await panelTells('Plus Under'), await panelTells('Plus No Edge'), await panelTells('Minus Lean')].join(',');
    // a night under the blend as it stands: 52 picks at +105, the unders 20-10 and the overs 12-10; a lean at -110 and a plus-money side with no edge beside them count for nothing
    const N = '2026-11-24', made = [];
    for (let i = 0; i < 30; i++) made.push(Object.assign(man(100 + i, 'Under ' + i, 'pts', 'UNDER', 10.5, 0.52, 105, 'LEAN'), { win: i < 20 }));
    for (let i = 0; i < 22; i++) made.push(Object.assign(man(200 + i, 'Over ' + i, 'pts', 'OVER', 10.5, 0.52, 105, 'LEAN'), { win: i < 12 }));
    made.push(Object.assign(man(300, 'Lean Loser', 'pts', 'UNDER', 10.5, 0.55, -110, 'LEAN'), { win: false })); made.push(Object.assign(man(301, 'Edge None', 'pts', 'OVER', 10.5, 0.44, 120, 'no edge'), { win: false }));
    await load(file(N, made.map(m => { const c = Object.assign({}, m); delete c.win; return c; })), 'nba-props-2026-11-24.json'); await load(grade(N, made, m => m.win), 'nba-grade-2026-11-24.json'); await wait(200);
    // and a night under the older blend, thirty such picks that all lost: before the day the blend changed, not in the pool
    const O = '2026-11-03', old = []; for (let i = 0; i < 30; i++) old.push(man(400 + i, 'Old ' + i, 'pts', 'UNDER', 10.5, 0.52, 100, 'LEAN'));
    await load(file(O, old), 'nba-props-2026-11-03.json'); await load(grade(O, old, () => false), 'nba-grade-2026-11-03.json'); await wait(200);
    if (document.getElementById('propsView').hidden) { document.getElementById('m-props').click(); await wait(); }
    await day(D); await pick('propsBelow', 'plus'); o.after = cards();
    o.tile = [...document.querySelectorAll('#propsCalib .calib > div')].map(txt).filter(t => /^The pick at even money or better/i.test(t));
    // the older night's thirty are picks with an edge at +100, so they list on their own date; they are only out of the chip's pool
    await day(O); o.oldCards = cards().length;
    // a date with a BET and a lean at -110 and nothing at even money: the BET, and a line that says there is none under it
    const E = '2026-11-25'; await load(file(E, [man(500, 'Solo Lean', 'pts', 'UNDER', 8.5, 0.55, -110, 'LEAN'), man(501, 'Solo Bet', 'pts', 'UNDER', 20.5, 0.60, -120, 'BET')]), 'nba-props-2026-11-25.json');
    if (document.getElementById('propsView').hidden) { document.getElementById('m-props').click(); await wait(); }
    await day(E); await pick('propsBelow', 'plus'); o.eCards = cards(); o.eNone = txt(best.querySelector('.plusnone')); o.eDiv = !!best.querySelector('.pk-divider.plusd');
    await day(D); await pick('propsBelow', 't3');
    return o;
  });
  await pg.evaluate(async (k) => { for (const x of Object.keys(k)) { if (x === 'below') { if (k[x] === null) localStorage.removeItem('callsheet3.props.below.v1'); else localStorage.setItem('callsheet3.props.below.v1', k[x]); continue; } if (k[x] === null || k[x] === undefined) await smStore.removeItem(x); else await smStore.setItem(x, k[x]); } }, pmKeep);
  await reloaded();
  const pmWho = (cs) => (cs || []).map(c => c.band + ' ' + c.who).join(' | ');
  chk(/\| plus=even money or better \| leans=the LEANs one by one$/.test(pm.options) && pmWho(pm.leans) === 'BET Plus Bet UNDER 3.5 assists | BET Big Bet UNDER 20.5 points | LEAN Plus Under UNDER 5.5 rebounds | LEAN Minus Lean UNDER 8.5 points | LEAN Even Over OVER 2.5 assists'
      && pmWho(pm.plus) === 'BET Plus Bet UNDER 3.5 assists | BET Big Bet UNDER 20.5 points | LEAN Plus Under UNDER 5.5 rebounds | LEAN Even Over OVER 2.5 assists' && pm.stored === 'plus' && pm.none0 === false
      && /^The sheet's side at even money or better below, to test, in the LEANs' place: every pick with an edge whose price pays \+100 or longer, the most edge first\. .* went 83-58 \(58\.9%\) .* the unders 49-34, the overs 34-24, .* not a scored edge\.$/.test(pm.div),
      'the pick at even money or better (12 Nov 2026): the choice sits under the BETs beside the tickets and the LEANs and is kept; it lists the BETs as always and under them every other pick with an edge at +100 or longer, the most edge first (the under at +105, the over at +100), leaving out the lean at -110 and the plus-money side with no edge, under a line that says what was measured and that it is a test',
      JSON.stringify({ options: pm.options, leans: pmWho(pm.leans), plus: pmWho(pm.plus), div: pm.div.slice(0, 200), stored: pm.stored }));
  const pmTell = (cs, who) => ((cs || []).find(c => c.who.indexOf(who) === 0) || {}).tell;
  chk(/^few \| Pays even money or better · the sheet's side at \+100 or longer has no graded pick since 5 Nov yet; replayed on fourteen nights it went 83-58$/i.test(pmTell(pm.plus, 'Plus Under') || '') && /^few \| Pays even money or better/i.test(pmTell(pm.plus, 'Plus Bet') || '') && /^few \| /.test(pmTell(pm.plus, 'Even Over') || '')
      && pmTell(pm.plus, 'Big Bet') === '' && pmTell(pm.leans, 'Minus Lean') === '' && pm.panel === '1,0,0'
      && /^green \| Pays even money or better · the sheet's side at \+100 or longer does 61\.5%, claimed 52\.0%, on 52 BET and LEAN picks since 5 Nov \(unders 20-10, overs 12-10\); replayed on fourteen nights it went 83-58$/i.test(pmTell(pm.after, 'Plus Under') || '')
      && /^green \| /.test(pmTell(pm.after, 'Even Over') || '') && pmTell(pm.after, 'Big Bet') === '',
      'the even-money chip: a pick with an edge at +100 or longer carries it, on its card and on its panel, a BET among them too, and a pick at a shorter price does not, nor a plus-money side with no edge; with nothing graded since the blend changed it is grey and says so; after a night of 52 such picks that went 32-20 it reads green with its own numbers by side, counting neither the thirty that lost under the older blend, nor a lean at -110, nor a plus-money side with no edge',
      JSON.stringify({ panel: pm.panel, before: (pm.plus || []).map(c => c.who + ' :: ' + c.tell), after: (pm.after || []).map(c => c.who + ' :: ' + c.tell) }));
  chk((pm.tile || []).length === 1 && /^The pick at even money or better, to test 32-20 says 52\.0% · does 61\.5% \(±6\.9\) · \+13\.60u an edge on the card at a price of \+100 or longer, as carded since 5 Nov \(the blend as it stands\): unders 20-10 \+11\.0u · overs 12-10 \+2\.6u · replayed under this blend on fourteen nights it went 83-58 \(shown, not scored\)$/i.test(pm.tile[0])
      && pm.oldCards === 30 && pmWho(pm.eCards) === 'BET Solo Bet UNDER 20.5 points' && pm.eDiv === true && pm.eNone === 'No pick with an edge on this date pays even money or better outside the BETs above.',
      'the even-money record: its own tile on the props record from the day the blend changed, by side, at the prices carded; the older night\'s thirty still list on their own date, being picks with an edge at +100; and a date with a BET and nothing at even money shows the BET and says under it that there is none',
      JSON.stringify({ tile: pm.tile, oldCards: pm.oldCards, eCards: pmWho(pm.eCards), eNone: pm.eNone, eDiv: pm.eDiv }));

  // ---- 12 Nov 2026: a marks file puts a bet back as it was marked (the user, of three bets of 11 Nov the page had recorded wrong: "Take care of these bro"). The marks
  //      of that night were flags, so the record read each bet at the lines a later run carded. The file corrects a mark that is on the page and makes none: a prop
  //      not marked, or a pair whose legs do not name each other, is left alone; a key the page does not hold is passed over; an entry it cannot read is refused ----
  const mkKeep = await pg.evaluate(async () => { await smStore.ready; const k = {}; for (const x of ['callsheet3.card.v1', 'callsheet3.props.v1', 'callsheet3.draft.v1']) k[x] = await smStore.getItem(x); await smStore.removeItem('callsheet3.card.v1'); await smStore.removeItem('callsheet3.props.v1'); return k; });
  await reloaded();
  const mkSrc = () => {
    const need = (price) => price < 0 ? -price / (-price + 100) : 100 / (price + 100);
    const man = (pid, name, team, mk, side, line, chance, price) => ({ pid: String(pid), name, team, opp: team === 'SAS' ? 'CHI' : 'SAS', home: team === 'CHI', pos: 'F', mk, line, op: side === 'OVER' ? price : 100, up: side === 'UNDER' ? price : 100, book: 'betmgm',
      books: { betmgm: [line, side === 'OVER' ? price : 100, side === 'UNDER' ? price : 100] }, proj: line + (side === 'OVER' ? 1.5 : -1.5), sd: 3, pm: side === 'OVER' ? 0.7 : 0.3, pb: 0.5, p: side === 'OVER' ? chance : Math.round((1 - chance) * 10000) / 10000, push: 0, side, chance, price,
      need: Math.round(need(price) * 10000) / 10000, edge: Math.round((chance - need(price)) * 10000) / 10000, band: chance - need(price) > 0 ? 'LEAN' : 'no edge', mins: 30, rate36: 8, base: 7, med: line, usg: 15, sdf: 1, starter: true, start_src: "RotoWire's expected five",
      why: ['x'], log: [6, 5, 7, 4, 6, 5, 8, 5, 6, 4].map((v, i) => ['2026-11-' + String(10 + i), 'OPP', i % 2, 30, v, ['won by 3']]), parts: [{ k: 'pace', t: 'Pace', eff: side === 'OVER' ? 0.3 : -0.3, i: 0 }] });
    const D = '2026-11-27';
    // the rows as a later run left them: the under at 6.5 is an over at 5.5 now, and the pair's second leg has turned to the over at 5.5
    const men = [man(21, 'Rebound Man', 'CHI', 'reb', 'OVER', 5.5, 0.518, -135), man(22, 'Dime Man', 'SAS', 'tpm', 'OVER', 0.5, 0.668, -210), man(22, 'Dime Man', 'SAS', 'ast', 'OVER', 5.5, 0.512, -125), man(23, 'Free Man', 'CHI', 'pts', 'OVER', 10.5, 0.60, -120),
      man(24, 'Loose One', 'SAS', 'reb', 'UNDER', 7.5, 0.60, -120), man(25, 'Loose Two', 'CHI', 'ast', 'OVER', 3.5, 0.58, -110)];
    const props = { format: 'callsheet3.props', version: 1, date: D, games: [{ gid: 'mk0', away: 'Spurs', home: 'Bulls', aab: 'SAS', hab: 'CHI', spread: -2.5, total: 225.5, props: men }] };
    // the box: five rebounds, two threes and nine assists, fourteen points
    const grade = { format: 'callsheet2.slate', version: 1, date: D, games: [{ sport: 'NBA', gdate: D, away: 'Spurs', home: 'Bulls', finals: { fa: '110', fh: '104', f5a: '55', f5h: '50' }, notes: [],
      box: { 21: ['Rebound Man', 30, 9, 5, 2, 1], 22: ['Dime Man', 30, 12, 4, 9, 2], 23: ['Free Man', 30, 14, 4, 2, 1], 24: ['Loose One', 30, 9, 6, 2, 1], 25: ['Loose Two', 30, 9, 4, 5, 1] } }] };
    const k = (pid, mk) => D + '|' + pid + '|' + mk;
    const marks = { format: 'callsheet3.marks', version: 1, date: D, props: [
        { key: k(21, 'reb'), name: 'Rebound Man', took: { side: 'UNDER', line: 6.5, price: -155, chance: 0.622, band: 'LEAN', book: 'betmgm', proj: 5.46 } },
        { key: k(23, 'pts'), name: 'Free Man', took: { side: 'UNDER', line: 10.5, price: -110, chance: 0.55 } },          // never marked: left alone
        { key: k(99, 'pts'), name: 'Nobody', took: { side: 'OVER', line: 1.5, price: -110, chance: 0.5 } },                // not on the page: passed over
        { key: k(21, 'reb'), name: 'Bad Side', took: { side: 'UP', line: 6.5, price: -155, chance: 0.6 } }],                 // not a side: refused
      pairs: [
        { ks: [k(22, 'tpm'), k(22, 'ast')], names: ['Dime Man OVER 0.5 threes', 'Dime Man UNDER 6.5 assists'], app: 'betmgm', kind: 'same_man', f: 1.15, chance: 0.508, at: [[0.5, -210, 0.672, 'OVER', 0.5], [6.5, -200, 0.658, 'UNDER', 6.5]] },
        { ks: [k(24, 'reb'), k(25, 'ast')], names: ['Loose One', 'Loose Two'], app: 'betmgm', chance: 0.4, at: [[7.5, -120, 0.6, 'UNDER', 7.5], [3.5, -110, 0.58, 'OVER', 3.5]] },   // a pair nobody marked: left alone
        { ks: [k(22, 'tpm'), k(22, 'ast')], names: ['Bad Pair'], chance: 0.5, at: [[0.5, -210, 0.672, 'OVER', 0.5]] }] };                                                          // one leg: refused
    return { D, props, grade, marks, k };
  };
  await pg.evaluate(async (src) => {
    const wait = (ms) => new Promise(r => setTimeout(r, ms || 130));
    await smStore.ready;
    const { D, props, k } = (0, eval)('(' + src + ')')();
    const load = async (doc, name) => { const dt = new DataTransfer(); dt.items.add(new File([JSON.stringify(doc)], name, { type: 'application/json' })); const inp = document.getElementById('slateFile'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true })); await wait(); await wait(); };
    await load(props, 'nba-props-2026-11-27.json');
    // the marks as they were before a mark kept anything: a flag on the prop, each leg naming the other. Written after the last click of this visit
    const all = JSON.parse(smStore.getItem('callsheet3.props.v1')), row = (pid, mk) => all.find(x => x.gdate === D && String(x.pid) === String(pid) && x.mk === mk);
    row(21, 'reb').take = true; row(22, 'tpm').pairs = [k(22, 'ast')]; row(22, 'ast').pairs = [k(22, 'tpm')];
    await smStore.setItem('callsheet3.props.v1', JSON.stringify(all));
  }, mkSrc.toString());
  await reloaded();
  const mk = await pg.evaluate(async (src) => {
    const wait = (ms) => new Promise(r => setTimeout(r, ms || 130)), txt = e => (e ? e.innerText : '').replace(/\s+/g, ' ').trim();
    await smStore.ready;
    const { D, grade, marks } = (0, eval)('(' + src + ')')();
    const load = async (doc, name) => { const dt = new DataTransfer(); dt.items.add(new File([JSON.stringify(doc)], name, { type: 'application/json' })); const inp = document.getElementById('slateFile'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true })); await wait(); await wait(); };
    await load(grade, 'nba-grade-2026-11-27.json'); await wait(200);
    const read = async () => {
      if (document.getElementById('propsView').hidden) { document.getElementById('m-props').click(); await wait(); }
      const pd = document.getElementById('propsDate'); pd.value = D; pd.dispatchEvent(new Event('change', { bubbles: true })); await wait();
      const o = { taking: [...document.querySelectorAll('#propsTaking .pk')].map(txt), said: txt(document.getElementById('propsMsg')), shown: !document.getElementById('propsView').hidden, date: document.getElementById('propsDate').value };
      const strip = (x) => { if (!x) return null; const c = JSON.parse(JSON.stringify(x)); (Array.isArray(c) ? c : [c]).forEach(y => { o.fixed = (o.fixed || 0) + (y.fixed ? 1 : 0); delete y.fixed; }); return c; };
      o.rows = JSON.parse(smStore.getItem('callsheet3.props.v1')).filter(x => x.gdate === D).map(x => x.name + ' ' + x.mk + ' | take ' + !!x.take + ' | took ' + JSON.stringify(strip(x.took)) + ' | pairs ' + JSON.stringify(x.pairs || null) + ' | kept ' + JSON.stringify(strip(x.pairsAt)));
      document.getElementById('m-nba').click(); await wait();
      o.took = [...document.querySelectorAll('#calibBox .calib[data-sport="TAKEN"] > div')].map(txt);
      o.list = [...document.querySelectorAll('#takenList tbody tr')].map(e => e.textContent.replace(/\s+/g, ' ').trim());
      return o;
    };
    const o = { before: await read() };
    document.getElementById('m-nba').click(); await wait();   // loaded from the board's tab: the file opens the props at its date
    await load(marks, 'nba-marks-2026-11-27.json'); o.opened = { shown: !document.getElementById('propsView').hidden, date: document.getElementById('propsDate').value, said: txt(document.getElementById('propsMsg')) };
    o.after = await read();
    await load(marks, 'nba-marks-2026-11-27.json'); o.again = await read();
    return o;
  }, mkSrc.toString());
  await pg.evaluate(async (k) => { for (const x of Object.keys(k)) { if (k[x] === null || k[x] === undefined) await smStore.removeItem(x); else await smStore.setItem(x, k[x]); } }, mkKeep);
  await reloaded();
  const mkOne = (xs, re) => (xs || []).filter(x => re.test(x));
  chk(mkOne(mk.before.taking, /Rebound Man OVER 5\.5 rebounds 51\.8% · -135 needs 57\.5% LOSS · 5/i).length === 1 && mkOne(mk.before.taking, /Dime Man OVER 0\.5 threes \+ Dime Man OVER 5\.5 assists WIN/i).length === 1
      && mkOne(mk.before.took, /^Props taken 0-1 /i).length === 1 && mkOne(mk.before.took, /^Same-game pairs taken 1-0 /i).length === 1,
      'a marks file, the night before it (12 Nov 2026): a prop marked with a flag and a pair marked by its legs\' keys read as the rows stand after a later run, the under at 6.5 as an over at 5.5 that lost on five rebounds and the pair with its second leg turned, a win',
      JSON.stringify({ taking: mk.before.taking.map(t => t.slice(0, 200)), took: mk.before.took }));
  chk(mk.opened.shown === true && mk.opened.date === '2026-11-27'
      && mk.opened.said === "The marks file nba-marks-2026-11-27.json put 2 bets back as they were marked: Rebound Man UNDER 6.5 rebounds at -155; Dime Man OVER 0.5 threes + Dime Man UNDER 6.5 assists at +121. Each is listed and graded from here on the line and the side kept, at the price kept. 2 left alone, not marked on this page: Free Man; Loose One + Loose Two. 1 passed over, not among the props this page holds: Nobody. 2 refused, not a mark this page can read: Bad Side; Bad Pair."
      && mkOne(mk.after.rows, /^Rebound Man reb \| take true \| took \{"side":"UNDER","line":6\.5,"price":-155,"chance":0\.622,"band":"LEAN","book":"betmgm","proj":5\.46\} \| pairs null \| kept null$/).length === 1
      && mkOne(mk.after.rows, /^Dime Man tpm \| take false \| took null \| pairs \["2026-11-27\|22\|ast"\] \| kept \[\{"ks":\["2026-11-27\|22\|tpm","2026-11-27\|22\|ast"\],"app":"betmgm","kind":"same_man","f":1\.15,"chance":0\.508,"at":\[\[0\.5,-210,0\.672,"OVER",0\.5\],\[6\.5,-200,0\.658,"UNDER",6\.5\]\]\}\]$/).length === 1
      && mkOne(mk.after.rows, /^Dime Man ast \| take false \| took null \| pairs \["2026-11-27\|22\|tpm"\] \| kept null$/).length === 1
      && mkOne(mk.after.rows, /^Free Man pts \| take false \| took null \| pairs null \| kept null$/).length === 1 && mkOne(mk.after.rows, /^Loose (One reb|Two ast) \| take false \| took null \| pairs null \| kept null$/).length === 2 && mk.after.fixed === 2,
      'a marks file, loaded: it opens the props at its date and says what it did; the prop marked on the page takes the bet the file kept (its side, line, price, chance, band and book) and the marked pair its ticket (the app, each leg\'s line, price, chance and side), stamped as put back; a prop nobody marked and a pair nobody marked are left alone, a key the page does not hold is passed over, and an entry with no side or one leg is refused',
      JSON.stringify({ opened: mk.opened, rows: mk.after.rows, fixed: mk.after.fixed }));
  chk(mkOne(mk.after.taking, /Rebound Man UNDER 6\.5 rebounds 62\.2% · -155 needs 60\.8% WIN · 5 .*The card has moved since you marked it: OVER 5\.5 at -135 now \(no edge\)\. Your bet stays as marked\./i).length === 1
      && mkOne(mk.after.taking, /Dime Man OVER 0\.5 threes \+ Dime Man UNDER 6\.5 assists LOSS both land 50\.8% · pays \+121 \(2\.21×\) needs 45\.2% Dime Man 67\.2% at -210 · Dime Man 65\.8% at -200 · one man, two markets, measured ×1\.15 As you marked it: the card has moved since/i).length === 1
      && mkOne(mk.after.took, /^Props taken 1-0 says 62\.2% · does 100\.0% \(±50\.0\) · \+0\.65u$/i).length === 1 && mkOne(mk.after.took, /^Same-game pairs taken 0-1 says 50\.8% · does 0\.0% \(±50\.0\) · [-−]1\.00u$/i).length === 1
      && mkOne(mk.after.list, /Rebound Man UNDER 6\.5 rebounds · Spurs @ Bullsprop62\.2%[-−]155WIN\+0\.65u$/).length === 1 && mkOne(mk.after.list, /Dime Man OVER 0\.5 threes \+ Dime Man UNDER 6\.5 assists · Spurs @ Bullssame-game pair50\.8%\+121LOSS[-−]1\.00u$/).length === 1
      && JSON.stringify(mk.again.rows) === JSON.stringify(mk.after.rows) && JSON.stringify(mk.again.took) === JSON.stringify(mk.after.took) && mk.again.said === mk.opened.said,
      'a marks file, the night after it: the prop is listed and graded as it was marked, the under at 6.5 a win on five rebounds at -155, with the card it has moved to named beside it; the pair is the ticket that was marked, a loss on nine assists at +121; What you took and the list of every pick read them so; and loading the file a second time changes nothing and keeps one ticket',
      JSON.stringify({ taking: mk.after.taking.map(t => t.slice(0, 330)), took: mk.after.took, list: (mk.after.list || []).slice(0, 4), same: JSON.stringify(mk.again.rows) === JSON.stringify(mk.after.rows), said2: mk.again.said.slice(0, 120) }));

  // ---- 13 Nov 2026: minutes on the way back. The props run reads a man's minutes off the mean of his last five games; with a short game among the five and his last
  //      two above them the mean runs low and the sheet calls the under on him (Zubac: 7, 19, 19, 28, 31, six unders lost on 11 Nov and five BETs on the under again
  //      on the 13th). Measured on fourteen nights: such a man played 4.8 minutes more than projected and the sheet's unders on him went 14-32. The card and the
  //      panel say so, the BETs' note counts them, such an under makes no leg of a ticket by either rule, and the record keeps its line through the trim ----
  const rpKeep = await pg.evaluate(async () => { await smStore.ready; const k = {}; for (const x of ['callsheet3.card.v1', 'callsheet3.props.v1', 'callsheet3.draft.v1']) k[x] = await smStore.getItem(x); k.below = localStorage.getItem('callsheet3.props.below.v1'); k.legs = localStorage.getItem('callsheet3.props.legs.v1'); await smStore.removeItem('callsheet3.card.v1'); await smStore.removeItem('callsheet3.props.v1'); return k; });
  await reloaded();
  const rp = await pg.evaluate(async () => {
    const wait = (ms) => new Promise(r => setTimeout(r, ms || 120)), txt = e => (e ? e.innerText : '').replace(/\s+/g, ' ').trim();
    await smStore.ready;
    const load = async (doc, name) => { const dt = new DataTransfer(); dt.items.add(new File([JSON.stringify(doc)], name, { type: 'application/json' })); const inp = document.getElementById('slateFile'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true })); await wait(); await wait(); };
    const G = [['Hawks', 'Magic', 'ATL', 'ORL', -2.5], ['Bulls', 'Bucks', 'CHI', 'MIL', 3.5], ['Heat', 'Jazz', 'MIA', 'UTA', -1.5]];
    const need = (price) => price < 0 ? -price / (-price + 100) : 100 / (price + 100);
    const steady = [31, 33, 32, 30, 34, 32, 31, 33, 32, 30], back = [30, 31, 30, 29, 30, 7, 19, 19, 28, 31];   // back: a short game five games ago and the last two above the five
    const cold = L => [L + 2, L - 2, L + 3, L - 1, L + 1, L - 2, L + 2, L - 3, L + 1, L - 1];   // three of his last five either way: no leg by the last-five rule
    const man = (pid, name, gi, home, mk, side, line, chance, price, band, mins, vals) => ({ gi, pid: String(pid), name, team: G[gi][home ? 3 : 2], opp: G[gi][home ? 2 : 3], home: !!home, pos: 'F', mk, line,
      op: side === 'OVER' ? price : 100, up: side === 'UNDER' ? price : 100, book: 'fanduel', books: { fanduel: [line, side === 'OVER' ? price : 100, side === 'UNDER' ? price : 100] },
      proj: line + (side === 'OVER' ? 2 : -2), sd: 6, pm: side === 'OVER' ? 0.7 : 0.3, pb: 0.5, p: side === 'OVER' ? chance : Math.round((1 - chance) * 10000) / 10000, push: 0, side, chance, price, need: Math.round(need(price) * 10000) / 10000,
      edge: Math.round((chance - need(price)) * 10000) / 10000, band, mins: 24, rate36: 20, base: 18, med: line + (side === 'OVER' ? 1.5 : -1.5), usg: 22, sdf: 1, starter: true, start_src: "RotoWire's expected five", why: ['x'],
      log: (vals || cold(line)).slice(0, mins.length).map((v, i) => ['2026-11-' + String(10 + i), 'OPP', i % 2, mins[i], v, ['won by 3']]), parts: [{ k: 'pace', t: 'Pace', eff: side === 'OVER' ? 0.4 : -0.4, i: 0 }] });
    const D = '2026-12-10';
    const men = [man(1, 'Ramp Under', 0, 0, 'pts', 'UNDER', 20.5, 0.70, -180, 'BET', back, [18, 25, 17, 19, 16, 4, 12, 14, 22, 18]), man(1, 'Ramp Under', 0, 0, 'reb', 'UNDER', 8.5, 0.66, -150, 'BET', back, [7, 10, 6, 8, 7, 2, 5, 6, 9, 7]),
      man(2, 'Ramp Over', 1, 0, 'ast', 'OVER', 5.5, 0.60, -130, 'LEAN', back),                                    // the same last five, and the sheet's side is the over: no caution
      man(3, 'Steady Under', 1, 1, 'reb', 'UNDER', 6.5, 0.64, -140, 'LEAN', steady, [5, 8, 6, 4, 7, 5, 6, 8, 5, 4]),
      man(4, 'Form Under', 2, 0, 'ast', 'UNDER', 4.5, 0.62, -135, 'LEAN', steady, [3, 6, 4, 2, 5, 3, 4, 6, 3, 2]),
      man(5, 'Short Last', 2, 1, 'pts', 'UNDER', 12.5, 0.59, -125, 'LEAN', [30, 31, 30, 29, 30, 31, 30, 31, 29, 7]),  // the short game is his last one: his last two sit under the five
      man(6, 'Rise No Short', 0, 1, 'reb', 'UNDER', 5.5, 0.60, -130, 'LEAN', [20, 20, 20, 20, 20, 20, 20, 20, 28, 30]),  // his last two above the five and no short game among them
      man(7, 'Four Games', 1, 0, 'pts', 'UNDER', 9.5, 0.585, -120, 'LEAN', [7, 19, 28, 31]),                        // four games behind him: no last five to read
      man(8, 'Median Man', 2, 1, 'reb', 'UNDER', 7.5, 0.57, -120, 'LEAN', [30, 30, 30, 30, 30, 12, 26, 26, 27, 28])];  // short against the median of his five (12 under half of 26), not against their mean (23.8): the median is the measure
    const file = (date, list) => ({ format: 'callsheet3.props', version: 1, date, games: G.map((g, gi) => ({ gid: 'rp' + gi, away: g[0], home: g[1], aab: g[2], hab: g[3], spread: g[4], total: 225.5, props: list.filter(m => m.gi === gi) })) });
    await load(file(D, men), 'nba-props-2026-12-10.json');
    if (document.getElementById('propsView').hidden) { document.getElementById('m-props').click(); await wait(); }
    document.getElementById('propsReset').click(); await wait();
    const pick = async (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('change', { bubbles: true })); await wait(); };
    const day = async (d) => { const pd = document.getElementById('propsDate'); pd.value = d; pd.dispatchEvent(new Event('change', { bubbles: true })); await wait(); };
    const best = document.getElementById('propsBest');
    const cards = () => [...best.querySelectorAll('.pk[data-prop]')].map(c => txt(c.querySelector('.n2')) + ' :: ' + txt(c.querySelector('.n5.ramp')));
    const tix = () => [...best.querySelectorAll('.pk.t3')].map(e => [...e.querySelectorAll('.leg .lname')].map(x => x.textContent).join(' + '));
    const o = {};
    await pick('propsBelow', 'leans'); o.note = txt(best.querySelector('.pk-note')); o.cards = cards();
    const panel = async (name) => { const tr = [...document.querySelectorAll('#propsTable tr[data-prop]')].find(r => r.textContent.indexOf(name) >= 0); tr.click(); await wait(); const t = document.getElementById('propDetail').hidden ? 'closed' : txt(document.querySelector('#propDetailBody .pd-ramp'));
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })); await wait(); return t; };
    o.panel = [await panel('Ramp Under'), await panel('Ramp Over'), await panel('Steady Under')];
    await pick('propsLegs', '2'); await pick('propsBelow', 't3c'); o.c2 = tix(); await pick('propsLegs', '3'); o.c3 = tix();
    await pick('propsLegs', '2'); await pick('propsBelow', 't3'); o.f2 = tix();
    // the night: his two unders lose (26 points, 10 rebounds), the over on the other man wins
    const box = { 'Ramp Under': [26, 10, 3], 'Ramp Over': [9, 4, 7], 'Steady Under': [9, 5, 2], 'Form Under': [9, 4, 6], 'Short Last': [10, 4, 2], 'Rise No Short': [9, 4, 2], 'Four Games': [12, 4, 2], 'Median Man': [9, 5, 2] };
    await load({ format: 'callsheet2.slate', version: 1, date: D, games: G.map((g, gi) => ({ sport: 'NBA', gdate: D, away: g[0], home: g[1], finals: { fa: '110', fh: '104', f5a: '55', f5h: '50' }, notes: [],
      box: Object.fromEntries(men.filter(m => m.gi === gi).map(m => [m.pid, [m.name, 30, box[m.name][0], box[m.name][1], box[m.name][2], 1]])) })) }, 'nba-grade-2026-12-10.json'); await wait(250);
    if (document.getElementById('propsView').hidden) { document.getElementById('m-props').click(); await wait(); }
    await day(D);
    const tile = () => [...document.querySelectorAll('#propsCalib .calib > div')].map(txt).filter(t => /way back/i.test(t));
    o.tile = tile();
    // seven later dates push the night out of the whole ones: its rows are trimmed, the log goes, the mark stays and the record's line with it
    for (let i = 1; i <= 7; i++) { const d = '2026-12-' + String(10 + i); await load(file(d, [man(900 + i, 'Later ' + i, 0, 0, 'pts', 'UNDER', 10.5, 0.5, -110, 'no edge', steady)]), 'nba-props-' + d + '.json'); }
    if (document.getElementById('propsView').hidden) { document.getElementById('m-props').click(); await wait(); }
    await day(D);
    o.kept = JSON.parse(smStore.getItem('callsheet3.props.v1')).filter(x => x.gdate === D).map(x => x.name + ' ' + x.mk + ':' + (x.trim ? 'trim' : 'whole') + (x.log ? ':log' : '') + (x.rmp ? ':rmp' : '')).sort().join(' | ');
    o.tileAfter = tile();
    await pick('propsBelow', 't3');
    return o;
  });
  await pg.evaluate(async (k) => { for (const x of Object.keys(k)) { if (x === 'below' || x === 'legs') { const key = x === 'below' ? 'callsheet3.props.below.v1' : 'callsheet3.props.legs.v1'; if (k[x] === null) localStorage.removeItem(key); else localStorage.setItem(key, k[x]); continue; } if (k[x] === null || k[x] === undefined) await smStore.removeItem(x); else await smStore.setItem(x, k[x]); } }, rpKeep);
  await reloaded();
  const rpLine = 'Minutes on the way back: the projection reads his last five games (7, 19, 19, 28, 31 minutes, 20.8 a game) and one of them is a short game; his last two ran 29.5. Such a man played 4.8 minutes more than the sheet projected on fourteen nights and its under on him went 14-32. Shown, not scored: the chance on this card is not changed.';
  chk(rp.note === "The 2 BETs on this date sit on 1 man in 1 game: a man's BETs land or miss together, so that is 1 bet, not 2. Both BETs on this date are unders on a man whose minutes are on the way back (Ramp Under): the projection reads a short game in his last five, and the sheet's under on such a man went 14-32."
      && (rp.cards || []).join(' ## ') === ['Ramp Under UNDER 8.5 rebounds :: ' + rpLine, 'Ramp Under UNDER 20.5 points :: ' + rpLine, 'Steady Under UNDER 6.5 rebounds :: ', 'Form Under UNDER 4.5 assists :: ', 'Four Games UNDER 9.5 points :: ', 'Rise No Short UNDER 5.5 rebounds :: ', 'Ramp Over OVER 5.5 assists :: ', 'Short Last UNDER 12.5 points :: ', 'Median Man UNDER 7.5 rebounds :: ' + rpLine.replace('7, 19, 19, 28, 31 minutes, 20.8 a game', '12, 26, 26, 27, 28 minutes, 23.8 a game').replace('ran 29.5', 'ran 27.5')].join(' ## ')
      && JSON.stringify(rp.panel) === JSON.stringify([rpLine, '', '']),
      'minutes on the way back (13 Nov 2026): the sheet\'s under on a man with a short game in his last five and his last two above them carries the caution on its card and its panel, with his five and what they average, and the BETs\' note says how many of the BETs are such unders and on whom; the over on such a man carries none, nor an under on steady minutes, nor one whose short game is his last, nor one whose minutes rose with no short game, nor a man with four games behind him; and the short game is read against the median of the five, not their mean',
      JSON.stringify({ note: rp.note, cards: rp.cards, panel: rp.panel }));
  chk(JSON.stringify(rp.c2) === JSON.stringify(['Steady Under + Form Under', 'Rise No Short + Short Last']) && JSON.stringify(rp.c3) === JSON.stringify(['Steady Under + Form Under + Rise No Short']) && JSON.stringify(rp.f2) === JSON.stringify(['Steady Under + Form Under']),
      'minutes on the way back, the tickets: his under is the likeliest pick on the date and the one with the form, and it makes no leg by either rule: the best-chance tickets are built from the next likeliest on each game and the last-five ticket from the other two men with the form',
      JSON.stringify({ c2: rp.c2, c3: rp.c3, f2: rp.f2 }));
  chk((rp.tile || []).length === 1 && /^The under on a man whose minutes are on the way back \(shown, not scored\) 1-2 says 64\.3% · does 33\.3% \(±28\.9\) · [-−]1\.17u a short game in his last five and his last two above them: the projection's minutes run low; counted from the nights whose logs the page holds · measured on fourteen nights before it, 14-32$/i.test(rp.tile[0])
      && rp.kept === 'Form Under ast:trim | Four Games pts:trim | Median Man reb:trim:rmp | Ramp Over ast:trim:rmp | Ramp Under pts:trim:rmp | Ramp Under reb:trim:rmp | Rise No Short reb:trim | Short Last pts:trim | Steady Under reb:trim'
      && JSON.stringify(rp.tileAfter) === JSON.stringify(rp.tile),
      'minutes on the way back, the record: the sheet\'s unders on such men, two lost and one won, sit on their own tile (the over on the other such man is not counted); and when seven later dates push the night out and its rows are trimmed, the log goes, the mark stays on the two men\'s rows and the tile reads the same',
      JSON.stringify({ tile: rp.tile, kept: rp.kept, after: rp.tileAfter }));

  // ---- 13 Nov 2026: a short game set aside in the minutes (the user: "do it"). slate.py now leaves a short game out of a starter's minutes, or counts it as half
  //      a game for another man on the rise, measured on four seasons of box scores, and marks the row (`mshort`). On such a row the page's own caution stands
  //      down, the card and the panel say what was set aside and what the five say untouched, the under is a ticket leg again, and the record keeps a tile for the
  //      picks on such rows, by side; a row of the same shape from the old run keeps the caution ----
  const msKeep = await pg.evaluate(async () => { await smStore.ready; const k = {}; for (const x of ['callsheet3.card.v1', 'callsheet3.props.v1', 'callsheet3.draft.v1']) k[x] = await smStore.getItem(x); k.below = localStorage.getItem('callsheet3.props.below.v1'); k.legs = localStorage.getItem('callsheet3.props.legs.v1'); await smStore.removeItem('callsheet3.card.v1'); await smStore.removeItem('callsheet3.props.v1'); return k; });
  await reloaded();
  const ms = await pg.evaluate(async () => {
    const wait = (ms) => new Promise(r => setTimeout(r, ms || 120)), txt = e => (e ? e.innerText : '').replace(/\s+/g, ' ').trim();
    await smStore.ready;
    const load = async (doc, name) => { const dt = new DataTransfer(); dt.items.add(new File([JSON.stringify(doc)], name, { type: 'application/json' })); const inp = document.getElementById('slateFile'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true })); await wait(); await wait(); };
    const G = [['Hawks', 'Magic', 'ATL', 'ORL', -2.5], ['Bulls', 'Bucks', 'CHI', 'MIL', 3.5], ['Heat', 'Jazz', 'MIA', 'UTA', -1.5]];
    const need = (price) => price < 0 ? -price / (-price + 100) : 100 / (price + 100);
    const steady = [31, 33, 32, 30, 34, 32, 31, 33, 32, 30], back = [30, 31, 30, 29, 30, 7, 19, 19, 28, 31];
    const cold = L => [L + 2, L - 2, L + 3, L - 1, L + 1, L - 2, L + 2, L - 3, L + 1, L - 1];
    const man = (pid, name, gi, home, mk, side, line, chance, price, band, mins, mshort) => Object.assign({ gi, pid: String(pid), name, team: G[gi][home ? 3 : 2], opp: G[gi][home ? 2 : 3], home: !!home, pos: 'F', mk, line,
      op: side === 'OVER' ? price : 100, up: side === 'UNDER' ? price : 100, book: 'fanduel', books: { fanduel: [line, side === 'OVER' ? price : 100, side === 'UNDER' ? price : 100] },
      proj: line + (side === 'OVER' ? 2 : -2), sd: 6, pm: side === 'OVER' ? 0.7 : 0.3, pb: 0.5, p: side === 'OVER' ? chance : Math.round((1 - chance) * 10000) / 10000, push: 0, side, chance, price, need: Math.round(need(price) * 10000) / 10000,
      edge: Math.round((chance - need(price)) * 10000) / 10000, band, mins: 24, rate36: 20, base: 18, med: line + (side === 'OVER' ? 1.5 : -1.5), usg: 22, sdf: 1, starter: true, start_src: "RotoWire's expected five", why: ['x'],
      log: cold(line).slice(0, mins.length).map((v, i) => ['2026-11-' + String(10 + i), 'OPP', i % 2, mins[i], v, ['won by 3']]), parts: [{ k: 'pace', t: 'Pace', eff: side === 'OVER' ? 0.4 : -0.4, i: 0 }] }, mshort ? { mshort } : {});
    const D = '2026-12-20';
    const men = [man(11, 'Set Aside', 0, 0, 'pts', 'UNDER', 20.5, 0.70, -180, 'BET', back, { how: 'out', min: [7], mean: 20.8, read: 24.3 }),                  // the new run: a starter's 7-minute game left out
      man(12, 'Old Run', 1, 0, 'reb', 'UNDER', 8.5, 0.66, -150, 'LEAN', back),                                                                             // the same five from the old run: the caution
      man(13, 'Half Man', 1, 1, 'ast', 'OVER', 5.5, 0.60, -130, 'LEAN', [20, 20, 20, 20, 20, 20, 8, 21, 24, 25], { how: 'half', min: [8], mean: 19.6, read: 20.9 }),
      man(14, 'Two Back', 2, 0, 'pts', 'UNDER', 12.5, 0.59, -125, 'LEAN', [30, 30, 30, 30, 30, 30, 31, 29, 7, 30], { how: 'half2', min: [7], mean: 25.4, read: 27.4 }),
      man(15, 'Two Short', 0, 1, 'reb', 'UNDER', 5.5, 0.585, -120, 'LEAN', [30, 30, 30, 30, 30, 8, 30, 9, 31, 32], { how: 'out', min: [8, 9], mean: 22, read: 31 }),
      man(16, 'No Edge Short', 2, 1, 'reb', 'UNDER', 7.5, 0.52, -120, 'no edge', back, { how: 'out', min: [7], mean: 20.8, read: 24.3 }),                   // no pick: the panel says what was set aside, the record does not count it
      man(17, 'Plain', 2, 1, 'ast', 'UNDER', 4.5, 0.64, -140, 'LEAN', steady)];
    const file = (date, list) => ({ format: 'callsheet3.props', version: 1, date, games: G.map((g, gi) => ({ gid: 'ms' + gi, away: g[0], home: g[1], aab: g[2], hab: g[3], spread: g[4], total: 225.5, props: list.filter(m => m.gi === gi) })) });
    await load(file(D, men), 'nba-props-2026-12-20.json');
    if (document.getElementById('propsView').hidden) { document.getElementById('m-props').click(); await wait(); }
    document.getElementById('propsReset').click(); await wait();
    const pick = async (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('change', { bubbles: true })); await wait(); };
    const day = async (d) => { const pd = document.getElementById('propsDate'); pd.value = d; pd.dispatchEvent(new Event('change', { bubbles: true })); await wait(); };
    const best = document.getElementById('propsBest');
    const cards = () => [...best.querySelectorAll('.pk[data-prop]')].map(c => txt(c.querySelector('.n2')) + ' :: ' + (c.querySelector('.n5.ramp') ? 'CAUTION' : '') + ' :: ' + txt(c.querySelector('.n5.msh')));
    const tix = () => [...best.querySelectorAll('.pk.t3')].map(e => [...e.querySelectorAll('.leg .lname')].map(x => x.textContent).join(' + '));
    const o = {};
    await pick('propsBelow', 'leans'); o.note = txt(best.querySelector('.pk-note')); o.cards = cards();
    const panel = async (name) => { const tr = [...document.querySelectorAll('#propsTable tr[data-prop]')].find(r => r.textContent.indexOf(name) >= 0); tr.click(); await wait(); const b = document.querySelector('#propDetailBody');
      const t = document.getElementById('propDetail').hidden ? 'closed' : (b.querySelector('.pd-ramp') ? 'CAUTION' : '') + ' :: ' + txt(b.querySelector('.pd-msh'));
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })); await wait(); return t; };
    o.panel = [await panel('Set Aside'), await panel('Old Run'), await panel('No Edge Short'), await panel('Plain')];
    await pick('propsLegs', '2'); await pick('propsBelow', 't3c'); o.c2 = tix();
    o.rows = JSON.parse(smStore.getItem('callsheet3.props.v1')).filter(x => x.gdate === D).map(x => x.name + ':' + JSON.stringify(x.mshort)).sort().join(' | ');
    // the night: Set Aside's under wins (15 points), Half Man's over loses (4 assists), Two Back's under wins (9), Two Short's under loses (7 rebounds), Old Run's under loses (10 rebounds)
    const box = { 'Set Aside': [15, 4, 2], 'Old Run': [9, 10, 2], 'Half Man': [9, 4, 4], 'Two Back': [9, 4, 2], 'Two Short': [9, 7, 2], 'No Edge Short': [9, 5, 2], 'Plain': [9, 4, 3] };
    await load({ format: 'callsheet2.slate', version: 1, date: D, games: G.map((g, gi) => ({ sport: 'NBA', gdate: D, away: g[0], home: g[1], finals: { fa: '110', fh: '104', f5a: '55', f5h: '50' }, notes: [],
      box: Object.fromEntries(men.filter(m => m.gi === gi).map(m => [m.pid, [m.name, 30, box[m.name][0], box[m.name][1], box[m.name][2], 1]])) })) }, 'nba-grade-2026-12-20.json'); await wait(250);
    if (document.getElementById('propsView').hidden) { document.getElementById('m-props').click(); await wait(); }
    await day(D);
    const tiles = () => [...document.querySelectorAll('#propsCalib .calib > div')].map(txt).filter(t => /way back|set aside/i.test(t));
    o.tiles = tiles(); o.short = ([...document.querySelectorAll('p.sides')].map(txt).join(' · ').match(/picks on a man with a short game set aside in his minutes [^·]*/) || [''])[0].trim();
    for (let i = 1; i <= 7; i++) { const d = '2026-12-' + String(20 + i); await load(file(d, [man(950 + i, 'Later ' + i, 0, 0, 'pts', 'UNDER', 10.5, 0.5, -110, 'no edge', steady)]), 'nba-props-' + d + '.json'); }
    if (document.getElementById('propsView').hidden) { document.getElementById('m-props').click(); await wait(); }
    await day(D);
    o.kept = JSON.parse(smStore.getItem('callsheet3.props.v1')).filter(x => x.gdate === D).map(x => x.name + ':' + (x.trim ? 'trim' : 'whole') + (x.log ? ':log' : '') + (x.rmp ? ':rmp' : '') + (x.mshort ? ':msh-' + x.mshort.how : '')).sort().join(' | ');
    o.tilesAfter = tiles();
    await pick('propsBelow', 't3');
    return o;
  });
  await pg.evaluate(async (k) => { for (const x of Object.keys(k)) { if (x === 'below' || x === 'legs') { const key = x === 'below' ? 'callsheet3.props.below.v1' : 'callsheet3.props.legs.v1'; if (k[x] === null) localStorage.removeItem(key); else localStorage.setItem(key, k[x]); continue; } if (k[x] === null || k[x] === undefined) await smStore.removeItem(x); else await smStore.setItem(x, k[x]); } }, msKeep);
  await reloaded();
  const msTail = ' Scored from 13 Nov 2026, measured on four seasons of box scores.';
  const msOut = 'Minutes: his 7-minute game is left out (he started all five, and a game cut short three or more back says nothing of tonight). The read is 24.3 a game where the mean of his last five says 20.8.' + msTail;
  chk(ms.note === ''
      && (ms.cards || []).join(' ## ') === ['Old Run UNDER 8.5 rebounds :: CAUTION :: ', 'Set Aside UNDER 20.5 points ::  :: ' + msOut, 'Plain UNDER 4.5 assists ::  :: ',
        'Two Short UNDER 5.5 rebounds ::  :: Minutes: his 8- and 9-minute games are left out (he started all five, and a game cut short three or more back says nothing of tonight). The read is 31.0 a game where the mean of his last five says 22.0.' + msTail,
        'Half Man OVER 5.5 assists ::  :: Minutes: his 8-minute game counts as half a game (his last two run above the five). The read is 20.9 a game where the mean of his last five says 19.6.' + msTail,
        'Two Back UNDER 12.5 points ::  :: Minutes: his 7-minute game two games back counts as half a game (he started all five and his last was a full game). The read is 27.4 a game where the mean of his last five says 25.4.' + msTail].join(' ## ')
      && JSON.stringify(ms.panel) === JSON.stringify([' :: ' + msOut, 'CAUTION :: ', ' :: ' + msOut, ' :: ']),
      'a short game set aside in the minutes (13 Nov 2026): a row the run marked carries no caution and says on its card and its panel which game was set aside, how, the read and what the five say untouched (left out, half a game, half a game two back, two games left out); the same five from the old run keeps the caution and has no such line; a man with no pick still says it on his panel; and the BETs\' note has nothing to add on a BET the run has already read right',
      JSON.stringify({ note: ms.note, cards: ms.cards, panel: ms.panel }));
  chk(JSON.stringify(ms.c2) === JSON.stringify(['Set Aside + Plain', 'Half Man + Two Back'])
      && ms.rows === 'Half Man:{"how":"half","min":[8],"mean":19.6,"read":20.9} | No Edge Short:{"how":"out","min":[7],"mean":20.8,"read":24.3} | Old Run:null | Plain:null | Set Aside:{"how":"out","min":[7],"mean":20.8,"read":24.3} | Two Back:{"how":"half2","min":[7],"mean":25.4,"read":27.4} | Two Short:{"how":"out","min":[8,9],"mean":22,"read":31}',
      'a short game set aside, the tickets and the rows: the under the run has read right makes a leg of the first best-chance ticket and the two half-game men the second, where the same five from the old run, the pick with the most edge on the date, makes none; and each row keeps the mark as the file gave it',
      JSON.stringify({ c2: ms.c2, rows: ms.rows }));
  chk((ms.tiles || []).length === 2
      && /^The under on a man whose minutes are on the way back \(shown, not scored\) 0-1 says 66\.0% · does 0\.0% \(±50\.0\) · [-−]1\.00u /i.test(ms.tiles[0])
      && /^A short game set aside in his minutes \(scored from 13 Nov 2026\) 2-2 says 61\.9% · does 50\.0% \(±25\.0\) · [-−]0\.64u the BET and LEAN picks on a man whose short game the run left out of his minutes or counted as half a game: unders 2-1 \+0\.4u · overs 0-1 [-−]1\.0u · measured on four seasons of box scores: the minutes missed by 6\.3 with the short game in, 5\.6 with it set aside$/i.test(ms.tiles[1])
      && /^picks on a man with a short game set aside in his minutes 2-2 [-−]0\.6u$/.test(ms.short)
      && ms.kept === 'Half Man:trim:msh-half | No Edge Short:trim:msh-out | Old Run:trim:rmp | Plain:trim | Set Aside:trim:msh-out | Two Back:trim:msh-half2 | Two Short:trim:msh-out'
      && JSON.stringify(ms.tilesAfter) === JSON.stringify(ms.tiles),
      'a short game set aside, the record: the four picks on rows the run marked, two won and two lost, sit on their own tile by side (the man with no pick is not counted, nor the old run\'s row, which stays on the caution\'s tile); and when seven later dates push the night out and its rows are trimmed the marks stay, the old run\'s row keeps the caution\'s mark and no other, and both tiles read the same',
      JSON.stringify({ tiles: ms.tiles, short: ms.short, kept: ms.kept, after: ms.tilesAfter }));
  // ---- 13 Nov 2026: the levers as corrected (the user: "Please make sure the levers are accurate"; "explore the confirmed lineups"). slate.py marks every row
  //      it projects with the levers' version (`lv`), says what the lever on who is out read (`chg`), and on a confirmed five with a new role reads his minutes
  //      from his games in that role (`mrole`). The page keeps the three off the file, says on the card and the panel how the minutes were read by the role,
  //      and gives the BET and LEAN picks made under the corrected levers a tile of their own, by band and side; a row from the run as it stood is not in it ----
  const lvKeep = await pg.evaluate(async () => { await smStore.ready; const k = {}; for (const x of ['callsheet3.card.v1', 'callsheet3.props.v1', 'callsheet3.draft.v1']) k[x] = await smStore.getItem(x); k.below = localStorage.getItem('callsheet3.props.below.v1'); k.legs = localStorage.getItem('callsheet3.props.legs.v1'); await smStore.removeItem('callsheet3.card.v1'); await smStore.removeItem('callsheet3.props.v1'); return k; });
  await reloaded();
  const lvr = await pg.evaluate(async () => {
    const wait = (ms) => new Promise(r => setTimeout(r, ms || 120)), txt = e => (e ? e.innerText : '').replace(/\s+/g, ' ').trim();
    await smStore.ready;
    const load = async (doc, name) => { const dt = new DataTransfer(); dt.items.add(new File([JSON.stringify(doc)], name, { type: 'application/json' })); const inp = document.getElementById('slateFile'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true })); await wait(); await wait(); };
    const G = [['Hawks', 'Magic', 'ATL', 'ORL', -2.5], ['Bulls', 'Bucks', 'CHI', 'MIL', 3.5], ['Heat', 'Jazz', 'MIA', 'UTA', -1.5]];
    const need = (price) => price < 0 ? -price / (-price + 100) : 100 / (price + 100);
    const steady = [31, 33, 32, 30, 34, 32, 31, 33, 32, 30];
    const cold = L => [L + 2, L - 2, L + 3, L - 1, L + 1, L - 2, L + 2, L - 3, L + 1, L - 1];
    const man = (pid, name, gi, home, mk, side, line, chance, price, band, extra) => Object.assign({ gi, pid: String(pid), name, team: G[gi][home ? 3 : 2], opp: G[gi][home ? 2 : 3], home: !!home, pos: 'F', mk, line,
      op: side === 'OVER' ? price : 100, up: side === 'UNDER' ? price : 100, book: 'fanduel', books: { fanduel: [line, side === 'OVER' ? price : 100, side === 'UNDER' ? price : 100] },
      proj: line + (side === 'OVER' ? 2 : -2), sd: 6, pm: side === 'OVER' ? 0.7 : 0.3, pb: 0.5, p: side === 'OVER' ? chance : Math.round((1 - chance) * 10000) / 10000, push: 0, side, chance, price, need: Math.round(need(price) * 10000) / 10000,
      edge: Math.round((chance - need(price)) * 10000) / 10000, band, mins: 24, rate36: 20, base: 18, med: line + (side === 'OVER' ? 1.5 : -1.5), usg: 22, sdf: 1, starter: true, start_src: "RotoWire's confirmed five", why: ['x'],
      log: cold(line).map((v, i) => ['2026-11-' + String(10 + i), 'OPP', i % 2, steady[i], v, ['won by 3']]), parts: [{ k: 'out', t: 'Who is out', eff: side === 'OVER' ? 0.4 : -0.4, i: 0 }] }, extra || {});
    const D = '2026-12-29';
    const chg = { 'new': 29.7, back: 5.6, dmin: 0.51, lvl: 41.7, lg: 20, drate36: 0.46 };
    const men = [man(21, 'Role Start', 0, 0, 'pts', 'OVER', 14.5, 0.62, -125, 'BET', { lv: 2, chg, mrole: { how: 'flat', games: 0, starter: true, mean: 16, read: 27.5 } }),          // a bench man in a confirmed five: no start this season
      man(22, 'Role Bench', 1, 0, 'reb', 'UNDER', 6.5, 0.60, -130, 'BET', { lv: 2, chg, starter: false, mrole: { how: 'few', games: 2, starter: false, mean: 24.8, read: 17.8 } }),  // a starter sent to the bench: two bench games this season
      man(23, 'Role Five', 2, 0, 'ast', 'OVER', 4.5, 0.58, -120, 'LEAN', { lv: 2, mrole: { how: 'role', games: 5, starter: true, mean: 22.4, read: 29.6 } }),                       // five starts behind him, in and out of the five
      man(24, 'Plain New', 0, 1, 'pts', 'UNDER', 18.5, 0.59, -125, 'LEAN', { lv: 2, chg: { 'new': null, back: null, dmin: 0, lvl: 0, lg: 20, drate36: -0.3 } }),                   // the corrected run, his last five as they are
      man(25, 'Old Levers', 1, 1, 'ast', 'UNDER', 5.5, 0.64, -140, 'BET', { start_src: "RotoWire's expected five" }),                                                               // a row from the run as it stood: no mark
      man(26, 'No Edge New', 2, 1, 'reb', 'UNDER', 7.5, 0.52, -120, 'no edge', { lv: 2, mrole: { how: 'role', games: 5, starter: true, mean: 20, read: 28 } })];                    // no pick: the panel says the role, the record does not count it
    const file = (date, list) => ({ format: 'callsheet3.props', version: 1, date, levers: 2, games: G.map((g, gi) => ({ gid: 'lv' + gi, away: g[0], home: g[1], aab: g[2], hab: g[3], spread: g[4], total: 225.5, props: list.filter(m => m.gi === gi) })) });
    await load(file(D, men), 'nba-props-2026-12-29.json');
    if (document.getElementById('propsView').hidden) { document.getElementById('m-props').click(); await wait(); }
    document.getElementById('propsReset').click(); await wait();
    const pick = async (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('change', { bubbles: true })); await wait(); };
    const day = async (d) => { const pd = document.getElementById('propsDate'); pd.value = d; pd.dispatchEvent(new Event('change', { bubbles: true })); await wait(); };
    const best = document.getElementById('propsBest');
    const o = {};
    await pick('propsBelow', 'leans');
    o.cards = [...best.querySelectorAll('.pk[data-prop]')].map(c => txt(c.querySelector('.n2')) + ' :: ' + txt(c.querySelector('.n5.mrole'))).sort();
    const panel = async (name) => { const tr = [...document.querySelectorAll('#propsTable tr[data-prop]')].find(r => r.textContent.indexOf(name) >= 0); tr.click(); await wait(); const b = document.querySelector('#propDetailBody');
      const t = document.getElementById('propDetail').hidden ? 'closed' : txt(b.querySelector('.pd-mrole')) + ' :: ' + (/Who is out/.test(txt(b)) ? 'lever named' : 'no lever');
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })); await wait(); return t; };
    o.panel = [await panel('Role Start'), await panel('Old Levers'), await panel('No Edge New'), await panel('Plain New')];
    o.rows = JSON.parse(smStore.getItem('callsheet3.props.v1')).filter(x => x.gdate === D).map(x => x.name + ':' + JSON.stringify([x.lv, x.mrole, x.chg])).sort().join(' | ');
    // the night: Role Start's over wins (20 points), Role Bench's under loses (9 rebounds), Role Five's over wins (6 assists), Plain New's under wins (12 points), Old Levers's under wins (3 assists)
    const box = { 'Role Start': [20, 4, 2], 'Role Bench': [9, 9, 2], 'Role Five': [9, 4, 6], 'Plain New': [12, 4, 2], 'Old Levers': [9, 4, 3], 'No Edge New': [9, 5, 2] };
    await load({ format: 'callsheet2.slate', version: 1, date: D, games: G.map((g, gi) => ({ sport: 'NBA', gdate: D, away: g[0], home: g[1], finals: { fa: '110', fh: '104', f5a: '55', f5h: '50' }, notes: [],
      box: Object.fromEntries(men.filter(m => m.gi === gi).map(m => [m.pid, [m.name, 30, box[m.name][0], box[m.name][1], box[m.name][2], 1]])) })) }, 'nba-grade-2026-12-29.json'); await wait(250);
    if (document.getElementById('propsView').hidden) { document.getElementById('m-props').click(); await wait(); }
    await day(D);
    const tiles = () => [...document.querySelectorAll('#propsCalib .calib > div')].map(txt).filter(t => /levers as corrected/i.test(t));
    o.tiles = tiles(); o.sides = ([...document.querySelectorAll('p.sides')].map(txt).join(' · ').match(/picks under the levers as corrected on 13 Nov 2026: the BET band [^·]* · the leans [^·]*/) || [''])[0].trim();
    for (let i = 1; i <= 7; i++) { const d = i <= 2 ? '2026-12-' + String(29 + i) : '2027-01-0' + String(i - 2); await load(file(d, [man(960 + i, 'After ' + i, 0, 0, 'pts', 'UNDER', 10.5, 0.5, -110, 'no edge', {})]), 'nba-props-' + d + '.json'); }
    if (document.getElementById('propsView').hidden) { document.getElementById('m-props').click(); await wait(); }
    await day(D);
    o.kept = JSON.parse(smStore.getItem('callsheet3.props.v1')).filter(x => x.gdate === D).map(x => x.name + ':' + (x.trim ? 'trim' : 'whole') + (x.lv ? ':lv' + x.lv : '') + (x.mrole ? ':role-' + x.mrole.how : '') + (x.chg ? ':chg' : '')).sort().join(' | ');
    o.tilesAfter = tiles();
    await pick('propsBelow', 't3');
    return o;
  });
  await pg.evaluate(async (k) => { for (const x of Object.keys(k)) { if (x === 'below' || x === 'legs') { const key = x === 'below' ? 'callsheet3.props.below.v1' : 'callsheet3.props.legs.v1'; if (k[x] === null) localStorage.removeItem(key); else localStorage.setItem(key, k[x]); continue; } if (k[x] === null || k[x] === undefined) await smStore.removeItem(x); else await smStore.setItem(x, k[x]); } }, lvKeep);
  await reloaded();
  const lvTail = ' Scored from 13 Nov 2026: with the real starters such a night misses by 5.0 minutes this way and 6.3 from his last five (three seasons of box scores).';
  const lvStart = 'Minutes: the five is confirmed and he starts tonight, a role he has not had in all his last five. The read is no game as a starter this season, so the 27.5 a rotation man with none plays, held to his own five: 27.5 a game where the mean of his last five says 16.0.' + lvTail;
  const lvNoEdge = 'Minutes: the five is confirmed and he starts tonight, a role he has not had in all his last five. The read is his last 5 games as a starter: 28.0 a game where the mean of his last five says 20.0.' + lvTail;
  chk(JSON.stringify(lvr.cards) === JSON.stringify(['Old Levers UNDER 5.5 assists :: ', 'Plain New UNDER 18.5 points :: ',
        'Role Bench UNDER 6.5 rebounds :: Minutes: the five is confirmed and he comes off the bench tonight, a role he has not had in all his last five. The read is his 2 games off the bench this season, with one game\'s weight on the 20.5 a rotation man with none plays: 17.8 a game where the mean of his last five says 24.8.' + lvTail,
        'Role Five OVER 4.5 assists :: Minutes: the five is confirmed and he starts tonight, a role he has not had in all his last five. The read is his last 5 games as a starter: 29.6 a game where the mean of his last five says 22.4.' + lvTail,
        'Role Start OVER 14.5 points :: ' + lvStart])
      && JSON.stringify(lvr.panel) === JSON.stringify([lvStart + ' :: lever named', ' :: lever named', lvNoEdge + ' :: lever named', ' :: lever named']),
      'the levers as corrected, the role read (13 Nov 2026): a row whose minutes the run read from his games in tonight\'s role says so on its card and its panel, by how it was read (no game in the role, a few, his last five in it), with the read and what his last five say; a row read from his last five, new run or old, says nothing; a man with no pick says it on his panel',
      JSON.stringify({ cards: lvr.cards, panel: lvr.panel }));
  chk(lvr.rows === 'No Edge New:[2,{"how":"role","games":5,"starter":true,"mean":20,"read":28},null] | Old Levers:[null,null,null] | Plain New:[2,null,{"nw":null,"back":null,"dmin":0,"lvl":0,"lg":20}] | Role Bench:[2,{"how":"few","games":2,"starter":false,"mean":24.8,"read":17.8},{"nw":29.7,"back":5.6,"dmin":0.51,"lvl":41.7,"lg":20}] | Role Five:[2,{"how":"role","games":5,"starter":true,"mean":22.4,"read":29.6},null] | Role Start:[2,{"how":"flat","games":0,"starter":true,"mean":16,"read":27.5},{"nw":29.7,"back":5.6,"dmin":0.51,"lvl":41.7,"lg":20}]',
      'the levers as corrected, the rows: each keeps the run\'s mark, the role read and what the lever on who is out read as the file gave them; a row from the run as it stood has none of the three',
      lvr.rows);
  chk((lvr.tiles || []).length === 1
      && /^Picks under the levers as corrected \(from 13 Nov 2026\) 3-1 says 59\.8% · does 75\.0% \(±25\.0\) · \+1\.43u the BET band 1-1 [-−]0\.2u · the leans 2-0 \+1\.6u · unders 1-1 [-−]0\.2u · overs 2-0 \+1\.6u · the sixteen nights before it, replayed with the ledgers in place: every pick with an edge 523-402 corrected against 465-383 as the levers stood, the BET band 30-29 against 32-13 \(59 and 45 picks: too few to tell apart, so this tile keeps the count\)$/i.test(lvr.tiles[0])
      && /^picks under the levers as corrected on 13 Nov 2026: the BET band 1-1 [-−]0\.2u · the leans 2-0 \+1\.6u$/.test(lvr.sides)
      && lvr.kept === 'No Edge New:trim:lv2:role-role | Old Levers:trim | Plain New:trim:lv2:chg | Role Bench:trim:lv2:role-few:chg | Role Five:trim:lv2:role-role | Role Start:trim:lv2:role-flat:chg'
      && JSON.stringify(lvr.tilesAfter) === JSON.stringify(lvr.tiles),
      'the levers as corrected, the record: the four BET and LEAN picks the corrected run made, three won and one lost, sit on a tile of their own by band and by side with the sixteen replayed nights beside them (the old run\'s BET, a winner, is not counted, nor the man with no pick); and when seven later dates push the night out and its rows are trimmed the marks stay and the tile reads the same',
      JSON.stringify({ tiles: lvr.tiles, sides: lvr.sides, kept: lvr.kept, after: lvr.tilesAfter }));
  // ---- 12 Nov 2026: a call on every game (the user: "the model wont give 'green bet' ... it still need to be able to provide a bet on something because an outcome is
  //      going to happen"). One a game on the board, by this order: the agreement rule, a side the sheet prices below its chance, a total at one of the four apps a
  //      point or more off the middle of every book's number, else the likelier winner at the best of the four prices. Each kind keeps its own record, replayed from the
  //      rows, and a rule that has lost over ten or more calls is cold: left out of the order, named on the card, counted on its line. Shown, not scored ----
  const clKeep = await pg.evaluate(async () => { await smStore.ready; const k = {}; for (const x of ['callsheet3.card.v1', 'callsheet3.props.v1', 'callsheet3.draft.v1']) k[x] = await smStore.getItem(x); await smStore.removeItem('callsheet3.card.v1'); await smStore.removeItem('callsheet3.props.v1'); return k; });
  await reloaded();
  const cl = await pg.evaluate(async () => {
    const wait = (ms) => new Promise(r => setTimeout(r, ms || 90)), txt = e => (e ? e.innerText : '').replace(/\s+/g, ' ').trim();
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    await smStore.ready;
    const game = async (date, away, home, f) => { document.getElementById('clear').click(); document.getElementById('m-nba').click(); await wait(); set('gdate', date); set('away', away); set('home', home); set('line', '229.5'); set('op', '-110'); set('up', '-110');
      Object.keys(f).forEach(k => set(k, f[k])); await wait(); document.getElementById('add').click(); await wait(); };
    const rows = () => JSON.parse(smStore.getItem('callsheet3.card.v1')), rowOf = (date, away) => rows().find(x => x.gdate === date && x.away === away);
    const grade = async (date, away, fa, fh) => { const r = rowOf(date, away); for (const [k, v] of [['fa', fa], ['fh', fh]]) { const el = document.querySelector('#cardTable .grade[data-id="' + r.id + '"][data-k="' + k + '"]'); el.value = String(v); el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); } await wait(); };
    const board = async (d) => { const bd = document.getElementById('boardDate'); bd.value = d; bd.dispatchEvent(new Event('change')); await wait(140); return { hidden: document.getElementById('callsHead').hidden && document.getElementById('calls').hidden,
      cards: [...document.querySelectorAll('#calls .pk.call')].map(c => ({ cls: c.className, n1: txt(c.querySelector('.n1')), n2: txt(c.querySelector('.n2')), n3: txt(c.querySelector('.n3')), n4: txt(c.querySelector('.n4')), also: txt(c.querySelector('.n4.also')), take: !!c.querySelector('.takebtn'), btn: txt(c.querySelector('.n6')) })) }; };
    const taking = () => [...document.querySelectorAll('#taking .pk.taking')].map(e => txt(e));
    const table = () => { const t = document.querySelector('#calibBox .callstab'); return t ? [...t.querySelectorAll('tbody tr')].map(tr => [...tr.children].slice(0, 5).map(td => txt(td)).join(' | ')) : null; };
    const tot = (lines) => { const o = { OVER: [], UNDER: [] }; Object.keys(lines).forEach(b => { o.OVER.push([b, -110, lines[b]]); o.UNDER.push([b, -110, lines[b]]); }); return o; };
    const ml = (h, a) => { const o = { HOME: [], AWAY: [] }; Object.keys(h).forEach(b => { o.HOME.push([b, h[b], null]); o.AWAY.push([b, a[b], null]); }); return o; };
    const hist = (lo, mean, sd) => { const c = []; for (let v = lo; v <= lo + 100; v++) c.push(Math.round(10000 * Math.exp(-((v - mean) ** 2) / (2 * sd * sd)))); return { lo, c }; };
    const D = '2026-11-23', o = {};
    // A: a short dog the sheet prices below its chance. B: a total at FanDuel a point and a half over the middle of five books. C: a heavy favourite, the best of the four
    // prices at DraftKings, and the crowd's price dearer than that and cheaper than the row's own. D: a favourite at 63%, the carded book alone. E: the simulation and
    // the crew both under the total
    await game(D, 'Hornets', 'Bucks', { hml: '-120', aml: '100' });
    await game(D, 'Celtics', 'Lakers', { hml: '-600', aml: '440', odds: JSON.stringify({ book: 'fanatics', total: tot({ fanatics: 225.5, draftkings: 225.5, fanduel: 227, betmgm: 225.5, pinnacle: 225.5 }) }) });
    await game(D, 'Heat', 'Jazz', { hml: '-650', aml: '460', nbakalshi: JSON.stringify({ h: { bid: 0.84, ask: 0.85 }, a: { bid: 0.15, ask: 0.16 }, fee: 0.07 }), odds: JSON.stringify({ book: 'fanatics', total: tot({ fanatics: 229.5, draftkings: 229.5, fanduel: 230, betmgm: 229.5, pinnacle: 231.5 }),   // the sharp book two points off the middle is not one of the four apps: no number here
      ml: ml({ fanatics: -650, draftkings: -600, fanduel: -620, betmgm: -640, pinnacle: -610 }, { fanatics: 460, draftkings: 440, fanduel: 450, betmgm: 455, pinnacle: 470 }) }) });
    await game(D, 'Suns', 'Kings', { hml: '-190', aml: '160' });
    await game(D, 'Bulls', 'Pistons', { line: '232', hml: '-190', aml: '160', ncrew: 'Ref One, Ref Two, Ref Three', nbarefs: JSON.stringify({ lg: [2462, 44.0, 228.8], r: { 'Ref One': [70, 44, 228, 10, 30, 0, 0], 'Ref Two': [70, 44, 228, 12, 30, 0, 0], 'Ref Three': [70, 44, 228, 11, 30, 0, 0] } }),
      nbasim: JSON.stringify({ v: 1, runs: 1000, own: { total: hist(160, 215, 12), h1: hist(60, 108, 9), h2: hist(60, 108, 9), q: [hist(20, 54, 6), hist(20, 54, 6), hist(20, 54, 6), hist(20, 54, 6)], margin: hist(-50, 3, 12), away: hist(60, 106, 10), home: hist(60, 109, 10), ot: 0.04 }, mkt: null, anchor: null, ft_factor: 1,
        shrink: { total: 0.0, h1: 0.1, spread: 0.0, ml: 0.97, team: 0.3, team_away: 0.3, team_own: 0.3, quarter: 0.1 }, bands: [[0.7, 'STRONG'], [0.65, 'BET'], [0.6, 'LEAN']] }) });
    o.before = await board(D);
    o.noNba = (await board('2026-07-04')).hidden;
    // the Take on the number and on the winner (cards 3 and 4): the mark keeps the app, the line and the price its card shows, not the row's own
    await board(D);
    for (const i of [2, 3]) { document.querySelectorAll('#calls .pk.call')[i].querySelector('[data-stake]').click(); await wait(160); }
    const bare = (ts) => (ts || []).map(t => { const c = Object.assign({}, t); delete c.at; return c; });
    o.taken = { btns: (await board(D)).cards.map(c => c.btn), list: taking(), b: bare(rowOf(D, 'Celtics').simTakes), c: bare(rowOf(D, 'Heat').simTakes) };
    // the finals: the dog wins, 228 lands over FanDuel's 227 and under the row's own 229.5 (the call is graded at the app's number), the Jazz and the Lakers win at
    // home, the Kings lose, 241 lands over 232 with the Pistons winning (the rule's one call a loss: one loss does not make a kind cold)
    await grade(D, 'Hornets', 110, 100); await grade(D, 'Celtics', 108, 120); await grade(D, 'Heat', 100, 120); await grade(D, 'Suns', 115, 110); await grade(D, 'Bulls', 120, 121);
    o.after = await board(D); o.table = table();
    o.took = [...document.querySelectorAll('#calibBox .calib[data-sport="TAKEN"] > div')].map(d => txt(d));
    o.tookList = [...document.querySelectorAll('#takenList tbody tr')].map(e => e.textContent.replace(/\s+/g, ' ').trim());
    o.takingGraded = taking();
    // ten short dogs that lose on the days before: the sheet's own call goes cold, and the next short dog is given the lean with the cold call named
    for (let i = 1; i <= 10; i++) { const d = '2026-11-' + String(i).padStart(2, '0'); await game(d, 'Hornets', 'Bucks', { hml: '-120', aml: '100' }); await grade(d, 'Hornets', 100, 112); }
    await game('2026-11-24', 'Hornets', 'Bucks', { hml: '-120', aml: '100' });
    o.cold = await board('2026-11-24'); o.tableCold = table();
    // the ten wiped, the call is the sheet's own again
    const keep = rows().filter(x => !(x.gdate >= '2026-11-01' && x.gdate <= '2026-11-10'));
    // and a later odds run on the Jazz game: DraftKings out to -700, FanDuel the best of the four at -590. The card follows it; the mark does not
    const later = keep.find(x => x.gdate === D && x.away === 'Heat'); later.inputs.oddsNow = JSON.stringify({ book: 'fanatics', total: tot({ fanatics: 229.5, draftkings: 229.5, fanduel: 230, betmgm: 229.5, pinnacle: 231.5 }),
      ml: ml({ fanatics: -650, draftkings: -700, fanduel: -590, betmgm: -640, pinnacle: -610 }, { fanatics: 460, draftkings: 500, fanduel: 430, betmgm: 455, pinnacle: 470 }) });
    await smStore.setItem('callsheet3.card.v1', JSON.stringify(keep));
    return o;
  });
  await reloaded();
  const clBack = await pg.evaluate(async () => { const txt = e => (e ? e.innerText : '').replace(/\s+/g, ' ').trim(), wait = (ms) => new Promise(r => setTimeout(r, ms || 140)); await smStore.ready; document.getElementById('m-nba').click(); await wait();
    const bd = document.getElementById('boardDate'); bd.value = '2026-11-24'; bd.dispatchEvent(new Event('change')); await wait(); const back = [...document.querySelectorAll('#calls .pk.call')].map(c => txt(c.querySelector('.n1')) + ' :: ' + txt(c.querySelector('.n2')) + ' :: ' + (c.querySelector('.n4.also') ? 'also' : 'no also'));
    bd.value = '2026-11-23'; bd.dispatchEvent(new Event('change')); await wait();
    const jazz = [...document.querySelectorAll('#calls .pk.call')].filter(c => /Jazz to win/.test(txt(c.querySelector('.n2')))).map(c => txt(c.querySelector('.n3')) + ' [' + txt(c.querySelector('.n6')) + ']');
    return { back, jazz, taking: [...document.querySelectorAll('#taking .pk.taking')].map(e => txt(e)) }; });
  await pg.evaluate(async (k) => { for (const x of Object.keys(k)) { if (k[x] === null || k[x] === undefined) await smStore.removeItem(x); else await smStore.setItem(x, k[x]); } }, clKeep);
  await reloaded();
  const clc = (cards) => cards.map(c => c.cls.replace('pk call ', '') + ' | ' + c.n1.toUpperCase() + ' | ' + c.n2);
  chk(cl.before.hidden === false && cl.noNba === true && clc(cl.before.cards).join(' ## ') === "bet | BET · THE AGREEMENT RULE | Total UNDER 232 ## bet | BET · THE SHEET'S OWN CALL | Hornets ML ## value | VALUE · THE BEST NUMBER ON THE BOARD | Total UNDER 227 ## lean | LEAN · THE LIKELIER WINNER, 80% OR MORE | Jazz to win ## lean | LEAN · THE LIKELIER WINNER, 60 TO 70% | Kings to win"
      && /^2 of 3 voices · -110 needs 52\.4% · the rule's rate 59\.2%$/.test(cl.before.cards[0].n3) && /^Bulls @ Pistons · the simulation and the crew on the same side of the total, the sheet not against it: 157-108 \(59\.2%\) over two seasons of closes · none graded here yet$/.test(cl.before.cards[0].n4)
      && /^51\.8% by the sheet · \+100 needs 50\.0%$/.test(cl.before.cards[1].n3) && /^Hornets @ Bucks · a side the sheet prices below its chance, or one a verdict sits on · none graded here yet$/.test(cl.before.cards[1].n4)
      && cl.before.cards[2].n3 === '-110 at FanDuel · the middle of 5 books is 225.5: 1.5 points over it, on your side' && /^Celtics @ Lakers · a total at one of your four apps a point or more off the middle of every book's number: 105-84 \(55\.6%\) on last season's closes, 78-70 at the opener · none graded here yet$/.test(cl.before.cards[2].n4)
      && /^82\.8% by the middle of 5 books · -600 at DraftKings needs 85\.7% · costs 3\.4% a bet Kalshi 85¢ needs 85\.9% after the fee v -600 needing 85\.7%: the book · the crowd 84\.5%$/i.test(cl.before.cards[3].n3) && /^Heat @ Jazz · the book's price: such favourites at the best of the four prices went 231-31 last season, -0\.3% a bet · none graded here yet$/.test(cl.before.cards[3].n4)
      && /^63\.0% by the middle of the carded book · -190 needs 65\.5% · costs 3\.8% a bet$/.test(cl.before.cards[4].n3) && /^Suns @ Kings · the book's price: 230-134 last season at the best of the four prices, -6\.0% a bet · none graded here yet$/.test(cl.before.cards[4].n4)
      && cl.before.cards.map(c => c.take ? 'T' : '-').join('') === 'TTTTT' && cl.before.cards.every(c => c.also === ''),
      'a call on every game (12 Nov 2026): the board gives every basketball game one call and the section is away on a date with none; the agreement rule where the simulation and the crew sit on one side of the total, a side the sheet prices below its chance, a total at one of the four apps a point or more off the middle of every book\'s number with the app and how far, else the likelier winner at the best of the four apps\' prices (the carded book alone where the shop is thin) with what the price costs; the BETs first, then the value, then the leans, the likelier first; each card says what its kind was measured to be and how it has done here, and carries Take; the crowd\'s chip on a winner reads against the price on the card (85.9% after the fee is dearer than -600 at DraftKings, though cheaper than the -650 the row was logged with)',
      JSON.stringify({ hidden: cl.before.hidden, noNba: cl.noNba, cards: cl.before.cards }));
  chk(clc(cl.after.cards).join(' ## ') === "bet loss | BET · THE AGREEMENT RULE | Total UNDER 232 LOSS ## bet win | BET · THE SHEET'S OWN CALL | Hornets ML WIN ## value loss | VALUE · THE BEST NUMBER ON THE BOARD | Total UNDER 227 LOSS ## lean win | LEAN · THE LIKELIER WINNER, 80% OR MORE | Jazz to win WIN ## lean loss | LEAN · THE LIKELIER WINNER, 60 TO 70% | Kings to win LOSS"
      && cl.table && cl.table.join(' ## ') === "BET · the agreement rule | 0-1 | 59.2% | 0.0% | -1.0u ## BET · the sheet's own call | 1-0 | " + ((cl.table[1] || '').split(' | ')[2] || '') + " | 100.0% | +1.0u ## VALUE · the best number on the board | 0-1 |  | 0.0% | -1.0u ## LEAN · the likelier winner, 80% or more | 2-0 | " + ((cl.table[3] || '').split(' | ')[2] || '') + " | 100.0% | +0.3u ## LEAN · the likelier winner, 70 to 80% | none yet |  |  |  ## LEAN · the likelier winner, 60 to 70% | 1-1 | " + ((cl.table[5] || '').split(' | ')[2] || '') + " | 50.0% | -0.5u ## LEAN · the likelier winner, near a coin | 0-1 | " + ((cl.table[6] || '').split(' | ')[2] || '') + " | 0.0% | -1.0u ## The call as given, one a game | 2-3 |  | 40.0% | -1.8u"
      && /0-1 here, -1\.0u$/.test(cl.after.cards[0].n4) && /2-0 here, \+0\.3u$/.test(cl.after.cards[3].n4) && /1-1 here, -0\.5u$/.test(cl.after.cards[4].n4),
      'a call on every game, graded: each call is graded on its own line and side (the total at the app\'s number, where 228 loses the under at 227 though it sits under the row\'s 229.5; the winner on the final) and the cards carry the results; the NBA record keeps every kind on every game it speaks to (the likelier winner on all five, by how likely the market made him), and the call as the board gave it, one a game',
      JSON.stringify({ cards: clc(cl.after.cards), n4: cl.after.cards.map(c => c.n4.slice(-28)), table: cl.table }));
  chk(cl.cold.cards.length === 1 && cl.cold.cards[0].n1 === 'LEAN · the likelier winner, near a coin' && cl.cold.cards[0].n2 === 'Bucks to win' && /^52\.2% by the middle of the carded book · -120 needs 54\.5% · costs 4\.3% a bet$/.test(cl.cold.cards[0].n3)
      && /^Also on this game: the sheet's own call says Hornets ML \(1-10 here, -9\.0u: cold, and left out of the order until its record turns\)\.$/.test(cl.cold.cards[0].also)
      && /^BET · the sheet's own call · cold here \| 1-10 \| /.test((cl.tableCold || [])[1] || '') && /^BET · the agreement rule \| 0-1 \| /.test((cl.tableCold || [])[0] || '') && /^The call as given, one a game \| 11-4 \| /.test((cl.tableCold || [])[7] || '')
      && clBack.back.length === 1 && clBack.back[0] === "BET · the sheet's own call :: Hornets ML :: no also",
      'a call on every game, a kind gone cold: ten short dogs lose on the days before and the sheet\'s own call, 1-10, is cold: the next short dog is given the likelier winner, the card names the call that was left out and its record, the record marks the kind cold and counts the call as given by what the board would give now (the day the dog won reads the favourite, a loss); with the ten gone the same game is the sheet\'s call again',
      JSON.stringify({ cold: cl.cold.cards, table: cl.tableCold, back: clBack.back }));
  const clT = cl.taken || {}, clOne = (xs, re) => (xs || []).filter(x => re.test(x));
  chk(JSON.stringify(clT.btns) === JSON.stringify(['Take', 'Take', '✓ Taking', '✓ Taking', 'Take'].map(s => s)) || JSON.stringify((clT.btns || []).map(s => s.toUpperCase())) === JSON.stringify(['TAKE', 'TAKE', '✓ TAKING', '✓ TAKING', 'TAKE'])
      , 'a call on every game, taken: Take on the best number and on the likelier winner turns to Taking on those two cards and no other',
      JSON.stringify(clT.btns));
  chk(JSON.stringify(clT.b) === JSON.stringify([{ id: 'call|total|UNDER', view: 'call', key: 'total', side: 'UNDER', line: 227, price: -110, p: null, worth: null, band: 'value', pick: 'Total UNDER 227 at FanDuel', book: 'fanduel', call: 'number' }])
      && JSON.stringify(clT.c) === JSON.stringify([{ id: 'call|ml|HOME', view: 'call', key: 'ml', side: 'HOME', line: null, price: -600, p: 0.8276, worth: null, band: 'lean', pick: 'Jazz ML at DraftKings', book: 'draftkings', call: 'winner' }])
      && (clT.list || []).length === 3
      && clOne(clT.list, /^TAKING · NBA · A CALL ON THE GAME · marked .+ Total UNDER 227 at FanDuel value · the best number on the board · -110 needs 52\.4% Celtics @ Lakers · a call on the game ✓ Taking$/i).length === 1
      && clOne(clT.list, /^TAKING · NBA · A CALL ON THE GAME · marked .+ Jazz ML at DraftKings lean · 82\.8% by the books' middle · -600 needs 85\.7% Heat @ Jazz · a call on the game ✓ Taking$/i).length === 1
      && /^TONIGHT 2 bets marked none graded yet · one unit each 0 on the card, 0 from the simulation, 2 calls on the game, 0 props$/i.test(clT.list[2])
      && clOne(cl.took, /^Calls on the game taken 1-1 says 66\.4% · does 50\.0% \(±35\.4\) · [-−]0\.83u$/i).length === 1 && clOne(cl.took, /^Simulation calls taken/i).length === 0 && clOne(cl.took, /^Game bets taken/i).length === 0
      && clOne(cl.tookList, /Jazz ML at DraftKings · Heat @ Jazzgame call82\.8%[-−]600WIN\+0\.17u$/).length === 1 && clOne(cl.tookList, /Total UNDER 227 at FanDuel · Celtics @ Lakersgame call50\.0%[-−]110LOSS[-−]1\.00u$/).length === 1
      && clOne(cl.takingGraded, /Total UNDER 227 at FanDuel .*-110 needs 52\.4% · loss Celtics @ Lakers/i).length === 1 && clOne(cl.takingGraded, /Jazz ML at DraftKings .*-600 needs 85\.7% · win Heat @ Jazz/i).length === 1
      && clOne(cl.takingGraded, /^TONIGHT 2 bets marked graded 1-1 · [-−]0\.83u at one unit each/i).length === 1
      && (clBack.jazz || []).length === 1 && /^82\.9% by the middle of 5 books · -590 at FanDuel needs 85\.5% · costs \d\.\d% a bet Kalshi 85¢ needs 85\.9% after the fee v -590 needing 85\.5%: the book · the crowd 84\.5% \[TAKEN\]$/i.test(clBack.jazz[0])
      && clOne(clBack.taking, /Jazz ML at DraftKings lean · 82\.8% by the books' middle · -600 needs 85\.7% · win Heat @ Jazz · a call on the game/i).length === 1,
      'a call on every game, the mark keeps the bet: the number is kept at the app\'s line and price (UNDER 227 at FanDuel, not the row\'s 229.5) and the winner at the app and price on the card (-600 at DraftKings, not the -650 the row was logged with), with the chance by the books\' middle; they list under Taking as calls on the game and are counted apart from the simulation\'s; graded, each on its own line (228 loses the under at 227), they sit on their own tile of What you took and in the list of every pick as game calls; and after a later odds run moves the best price to another app the card follows it and the mark does not',
      JSON.stringify({ b: clT.b, c: clT.c, list: clT.list, took: cl.took, tookList: (cl.tookList || []).slice(0, 4), graded: cl.takingGraded, jazz: clBack.jazz, backTaking: clBack.taking }));

  // ---- 11 Nov 2026: the NBA record counts the sheet's calls (the user: "fix the NBA record so tiles count only real calls") -- a market where neither side is priced below its chance is the book's own number, listed under the tile as no call and left out of its count ----
  const callsKeep = await pg.evaluate(async () => { await smStore.ready; const k = { card: await smStore.getItem('callsheet3.card.v1'), slate: await smStore.getItem('callsheet3.slate.v1') }; await smStore.removeItem('callsheet3.card.v1'); return k; });
  await reloaded();
  const callsT = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 90));
    const txt = e => (e ? e.innerText : '').replace(/\s+/g, ' ').trim();
    await smStore.ready;
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    const load = async (doc, name) => { const dt = new DataTransfer(); dt.items.add(new File([JSON.stringify(doc)], name, { type: 'application/json' })); const inp = document.getElementById('slateFile'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true })); await wait(); await wait(); };
    document.getElementById('clear').click(); document.getElementById('m-nba').click(); await wait();
    const game = async (away, home, line, op, up, hml, aml, sp, h1) => { document.getElementById('clear').click(); await wait(); set('gdate', '2026-11-22'); set('away', away); set('home', home); set('line', line); set('op', op); set('up', up); set('hml', hml); set('aml', aml);
      set('sp', sp); set('sph', sp ? '-110' : ''); set('spa', sp ? '-110' : ''); set('h1line', h1); set('h1op', '-110'); set('h1up', '-110'); await wait(); document.getElementById('add').click(); await wait(); };
    await game('Hornets', 'Bucks', '229.5', '-110', '-110', '-120', '100', '', '114.5');          // a short dog priced below its lifted chance: a moneyline call; no spread on the row
    await game('Pistons', 'Celtics', '224', '-110', '-110', '-300', '240', '-7.5', '111.5');      // a long dog, the closer of two sides neither priced below its chance: nobody's call
    await game('Jazz', 'Suns', '223.5', '-210', '160', '-150', '130', '-3.5', '110.5');           // the under at a price a hair below its chance: a call on the total; a short dog lifted but not below its price: no call
    const stored = JSON.parse(smStore.getItem('callsheet3.card.v1')).map(r => r.matchup + ' :: ' + r.markets.map(m => m.key + ' ' + m.pick + ' e' + (m.edge === null ? 'null' : (m.edge > 0 ? '+' : '-')) + (m.informed ? ' informed' : '')).join(' | '));
    await load({ format: 'callsheet2.slate', version: 1, date: '2026-11-22', games: [
      { sport: 'NBA', gdate: '2026-11-22', away: 'Hornets', home: 'Bucks', finals: { fa: '118', fh: '110', f5a: '60', f5h: '55' }, notes: [] },
      { sport: 'NBA', gdate: '2026-11-22', away: 'Pistons', home: 'Celtics', finals: { fa: '100', fh: '120', f5a: '48', f5h: '62' }, notes: [] },
      { sport: 'NBA', gdate: '2026-11-22', away: 'Jazz', home: 'Suns', finals: { fa: '100', fh: '110', f5a: '52', f5h: '54' }, notes: [] }] }, 'nba-grade-2026-11-22.json');
    const head = txt(document.querySelector('#calibBox .subhead[data-sport="NBA"]'));
    const tiles = [...document.querySelectorAll('#calibBox .calib[data-sport="NBA"] > div')].map(d => [d.className, txt(d.querySelector('.k')), txt(d.querySelector('.v')), txt(d.querySelector('.s')), txt(d.querySelector('.s.sides'))].join(' | '));
    const verdict = txt([...document.querySelectorAll('#calibBox .verdict')].find(v => /graded NBA call/.test(v.textContent)));
    const others = txt(document.querySelector('#calibBox .subhead[data-sport="MLB"]')) + ' / ' + txt(document.querySelector('#calibBox .subhead[data-sport="WNBA"]'));
    document.getElementById('clear').click(); await wait();
    return { stored, head, tiles, verdict, others };
  });
  await pg.evaluate(async (k) => { if (k.card === null || k.card === undefined) await smStore.removeItem('callsheet3.card.v1'); else await smStore.setItem('callsheet3.card.v1', k.card); if (k.slate === null || k.slate === undefined) await smStore.removeItem('callsheet3.slate.v1'); else await smStore.setItem('callsheet3.slate.v1', k.slate); }, callsKeep);
  await reloaded();
  const callsTile = (re) => callsT.tiles.find(t => re.test(t)) || '';
  chk(/^Hornets @ Bucks :: total OVER 229\.5 e- \| h1 1H OVER 114\.5 e- \| ml Hornets ML e\+ informed$/.test(callsT.stored[0]) && / \| ml Pistons ML e- \| spread Celtics -7\.5 e-$/.test(callsT.stored[1])
      && /^Jazz @ Suns :: total UNDER 223\.5 e\+ \| h1 1H OVER 110\.5 e- \| ml Jazz ML e- informed \| spread Suns -3\.5 e-$/.test(callsT.stored[2])
      && /^NBA 3 graded games · 2 calls graded, the rest the book's own number$/i.test(callsT.head)
      && /^ \| Full-game total · calls \| 1-0 \| says 38\.9% · does 100\.0% \(±0\.0\) · \+1\.60u \| under 1-0 · no call on 2 games, the book's own number: the closer side 0-2, not counted$/i.test(callsTile(/Full-game total/i))
      && /^ \| Moneyline · calls \| 1-0 \| says 51\.8% · does 100\.0% \(±0\.0\) · \+1\.00u \| away 1-0 · the short dog 1-1 · no call on 2 games, the book's own number: the closer side 0-2, not counted$/i.test(callsTile(/Moneyline/i)),
      'nba record, calls only (11 Nov 2026): three graded games, and the tiles count the two calls the sheet made (the under priced a hair below its chance, the short dog priced below its lifted chance); the two totals and the two moneylines that were only the closer of two sides are listed under the tile as no call with their own record and left out of the count; the short dog\'s own line still reads every lifted dog',
      JSON.stringify({ stored: callsT.stored, head: callsT.head, total: callsTile(/Full-game total/i), ml: callsTile(/Moneyline/i) }));
  chk(/^nocall \| First half · calls \| no call \| no side priced below its chance yet \| no call on 3 games, the book's own number: the closer side 1-2, not counted$/i.test(callsTile(/First half/i))
      && /^nocall \| Spread · calls \| no call \| no side priced below its chance yet \| no call on 2 games, the book's own number: the closer side 2-0, not counted$/i.test(callsTile(/Spread/i))
      && /^2 graded NBA calls\. Nothing here can be read yet/.test(callsT.verdict) && /A call is a side the sheet prices below its chance, or one a verdict sits on\. Where neither side is, the market is the book's own number: it is listed under the tile as no call and left out of the tile's count/.test(callsT.verdict)
      && /The watches under a tile read every game\.$/.test(callsT.verdict) && /^MLB nothing graded yet \/ WNBA nothing graded yet$/i.test(callsT.others),
      'nba record, calls only: a market the sheet has not called says no call in place of a record (the first half and the spread, the book\'s own number on every game) with the closer side\'s record beside it for scale; the verdict says what a call is; the other sports\' blocks are untouched',
      JSON.stringify({ h1: callsTile(/First half/i), spread: callsTile(/Spread/i), verdict: callsT.verdict.slice(0, 80) + ' … ' + callsT.verdict.slice(-330), others: callsT.others }));

  // ---- 4 Nov 2026: the crowd on Kalshi -- the exchange's game-winner prices on the row, the card beside the book and Pinnacle, the better price after the fee on the board, the sharp side against the crowd on the moneyline tile ----
  const kalT = await pg.evaluate(async () => {
    const wait = () => new Promise(r => setTimeout(r, 120));
    const txt = e => (e ? e.innerText : '').replace(/\s+/g, ' ').trim();
    const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    const load = async (doc, fname) => { const dt = new DataTransfer(); dt.items.add(new File([JSON.stringify(doc)], fname, { type: 'application/json' })); const inp = document.getElementById('slateFile'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true })); await wait(); };
    await smStore.removeItem('callsheet3.card.v1'); document.getElementById('clear').click(); document.getElementById('m-nba').click(); await wait();
    const empty = txt(document.getElementById('nbaKalshiPanel'));
    // the game winner a side, and the ladders (the Hawks by 2.75 at even money: 51% to win by 2.5 and 47% by 3.5; the total 232.25)
    const rung = (x, mid, vol) => [x, +(mid - 0.01).toFixed(2), +(mid + 0.01).toFixed(2), +mid.toFixed(2), vol];
    const kal = { at: '2026-11-14T20:00:00Z', ev: 'KXNBAGAME-26NOV14ATLWAS', fee: 0.07, a: { bid: 0.57, ask: 0.58, last: 0.58, vol: 149511, oi: 136925 }, h: { bid: 0.42, ask: 0.43, last: 0.43, vol: 140051, oi: 115254 },
      sp: { a: [rung(1.5, 0.56, 900), rung(2.5, 0.51, 1200), rung(3.5, 0.47, 800), rung(4.5, 0.41, 500), rung(6.5, 0.33, 60)], h: [rung(1.5, 0.33, 40), rung(3.5, 0.25, 0)] },
      tot: [rung(230.5, 0.57, 1500), rung(232.5, 0.49, 8000), rung(234.5, 0.41, 300)],
      // the team totals (the Hawks 117.5 and the Wizards 114.1 at even money); the book's Hawks line 118.5 is a rung, its Wizards line 113.5 sits between two
      tt: { a: [rung(116.5, 0.55, 400), rung(118.5, 0.45, 600)], h: [rung(112.5, 0.58, 300), rung(114.5, 0.48, 700)] } };
    const pin = JSON.stringify({ book: 'pinnacle', line: 232.5, op: -108, up: -108, hml: 150, aml: -170 });
    set('gdate', '2026-11-14'); set('away', 'Hawks'); set('home', 'Wizards'); set('line', '232.5'); set('op', '-110'); set('up', '-110'); set('hml', '140'); set('aml', '-165'); set('sp', '2.5'); set('sph', '-110'); set('spa', '-110');
    set('odds', JSON.stringify({ book: 'fanatics', team: { AWAY: { OVER: [['fanatics', -110, 118.5]], UNDER: [['fanatics', -110, 118.5]] }, HOME: { OVER: [['fanatics', -115, 113.5]], UNDER: [['fanatics', -105, 113.5]] } } }));
    set('sharp', pin); set('nbakalshi', JSON.stringify(kal)); await wait();
    const panel = txt(document.getElementById('nbaKalshiPanel'));
    set('line', '231.5'); await wait(); const between = txt(document.getElementById('nbaKalshiPanel')); set('line', '232.5'); await wait();
    set('sharp', ''); await wait(); const noPin = txt(document.getElementById('nbaKalshiPanel'));
    set('sharp', pin); await wait();
    // with the simulation on the row (the Hawks' mean 117, the Wizards' 115): the card adds its mean and its chance at the book's line, the sim's table carries the crowd under its team-total rows
    const hist = (lo, mean, sd) => { const c = []; for (let v = lo; v <= lo + 100; v++) c.push(Math.round(10000 * Math.exp(-((v - mean) ** 2) / (2 * sd * sd)))); return { lo, c }; };
    set('nbasim', JSON.stringify({ v: 1, runs: 1000, own: { total: hist(170, 232, 15), h1: hist(80, 116, 10), h2: hist(80, 116, 10), q: [hist(30, 58, 7), hist(30, 58, 7), hist(30, 58, 7), hist(30, 58, 7)], margin: hist(-50, -3, 12), away: hist(80, 117, 11), home: hist(80, 115, 11), ot: 0.04 }, mkt: null, anchor: null, ft_factor: 1.0,
                                   shrink: { total: 0.05, h1: 0.1, spread: 0.0, ml: 0.97, team: 1.5, team_away: 0.3, team_own: 0.3, quarter: 0.1 }, bands: [[0.7, 'STRONG'], [0.65, 'BET'], [0.6, 'LEAN']] })); await wait();
    const withSim = txt(document.getElementById('nbaKalshiPanel'));
    const simTT = [...document.querySelectorAll('#nbaSimPanel .simtab td')].map(td => txt(td)).filter(s => /team total/i.test(s));
    // tonight's signals on the rail (4 Nov 2026): the gap's two sides (a watch from 11 Nov 2026), the crowd's sharp side and numbers; the jump bar's dots and the live lines read off the same list
    const signals = txt(document.getElementById('signals')), simLive = txt(document.getElementById('secSimLive')), kalLive = txt(document.getElementById('secKalshiLive'));
    const dots = [...document.querySelectorAll('#nbaNav a[data-go]')].map(a => a.dataset.go + ':' + ((a.querySelector('.dot') || {}).className || ''));
    const folded = { about: [...document.querySelectorAll('#nbaFields details.about')].length, aboutOpen: [...document.querySelectorAll('#nbaFields details.about[open]')].length, rail: !!document.querySelector('#markets + details.about, .rail details.about'), notes: [...document.querySelectorAll('#markets details.mknotes')].length };
    set('nbasim', ''); await wait();
    document.getElementById('add').click(); await wait();
    document.getElementById('boardDate').value = '2026-11-14'; document.getElementById('boardDate').dispatchEvent(new Event('change')); await wait();
    const chips = [...document.querySelectorAll('.pk:not(.call)')].filter(e => /Hawks ML|Wizards ML/.test(e.textContent)).map(e => txt(e.querySelector('.n4')));   // the board's own moneyline cards; the calls section (12 Nov 2026) has its own check
    const row = JSON.parse(smStore.getItem('callsheet3.card.v1')).find(r => /Hawks @ Wizards/.test(r.matchup)), stored = !!((row.inputs || {}).nbakalshi);
    // graded: the sharp side (the Hawks, Pinnacle's 61.2% against the crowd's 57.5%) wins, and the moneyline tile keeps the line
    await load({ format: 'callsheet2.slate', version: 1, date: '2026-11-14', games: [{ sport: 'NBA', gdate: '2026-11-14', away: 'Hawks', home: 'Wizards', finals: { fa: '118', fh: '110', f5a: '60', f5h: '55' }, close: { ctot: '232.5' }, notes: [] }] }, 'nba-grade-2026-11-14.json');
    const mlTile = txt([...document.querySelectorAll('#calibBox .calib[data-sport="NBA"] > div')].find(d => /^MONEYLINE/i.test(txt(d))));
    // the loader: a bare row takes the block from a slate, and a newer slate's block replaces it
    document.getElementById('clear').click(); await wait();
    set('gdate', '2026-11-15'); set('away', 'Kings'); set('home', 'Spurs'); set('line', '222.5'); set('op', '-110'); set('up', '-110'); await wait(); document.getElementById('add').click(); await wait();
    await load({ format: 'callsheet2.slate', version: 1, date: '2026-11-15', games: [{ sport: 'NBA', gdate: '2026-11-15', away: 'Kings', home: 'Spurs', notes: [], inputs: { nbakalshi: JSON.stringify(Object.assign({}, kal, { ev: 'KXNBAGAME-26NOV15SACSAS' })) } }] }, 'nba-slate-2026-11-15.json');
    const first = ((JSON.parse(smStore.getItem('callsheet3.card.v1')).find(r => /Kings @ Spurs/.test(r.matchup)) || { inputs: {} }).inputs.nbakalshi || '');
    await load({ format: 'callsheet2.slate', version: 1, date: '2026-11-15', games: [{ sport: 'NBA', gdate: '2026-11-15', away: 'Kings', home: 'Spurs', notes: [], inputs: { nbakalshi: JSON.stringify(Object.assign({}, kal, { ev: 'KXNBAGAME-26NOV15SACSAS', a: { bid: 0.60, ask: 0.61, last: 0.61, vol: 5000, oi: 4000 } })) } }] }, 'nba-slate-2026-11-15b.json');
    const second = ((JSON.parse(smStore.getItem('callsheet3.card.v1')).find(r => /Kings @ Spurs/.test(r.matchup)) || { inputs: {} }).inputs.nbakalshi || '');
    document.getElementById('clear').click(); await wait(); await smStore.removeItem('callsheet3.card.v1');
    return { empty, panel, noPin, chips, stored, mlTile, first: first.slice(0, 60), second: second.indexOf('"bid":0.6') >= 0, between, withSim, simTT, signals, simLive, kalLive, dots, folded };
  });
  chk(/gap watch:? ?Hawks team total UNDER 118\.5 · gap \+1 · not scored/i.test(kalT.signals) && /gap watch:? ?Wizards team total OVER 113\.5 · gap -1\.5 · not scored/i.test(kalT.signals) && !/gap rule/i.test(kalT.signals)
      && /Kalshi:? ?the sharp side Hawks · the crowd 3\.7 points over Pinnacle on the Wizards/i.test(kalT.signals)
      && /the crowd:? ?Hawks to win 57\.5% · spread Hawks [-−]2\.8 · total 232\.3\b/i.test(kalT.signals)
      && /Kalshi team total:? ?Hawks 117\.5 · the book 118\.5 · leans UNDER, the over 45\.0% at the book's number/i.test(kalT.signals)
      && /Kalshi team total:? ?Wizards 114\.1 · the book 113\.5 · sits with the book, the over 53\.0% at the book's number/i.test(kalT.signals)
      && /gap watch: Hawks team total UNDER 118\.5 · gap \+1 · not scored · gap watch: Wizards team total OVER 113\.5 · gap -1\.5 · not scored/.test(kalT.simLive) && /^Kalshi: the sharp side Hawks/.test(kalT.kalLive)
      && kalT.dots.indexOf('secSim:dot watch') >= 0 && kalT.dots.indexOf('secSim:dot go') < 0 && kalT.dots.indexOf('secKalshi:dot crowd') >= 0 && kalT.dots.indexOf('secMid:dot') >= 0 && kalT.dots.indexOf('boardDate:') >= 0
      && kalT.folded.about === 7 && kalT.folded.aboutOpen === 0 && kalT.folded.rail && kalT.folded.notes >= 3,
      'signals: the matchup rail opens with tonight\'s signals, every engine\'s call on the row as a chip that links to its section (the gap\'s two sides gold, a watch from 11 Nov 2026 and green before it, the crowd\'s sharp side and its numbers in the exchange\'s colour, each club\'s team total as a chip of its own against the book\'s line with the side the crowd leans to); the jump bar\'s dots and the sections\' live lines read off the same list, and the explanations fold under a line on the rail, on every NBA section and under each market row',
      JSON.stringify({ signals: kalT.signals.slice(0, 900), simLive: kalT.simLive, kalLive: kalT.kalLive, dots: kalT.dots, folded: kalT.folded }));
  chk(/The spread: the crowd Hawks [-−]2\.8 · the book Hawks [-−]2\.5\. At the book's number: Wizards covers 49\.0% by the crowd, \d+\.\d% by the sheet · Wizards \+2\.5 49\.0% by the crowd, better on Kalshi: 50¢ needs 51\.[78]% after the fee against [-−]110 needing 52\.4% · Hawks [-−]2\.5 51\.0% by the crowd, the book's price: 52¢ needs 53\.7% after the fee against [-−]110 needing 52\.4%\./.test(kalT.panel)
      && /The total: the crowd 232\.3 · the book 232\.5 · Pinnacle 232\.5\. At the book's 232\.5: the over 49\.0% by the crowd, \d+\.\d% by the sheet · over 232\.5 49\.0% by the crowd, better on Kalshi: 50¢ needs 51\.[78]% after the fee against [-−]110 needing 52\.4% · under 232\.5 51\.0% by the crowd, the book's price: 52¢ needs 53\.7% after the fee against [-−]110 needing 52\.4%\./.test(kalT.panel)
      && /At the book's 231\.5: the over 53\.0% by the crowd, \d+\.\d% by the sheet · no rung at the book's number on the exchange \(its ladder runs two points apart\), so no price to compare\./.test(kalT.between),
      'kalshi ladders: the card reads the crowd\'s spread and total at even money off the ladders (the Hawks by 2.8, the total 232.3), the chance of each side at the book\'s number read straight between rungs with the sheet\'s beside it, and when the number is a rung the price of each side after the fee against the book\'s (the no side one less the yes bid); a number between rungs gets the chance and no price',
      JSON.stringify({ panel: kalT.panel.slice(500, 1500), between: kalT.between.slice(900, 1300) }));
  chk(/The Hawks team total: the crowd 117\.5 · the book 118\.5 \(fanatics [-−]110\/[-−]110\) · implied by the book's total and spread 117\.5\. At the book's 118\.5: the over 45\.0% by the crowd · over 118\.5 45\.0% by the crowd, better on Kalshi: 46¢ needs 47\.7% after the fee against [-−]110 needing 52\.4% · under 118\.5 55\.0% by the crowd, the book's price: 56¢ needs 57\.7% after the fee against [-−]110 needing 52\.4%\./.test(kalT.panel)
      && /The Wizards team total: the crowd 114\.1 · the book 113\.5 \(fanatics [-−]115\/[-−]105\) · implied by the book's total and spread 115\.0\. At the book's 113\.5: the over 53\.0% by the crowd · no rung at the book's number on the exchange, so no price to compare\./.test(kalT.panel),
      'kalshi team totals: the card reads each club\'s team total at even money off its ladder (the Hawks 117.5, the Wizards 114.1) beside the book\'s line and the number the book\'s total and spread imply, the crowd\'s chance of the over at the book\'s line, and on a rung each side\'s price after the fee against the book\'s (the Hawks over 118.5 at 46¢ better than -110); a line between rungs gets the chance and no price',
      JSON.stringify({ panel: kalT.panel.slice(1400, 2400) }));
  chk(/the simulation's own view 117\.0\. At the book's 118\.5: the over 45\.0% by the crowd, 4\d\.\d% by the simulation's own view/.test(kalT.withSim)
      && kalT.simTT.length === 2 && /Kalshi: the crowd 45\.0% over at 118\.5 · over 46¢ needs 47\.7% after the fee, better than [-−]110 needing 52\.4% · under 56¢ needs 57\.7% after the fee, not better than [-−]110 needing 52\.4%/.test(kalT.simTT[0])
      && /Kalshi: the crowd 53\.0% over at 113\.5 · no rung at the line, so no price/.test(kalT.simTT[1]),
      'kalshi team totals: with the simulation on the row the card adds its mean and its chance at the book\'s line, and the simulation\'s table carries the crowd\'s read under each team-total row beside the gap',
      JSON.stringify({ withSim: kalT.withSim.slice(1400, 2400), simTT: kalT.simTT }));
  chk(/^No Kalshi price on the row/.test(kalT.empty)
      && /^The crowd on Kalshi · as the run read it, Nov 14, \d{1,2}:\d\d [AP]M Hawks 57\.5¢ \(bid 57¢ \/ ask 58¢ · 150k contracts\): the crowd 57\.5% · the book 59\.9% \([-−]165\) · Pinnacle 61\.2% · better on Kalshi: 58¢ needs 59\.7% after the fee against [-−]165 needing 62\.3% Wizards 42\.5¢ \(bid 42¢ \/ ask 43¢ · 140k contracts\): the crowd 42\.5% · the book 40\.1% \(\+140\) · Pinnacle 38\.8% · the book's price: 43¢ needs 44\.7% after the fee against \+140 needing 41\.7% The spread:/.test(kalT.panel)
      && /The crowd sits 3\.7 points above Pinnacle on the Wizards: the sharp side is the Hawks\./.test(kalT.panel)
      && /No Pinnacle moneyline on the row to set the crowd against/.test(kalT.noPin) && !/sharp side/.test(kalT.noPin),
      'kalshi: the form\'s card reads each side three ways (the crowd\'s no-vig price, the book\'s devigged moneyline, Pinnacle\'s) with the bid, the ask and the contracts, says which price is better after the 7% fee on the win (the Hawks at 58¢ needing 59.7% against -165 needing 62.3%), and names the sharp side when the crowd sits three points from Pinnacle; without Pinnacle it says so',
      JSON.stringify({ empty: kalT.empty, panel: kalT.panel.slice(0, 520), noPin: kalT.noPin.slice(0, 200) }));
  chk(kalT.stored && kalT.chips.length >= 2 && /better on Kalshi: 58¢ needs 59\.7% after the fee v [-−]165 needing 62\.3% · the crowd 57\.5%/i.test(kalT.chips[0]) && /Kalshi 43¢ needs 44\.7% after the fee v \+140 needing 41\.7%: the book · the crowd 42\.5%/i.test(kalT.chips[1])
      && /the sharp side against Kalshi's crowd, 3\+ points 1-0/.test(kalT.mlTile) && /^\{"at":"2026-11-14T20:00:00Z","ev":"KXNBAGAME-26NOV15SACSAS",/.test(kalT.first) && kalT.second,
      'kalshi: Add carries the block on the row, the board\'s moneyline cards carry the exchange\'s price for their side against the book\'s after the fee, the moneyline tile keeps the sharp side against the crowd once the game grades (the Hawks, 1-0), and a slate fills a bare row\'s block and a newer slate replaces it',
      JSON.stringify({ stored: kalT.stored, chips: kalT.chips, tile: kalT.mlTile, first: kalT.first, second: kalT.second }));

  const git = (cmd) => execSync(cmd, { cwd: __dirname, encoding: 'utf8' }).trim();
  let want, why;
  try {
    if (git('git status --porcelain -- web/callsheet3.html web/nba.engine.js web/callsheet3.nba-fields.html tools_build_callsheet3.py')) { want = git('date +%Y-%m-%d'); why = 'edited and not committed, so today'; }
    else { want = git('git log -1 --format=%cs -- web/callsheet3.html'); why = 'committed, so the commit date'; }
  } catch (e) { want = stamp; why = 'no git here'; }
  chk(stamp === want, `build: the stamp is current (${why})`, `page says ${stamp}, expected ${want}`);

  if (errs.length) { console.log('PAGE ERRORS:\n' + errs.join('\n')); fails++; }
  console.log(fails ? `\n${fails} FAILED` : `\nall checks passed (${CASES.length} cases)`);
  await b.close();
  process.exit(fails ? 1 : 0);
})();
