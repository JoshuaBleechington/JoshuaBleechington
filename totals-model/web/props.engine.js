  /* ===== PROPS BLOCK: NBA player props (19 Oct 2026) =====
     The user: "set up another tab for player props". slate.py's nba-props run
     writes one file a day with every prop The Odds API lists on the day's
     games and, beside each, the slate's own projection (rate x minutes, the
     regulars out, pace, defence v position) blended with the book's own
     chance. This tab lists them, keeps them, grades them from the nba-grade
     file's box lines, and keeps a record tile. The page scores NOTHING here: a
     prop row is the slate's call as made, so the record is of what was shown
     at the price it was shown. */
  var PROPS_KEY = "callsheet3.props.v1";
  var PROPS_LABEL = { pts: "points", reb: "rebounds", ast: "assists", tpm: "threes", pra: "pts + reb + ast", pr: "pts + reb", pa: "pts + ast", ra: "reb + ast" };
  var PROPS_COMBO = { pra: ["pts", "reb", "ast"], pr: ["pts", "reb"], pa: ["pts", "ast"], ra: ["reb", "ast"] };   // the combination markets (27 Oct 2026)
  var PROPS_ORDER = ["pts", "reb", "ast", "tpm", "pra", "pr", "pa", "ra"];
  var props = [];
  try { props = JSON.parse(localStorage.getItem(PROPS_KEY) || "[]"); if (!Array.isArray(props)) props = []; } catch (e) { props = []; }
  var propsView = false;
  var propsOrder = [], propDetailId = null;   // the Every-prop table's order, and the prop the panel shows (22 Oct 2026)
  var pairsOrder = [], propDetailKind = "prop";   // the night's tickets in order, and whether the panel shows a prop or a pair (26 Oct 2026)
  /* the table's view (22 Oct 2026, the user: "is there a way for me to rearrange the rows? all the rebound props, or
     the points for a player, by chance percentage and band"): a sort column with its direction, and filters by market,
     band, side and a name. Kept in this browser only; Reset view puts the table back to by game, then by edge */
  var PROPS_VIEW_KEY = "callsheet3.props.view.v1";
  var PROPS_VIEW_DEFAULT = { sort: "default", dir: -1, mk: "", band: "", side: "", q: "", agree: "", usage: "", role: "", sim: "" };
  /* the floors (26 Oct 2026, the user: "PRA alt lines at 95% or more, Sengun 10+ points, 5+ rebounds, 3+ assists"): the number
     the model says he clears 95, 90 and 80% of nights, read off the median and the sigma the chance already uses. Measured on
     2025-26 (tools_nba_usage_floors.py): the 95% floors cleared 97.5% of nights, the 90% 93%, the 80% 82%; posted as a whole
     number ("x+") the 95% line cleared 98%; one man's three 95% floors (points, rebounds, assists) all cleared 96.5% of nights,
     against 85.7% if they were independent, because his minutes carry all three. A file from before the slate wrote the median
     reads it off the projection with the same shift the slate uses */
  var PROPS_MEDIAN_SHIFT = { pts: 0.08, reb: 0.11, ast: 0.14, tpm: 0.23, pra: 0.05, pr: 0.06, pa: 0.05, ra: 0.08 };
  var PROPS_FLOOR_Z = { 95: 1.6449, 90: 1.2816, 80: 0.8416 };
  function propMedian(r) { return r.med !== undefined && r.med !== null ? +r.med : +r.proj - (PROPS_MEDIAN_SHIFT[r.mk] || 0) * +r.sd; }
  function propFloor(r, q) { var f = Math.floor(propMedian(r) - PROPS_FLOOR_Z[q] * +r.sd); return f >= 1 ? f : null; }
  function propUsageBucket(r) { return r.usg === null || r.usg === undefined ? "" : r.usg < 18 ? "lo" : r.usg < 24 ? "mid" : "hi"; }
  /* the simulation's stats on the Props page (26 Oct 2026, the user: "add the simulation stats to the Prop page as well"): the
     game's block from the props run (each club's points with the middle half against the ratings' points a game, the total,
     the margin, the blowout and overtime chances, the pace, the regulars out) rides on each of the game's rows, compact, and is
     shown as a strip above the picks, one card a game; the sim's own read of each prop is a column of the table, a filter, a
     line on the best cards and on the phone sheet. Shown, not scored: the scored part is the matchup lever at half weight */
  function propsGameSim(gs) {
    if (!gs || !gs.away || !gs.home) return null;
    var side = function (s) { return [s.median, s.p25, s.p75, s.ppg === undefined ? null : s.ppg]; };
    return { runs: gs.runs, a: side(gs.away), h: side(gs.home), t: gs.total, m: gs.margin, hw: gs.home_win, ot: gs.ot, bo: gs.blowout, poss: gs.poss,
             out: [+((gs.out || {}).away || 0), +((gs.out || {}).home || 0)] };
  }
  function propSimRead(r) { return r.sim && r.sim.read !== null && r.sim.read !== undefined && isFinite(+r.sim.read) ? +r.sim.read : null; }
  function propSimAgrees(r) { var v = propSimRead(r); if (v === null || !propHas(r) || v === +r.line) return null; return r.side === "UNDER" ? v < +r.line : v > +r.line; }
  function propSimGap(r) { var v = propSimRead(r); if (v === null || !propHas(r)) return null; return Math.round(((r.side === "UNDER" ? +r.line - v : v - +r.line)) * 10) / 10; }
  function propsPct(v) { v = +v * 100; return v.toFixed(v >= 10 ? 0 : 1) + "%"; }
  function propSimLine(r) {
    var v = propSimRead(r), ag = propSimAgrees(r), s = r.sim;
    if (v === null) return "";
    return 'Sim reads ' + v + ' v the ' + r.line + ' line, ' + (ag === true ? 'on the ' + esc(r.side) + '\'s side' : ag === false ? 'against the ' + esc(r.side) : 'on the line') + ' · ' + esc(r.team || 'his club') + ' ' + s.team_pts + ' (' + s.team_lo + '–' + s.team_hi + ') · blowout ' + propsPct(s.blowout);
  }
  function propsGameSimFromRows(gr, r0) {
    /* a file loaded before the strip existed carries the game's block on no row; the props' own sim blocks give most of it back */
    var aab = r0.aab || r0.away, hab = r0.hab || r0.home, a = null, h = null, any = null;
    gr.forEach(function (x) { if (!x.sim || x.sim.team_pts === undefined || x.sim.team_pts === null) return; any = any || x.sim; if (x.team === aab && !a) a = x.sim; if (x.team === hab && !h) h = x.sim; });
    if (!a || !h || !any) return null;
    var side = function (s) { return [s.team_pts, s.team_lo, s.team_hi, s.team_ppg || null]; };
    return { runs: any.runs, a: side(a), h: side(h), t: Math.round(+a.team_pts + +h.team_pts), m: null, hw: any.home_win, ot: any.ot, bo: any.blowout, poss: any.poss, out: [+(a.out || 0), +(h.out || 0)], approx: true };
  }
  function propsSimStripHtml(rows) {
    var games = {}, order = [];
    rows.forEach(function (r) {
      if (!games[r.game]) { games[r.game] = { r: r, n: 0, yes: 0 }; order.push(r.game); }
      var g = games[r.game]; if (!g.r.gsim && r.gsim) g.r = r;
      if (propHas(r) && propSimAgrees(r) !== null) { g.n++; if (propSimAgrees(r)) g.yes++; }
    });
    if (!order.length) return '';
    return order.sort().map(function (game) {
      var g = games[game], r = g.r, s = r.gsim || propsGameSimFromRows(rows.filter(function (x) { return x.game === game; }), r);
      if (!s) return '<div class="pk simg dim"><div class="n1">' + esc(game) + '</div><div class="n4">This file\'s run carried no simulation on the game; a props run with the current slate.py plays it 10,000 times.</div></div>';
      var aab = r.aab || r.away || "away", hab = r.hab || r.home || "home", hasM = s.m !== null && s.m !== undefined && isFinite(+s.m), fav = +s.m >= 0 ? hab : aab;
      var book = r.total !== null && r.total !== undefined && isFinite(+r.total) ? ' · the book\'s ' + r.total + ' (' + sgn(+s.t - +r.total, 1) + ')' : '';
      var outs = [[aab, s.out[0]], [hab, s.out[1]]].filter(function (x) { return x[1]; }).map(function (x) { return ' · ' + esc(x[0]) + '\'s regulars out ' + sgn(x[1], 1) + ' per 100 on the offence'; }).join('');
      return '<div class="pk simg"><div class="n1">' + esc(game) + ' · played ' + esc(Number(s.runs).toLocaleString()) + ' times</div>' +
        '<div class="n2">' + esc(aab) + ' ' + s.a[0] + ' · ' + esc(hab) + ' ' + s.h[0] + ' <span class="dim">total ' + (s.approx ? 'about ' : '') + s.t + '</span></div>' +
        '<div class="n3">' + (hasM ? esc(fav) + ' by ' + Math.abs(+s.m).toFixed(1) + ' · ' : '') + (s.hw !== null && s.hw !== undefined ? 'home win ' + propsPct(s.hw) + ' · ' : '') + 'total ' + (s.approx ? 'about ' : '') + s.t + book + '</div>' +
        '<div class="n4">' + esc(aab) + ' middle half ' + s.a[1] + '–' + s.a[2] + (s.a[3] ? ' against ' + s.a[3] + ' a game by the ratings' : '') + ' · ' + esc(hab) + ' ' + s.h[1] + '–' + s.h[2] + (s.h[3] ? ' against ' + s.h[3] : '') + '</div>' +
        '<div class="n5">blowout of 15 or more ' + propsPct(s.bo) + ' · overtime ' + propsPct(s.ot) + ' · ' + s.poss + ' possessions' + outs + (g.n ? ' · the sim\'s read on the pick\'s side for <b>' + g.yes + ' of ' + g.n + '</b> props' : '') + '</div></div>';
    }).join('');
  }
  /* two props from one game as a ticket (26 Oct 2026, the user: "the ones that hit quickly were same game parlays with 2 legs...
     offer same game parlay tickets with the players' matchups on the same games that are the most likely to hit"): the legs are
     the date's projected props at 55% or better, likeliest first, up to four a game; every pair in a game is a ticket whose chance
     is the product of the two chances times what 2025-26 measured for the pair's kind (two players' props land almost
     independently: two overs on one club 0.95 of the product, anything else 1.0; one man's two markets together more often,
     1.15, and his points with his threes 1.5), capped at the lesser leg; the price is the two legs' prices multiplied and what it
     needs is one over that. The tickets are rebuilt from the rows every time, so a graded night's tickets are the night's as
     it stood, and the record grades them the same way */
  var PROPS_PAIR_FACTOR = { same_club_overs: 0.95, cross: 1.0, same_man: 1.15, same_man_pts_tpm: 1.5 };
  var PROPS_PAIR_MIN = 0.52, PROPS_PAIR_LEGS = 4, PROPS_PAIR_MAX = 8;
  function propsPairTicket(a, b) {
    if (!a || !b || !propHas(a) || !propHas(b) || String(a.id) === String(b.id)) return null;
    if (b.chance > a.chance) { var s = a; a = b; b = s; }   // the likelier leg first
    var kind;
    if (String(a.pid) === String(b.pid)) { if (a.mk === b.mk) return null; kind = ((a.mk === "pts" && b.mk === "tpm") || (a.mk === "tpm" && b.mk === "pts")) ? "same_man_pts_tpm" : "same_man"; }
    else kind = (a.team === b.team && a.side === "OVER" && b.side === "OVER") ? "same_club_overs" : "cross";
    var f = PROPS_PAIR_FACTOR[kind], chance = Math.min(a.chance, b.chance, a.chance * b.chance * f), dec = decimalOf(a.price) * decimalOf(b.price);
    return { id: a.id + "|" + b.id, game: a.game, legs: [a, b], kind: kind, f: f, chance: chance, dec: dec, price: americanOf(dec), need: 1 / dec };
  }
  function propsPairs(dateISO, rowsIn) {
    var rows = (rowsIn || propsSource()).filter(function (r) { return (r.gdate || "") === dateISO && propHas(r) && r.chance >= PROPS_PAIR_MIN && r.result !== "void"; });
    var byGame = {};
    rows.forEach(function (r) { (byGame[r.game] = byGame[r.game] || []).push(r); });
    var out = [];
    Object.keys(byGame).forEach(function (game) {
      var legs = byGame[game].slice().sort(function (a, b) { return b.chance - a.chance; }).slice(0, PROPS_PAIR_LEGS);
      for (var i = 0; i < legs.length; i++) for (var j = i + 1; j < legs.length; j++) {
        var t = propsPairTicket(legs[i], legs[j]); if (t) out.push(t);
      }
    });
    out.sort(function (x, y) { return (y.chance - x.chance) || (x.need - y.need); });
    return out.slice(0, PROPS_PAIR_MAX);
  }
  /* a pair you take (26 Oct 2026, the user: "when I click on the same-game pairs they don't open to show any details; I'd like
     something similar to how the props are for the singles"): the mark lives on both legs as the other leg's key (`pairs`),
     so it rides through a reload like a prop's own mark, and the ticket is rebuilt from the two rows as the night stood */
  function propsPairTaken(t) { return ((t.legs[0].pairs || []).indexOf(propKey(t.legs[1])) >= 0); }
  function propsPairTakeBtn(t, big) {
    var a = t.legs[0], b = t.legs[1], on = propsPairTaken(t);
    if (a.result || b.result) return on ? ' <span class="chip taken">TAKEN</span>' : "";
    return '<button type="button" class="takebtn' + (on ? ' on' : '') + (big ? ' big' : '') + '" data-ttake="' + a.id + '|' + b.id + '" title="' +
           (on ? 'Marked as a ticket you are placing: click to unmark it' : 'Mark this pair as a ticket you are placing') + '">' + (on ? '&#10003; Taking' : (big ? 'Take this pair' : 'Take')) + '</button>';
  }
  function togglePairTake(spec) {
    var p = String(spec).split("|"), a = propById(p[0]), b = propById(p[1]); if (!a || !b || !propHas(a) || !propHas(b)) return;
    if (a.result || b.result) { propsSay("<b>" + esc(a.name) + " + " + esc(b.name) + "</b> is graded: a ticket is marked before the game, not after."); return; }
    var ka = propKey(a), kb = propKey(b), on = (a.pairs || []).indexOf(kb) >= 0;
    var drop = function (r, k) { r.pairs = (r.pairs || []).filter(function (x) { return x !== k; }); if (!r.pairs.length) delete r.pairs; };
    var add = function (r, k) { if ((r.pairs || []).indexOf(k) < 0) r.pairs = (r.pairs || []).concat([k]); };
    if (on) { drop(a, kb); drop(b, ka); } else { add(a, kb); add(b, ka); }
    if (!propsPreview) saveProps();
    renderProps(); renderCalib(); if (typeof renderBoard === "function") renderBoard();
    refreshPropDetail();
  }
  function pairTakesOn(dateISO) {
    var rows = propsSource().filter(function (r) { return (r.gdate || "") === dateISO; }), byKey = {}, seen = {}, out = [];
    rows.forEach(function (r) { byKey[propKey(r)] = r; });
    rows.forEach(function (a) {
      (a.pairs || []).forEach(function (k) {
        var b = byKey[k], t = b ? propsPairTicket(a, b) : null; if (!t || seen[t.id]) return;
        seen[t.id] = true; out.push(t);
      });
    });
    out.sort(function (x, y) { return (y.chance - x.chance) || (x.need - y.need); });
    return out;
  }
  function pairTakesAll() { var out = []; propsDates().forEach(function (d) { out = out.concat(pairTakesOn(d)); }); return out; }
  function propsPairRes(t) {
    var rs = t.legs.map(function (r) { return r.result; });
    if (rs.some(function (r) { return !r || r === "graded"; })) return null;
    if (rs.some(function (r) { return r === "void"; })) return null;
    if (rs.some(function (r) { return r === "loss"; })) return "loss";
    var live = rs.filter(function (r) { return r !== "push"; });
    return live.length ? "win" : "push";
  }
  function propsPairUnits(t, res) {
    if (res === "loss") return -1;
    if (res !== "win") return 0;
    var dec = 1;
    t.legs.forEach(function (r) { if (r.result === "win") dec *= decimalOf(r.price); });   // a pushed leg drops out of the ticket
    return dec - 1;
  }
  function propsPairKindWords(kind) { return kind === "same_club_overs" ? "two overs on one club" : kind === "cross" ? "two players" : kind === "same_man_pts_tpm" ? "one man, his points with his threes" : "one man, two markets"; }
  function propsPairLeg(r) { return esc(r.name) + ' ' + esc(r.side) + ' ' + r.line + ' ' + esc(PROPS_LABEL[r.mk] || r.mk); }
  function propsPairCard(t, i, asTaking) {
    var res = propsPairRes(t), ok = t.chance >= t.need, a = t.legs[0], b = t.legs[1], on = propsPairTaken(t), leg = propsPairLeg;
    return '<div class="pk pair' + (ok ? ' agrees' : '') + (res ? ' ' + res : '') + (on ? ' taking' : '') + '" data-pair="' + esc(t.id) + '"><div class="n1">' + (asTaking ? 'TAKING · SAME-GAME PAIR' : 'PAIR #' + (i + 1)) + ' · ' + esc(t.game) + ' · ' + (ok ? 'the price agrees' : 'the price asks more') + '</div>' +
      '<div class="n2">' + leg(a) + ' <span class="amp">+</span> ' + leg(b) + (res ? ' <span class="chip ' + res + '">' + esc(res.toUpperCase()) + '</span>' : '') + '</div>' +
      '<div class="n3">both land ' + (t.chance * 100).toFixed(1) + '% · pays ' + sgn(t.price, 0) + ' (' + t.dec.toFixed(2) + '×) needs ' + (t.need * 100).toFixed(1) + '%</div>' +
      '<div class="n4">' + esc(a.name) + ' ' + (a.chance * 100).toFixed(1) + '% at ' + sgn(a.price, 0) + ' · ' + esc(b.name) + ' ' + (b.chance * 100).toFixed(1) + '% at ' + sgn(b.price, 0) + ' · ' + esc(propsPairKindWords(t.kind)) + ', measured ×' + t.f.toFixed(2) + '</div>' +
      '<div class="n6">' + propsPairTakeBtn(t) + '</div></div>';
  }
  /* the pair's own panel (26 Oct 2026): the ticket's numbers as tiles, how the chance is made from the two legs and the
     measured factor, then each leg's numbers with a button to its own panel. Previous / Next walk the night's tickets */
  function propsPairMeasured(kind) {
    return kind === "cross" ? "Two players' props in one game landed almost as independence says on 2025-26 (both over the median 25.2% of pairs on opposite clubs and 23.7% on one club, against 25.0%), so the product carries ×1.00"
         : kind === "same_club_overs" ? "Two overs on one club landed together a shade less often than independence says on 2025-26 (23.7% of pairs against 25.0%), so the product carries ×0.95"
         : kind === "same_man_pts_tpm" ? "One man's points and threes land together far more often than independence says on 2025-26 (38.2% of pairs against 25%): the threes are points, so the product carries ×1.5"
         : "One man's two markets land together more often than independence says on 2025-26 (28 to 29% of pairs against 25%), his minutes carrying both, so the product carries ×1.15";
  }
  function propsPairDetailHtml(t) {
    var a = t.legs[0], b = t.legs[1], res = propsPairRes(t), ok = t.chance >= t.need, leg = propsPairLeg, pc = function (v) { return (v * 100).toFixed(1) + "%"; };
    var tile = function (k, v, s, cls) { return '<div class="pd-tile' + (cls ? ' ' + cls : '') + '"><div class="k">' + esc(k) + '</div><div class="v">' + v + '</div>' + (s ? '<div class="s">' + s + '</div>' : '') + '</div>'; };
    var h = '<div class="pd-band">Same-game pair · ' + (ok ? 'the price agrees' : 'the price asks more') + '</div>';
    h += '<h3>' + leg(a) + ' <span class="amp">+</span> ' + leg(b) + '</h3>';
    h += '<div class="pd-pick">both land ' + pc(t.chance) + ' · pays ' + sgn(t.price, 0) + ' (' + t.dec.toFixed(2) + '×) needs ' + pc(t.need) + (res ? ' <span class="chip ' + res + '">' + esc(res.toUpperCase()) + '</span>' : '') + '</div>';
    h += '<div class="pd-sub">' + esc(t.game) + ' · ' + esc(gameDate(a.gdate)) + ' · ' + esc(propsPairKindWords(t.kind)) + ', measured ×' + t.f.toFixed(2) + ' · ' + esc(a.book || "the book") + (b.book && b.book !== a.book ? ' and ' + esc(b.book) : '') + '</div>';
    if ((propsPairTakeBtn(t, true) || "").length) h += '<div class="pd-take">' + propsPairTakeBtn(t, true) + '</div>';
    h += '<div class="pd-tiles">' +
      tile("Both land", pc(t.chance), "the two chances multiplied, × " + t.f.toFixed(2) + " measured, capped at the lesser leg") +
      tile("Parlay price", sgn(t.price, 0), t.dec.toFixed(2) + "× the stake · needs " + pc(t.need)) +
      tile("Edge", sgn((t.chance - t.need) * 100, 1), "points of chance over the parlay price", ok ? "good" : "bad") +
      tile("Leg 1", pc(a.chance), leg(a) + " at " + sgn(a.price, 0) + " · " + esc(a.band)) +
      tile("Leg 2", pc(b.chance), leg(b) + " at " + sgn(b.price, 0) + " · " + esc(b.band)) +
      '</div>';
    var raw = a.chance * b.chance * t.f, capped = t.chance < raw - 1e-9;
    h += '<h4>How the chance is made</h4><p class="pd-base">' + leg(a) + ' lands <b>' + pc(a.chance) + '</b> by the sheet and ' + leg(b) + ' <b>' + pc(b.chance) + '</b>, each the blended chance on its own panel. ' +
         propsPairMeasured(t.kind) + ': ' + pc(a.chance) + ' × ' + pc(b.chance) + ' × ' + t.f.toFixed(2) + ' = <b>' + pc(raw) + '</b>' + (capped ? ', capped at the lesser leg\'s ' + pc(t.chance) : '') +
         '. The ticket pays the two prices multiplied, ' + decimalOf(a.price).toFixed(2) + ' × ' + decimalOf(b.price).toFixed(2) + ' = ' + t.dec.toFixed(2) + '×, ' + sgn(t.price, 0) + ', which needs ' + pc(t.need) + ': ' +
         (ok ? 'the price agrees by ' + ((t.chance - t.need) * 100).toFixed(1) + ' points' : 'the price asks ' + ((t.need - t.chance) * 100).toFixed(1) + ' points more than the sheet gives') +
         '. A pushed leg drops out of the ticket as the books do it; a lost leg loses it.</p>';
    [a, b].forEach(function (r, i) {
      var lv = propsLeversLine(r), sl = propSimLine(r), tally = propsLeverTally(r), tl = propsLogTally(r), ag = propSimAgrees(r);
      h += '<div class="pd-leg"><h4>Leg ' + (i + 1) + ' <span class="dim">· ' + leg(r) + (r.pos ? ' · ' + esc(r.pos) : '') + (r.team ? ' ' + esc(r.team) : '') + (r.starter === true ? ' · starter' : r.starter === false ? ' · bench' : '') + '</span></h4>';
      h += '<div class="pd-tiles">' +
        tile("Chance", pc(r.chance), "the over " + pc(r.pm) + " by the model, " + pc(r.pb) + " by the book") +
        tile("Price", sgn(r.price, 0), "needs " + pc(r.need)) +
        tile("Edge", sgn(r.edge * 100, 1), esc(r.band), r.edge > 0 ? "good" : "bad") +
        tile("Projection", esc(String(r.proj)), "± " + esc(String(r.sd)) + " one sigma · line " + esc(String(r.line))) +
        tile("Minutes", esc(String(r.mins)), esc(String(r.rate36)) + " per 36") +
        (r.usg !== null && r.usg !== undefined ? tile("Usage", esc(String(r.usg)) + "%", "of his club's possessions") : "") +
        '</div>';
      h += '<p class="pd-base">' + (lv ? 'Moves it: ' + lv + (tally.n ? ' (' + esc(tally.words) + ')' : '') + '. ' : '') + (sl ? '<span class="' + (ag === true ? 'pos' : ag === false ? 'neg' : '') + '">' + sl + '</span>. ' : '') + (tl ? 'Last games' + tl + '.' : '') + '</p>';
      h += '<div class="row"><button type="button" class="btn" data-prop="' + r.id + '">Open this prop</button> ' + propTakeBtn(r) + '</div></div>';
    });
    h += '<p class="note">Two of the slate\'s calls as made, priced as one ticket at the two legs\' prices multiplied; the Same-game pairs tile in Is it working is the test, and a pair you mark grades under What you took.</p>';
    return h;
  }
  function openPairDetail(spec) {
    var p = String(spec).split("|"), a = propById(p[0]), b = propById(p[1]), dlg = $("propDetail"); if (!a || !b || !dlg) return;
    var t = propsPairTicket(a, b); if (!t) return;
    propDetailId = String(t.id); propDetailKind = "pair";
    $("propDetailBody").innerHTML = propsPairDetailHtml(t);
    var i = pairsOrder.indexOf(propDetailId), nav = $("propDetailNav");
    if (nav) {
      nav.hidden = i < 0 || pairsOrder.length < 2;
      $("propDetailPos").textContent = i >= 0 ? (i + 1) + " of " + pairsOrder.length + " pairs" : "";
      $("propDetailPrev").disabled = i <= 0;
      $("propDetailNext").disabled = i < 0 || i >= pairsOrder.length - 1;
    }
    dlg.hidden = false; dlg.scrollTop = 0;
    document.body.classList.add("noscroll");
    if ($("propDetailClose")) $("propDetailClose").focus();
  }
  function refreshPropDetail() {
    var dlg = $("propDetail"); if (!dlg || dlg.hidden || !propDetailId) return;
    if (propDetailKind === "pair") { var p = propDetailId.split("|"), a = propById(p[0]), b = propById(p[1]), t = a && b ? propsPairTicket(a, b) : null; if (t) $("propDetailBody").innerHTML = propsPairDetailHtml(t); }
    else { var r = propById(propDetailId); if (r) $("propDetailBody").innerHTML = propsDetailHtml(r); }
  }
  var propsTableView = Object.assign({}, PROPS_VIEW_DEFAULT);
  try { var pv0 = JSON.parse(localStorage.getItem(PROPS_VIEW_KEY) || "null"); if (pv0 && typeof pv0 === "object") propsTableView = Object.assign({}, PROPS_VIEW_DEFAULT, pv0); } catch (e) {}
  function savePropsTableView() { try { localStorage.setItem(PROPS_VIEW_KEY, JSON.stringify(propsTableView)); } catch (e) {} }
  var PROPS_BAND_RANK = { "BET": 0, "LEAN": 1, "no edge": 2 };
  var PROPS_SORT_COLS = [["game", "Game"], ["name", "Player"], ["mk", "Market"], ["line", "Line"], ["side", "Pick"], ["chance", "Chance"], ["price", "Price"], ["need", "Needs"], ["edge", "Edge"], ["proj", "Proj"], ["band", "Band"], ["result", "Result"], ["agree", "Levers"], ["sim", "Sim"], ["usage", "Usage"]];
  /* the levers' tally (26 Oct 2026, the user: "find props like this one, where What moves it shows multiple green bars
     pointing toward the pick"): how many of the factors push toward the pick's side and how many against, a push under
     0.05 in the stat's units counting as neither. A column to sort by, a filter, a tag on the card and the panel's heading */
  function propsLeverTally(r) {
    var toward = 0, against = 0;
    if (propHas(r)) (r.parts || []).forEach(function (p) {
      if (!p || !isFinite(+p.eff) || Math.abs(+p.eff) < 0.05) return;
      if (propsLeverHelps(r, +p.eff)) toward++; else against++;
    });
    var n = toward + against;
    return { toward: toward, against: against, n: n, all: n >= 2 && against === 0, most: toward > against,
             text: n ? toward + "▲ " + against + "▼" : "", words: n ? toward + " of " + n + " lever" + (n === 1 ? "" : "s") + " toward the " + (r.side || "pick") + (against ? ", " + against + " against" : "") : "" };
  }
  function propsSortValue(r, key) {
    var has = propHas(r);
    switch (key) {
      case "agree": return has ? (function (t) { return t.n ? (t.toward - t.against) + t.toward / 10 : -50; })(propsLeverTally(r)) : -99;
      case "sim": return has ? (function (g) { return g === null ? -99 : g; })(propSimGap(r)) : -999;
      case "usage": return r.usg === null || r.usg === undefined ? -1 : +r.usg;
      case "game": return r.game || "";
      case "name": return r.name || "";
      case "mk": return PROPS_LABEL[r.mk] || r.mk || "";
      case "line": return +r.line;
      case "side": return has ? (r.side || "") : "~";
      case "chance": return has ? +r.chance : -1;
      case "price": return has ? +r.price : -99999;
      case "need": return has ? +r.need : -1;
      case "edge": return has ? +r.edge : -9;
      case "proj": return has ? +r.proj : -1;
      case "band": return has ? (PROPS_BAND_RANK[r.band] !== undefined ? PROPS_BAND_RANK[r.band] : 3) : 4;
      case "result": return r.result || "~";
    }
    return 0;
  }
  function propsTableRows(rows) {
    var v = propsTableView, q = String(v.q || "").trim().toLowerCase();
    var list = rows.filter(function (r) {
      if (v.mk && r.mk !== v.mk) return false;
      if (v.band && (!propHas(r) || r.band !== v.band)) return false;
      if (v.side && (!propHas(r) || r.side !== v.side)) return false;
      if (v.agree) { var t = propsLeverTally(r); if (!propHas(r) || (v.agree === "all" ? !t.all : !t.most)) return false; }
      if (v.usage && propUsageBucket(r) !== v.usage) return false;
      if (v.role && !(v.role === "starter" ? r.starter === true : r.starter === false)) return false;
      if (v.sim) { var ag = propSimAgrees(r); if (ag === null || (v.sim === "yes" ? !ag : ag)) return false; }
      if (q && String(r.name || "").toLowerCase().indexOf(q) < 0 && String(r.game || "").toLowerCase().indexOf(q) < 0) return false;
      return true;
    });
    var byDefault = function (a, b) { return (a.game < b.game ? -1 : a.game > b.game ? 1 : 0) || ((propHas(b) ? b.edge : -9) - (propHas(a) ? a.edge : -9)) || String(a.name).localeCompare(String(b.name)); };
    if (v.sort === "default") return list.sort(byDefault);
    return list.sort(function (a, b) {
      var x = propsSortValue(a, v.sort), y = propsSortValue(b, v.sort), c = typeof x === "string" ? x.localeCompare(y) : (x - y);
      if (v.sort === "band") c = -c;   // the band's rank runs BET first; a "descending" band sort still reads BET at the top
      return (c * v.dir) || byDefault(a, b);
    });
  }
  /* the example (19 Oct 2026, the user: "put an example on the NBA props model
     like you did for the NBA"): one game's props computed at build time through
     the slate's own projection, previewed in the tab and never saved -- a real
     file, Clear this date or a sport button puts it away */
  var PROPS_EXAMPLE_GAMES = /*PROPS_EXAMPLE*/[];
  var propsPreview = null;
  function propsSource() { return propsPreview || props; }
  function saveProps() { try { localStorage.setItem(PROPS_KEY, JSON.stringify(props)); } catch (e) {} }
  function propsSay(msg) { var el = $("propsMsg"); if (!el) return; el.hidden = false; el.innerHTML = msg; }
  function propKey(r) { return (r.gdate || "") + "|" + r.pid + "|" + r.mk; }
  function propsDates() { var d = {}; propsSource().forEach(function (r) { if (r.gdate) d[r.gdate] = true; }); return Object.keys(d).sort(); }
  /* one row per player per market from a props file's games */
  function propsRowsFrom(d) {
    var rows = [];
    (d.games || []).forEach(function (g) {
      (g.props || []).forEach(function (x) {
        rows.push({ id: 0, gdate: d.date || "", game: g.away + " @ " + g.home, away: g.away, home: g.home, aab: g.aab, hab: g.hab, spread: g.spread, total: g.total, pace: g.pace,
                    pid: String(x.pid), name: x.name, team: x.team, opp: x.opp, athome: !!x.home, pos: x.pos || "", mk: x.mk, line: x.line, op: x.op, up: x.up, book: x.book, books: x.books || {},
                    proj: x.proj, sd: x.sd, pm: x.pm, pb: x.pb, p: x.p, push: x.push, side: x.side, chance: x.chance, price: x.price, need: x.need, edge: x.edge, band: x.band,
                    mins: x.mins, rate36: x.rate36, base: x.base, parts: x.parts || [], why: x.why || [], log: x.log || [], sim: x.sim || null,
                    med: x.med, usg: x.usg, sdf: x.sdf, starter: x.starter === undefined ? null : x.starter, start_src: x.start_src || null, gsim: propsGameSim(g.sim), fives: g.fives || null, actual: null, result: null });
      });
    });
    return rows;
  }
  function propsExample() {
    var doc = { format: "callsheet3.props", date: todayISO(), games: PROPS_EXAMPLE_GAMES };
    propsPreview = propsRowsFrom(doc).map(function (r, i) { r.id = 90001 + i; return r; });
    if ($("propsDate")) $("propsDate").value = doc.date;
    showProps(true);
    propsSay("<b>An example</b>, one game's props as a real file lists them, with the projection built the slate's way. Nothing here is saved or graded: load a real props file, press Clear this date or a sport button, and it goes.");
  }
  function propsCanon(s) { return String(s || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim(); }
  /* the matchup and the fives on the prop (27 Oct 2026, the user: "a button to take me to the matchup for that game, or show the
     lineup for that team in the prop"): the NBA card's row for the prop's game, when the slate put it there, opens into the form
     from the panel or the card; the props file carries each club's starting five from RotoWire, shown on the panel with the man marked */
  function propsCardRow(r) {
    if (!r || typeof card === "undefined") return null;
    for (var i = 0; i < card.length; i++) {
      var x = card[i];
      if (x.sport === "NBA" && (x.gdate || "") === (r.gdate || "") && propsCanon(x.away) === propsCanon(r.away) && propsCanon(x.home) === propsCanon(r.home)) return x;
    }
    return null;
  }
  function propsGoBtn(r, big) {
    var row = propsCardRow(r);
    return '<button type="button" class="btn go' + (row ? '' : ' off') + '" data-pgo="' + r.id + '" title="' + (row ? 'Open ' + esc(r.game) + ' on the NBA card, into the form' : 'The NBA card has no row for ' + esc(r.game) + ' on ' + esc(gameDate(r.gdate)) + ': load the NBA slate for the date and Add the game') + '">' + (big ? 'Open the matchup on the NBA card' : 'Matchup') + '</button>';
  }
  function openPropMatchup(id) {
    var r = propById(id); if (!r) return;
    var row = propsCardRow(r);
    if (!row) { propsSay("The NBA card has no row for <b>" + esc(r.game) + "</b> on " + esc(gameDate(r.gdate)) + ": load the NBA slate for the date (Load slate) and Add the game, and the button opens it."); return; }
    closePropDetail(); showProps(false);
    if (typeof openRow === "function") openRow(row.id);
  }
  function propsFivesHtml(r) {
    var f = r.fives; if (!f || (!f.away && !f.home)) return '';
    var me = propsNameKey(r.name);
    var h = '<h4>The starting fives <span class="dim">· RotoWire\'s, as the props run read them; expected is the morning\'s lineup, confirmed the club\'s; shown, not scored</span></h4><div class="pd-fives">';
    [["away", r.away], ["home", r.home]].forEach(function (s) {
      var L = f[s[0]];
      h += '<div class="five">';
      if (!L) { h += '<p><b>' + esc(s[1]) + '</b> <span class="lbadge none">no lineup</span> <span class="dim">RotoWire had not posted this side at the run.</span></p></div>'; return; }
      var st = String(L.status || "").toLowerCase();
      h += '<p><b>' + esc(s[1]) + '</b> <span class="lbadge ' + (st === "confirmed" ? 'conf' : 'exp') + '">' + esc(st || 'lineup') + '</span></p><table class="form"><tbody>' +
        (L.five || []).map(function (p) { return '<tr' + (propsNameKey(p[1]) === me ? ' class="me"' : '') + '><td class="pos">' + esc(p[0] || '') + '</td><td>' + esc(p[1] || '') + (propsNameKey(p[1]) === me ? ' <span class="tag">this prop</span>' : '') + '</td></tr>'; }).join('') + '</tbody></table>';
      if ((L.maybe || []).length) h += '<p class="dim">May not play: ' + L.maybe.map(function (p) { return (p[0] ? esc(p[0]) + ' ' : '') + esc(p[1] || '') + (p[2] ? ' (' + esc(p[2]) + ')' : ''); }).join('; ') + '.</p>';
      h += '</div>';
    });
    return h + '</div>';
  }
  function propsNameKey(n) { return String(n || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z ]+/g, "").replace(/\b(jr|sr|ii|iii|iv)\b/g, "").replace(/\s+/g, " ").trim(); }
  function propHas(r) { return r.p !== null && r.p !== undefined; }
  /* the tab: the matchup columns go, the props section comes, the sport buttons read unpressed */
  function showProps(on) {
    propsView = !!on;
    if (!propsView) { propsPreview = null; closePropDetail(); }
    var cols = document.querySelector(".cols"); if (cols) cols.hidden = propsView;
    var v = $("propsView"); if (v) v.hidden = !propsView;
    var b = $("m-props"); if (b) b.setAttribute("aria-pressed", propsView ? "true" : "false");
    ["m-mlb", "m-nhl", "m-nba", "m-wnba"].forEach(function (id) { if (propsView && $(id)) $(id).setAttribute("aria-pressed", "false"); });
    if (!propsView && typeof sport === "string") { var sb = $("m-" + sport.toLowerCase()); if (sb) sb.setAttribute("aria-pressed", "true"); }
    if (propsView) { $("eyebrow").textContent = "NBA · player props"; renderProps(); }
    else if (typeof sport === "string") $("eyebrow").textContent = sport + " · every market on the game";
  }
  /* the file: one row per player per market per date; a row already graded is a record and stays */
  function applyProps(d, name) {
    if (!d || d.format !== "callsheet3.props" || !Array.isArray(d.games)) throw new Error("not a Super Model props file");
    var added = 0, replaced = 0, kept = 0, inPlay = 0, nextP = props.reduce(function (m, r) { return Math.max(m, r.id || 0); }, 0) + 1;
    var have = {}; props.forEach(function (r, i) { have[propKey(r)] = i; });
    propsPreview = null;
    /* a game that had tipped when the file was written carries in-play lines (23 Oct 2026, the Bulls at the Bucks in the
       second half): its props are left out, so the calls made before tip stand. The run skips such games from today;
       this guards a file from an older run */
    var gen = String(d.generated || ""), startedGames = {};
    (d.games || []).forEach(function (g) { if (g.tip && gen && String(g.tip).slice(0, 19) <= gen.slice(0, 19)) startedGames[g.away + " @ " + g.home] = true; });
    propsRowsFrom(d).forEach(function (row) {
      if (startedGames[row.game]) { inPlay++; return; }
      var k = propKey(row), i = have[k];
      if (i !== undefined) { if (props[i].result) { kept++; return; } row.id = props[i].id; if (props[i].take) row.take = true; if (props[i].pairs) row.pairs = props[i].pairs; props[i] = row; replaced++; }   // the take and pair marks ride through a reload (26 Oct 2026)
      else { row.id = nextP++; have[k] = props.length; props.push(row); added++; }
    });
    saveProps();
    if ($("propsDate") && d.date) $("propsDate").value = d.date;
    showProps(true); renderCalib();
    /* a file that projects nothing (23 Oct 2026, the user's file of the 23rd: 712 props, every one "no history"):
       the run read no ledger, and the file says so from today; the message names the cause instead of leaving the cards empty */
    var incoming = propsRowsFrom(d), none = incoming.length && !incoming.some(propHas), lg = d.ledgers || null, warn = "";
    if (none) {
      var lastSeason = (lg && lg.last && lg.last.season) || "2025-26", lastFile = "nba-ledger-" + lastSeason.replace("-", "") + ".json";
      warn = " <b>None of the " + incoming.length + " props has a projection.</b>" +
             (lg ? " The run read " + (lg.this ? lg.this.games : 0) + " games of " + esc((lg.this || {}).season || "this season") + " and " + (lg.last ? lg.last.games : 0) + " of " + esc(lastSeason) +
                   (lg.folder ? " in " + esc(lg.folder) : "") + "." : "") +
             (!lg || (lg.last || {}).games === 0
               ? " <b>Last season's ledger, " + esc(lastFile) + ", was not read.</b> With a game or two this season nobody has the sixty minutes a projection needs, so every prop reads no history. Put that file back in the slate folder beside slate.py" +
                 ((lg && (lg.this || {}).games === 0) ? ", with this season's ledger beside it" : "") + ", run the props again from that folder, and load the new file; it replaces these."
               : "");
    }
    /* a file whose projections rest on this season alone (25 Oct 2026, the user's file of the 24th: 140 projected, 135 of them
       "no last season to blend", 263 with no side at all): the run read no last-season ledger, and nothing had said so */
    var withSide = incoming.filter(propHas), noHist = incoming.length - withSide.length,
        thin = withSide.filter(function (r) { return (r.why || []).some(function (w) { return /no last season to blend/.test(String(w)); }); }).length;
    if (!none && withSide.length && ((lg && lg.last && !lg.last.games) || (!lg && thin > withSide.length / 2))) {
      var lastSeason2 = (lg && lg.last && lg.last.season) || "2025-26";
      warn += " <b>Last season's ledger, nba-ledger-" + esc(lastSeason2.replace("-", "")) + ".json, was not read by this run:</b> " + thin + " of the " + withSide.length +
              " projections rest on this season's two or three games a player, and " + noHist + (noHist === 1 ? " prop has" : " props have") +
              " no history at all. Put the file back beside slate.py, run the props again before tip, and load the new file; it replaces these.";
    }
    propsSay("Props " + (name ? "<b>" + esc(name) + "</b> " : "") + "loaded: <b>" + added + "</b> new, " + replaced + " replaced, " + kept + " graded and left as " +
             (kept === 1 ? "it was" : "they were") + (inPlay ? ", <b>" + inPlay + "</b> on " + Object.keys(startedGames).length + " game" + (Object.keys(startedGames).length === 1 ? "" : "s") + " already under way left out (in-play lines; the calls made before tip stand)" : "") +
             ". A prop is the slate's call as made; the page does not rescore it." + warn);
    return { added: added, replaced: replaced, kept: kept };
  }
  /* the grade: the nba-grade file carries each game's box by ESPN id,
     [name, minutes, points, rebounds, assists, threes]; a player with a prop
     and no box line did not play, and the row is void, as the books void it */
  function propActual(r, box) {
    var b = box[r.pid]; if (!b) return null;
    var idx = { pts: 2, reb: 3, ast: 4, tpm: 5 }, v;
    if (PROPS_COMBO[r.mk]) {
      v = 0;
      for (var i = 0; i < PROPS_COMBO[r.mk].length; i++) { var c = b[idx[PROPS_COMBO[r.mk][i]]]; if (c === null || c === undefined) { v = null; break; } v += c; }
    } else v = b[idx[r.mk]];
    return (v === null || v === undefined) ? undefined : v;
  }
  var propsMinsFilled = 0;   // graded props whose minutes a second load of the night's grade file filled in (25 Oct 2026)
  function gradeProps(d) {
    if (!d || !Array.isArray(d.games)) return 0;
    var n = 0, filled = 0;
    d.games.forEach(function (g) {
      if (!g.box) return;
      props.forEach(function (r) {
        if ((r.gdate || "") !== (g.gdate || d.date || "")) return;
        if (propsCanon(r.away) !== propsCanon(g.away) || propsCanon(r.home) !== propsCanon(g.home)) return;
        var bl = g.box[r.pid] || [], mins = bl[1] === null || bl[1] === undefined ? null : bl[1];   // his minutes that night, for the panel's last-games row
        var what = bl[6] && typeof bl[6] === "object" && Array.isArray(bl[6][r.mk]) ? bl[6][r.mk] : null;   // what happened on his game, per market (27 Oct 2026)
        if (r.result) {
          /* graded already: the result stands, and only the minutes fill in when the row has none (25 Oct 2026, the user:
             "could the older graded props get their minutes filled in too?"): load the night's grade file again */
          if ((r.amin === null || r.amin === undefined) && mins !== null) { r.amin = mins; filled++; }
          if (!(r.awhat && r.awhat.length) && what && what.length) { r.awhat = what; filled++; }
          return;
        }
        var v = propActual(r, g.box);
        if (v === undefined) return;
        r.amin = mins;
        if (what && what.length) r.awhat = what;
        if (v === null) { r.result = "void"; r.actual = null; n++; return; }
        r.actual = v;
        r.result = !r.side ? "graded" : (v === r.line ? "push" : ((v > r.line) === (r.side === "OVER") ? "win" : "loss"));
        n++;
      });
    });
    propsMinsFilled = filled;
    if (n || filled) { saveProps(); renderProps(); }
    return n;
  }
  /* the record: every graded prop with a side, by market, by band, by side; says is the blended chance.
     propsRecordHtml() is the block on the card's "Is it working" section; propsRecordHtml(true) is the
     fuller one on the Props tab itself (22 Oct 2026, the user: "a section at the top similar to the
     'is this working' on the other models"): the bands as tiles, the edge the sheet claimed, the centre
     the chance was read around (the mean to 21 Oct, the median from 22 Oct), night by night, and
     says against does by the chance claimed */
  var PROPS_EDGE_BUCKETS = ["10+ points of edge", "6 to 10 points", "3 to 6 points", "under 3 points", "no edge"];
  var PROPS_CHANCE_BUCKETS = ["50 to 55%", "55 to 60%", "60 to 65%", "65% and up"];
  function propsEdgeBucket(r) { var e = (r.edge || 0) * 100; return e >= 10 ? PROPS_EDGE_BUCKETS[0] : e >= 6 ? PROPS_EDGE_BUCKETS[1] : e >= 3 ? PROPS_EDGE_BUCKETS[2] : e > 0 ? PROPS_EDGE_BUCKETS[3] : PROPS_EDGE_BUCKETS[4]; }
  function propsChanceBucket(r) { var c = (r.chance || 0) * 100; return c < 55 ? PROPS_CHANCE_BUCKETS[0] : c < 60 ? PROPS_CHANCE_BUCKETS[1] : c < 65 ? PROPS_CHANCE_BUCKETS[2] : PROPS_CHANCE_BUCKETS[3]; }
  function propsCentre(r) { return (r.why || []).some(function (w) { return /around the median/.test(String(w)); }) ? "median" : "mean"; }
  function propsRecordHtml(full) {
    var graded = props.filter(function (r) { return r.result && r.result !== "graded"; });
    if (!graded.length) return "";
    var mk = function () { return { n: 0, w: 0, l: 0, p: 0, v: 0, says: 0, units: 0 }; };
    var all = mk(), byMk = {}, byBand = {}, bySide = {}, byEdge = {}, byChance = {}, byDate = {}, byDateBet = {}, byCentre = {}, byTake = mk();
    /* the same-game pairs' record (26 Oct 2026): each graded date's tickets as the night built them, a ticket won when both legs did */
    var byPair = mk(), byPairTake = mk(), pairDates = {};
    graded.forEach(function (r) { if (r.gdate) pairDates[r.gdate] = true; });
    var pairSink = function (s) { return function (t) {
      var res = propsPairRes(t); if (!res) return;
      if (res === "push") { s.p++; return; }
      s.n++; s.says += t.chance;
      if (res === "win") { s.w++; s.units += propsPairUnits(t, res); } else { s.l++; s.units -= 1; }
    }; };
    Object.keys(pairDates).forEach(function (d) { propsPairs(d, props).forEach(pairSink(byPair)); pairTakesOn(d).forEach(pairSink(byPairTake)); });
    var dec = function (price) { return price > 0 ? 1 + price / 100 : 1 + 100 / (-price); };
    graded.forEach(function (r) {
      var d = r.gdate || "?";
      var sinks = [all, byMk[r.mk] || (byMk[r.mk] = mk()), byBand[r.band] || (byBand[r.band] = mk()), bySide[r.side] || (bySide[r.side] = mk()),
                   byEdge[propsEdgeBucket(r)] || (byEdge[propsEdgeBucket(r)] = mk()), byChance[propsChanceBucket(r)] || (byChance[propsChanceBucket(r)] = mk()),
                   byDate[d] || (byDate[d] = mk()), byCentre[propsCentre(r)] || (byCentre[propsCentre(r)] = mk())];
      if (r.band === "BET") sinks.push(byDateBet[d] || (byDateBet[d] = mk()));
      if (r.take) sinks.push(byTake);   // the props marked as taken (26 Oct 2026)
      sinks.forEach(function (s) {
        if (r.result === "void") { s.v++; return; }
        if (r.result === "push") { s.p++; return; }
        s.n++; s.says += r.chance;
        if (r.result === "win") { s.w++; s.units += dec(r.price) - 1; } else { s.l++; s.units -= 1; }
      });
    });
    var rec = function (s) { return s.w + "-" + s.l + (s.p ? "-" + s.p : ""); };
    var says = function (s) { return s.n ? (s.says / s.n * 100).toFixed(1) + "%" : "—"; };
    var does = function (s) { return s.n ? (s.w / s.n * 100).toFixed(1) + "%" : "—"; };
    var line = function (s) {
      if (!s.n) return "pushes only";
      return "says " + says(s) + " · does " + does(s) + " (±" + (100 / Math.sqrt(s.n) / 2).toFixed(1) + ") · " + sgn(s.units, 2) + "u";
    };
    /* the tab's tiles carry colour (22 Oct 2026, the user: "jazz that up with some colors"): the record
       green when the units are up and red when down, does marked against says the same way */
    var tile = function (label, s, parts) {
      var cls = full && s.n ? (s.units > 0 ? ' class="good"' : s.units < 0 ? ' class="bad"' : '') : '';
      var body = line(s);
      if (full && s.n) body = "says " + says(s) + ' · does <span class="does ' + (s.w / s.n >= s.says / s.n ? 'up' : 'down') + '">' + does(s) + '</span> (±' + (100 / Math.sqrt(s.n) / 2).toFixed(1) + ') · <span class="units">' + sgn(s.units, 2) + 'u</span>';
      return '<div' + cls + '><p class="k">' + esc(label) + '</p><p class="v">' + rec(s) + '</p><p class="s">' + body + (s.v ? ' · ' + s.v + ' void' : '') + '</p>' +
        (parts && parts.length ? '<p class="s sides">' + esc(parts.join(" · ")) + '</p>' : '') + '</div>';
    };
    var parts = [];
    ["OVER", "UNDER"].forEach(function (sd) { if (bySide[sd]) parts.push(sd.toLowerCase() + " " + rec(bySide[sd])); });
    ["BET", "LEAN", "no edge"].forEach(function (b) { if (byBand[b]) parts.push(b + " " + rec(byBand[b]) + (byBand[b].n ? " " + sgn(byBand[b].units, 1) + "u" : "")); });
    if (byTake.n || byTake.p) parts.push("taken " + rec(byTake) + (byTake.n ? " " + sgn(byTake.units, 1) + "u" : ""));
    if (byPair.n || byPair.p) parts.push("same-game pairs " + rec(byPair) + (byPair.n ? " " + sgn(byPair.units, 1) + "u" : ""));
    if (byPairTake.n || byPairTake.p) parts.push("pairs taken " + rec(byPairTake) + (byPairTake.n ? " " + sgn(byPairTake.units, 1) + "u" : ""));
    var markets = PROPS_ORDER.map(function (k) { return byMk[k] ? tile(PROPS_LABEL[k], byMk[k], []) : ""; }).join("");
    var verdict = 'The props are a priori: the pooled rules behind them were measured on last season\'s box scores. Read the BET band against the rest and <i>does</i> against <i>says</i>; under 100 graded props nothing here is a reading. ' +
                  'Measured on the first ten nights (30 Oct 2026, 4,321 graded props): the model\'s own lean added nothing to the book\'s price (the best weight on it was none; where it stood ten points from Pinnacle the outcome followed Pinnacle), the over\'s shade is real (the under landed 53.2% at prices saying 50.7%), and a starter\'s minutes follow the game script. From the 30th the sheet runs with the market as its spine (the model at a ninth, the over read 2.5 points lower) and the game script on starters\' minutes; the nights before carry the old weights.';
    if (!full) {
      var h = '<div class="subhead" data-sport="PROPS">NBA player props <span class="tag">' + graded.length + ' graded · the slate\'s call as made, at the price posted · says is the blended chance</span></div>';
      h += '<div class="calib" data-sport="PROPS">' + tile("Every prop with a side", all, parts) + markets + '</div>';
      h += '<div class="verdict">' + verdict + '</div>';
      return h;
    }
    var dates = Object.keys(byDate).sort();
    var h2 = '<div class="calib" data-sport="PROPS-TAB">' + tile("Every prop with a side", all, parts.slice(0, 2));
    ["BET", "LEAN", "no edge"].forEach(function (b) { if (byBand[b]) h2 += tile(b === "no edge" ? "No edge: the book's own side" : b + " band", byBand[b], []); });
    if (byTake.n || byTake.p) h2 += tile("Taken: the props you marked", byTake, []);
    if (byPair.n || byPair.p) h2 += tile("Same-game pairs, at the parlay price", byPair, []);
    h2 += '</div>';
    h2 += '<div class="subhead">By market</div><div class="calib" data-sport="PROPS-MK">' + markets + '</div>';
    h2 += '<div class="subhead">By the edge the sheet claimed <span class="tag">the chance less what the price needs</span></div><div class="calib" data-sport="PROPS-EDGE">' +
          PROPS_EDGE_BUCKETS.map(function (b) { return byEdge[b] ? tile(b, byEdge[b], []) : ""; }).join("") + '</div>';
    h2 += '<div class="subhead">By the centre the chance was read around <span class="tag">the mean to 21 Oct 2026, the median from the 22nd: a box-score stat skews right</span></div><div class="calib" data-sport="PROPS-CENTRE">' +
          (byCentre.mean ? tile("Called at the mean, to 21 Oct", byCentre.mean, []) : "") + (byCentre.median ? tile("Called at the median, from 22 Oct", byCentre.median, []) : "") + '</div>';
    h2 += '<div class="subhead">Night by night <span class="tag">' + dates.length + ' night' + (dates.length === 1 ? '' : 's') + ' graded</span></div>' +
          '<table class="form" id="propsNights"><thead><tr><th>Night</th><th>Record</th><th>Says</th><th>Does</th><th>Units</th><th>BET band</th></tr></thead><tbody>' +
          dates.slice().reverse().map(function (d) {
            var s = byDate[d], b = byDateBet[d];
            var up = s.n && s.w / s.n >= s.says / s.n;
            return '<tr><td>' + esc(gameDate(d)) + '</td><td class="' + (s.units >= 0 ? 'pos' : 'neg') + '">' + rec(s) + (s.v ? ' <span class="dim">' + s.v + ' void</span>' : '') + '</td><td>' + says(s) + '</td><td class="' + (up ? 'pos' : 'neg') + '">' + does(s) + '</td><td class="' + (s.units >= 0 ? 'pos' : 'neg') + '">' + sgn(s.units, 1) + 'u</td>' +
                   '<td class="' + (b ? (b.units >= 0 ? 'pos' : 'neg') : '') + '">' + (b ? rec(b) + ' ' + sgn(b.units, 1) + 'u' : '—') + '</td></tr>';
          }).join("") + '</tbody></table>';
    h2 += '<div class="subhead">Says against does, by the chance claimed <span class="tag">a calibrated sheet reads the same in both columns</span></div>' +
          '<table class="form" id="propsLadder"><thead><tr><th>Chance claimed</th><th>Props</th><th>Says</th><th>Does</th><th>±</th><th>Units</th></tr></thead><tbody>' +
          PROPS_CHANCE_BUCKETS.map(function (b) {
            var s = byChance[b]; if (!s || !s.n) return "";
            var up = s.w / s.n >= s.says / s.n;
            return '<tr><td>' + esc(b) + '</td><td>' + s.n + '</td><td>' + says(s) + '</td><td class="' + (up ? 'pos' : 'neg') + '">' + does(s) + '</td><td>' + (100 / Math.sqrt(s.n) / 2).toFixed(1) + '</td><td class="' + (s.units >= 0 ? 'pos' : 'neg') + '">' + sgn(s.units, 1) + 'u</td></tr>';
          }).join("") + '</tbody></table>';
    h2 += '<div class="verdict">' + verdict + ' The first two nights (829 props) were called at the mean and read 423-406, the sheet saying 55.7% and doing 51.0%; ' +
          're-scored at the median they read 452-377 with the say-so within a point of the done. The median tile is the one to read from here, on its own, once it has a hundred props.</div>';
    return h2;
  }
  function propResChip(r) {
    if (!r.result) return '';
    var cls = r.result === "win" ? "win" : r.result === "loss" ? "loss" : "push";
    return ' <span class="chip ' + cls + '">' + esc(r.result === "void" ? "VOID · did not play" : r.result.toUpperCase()) + (r.actual !== null && r.actual !== undefined ? " · " + r.actual : "") + '</span>';
  }
  /* the props you take (26 Oct 2026, the user: "a select or picked option for the props or bets I take, that way I
     can see on the page the ones I will place"): a Take button on every projected prop, on the best cards, the table
     and the panel; the mark is a flag on the row, kept with the props, carried through a reload of the night's file,
     listed under Taking on this tab and under Taking tonight on the day board, and graded on its own line in the
     record. A graded prop cannot be marked after the fact. Nothing here changes a chance or a band */
  function propTakeBtn(r, big) {
    if (!propHas(r)) return "";
    if (r.result) return r.take ? ' <span class="chip taken">TAKEN</span>' : "";
    return '<button type="button" class="takebtn' + (r.take ? ' on' : '') + (big ? ' big' : '') + '" data-ptake="' + r.id + '" title="' +
           (r.take ? 'Marked as a bet you are placing: click to unmark it' : 'Mark this prop as a bet you are placing') + '">' + (r.take ? '&#10003; Taking' : (big ? 'Take this prop' : 'Take')) + '</button>';
  }
  function propTakeCard(r) {
    return '<div class="pk taking" data-prop="' + r.id + '"><div class="n1">TAKING · NBA PROP · ' + esc(r.band) + '</div>' +
      '<div class="n2">' + esc(r.name) + ' ' + esc(r.side) + ' ' + r.line + ' ' + esc(PROPS_LABEL[r.mk] || r.mk) + '</div>' +
      '<div class="n3">' + (r.chance * 100).toFixed(1) + '% · ' + sgn(r.price, 0) + ' needs ' + (r.need * 100).toFixed(1) + '%' + propResChip(r) + '</div>' +
      '<div class="n4">' + esc(r.game) + ' · ' + esc(r.book) + ' · projected ' + r.proj + '</div><div class="n6">' + propTakeBtn(r) + '</div></div>';
  }
  function togglePropTake(id) {
    var r = propById(id); if (!r || !propHas(r)) return;
    if (r.result) { propsSay("<b>" + esc(r.name) + "</b> is graded: a prop is marked before the game, not after."); return; }
    r.take = !r.take;
    if (!propsPreview) saveProps();
    renderProps(); renderCalib(); if (typeof renderBoard === "function") renderBoard();
    refreshPropDetail();
  }
  /* the last games (20 Oct 2026, the user: "highlight their scored numbers so it's easy to see"):
     the stat of each game in its own mark, green over the prop's line, red under it, grey on it,
     and a tally at the end of how many of them cleared the number */
  function propsLogMark(v, line) {
    var val = (v === null || v === undefined || v === "") ? null : +v;
    var cls = val === null || line === null || line === undefined || isNaN(+line) ? "" : (val > +line ? " over" : val < +line ? " under" : " push");
    return '<b class="lg' + cls + '">' + (val === null ? "?" : esc(String(v))) + '</b>';
  }
  function propsLogTally(r) {
    var vals = (r.log || []).map(function (g) { return g[4]; }).filter(function (v) { return v !== null && v !== undefined && v !== "" && !isNaN(+v); });
    if (!vals.length || r.line === null || r.line === undefined || isNaN(+r.line)) return "";
    var over = vals.filter(function (v) { return +v > +r.line; }).length, push = vals.filter(function (v) { return +v === +r.line; }).length;
    return ' <span class="dim">(' + over + " of " + vals.length + " over " + r.line + (push ? ", " + push + " on it" : "") + ")</span>";
  }
  /* ---- the detail panel (21 Oct 2026, the user: "when I click one, could you have it open a
     page or something with the details of the prop instead of in the list below"): a best-prop
     card opens the prop on its own panel over the page, the numbers as tiles, the why as a
     list, the last games as a table with the marks, every book's line; a table row still folds
     its why open below it. Escape, the Close button or a click outside puts it away ---- */
  function propById(id) {
    var s = propsSource();
    for (var i = 0; i < s.length; i++) if (String(s[i].id) === String(id)) return s[i];
    return null;
  }
  /* what moves it (21 Oct 2026, the user: "highlight the areas of the prop bet that are helping
     with the prediction the most"): the slate writes each factor's push on the projection in the
     stat's units (parts: regulars out, their centre out on a big man's rebounds (28 Oct 2026),
     pace, the defence, the matchup, last season's prior, the minutes trend), each pointing at
     its why line. Ranked by size, largest first; a push toward the pick's side helps, away
     from it hurts */
  function propsLevers(r) {
    return (r.parts || []).filter(function (p) { return p && isFinite(+p.eff); }).slice().sort(function (a, b) { return Math.abs(b.eff) - Math.abs(a.eff); });
  }
  function propsLeverHelps(r, eff) { return r.side === "UNDER" ? eff < 0 : eff > 0; }
  function propsLeversLine(r) {
    var lv = propsLevers(r).slice(0, 2);
    return lv.length ? lv.map(function (p) { return esc(p.t) + " " + sgn(+p.eff, 1); }).join(" · ") : "";
  }
  /* the simulation on the prop (26 Oct 2026, the user: "confirm the simulation is being run for the props as
     well, and attach the results to the player props when I select them to see what the simulation did in
     regards to how it was scored"): the props run plays each game the same 10,000 times as the slate, from
     the same profiles, and the file carries on every prop his club's points in those runs with the middle
     half, against the club's points a game by its ratings alone, the blowout and overtime chances and the
     game's possessions. What the SCORE takes from the simulation is the matchup lever (the club's efficiency
     into tonight's defence, from the same profiles, at the half weight that measured; none on rebounds), so
     that lever is the tile in colour; the sim's full-weight read of his number is beside the projection and
     the rest is shown, not scored */
  function propsSimHtml(r, tile) {
    var s = r.sim, lab = PROPS_LABEL[r.mk] || r.mk, club = r.team || "his club";
    var match = (r.parts || []).filter(function (p) { return p && p.k === "match" && isFinite(+p.eff); })[0] || null;
    var h = '<div class="pd-sim"><h4>Simulation' + (s ? ' <span class="dim">· ' + esc(r.game) + ' played ' + esc(Number(s.runs).toLocaleString()) + ' times</span>' : '') + '</h4>';
    if (!s) {
      h += '<p class="note">This file\'s run carried no simulation on the props' + (match ? ', though the matchup lever (' + sgn(+match.eff, 1) + ') came from its profiles' : '') +
           '. A props run with the current slate.py plays the game 10,000 times and attaches it here.</p></div>';
      return h;
    }
    var pc = function (v) { return (v * 100).toFixed(v * 100 >= 10 ? 0 : 1) + "%"; };
    var vsProj = s.read !== null && s.read !== undefined ? sgn(s.read - r.proj, 1) + " against the model's " + esc(String(r.proj)) : "no read";
    var mEff = match ? sgn(+match.eff, 1) : "0.0";
    var mSub = r.mk === "reb" ? "scored at no weight on rebounds (measured)" : match ? "the scored part, at half weight" + (propsLeverHelps(r, +match.eff) ? ", toward the " + esc(r.side) : ", against the " + esc(r.side)) : "no lever on this prop";
    h += '<div class="pd-simtiles">' +
      tile(esc(club) + " points", esc(String(s.team_pts)), "middle half " + esc(String(s.team_lo)) + "–" + esc(String(s.team_hi)) + (s.team_ppg ? " · " + esc(String(s.team_ppg)) + " a game by the ratings" : "")) +
      tile("Sim's read", s.read === null || s.read === undefined ? "–" : esc(String(s.read)), "his per 36 at his minutes × " + (s.ratio ? esc(s.ratio.toFixed(2)) : "–") + "; " + vsProj) +
      tile("Matchup lever", mEff, mSub, match && r.mk !== "reb" ? (propsLeverHelps(r, +match.eff) ? "good" : "bad") : "") +
      tile("Blowout", pc(s.blowout), "15 or more either way; shown, not scored") +
      tile("Overtime", pc(s.ot), "chance of extra minutes") +
      tile("Possessions", esc(String(s.poss)), "the game's pace in the runs") +
      '</div>';
    h += '<p class="pd-base">The slate played the game ' + esc(Number(s.runs).toLocaleString()) + ' times from the two clubs\' profiles (ratings, pace, shot mix, rest) and the injury report as it stood at the run' +
         (s.out ? ' (' + esc(club) + '\'s regulars out took ' + esc(Math.abs(+s.out).toFixed(1)) + ' per 100 off its offence)' : '') + '; a later run carries the later report. It puts ' + esc(club) + ' at <b>' + esc(String(s.team_pts)) +
         '</b> points, the middle half ' + esc(String(s.team_lo)) + ' to ' + esc(String(s.team_hi)) + (s.team_ppg ? ', against ' + esc(String(s.team_ppg)) + ' a game by the ratings alone' : '') +
         (s.ratio ? ', so the matchup is worth ×' + esc(s.ratio.toFixed(2)) + ' on the club\'s scoring' : '') + '. ' +
         (s.read !== null && s.read !== undefined ? 'Applied in full to his ' + esc(String(r.rate36)) + ' per 36 at ' + esc(String(r.mins)) + ' minutes, that reads <b>' + esc(String(s.read)) + '</b> ' + esc(lab) + ' against the model\'s ' + esc(String(r.proj)) + '. ' : '') +
         'What the score takes from the simulation is the <b>matchup lever</b>, ' + (r.mk === "reb" ? 'none on rebounds, where it measured nothing' : mEff + ' here, at half weight, the weight that measured against 2025-26\'s box scores (full weight counted the defence twice)') +
         '. The blowout chance (' + pc(s.blowout) + ') and overtime (' + pc(s.ot) + ') are shown, not scored: his minutes come from his own last games, and trimming them for a rout made the projection worse out of sample.</p></div>';
    return h;
  }
  function propsDetailHtml(r) {
    var has = propHas(r), lab = PROPS_LABEL[r.mk] || r.mk;
    var tile = function (k, v, s, cls) { return '<div class="pd-tile' + (cls ? ' ' + cls : '') + '"><div class="k">' + esc(k) + '</div><div class="v">' + v + '</div>' + (s ? '<div class="s">' + s + '</div>' : '') + '</div>'; };
    var h = '<div class="pd-band">' + esc(has ? r.band : "no projection") + '</div>';
    h += '<h3>' + esc(r.name) + (r.pos ? ' <span class="tag">' + esc(r.pos) + '</span>' : '') + (r.team ? ' <span class="tag">' + esc(r.team) + '</span>' : '') +
         (r.starter === true ? ' <span class="tag role" title="' + esc(r.start_src || '') + '">starter</span>' : r.starter === false ? ' <span class="tag role" title="' + esc(r.start_src || '') + '">bench</span>' : '') + '</h3>';
    h += '<div class="pd-pick">' + (has ? esc(r.side) + ' ' : '') + esc(String(r.line)) + ' ' + esc(lab) + propResChip(r) + '</div>';
    h += '<div class="pd-sub">' + esc(r.game) + ' · ' + esc(gameDate(r.gdate)) + (r.opp ? ' · ' + (r.athome ? 'at home against ' : 'on the road at ') + esc(r.opp) : '') +
         ' · ' + esc(r.book || "the book") + ' ' + esc(String(r.line)) + ' (' + sgn(r.op, 0) + '/' + sgn(r.up, 0) + ')</div>';
    h += '<div class="pd-take pd-go">' + (has && (propTakeBtn(r, true) || "").length ? propTakeBtn(r, true) + ' ' : '') + propsGoBtn(r, true) + '</div>';
    if (has) {
      h += '<div class="pd-tiles">' +
        tile("Chance", (r.chance * 100).toFixed(1) + "%", "blended: the over is " + (r.pm * 100).toFixed(1) + "% by the model, " + (r.pb * 100).toFixed(1) + "% by the book") +
        tile("Price", sgn(r.price, 0), "needs " + (r.need * 100).toFixed(1) + "%") +
        tile("Edge", sgn(r.edge * 100, 1), "points of chance over the price", r.edge > 0 ? "good" : "bad") +
        tile("Projection", esc(String(r.proj)), "± " + esc(String(r.sd)) + " one sigma") +
        tile("Minutes", esc(String(r.mins)), "projected") +
        tile("Per 36", esc(String(r.rate36)), esc(lab) + " per 36 minutes") +
        (r.usg !== null && r.usg !== undefined ? tile("Usage", esc(String(r.usg)) + "%", "of his club's possessions while on; " + (r.starter === true ? "a starter" : r.starter === false ? "off the bench" : "role unknown") + (r.sdf && r.sdf !== 1 ? ", the miss read at " + esc(String(r.sdf)) + " sigmas (measured)" : "")) : "") +
        '</div>';
      /* the floors (26 Oct 2026): the number he clears 95, 90 and 80% of nights by the model, and his other markets' 95% floors tonight */
      var f95 = propFloor(r, 95), f90 = propFloor(r, 90), f80 = propFloor(r, 80);
      if (f95 || f90 || f80) {
        var mine = propsSource().filter(function (x) { return String(x.pid) === String(r.pid) && (x.gdate || "") === (r.gdate || "") && propHas(x) && !PROPS_COMBO[x.mk]; })
          .sort(function (a, b) { return ["pts", "reb", "ast", "tpm"].indexOf(a.mk) - ["pts", "reb", "ast", "tpm"].indexOf(b.mk); });
        var ladder = mine.map(function (x) { var f = propFloor(x, 95); return f ? f + "+ " + (PROPS_LABEL[x.mk] || x.mk) : null; }).filter(function (s) { return s; });
        h += '<h4>Floors <span class="dim">· the number he clears, by the model</span></h4><p class="pd-floors">' +
             (f95 ? '95% of nights: <b>' + f95 + '+</b>' : '') + (f90 ? ' · 90%: <b>' + f90 + '+</b>' : '') + (f80 ? ' · 80%: <b>' + f80 + '+</b>' : '') + ' ' + esc(lab) +
             (ladder.length >= 2 ? '. His 95% floors tonight: <b>' + ladder.join(', ') + '</b>' + (ladder.length >= 3 ? ' (one man\'s three 95% floors all cleared 96.5% of nights last season, his minutes carrying them together)' : '') : '') +
             '. Measured on 2025-26: the 95% floors cleared 97.5% of nights, the 90% 93%, the 80% 82%; posted as a whole number the 95% line cleared 98%. Honest to conservative, and priced by the book as an alternate line.</p>';
      }
    } else {
      h += '<p class="note">' + esc((r.why && r.why[0]) || "No projection on this prop.") + '</p>';
    }
    h += propsFivesHtml(r);
    var levers = has ? propsLevers(r) : [];
    /* the Why's marked lines (26 Oct 2026, the user: "are those the two biggest reasons for the pick?"; they had been the two
       biggest by size in either direction, so a pace lever against the over read as a reason for it): the two biggest levers
       toward the pick's side are bold, the biggest against it is tagged, a push under 0.05 in the stat's units counting as neither */
    var felt = levers.filter(function (p) { return Math.abs(+p.eff) >= 0.05; });
    var top = felt.filter(function (p) { return propsLeverHelps(r, +p.eff); }).slice(0, 2).map(function (p) { return +p.i; });
    var against = felt.filter(function (p) { return !propsLeverHelps(r, +p.eff); }).slice(0, 1).map(function (p) { return +p.i; });
    if (levers.length && r.base !== undefined && r.base !== null) {
      var maxE = Math.max.apply(null, levers.map(function (p) { return Math.abs(+p.eff); }).concat([0.01])), gap = r.proj - r.line;
      var hasMatch = levers.some(function (p) { return p.k === "match"; }), hasOppc = levers.some(function (p) { return p.k === "oppc"; }), tally = propsLeverTally(r);
      h += '<h4>What moves it' + (tally.n ? ' <span class="dim">· ' + esc(tally.words) + '</span>' : '') + '</h4><p class="pd-base">Starts from <b>' + esc(String(r.base)) + '</b>, his ' + esc(String(r.rate36)) + ' per 36 at his minutes; the regulars out' + (hasOppc ? ', their centre out' : '') + ', pace' + (hasMatch ? ', the matchup' : '') + ' and the defence take it to <b>' + esc(String(r.proj)) +
           '</b>, ' + sgn(gap, 1) + ' against the line. Green pushes toward the ' + esc(r.side || "pick") + ', red away from it. The prior and the minutes trend say what sits inside the start.</p>';
      h += '<div class="pd-levers">' + levers.map(function (p, i) {
        var helps = propsLeverHelps(r, +p.eff), w = Math.max(3, Math.round(Math.abs(+p.eff) / maxE * 100));
        return '<div class="lever' + (helps ? ' helps' : ' hurts') + (i === 0 ? ' top' : '') + '"><div class="lt">' + esc(p.t) + (i === 0 ? ' <span class="tag">biggest lever</span>' : '') + '</div>' +
               '<div class="lb"><span style="width:' + w + '%"></span></div><div class="lv">' + sgn(+p.eff, 1) + '</div></div>';
      }).join("") + '</div>';
    }
    if (has) h += propsSimHtml(r, tile);
    if (r.why && r.why.length) h += '<h4>Why' + (felt.length ? ' <span class="dim">· ' + (top.length ? 'the biggest reason' + (top.length > 1 ? 's' : '') + ' for the ' + esc(r.side || "pick") + ' in green' : 'no lever toward the ' + esc(r.side || "pick")) + (against.length ? (top.length ? ', ' : '; ') + 'the biggest against it in red' : '') + '</span>' : '') + '</h4><ul class="pd-why">' + r.why.map(function (w, i) {
      var rank = top.indexOf(i), cls = rank >= 0 ? ' class="lever-line"' : against.indexOf(i) >= 0 ? ' class="lever-against"' : '';
      return '<li' + cls + '>' + esc(w) + (rank >= 0 ? ' <span class="tag helps">the ' + (rank === 0 ? '' : 'second ') + 'biggest for the ' + esc(r.side || "pick") + '</span>' : '') +
             (against.indexOf(i) >= 0 ? ' <span class="tag hurts">the biggest against the ' + esc(r.side || "pick") + '</span>' : '') + '</li>';
    }).join("") + '</ul>';
    /* the game the prop was on joins the list once it is graded (25 Oct 2026, the user: "they only show the last
       date of 10/23 and not 10/24 for the props that were on yesterday"): the last games are the history the
       call was made from, as the file carried them, and the graded night goes under them with his minutes from
       the box line and the stat marked like the rest; a prop graded before the minutes were kept shows a dash */
    var played = !!(r.result && r.result !== "graded");
    if ((r.log && r.log.length) || played) {
      /* what happened (26 Oct 2026, the user, on P.J. Washington's panel: "on the last games, the ones that didn't cover, is there a
         way to put next to those losses what may have been the factor?"): the slate writes beside each game what the box says,
         the night's causes first (a regular back or out, a blowout, his role), then his minutes, shots and shooting against his
         season's, then overtime and the pace; the first is bold, red under the line and green over it. A file from before carries
         none, and the column stays away. The graded night's own line gets his minutes against the games above it */
      var what = (r.log || []).some(function (g) { return g[5] && g[5].length; }) || !!(r.awhat && r.awhat.length);
      var whatCell = function (f, v) {
        if (!f || !f.length) return '<td class="pd-what"></td>';
        var side = v === null || v === undefined || r.line === null || r.line === undefined || isNaN(+r.line) ? "" : (+v > +r.line ? " over" : +v < +r.line ? " under" : "");
        return '<td class="pd-what"><b class="' + side.trim() + '">' + esc(f[0]) + '</b>' + (f.length > 1 ? ' · ' + f.slice(1).map(esc).join(' · ') : '') + '</td>';
      };
      var thisWhat = function () {
        if (r.awhat && r.awhat.length) return r.awhat;   // the grade file's own line for the night (27 Oct 2026)
        var mins = (r.log || []).map(function (g) { return +g[3]; }).filter(function (m) { return isFinite(m) && m > 0; });
        if (r.result === "void") return ["did not play"];
        if (!mins.length || r.amin === null || r.amin === undefined) return [];
        var avg = mins.reduce(function (a, b) { return a + b; }, 0) / mins.length, d = +r.amin - avg;
        return Math.abs(d) >= 4 ? [Math.round(+r.amin) + " min, " + Math.round(Math.abs(d)) + (d < 0 ? " under" : " over") + " his usual " + Math.round(avg)] : [];
      };
      h += '<h4>Last games' + propsLogTally(r) + (what ? ' <span class="dim">· what the box says happened, the biggest factor first</span>' : '') + '</h4><table class="form pd-log"><thead><tr><th>Date</th><th>Opp</th><th>Min</th><th>' + esc(lab) + '</th>' + (what ? '<th>What happened</th>' : '') + '</tr></thead><tbody>' +
        (r.log || []).map(function (g) {
          return '<tr><td>' + esc(String(g[0] || "").slice(5)) + '</td><td>' + esc((g[2] ? "v " : "@ ") + (g[1] || "")) + '</td><td>' + esc(String(g[3] === null || g[3] === undefined ? "" : g[3])) + '</td><td>' + propsLogMark(g[4], r.line) + '</td>' + (what ? whatCell(g[5], g[4]) : '') + '</tr>';
        }).join("") +
        (played ? '<tr class="this"><td>' + esc(String(r.gdate || "").slice(5)) + '</td><td>' + esc((r.athome ? "v " : "@ ") + (r.opp || "")) + ' <span class="tag">this game</span></td><td>' +
                  esc(r.amin === null || r.amin === undefined ? "–" : String(r.amin)) + '</td><td>' + (r.result === "void" ? '<b class="lg">DNP</b>' : propsLogMark(r.actual, r.line)) + '</td>' + (what ? whatCell(thisWhat(), r.actual) : '') + '</tr>' : '') +
        '</tbody></table>';
    }
    var bks = Object.keys(r.books || {});
    if (bks.length) {
      h += '<h4>Every book</h4><table class="form pd-books"><thead><tr><th>Book</th><th>Line</th><th>Over</th><th>Under</th></tr></thead><tbody>' + bks.map(function (b) {
        var x = r.books[b] || [];
        return '<tr' + (b === r.book ? ' class="carded"' : '') + '><td>' + esc(b) + (b === r.book ? ' <span class="tag">carded</span>' : '') + '</td><td>' + esc(String(x[0])) + '</td><td>' + (x[1] === null || x[1] === undefined ? "" : sgn(+x[1], 0)) + '</td><td>' + (x[2] === null || x[2] === undefined ? "" : sgn(+x[2], 0)) + '</td></tr>';
      }).join("") + '</tbody></table>';
    }
    h += '<p class="note">A prop is the slate\'s call as made at the price posted; the page does not rescore it, and the Props record tile is the test.</p>';
    return h;
  }
  /* a best-prop card or a row of the Every-prop table opens the panel (22 Oct 2026, the user:
     "the same for the entries on the list so they are easy to review"); Previous / Next and the
     arrow keys walk the table's order from there */
  function openPropDetail(id) {
    var r = propById(id), dlg = $("propDetail"); if (!r || !dlg) return;
    propDetailId = String(id); propDetailKind = "prop";
    $("propDetailBody").innerHTML = propsDetailHtml(r);
    var i = propsOrder.indexOf(propDetailId), nav = $("propDetailNav");
    if (nav) {
      nav.hidden = i < 0 || propsOrder.length < 2;
      $("propDetailPos").textContent = i >= 0 ? (i + 1) + " of " + propsOrder.length : "";
      $("propDetailPrev").disabled = i <= 0;
      $("propDetailNext").disabled = i < 0 || i >= propsOrder.length - 1;
    }
    dlg.hidden = false; dlg.scrollTop = 0;
    document.body.classList.add("noscroll");
    if ($("propDetailClose")) $("propDetailClose").focus();
  }
  function stepPropDetail(d) {
    var order = propDetailKind === "pair" ? pairsOrder : propsOrder, i = order.indexOf(propDetailId); if (i < 0) return;
    var j = i + d; if (j < 0 || j >= order.length) return;
    if (propDetailKind === "pair") openPairDetail(order[j]); else openPropDetail(order[j]);
  }
  function closePropDetail() {
    var dlg = $("propDetail"); if (!dlg) return;
    dlg.hidden = true; propDetailId = null; propDetailKind = "prop";
    document.body.classList.remove("noscroll");
  }
  function renderProps() {
    var v = $("propsView"); if (!v) return;
    var dates = propsDates(), sel = $("propsDate");
    if (!sel.value || dates.indexOf(sel.value) < 0) sel.value = dates.length ? dates[dates.length - 1] : "";
    var date = sel.value;
    var rows = propsSource().filter(function (r) { return (r.gdate || "") === date; });
    if ($("propsCalib")) $("propsCalib").innerHTML = propsRecordHtml(true) || '<div class="verdict">Nothing graded yet. The morning\'s grade file (Grade NBA yesterday.bat, then Load slate) grades every prop with a side against the box score, and the record builds here: by band, by market, by the edge claimed, night by night, and says against does.</div>';
    $("propsCount").textContent =(propsPreview ? "EXAMPLE · " : "") + (rows.length ? rows.length + " props on " + gameDate(date) + " · " + dates.length + " date" + (dates.length === 1 ? "" : "s") + " kept"
                                              : (propsSource().length ? "no props on this date" : "no props loaded"));
    var resChip = propResChip;
    var picks = rows.filter(function (r) { return propHas(r) && r.edge > 0; }).sort(function (a, b) { return b.edge - a.edge; });
    $("propsBest").innerHTML = picks.length ? picks.slice(0, 12).map(function (r, i) {
      var tl = propsLeverTally(r);
      return '<div class="pk' + (r.band === "BET" ? ' scored' : '') + '" data-prop="' + r.id + '"><div class="n1">#' + (i + 1) + ' · ' + esc(r.band) + (tl.n ? ' <span class="tag' + (tl.all ? ' agree' : '') + '" title="' + esc(tl.words) + '">levers ' + tl.text + '</span>' : '') + '</div>' +
        '<div class="n2">' + esc(r.name) + ' ' + esc(r.side) + ' ' + r.line + ' ' + esc(PROPS_LABEL[r.mk] || r.mk) + '</div>' +
        '<div class="n3">' + (r.chance * 100).toFixed(1) + '% · ' + sgn(r.price, 0) + ' needs ' + (r.need * 100).toFixed(1) + '% · edge ' + sgn(r.edge * 100, 1) + resChip(r) + '</div>' +
        '<div class="n4">' + esc(r.game) + ' · projected ' + r.proj + ' (±' + r.sd + ') · ' + esc(r.book) + '</div>' +
        (propsLeversLine(r) ? '<div class="n5">Moves it: ' + propsLeversLine(r) + '</div>' : '') +
        (propSimLine(r) ? '<div class="n5 simline' + (propSimAgrees(r) === true ? ' pos' : propSimAgrees(r) === false ? ' neg' : '') + '">' + propSimLine(r) + '</div>' : '') + '<div class="n6">' + propTakeBtn(r) + propsGoBtn(r) + '</div></div>';
    }).join("") : '<div class="empty">' + (rows.length ? 'No prop on this date clears its price.' : 'Load a props file: Run NBA props.bat writes nba-props-DATE.json.') + '</div>';
    /* the simulation's strip (26 Oct 2026): one card a game */
    if ($("propsSim")) $("propsSim").innerHTML = rows.length ? propsSimStripHtml(rows) : '<div class="empty">Load a props file and each game\'s simulation lands here.</div>';
    /* the props marked as taken on the date (26 Oct 2026), above the best list */
    var taken = rows.filter(function (r) { return r.take && propHas(r); }), takenPairs = pairTakesOn(date), nTaken = taken.length + takenPairs.length;
    if ($("propsTaking")) {
      $("propsTakingHead").hidden = !nTaken; $("propsTaking").hidden = !nTaken;
      $("propsTaking").innerHTML = takenPairs.map(function (t, i) { return propsPairCard(t, i, true); }).join("") + taken.map(propTakeCard).join("");
      $("propsTakingCount").textContent = nTaken ? nTaken + " marked" : "";
    }
    var pool = ($("propsAll").checked ? rows : rows.filter(propHas)).slice(), list = propsTableRows(pool);
    ["propsMk", "propsBand", "propsSide", "propsQ", "propsAgree", "propsUsage", "propsRole", "propsSimSel"].forEach(function (id) { var el = $(id); if (el) { var k = { propsMk: "mk", propsBand: "band", propsSide: "side", propsQ: "q", propsAgree: "agree", propsUsage: "usage", propsRole: "role", propsSimSel: "sim" }[id]; if (el.value !== propsTableView[k]) el.value = propsTableView[k]; } });
    /* the same-game pairs (26 Oct 2026), the likeliest tickets first */
    if ($("propsPairs")) {
      var pairs = propsPairs(date, rows);
      pairsOrder = pairs.map(function (t) { return String(t.id); });   // the panel's Previous / Next walk the night's tickets
      $("propsPairs").innerHTML = pairs.length ? pairs.map(function (t, i) { return propsPairCard(t, i); }).join("") : '<div class="empty">' + (rows.length ? 'No game on this date has two props at 52% or better.' : 'Load a props file and the pairs land here.') + '</div>';
    }
    if ($("propsShown")) $("propsShown").textContent = rows.length ? (list.length === pool.length ? pool.length + " shown" : list.length + " of " + pool.length + " shown") + (propsTableView.sort !== "default" ? " · sorted by " + (PROPS_SORT_COLS.filter(function (c) { return c[0] === propsTableView.sort; })[0] || ["", propsTableView.sort])[1].toLowerCase() + (propsTableView.dir < 0 ? " ▾" : " ▴") : "") : "";
    var h = '<table class="form props"><thead><tr>' + PROPS_SORT_COLS.map(function (c) {
      var on = propsTableView.sort === c[0];
      return '<th data-sort="' + c[0] + '" class="sortable' + (on ? ' on' : '') + '" title="Sort by ' + c[1].toLowerCase() + '">' + c[1] + (on ? (propsTableView.dir < 0 ? ' ▾' : ' ▴') : '') + '</th>';
    }).join('') + '<th>Take</th></tr></thead><tbody>';
    list.forEach(function (r) {
      h += '<tr data-prop="' + r.id + '" class="' + (r.result || '') + (r.take ? ' taking' : '') + '"><td>' + esc(r.game) + '</td><td>' + esc(r.name) + (r.pos ? ' <span class="tag">' + esc(r.pos) + '</span>' : '') + '</td>' +
        '<td>' + esc(PROPS_LABEL[r.mk] || r.mk) + '</td><td>' + r.line + ' (' + sgn(r.op, 0) + '/' + sgn(r.up, 0) + ')</td>' +
        (propHas(r) ? '<td>' + esc(r.side) + '</td><td>' + (r.chance * 100).toFixed(1) + '%</td><td>' + sgn(r.price, 0) + '</td><td>' + (r.need * 100).toFixed(1) + '%</td>' +
                      '<td class="' + (r.edge > 0 ? 'pos' : 'neg') + '">' + sgn(r.edge * 100, 1) + '</td><td>' + r.proj + '</td><td>' + esc(r.band) + '</td>'
                    : '<td colspan="7" class="dim">' + esc((r.why && r.why[0]) || 'no projection') + '</td>') +
        '<td>' + (r.result ? esc(r.result) + (r.actual !== null && r.actual !== undefined ? ' · ' + r.actual : '') : '') + '</td>' +
        (function (t) { return '<td class="agree' + (t.n ? (t.all ? ' pos' : t.against > t.toward ? ' neg' : '') : '') + '" title="' + esc(t.words) + '">' + t.text + '</td>'; })(propsLeverTally(r)) +
        (function (v, ag) { return '<td class="simc' + (ag === true ? ' pos' : ag === false ? ' neg' : '') + '" title="' + (v === null ? 'no simulation on this prop' : 'the simulation\'s own read of the stat, his per 36 at his minutes scaled by his club\'s runs; ' + (ag === true ? 'on the ' + esc(r.side) + '\'s side of the line' : ag === false ? 'against the ' + esc(r.side) : 'on the line') + ' (shown, not scored)') + '">' + (v === null ? '' : v) + '</td>'; })(propSimRead(r), propSimAgrees(r)) +
        (function (u) { return '<td class="usgc' + (u === "hi" ? ' pos' : '') + '" title="' + (r.usg === null || r.usg === undefined ? 'no usage on this prop' : 'his share of his club\'s possessions while on the floor' + (r.starter === true ? '; a starter' : r.starter === false ? '; off the bench' : '') + (r.sdf && r.sdf !== 1 ? '; the miss read at ' + r.sdf + ' sigmas (measured)' : '')) + '">' + (r.usg === null || r.usg === undefined ? '' : esc(String(r.usg)) + '%' + (r.starter === true ? ' <span class="tag">S</span>' : r.starter === false ? ' <span class="tag">B</span>' : '')) + '</td>'; })(propUsageBucket(r)) +
        '<td class="take">' + propTakeBtn(r) + '</td></tr>';
    });
    h += '</tbody></table>';
    propsOrder = list.map(function (r) { return String(r.id); });   // the panel's Previous / Next walk the table's order
    $("propsTable").innerHTML = rows.length ? h : '';
  }
  function propsAsText() {
    var date = $("propsDate").value;
    var rows = props.filter(function (r) { return (r.gdate || "") === date && propHas(r); }).sort(function (a, b) { return b.edge - a.edge; });
    var out = ["The Super Model — NBA props — " + gameDate(date)];
    rows.forEach(function (r, i) {
      out.push((i + 1) + ". " + (r.take ? "TAKING · " : "") + r.name + " " + r.side + " " + r.line + " " + (PROPS_LABEL[r.mk] || r.mk) + " " + sgn(r.price, 0) + " · " + (r.chance * 100).toFixed(1) + "% needs " +
               (r.need * 100).toFixed(1) + "% · " + r.band + " · " + r.game + " · proj " + r.proj + (propSimRead(r) !== null ? " · sim " + propSimRead(r) : "") + (r.result ? " · " + r.result.toUpperCase() + (r.actual !== null && r.actual !== undefined ? " " + r.actual : "") : ""));
    });
    return out.join("\n");
  }
  if ($("m-props")) {
    $("m-props").addEventListener("click", function () { showProps(!propsView); });
    $("loadProps").addEventListener("click", function () { $("slateFile").click(); });
    $("propsDate").addEventListener("change", renderProps);
    $("propsAll").addEventListener("change", renderProps);
    $("propsExample").addEventListener("click", propsExample);
    $("propsClear").addEventListener("click", function () {
      if (propsPreview) { propsPreview = null; renderProps(); propsSay("The example is gone. Load a real props file when you have one."); return; }
      var date = $("propsDate").value, before = props.length;
      props = props.filter(function (r) { return (r.gdate || "") !== date || r.result; });
      saveProps(); renderProps(); renderCalib();
      propsSay("Cleared <b>" + (before - props.length) + "</b> ungraded prop" + (before - props.length === 1 ? "" : "s") + " on " + esc(gameDate(date)) + "; graded ones are records and stay.");
    });
    $("propsText").addEventListener("click", function () {
      var text = propsAsText();
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(function () { propsSay("Copied the props as text."); }, function () { propsSay("The clipboard is blocked here; the text is below.<pre>" + esc(text) + "</pre>"); });
      else propsSay("<pre>" + esc(text) + "</pre>");
    });
    var openFrom = function (e) { var t = e.target.closest("[data-prop]"); if (t) openPropDetail(t.getAttribute("data-prop")); };
    document.addEventListener("click", function (e) {
      var t = e.target && e.target.closest ? e.target.closest("[data-pgo]") : null; if (!t) return;
      e.stopPropagation(); e.preventDefault(); openPropMatchup(t.getAttribute("data-pgo"));
    }, true);
    $("propsTable").addEventListener("click", function (e) {
      var th = e.target.closest("th[data-sort]");
      if (th) {
        var k = th.getAttribute("data-sort");
        if (propsTableView.sort === k) { if (propsTableView.dir < 0) propsTableView.dir = 1; else { propsTableView.sort = "default"; propsTableView.dir = -1; } }
        else { propsTableView.sort = k; propsTableView.dir = (k === "game" || k === "name" || k === "mk" || k === "side" || k === "result" || k === "band") ? 1 : -1; }
        savePropsTableView(); renderProps(); return;
      }
      openFrom(e);
    });
    [["propsMk", "mk"], ["propsBand", "band"], ["propsSide", "side"], ["propsQ", "q"], ["propsAgree", "agree"], ["propsUsage", "usage"], ["propsRole", "role"], ["propsSimSel", "sim"]].forEach(function (p) {
      var el = $(p[0]); if (!el) return;
      el.addEventListener(p[0] === "propsQ" ? "input" : "change", function () { propsTableView[p[1]] = el.value; savePropsTableView(); renderProps(); });
    });
    if ($("propsReset")) $("propsReset").addEventListener("click", function () { propsTableView = Object.assign({}, PROPS_VIEW_DEFAULT); try { localStorage.removeItem(PROPS_VIEW_KEY); } catch (e) {} renderProps(); });
    $("propsBest").addEventListener("click", openFrom);
    var openPairFrom = function (e) { var t = e.target.closest("[data-pair]"); if (t) { openPairDetail(t.getAttribute("data-pair")); return true; } return false; };
    if ($("propsPairs")) $("propsPairs").addEventListener("click", openPairFrom);
    if ($("propsTaking")) {
      $("propsTaking").addEventListener("click", function (e) { if (!openPairFrom(e)) openFrom(e); });
      $("propsTakingText").addEventListener("click", function () { copyText(takingAsText($("propsDate").value), propsSay, "the props you are taking"); });
    }
    if ($("propDetail")) {
      $("propDetailClose").addEventListener("click", closePropDetail);
      $("propDetailPrev").addEventListener("click", function () { stepPropDetail(-1); });
      $("propDetailNext").addEventListener("click", function () { stepPropDetail(1); });
      $("propDetail").addEventListener("click", function (e) { if (e.target === $("propDetail")) closePropDetail(); });
      $("propDetailBody").addEventListener("click", function (e) { if (propDetailKind !== "pair") return; var t = e.target.closest("[data-prop]"); if (t) openPropDetail(t.getAttribute("data-prop")); });   // a leg's own panel from the pair's
      document.addEventListener("keydown", function (e) {
        if ($("propDetail").hidden) return;
        var tag = e.target && e.target.tagName ? e.target.tagName.toLowerCase() : "";
        if (e.key === "Escape") closePropDetail();
        else if (e.key === "ArrowLeft" && tag !== "input" && tag !== "textarea") stepPropDetail(-1);
        else if (e.key === "ArrowRight" && tag !== "input" && tag !== "textarea") stepPropDetail(1);
      });
    }
  }
  /* ===== END PROPS BLOCK ===== */
