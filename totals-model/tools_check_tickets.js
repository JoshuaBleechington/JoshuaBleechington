// Is the page finding the best tickets? (11 Nov 2026, the user: "thoroughly test multiple times to make sure the algorithm
// is finding the best pairs.") An oracle written apart from the page's code: random nights of props, every valid ticket
// enumerated by brute force (every pair or three of qualifying legs at every app), and at each step the page's ticket must
// be a valid one and worth exactly what the best one left is worth, two legs and three, either side, the overs, the unders.
//
//   node tools_check_tickets.js [nights=200] [seed=1] [dense|v]
//
// "dense" makes busy nights (four to eight games, four to nine men a game, most legs qualifying: a thousand valid tickets
// on the median list). The page harness (tools_check_callsheet3_page.js) runs a short seeded sample of both on every build.
// The leg's rule is written here a second time, from the words the user was given, not from the page's code: an edge on the
// card and at the app's price, four of his last five and half of his last ten (eight or more) the pick's way, more measured
// levers toward the pick than against, and the over on a favourite's man out. The app's line is the carded one on these
// nights, so the chance at an app is the card's; a line that differs by app is covered by the replay on the real nights.
const APPS = ['fanatics', 'draftkings', 'fanduel', 'betmgm'], APPNAME = { fanatics: 'Fanatics', draftkings: 'DraftKings', fanduel: 'FanDuel', betmgm: 'BetMGM' };
const LABEL = { pts: 'points', reb: 'rebounds', ast: 'assists', tpm: 'threes', pra: 'pts + reb + ast', pr: 'pts + reb', pa: 'pts + ast', ra: 'reb + ast' };
const rng = (seed) => () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
const implied = (a) => a < 0 ? -a / (-a + 100) : 100 / (a + 100), dec = (a) => a > 0 ? 1 + a / 100 : 1 + 100 / Math.abs(a);
const TEAMS = ['ATL', 'BOS', 'BKN', 'CHA', 'CHI', 'CLE', 'DAL', 'DEN', 'DET', 'GSW', 'HOU', 'IND', 'LAC', 'LAL', 'MEM', 'MIA'];
const CLUBS = ['Hawks', 'Celtics', 'Nets', 'Hornets', 'Bulls', 'Cavaliers', 'Mavericks', 'Nuggets', 'Pistons', 'Warriors', 'Rockets', 'Pacers', 'Clippers', 'Lakers', 'Grizzlies', 'Heat'];
function night(seed, date, DENSE) {   // a random night: games, men, markets, lines, chances, each app's prices, logs, levers, spreads
  const R = rng(seed), ri = (a, b) => a + Math.floor(R() * (b - a + 1)), pick = (xs) => xs[Math.floor(R() * xs.length)];
  const nG = DENSE ? ri(4, 8) : ri(1, 7), games = [], men = [];
  for (let g = 0; g < nG; g++) {
    const spread = pick([-9.5, -6.5, -4.5, -2.5, -1.5, 1.5, 3.5, 5.5, 8.5]);   // the home side's spread: negative, the home club favoured
    games.push({ gi: g, away: CLUBS[2 * g], home: CLUBS[2 * g + 1], aab: TEAMS[2 * g], hab: TEAMS[2 * g + 1], spread });
    const nM = DENSE ? ri(4, 9) : ri(1, 6);
    for (let m = 0; m < nM; m++) {
      const pid = String(1000 + g * 10 + m), home = R() < 0.5, team = home ? TEAMS[2 * g + 1] : TEAMS[2 * g], name = 'Man ' + pid;
      const mks = R() < 0.3 ? ['pts', 'reb'] : [pick(['pts', 'reb', 'ast', 'tpm', 'pra', 'pr', 'pa', 'ra'])];
      for (const mk of mks) {
        const side = R() < 0.5 ? 'OVER' : 'UNDER', line = ri(2, 30) + 0.5, chance = Math.round(((DENSE ? 0.56 : 0.5) + R() * (DENSE ? 0.16 : 0.2)) * 10000) / 10000;
        const books = {}; APPS.forEach(a => { if (R() < (DENSE ? 0.9 : 0.75)) { const pr = pick([-150, -140, -130, -125, -120, -115, -110, -105, 100, 105, 110, 120]); const other = pick([-140, -125, -115, -110, 100, 110]); books[a] = side === 'OVER' ? [line, pr, other] : [line, other, pr]; } });
        const apps = Object.keys(books); if (!apps.length) continue;
        const book = pick(apps), price = side === 'OVER' ? books[book][1] : books[book][2], need = Math.round(implied(price) * 10000) / 10000, edge = Math.round((chance - need) * 10000) / 10000;
        const kind = R();   // his last ten: mostly the pick's way, some cold, some short
        const n = kind < (DENSE ? 0.04 : 0.12) ? ri(5, 7) : 10, pHit = kind < (DENSE ? 0.1 : 0.3) ? 0.45 : (DENSE ? 0.92 : 0.8);
        const vals = []; for (let i = 0; i < n; i++) { const hit = R() < pHit; vals.push(side === 'OVER' ? (hit ? line + ri(1, 6) - 0.5 : line - ri(1, 6) + 0.5) : (hit ? line - ri(1, 6) + 0.5 : line + ri(1, 6) - 0.5)); }
        const lv = R(), sgn = side === 'OVER' ? 1 : -1;   // the measured levers: mostly toward the pick, some level, some against
        const parts = lv < (DENSE ? 0.92 : 0.7) ? [{ k: 'pace', t: 'Pace', eff: 0.4 * sgn, i: 0 }, { k: 'dvp', t: 'Defence v position', eff: 0.5 * sgn, i: 0 }] : lv < 0.85 ? [{ k: 'pace', t: 'Pace', eff: 0.4 * sgn, i: 0 }, { k: 'dvp', t: 'Defence v position', eff: -0.5 * sgn, i: 0 }] : [{ k: 'pace', t: 'Pace', eff: -0.4 * sgn, i: 0 }, { k: 'minutes', t: 'Minutes', eff: 0.9, i: 0 }];
        men.push({ gi: g, pid, name, team, opp: home ? TEAMS[2 * g] : TEAMS[2 * g + 1], home, pos: 'G', mk, line, op: books[book][1], up: books[book][2], book, books, proj: line + sgn * 2, sd: 6, pm: side === 'OVER' ? 0.7 : 0.3, pb: 0.5,
          p: side === 'OVER' ? chance : Math.round((1 - chance) * 10000) / 10000, push: 0, side, chance, price, need, edge, band: edge >= 0.03 && chance >= 0.55 ? 'BET' : edge > 0 ? 'LEAN' : 'no edge', mins: 32, rate36: 20, base: 18, med: line + sgn * 1.5, usg: 22, sdf: 1, starter: true, why: ['x'],
          log: vals.map((v, i) => ['2026-10-' + String(10 + i), 'OPP', i % 2, 30, v, ['x']]), parts });
      }
    }
  }
  return { doc: { format: 'callsheet3.props', version: 1, date, games: games.map(g => ({ gid: 'r' + seed + '-' + g.gi, away: g.away, home: g.home, aab: g.aab, hab: g.hab, spread: g.spread, total: 225.5, props: men.filter(m => m.gi === g.gi) })) }, games, men };
}
// the oracle: a leg at an app, by the rule as the user was told it
function legAt(m, app, g) {
  if (!(m.edge > 0)) return null;
  const bk = m.books[app]; if (!bk) return null;
  const price = m.side === 'OVER' ? bk[1] : bk[2], chance = m.chance;   // the app's line is the carded one on these nights, so the chance is the card's
  if (!(chance - implied(price) > 0)) return null;
  const vals = m.log.map(x => x[4]).slice(-10), on = v => m.side === 'OVER' ? v > m.line : v < m.line, l5 = vals.slice(-5);
  if (l5.length < 5 || l5.filter(on).length < 4 || vals.length < 8 || vals.filter(on).length / vals.length < 0.5) return null;
  let tow = 0, ag = 0; m.parts.forEach(p => { if (!{ out: 1, oppc: 1, script: 1, pace: 1, dvp: 1, cons: 1 }[p.k] || Math.abs(p.eff) < 0.05) return; if (m.side === 'UNDER' ? p.eff < 0 : p.eff > 0) tow++; else ag++; });
  if (!(tow > ag)) return null;
  const fav = m.home ? -g.spread : g.spread;   // his club's margin on the spread
  if (m.side === 'OVER' && fav >= 5) return null;   // the over on a favourite's man, no record to read green
  return { m, app, price, chance, key: m.pid + ':' + m.mk };
}
function worth(legs) {   // a ticket's games and expected value: the product of the chances (two overs on one club at 0.95), never more than the weakest leg's
  let f = 1, d = 1, c = 1; const gs = new Set();
  legs.forEach((a, i) => { d *= dec(a.price); c *= a.chance; gs.add(a.m.gi); legs.slice(i + 1).forEach(b => { if (a.m.team === b.m.team && a.m.gi === b.m.gi && a.m.side === 'OVER' && b.m.side === 'OVER') f *= 0.95; }); });
  const chance = Math.min(...legs.map(l => l.chance), c * f);
  return { games: gs.size, ev: chance * d - 1, chance, dec: d };
}
function combos(xs, k) { const out = []; const go = (s, acc) => { if (acc.length === k) { out.push(acc.slice()); return; } for (let i = s; i < xs.length; i++) { acc.push(xs[i]); go(i + 1, acc); acc.pop(); } }; go(0, []); return out; }
function bestLeft(N, k, used, mode) {   // every valid ticket among the men not yet used, at every app; the best by games then value
  let best = null, count = 0;
  for (const app of APPS) {
    const legs = N.men.map(m => (mode === 't3o' && m.side !== 'OVER') || (mode === 't3u' && m.side !== 'UNDER') ? null : legAt(m, app, N.games[m.gi])).filter(l => l && !used.has(l.m.pid));
    for (const c of combos(legs, k)) {
      if (new Set(c.map(l => l.m.pid)).size < k) continue;
      const w = worth(c); if (k === 2 && w.games < 2) continue;
      count++;
      if (!best || w.games > best.games || (w.games === best.games && w.ev > best.ev)) best = { games: w.games, ev: w.ev, app, legs: c };
    }
  }
  return { best, count };
}
async function checkNights(pg, nights, seed0, dense, dateBase, verbose) {
  const stats = { nights: 0, checks: 0, tickets: { 2: 0, 3: 0 }, valid: 0, fails: [], empties: 0, sizes: [], shared: 0 };
  const d0 = new Date(dateBase + 'T00:00:00Z');
  for (let s = 0; s < nights; s++) {
    const seed = seed0 + s, date = new Date(d0.getTime() + s * 86400000).toISOString().slice(0, 10), N = night(seed, date, dense);
    const read = await pg.evaluate(async ([doc, name]) => {
      const wait = (ms) => new Promise(r => setTimeout(r, ms)); const txt = e => (e ? e.innerText : '').replace(/\s+/g, ' ').trim();
      const dt = new DataTransfer(); dt.items.add(new File([JSON.stringify(doc)], name, { type: 'application/json' })); const inp = document.getElementById('slateFile'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true })); await wait(140);
      if (document.getElementById('propsView').hidden) { document.getElementById('m-props').click(); await wait(80); }
      const set = (id, v) => { const el = document.getElementById(id); if (el.value !== v) { el.value = v; el.dispatchEvent(new Event('change', { bubbles: true })); } };
      const out = { date: document.getElementById('propsDate').value };
      for (const k of ['2', '3']) for (const mode of ['t3', 't3o', 't3u']) { set('propsLegs', k); set('propsBelow', mode); await wait(40);
        out[k + mode] = [...document.querySelectorAll('#propsBest .pk.t3')].map(c => ({ app: (txt(c.querySelector('.n1')).match(/ at (\w+) /) || [])[1], legs: [...c.querySelectorAll('.leg')].map(l => txt(l.querySelector('.lname')) + '|' + txt(l.querySelector('.chip i')).toLowerCase()), lands: txt(c.querySelector('.t3stats b')) })); }
      return out;
    }, [N.doc, 'nba-props-' + date + '.json']);
    if (read.date !== date) { stats.fails.push('seed ' + seed + ': the page is on ' + read.date + ', not ' + date); continue; }
    stats.nights++;
    const byNameLabel = {}; N.men.forEach(m => { byNameLabel[m.name + '|' + LABEL[m.mk]] = m; });
    for (const k of [2, 3]) for (const mode of ['t3', 't3o', 't3u']) {
      const list = read[k + mode], used = new Set(); stats.checks++;
      let ok = true;
      for (let i = 0; i <= list.length && ok; i++) {
        const { best, count } = bestLeft(N, k, used, mode);
        if (i === 0) stats.sizes.push(count);
        if (i === list.length) {   // the list ended: either six tickets, or nothing valid is left
          if (list.length < 6 && best) { ok = false; stats.fails.push(`seed ${seed} k${k} ${mode}: the list stops at ${list.length} with a valid ticket left (${best.legs.map(l => l.m.name).join(' + ')} at ${best.app})`); }
          if (!list.length && !best) stats.empties++;
          break;
        }
        const t = list[i], app = Object.keys(APPNAME).find(a => APPNAME[a] === t.app), legs = t.legs.map(x => byNameLabel[x]).map(m => m && legAt(m, app, N.games[m.gi]));
        if (!app || legs.length !== k || legs.some(l => !l) || new Set(legs.map(l => l.m.pid)).size < k || legs.some(l => used.has(l.m.pid)) || (mode === 't3o' && legs.some(l => l.m.side !== 'OVER')) || (mode === 't3u' && legs.some(l => l.m.side !== 'UNDER'))) { ok = false; stats.fails.push(`seed ${seed} k${k} ${mode} #${i + 1}: not a valid ticket: ${JSON.stringify(t)}`); break; }
        const w = worth(legs); stats.valid++; stats.tickets[k]++; if (w.games < k) stats.shared++;
        if (!best || w.games !== best.games || Math.abs(w.ev - best.ev) > 1e-9) { ok = false; stats.fails.push(`seed ${seed} k${k} ${mode} #${i + 1}: the page's ticket is worth ${w.ev.toFixed(5)} on ${w.games} games (${legs.map(l => l.m.name).join(' + ')} at ${app}); the best left is ${best ? best.ev.toFixed(5) + ' on ' + best.games + ' games (' + best.legs.map(l => l.m.name).join(' + ') + ' at ' + best.app + ')' : 'none'}`); break; }
        if (Math.abs(parseFloat(t.lands) - 100 * w.chance) > 0.0501) { ok = false; stats.fails.push(`seed ${seed} k${k} ${mode} #${i + 1}: the card says ${t.lands} to land, the legs make ${(100 * w.chance).toFixed(2)}%`); break; }
        legs.forEach(l => used.add(l.m.pid));
      }
      if (verbose && k === 2 && mode === 't3') console.log(`seed ${seed}: ${N.men.length} props on ${N.games.length} games, ${stats.sizes[stats.sizes.length - 1]} valid pairs, the page lists ${list.length}: ${list.map(t => t.legs.map(x => x.split('|')[0]).join('+') + '@' + t.app + ' ' + t.lands).join(' ; ')}`);
    }
  }
  return stats;
}
function report(stats) {
  const sz = stats.sizes.slice().sort((a, b) => a - b);
  return `${stats.nights} random nights, ${stats.checks} lists read (two and three legs, either side, the overs, the unders): ${stats.tickets[2]} two-leg tickets and ${stats.tickets[3]} three-leg tickets checked against every valid ticket by brute force (${stats.shared} three-leg tickets sharing a game); ${stats.empties} lists rightly empty; valid tickets to choose from on a list: median ${sz[Math.floor(sz.length / 2)]}, most ${sz[sz.length - 1]}`;
}
module.exports = { checkNights, report, night, legAt, worth, bestLeft };
if (require.main === module) (async () => {
  const { chromium } = require('playwright'), path = require('path');
  const nights = +(process.argv[2] || 200), seed0 = +(process.argv[3] || 1), dense = process.argv[4] === 'dense', verbose = process.argv[4] === 'v';
  const browser = await chromium.launch(process.env.PW_CHROMIUM ? { executablePath: process.env.PW_CHROMIUM } : (require('fs').existsSync('/opt/pw-browsers/chromium') ? { executablePath: '/opt/pw-browsers/chromium' } : {}));
  const pg = await browser.newPage({ viewport: { width: 1280, height: 1400 } });
  const errors = []; pg.on('pageerror', e => errors.push(String(e.message || e)));
  await pg.goto('file://' + (process.env.TICKETS_PAGE || path.join(__dirname, 'web/callsheet3.html')));   // TICKETS_PAGE: another build of the page, for a mutation test of this checker
  await pg.waitForFunction(() => window.smStore && document.getElementById('propsBest'), null, { polling: 100, timeout: 60000 });
  await pg.evaluate(() => smStore.ready.then(() => smStore.clear())); await pg.reload();
  await pg.waitForFunction(() => window.smStore && document.getElementById('propsBest'), null, { polling: 100, timeout: 60000 }); await pg.waitForTimeout(300);
  const stats = await checkNights(pg, nights, seed0, dense, '2027-01-01', verbose);
  console.log(report(stats));
  console.log(stats.fails.length ? 'FAILS (' + stats.fails.length + '):\n  ' + stats.fails.slice(0, 12).join('\n  ') : 'every ticket the page listed was the best one left: 0 failures');
  console.log('page errors:', errors.length ? errors.slice(0, 3) : 'none');
  await browser.close();
  process.exit(stats.fails.length || errors.length ? 1 : 0);
})();
