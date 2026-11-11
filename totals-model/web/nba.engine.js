  /* ===== NBA BLOCK. Ported from totals/nba.py; web/callsheet3-cases.json is
     replayed through this page against the package on every change. It sits
     after Call Sheet #1's engine block and the NHL block and changes nothing
     inside them: the point distribution is registered by reassigning splitFor
     again, the plausibility windows are added to PLAUSIBLE, and the team table
     gets an NBA page. Built 15 Oct 2026 from two seasons of the user's ledger
     against KillerSports' closes (NBA.md): the sides are priced and shown,
     the total carries a faded ratings lean and two stage deltas, both tagged,
     and the first half anchors on its own market. ===== */
  var NBA = {
    /* measured 15 Oct 2026 on 2,449 closes, the 2024-25 and 2025-26 ledgers (totals/nba.py has each figure's story) */
    POINTS: 228.8,          // a game, both teams, at the close
    TOTAL_SD: 18.0,         // the total's residual on the close, flat across levels
    MARGIN_SD: 12.5,        // a normal margin at 12.5 fits the spread's home win rate (13.7 raw overstates the dog)
    HALF_SHARE: 0.5036, HALF_SD: 11.9,   // the first half's share of regulation points, the same at every level; the half's spread on half the close
    HOME_COURT: 1.7, OT: 0.047, PACE: 101.5,
    FADE: -0.25, SHRINK_K: 20, FADE_UNTIL: 50, MIN_GAMES: 10,   // the ratings projection, faded and tagged: -0.22 a point of lean under 50 games (t -2.6), null after
    DEADLINE_DELTA: 1.0, LAST_TWO_WEEKS_DELTA: 2.0,              // the stage of the season, tagged: +1.36 after the deadline (t 2.3), +2.25 in the last fortnight (t 1.8)
    SEASON: { deadline: "2027-02-04", last_two_weeks: "2027-03-29", end: "2027-04-11" },   // A PRIORI for 2026-27 until the league publishes
    REGULAR_MPG: 20,
    EARLY_SIDE_GAMES: 30, EARLY_SIDE_LEAN: 4,   // the WNBA card's pattern on the NBA: the ratings' side at 4+ points of lean 148-124 in a club's first thirty games, 50/50 after; a watch
    SHORT_DOG_MIN: 0.40, SHORT_DOG_LIFT: 0.04,   // the short dog (16 Oct 2026, two seasons of closing moneylines): a dog the book makes 40%+ won +5.6 points more than priced (z 2.8, +5.6 both seasons, +9.8% a bet); two-thirds of it, tagged, the moneyline pickable
    FAIR_SPAN: 30
  };
  NBA.RATING = Math.round(NBA.POINTS / 2 / NBA.PACE * 100 * 10) / 10;   // 112.7 points per 100 possessions
  var NBA_WEIGHTS = { market: 4.0, h1mkt: 4.0 };
  var NBA_WATCHED = { "Nuggets": "+5.1 and +4.3 a game over the close", "Jazz": "+3.0 and +5.7 a game over the close" };
  PLAUSIBLE.nba_total = [170, 300]; PLAUSIBLE.nba_half = [80, 150]; PLAUSIBLE.nba_pace = [85, 120]; PLAUSIBLE.nba_rating = [90, 135];

  function nbaSplit(line, mu) { return normalSplit(line, mu, NBA.TOTAL_SD); }
  function nbaHalfSplit(line, mu) { return normalSplit(line, mu, NBA.HALF_SD); }
  var splitForBaseNba = splitFor;
  splitFor = function (sport, line, mu) {
    if (sport === "NBA") return nbaSplit(line, mu);
    if (sport === "NBA_H1") return nbaHalfSplit(line, mu);
    return splitForBaseNba(sport, line, mu);
  };
  /* fairTotal with a basketball-sized bracket (totals/nba.py nba_fair_total): the
     engine block's solve brackets four runs, which a total that moves 18 points a
     sigma can leave. The same de-vig, reconstruction and confidence cut. */
  function nbaFairTotal(sport, line, op, up) {
    var quoted = op !== null && up !== null;
    var rebuilt = quoted ? null : completePair(op, up);
    if (rebuilt) { op = rebuilt[0]; up = rebuilt[1]; quoted = true; }
    if (!quoted) { op = -110; up = -110; }
    var o = implied(op), u = implied(up), s = o + u;
    var bookHold = s - 1;
    var conf = marketConfidence(rebuilt ? HOLD_90TH : bookHold);
    var rawOver = o / s;
    var pOver = 0.5 + (rawOver - 0.5) * conf;
    var lo = Math.max(0.5, line - NBA.FAIR_SPAN), hi = line + NBA.FAIR_SPAN;
    for (var i = 0; i < 80; i++) {
      var mid = (lo + hi) / 2, sp = splitFor(sport, line, mid);
      var live = sp[0] + sp[2];
      var conditional = live > 0 ? sp[0] / live : 0.5;
      if (conditional < pOver) lo = mid; else hi = mid;
    }
    var mu = (lo + hi) / 2;
    var tail = conf < 1
      ? " That is a " + (bookHold * 100).toFixed(1) + "% hold where a main line runs " + (HOLD_REFERENCE * 100).toFixed(0) +
        "%: most likely an ALTERNATE line. The read has been pulled back from " + (rawOver * 100).toFixed(1) + "% toward even and only " + (conf * 100).toFixed(0) + "% of it is kept."
      : "";
    var why = rebuilt
      ? ("Only one price was given, so the other side was reconstructed at the " + (TYPICAL_HOLD * 100).toFixed(1) + "% hold this book typically charges, giving " + sgn(op, 0) + "/" + sgn(up, 0) +
         ". That de-vigs to " + (pOver * 100).toFixed(1) + "% over and puts fair at " + mu.toFixed(1) + " rather than the " + line + " posted; the confidence is cut against the " +
         (HOLD_90TH * 100).toFixed(1) + "% 90th-percentile hold, so only " + (marketConfidence(HOLD_90TH) * 100).toFixed(0) + "% of the " + (rawOver * 100).toFixed(1) + "% read is kept.")
      : quoted
      ? (sgn(op, 0) + "/" + sgn(up, 0) + " de-vigs to " + (pOver * 100).toFixed(1) + "% over (" + (bookHold * 100).toFixed(2) + "% hold), which is the market saying fair is " +
         mu.toFixed(1) + " rather than the " + line + " it posted." + tail)
      : ("No prices given, so an evenly-priced market is assumed. A line of " + line + " splitting 50/50 implies a mean of " + mu.toFixed(1) +
         ": a basketball total is symmetric, so the mean sits on the number.");
    return [mu, why];
  }
  function nbaRatingsSides(ao, ho, ad, hd, ap, hp, lgr, lgp) {
    var four = [ao, ho, ad, hd];
    for (var i = 0; i < 4; i++) if (four[i] === null || !ok(four[i], "nba_rating")) return null;
    var lg = (lgr !== null && ok(lgr, "nba_rating")) ? lgr : NBA.RATING;
    var lp = (lgp !== null && ok(lgp, "nba_pace")) ? lgp : NBA.PACE;
    var paces = [ap, hp].filter(function (p) { return p !== null && ok(p, "nba_pace"); });
    var pace = paces.length === 2 ? (paces[0] + paces[1]) / 2 : lp;
    return [pace / 100 * (ao + hd - lg), pace / 100 * (ho + ad - lg), pace, lg];
  }
  function nbaRatingsProjection(ao, ho, ad, hd, ap, hp, lgr, lgp) {
    var s = nbaRatingsSides(ao, ho, ad, hd, ap, hp, lgr, lgp);
    if (!s) return null;
    var ea = s[0], eh = s[1], pace = s[2], lg = s[3];
    return [ea + eh, "away " + ao.toFixed(1) + " into " + hd.toFixed(1) + " and home " + ho.toFixed(1) + " into " + ad.toFixed(1) + ", each less the league's " + lg.toFixed(1) +
      ", over " + pace.toFixed(1) + " possessions: " + ea.toFixed(1) + " and " + eh.toFixed(1) + ", " + (ea + eh).toFixed(1) + " together"];
  }
  /* the same projection as a margin, home minus away: the spread's own projection,
     priced against two seasons of closes (slope -0.01); an early-season watch only */
  function nbaRatingsMargin(ao, ho, ad, hd, ap, hp, lgr, lgp) {
    var s = nbaRatingsSides(ao, ho, ad, hd, ap, hp, lgr, lgp);
    return s ? s[1] - s[0] : null;
  }
  function nbaStageOf(gdate) {
    var d = String(gdate || "").slice(0, 10);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(d)) return null;
    var s = NBA.SEASON;
    if (d > s.end) return null;
    if (d >= s.last_two_weeks) return [NBA.LAST_TWO_WEEKS_DELTA, "the last two weeks of the season"];
    if (d > s.deadline) return [NBA.DEADLINE_DELTA, "after the trade deadline"];
    return null;
  }
  /* the who-is-out list the slate writes (JSON in the hidden nbaout box): each side's
     players out or in doubt with his minutes, points and plus-minus a game to date; a
     questionable player counts as out when his box is ticked (the ids in nbaq) */
  function nbaOutList() {
    var raw = txt("nbaout") || "", d = null;
    try { d = raw ? JSON.parse(raw) : null; } catch (e) { d = null; }
    return d && typeof d === "object" ? d : { away: [], home: [] };
  }
  function nbaTicked() {
    return String(txt("nbaq") || "").split(",").filter(function (x) { return x; });
  }
  function nbaOutMinutes(side) {
    var list = nbaOutList()[side] || [], ticked = nbaTicked(), sum = 0;
    list.forEach(function (p) {
      var out = /^out/i.test(String(p.st || "")) || ticked.indexOf(String(p.id)) >= 0;
      if (out && +p.mpg >= NBA.REGULAR_MPG) sum += +p.mpg;
    });
    return sum;
  }
  function readNba() {
    var line = num("line");
    if (!ok(line, "nba_total")) return null;
    var w = NBA_WEIGHTS, notes = [];
    var fa = nbaFairTotal("NBA", line, num("op"), num("up")), anchor = fa[0];
    var estimates = [est("Market", anchor, w.market, fa[1])], deltas = [];
    /* the clubs through txt(), not the form: a card row re-scored while another game sat in
       the form (a slate or odds file merged into the card) took that game's names onto its
       moneyline and spread until 21 Oct 2026 (the user's backup: "Islanders ML" on Celtics @ Pistons) */
    var away = canonTeam(txt("away"), "NBA") || "Away", home = canonTeam(txt("home"), "NBA") || "Home";
    var ao = num("naort"), ho = num("nhort"), ad = num("nadrt"), hd = num("nhdrt"), ap = num("napace"), hp = num("nhpace");
    var ag = num("nagp"), hg = num("nhgp"), lgr = num("nlrtg"), lgp = num("nlpace");
    var rp = nbaRatingsProjection(ao, ho, ad, hd, ap, hp, lgr, lgp);
    if (rp) {
      var n = (ag !== null && hg !== null) ? Math.min(ag, hg) : null, lean = rp[0] - anchor;
      if (n === null || n < NBA.MIN_GAMES) {
        notes.push("Ratings projection " + rp[0].toFixed(1) + " (" + rp[1] + "), " + sgn(lean, 1) + " on the market's " + anchor.toFixed(1) + ". <b>SHOWN, NOT SCORED</b>: the fade needs " +
          NBA.MIN_GAMES + " games a side" + (n === null ? "" : " and the lesser side has " + n) + ".");
      } else if (n >= NBA.FADE_UNTIL) {
        notes.push("Ratings projection " + rp[0].toFixed(1) + " (" + rp[1] + "), " + sgn(lean, 1) + " on the market's " + anchor.toFixed(1) + ". <b>SHOWN, NOT SCORED</b>: past " +
          NBA.FADE_UNTIL + " games a side the market has the ratings priced (slope +0.003 on 944 games).");
      } else {
        var shrunk = lean * n / (n + NBA.SHRINK_K), size = NBA.FADE * shrunk;
        var fadeWhy = "Pace x efficiency projects " + rp[0].toFixed(1) + " (" + rp[1] + "), " + sgn(lean, 1) + " on the market's " + anchor.toFixed(1) + "; shrunk by " + n + "/(" + n + "+" + NBA.SHRINK_K +
          ") games to " + sgn(shrunk, 1) + ". The market OVER-MOVES with early-season ratings: against two seasons of closes the final ran 0.22 a point the OTHER way per point of lean under " +
          NBA.FADE_UNTIL + " games (t -2.6, both seasons), nothing after. So " + sgn(NBA.FADE, 2) + " a point goes on the line, " + sgn(size, 2) + "; tagged, it cannot buy a band.";
        deltas.push(delta("Ratings, faded", size, fadeWhy, false));
        notes.push("<b>Ratings, faded</b>: " + fadeWhy);
      }
    } else if (ao !== null || ho !== null || ad !== null || hd !== null) {
      notes.push("The four ratings travel together, each offence into the defence it faces; a partial set is dropped.");
    }
    var st = nbaStageOf(($("gdate") || {}).value);
    if (st) {
      var stWhy = st[1].charAt(0).toUpperCase() + st[1].slice(1) + ": against two seasons of closes the total ran " +
        (st[0] === NBA.LAST_TWO_WEEKS_DELTA ? "+2.25 a game in the last two weeks (224 games, +1.40 and +3.10 by season; April alone +3.2)" : "+1.36 a game after the deadline (933 games, +1.17 and +1.56 by season)") +
        ". Tanking, bench minutes and no defence; the market under-prices it. " + sgn(st[0], 1) + " on the line, tagged.";
      deltas.push(delta("Stage of the season", st[0], stWhy, false));
      notes.push("<b>Stage of the season</b>, " + stWhy);
    }
    [away, home].forEach(function (nm) {
      if (NBA_WATCHED[nm]) notes.push("<b>" + esc(nm) + "</b> games ran " + NBA_WATCHED[nm] + " both seasons, home and away. <b>WATCHED, NOT SCORED</b>: a club's own over/under residual does not persist within a season (slope -0.05 on 2,137 games).");
    });
    var ar = num("narest"), hr = num("nhrest"), b2b = [];
    if (ar !== null && ar <= 0) b2b.push("away");
    if (hr !== null && hr <= 0) b2b.push("home");
    if (b2b.length) notes.push("Back to back for the " + b2b.join(" and ") + " side. <b>A LABEL</b>: rest, the second night on the road, three in four and the time zones all flipped sign between seasons against two seasons of closes. The market prices rest.");
    var outA = nbaOutMinutes("away"), outH = nbaOutMinutes("home"), outBits = [];
    if (outA > 0) outBits.push("away " + outA.toFixed(0));
    if (outH > 0) outBits.push("home " + outH.toFixed(0));
    if (outBits.length) notes.push("Regulars out, minutes a game: " + outBits.join(", ") + ". <b>SHOWN, NOT SCORED</b>: announced absences are in the close (slope -0.01 on the total, +0.29 on the side, t 1.2); games with 40+ minutes of regulars out ran +0.87 over the close (t 1.8). The card measures the late ones from opening night.");
    var opened = num("opened");
    if (opened !== null && Math.abs(opened - line) > 1e-9) notes.push("The number moved " + opened + " to " + line + " (" + sgn(line - opened, 1) + "). Not scored — the current line is the anchor and the move is already inside it.");
    var f = assemble("NBA", away, home, line, estimates, deltas, notes);
    f.away = away; f.home = home; f.line = line;
    return f;
  }
  function nbaMarginFromSpread(spread, ph, pa) {
    if (ph !== null && pa !== null) {
      var pc = devig(ph, pa)[0], lo = -40, hi = 40;
      for (var i = 0; i < 60; i++) {
        var mid = (lo + hi) / 2, sp = spreadProbs(mid, spread, NBA.MARGIN_SD), live = sp[0] + sp[2];
        if ((live > 0 ? sp[0] / live : 0.5) < pc) lo = mid; else hi = mid;
      }
      var m = (lo + hi) / 2;
      return [m, "spread " + fmtLine(spread) + " at " + sgn(ph, 0) + "/" + sgn(pa, 0) + ", which de-vigs to " + (pc * 100).toFixed(1) + "% home and moves fair to " + sgn(m, 1)];
    }
    return [-spread, "spread " + fmtLine(spread) + " taken as the mean margin (no prices)"];
  }
  /* the context card: the slate's league ranks for the two clubs, each with the tag that
     says what the sheet did with the fact (the hockey card's shape, nhlCtxPanel) */
  /* the crew line: the names in the Crew box (the slate's, or typed from the league's page)
     against the referee table the slate writes from the ledger (nbarefs: each official's
     games, free throws and points a game, and the league's). Shown, not scored: NBA.md */
  var NBA_CREW_TAG = "shown, not scored: crews predict the night's free throws (slope 0.60, t 7.3 on two seasons) and the total does not follow them (t −1.0 against the close); a referee's over/under record is a watch until this season repeats it";
  function nbaCrewLine() {
    var names = String(($("ncrew") || {}).value || "").split(/[,;]+/).map(function (s) { return s.trim(); }).filter(function (s) { return s; });
    if (!names.length) return null;
    var raw = ($("nbarefs") || {}).value || "", refs = null;
    try { refs = raw ? JSON.parse(raw) : null; } catch (e) { refs = null; }
    var table = refs && refs.r ? refs.r : {}, keys = Object.keys(table);
    var find = function (n) {
      if (table[n]) return table[n];
      var low = n.toLowerCase(), hit = keys.filter(function (k) { return k.toLowerCase() === low; });
      if (!hit.length) { var last = low.split(" ").pop(); hit = keys.filter(function (k) { return k.toLowerCase().split(" ").pop() === last; }); }
      return hit.length === 1 ? table[hit[0]] : null;
    };
    var bits = names.map(function (n) {
      var d = find(n);
      if (!d) return n + " (no games in the ledger)";
      var ou = (d.length > 4 && (+d[3] || +d[4])) ? ", over the close " + d[3] + "-" + d[4] + " the last two seasons" : "";
      if (d.length > 6 && (+d[5] || +d[6])) ou += (ou ? " and " : ", over the close ") + d[5] + "-" + d[6] + " this season";
      return n + " " + (+d[1]).toFixed(1) + " free throws and " + (+d[2]).toFixed(1) + " points a game (" + d[0] + " games)" + ou;
    });
    return { side: "game", k: "crew", s: "shown", t: "Crew: " + bits.join("; ") + (refs && refs.lg ? "; the league " + (+refs.lg[1]).toFixed(1) + " and " + (+refs.lg[2]).toFixed(1) + "." : "."), tag: NBA_CREW_TAG };
  }
  /* the crowd on Kalshi (4 Nov 2026, the user: "if I wanted to use some metrics from Kalshi such as public percentages on who
     may win the game... what could we add?"): the slate keeps each side's bid, ask, last, volume and open interest from the
     exchange's game-winner market on the row (nbakalshi). A contract's price is the crowd's probability with no vig; the fee
     is taken on the win (7% of the expected profit), so a 57-cent yes needs 58.7%. The card shows the crowd beside the book's
     devigged moneyline and Pinnacle's, says which price is better after the fee, and names the sharp side when the crowd sits
     three points or more from Pinnacle: a watch with its own line on the moneyline tile's record. Shown, not scored */
  var KALSHI_GAP = 0.03;
  function kalshiMid(s) {
    if (!s) return null;
    var b = +s.bid, a = +s.ask;
    if (isFinite(b) && isFinite(a) && a > 0) return (b + a) / 2;
    return isFinite(+s.last) && +s.last > 0 ? +s.last : null;
  }
  function kalshiNeed(s, fee) { var a = +(s || {}).ask; if (!isFinite(a) || a <= 0 || a >= 1) return null; return a + fee * a * (1 - a); }   // what a yes at the ask needs, the fee on the win counted
  function kalshiNeedAt(ask, fee) { return !isFinite(ask) || ask <= 0 || ask >= 1 ? null : ask + fee * ask * (1 - ask); }
  /* the ladders (4 Nov 2026, the user's spread and total listings): a club's spread markets ("Memphis wins by over 6.5 points")
     and the game's total markets ("Over 228.5 points") each read as the crowd's chance of more than the floor, so together they
     are the crowd's distribution of the margin and the total: the number at even money is the crowd's spread or total, and the
     chance at the book's line is read straight between two rungs */
  function kalshiRungs(list) {
    return (list || []).map(function (r) { var bid = +r[1], ask = +r[2]; return isFinite(bid) && isFinite(ask) && ask > 0 && isFinite(+r[0]) ? { x: +r[0], p: (bid + ask) / 2, bid: bid, ask: ask, vol: +r[4] || 0 } : null; })
      .filter(function (r) { return r; }).sort(function (a, b) { return a.x - b.x; });
  }
  function kalshiCurveAt(pts, x) {   // P(more than x) off the rungs, straight between two, null outside them
    if (!pts || !pts.length || x < pts[0].x || x > pts[pts.length - 1].x) return null;
    for (var i = 0; i < pts.length; i++) {
      if (x === pts[i].x) return pts[i].p;
      if (i && x < pts[i].x) { var a = pts[i - 1], b = pts[i]; return a.p + (b.p - a.p) * (x - a.x) / (b.x - a.x); }
    }
    return null;
  }
  function kalshiMedian(pts) {   // the number the crowd puts at even money
    for (var i = 1; i < (pts || []).length; i++) { var a = pts[i - 1], b = pts[i]; if (a.p >= 0.5 && b.p < 0.5) return a.p === b.p ? a.x : a.x + (a.p - 0.5) / (a.p - b.p) * (b.x - a.x); }
    return null;
  }
  function kalshiRungAt(pts, x) { for (var i = 0; i < (pts || []).length; i++) if (pts[i].x === x) return pts[i]; return null; }
  function kalshiOf(raw) {
    var k = null; try { k = raw ? JSON.parse(raw) : null; } catch (e) { k = null; }
    if (!k || typeof k !== "object") return null;
    k.fee = isFinite(+k.fee) ? +k.fee : 0.07;
    var ma = kalshiMid(k.a), mh = kalshiMid(k.h);
    k.ml = !!(k.a && k.h && ma !== null && mh !== null && ma + mh > 0);
    if (k.ml) { k.pa = ma / (ma + mh); k.ph = mh / (ma + mh); k.needA = kalshiNeed(k.a, k.fee); k.needH = kalshiNeed(k.h, k.fee); }   // the crowd's chances: the two sides' mids made to sum to one
    else { k.pa = k.ph = k.needA = k.needH = null; }
    k.spH = kalshiRungs(k.sp && k.sp.h); k.spA = kalshiRungs(k.sp && k.sp.a);
    /* the home margin's curve: P(the home side wins by more than x) from its own ladder, and from the away ladder as P(the away side
       wins by more than y) = P(the home margin is under -y), the margins never landing on a half */
    k.margin = k.spH.map(function (r) { return { x: r.x, p: r.p }; }).concat(k.spA.map(function (r) { return { x: -r.x, p: 1 - r.p }; })).sort(function (a, b) { return a.x - b.x; });
    k.total = kalshiRungs(k.tot);
    k.spMed = k.margin.length >= 2 ? kalshiMedian(k.margin) : null;   // the crowd's spread, as the home margin at even money
    k.totMed = k.total.length >= 2 ? kalshiMedian(k.total) : null;    // the crowd's total at even money
    /* the team totals (4 Nov 2026, the user's address off the Game Props tab): a ladder a club, P(the club scores more than x) */
    k.ttA = kalshiRungs(k.tt && k.tt.a); k.ttH = kalshiRungs(k.tt && k.tt.h);
    k.ttAMed = k.ttA.length >= 2 ? kalshiMedian(k.ttA) : null; k.ttHMed = k.ttH.length >= 2 ? kalshiMedian(k.ttH) : null;
    if (!k.ml && !k.margin.length && !k.total.length && !k.ttA.length && !k.ttH.length) return null;
    return k;
  }
  /* the crowd on one side of one market at one line: its chance, and when the line is a rung of the ladder, the price it trades at
     (the yes ask for the side the ladder names, the no ask -- one less the yes bid -- for the other) and what that needs after the fee */
  function kalshiSideQuote(k, key, side, line) {
    if (!k) return null;
    var q = { p: null, ask: null, need: null, rung: false }, r;
    if (key === "ml") { if (!k.ml) return null; q.p = side === "HOME" ? k.ph : k.pa; q.ask = +(side === "HOME" ? k.h : k.a).ask; q.need = side === "HOME" ? k.needH : k.needA; q.rung = true; }
    else if (key === "total") {
      if (!k.total.length || !isFinite(+line)) return null;
      var po = kalshiCurveAt(k.total, +line); if (po === null) return null;
      q.p = side === "OVER" ? po : 1 - po;
      r = kalshiRungAt(k.total, +line);
      if (r) { q.rung = true; q.ask = side === "OVER" ? r.ask : 1 - r.bid; q.need = kalshiNeedAt(q.ask, k.fee); }
    } else if (key === "spread") {
      if (!k.margin.length || !isFinite(+line)) return null;
      var ph = kalshiCurveAt(k.margin, -(+line)); if (ph === null) return null;   // the home side covers when its margin beats the number it gives
      q.p = side === "HOME" ? ph : 1 - ph;
      if (+line < 0) { r = kalshiRungAt(k.spH, -(+line)); if (r) { q.rung = true; q.ask = side === "HOME" ? r.ask : 1 - r.bid; } }
      else if (+line > 0) { r = kalshiRungAt(k.spA, +line); if (r) { q.rung = true; q.ask = side === "AWAY" ? r.ask : 1 - r.bid; } }
      if (q.rung) q.need = kalshiNeedAt(q.ask, k.fee);
    } else if (key === "away_total" || key === "home_total") {
      var lad = key === "away_total" ? k.ttA : k.ttH;
      if (!lad.length || !isFinite(+line)) return null;
      var pt = kalshiCurveAt(lad, +line); if (pt === null) return null;
      q.p = side === "OVER" ? pt : 1 - pt;
      r = kalshiRungAt(lad, +line);
      if (r) { q.rung = true; q.ask = side === "OVER" ? r.ask : 1 - r.bid; q.need = kalshiNeedAt(q.ask, k.fee); }
    } else return null;
    return q.p === null ? null : q;
  }
  /* the team totals on the simulation's table (4 Nov 2026): one line under the row's team-total line, the crowd's chance of the
     over at the book's number and, on a rung, each side's price after the fee against the book's */
  function kalshiTTLine(k, key, line, op, up) {
    var qo = kalshiSideQuote(k, key, "OVER", line), qu = kalshiSideQuote(k, key, "UNDER", line);
    if (!qo) return "";
    var px = function (nm, q, bp) {
      if (!q || q.need === null) return '';
      var bn = isFinite(+bp) && +bp ? implied(+bp) : null, better = bn !== null && q.need < bn - 0.001;
      return ' · ' + nm + ' ' + kalshiCents(q.ask) + ' needs ' + (100 * q.need).toFixed(1) + '% after the fee' + (bn !== null ? (better ? ', <b>better than</b> ' : ', not better than ') + sgn(+bp, 0) + ' needing ' + (100 * bn).toFixed(1) + '%' : '');
    };
    return '<b class="kname">Kalshi</b>: the crowd <b>' + (100 * qo.p).toFixed(1) + '%</b> over at ' + esc(String(line)) + (qo.rung ? px('over', qo, op) + px('under', qu, up) : ' · no rung at the line, so no price');
  }
  /* ---- tonight's signals (4 Nov 2026, the user: "it never gives a green bet signal anymore... make the other sections, like
     the simulation, refs, lineups, Kalshi, the board, the middles, the context be a little more of the forefront"). The
     sheet's own pick stays grey on most NBA rows because the close already carries what its inputs know; the calls that do
     fire live in the engines down the card. This strip gathers every one of them at the top of the matchup rail: the pick
     and #1's verdict, the upset signal, Pinnacle's shade, the agreement rule, the simulation's bands, the gap watch, the
     middles, the crew's lean, the crowd on Kalshi and who is out. Green when a scored rule fires, gold for a watch, the
     exchange in its own colour, each chip a link to its section; the jump bar's dots and the sections' live lines read
     off the same list. Shown: it adds no number and takes nothing ---- */
  function signalChip(cls, go, badge, html) { return { cls: cls, go: go, badge: badge, html: html, text: badge + ": " + html.replace(/<[^>]+>/g, "") }; }
  function signalList(m, pk, upsetView, leg) {
    var out = [], pc = function (p) { return (100 * p).toFixed(1) + "%"; }, nba = sport === "NBA";
    if (pk && !pk.none && pk.mk) {
      var hot = !!(pk.mk.band && pk.mk.band !== "NO BET");
      out.push(signalChip(hot ? "go" : "watch", "markets", hot ? "the pick · " + pk.mk.band : "the pick", "<b>" + esc(pk.mk.pick) + "</b> · " + pc(pk.mk.p) + (pk.mk.edge !== null && pk.mk.edge !== undefined ? " · edge " + sgn(pk.mk.edge * 100, 1) : "")));
    }
    if (leg && typeof bandOf === "function" && bandOf(leg)) out.push(signalChip("go", "markets", "#1 says " + bandOf(leg), "<b>" + esc(leg.pick) + "</b> · " + pc(leg.p) + " at " + sgn(leg.price, 0)));
    if (upsetView && upsetView.dog) out.push(signalChip(upsetView.scored ? "go" : "watch", "markets", upsetView.scored ? "upset signal" : "upset watch", "<b>" + esc(upsetView.dog.pick) + "</b> · " + pc(upsetView.dog.p)));
    var ss = typeof sharpShadeOf === "function" ? sharpShadeOf(($("sharp") || {}).value || "") : null;
    if (ss) out.push(signalChip("watch", "markets", "Pinnacle", "shades the <b>" + esc(ss.side) + "</b> by " + ss.pts.toFixed(1) + " points"));
    if (!nba) return out;
    var inputs = snapshot(), f = readNba(), row = nbaSimTakeRow(f), away = f.away || "Away", home = f.home || "Home";
    var V = null; try { V = nbaVoices({ sport: "NBA", inputs: inputs, markets: (m && m.markets) || [] }); } catch (e) { V = null; }
    if (V && V.fires) out.push(signalChip("go", "secSim", "three voices · BET", "<b>" + esc(V.side) + " " + esc(String(V.line)) + "</b> · " + V.count + " of 3 on it, none against"));
    else if (V && V.side && !V.against) out.push(signalChip("watch", "secSim", "three voices", V.count + " of 3 on the <b>" + esc(V.side) + "</b>" + (V.agree ? (V.alt ? ", but the row's line is an alternate" : ", but the price asks more than the rule's rate") : ", no rule without the sim and the crew")));
    var sim = nbaSim(), lines = nbaSimLinesFromForm();
    if (sim) {
      var seen = {};
      ["own", "mkt"].forEach(function (view) {
        if (view === "mkt" && !sim.mkt) return;
        nbaSimCalls(sim, lines, view).forEach(function (c) {
          if (c.band === "no call" || seen[c.key + c.side]) return;
          seen[c.key + c.side] = true;
          var what = c.key === "away_total" ? away + " team total " + c.side + " " + c.line : c.key === "home_total" ? home + " team total " + c.side + " " + c.line
                   : c.key === "ml" ? (c.side === "HOME" ? home : away) + " ML" : c.key === "spread" ? (c.side === "HOME" ? home : away) + " " + sgn(c.side === "HOME" ? +c.line : -c.line, 1)
                   : (c.key === "h1" ? "1H " : "") + c.side + " " + c.line;
          out.push(signalChip(c.band === "LEAN" ? "watch" : "go", "secSim", "sim · " + c.band, "<b>" + esc(what) + "</b> · worth " + (100 * c.worth).toFixed(0) + "%" + (view === "mkt" ? " · anchored to the market" : "")));
        });
      });
    }
    [["away_tt", away], ["home_tt", home]].forEach(function (t) {
      var tt = lines[t[0]]; if (!tt || !tt.rule || !tt.rule.call) return;
      out.push(signalChip("watch", "secSim", "gap watch", "<b>" + esc(t[1]) + " team total " + tt.rule.call + " " + esc(String(tt.line)) + "</b> · gap " + (tt.rule.gap > 0 ? "+" : "") + tt.rule.gap + " · not scored"));   // gold from 11 Nov 2026: the two-season edge was a fault in the season pull
    });
    try {
      var W = row ? nbaMiddleWatch(row) : [], paying = W.filter(function (x) { return x.m.pays; })[0];
      if (paying) out.push(signalChip("go", "secMid", "middle open", "<b>" + esc(paying.side) + " " + esc(String(paying.other.point)) + " at " + esc(bookName(paying.other.book)) + "</b> with your " + esc(paying.leg.side) + " " + esc(String(paying.leg.line)) + " · pays " + sgn(100 * paying.m.ev, 1) + "%"));
      else {
        var P = nbaMiddlePairs(row ? row.inputs : inputs, 6), pp = P ? P.pairs.filter(function (x) { return x.m.pays; })[0] : null;
        if (pp) out.push(signalChip("go", "secMid", "a pair pays", "<b>over " + esc(String(pp.over.point)) + " / under " + esc(String(pp.under.point)) + "</b> · " + sgn(100 * pp.m.ev, 1) + "% of the stake"));
      }
    } catch (e) {}
    var cl = null; try { cl = nbaCrewLean({ inputs: inputs }); } catch (e) { cl = null; }
    if (cl && cl.lean && cl.lean !== "even") out.push(signalChip("watch", "secCrew", "crew", "leans <b>" + esc(String(cl.lean).toUpperCase()) + "</b> · z " + sgn(cl.z, 1)));
    var k = kalshiOf(($("nbakalshi") || {}).value || "");
    if (k) {
      var ks = kalshiSharpOf({ inputs: inputs });
      if (ks) out.push(signalChip("crowd", "secKalshi", "Kalshi", "the sharp side <b>" + esc(ks.side === "HOME" ? home : away) + "</b> · the crowd " + ks.pts.toFixed(1) + " points over Pinnacle on the " + esc(ks.side === "HOME" ? away : home)));
      var bits = [];
      if (k.ml) bits.push("<b>" + esc(k.ph >= 0.5 ? home : away) + "</b> to win " + pc(Math.max(k.ph, k.pa)));
      if (k.spMed !== null) bits.push("spread <b>" + (Math.abs(k.spMed) < 0.05 ? "a pick" : esc(k.spMed > 0 ? home : away) + " " + sgn(-Math.abs(k.spMed), 1)) + "</b>");
      if (k.totMed !== null) bits.push("total <b>" + k.totMed.toFixed(1) + "</b>");
      if (bits.length) out.push(signalChip("crowd", "secKalshi", "the crowd", bits.join(" · ")));
      /* the team totals as chips of their own (4 Nov 2026, the user: "can i have the team totals predictions from kalshi be on the
         matchup section with a color like you have the other signals"): each club's number at even money against the book's
         team-total line, the side the crowd leans to when it sits a point or more off it, and the crowd's chance of the over at
         the book's number; without a book line, against the number the book's total and spread imply */
      var oddsRaw = ($("odds") || {}).value || "", tl = parseFloat(inputs.line), spv = parseFloat(inputs.sp);
      [["AWAY", away, k.ttAMed, "away_total"], ["HOME", home, k.ttHMed, "home_total"]].forEach(function (t) {
        if (t[2] === null || t[2] === undefined) return;
        var bl = typeof nbaTeamTotalLine === "function" ? nbaTeamTotalLine(oddsRaw, t[0]) : null, s = "<b>" + esc(t[1]) + " " + t[2].toFixed(1) + "</b>";
        var lean = function (d) { return d <= -1 ? "<b>leans UNDER</b>" : d >= 1 ? "<b>leans OVER</b>" : "sits with the book"; };
        if (bl) {
          var q = kalshiSideQuote(k, t[3], "OVER", bl.line);
          s += " · the book " + bl.line + " · " + lean(t[2] - bl.line) + (q ? ", the over " + pc(q.p) + " at the book's number" : "");
        } else if (isFinite(tl) && isFinite(spv)) {
          var imp = t[0] === "HOME" ? (tl - spv) / 2 : (tl + spv) / 2;
          s += " · the book's total and spread imply " + imp.toFixed(1) + " · " + lean(t[2] - imp).replace("sits with the book", "sits with that number");
        }
        out.push(signalChip("crowd", "secKalshi", "Kalshi team total", s));
      });
    }
    try {
      var d = nbaOutList(), outs = function (s) { return (d[s] || []).filter(function (p) { return /^out/i.test(String(p.st || "")); }).length; }, oa = outs("away"), oh = outs("home");
      if (oa || oh) out.push(signalChip("info", "secOut", "out", [oa ? esc(away) + " <b>" + oa + "</b> (" + nbaOutMinutes("away").toFixed(0) + " min of regulars)" : "", oh ? esc(home) + " <b>" + oh + "</b> (" + nbaOutMinutes("home").toFixed(0) + " min of regulars)" : ""].filter(Boolean).join(" · ")));
    } catch (e) {}
    return out;
  }
  function signalStrip(m, pk, upsetView, likely, leg) {
    var el = $("signals"); if (!el) return;
    var nav = $("nbaNav"), live = { secOut: [], secSim: [], secMid: [], secCrew: [], secKalshi: [] };
    var list = [];
    if (m) { try { list = signalList(m, pk, upsetView, leg); } catch (e) { list = []; } }
    if (!m) { el.hidden = true; el.innerHTML = ""; }
    else {
      el.hidden = false;
      el.innerHTML = '<div class="sighead">Tonight\'s signals <span class="tag">every engine\'s call on this row · green fires, gold watches, purple the crowd</span></div>' +
        (list.length ? list.map(function (s) { return '<a class="sig ' + s.cls + '" href="#' + s.go + '"><span class="sb">' + esc(s.badge) + '</span><span class="st">' + s.html + '</span></a>'; }).join("")   // two flex items: the badge, then the words as one span, so the gap never splits a sentence
                     : '<span class="quiet">Nothing fires on this row tonight: the sheet\'s pick, the simulation, the agreement rule, the middles and the watches all sit inside their lines.</span>');
    }
    list.forEach(function (s) { if (live[s.go]) live[s.go].push(s); });
    Object.keys(live).forEach(function (id) {
      var t = $(id + "Live"); if (t) t.textContent = live[id].map(function (s) { return s.text; }).join(" · ");
      if (nav) {
        var dot = nav.querySelector('a[data-go="' + id + '"] .dot');
        if (dot) { var top = live[id].filter(function (s) { return s.cls === "go"; })[0] || live[id].filter(function (s) { return s.cls === "watch"; })[0] || live[id][0]; dot.className = "dot" + (top ? " " + top.cls : ""); }
      }
    });
  }
  function kalshiSharpRaw(raw) { var s = null; try { s = raw ? JSON.parse(raw) : null; } catch (e) { s = null; } return s && isFinite(+s.hml) && isFinite(+s.aml) && +s.hml && +s.aml ? s : null; }
  function kalshiSharpOf(row) {
    var i = (row && row.inputs) || {}, k = kalshiOf(i.nbakalshi), sh = kalshiSharpRaw(i.sharp);
    if (!k || !k.ml || !sh) return null;
    var ih = implied(+sh.hml), ia = implied(+sh.aml), ph = ih / (ih + ia), gap = k.ph - ph;   // the crowd above the sharp book on the home side
    if (Math.abs(gap) < KALSHI_GAP) return null;
    return { side: gap > 0 ? "AWAY" : "HOME", pts: Math.abs(gap) * 100, crowdHome: k.ph, sharpHome: ph };
  }
  function kalshiCents(v) { return v === null || v === undefined || !isFinite(+v) ? "–" : (Math.round(+v * 1000) / 10).toFixed(1).replace(/\.0$/, "") + "¢"; }
  function kalshiVol(v) { return v === null || v === undefined || !isFinite(+v) ? "?" : (+v >= 1000 ? Math.round(+v / 1000) + "k" : String(Math.round(+v))) + " contracts"; }
  /* the chip on a moneyline pick card (the board): the exchange's price for the pick's side against the book's, after the fee */
  function kalshiChip(row, mk) {
    if (!row || !mk || row.sport !== "NBA" || (mk.key !== "ml" && mk.key !== "total" && mk.key !== "spread")) return "";
    var k = kalshiOf((row.inputs || {}).nbakalshi); if (!k) return "";
    var line = mk.key === "ml" ? null : (typeof lineOf === "function" ? lineOf(mk) : mk.point), q = kalshiSideQuote(k, mk.key, mk.side, line);
    if (!q) return "";
    var crowd = 'the crowd ' + (q.p * 100).toFixed(1) + '%' + (mk.key === "ml" ? '' : ' at this line');
    if (q.need === null || mk.price === null || mk.price === undefined) return ' <span class="tagm kal">Kalshi: ' + crowd + '</span>';
    var book = implied(+mk.price), better = q.need < book - 0.001;
    return ' <span class="tagm kal' + (better ? ' warn' : '') + '" title="' + (better ? 'The exchange\'s price for this side needs less than the book\'s after Kalshi\'s fee on the win' : 'The book\'s price needs less than the exchange\'s after Kalshi\'s fee on the win') + '">' +
           (better ? 'better on Kalshi: ' : 'Kalshi ') + kalshiCents(q.ask) + ' needs ' + (q.need * 100).toFixed(1) + '% after the fee v ' + sgn(+mk.price, 0) + ' needing ' + (book * 100).toFixed(1) + '%' + (better ? '' : ': the book') + ' · ' + crowd + '</span>';
  }
  function nbaKalshiPanel() {
    var el = $("nbaKalshiPanel"); if (!el) return;
    var k = kalshiOf(($("nbakalshi") || {}).value || "");
    if (!k) { el.innerHTML = "No Kalshi price on the row — load the slate or the odds file and Fill form, and the exchange's game-winner market comes with it."; return; }
    var away = ($("away") || {}).value || "the away side", home = ($("home") || {}).value || "the home side";
    var hml = +(($("hml") || {}).value), aml = +(($("aml") || {}).value), book = null;
    if (isFinite(hml) && isFinite(aml) && hml && aml) { var ih = implied(hml), ia = implied(aml); book = { h: ih / (ih + ia), a: ia / (ih + ia), hml: hml, aml: aml }; }
    var sh = kalshiSharpRaw(($("sharp") || {}).value || ""), pin = null;
    if (sh) { var sh_h = implied(+sh.hml), sh_a = implied(+sh.aml); pin = { h: sh_h / (sh_h + sh_a), a: sh_a / (sh_h + sh_a), hml: +sh.hml, aml: +sh.aml }; }
    var when = k.at ? new Date(k.at) : null, whenTxt = when && !isNaN(when.getTime()) ? when.toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "";
    var pc = function (v) { return (v * 100).toFixed(1) + "%"; };
    var line = function (nick, s, p, pb, pr, ml, need) {
      var bits = ['the crowd <b>' + pc(p) + '</b>'];
      if (pb !== null) bits.push('the book ' + pc(pb) + ' (' + sgn(ml, 0) + ')');
      if (pr !== null) bits.push('Pinnacle ' + pc(pr));
      var price = '';
      if (need !== null && pb !== null) {
        var bn = implied(ml), better = need < bn - 0.001;
        price = ' · ' + (better ? '<b>better on Kalshi</b>: ' : 'the book\'s price: ') + kalshiCents(s.ask) + ' needs ' + pc(need) + ' after the fee against ' + sgn(ml, 0) + ' needing ' + pc(bn);
      } else if (need !== null) price = ' · ' + kalshiCents(s.ask) + ' needs ' + pc(need) + ' after the fee';
      return '<li><b>' + esc(nick) + '</b> ' + kalshiCents(kalshiMid(s)) + ' <span class="dim">(bid ' + kalshiCents(s.bid) + ' / ask ' + kalshiCents(s.ask) + ' · ' + kalshiVol(s.vol) + ')</span>: ' + bits.join(' · ') + price + '</li>';
    };
    var h = '<div class="kalshi"><p><b>The crowd on <span class="kname">Kalshi</span></b>' + (whenTxt ? ' <span class="dim">· as the run read it, ' + esc(whenTxt) + '</span>' : '') + '</p>';
    var gapTxt = "";
    if (k.ml) {
      h += '<ul class="ctx">' + line(away, k.a, k.pa, book ? book.a : null, pin ? pin.a : null, book ? book.aml : null, k.needA) +
           line(home, k.h, k.ph, book ? book.h : null, pin ? pin.h : null, book ? book.hml : null, k.needH) + '</ul>';
      if (pin) {
        var gap = k.ph - pin.h, over = gap > 0 ? home : away, sharp = gap > 0 ? away : home;
        gapTxt = Math.abs(gap) >= KALSHI_GAP
          ? '<p><b>The crowd sits ' + (Math.abs(gap) * 100).toFixed(1) + ' points above Pinnacle on the ' + esc(over) + ': the sharp side is the ' + esc(sharp) + '.</b> <span class="dim">A watch, on the moneyline tile\'s record; the Pinnacle shade on totals hit 56% at three points over two seasons, and this is its moneyline cousin, unmeasured.</span></p>'
          : '<p class="dim">The crowd and Pinnacle sit within three points of each other (' + (Math.abs(gap) * 100).toFixed(1) + ' on the home side): no watch.</p>';
      } else gapTxt = '<p class="dim">No Pinnacle moneyline on the row to set the crowd against (the odds run brings it).</p>';
    } else h += '<p class="dim">No game-winner market on the row.</p>';
    /* the ladders (4 Nov 2026): the crowd's spread and total at even money against the book's numbers, the sheet's chance at the
       book's line and the simulation's, and the price of each side at the book's line when it is a rung of the ladder */
    var sheet = (typeof last !== "undefined" && last && last.markets) ? last.markets : [], sheetOf = function (key) { return sheet.filter(function (m) { return m.key === key; })[0] || null; };
    var sim = typeof nbaSim === "function" ? nbaSim() : null;
    var sideTxt = function (nick, q, bookPrice) {
      if (!q) return '';
      var s = ' · <b>' + esc(nick) + '</b> ' + pc(q.p) + ' by the crowd';
      if (q.need !== null && bookPrice !== null && isFinite(bookPrice)) {
        var bn = implied(bookPrice), better = q.need < bn - 0.001;
        s += (better ? ', <b>better on Kalshi</b>: ' : ', the book\'s price: ') + kalshiCents(q.ask) + ' needs ' + pc(q.need) + ' after the fee against ' + sgn(bookPrice, 0) + ' needing ' + pc(bn);
      } else if (q.need !== null) s += ', ' + kalshiCents(q.ask) + ' on the exchange (needs ' + pc(q.need) + ' after the fee)';
      return s;
    };
    var spIn = ($("sp") || {}).value, sp = spIn === "" || spIn === undefined || isNaN(+spIn) ? null : +spIn, sph = +(($("sph") || {}).value), spa = +(($("spa") || {}).value);
    if (k.margin.length >= 2) {
      var m = k.spMed, mTxt = m === null ? 'no even-money number inside the ladder' : (Math.abs(m) < 0.05 ? 'a pick' : esc(m > 0 ? home : away) + ' ' + sgn(-Math.abs(m), 1));
      var s2 = '<p><b>The spread</b>: the crowd ' + mTxt;
      if (sp !== null) {
        s2 += ' · the book ' + esc(sp <= 0 ? home : away) + ' ' + sgn(-Math.abs(sp), 1);
        var sm = sheetOf("spread"), simSp = sim && sim.own && sim.own.margin ? nbaSimOver(sim.own.margin, -sp) : null;
        var qh = kalshiSideQuote(k, "spread", "HOME", sp), qa = kalshiSideQuote(k, "spread", "AWAY", sp);
        s2 += '. At the book\'s number' + (qh ? ': ' + esc(home) + ' covers ' + pc(qh.p) + ' by the crowd' + (sm && isFinite(+sm.p) ? ', ' + pc(sm.side === "HOME" ? +sm.p : 1 - +sm.p) + ' by the sheet' : '') + (simSp ? ', ' + pc(simSp.over) + ' by the simulation\'s own view' : '') : ': the crowd\'s ladder does not reach it');
        if (qh && qh.rung) s2 += sideTxt(home + ' ' + sgn(sp, 1), qh, isFinite(sph) && sph ? sph : null) + sideTxt(away + ' ' + sgn(-sp, 1), qa, isFinite(spa) && spa ? spa : null);
        else if (qh) s2 += ' · <span class="dim">no rung at the book\'s number on the exchange (its ladder runs on halves), so no price to compare</span>';
      }
      h += s2 + '.</p>';
    }
    var tl = ($("line") || {}).value, line0 = tl === "" || tl === undefined || isNaN(+tl) ? null : +tl, op = +(($("op") || {}).value), up = +(($("up") || {}).value);
    if (k.total.length >= 2) {
      var t = k.totMed, s3 = '<p><b>The total</b>: the crowd ' + (t === null ? 'no even-money number inside the ladder' : t.toFixed(1));
      if (line0 !== null) s3 += ' · the book ' + line0;
      if (sh && isFinite(+sh.line)) s3 += ' · Pinnacle ' + (+sh.line);
      if (sim && sim.own && sim.own.total) { var q50 = nbaSimQ(sim.own.total, 0.5); if (q50 !== null) s3 += ' · the simulation\'s own view ' + q50 + (sim.mkt && sim.mkt.total ? ' (anchored to the market ' + nbaSimQ(sim.mkt.total, 0.5) + ')' : ''); }
      if (line0 !== null) {
        var tm = sheetOf("total"), simT = sim && sim.own && sim.own.total ? nbaSimOver(sim.own.total, line0) : null;
        var qo = kalshiSideQuote(k, "total", "OVER", line0), qu = kalshiSideQuote(k, "total", "UNDER", line0);
        s3 += '. At the book\'s ' + line0 + (qo ? ': the over ' + pc(qo.p) + ' by the crowd' + (tm && isFinite(+tm.p) ? ', ' + pc(tm.side === "OVER" ? +tm.p : 1 - +tm.p) + ' by the sheet' : '') + (simT ? ', ' + pc(simT.over) + ' by the simulation\'s own view' : '') : ': the crowd\'s ladder does not reach it');
        if (qo && qo.rung) s3 += sideTxt('over ' + line0, qo, isFinite(op) && op ? op : null) + sideTxt('under ' + line0, qu, isFinite(up) && up ? up : null);
        else if (qo) s3 += ' · <span class="dim">no rung at the book\'s number on the exchange (its ladder runs two points apart), so no price to compare</span>';
      }
      h += s3 + '.</p>';
    }
    /* the team totals (4 Nov 2026, the user: "Can we also have team totals too?"): a paragraph a club, the crowd's team total at
       even money against the book's team-total line (the odds run's), the number the book's own total and spread imply and the
       simulation's mean; at the book's line the crowd's chance of the over, the simulation's, and on a rung each side's price */
    var oddsRaw = ($("odds") || {}).value || "";
    [["AWAY", away, k.ttA, k.ttAMed, "away"], ["HOME", home, k.ttH, k.ttHMed, "home"]].forEach(function (t) {
      var side = t[0], nick = t[1], lad = t[2], med = t[3], hk = t[4];
      if (lad.length < 2) return;
      var bl = typeof nbaTeamTotalLine === "function" ? nbaTeamTotalLine(oddsRaw, side) : null, imp = line0 !== null && sp !== null ? (side === "HOME" ? (line0 - sp) / 2 : (line0 + sp) / 2) : null;
      var hist = sim && sim.own ? sim.own[hk] : null, simMean = hist ? nbaSimMean(hist) : null;
      var s4 = '<p><b>The ' + esc(nick) + ' team total</b>: the crowd ' + (med === null ? 'no even-money number inside the ladder' : med.toFixed(1));
      if (bl) s4 += ' · the book ' + bl.line + ' (' + esc(String(bl.book)) + ' ' + sgn(bl.op, 0) + '/' + sgn(bl.up, 0) + ')';
      if (imp !== null) s4 += ' · implied by the book\'s total and spread ' + imp.toFixed(1);
      if (simMean !== null) s4 += ' · the simulation\'s own view ' + simMean.toFixed(1);
      if (bl) {
        var qo = kalshiSideQuote(k, hk + "_total", "OVER", bl.line), qu = kalshiSideQuote(k, hk + "_total", "UNDER", bl.line), simO = hist ? nbaSimOver(hist, bl.line) : null;
        s4 += '. At the book\'s ' + bl.line + (qo ? ': the over ' + pc(qo.p) + ' by the crowd' + (simO ? ', ' + pc(simO.over) + ' by the simulation\'s own view' : '') : ': the crowd\'s ladder does not reach it');
        if (qo && qo.rung) s4 += sideTxt('over ' + bl.line, qo, bl.op) + sideTxt('under ' + bl.line, qu, bl.up);
        else if (qo) s4 += ' · <span class="dim">no rung at the book\'s number on the exchange, so no price to compare</span>';
      } else s4 += ' · <span class="dim">no book team total on the row (the odds run brings it)</span>';
      h += s4 + '.</p>';
    });
    el.innerHTML = h + gapTxt + '<p class="dim">Shown, not scored: a prediction market\'s price is a market price, which is already the sheet\'s spine. The fee is Kalshi\'s on the win, ' + (k.fee * 100).toFixed(0) + '% of the expected profit a contract.</p></div>';
  }
  function nbaCtxPanel() {
    var el = $("nbaCtxPanel"); if (!el) return;
    var raw = ($("nbactx") || {}).value || "", ctx = null;
    try { ctx = raw ? JSON.parse(raw) : null; } catch (e) { ctx = null; }
    var items = (ctx || []).slice();
    if (!items.length) {
      el.innerHTML = "No context on the row — load the slate and Fill form, and the lines come with it.";
      return;
    }
    var order = { scored: 0, faded: 1, shown: 2, label: 3 };
    items.sort(function (a, b) { return (order[a.s] || 0) - (order[b.s] || 0); });
    el.innerHTML = '<ul class="ctx">' + items.map(function (c) {
      var s = order[c.s] !== undefined ? c.s : "shown";
      return '<li class="ctx-' + s + '"><span class="cbadge">' + s + '</span> <span class="ctext">' + esc(c.t || "") + '</span>' +
             (c.tag ? ' <span class="ctag">' + esc(c.tag) + '</span>' : '') + '</li>';
    }).join("") + '</ul>';
  }
  /* the Referee stats card (22 Oct 2026, the user: "change the name from context to Referee stats... make sure that's set
     up for all NBA games"): the crew line on its own card, highlighted in the crew's lean with a badge, each official a
     chip with his past record, his own lean and this season; the sentence is nbaCrewLine's, unchanged */
  function nbaCrewPanel() {
    var el = $("nbaCrewPanel"); if (!el) return;
    var crew = nbaCrewLine();
    if (!crew) { el.innerHTML = "No crew on the row — load the slate and Fill form once the league has posted the assignments (about 9 am Eastern), or type the names below."; return; }
    var refsRaw = ($("nbarefs") || {}).value || "", refsD = null;
    try { refsD = refsRaw ? JSON.parse(refsRaw) : null; } catch (e) { refsD = null; }
    var det = nbaCrewDetails(nbaCrewNames(($("ncrew") || {}).value), refsD), lean = det && det.found ? det.lean : "even";
    var alert = lean === "even" ? '<span class="crewalert even">' + (det && det.found ? 'Crew even' : 'Crew unread') + '</span>' : '<span class="crewalert ' + lean + '">Crew leans ' + lean.toUpperCase() + ' · z ' + sgn(det.z, 1) + '</span>';
    var chips = det ? det.officials.map(function (o) {
      return '<span class="refchip ' + o.lean + '">' + esc(o.name) + (o.d ? ' <b>' + o.pastW + '-' + o.pastL + '</b>' + (o.lean !== "even" ? ' ' + o.lean.toUpperCase() + ' LEAN' : '') + (o.thisW + o.thisL ? ' · ' + o.thisW + '-' + o.thisL + ' this season' : '') : ' <span class="dim">no games</span>') + '</span>';
    }).join("") : "";
    /* the crew call (22 Oct 2026, the user: "maybe a little prediction too"): what the numbers say for tonight, with the
       honest weights: free throws against the league (the one thing a crew predicts, t 7.3), points a game by their history
       (the total did not follow, t -1.0), and the past table's over rate with these three as a soft lean. Never scored */
    var call = "";
    if (det && det.found) {
      var known = det.officials.filter(function (o) { return o.d; }), lg = refsD && refsD.lg ? refsD.lg : null;
      var fta = known.reduce(function (a, o) { return a + (+o.d[1] || 0); }, 0) / known.length, pts = known.reduce(function (a, o) { return a + (+o.d[2] || 0); }, 0) / known.length;
      var past = det.pastW + det.pastL, rate = past ? det.pastW / past : 0.5;
      var leanTxt = lean === "over" ? "a soft lean to the OVER" : lean === "under" ? "a soft lean to the UNDER" : "no lean";
      call = '<div class="crewcall"><b>Crew call for tonight:</b> ' +
             (lg ? 'free throws ' + sgn(fta - (+lg[1]), 1) + ' against the league\'s ' + (+lg[1]).toFixed(1) + ' (the one thing a crew predicts, t 7.3); points ' + sgn(pts - (+lg[2]), 1) + ' a game by their history' : 'free throws ' + fta.toFixed(1) + ' and points ' + pts.toFixed(1) + ' a game by their history') +
             (past ? '; the past table\'s over rate with these ' + known.length + ' is <b>' + (rate * 100).toFixed(1) + '%</b> on ' + past + ' games, ' + leanTxt : '') +
             '. <span class="dim">Shown, not scored: the total did not follow the crew over two seasons of closes; the referee watch on the record is the test.</span></div>';
    }
    el.innerHTML = '<div class="crewblock lean-' + lean + '"><span class="cbadge">shown</span> ' + alert + ' <span class="ctext">' + esc(crew.t || "") + '</span>' +
                   '<span class="crewchips">' + chips + '</span>' + call + (crew.tag ? ' <span class="ctag">' + esc(crew.tag) + '</span>' : '') + '</div>';
  }
  function forecastMatchupNba() {
    if (!SRC) { nbaOutPanel(); nbaLineupPanel(); nbaFormPanel(); nbaSimPanel(); nbaMidPanel(); nbaCrewPanel(); nbaKalshiPanel(); nbaCtxPanel(); }   // the form's panels: not while a card row is being re-scored
    var f = readNba();
    var away = f.away, home = f.home, line = f.line;
    var op = num("op"), up = num("up"), hml = num("hml"), aml = num("aml");
    var spIn = num("sp"), sph = num("sph"), spa = num("spa");
    var h1line = num("h1line"), h1op = num("h1op"), h1up = num("h1up");
    var notes = [], markets = [];
    markets.push(totalMarket(f, line, op, up, 1));
    var anchor = f.estimates.filter(function (e) { return e.name === "Market"; })[0].total;
    var projH1 = null;
    if (h1line !== null) {
      if (!ok(h1line, "nba_half")) throw new Error("first-half total out of range");
      var fh = nbaFairTotal("NBA_H1", h1line, h1op, h1up), lean1 = (f.projected - anchor) * NBA.HALF_SHARE;
      projH1 = fh[0] + lean1;
      var s1 = nbaHalfSplit(h1line, projH1);
      markets.push(pickOf("h1", "First half total " + h1line,
        [sideOf("1H OVER " + h1line, "OVER", s1[0], s1[1], h1op), sideOf("1H UNDER " + h1line, "UNDER", s1[2], s1[1], h1up)],
        h1op !== null && h1up !== null, "",
        ["Anchored on the first-half market: " + fh[1],
         "The full game's lean, " + sgn(f.projected - anchor, 1) + " on its anchor, comes over at the half's " + (NBA.HALF_SHARE * 100).toFixed(1) + "% share: " + sgn(lean1, 1) +
         ". The share holds at every total level (0.5037 under 220, 0.5003 at 240 and up); the half spreads " + NBA.HALF_SD + " points on its number.",
         "Projected " + projH1.toFixed(1) + " against " + h1line + "."]));
    }
    var margin = null, src = "";
    if (spIn !== null) { var ms = nbaMarginFromSpread(spIn, sph, spa); margin = ms[0]; src = ms[1]; }
    else if (hml !== null && aml !== null) {
      var pHm = devig(hml, aml)[0];
      margin = -NBA.MARGIN_SD * invNcdf(1 - pHm);
      src = "moneyline " + sgn(hml, 0) + "/" + sgn(aml, 0) + ", " + (pHm * 100).toFixed(1) + "% home";
    }
    var lamH = null, lamA = null;
    if (margin === null) {
      notes.push("No spread or moneyline entered, so no side markets on this card.");
    } else {
      notes.push("Margin (home minus away) of <b>" + sgn(margin, 1) + "</b> from the " + src + ", on a margin SD of " + NBA.MARGIN_SD + ". Nothing on this sheet moves it: against two seasons of closes the pace x efficiency margin projection read 0.00 on the spread, and rest, travel, time zones and announced absences all sat inside the number. The sides are the book's own number read back, shown and graded, never the pick.");
      var halfT = f.projected / 2;
      lamH = halfT + margin / 2; lamA = halfT - margin / 2;
      if (spIn !== null && spIn <= -10) notes.push("A home favourite of ten or more: against two seasons of closes these covered by +0.84 a game (426 games, +1.28 and +0.42 by season, t 1.3). Watched, not scored.");
      /* the WNBA card's pattern, early in the season: a watch, not scored (totals/nba.py EARLY_SIDE_*) */
      var rm = nbaRatingsMargin(num("naort"), num("nhort"), num("nadrt"), num("nhdrt"), num("napace"), num("nhpace"), num("nlrtg"), num("nlpace"));
      var agS = num("nagp"), hgS = num("nhgp"), nSide = (agS !== null && hgS !== null) ? Math.min(agS, hgS) : null;
      if (rm !== null && nSide !== null && nSide >= NBA.MIN_GAMES && nSide < NBA.EARLY_SIDE_GAMES && Math.abs(rm - margin) >= NBA.EARLY_SIDE_LEAN) {
        notes.push("<b>Early-season side watch</b>: the ratings' margin projects " + sgn(rm, 1) + " against the market's " + sgn(margin, 1) + ", " + Math.abs(rm - margin).toFixed(1) + " points toward the " +
          esc(rm > margin ? home : away) + ". <b>WATCHED, NOT SCORED</b>: in a club's first " + NBA.EARLY_SIDE_GAMES + " games the ratings' side at " + NBA.EARLY_SIDE_LEAN + "+ points of lean went 148-124 (54.4%; slope +0.156 a point, t 1.5) against two seasons of closes, " +
          "then 135-143 from thirty to sixty games and 113-125 after, 394-394 over the whole. The WNBA card's spread scores the ratings at 1.2 against the market's 4.0 and is 7-0 informed on seven games; on the NBA that blend went 351-344 at a point of lean. The record section keeps this watch from opening night.");
      }
      /* the short dog, SCORED and tagged (totals/nba.py SHORT_DOG_*); the rest of the upset watch named, not scored */
      var pH = 1 - ncdf((0 - margin) / NBA.MARGIN_SD);
      var pHomeBook = (hml !== null && aml !== null) ? devig(hml, aml)[0] : pH;
      var favHomeU = pHomeBook >= 0.5, dogU = favHomeU ? away : home, favU = favHomeU ? home : away, pDogBook = favHomeU ? 1 - pHomeBook : pHomeBook;
      var favOutU = favHomeU ? nbaOutMinutes("home") : nbaOutMinutes("away"), arU = num("narest"), hrU = num("nhrest"), favRestU = favHomeU ? hrU : arU, watchU = [];
      var mlNotesN = ["Read off the margin through a normal at " + NBA.MARGIN_SD + ", which fits the spread's home win rate within a few points at every bucket (big home dogs win a little less than it says). An edge here is only the book's moneyline disagreeing with its own spread."];
      var shortDog = pDogBook >= NBA.SHORT_DOG_MIN;
      if (shortDog) {
        pH = favHomeU ? pH - NBA.SHORT_DOG_LIFT : pH + NBA.SHORT_DOG_LIFT;
        mlNotesN.push("<b>UPSET SIGNAL, the short dog</b>: the book makes " + esc(dogU) + " " + (pDogBook * 100).toFixed(1) + "% and the market under-prices a dog this short. Against two seasons of closing moneylines dogs at 40% or better won 315 of 626 against 280 priced (+5.6 points, z 2.8, +5.6 and +5.6 by season; +9.8% a bet at the best retail price). " +
          sgn(NBA.SHORT_DOG_LIFT * 100, 0) + " points to " + esc(dogU) + ", tagged: this side is pickable on the record's own line.");
        watchU.push(esc(dogU) + " a short dog at " + (pDogBook * 100).toFixed(0) + "% (scored, " + sgn(NBA.SHORT_DOG_LIFT * 100, 0) + " points)" +
          (favOutU >= 20 ? "; " + esc(favU) + " missing " + favOutU.toFixed(0) + " minutes of regulars, where the short dog ran +7.3 (460 games) against +0.8 at full strength" : ""));
      }
      if (favOutU >= 40) watchU.push(esc(favU) + " missing " + favOutU.toFixed(0) + " minutes a game of regulars: dogs won +2.1 points more than priced on 926 such games (z 1.5; -0.2 and +3.4 by season)");
      if (Math.abs(margin) >= 10 && favRestU !== null && favRestU <= 0) watchU.push(esc(favU) + " a favourite of ten or more on a back to back: dogs won +3.9 points more than priced on 86 games (z 1.0; +0.4 and +7.2)");
      if (rm !== null && nSide !== null && nSide >= NBA.MIN_GAMES && nSide < NBA.EARLY_SIDE_GAMES && (favHomeU ? (margin - rm) : (rm - margin)) >= NBA.EARLY_SIDE_LEAN)
        watchU.push("the ratings like " + esc(dogU) + " by " + Math.abs(rm - margin).toFixed(1) + " points more than the market in the first thirty games: dogs won +10.0 points more than priced on 89 games (z 2.0, but +0.4 and +25.5 by season: one season's)");
      var stU = nbaStageOf(($("gdate") || {}).value);
      if (stU) watchU.push(stU[1] + ": FEWER upsets, dogs won " + (stU[0] === NBA.LAST_TWO_WEEKS_DELTA ? "4.9" : "2.4") + " points less than priced (z -1.8); the favourites run through the tankers");
      if (watchU.length) notes.push("<b>Upset watch</b>, " + esc(dogU) + ((hml !== null && aml !== null) ? " at " + sgn(favHomeU ? aml : hml, 0) : "") + ": " + watchU.join("; ") +
        (shortDog ? ". The scored signal is the short dog; the rest are watched on the record." : ". <b>WATCHED, NOT SCORED</b>: none of these clears noise with the same sign both seasons; the record decides."));
      var mlmN = pickOf("ml", "Moneyline",
        [sideOf(home + " ML", "HOME", pH, 0, hml), sideOf(away + " ML", "AWAY", 1 - pH, 0, aml)],
        hml !== null && aml !== null, "", mlNotesN);
      mlmN.informed = shortDog;
      markets.push(mlmN);
      if (spIn !== null) {
        var pr = spreadProbs(margin, spIn, NBA.MARGIN_SD);
        markets.push(pickOf("spread", "Spread " + home + ": " + fmtLine(spIn),
          [sideOf(home + " " + fmtLine(spIn), "HOME", pr[0], pr[1], sph), sideOf(away + " " + fmtLine(-spIn), "AWAY", pr[2], pr[1], spa)],
          sph !== null && spa !== null, "",
          ["The spread with both prices in is the anchor and nothing moves it off: the sides are priced. Shown and graded, never the pick."]));
      }
    }
    if (!SRC) nbaVoicesFill({ markets: markets });   // the three voices on the total (28 Oct 2026), with this render's sheet
    return { sport: "NBA", away: away, home: home, matchup: away + " @ " + home, markets: markets, lamHome: lamH, lamAway: lamA, total: f, notes: notes, period: projH1 };
  }
  /* ---- the who-is-out panel: each side's list, the regulars' minutes summed, a tick for the doubtful ---- */
  function nbaOutPanel() {
    var el = $("nbaOutPanel"); if (!el) return;
    var d = nbaOutList(), ticked = nbaTicked(), h = "";
    var any = (d.away || []).length || (d.home || []).length;
    if (!any) { el.innerHTML = "No list on the row — load the slate and Fill form, and each side's injury report comes with it."; return; }
    [["away", canonTeam($("away").value, "NBA") || "Away"], ["home", canonTeam($("home").value, "NBA") || "Home"]].forEach(function (s) {
      var list = d[s[0]] || [], mins = nbaOutMinutes(s[0]);
      h += "<p><b>" + esc(s[1]) + "</b>: " + (list.length ? list.length + " listed, <b>" + mins.toFixed(0) + " minutes a game</b> of regulars out." : "nobody listed.") + "</p>";
      if (!list.length) return;
      h += '<table class="form"><thead><tr><th>Player</th><th>Status</th><th>Min</th><th>Pts</th><th>+/-</th><th>Note</th><th>Out?</th></tr></thead><tbody>';
      list.forEach(function (p) {
        var isOut = /^out/i.test(String(p.st || "")), id = String(p.id || p.n);
        var box = isOut ? "out" : '<input type="checkbox" data-q="' + esc(id) + '"' + (ticked.indexOf(id) >= 0 ? " checked" : "") + ' title="Tick when he is ruled out">';
        var ret = p.ret && /^\d{4}-\d{2}-\d{2}$/.test(String(p.ret)) ? MONTHS[+String(p.ret).slice(5, 7) - 1] + " " + (+String(p.ret).slice(8, 10)) : (p.ret || "");
        var note = esc(p.note || "") + (ret ? (p.note ? "; " : "") + "back " + esc(ret) + (p.past ? " (before this game: likely stale)" : "") : "") + (p.src === "last season" ? '<span class="dim"> (last season\'s line)</span>' : "");
        h += "<tr" + (isOut || ticked.indexOf(id) >= 0 ? ' class="out"' : "") + "><td>" + esc(p.n || "?") + (p.c ? '<div class="dim">' + esc(p.c) + "</div>" : "") + "</td><td>" + esc(p.st || "") + "</td><td>" + (p.mpg !== undefined && p.mpg !== null ? (+p.mpg).toFixed(1) : "—") +
             "</td><td>" + (p.ppg !== undefined && p.ppg !== null ? (+p.ppg).toFixed(1) : "—") + "</td><td>" + (p.pm !== undefined && p.pm !== null ? sgn(+p.pm, 1) : "—") + "</td><td>" + note + "</td><td>" + box + "</td></tr>";
      });
      h += "</tbody></table>";
    });
    el.innerHTML = h;
  }
  /* ---- the starting five (20 Oct 2026): RotoWire's expected or confirmed lineup for each
     club, written by the slate into the hidden nbalineup box with the men who may not play
     under it. Shown beside the who-is-out list, never scored; the engine does not read it ---- */
  function nbaLineup() {
    var raw = ($("nbalineup") || {}).value || "", d = null;
    try { d = raw ? JSON.parse(raw) : null; } catch (e) { d = null; }
    return d && typeof d === "object" ? d : {};
  }
  function nbaLineupPanel() {
    var el = $("nbaLineupPanel"); if (!el) return;
    var d = nbaLineup();
    if (!d.away && !d.home) { el.innerHTML = "No lineup on the row — load the slate and Fill form, and RotoWire's starting five for each side comes with it (today's and tomorrow's games only)."; return; }
    var h = '<div class="grid2 fives">';
    [["away", canonTeam($("away").value, "NBA") || "Away"], ["home", canonTeam($("home").value, "NBA") || "Home"]].forEach(function (s) {
      var L = d[s[0]];
      h += '<div class="five" data-side="' + s[0] + '">';
      if (!L) { h += "<p><b>" + esc(s[1]) + "</b> <span class=\"lbadge none\">no lineup</span> <span class=\"dim\">RotoWire has not posted this side yet.</span></p></div>"; return; }
      var st = String(L.status || "").toLowerCase(), word = st === "confirmed" ? "confirmed" : st === "expected" ? "expected" : (st || "lineup");
      h += "<p><b>" + esc(s[1]) + "</b> <span class=\"lbadge " + (st === "confirmed" ? "conf" : "exp") + "\">" + esc(word) + "</span></p>";
      h += '<table class="form"><tbody>' + (L.five || []).map(function (p) {
        return "<tr><td class=\"pos\">" + esc(p[0] || "") + "</td><td>" + esc(p[1] || "") + "</td></tr>";
      }).join("") + "</tbody></table>";
      if ((L.maybe || []).length) h += '<p class="dim">May not play: ' + L.maybe.map(function (p) { return (p[0] ? esc(p[0]) + " " : "") + esc(p[1] || "") + (p[2] ? " (" + esc(p[2]) + ")" : ""); }).join("; ") + ".</p>";
      h += "</div>";
    });
    h += "</div>";
    if (d.src) h += '<p class="dim">Source: ' + esc(d.src) + ", as the slate read it. Expected is the morning's lineup; confirmed is the club's.</p>";
    el.innerHTML = h;
  }
  document.addEventListener("change", function (e) {
    var t = e.target;
    if (!t || !t.getAttribute || !t.getAttribute("data-q") || !$("nbaq")) return;
    var id = t.getAttribute("data-q"), ticked = nbaTicked().filter(function (x) { return x !== id; });
    if (t.checked) ticked.push(id);
    $("nbaq").value = ticked.join(",");
    $("nbaq").dispatchEvent(new Event("input", { bubbles: true }));
  });

  /* ---- the team table: an NBA page, same ordered first-hit-wins rule ------- */
  TEAM_PATTERNS.NBA = [
    ["Trail Blazers", /trail|blazer|portland|\bpor\b/],
    ["76ers",         /76|sixers|philadelphia|\bphi\b/],
    ["Timberwolves",  /timberwol|\bwolves\b|minnesota|\bmin\b/],
    ["Hawks",         /hawk|atlanta|\batl\b/],
    ["Celtics",       /celtic|boston|\bbos\b/],
    ["Nets",          /\bnets?\b|brooklyn|\bbkn\b/],
    ["Hornets",       /hornet|charlotte|\bcha\b/],
    ["Bulls",         /\bbulls?\b|chicago|\bchi\b/],
    ["Cavaliers",     /cavalier|\bcavs\b|cleveland|\bcle\b/],
    ["Mavericks",     /maverick|\bmavs\b|dallas|\bdal\b/],
    ["Nuggets",       /nugget|denver|\bden\b/],
    ["Pistons",       /piston|detroit|\bdet\b/],
    ["Warriors",      /warrior|golden state|\bgsw\b|\bgs\b/],
    ["Rockets",       /rocket|houston|\bhou\b/],
    ["Pacers",        /pacer|indiana|\bind\b/],
    ["Clippers",      /clipper|\blac\b/],
    ["Lakers",        /laker|\blal\b/],
    ["Grizzlies",     /grizzl|memphis|\bmem\b/],
    ["Heat",          /\bheat\b|miami|\bmia\b/],
    ["Bucks",         /\bbucks?\b|milwaukee|\bmil\b/],
    ["Pelicans",      /pelican|\bpels\b|new orleans|\bnop\b|\bno\b/],
    ["Knicks",        /knick|\bnyk\b|\bny\b/],
    ["Thunder",       /thunder|oklahoma|\bokc\b/],
    ["Magic",         /magic|orlando|\borl\b/],
    ["Suns",          /\bsuns?\b|phoenix|\bphx\b/],
    ["Kings",         /\bkings?\b|sacramento|\bsac\b/],
    ["Spurs",         /spur|san antonio|\bsas\b|\bsa\b/],
    ["Raptors",       /raptor|toronto|\btor\b/],
    ["Jazz",          /\bjazz\b|\butah\b|\buta\b/],
    ["Wizards",       /wizard|washington|\bwas\b|\bwsh\b/]
  ];
  var canonTeamBaseNba = canonTeam, teamsForBaseNba = teamsFor;
  canonTeam = function (sRaw, sport) {
    if (sport !== "NBA") return canonTeamBaseNba(sRaw, sport);
    var s = String(sRaw === undefined || sRaw === null ? "" : sRaw).trim();
    if (!s) return "";
    var low = s.toLowerCase(), list = TEAM_PATTERNS.NBA;
    for (var i = 0; i < list.length; i++) if (list[i][1].test(low)) return list[i][0];
    return s;
  };
  teamsFor = function (sport) {
    if (sport !== "NBA") return teamsForBaseNba(sport);
    return TEAM_PATTERNS.NBA.map(function (p) { return p[0]; }).sort();
  };
  /* ---- recent form (22 Oct 2026, the user: "add in the last 5 games for the teams like you do for
     NHL, with the scores like first half, total and spread covered or no, and with a little color"):
     the slate writes each side's last five finals from the ledger into the hidden nbaform box with
     the half-time score and the close the odds run last saw (the total, the first-half total, the
     home spread). A game the odds run never saw borrows the close from this card's own row when the
     game is on it. Shown, never scored ---- */
  function nbaForm() {
    var raw = ($("nbaform") || {}).value || "", d = null;
    try { d = raw ? JSON.parse(raw) : null; } catch (e) { d = null; }
    return d && typeof d === "object" ? d : {};
  }
  function nbaCardCloseFor(date, awayNick, homeNick) {
    var hit = card.filter(function (r) {
      return r.sport === "NBA" && (r.gdate || "") === date && canonTeam(r.away, "NBA") === canonTeam(awayNick, "NBA") && canonTeam(r.home, "NBA") === canonTeam(homeNick, "NBA");
    })[0];
    if (!hit) return {};
    var i = hit.inputs || {}, c = hit.close || {};
    var num = function (v) { var x = parseFloat(v); return isFinite(x) ? x : null; };
    return { ctot: num(c.ctot) !== null ? num(c.ctot) : num(i.line), ch1: num(c.cf5) !== null ? num(c.cf5) : num(i.h1line), csp: num(i.sp) };
  }
  function nbaFormPanel() {
    var el = $("nbaFormPanel"); if (!el) return;
    var d = nbaForm();
    if (!(d.away || []).length && !(d.home || []).length) { el.innerHTML = "No recent games on the row — load the slate and Fill form, and each side's last five come with it."; return; }
    var chip = function (cls, text) { return '<span class="chip ' + cls + '">' + esc(text) + '</span>'; };
    var h = "";
    [["away", canonTeam($("away").value, "NBA") || "Away"], ["home", canonTeam($("home").value, "NBA") || "Home"]].forEach(function (s) {
      var games = d[s[0]] || [];
      if (!games.length) { h += "<p><b>" + esc(s[1]) + "</b>: no finals in the ledger yet.</p>"; return; }
      var w = 0, ov = 0, un = 0, cov = 0, ncov = 0, pf = 0, pa = 0, h1f = 0, h1a = 0, nH1 = 0, h1o = 0, h1u = 0;
      var rows = games.map(function (g) {
        var us = +g.pf, them = +g.pa, hasScore = isFinite(us) && isFinite(them);
        var won = hasScore && us > them;
        if (won) w++;
        if (hasScore) { pf += us; pa += them; }
        var hasH1 = g.h1f !== null && g.h1f !== undefined && g.h1a !== null && g.h1a !== undefined;
        if (hasH1) { h1f += +g.h1f; h1a += +g.h1a; nH1++; }
        var awayNick = g.home ? g.opp : s[1], homeNick = g.home ? s[1] : g.opp;   // this side at home: the opponent was the visitor
        var fb = (g.ctot === null || g.ctot === undefined || g.csp === null || g.csp === undefined || g.ch1 === null || g.ch1 === undefined) ? nbaCardCloseFor(g.date, awayNick, homeNick) : {};
        var ctot = g.ctot !== null && g.ctot !== undefined ? +g.ctot : fb.ctot, ch1 = g.ch1 !== null && g.ch1 !== undefined ? +g.ch1 : fb.ch1, csp = g.csp !== null && g.csp !== undefined ? +g.csp : fb.csp;
        var total = hasScore ? us + them : null, totCell = "—", h1Cell = "—", spCell = "—";
        if (total !== null && ctot !== null && ctot !== undefined) {
          if (total > ctot) { ov++; totCell = chip("over", "OVER") + " " + total + "/" + ctot; }
          else if (total < ctot) { un++; totCell = chip("under", "UNDER") + " " + total + "/" + ctot; }
          else totCell = chip("push", "PUSH") + " " + total;
        } else if (total !== null) totCell = total + ' <span class="dim">no close</span>';
        if (hasH1) {
          var h1t = (+g.h1f) + (+g.h1a);
          h1Cell = esc(g.h1f) + "–" + esc(g.h1a);
          if (ch1 !== null && ch1 !== undefined) { if (h1t > ch1) { h1o++; h1Cell += " " + chip("over", "O " + ch1); } else if (h1t < ch1) { h1u++; h1Cell += " " + chip("under", "U " + ch1); } else h1Cell += " " + chip("push", "push"); }
        }
        if (hasScore && csp !== null && csp !== undefined) {
          var ours = g.home ? csp : -csp, margin = us - them + ours;   // the home spread turned to this side's view, then the result against it
          spCell = (ours >= 0 ? "+" : "") + ours + " " + (margin > 0 ? chip("win", "COVERED") : margin < 0 ? chip("loss", "NO") : chip("push", "PUSH"));
          if (margin > 0) cov++; else if (margin < 0) ncov++;
        }
        return "<tr><td>" + esc(String(g.date || "").slice(5)) + "</td><td>" + (g.home ? "v " : "@ ") + esc(g.opp || "?") + "</td>" +
               "<td>" + (hasScore ? chip(won ? "win" : "loss", won ? "W" : "L") + " " + us + "–" + them + (g.end && g.end !== "REG" ? " (" + esc(g.end) + ")" : "") : "—") + "</td>" +
               "<td>" + h1Cell + "</td><td>" + totCell + "</td><td>" + spCell + "</td></tr>";
      });
      var n = games.length;
      h += "<p><b>" + esc(s[1]) + "</b> last " + n + ": <b>" + w + "-" + (n - w) + "</b>" + (ov + un ? ", over " + ov + "-" + un : "") + (cov + ncov ? ", covered " + cov + "-" + ncov : "") +
           (n ? ", " + (pf / n).toFixed(1) + " for and " + (pa / n).toFixed(1) + " against" : "") + (nH1 ? ", the half " + (h1f / nH1).toFixed(1) + "–" + (h1a / nH1).toFixed(1) + (h1o + h1u ? " (over " + h1o + "-" + h1u + ")" : "") : "") + ".</p>" +
           '<div class="scroll"><table class="form nbaform"><thead><tr><th>Date</th><th>Opp</th><th>Result</th><th>Half</th><th>Total</th><th>Spread</th></tr></thead><tbody>' + rows.join("") + "</tbody></table></div>";
    });
    el.innerHTML = h;
  }
  /* ---- the referees as a watch (22 Oct 2026, the user: "add the tile so I can see it build... I want
     to see what impact the refs have on the game, even if small"). The frozen two-season table the
     slate writes into the row's nbarefs box gives each official's over/under record against the
     close; an official 1.5 sigma or more over or under across those seasons leans, the crew's lean is
     the sum of its three, and this block keeps the season's graded totals against the close by the
     crew's lean, with the points over the close a game. Shown, never scored: the decision is the
     season's end, and the test is whether the past table's lean carries ---- */
  /* ---- the simulation (25 Oct 2026): the slate plays each game NBA_SIM_RUNS times, twice, and the row carries the
     distributions as histograms. The sim's OWN view: the ledger's ratings, pace and shot mix, who is out, rest, the crew.
     The MARKET-ANCHORED view: the same game centred on the scoreboard book's total and spread, for the derivative
     markets (the first half, the quarters, the team totals). The page reads the chance of any line off the histograms,
     so the calls follow the lines on the row, and the record keeps says against does by band from the first night. */
  function nbaSim() {
    var raw = ($("nbasim") || {}).value || "", d = null;
    try { d = raw ? JSON.parse(raw) : null; } catch (e) { d = null; }
    return d && d.own ? d : null;
  }
  function nbaSimOver(h, line) {
    if (!h || line === null || line === undefined || line === "" || isNaN(+line)) return null;
    var n = 0, over = 0, push = 0, L = +line;
    h.c.forEach(function (c, i) { n += c; var v = h.lo + i; if (v > L) over += c; else if (v === L) push += c; });
    if (!n) return null;
    var live = n - push;
    return { over: live ? over / live : 0.5, push: push / n, n: n };
  }
  function nbaSimQ(h, p) {
    if (!h) return null;
    var n = h.c.reduce(function (a, b) { return a + b; }, 0), acc = 0;
    for (var i = 0; i < h.c.length; i++) { acc += h.c[i]; if (acc >= p * n) return h.lo + i; }
    return h.lo + h.c.length - 1;
  }
  function nbaSimMean(h) {
    if (!h) return null;
    var n = 0, s = 0;
    h.c.forEach(function (c, i) { n += c; s += c * (h.lo + i); });
    return n ? s / n : null;
  }
  function nbaSimBand(p, bands) {
    var c = Math.max(p, 1 - p), b = bands || [[0.7, "STRONG"], [0.65, "BET"], [0.6, "LEAN"]];
    for (var i = 0; i < b.length; i++) if (c >= b[i][0]) return b[i][1];
    return "no call";
  }
  /* the worth (26 Oct 2026): the team totals' shrink depends on the view and the side (nbasim.SHRINK); a row stored before
     the split lacks the new keys, so the measured defaults stand in. The band is read off the WORTH, not the raw chance,
     so a 71% that is worth 56% reads as no call and a 57% worth 61% reads LEAN: the replay's answer, not the sim's say-so */
  /* The home side's boost withdrawn (11 Nov 2026). The anchored home team total carried 1.5: the replay had its calls
     landing 60.7% and 59.0% over two seasons. The lines it was replayed on were not the book's. The season pull kept one
     line a book as the FIRST point listed with the LAST over and under prices, and the one book it read in 2025-26 was
     BetRivers on 673 of 674 games, which lists four or five team-total points a side. This season's rows keep every point,
     so the fault can be replayed on them: the point that pull would have kept is BetRivers' main line on three sides in
     ten and one or two points off it on the rest, a "gap" of a point or more shows on 63% of sides where the main line
     shows one on 2%, and the call on the kept point lands 111-77 (59.0%), +23.0 units at the prices kept beside it and
     +0.9 at the point's own. So the boost measured the fault, not the sim: an alternate's number at another line's price.
     The home side reads at the 0.3 of its two siblings on every row, whatever shrink the slate stored with it
     (NBA_SIM_SHRINK_RULES), and the record keeps what the boost would have called as a watch, so the place can be earned
     back on lines that are the book's. The gap rule below went the same way for the same reason */
  var NBA_SIM_SHRINK_DEFAULT = { team: 0.3, team_away: 0.3, team_own: 0.3 };
  var NBA_SIM_SHRINK_RULES = { team: 0.3 };   // the page's word over the row's: every slate written before 11 Nov 2026 stored 1.5
  var NBA_SIM_TEAM_WAS = 1.5;                 // the withdrawn boost, kept to tally what it would have called
  function nbaSimWorth(p, kind, shrink) { var k = NBA_SIM_SHRINK_RULES[kind]; if (k === undefined || k === null) k = (shrink || {})[kind]; if (k === undefined || k === null) k = NBA_SIM_SHRINK_DEFAULT[kind]; if (k === undefined || k === null) k = 1; return Math.max(0, Math.min(1, 0.5 + (p - 0.5) * k)); }
  function nbaSimTeamKind(view, key) { return view === "own" ? "team_own" : key === "away_total" ? "team_away" : "team"; }
  /* every call the row's lines allow, from one view's histograms: {key, view, label, line, side, p, worth, band, push} */
  function nbaSimCalls(sim, lines, view) {
    var H = sim[view]; if (!H) return [];
    var out = [], bands = sim.bands, shrink = sim.shrink || {};
    var add = function (key, kind, label, line, r, first, second) {
      if (!r) return;
      var p = r.over, side = p >= 0.5 ? first : second, prob = p >= 0.5 ? p : 1 - p, worth = nbaSimWorth(prob, kind, shrink);
      out.push({ key: key, view: view, label: label, line: line, side: side, p: prob, worth: worth, band: nbaSimBand(worth, bands), push: r.push });
    };
    add("total", "total", "Total", lines.total, nbaSimOver(H.total, lines.total), "OVER", "UNDER");
    add("h1", "h1", "First half", lines.h1, nbaSimOver(H.h1, lines.h1), "OVER", "UNDER");
    if (lines.sp !== null && lines.sp !== undefined && lines.sp !== "" && !isNaN(+lines.sp)) add("spread", "spread", "Spread", +lines.sp, nbaSimOver(H.margin, -(+lines.sp)), "HOME", "AWAY");
    if (view === "own") add("ml", "ml", "Moneyline", null, nbaSimOver(H.margin, 0), "HOME", "AWAY");
    if (lines.away_tt) add("away_total", nbaSimTeamKind(view, "away_total"), "Away team total", lines.away_tt.line, nbaSimOver(H.away, lines.away_tt.line), "OVER", "UNDER");
    if (lines.home_tt) add("home_total", nbaSimTeamKind(view, "home_total"), "Home team total", lines.home_tt.line, nbaSimOver(H.home, lines.home_tt.line), "OVER", "UNDER");
    return out;
  }
  /* the team totals (26 Oct 2026): the book's main line on each side from the row's odds JSON (the carded book first, the
     point whose two prices sit closest together; the shop also lists the alternates). The replay of 588 games of 2025-26
     found the book's team-total line sitting off the number the game's total and spread imply, and the anchored sim's call
     landing 60.7% at home and 53.9% away, so these two get their own rows and their own record. That replay's lines were
     not the book's (11 Nov 2026, the note above NBA_SIM_SHRINK_RULES): the rows and the record stay, the edge does not.
     This picker is the guard the season pull lacked: of the points a book lists, the one priced nearest even */
  function nbaTeamTotalLine(oddsRaw, side) {
    var o = null;
    try { o = oddsRaw ? JSON.parse(oddsRaw) : null; } catch (e) { o = null; }
    var t = o && o.team && o.team[side];
    if (!t) return null;
    var pick = function (bk) {
      var byPt = {};
      (t.OVER || []).forEach(function (x) { if (x[0] === bk && x[2] !== null && x[2] !== undefined) (byPt[x[2]] = byPt[x[2]] || {}).over = x[1]; });
      (t.UNDER || []).forEach(function (x) { if (x[0] === bk && x[2] !== null && x[2] !== undefined) (byPt[x[2]] = byPt[x[2]] || {}).under = x[1]; });
      var best = null;
      Object.keys(byPt).forEach(function (pt) {
        var e = byPt[pt];
        if (e.over === undefined || e.under === undefined) return;
        var gap = Math.abs((+e.over) - (+e.under));
        if (!best || gap < best.gap) best = { line: +pt, op: +e.over, up: +e.under, gap: gap, book: bk };
      });
      return best;
    };
    var books = [o.book].concat((t.OVER || []).map(function (x) { return x[0]; })).filter(function (b, i, a) { return b && a.indexOf(b) === i; });
    for (var i = 0; i < books.length; i++) { var b = pick(books[i]); if (b) return b; }
    return null;
  }
  /* a call on the record (11 Nov 2026, the user: "fix the NBA record so tiles count only real calls"). The NBA card reads the
     book's own number on the spread, the first half and most totals and moneylines, and its "pick" there is only the closer of
     two sides neither of which is priced below its chance (the note on the market says so). The record's tiles had counted
     every row: on the 160 games to 10 Nov the moneyline's line read 79-81 for -28.9 units, of which 130 rows were no call (35
     long dogs among them, 3-32 for -24.8) and 29 were calls (11-18, -6.7); the spread's 73-86-1 and the first half's 80-80
     were a coin less the price on a side nobody had called. A call is a side priced below the sheet's chance (an edge above
     zero) or one a verdict sits on; the rest is listed under the tile as no call and left out of its count. The watches that
     read both sides of a market (Pinnacle's shade, the short dog, the crowd on Kalshi, the 54%+ line) keep every game. No
     chance and no pick moves: this is the record's arithmetic alone */
  function nbaIsCall(mk) { return !!mk && ((mk.edge !== null && mk.edge !== undefined && mk.edge > 1e-9) || !!bandOf(mk)); }
  /* the gap rule (26 Oct 2026): the book's team total against the number the game's own total and spread imply, (total -/+
     spread) / 2. Two seasons of closes: a home line a point or more ABOVE the implied went under 62.1% and 63.2% of the time
     (169 and 247 games), a point or more BELOW went over 68.1% and 63.1% (94 and 195); the away side 55.4% / 56.8% and
     57.1% / 56.5%; the slope of the over's chance on the gap -0.080 and -0.057 a point at home (t -5.1, -5.7), -0.036 and
     -0.030 away (t -2.4, -2.8). Scored: a gap of a point or more is a call, and the record keeps it from the first night */
  /* A watch from 11 Nov 2026, shown and not scored. The re-test (slate.py nba-gap-retest, the user's file of 674 games of
     2025-26) held every team-total line against three numbers. As the backtest had it the call went 278-177 at home
     (61.1%, t -5.2 on the gap), and every one of those lines but two was BetRivers'. BetRivers against its OWN total and
     spread: 177-107 (62.3%), a gap of a point or more on 73% of lines, sd 1.95. DraftKings, ESPN BET and FanDuel against
     theirs: 114-96, 164-150 and 72-62 at home, 100-102, 178-164 and 65-65 away, a gap on 20 to 47% of lines, sd 0.8 to 0.9,
     no slope above t 1.3. One call a game at the apps (FanDuel, DraftKings, BetMGM): 136-117 at home (53.8%, +3.4 units)
     and 130-123 away (-7.7) against the book's own number, 104-93 (-1.2) and 103-97 (-5.9) against the other books'
     middle. So the edge was one book's line, and that line was not the book's: the season pull kept the first point
     BetRivers listed with another point's prices (the note above NBA_SIM_SHRINK_RULES has the replay of the fault on this
     season's rows, where the call on the kept point is worth +23.0 units at the kept prices and +0.9 at its own). On the
     books' own lines the gap is a coin less the price. The number, the gap and the side still show on the Simulation
     card, the signal is gold, the Take button stays, and the record keeps counting both sides: a book that hangs a line
     a point off its own numbers can still earn the rule back.
     2024-25 read the same day (554 games, the user's two files and ledger): BetRivers' line again, on 552 of them, 142-92
     at home as it was scored and 152-106 against its own numbers; at the apps the home call LOST, 76-93 (-25.7 units), and
     the away call went 92-87. Two seasons at the apps, one call a game: 212-210 at home (-22.3 units) and 222-210 away
     (-13.6) against the book's own number, 176-190 (-34.8) and 194-179 (-7.8) against the other books' middle. In that
     file BetRivers' stored point sits a point or more off DraftKings' and FanDuel's line on 65% of sides, and where it does
     the stored price belongs to a point on the other side of the main line four times in five. The 53.8% at home in
     2025-26 was one season's noise */
  var NBA_TT_GAP = 1.0;
  function nbaTeamTotalGap(tt, total, sp, side) {
    if (!tt || total === null || total === undefined || sp === null || sp === undefined || isNaN(+total) || isNaN(+sp)) return null;
    var implied = side === "HOME" ? (+total - +sp) / 2.0 : (+total + +sp) / 2.0, gap = tt.line - implied;
    return { implied: Math.round(implied * 10) / 10, gap: Math.round(gap * 10) / 10, call: gap >= NBA_TT_GAP ? "UNDER" : gap <= -NBA_TT_GAP ? "OVER" : null };
  }
  function nbaSimLinesFrom(inputs) {
    var oddsRaw = inputs.odds || "";
    var total = blank(inputs.line) ? null : +inputs.line, sp = blank(inputs.sp) ? null : +inputs.sp;
    var out = { total: total, h1: blank(inputs.h1line) ? null : +inputs.h1line, sp: sp, away_tt: nbaTeamTotalLine(oddsRaw, "AWAY"), home_tt: nbaTeamTotalLine(oddsRaw, "HOME") };
    if (out.away_tt) out.away_tt.rule = nbaTeamTotalGap(out.away_tt, total, sp, "AWAY");
    if (out.home_tt) out.home_tt.rule = nbaTeamTotalGap(out.home_tt, total, sp, "HOME");
    return out;
  }
  function nbaSimLinesFromForm() { return nbaSimLinesFrom({ line: $("line").value, h1line: $("h1line").value, sp: $("sp").value, odds: ($("odds") || {}).value || "" }); }
  function nbaSimChip(c) {
    if (!c) return '<span class="dim">—</span>';
    var cls = c.band === "no call" ? "simno" : c.band === "LEAN" ? "simlean" : c.band === "BET" ? "simbet" : "simstrong";
    return '<span class="simchip ' + cls + '"><b>' + esc(c.side) + '</b> ' + (100 * c.p).toFixed(0) + '%</span>' +
           (c.band !== "no call" ? ' <span class="tag">' + esc(c.band) + '</span>' : '') +
           ' <span class="dim">worth ' + (100 * c.worth).toFixed(0) + '%</span>';
  }
  function nbaSimPanel() {
    var el = $("nbaSimPanel"); if (!el) return;
    var sim = nbaSim();
    if (!sim) { el.innerHTML = "No simulation on the row — load the slate and Fill form, and the game's runs come with it."; return; }
    var f = readNba(), away = f.away || "Away", home = f.home || "Home";
    var lines = nbaSimLinesFromForm(), own = sim.own, mkt = sim.mkt;
    var calls = { own: {}, mkt: {} };
    nbaSimCalls(sim, lines, "own").forEach(function (c) { calls.own[c.key] = c; });
    if (mkt) nbaSimCalls(sim, lines, "mkt").forEach(function (c) { calls.mkt[c.key] = c; });
    /* the layout (26 Oct 2026, the user: "off centred and a tiny bit hard to read"): four tiles for the game, one line
       of context, a three-column table that fits the card (the market and its line in the first column, a chip with its
       band and worth under it in each view's column), the medians as a small table, the profiles last */
    var fmt1 = function (x) { return x === null || x === undefined ? "?" : (+x).toFixed(1); };
    var mA = nbaSimMean(own.away), mH = nbaSimMean(own.home), mg = nbaSimMean(own.margin);
    var tile = function (k, v, s, cls) { return '<div class="simtile' + (cls ? ' ' + cls : '') + '"><div class="k">' + k + '</div><div class="v">' + v + '</div>' + (s ? '<div class="s">' + s + '</div>' : '') + '</div>'; };
    var h = '<div class="simtiles">' +
            tile("Total", nbaSimQ(own.total, 0.5), 'middle half ' + nbaSimQ(own.total, 0.25) + '–' + nbaSimQ(own.total, 0.75)) +
            tile("Margin", esc(mg >= 0 ? home : away) + ' by ' + Math.abs(mg).toFixed(1), esc(away) + ' ' + fmt1(mA) + ' · ' + esc(home) + ' ' + fmt1(mH)) +
            tile(esc(home) + " wins", (100 * (nbaSimOver(own.margin, 0) || {}).over).toFixed(0) + '%', 'the one chance the replay found true') +
            tile("Overtime", (100 * (own.ot || 0)).toFixed(1) + '%', '') + '</div>';
    h += '<div class="simmeta"><b>' + String(sim.runs).replace(/\B(?=(\d{3})+(?!\d))/g, ",") + ' games</b>, the sim\'s own view. ' +
         (sim.anchor ? 'Anchored to ' + esc(sim.anchor.book) + '\'s ' + esc(String(sim.anchor.total)) + (sim.anchor.sp !== null && sim.anchor.sp !== undefined ? ' / ' + (sim.anchor.sp > 0 ? '+' : '') + esc(String(sim.anchor.sp)) : '') + ' for the market view.' : 'No book on the scoreboard at the run: no market view.') +
         (sim.level && sim.level.ortg ? ' The ratings ride the league\'s level of the last fortnight, ' + esc(String(sim.level.ortg)) + ' per 100 at ' + esc(String(sim.level.pace)) + ' possessions (30 Oct 2026).' : '') +
         (sim.v >= 2 ? ' Engine 2: score effects, the market\'s shape (30 Oct 2026).' : '') + '</div>';
    h += '<div id="nbaVoices"></div>';   // the three voices on the total (28 Oct 2026), filled once the sheet has scored this render
    var takeRow = nbaSimTakeRow(f);   // the card row this game is on, if any: a sim call is taken on the row (26 Oct 2026)
    var cell = function (c) {
      if (!c) return '<span class="dim">—</span>';
      var cls = c.band === "no call" ? "simno" : c.band === "LEAN" ? "simlean" : c.band === "BET" ? "simbet" : "simstrong";
      return '<span class="simchip ' + cls + '"><b>' + esc(c.side) + '</b> ' + (100 * c.p).toFixed(0) + '%</span>' +
             '<div class="simsub">' + (c.band !== "no call" ? esc(c.band) + ' · ' : '') + 'worth ' + (100 * c.worth).toFixed(0) + '%</div>' +
             '<div class="simtake">' + nbaSimTakeBtn(takeRow, c.view, c.key, c.side) + '</div>';
    };
    h += '<table class="form simtab"><thead><tr><th>Market</th><th>The sim\'s own view</th><th>Anchored to the market</th></tr></thead><tbody>';
    [["total", "Total", lines.total], ["h1", "First half", lines.h1], ["spread", "Spread (home)", lines.sp], ["ml", "Moneyline", null],
     ["away_total", esc(away) + " team total", lines.away_tt ? lines.away_tt.line : null], ["home_total", esc(home) + " team total", lines.home_tt ? lines.home_tt.line : null]].forEach(function (m) {
      var first = '<div class="mkname">' + m[1] + '</div>';
      if (m[2] === null || m[2] === undefined) {
        if (m[0] !== "ml") first += '<div class="mkline dim">no line on the row' + (/_total$/.test(m[0]) ? ' (the odds run brings it)' : '') + '</div>';
      } else {
        first += '<div class="mkline">' + esc(String(m[2]));
        if (/_total$/.test(m[0])) {
          var tt = m[0] === "away_total" ? lines.away_tt : lines.home_tt;
          first += ' <span class="dim">' + esc(tt.book) + ' ' + (tt.op > 0 ? '+' : '') + tt.op + '/' + (tt.up > 0 ? '+' : '') + tt.up + '</span></div>';
          if (tt.rule) {
            first += '<div class="ttgap">implied <b>' + tt.rule.implied + '</b>, gap <b>' + (tt.rule.gap > 0 ? '+' : '') + tt.rule.gap + '</b> · ' +
                     (tt.rule.call ? '<span class="simchip simwatch gaprule"><b>' + tt.rule.call + '</b> by the gap</span> <span class="dim">a watch, not scored</span> ' + nbaSimTakeBtn(takeRow, "gap", m[0], tt.rule.call) : '<span class="dim">inside a point</span>') + '</div>';
          }
          var kk = typeof kalshiOf === "function" ? kalshiOf(($("nbakalshi") || {}).value || "") : null, kl = kk ? kalshiTTLine(kk, m[0], +m[2], tt.op, tt.up) : "";   // the crowd on Kalshi beside the gap rule (4 Nov 2026)
          if (kl) first += '<div class="ttgap kal">' + kl + '</div>';
        } else {
          first += '</div>';
        }
      }
      h += '<tr><td>' + first + '</td><td>' + cell(calls.own[m[0]]) + '</td><td>' + (m[0] === "ml" ? '<span class="dim">the own view\'s</span>' : cell(calls.mkt[m[0]])) + '</td></tr>';
    });
    h += '</tbody></table>';
    var V = mkt || own, tag = mkt ? "anchored to the market" : "the own view";
    var tot = nbaSimQ(V.total, 0.5);
    h += '<table class="form simq"><thead><tr><th>Medians, ' + tag + '</th><th>Q1</th><th>Q2</th><th>Q3</th><th>Q4</th><th>1H</th><th>2H</th><th>' + esc(away) + '</th><th>' + esc(home) + '</th></tr></thead><tbody><tr><td class="dim">' +
         (tot ? 'the fourth ' + (100 * nbaSimQ(V.q[3], 0.5) / tot).toFixed(1) + '% of the game' : '') + '</td>' +
         (V.q || []).map(function (q) { return '<td>' + nbaSimQ(q, 0.5) + '</td>'; }).join('') +
         '<td>' + nbaSimQ(V.h1, 0.5) + '</td><td>' + nbaSimQ(V.h2, 0.5) + '</td><td>' + nbaSimQ(V.away, 0.5) + '</td><td>' + nbaSimQ(V.home, 0.5) + '</td></tr></tbody></table>';
    h += nbaWindowHtml(sim, takeRow);   // the window on the total as one ticket (29 Oct 2026)
    var pa = sim.prof && sim.prof.away, ph = sim.prof && sim.prof.home;
    if (pa && ph) {
      h += '<div class="simprof dim">Profiles: ' + esc(away) + ' ' + pa.ortg + ' / ' + pa.drtg + ' per 100, pace ' + pa.pace + (pa.b2b ? ', back to back' : '') + (pa.out ? ', out ' + pa.out + ' per 100' : '') +
           ' · ' + esc(home) + ' ' + ph.ortg + ' / ' + ph.drtg + ', pace ' + ph.pace + (ph.b2b ? ', back to back' : '') + (ph.out ? ', out ' + ph.out + ' per 100' : '') +
           (sim.ft_factor && Math.abs(sim.ft_factor - 1) >= 0.02 ? ' · the crew\'s whistle x' + sim.ft_factor : '') + '</div>';
    }
    el.innerHTML = h;
  }
  /* the window on the total (29 Oct 2026, the user: "select the middle half at 221-246 ... over 221 and under 246 as a
     same game parlay"): one ticket, over the low number and under the high, paid when the total lands between them. The
     sim's histogram gives the chance of landing inside any window directly, a push at an integer number set aside (that
     leg voids on most apps, so the half-point numbers are the ones to type). The ANCHORED view prices the ticket, since
     the replay found the own view's centre carries nothing the close does not; the own view's chance is shown beside it.
     The boxes default to the anchored view's middle half on half-point numbers; the price is the app's parlay quote,
     typed. The ticket is taken like a sim call, listed under Taking tonight, graded inside or out, and recorded on its
     own line. Nothing here moves a call or a band. */
  var winCalc = { lo: "", hi: "", price: "" };
  function nbaWindowChance(H, lo, hi) {
    if (!H || !isFinite(lo) || !isFinite(hi) || hi <= lo) return null;
    var n = 0, inside = 0, pLo = 0, pHi = 0;
    H.c.forEach(function (c, i) { n += c; var v = H.lo + i; if (v > lo && v < hi) inside += c; else if (v === lo) pLo += c; else if (v === hi) pHi += c; });
    if (!n) return null;
    return { inside: inside / n, pushLo: pLo / n, pushHi: pHi / n };
  }
  function nbaWindowDefault(sim) {
    var V = (sim && (sim.mkt || sim.own)) || null; if (!V || !V.total) return null;
    return { lo: nbaSimQ(V.total, 0.25) - 0.5, hi: nbaSimQ(V.total, 0.75) + 0.5 };
  }
  function nbaWindowRead(sim) {
    var d = nbaWindowDefault(sim), lo = parseFloat(winCalc.lo), hi = parseFloat(winCalc.hi), price = parseFloat(winCalc.price);
    if (!isFinite(lo) && d) lo = d.lo;
    if (!isFinite(hi) && d) hi = d.hi;
    if (!isFinite(lo) || !isFinite(hi) || hi <= lo) return null;
    var own = nbaWindowChance(sim.own.total, lo, hi), mkt = sim.mkt ? nbaWindowChance(sim.mkt.total, lo, hi) : null;
    if (!own && !mkt) return null;
    return { lo: lo, hi: hi, price: isFinite(price) ? price : null, own: own, mkt: mkt, use: mkt || own, view: mkt ? "mkt" : "own", side: "WINDOW " + lo + "-" + hi };
  }
  function nbaWindowOut(sim) {
    var w = nbaWindowRead(sim);
    if (!w) {
      var d = nbaWindowDefault(sim);
      return '<span class="dim">' + (d ? 'The under number has to sit above the over number.' : 'Type the over number and the under number.') + '</span>';
    }
    var pc = function (p) { return (100 * p).toFixed(1) + "%"; }, u = w.use;
    var h = '<b>Over ' + esc(String(w.lo)) + ' and under ' + esc(String(w.hi)) + '</b>, a ' + (+(w.hi - w.lo).toFixed(1)) + '-point window: lands inside <b>' + pc(u.inside) + '</b>' +
            (w.mkt ? ' anchored to the market' + (w.own ? ' (the sim\'s own view ' + pc(w.own.inside) + ')' : '') : ' by the sim\'s own view') + ' · fair ' + sgn(priceFor(u.inside), 0);
    if (u.pushLo + u.pushHi > 0.0005) h += ' · lands on a number ' + pc(u.pushLo + u.pushHi) + ' (that leg voids on most apps; the half-point numbers are the ones to type)';
    if (w.price !== null) {
      var need = implied(w.price), edge = u.inside - need;
      h += ' · at ' + sgn(w.price, 0) + ' the ticket needs ' + pc(need) + ': <b>' + (edge > 0 ? 'PAYS, ' + sgn(100 * edge, 1) + ' points over the price' : 'the app\'s price, ' + sgn(100 * edge, 1) + ' points') + '</b>';
    } else {
      h += ' · type the app\'s parlay price and the edge reads here';
    }
    return h;
  }
  function nbaWindowHtml(sim, takeRow) {
    var d = nbaWindowDefault(sim), w = nbaWindowRead(sim);
    return '<div class="midcalc simwin"><b>The window</b> <span class="dim">· one ticket, over the low number and under the high, a same-game parlay · the boxes start at the middle half' + (sim.mkt ? ' anchored to the market' : '') + '</span><div class="midcalcrow">' +
           '<input id="winLo" inputmode="decimal" placeholder="' + (d ? 'over ' + d.lo : 'over') + '" value="' + esc(winCalc.lo) + '"><input id="winHi" inputmode="decimal" placeholder="' + (d ? 'under ' + d.hi : 'under') + '" value="' + esc(winCalc.hi) + '">' +
           '<input id="winPrice" inputmode="numeric" placeholder="parlay price" value="' + esc(winCalc.price) + '"><div class="simtake">' + nbaSimTakeBtn(takeRow, "window", "total", w ? w.side : "WINDOW") + '</div></div>' +
           '<div id="winOut">' + nbaWindowOut(sim) + '</div></div>';
  }
  /* the simulation's calls you take (26 Oct 2026, the user: "lets say I decide to go with the Thunder team total under
     119.5 at 72%, I would like to be able to select from this field too for tracking purposes and to show on the take for
     the home screen"): a Take button under every chip on the Simulation card and beside the gap rule's call. The mark
     lives on the card row (row.simTakes), one per view, market and side, and keeps the call as shown when it was
     marked: the line, the book's price on that side, the sim's chance, its worth and its band, with the pick in words.
     The game has to be on the card first, since the row is where the mark and the finals live. Listed under Taking
     tonight with the rest, graded off the row's finals the way the sim record grades (the half from the half-time
     score), on its own tile in What you took. Nothing here changes a call or a band. */
  function nbaSimTakeRow(f) {
    var away = (f && f.away) || $("away").value, home = (f && f.home) || $("home").value, gdate = $("gdate").value;
    if (!away || !home) return null;
    return card.filter(function (r) { return r.sport === "NBA" && sameGame(r, { sport: "NBA", gdate: gdate, away: away, home: home }); })[0] || null;
  }
  function nbaSimTakeId(view, key, side) { return view + "|" + key + "|" + side; }
  function nbaSimTakeOf(row, view, key, side) {
    var id = nbaSimTakeId(view, key, side);
    return ((row && row.simTakes) || []).filter(function (t) { return t.id === id; })[0] || null;
  }
  function nbaSimTakeBtn(row, view, key, side) {
    if (!row) return '<button type="button" class="takebtn off" disabled title="Add the game to the card first (Add, or Fill form from the slate and Add); the mark lives on the card row">Take</button>';
    var t = nbaSimTakeOf(row, view, key, side);
    if (isVoid(row) || rowGraded(row)) return t ? '<span class="chip taken">TAKEN</span>' : '';
    return '<button type="button" class="takebtn' + (t ? ' on' : '') + '" data-stake="' + row.id + '|' + view + '|' + key + '|' + side + '" title="' +
           (t ? 'Marked as a bet you are placing: click to unmark it' : 'Mark this call as a bet you are placing') + '">' + (t ? '&#10003; Taking' : 'Take') + '</button>';
  }
  /* the book's price on the call's side, from the form's boxes (the total, the half, the spread and the moneyline) or the team total's own line */
  function nbaSimPriceOf(key, side, lines, inp) {
    var v = key === "total" ? (side === "OVER" ? inp.op : inp.up) : key === "h1" ? (side === "OVER" ? inp.h1op : inp.h1up) : key === "spread" ? (side === "HOME" ? inp.sph : inp.spa)
          : key === "ml" ? (side === "HOME" ? inp.hml : inp.aml) : (function () { var tt = key === "away_total" ? lines.away_tt : lines.home_tt; return tt ? (side === "OVER" ? tt.op : tt.up) : null; })();
    return v === null || v === undefined || v === "" || isNaN(+v) ? null : +v;
  }
  function nbaSimPickText(key, side, line, away, home) {
    if (key === "total") return "Total " + side + " " + line;
    if (key === "h1") return "First half " + side + " " + line;
    if (key === "spread") return (side === "HOME" ? home + " " + fmtLine(+line) : away + " " + fmtLine(-(+line)));
    if (key === "ml") return (side === "HOME" ? home : away) + " ML";
    return (key === "away_total" ? away : home) + " team total " + side + " " + line;
  }
  function toggleSimTake(spec) {
    var p = String(spec).split("|"), row = card.filter(function (r) { return String(r.id) === p[0]; })[0]; if (!row) return;
    var view = p[1], key = p[2], side = p[3], id = nbaSimTakeId(view, key, side);
    if (rowGraded(row) || isVoid(row)) { say("<b>" + esc(row.matchup) + "</b> is graded: a bet is marked before the game, not after."); return; }
    var done = function () { save(); render(); renderCard(); renderBoard(); renderCalib(); };
    if (nbaSimTakeOf(row, view, key, side)) {   // marked already: unmark it
      row.simTakes = row.simTakes.filter(function (t) { return t.id !== id; });
      done(); return;
    }
    // mark it as the card shows it now: the call from the form's own runs and lines
    var sim = nbaSim(), lines = nbaSimLinesFromForm(), f = readNba();
    var tt = key === "away_total" ? lines.away_tt : key === "home_total" ? lines.home_tt : null, c = null;
    if (view === "gap") { if (tt && tt.rule && tt.rule.call === side) c = { line: tt.line, p: null, worth: null, band: "gap watch" }; }
    else if (view === "agree") {   // the agreement rule (28 Oct 2026): read off the ROW, so the board's card takes it whatever game the form holds
      var V = nbaVoices(row);
      if (V && V.fires && V.side === side && key === "total") c = { line: V.line, p: side === "OVER" ? V.sim.p : 1 - V.sim.p, worth: null, band: "agreement" };
    }
    else if (view === "middle") {   // the middle's second leg (28 Oct 2026): the number, the price and the app from the watch, paired with the leg held
      var W = nbaMiddleWatch(row).filter(function (x) { return x.side === side && String(x.other.point) === p[4] && x.other.book === p[6] && String(x.leg.id) === p[7]; })[0];
      if (W && W.m.pays) c = { line: W.other.point, p: W.second, worth: null, band: "middle", price: W.other.price, book: W.other.book, with: { side: W.leg.side, line: W.leg.line, price: W.leg.price, how: W.leg.how }, pair: { pBoth: +W.m.pBoth.toFixed(4), ev: +W.m.ev.toFixed(4), gap: W.m.gap, mu: W.mu } };
    }
    else if (view === "window") {   // the window on the total as one ticket (29 Oct 2026): the boxes as they stand, the anchored chance
      var Wn = sim ? nbaWindowRead(sim) : null;
      if (Wn && Wn.side === side) c = { line: Wn.lo + "-" + Wn.hi, p: Wn.use.inside, worth: Wn.use.inside, band: "window", price: Wn.price, lo: Wn.lo, hi: Wn.hi, winView: Wn.view };
    }
    else if (sim) c = nbaSimCalls(sim, lines, view).filter(function (x) { return x.key === key && x.side === side; })[0] || null;
    if (!c) { say("That call is not on the card as shown now; put the line back and take it again."); return; }
    var inp = view === "agree" ? { op: (row.inputs || {}).op, up: (row.inputs || {}).up }
            : { op: $("op").value, up: $("up").value, h1op: $("h1op").value, h1up: $("h1up").value, sph: $("sph").value, spa: $("spa").value, hml: $("hml").value, aml: $("aml").value };
    var take = { id: id, view: view, key: key, side: side, line: c.line, price: (view === "middle" || view === "window") ? c.price : nbaSimPriceOf(key, side, lines, inp),
                 p: c.p === null ? null : +(+c.p).toFixed(4), worth: c.worth === null ? null : +(+c.worth).toFixed(4), band: c.band,
                 pick: view === "middle" ? "Total " + side + " " + c.line + " at " + bookName(c.book) + " (the middle with " + c.with.side + " " + c.with.line + ")"
                     : view === "window" ? "Total window " + c.lo + "-" + c.hi + " (over the low, under the high), one ticket"
                     : nbaSimPickText(key, side, c.line, f.away || row.away, f.home || row.home), at: new Date().toISOString() };
    if (view === "middle") { take.book = c.book; take.with = c.with; take.pair = c.pair; }
    if (view === "window") { take.lo = c.lo; take.hi = c.hi; take.winView = c.winView; }
    row.simTakes = (row.simTakes || []).concat([take]);
    done();
  }
  /* a taken call's result off the row's finals, the sim record's reading: the half from the half-time score */
  function nbaSimTakeRes(t, row) {
    var fin = (row && row.finals) || {};
    if (fin.void) return null;
    var fa = parseFloat(fin.fa), fh = parseFloat(fin.fh);
    if (!isFinite(fa) || !isFinite(fh)) return null;
    var cmp = function (v, line, over) { if (v === line) return "push"; return ((v > line) === over) ? "win" : "loss"; };
    if (t.view === "window") { var tw = fa + fh; if (tw === +t.lo || tw === +t.hi) return "push"; return (tw > +t.lo && tw < +t.hi) ? "win" : "loss"; }   // inside the window wins the ticket (29 Oct 2026)
    if (t.key === "total") return cmp(fa + fh, +t.line, t.side === "OVER");
    if (t.key === "h1") { var f5a = parseFloat(fin.f5a), f5h = parseFloat(fin.f5h); if (!isFinite(f5a) || !isFinite(f5h)) return null; return cmp(f5a + f5h, +t.line, t.side === "OVER"); }
    if (t.key === "spread") { var m = fh - fa + +t.line; if (m === 0) return "push"; return ((m > 0) === (t.side === "HOME")) ? "win" : "loss"; }
    if (t.key === "ml") { if (fa === fh) return "push"; return ((fh > fa) === (t.side === "HOME")) ? "win" : "loss"; }
    if (t.key === "away_total") return cmp(fa, +t.line, t.side === "OVER");
    if (t.key === "home_total") return cmp(fh, +t.line, t.side === "OVER");
    return null;
  }
  function nbaSimTakeViewLabel(view) { return view === "own" ? "the sim's own view" : view === "mkt" ? "anchored to the market" : view === "agree" ? "the agreement rule, the sim and the crew" : view === "middle" ? "the middle's second leg" : view === "window" ? "the window, one ticket (anchored to the market)" : "the gap, a watch"; }
  /* the record: every graded NBA row's sim calls at LEAN or better, says against does by view, market and band */
  function nbaSimUnits(price, win) { var p = +price; if (!p || isNaN(p)) p = -110; return win ? (p > 0 ? p / 100 : 100 / -p) : -1; }
  function nbaSimRecordHtml() {
    var rows = card.filter(function (r) { return r.sport === "NBA" && rowGraded(r) && r.inputs && (r.inputs.nbasim || (r.simTakes || []).some(function (t) { return t.view === "middle" || t.view === "window"; })); });
    if (!rows.length) return '';
    var T = {}, n = 0, G = { HOME: { n: 0, w: 0, units: 0 }, AWAY: { n: 0, w: 0, units: 0 } }, gn = 0;
    var A = { 2: { n: 0, w: 0, units: 0 }, 3: { n: 0, w: 0, units: 0 } }, an = 0;   // the agreement rule's own tally (28 Oct 2026)
    var B = { n: 0, w: 0, says: 0, units: 0 };   // the withdrawn boost (11 Nov 2026): what the anchored home team total would have called at 1.5 and no longer does
    var M = { n: 0, both: 0, half: 0, split: 0, units: 0, first: 0, says: 0 };   // the middles (28 Oct 2026): the pair graded together, and the first leg alone
    var Wd = { n: 0, w: 0, p: 0, says: 0, units: 0 };   // the windows (29 Oct 2026): one ticket, inside or out
    rows.forEach(function (r) {
      var fin = r.finals || {}, fa = +fin.fa, fh = +fin.fh, half = (fin.f5a !== undefined && fin.f5a !== "" && fin.f5h !== undefined && fin.f5h !== "") ? (+fin.f5a + +fin.f5h) : null;
      (r.simTakes || []).forEach(function (t) {
        if (t.view === "window") {
          var rw = nbaSimTakeRes(t, r); if (!rw) return;
          if (rw === "push") { Wd.p++; return; }
          Wd.n++; Wd.w += rw === "win" ? 1 : 0; Wd.says += t.p || 0.5; Wd.units += rw === "win" ? nbaWinAmount(t.price) : -1;
          return;
        }
        if (t.view !== "middle" || !t.with) return;
        var r2 = nbaSimTakeRes(t, r), r1 = nbaSimTakeRes({ key: "total", side: t.with.side, line: t.with.line }, r);
        if (!r2 || !r1) return;
        var u2 = r2 === "push" ? 0 : r2 === "win" ? nbaWinAmount(t.price) : -1, u1 = r1 === "push" ? 0 : r1 === "win" ? nbaWinAmount(t.with.price) : -1;
        M.n++; M.units += u1 + u2; M.first += u1; M.says += t.pair ? +t.pair.pBoth : 0;
        if (r1 === "win" && r2 === "win") M.both++; else if (r1 === "push" || r2 === "push") M.half++; else M.split++;
      });
      var sim = null; try { sim = JSON.parse(r.inputs.nbasim); } catch (e) { sim = null; }
      if (!sim || !sim.own) return;
      var lines = nbaSimLinesFrom(r.inputs);
      var V = nbaVoices(r);
      if (V && V.fires && V.line !== null && fa + fh !== V.line) {
        var wonA = (fa + fh > V.line) === (V.side === "OVER"), dA = A[V.count === 3 ? 3 : 2];
        dA.n++; dA.w += wonA ? 1 : 0; dA.units += nbaSimUnits(V.side === "OVER" ? r.inputs.op : r.inputs.up, wonA); an++;
      }
      // the gap's own tally: a watch from 11 Nov 2026, counted as it always was
      [["AWAY", lines.away_tt, fa], ["HOME", lines.home_tt, fh]].forEach(function (x) {
        var tt = x[1];
        if (!tt || !tt.rule || !tt.rule.call || x[2] === tt.line) return;
        var won = (x[2] > tt.line) === (tt.rule.call === "OVER"), d = G[x[0]];
        d.n++; d.w += won ? 1 : 0; d.units += nbaSimUnits(tt.rule.call === "OVER" ? tt.op : tt.up, won); gn++;
      });
      ["own", "mkt"].forEach(function (view) {
        nbaSimCalls(sim, lines, view).forEach(function (c) {
          if (view === "mkt" && c.key === "home_total" && c.band === "no call" && lines.home_tt && fh !== c.line &&
              nbaSimBand(Math.max(0, Math.min(1, 0.5 + (c.p - 0.5) * NBA_SIM_TEAM_WAS)), sim.bands) !== "no call") {
            var wonB = (fh > c.line) === (c.side === "OVER");
            B.n++; B.w += wonB ? 1 : 0; B.says += c.p; B.units += nbaSimUnits(c.side === "OVER" ? lines.home_tt.op : lines.home_tt.up, wonB);
          }
          if (c.band === "no call") return;
          var won = null, price = -110;
          if (c.key === "total") { if (fa + fh === c.line) return; won = (fa + fh > c.line) === (c.side === "OVER"); price = c.side === "OVER" ? r.inputs.op : r.inputs.up; }
          else if (c.key === "h1") { if (half === null || half === c.line) return; won = (half > c.line) === (c.side === "OVER"); price = c.side === "OVER" ? r.inputs.h1op : r.inputs.h1up; }
          else if (c.key === "spread") { var m = fh - fa + c.line; if (m === 0) return; won = (m > 0) === (c.side === "HOME"); price = c.side === "HOME" ? r.inputs.sph : r.inputs.spa; }
          else if (c.key === "ml") { if (fa === fh) return; won = (fh > fa) === (c.side === "HOME"); price = c.side === "HOME" ? r.inputs.hml : r.inputs.aml; }
          else if (c.key === "away_total" || c.key === "home_total") {
            var pts = c.key === "away_total" ? fa : fh, tt = c.key === "away_total" ? lines.away_tt : lines.home_tt;
            if (pts === c.line) return;
            won = (pts > c.line) === (c.side === "OVER"); price = c.side === "OVER" ? tt.op : tt.up;
          }
          if (won === null) return;
          var k = view + "|" + c.key + "|" + c.band;
          var d = T[k] || (T[k] = { view: view, key: c.key, band: c.band, n: 0, w: 0, says: 0, units: 0 });
          d.n++; d.w += won ? 1 : 0; d.says += c.p; d.units += nbaSimUnits(price, won); n++;
        });
      });
    });
    if (!n && !gn && !an && !B.n && !M.n && !Wd.n && !Wd.p) return '';
    var order = { total: 0, h1: 1, spread: 2, ml: 3, away_total: 4, home_total: 5 }, bandOrder = { STRONG: 0, BET: 1, LEAN: 2 },
        label = { total: "Total", h1: "First half", spread: "Spread", ml: "Moneyline", away_total: "Away team total", home_total: "Home team total" };
    var h = '<div class="simrec"><div class="calibhead">SIMULATION · says against does, every call at LEAN or better</div>';
    ["own", "mkt"].forEach(function (view) {
      var ks = Object.keys(T).filter(function (k) { return T[k].view === view; }).sort(function (a, b) { return (order[T[a].key] - order[T[b].key]) || (bandOrder[T[a].band] - bandOrder[T[b].band]); });
      if (!ks.length) return;
      h += '<div class="simrecview">' + (view === "own" ? "The sim's own view" : "Anchored to the market") + '</div><table class="form simrectab"><thead><tr><th>Market</th><th>Band</th><th>Record</th><th>Says</th><th>Does</th><th>Units</th></tr></thead><tbody>';
      ks.forEach(function (k) {
        var d = T[k], does = d.w / d.n, says = d.says / d.n, cls = d.units > 0 ? "good" : d.units < 0 ? "bad" : "";
        h += '<tr><td>' + label[d.key] + '</td><td>' + esc(d.band) + '</td><td>' + d.w + '-' + (d.n - d.w) + '</td><td>' + (100 * says).toFixed(1) + '%</td><td class="' + cls + '">' + (100 * does).toFixed(1) + '%</td><td class="' + cls + '">' + (d.units >= 0 ? '+' : '') + d.units.toFixed(1) + 'u</td></tr>';
      });
      h += '</tbody></table>';
    });
    if (gn) {
      h += '<div class="simrecview">The team-total gap, a watch <span class="tag">the book\'s line a point or more off the number the game\'s total and spread imply · shown, not scored, from 11 Nov 2026 · the two seasons behind the rule read one book\'s line, and the season pull had kept that book\'s alternate points with another point\'s prices: 61% on those, a coin less the price on the books\' own lines</span></div><table class="form simrectab gaptab"><thead><tr><th>Side</th><th>Record</th><th>Does</th><th>Units</th><th>The re-test said, two seasons</th></tr></thead><tbody>';
      [["HOME", "212-210 (50.2%), −22.3u at the apps against the book\'s own number; 176-190, −34.8u against the other books\'"], ["AWAY", "222-210 (51.4%), −13.6u; 194-179, −7.8u"]].forEach(function (x) {
        var d = G[x[0]];
        if (!d.n) return;
        var cls = d.units > 0 ? "good" : d.units < 0 ? "bad" : "";
        h += '<tr><td>' + (x[0] === "HOME" ? "Home team total" : "Away team total") + '</td><td>' + d.w + '-' + (d.n - d.w) + '</td><td class="' + cls + '">' + (100 * d.w / d.n).toFixed(1) + '%</td><td class="' + cls + '">' + (d.units >= 0 ? '+' : '') + d.units.toFixed(1) + 'u</td><td class="dim">' + x[1] + '</td></tr>';
      });
      h += '</tbody></table>';
    }
    if (B.n) {
      var bcls = B.units > 0 ? "good" : B.units < 0 ? "bad" : "";
      h += '<div class="simrecview">The anchored home team total at its old weight, a watch <span class="tag">the sim\'s chance times 1.5, the weight the same replay gave it · withdrawn 11 Nov 2026 with the gap rule: it reads at 0.3 now, like the away side, and calls nothing here until a replay on the books\' own lines says otherwise</span></div><table class="form simrectab boosttab"><thead><tr><th>Calls it would have made</th><th>Record</th><th>Says</th><th>Does</th><th>Units</th></tr></thead><tbody>' +
           '<tr><td>' + B.n + '</td><td>' + B.w + '-' + (B.n - B.w) + '</td><td>' + (100 * B.says / B.n).toFixed(1) + '%</td><td class="' + bcls + '">' + (100 * B.w / B.n).toFixed(1) + '%</td><td class="' + bcls + '">' + (B.units >= 0 ? '+' : '') + B.units.toFixed(1) + 'u</td></tr></tbody></table>';
    }
    if (an) {
      h += '<div class="simrecview">The agreement rule on the total <span class="tag">' + esc(NBA_AGREE_TAG) + ' · scored, BET</span></div><table class="form simrectab agreetab"><thead><tr><th>Voices</th><th>Record</th><th>Does</th><th>Units</th><th>Two seasons said</th></tr></thead><tbody>';
      [[2, "2 of 3: the sim and the crew, the sheet silent", "134-98 (57.8%), +23.8u"], [3, "3 of 3: the sheet on it too", "23-10 (69.7%), +10.9u"]].forEach(function (x) {
        var d = A[x[0]];
        if (!d.n) return;
        var cls = d.units > 0 ? "good" : d.units < 0 ? "bad" : "";
        h += '<tr><td>' + x[1] + '</td><td>' + d.w + '-' + (d.n - d.w) + '</td><td class="' + cls + '">' + (100 * d.w / d.n).toFixed(1) + '%</td><td class="' + cls + '">' + (d.units >= 0 ? '+' : '') + d.units.toFixed(1) + 'u</td><td class="dim">' + x[2] + '</td></tr>';
      });
      h += '</tbody></table>';
    }
    if (M.n) {
      var cls = M.units > 0 ? "good" : M.units < 0 ? "bad" : "";
      h += '<div class="simrecview">Middles on the total <span class="tag">the second leg taken from the watch, the pair graded together · ' + esc(NBA_MIDDLE_TAG) + '</span></div><table class="form simrectab midrectab"><thead><tr><th>Pairs</th><th>Both won</th><th>One pushed</th><th>Split</th><th>Said both</th><th>The pair</th><th>The first leg alone</th></tr></thead><tbody>' +
           '<tr><td>' + M.n + '</td><td>' + M.both + ' (' + (100 * M.both / M.n).toFixed(1) + '%)</td><td>' + M.half + '</td><td>' + M.split + '</td><td>' + (100 * M.says / M.n).toFixed(1) + '%</td><td class="' + cls + '">' + (M.units >= 0 ? '+' : '') + M.units.toFixed(2) + 'u</td><td>' + (M.first >= 0 ? '+' : '') + M.first.toFixed(2) + 'u</td></tr></tbody></table>';
    }
    if (Wd.n || Wd.p) {
      var wcls = Wd.units > 0 ? "good" : Wd.units < 0 ? "bad" : "";
      h += '<div class="simrecview">Windows on the total <span class="tag">one ticket, over the low number and under the high; the chance is the anchored sim\'s mass inside the window</span></div><table class="form simrectab"><thead><tr><th>Tickets</th><th>Record</th><th>Says</th><th>Does</th><th>Units</th></tr></thead><tbody>' +
           '<tr><td>' + (Wd.n + Wd.p) + (Wd.p ? ' (' + Wd.p + ' on a number)' : '') + '</td><td>' + Wd.w + '-' + (Wd.n - Wd.w) + '</td><td>' + (Wd.n ? (100 * Wd.says / Wd.n).toFixed(1) + '%' : '—') + '</td><td class="' + wcls + '">' + (Wd.n ? (100 * Wd.w / Wd.n).toFixed(1) + '%' : '—') + '</td><td class="' + wcls + '">' + (Wd.units >= 0 ? '+' : '') + Wd.units.toFixed(2) + 'u</td></tr></tbody></table>';
    }
    h += '<div class="note dim">A call is the sim\'s side on the line the row carried whose WORTH (the chance shrunk by what the replay found) reads LEAN (60%) or better; "says" is the sim\'s own chance, "does" the share that landed. The replays: the own view\'s total and spread calls land at 50% whatever they say (the close already carries the ratings), its win chances within 3 points of true; the first half is a coin from either view over two seasons. The team totals were scored until 11 Nov 2026 on a replay whose lines were not the book\'s: the season pull had kept, for the one book it read, an alternate point with another point\'s prices. On the books\' own lines the gap between a team total and the number the game\'s total and spread imply reads a coin less the price, so the gap and the anchored home team total are watches now, counted above and scored nowhere.</div></div>';
    return h;
  }

  var NBA_REF_Z = 1.5;
  function nbaRefZ(rec) { var w = +rec[3] || 0, l = +rec[4] || 0; return (w + l) ? (w - l) / Math.sqrt(w + l) : 0; }
  function nbaRefLean(z) { return z >= NBA_REF_Z ? "over" : z <= -NBA_REF_Z ? "under" : "even"; }
  function nbaRefLookup(table, n) {
    if (table[n]) return table[n];
    var keys = Object.keys(table), low = n.toLowerCase(), hit = keys.filter(function (k) { return k.toLowerCase() === low; });
    if (!hit.length) { var last = low.split(" ").pop(); hit = keys.filter(function (k) { return k.toLowerCase().split(" ").pop() === last; }); }
    return hit.length === 1 ? table[hit[0]] : null;
  }
  function nbaCrewNames(s) { return String(s || "").split(/[,;]+/).map(function (x) { return x.trim(); }).filter(function (x) { return x; }); }
  /* the crew read against the frozen table: each official's past record, its z and lean, this season's record, and the crew's own lean (the sum of the z's) */
  function nbaCrewDetails(names, refs) {
    if (!names.length) return null;
    var table = refs && refs.r ? refs.r : {}, z = 0, found = 0, pastW = 0, pastL = 0, officials = [];
    names.forEach(function (n) {
      var d = nbaRefLookup(table, n);
      var o = { name: n, d: d && d.length >= 5 ? d : null, z: 0, lean: "even", pastW: 0, pastL: 0, thisW: 0, thisL: 0 };
      if (o.d) {
        o.z = nbaRefZ(o.d); o.lean = nbaRefLean(o.z); o.pastW = +o.d[3] || 0; o.pastL = +o.d[4] || 0; o.thisW = +o.d[5] || 0; o.thisL = +o.d[6] || 0;
        found++; z += o.z; pastW += o.pastW; pastL += o.pastL;
      }
      officials.push(o);
    });
    return { officials: officials, z: z, lean: found ? nbaRefLean(z) : "even", pastW: pastW, pastL: pastL, found: found };
  }
  function nbaCrewLean(row) {
    var names = nbaCrewNames((row.inputs || {}).ncrew);
    if (!names.length) return null;
    var refs = null;
    try { refs = row.inputs.nbarefs ? JSON.parse(row.inputs.nbarefs) : null; } catch (e) { refs = null; }
    var det = nbaCrewDetails(names, refs);
    return det && det.found ? det : null;
  }
  /* ---- the three voices on the total (28 Oct 2026, the user: "if the simulation, the refs and the super model are all
     thinking over or under for the total, that should get a green BET signal; two out of three should be enough. Look at
     the Lakers and Spurs games: the simulation and the refs were pointing to the over"). Alone, each had measured nothing
     against two seasons of closes; asked together (tools_nba_total_agree.py, 2,449 games with a close), the sim's own
     view at 55%+ and the crew's lean on the same side, the sheet not against it, landed 157-108 (59.2%, +34.7 units at
     -110): 134-98 with the sheet silent, 23-10 with the sheet on it too, and 15-20 when the sheet was BET the other way,
     which is why a sheet against it blocks the rule. The sheet's own BET band lands 56.3% on the same games, so the rule
     reads BET, green: on the Simulation card, on the board's Agreement section, takeable, with its own record line ---- */
  var NBA_AGREE = { sim: 0.55, model: 0.53, rate: 0.592, alt: 1.5 };   // the rule's measured rate gates the price; a row line 1.5+ off the market's number is an alternate, outside the measurement
  var NBA_AGREE_TAG = "the sim's own view at 55%+ and the crew's lean on the same side, the sheet not against it: 157-108 (59.2%) over two seasons of closes, +34.7u at -110; 23-10 with the sheet on it too, 15-20 when the sheet was against it. On watch (30 Oct 2026): an official's over/under lean did not carry from 2024-25 to 2025-26 (r -0.09 over 60 officials), so the crew's voice may be noise and the replay's 59% a lucky cut; the live record decides";
  /* the market's main number from the row's odds block: the carded book's total, else the commonest point across the books */
  function nbaMainTotal(inp) {
    var o = null; try { o = inp && inp.odds ? JSON.parse(inp.odds) : null; } catch (e) { o = null; }
    var t = o && o.total && o.total.OVER; if (!t || !t.length) return null;
    var pick = t.filter(function (x) { return x[0] === o.book && x[2] !== null && x[2] !== undefined && isFinite(+x[2]); })[0];
    if (pick) return +pick[2];
    var cnt = {}, best = null;
    t.forEach(function (x) { if (x[2] !== null && x[2] !== undefined && isFinite(+x[2])) cnt[x[2]] = (cnt[x[2]] || 0) + 1; });
    Object.keys(cnt).forEach(function (k) { if (best === null || cnt[k] > cnt[best]) best = k; });
    return best === null ? null : +best;
  }
  function nbaVoices(row) {
    if (!row || (row.sport && row.sport !== "NBA")) return null;
    var inp = row.inputs || {}, line = parseFloat(inp.line);
    var mk = (row.markets || []).filter(function (m) { return m.key === "total"; })[0] || null;
    var model = null;
    if (mk && isFinite(+mk.p)) {
      /* the sheet's voice is its LIKELIER side, not the pick by edge: a row at an alternate 225.5 (-208) carried "UNDER 36.6%" as
         the pick with the over at 63.4% behind it (the user's Spurs row, 27 Oct 2026) */
      var ms = mk.side, mp = +mk.p;
      if (mk.other && isFinite(+mk.other.p) && +mk.other.p > mp) { ms = /^UNDER/i.test(String(mk.other.pick || "")) ? "UNDER" : "OVER"; mp = +mk.other.p; }
      model = { side: ms, p: mp, band: mk.band1 || mk.band || "", votes: mp >= NBA_AGREE.model ? ms : null };
    }
    var sim = null; try { sim = inp.nbasim ? JSON.parse(inp.nbasim) : null; } catch (e) { sim = null; }
    var r = sim && sim.own && sim.own.total && isFinite(line) ? nbaSimOver(sim.own.total, line) : null;
    var simV = r ? { p: r.over, side: r.over >= 0.5 ? "OVER" : "UNDER", votes: null } : null;
    if (simV) simV.votes = Math.max(simV.p, 1 - simV.p) >= NBA_AGREE.sim ? simV.side : null;
    var cl = nbaCrewLean({ inputs: inp }), crew = cl ? { z: cl.z, lean: cl.lean, votes: cl.lean === "even" ? null : cl.lean.toUpperCase() } : null;
    if (!simV && !crew) return null;
    var v = [model && model.votes, simV && simV.votes, crew && crew.votes].filter(function (x) { return x; });
    var side = null, count = 0, against = false;
    ["OVER", "UNDER"].forEach(function (s) { var c = v.filter(function (x) { return x === s; }).length; if (c >= 2) { side = s; count = c; against = v.length > c; } });
    var agree = !!side && !against && !!simV && !!crew && simV.votes === side && crew.votes === side;
    /* the two gates (28 Oct 2026, the user's Spurs row): the rule was measured on the market's main number at -110, so an
       alternate line is outside it, and a price that asks more than the rule's 59.2% is the book's price, not a bet */
    var main = nbaMainTotal(inp), alt = main !== null && isFinite(line) && Math.abs(line - main) >= NBA_AGREE.alt;
    var price = agree ? parseFloat(side === "OVER" ? inp.op : inp.up) : NaN, need = isFinite(price) ? implied(price) : implied(-110);
    var priceOk = need <= NBA_AGREE.rate;
    return { model: model, sim: simV, crew: crew, line: isFinite(line) ? line : null, side: side, count: count, against: against, agree: agree,
             main: main, alt: alt, price: isFinite(price) ? price : null, need: need, priceOk: priceOk, fires: agree && !alt && priceOk };
  }
  function nbaVoicesWords(V) {
    var pc = function (p) { return (100 * p).toFixed(0) + "%"; }, bits = [];
    bits.push(V.model ? (V.model.votes ? "the sheet " + esc(V.model.side) + " " + pc(V.model.p) + " (" + esc(V.model.band || "BET") + ")" : "the sheet silent (" + esc(V.model.side) + " " + pc(V.model.p) + ", no bet)") : "the sheet not scored here");
    bits.push(V.sim ? "the sim " + esc(V.sim.side) + " " + pc(Math.max(V.sim.p, 1 - V.sim.p)) + (V.sim.votes ? "" : " (short of 55%)") : "no simulation on the row");
    bits.push(V.crew ? (V.crew.votes ? "the crew leans " + esc(V.crew.votes) + " (z " + sgn(V.crew.z, 1) + ")" : "the crew even (z " + sgn(V.crew.z, 1) + ")") : "no crew on the row");
    var verdict = V.fires ? (V.count + " of 3 on the " + V.side + ", none against: BET by the agreement rule")
      : V.agree && V.alt ? (V.count + " of 3 on the " + V.side + ", but the row's line " + V.line + " is an alternate (the market's number is " + V.main + "): the rule was measured on the main line, no bet")
      : V.agree && !V.priceOk ? (V.count + " of 3 on the " + V.side + ", but at " + sgn(V.price, 0) + " it needs " + (100 * V.need).toFixed(1) + "%, more than the rule's " + (100 * NBA_AGREE.rate).toFixed(1) + "%: the book's price, not a bet")
      : V.side && V.against ? ("split, " + V.count + " on the " + V.side + " with one against: no rule")
      : V.side ? (V.count + " of 3 on the " + V.side + ", but the rule needs the sim and the crew; the sheet's own call stands")
      : "no two voices on a side: no rule";
    return { bits: bits, verdict: verdict };
  }
  function nbaVoicesHtml(V, row) {
    if (!V) return '<div class="voices none"><span class="vbadge">three voices</span> No simulation or crew on the row yet: the agreement read needs both.</div>';
    var w = nbaVoicesWords(V);
    var badge = V.fires ? '<span class="vbadge bet">BET · ' + V.count + ' of 3</span>' : '<span class="vbadge">' + (V.agree ? V.count + ' of 3 · no bet' : V.side && !V.against ? V.count + ' of 3' : 'no rule') + '</span>';
    return '<div class="voices' + (V.fires ? ' fires' : '') + '"><div class="vhead">' + badge + ' <b>The three voices on the total' + (V.line !== null ? ' ' + esc(String(V.line)) : '') + '</b></div>' +
           '<div class="vline">' + w.bits.join(' · ') + ' — ' + esc(w.verdict) + '.</div>' +
           (V.fires ? '<div class="vtake">' + nbaSimTakeBtn(row, "agree", "total", V.side) + ' <span class="dim">Total ' + esc(V.side) + ' ' + esc(String(V.line)) + ' by the agreement rule</span></div>' : '') +
           '<div class="vtag dim">Measured: ' + esc(NBA_AGREE_TAG) + '.</div></div>';
  }
  /* filled at the end of the form's forecast, so the sheet's voice is this render's and not the last one's */
  function nbaVoicesFill(m) {
    var el = $("nbaVoices"); if (!el) return;
    var row = nbaSimTakeRow(readNba());
    el.innerHTML = nbaVoicesHtml(nbaVoices({ sport: "NBA", inputs: snapshot(), markets: (m && m.markets) || [] }), row);
  }
  /* ---- middles on the total (28 Oct 2026, the user: "I use four apps, FanDuel, BetMGM, DraftKings and Fanatics; how could
     we use the model to capitalize on middle betting?"). The over at one number and the under at a higher one: the final
     between them wins both legs, outside them one leg loses and the other wins. Measured on two seasons of lines history
     (tools_nba_middles.py, NBA.md): the apps sit within a point of each other at tip in 99% of games and a one-point gap
     loses 3% of the stake; the money is the MOVE, a number that has run 3.5+ points from a leg you already hold (8-9% both
     win, +3% of the stake; 5+ points 17-20%, +12-14%). The sheet's normal at 18 points sizes the chance within a point of
     what landed, so the page prices any pair from it: the chance of landing between, the pushes on an integer line, the
     two prices. A pair pays when that expectation is positive and the gap is three points or more (under three the pairs
     the normal liked lost in both seasons). The value is made by the first leg, a bet you wanted anyway, once the number
     has moved away from it; the second leg gives up the vig and takes the loss off the table. The watch names it ---- */
  var NBA_MIDDLE = { sd: NBA.TOTAL_SD, minGap: 3.0, apps: ["fanduel", "betmgm", "draftkings", "fanatics"], maxPrice: 400 };
  var NBA_MIDDLE_TAG = "two seasons of lines history: the apps sit within a point of each other at tip in 99% of games and a one-point gap loses 3% of the stake; a number that has moved 3.5+ points from a leg you hold pays (8-9% both win, +3% of the stake; 5+ points 17-20%, +12-14%), the sheet's normal sizing the chance within a point of what landed; the pairs the rule takes ran +3.4% and +2.9% of the stake";
  function nbaWinAmount(price) { var p = isFinite(+price) ? +price : -110; return p < 0 ? 100 / -p : p / 100; }
  function nbaNormCdf(x) { return 0.5 * (1 + erf(x / Math.SQRT2)); }
  /* a pair priced from the sheet's normal on integer totals: both win between the numbers, a push on an integer line, one wins and one loses outside */
  function nbaMiddleEv(lo, loPrice, hi, hiPrice, mu) {
    if (!isFinite(lo) || !isFinite(hi) || !isFinite(mu) || hi <= lo) return null;
    var sd = NBA_MIDDLE.sd, wo = nbaWinAmount(loPrice), wu = nbaWinAmount(hiPrice);
    var tLo = Math.floor(lo) - 1, tHi = Math.ceil(hi) + 1;
    var pBelow = nbaNormCdf((tLo - 0.5 - mu) / sd), pAbove = 1 - nbaNormCdf((tHi + 0.5 - mu) / sd);
    var ev = pBelow * (wu - 1) + pAbove * (wo - 1), pBoth = 0, pHalf = 0;
    for (var t = tLo; t <= tHi; t++) {
      var p = nbaNormCdf((t + 0.5 - mu) / sd) - nbaNormCdf((t - 0.5 - mu) / sd);
      var o = t === lo ? null : t > lo, u = t === hi ? null : t < hi;
      ev += p * ((o === null ? 0 : o ? wo : -1) + (u === null ? 0 : u ? wu : -1));
      if (o && u) pBoth += p; else if ((o === null && u) || (u === null && o)) pHalf += p;
    }
    var wbar = (wo + wu) / 2, need = (1 - wbar) / (1 + wbar);
    return { ev: ev / 2, pBoth: pBoth, pHalf: pHalf, need: need, gap: hi - lo, pays: ev > 0 && hi - lo >= NBA_MIDDLE.minGap - 1e-9, wo: wo, wu: wu };
  }
  /* one leg alone: the chance the over at lo (or the under at hi) wins, the push left out */
  function nbaLegWin(side, line, mu) { var sd = NBA_MIDDLE.sd; return side === "OVER" ? 1 - nbaNormCdf((Math.floor(line) + 0.5 - mu) / sd) : nbaNormCdf((Math.ceil(line) - 0.5 - mu) / sd); }
  /* the apps' numbers as they stand: the newest odds run on the row (oddsNow), else the odds the row was logged with */
  function nbaOddsBlock(inp) { var raw = inp && (inp.oddsNow || inp.odds), o = null; try { o = raw ? JSON.parse(raw) : null; } catch (e) { o = null; } return o; }
  function nbaMiddleMu(inp) { var mu = nbaMainTotal({ odds: (inp || {}).oddsNow || (inp || {}).odds }); if (mu === null) mu = parseFloat((inp || {}).line); return isFinite(mu) ? mu : null; }
  /* every over or under the apps post on the full-game total, the main lines and the alternates: [{book, price, point, alt}] */
  function nbaTotalLegs(o, side) {
    var out = [], seen = {};
    [["total", false], ["alt", true]].forEach(function (src) {
      (((o || {})[src[0]] || {})[side] || []).forEach(function (x) {
        if (NBA_MIDDLE.apps.indexOf(x[0]) < 0 || !isFinite(+x[2]) || !isFinite(+x[1]) || Math.abs(+x[1]) > NBA_MIDDLE.maxPrice) return;
        var k = x[0] + "|" + x[2]; if (seen[k]) return; seen[k] = 1;
        out.push({ book: x[0], price: +x[1], point: +x[2], alt: src[1] });
      });
    });
    return out;
  }
  /* every over/under pair across the apps, best first; the mains for the "apps now" line */
  function nbaMiddlePairs(inp, limit) {
    var o = nbaOddsBlock(inp), mu = nbaMiddleMu(inp); if (!o || mu === null) return null;
    var overs = nbaTotalLegs(o, "OVER"), unders = nbaTotalLegs(o, "UNDER"), out = [];
    overs.forEach(function (a) { unders.forEach(function (b) {
      var gap = b.point - a.point; if (gap < 1 || gap > 15) return;
      var m = nbaMiddleEv(a.point, a.price, b.point, b.price, mu); if (m) out.push({ over: a, under: b, m: m });
    }); });
    out.sort(function (x, y) { return y.m.ev - x.m.ev; });
    var mains = {};
    overs.concat(unders).forEach(function (x) { if (x.alt) return; var d = mains[x.book] || (mains[x.book] = { book: x.book, over: null, under: null }); });
    overs.forEach(function (a) { if (!a.alt && mains[a.book]) mains[a.book].over = a; });
    unders.forEach(function (b) { if (!b.alt && mains[b.book]) mains[b.book].under = b; });
    return { pairs: out.slice(0, limit || 6), n: out.length, pays: out.filter(function (x) { return x.m.pays; }).length, mu: mu, mains: NBA_MIDDLE.apps.map(function (b) { return mains[b]; }).filter(function (x) { return x; }) };
  }
  /* the full-game total legs you hold on a row: the sheet's pick taken, a sim call, the agreement rule; each {side, line, price, how, id} */
  function nbaHeldTotals(row) {
    var out = [];
    (row.markets || []).forEach(function (m) {
      if (m.key !== "total" || !m.take) return;
      var mm = /(OVER|UNDER)\s+(\d+(?:\.\d+)?)/i.exec(String(m.take.pick || m.pick || ""));
      if (mm) out.push({ side: mm[1].toUpperCase(), line: +mm[2], price: m.take.price === null || m.take.price === undefined ? null : +m.take.price, how: "the sheet's pick", id: "sheet" });
    });
    (row.simTakes || []).forEach(function (t) {
      if (t.key !== "total" || t.view === "middle") return;
      out.push({ side: t.side, line: +t.line, price: t.price === null || t.price === undefined ? null : +t.price, how: nbaSimTakeViewLabel(t.view), id: t.id });
    });
    return out;
  }
  /* the watch: for each leg you hold, the best number the apps post on the other side now and whether the pair pays */
  function nbaMiddleWatch(row) {
    var inp = (row && row.inputs) || {}, o = nbaOddsBlock(inp), mu = nbaMiddleMu(inp); if (!o || mu === null) return [];
    var out = [];
    nbaHeldTotals(row).forEach(function (leg) {
      var side2 = leg.side === "OVER" ? "UNDER" : "OVER", best = null;
      nbaTotalLegs(o, side2).forEach(function (x) {
        var lo = leg.side === "OVER" ? leg.line : x.point, hi = leg.side === "OVER" ? x.point : leg.line;
        var m = nbaMiddleEv(lo, leg.side === "OVER" ? leg.price : x.price, hi, leg.side === "OVER" ? x.price : leg.price, mu);
        if (m && (!best || m.ev > best.m.ev)) best = { leg: leg, side: side2, other: x, m: m, lo: lo, hi: hi, mu: mu, first: nbaLegWin(leg.side, leg.line, mu), second: nbaLegWin(side2, x.point, mu) };
      });
      if (best) out.push(best);
    });
    return out;
  }
  function nbaMiddleTakeBtn(row, x) {
    if (!row) return '';
    var t = nbaSimTakeOf(row, "middle", "total", x.side);
    if (isVoid(row) || rowGraded(row)) return t ? '<span class="chip taken">TAKEN</span>' : '';
    return '<button type="button" class="takebtn' + (t ? ' on' : '') + '" data-stake="' + row.id + '|middle|total|' + x.side + '|' + x.other.point + '|' + x.other.price + '|' + x.other.book + '|' + x.leg.id + '" title="' +
           (t ? 'Marked as the second leg you are placing: click to unmark it' : 'Mark the second leg as a bet you are placing') + '">' + (t ? '&#10003; Taking' : 'Take') + '</button>';
  }
  function nbaMiddleWatchHtml(x, row) {
    var pc = function (p) { return (100 * p).toFixed(1) + "%"; }, m = x.m;
    var head = m.pays ? 'MIDDLE OPEN · a ' + (+m.gap.toFixed(1)) + '-point window · pays ' + sgn(100 * m.ev, 1) + '% of the stake' : 'no window yet · ' + (+m.gap.toFixed(1)) + ' points between the numbers' + (m.gap >= NBA_MIDDLE.minGap ? ', the pair ' + sgn(100 * m.ev, 1) + '%' : ', the rule needs three');
    return '<div class="midwatch' + (m.pays ? ' pays' : '') + '"><div class="mwhead"><span class="vbadge' + (m.pays ? ' bet' : '') + '">' + (m.pays ? 'middle' : 'watch') + '</span> <b>' + esc(head) + '</b></div>' +
           '<div class="mwline">You hold <b>' + esc(x.leg.side) + ' ' + esc(String(x.leg.line)) + '</b>' + (x.leg.price === null ? '' : ' at ' + sgn(x.leg.price, 0)) + ' (' + esc(x.leg.how) + '); the market\'s number is ' + esc(String(x.mu)) +
           ', so that leg alone is ' + pc(x.first) + ' to win. The best ' + esc(x.side.toLowerCase()) + ' now: <b>' + esc(bookName(x.other.book)) + ' ' + esc(String(x.other.point)) + ' at ' + sgn(x.other.price, 0) + '</b>' + (x.other.alt ? ' (an alternate)' : '') +
           '. Both win ' + pc(m.pBoth) + ' (the pair needs ' + pc(m.need) + ')' + (m.pHalf > 0.001 ? ', one pushes and one wins ' + pc(m.pHalf) : '') + '; the second leg gives up its vig and takes the loss off the table.</div>' +
           (m.pays ? '<div class="mwtake">' + nbaMiddleTakeBtn(row, x) + ' <span class="dim">Total ' + esc(x.side) + ' ' + esc(String(x.other.point)) + ' at ' + esc(bookName(x.other.book)) + ', the middle with your ' + esc(x.leg.side) + ' ' + esc(String(x.leg.line)) + '</span></div>' : '') + '</div>';
  }
  var midCalc = { ol: "", op: "", ul: "", up: "" };
  function nbaMidCalcOut(mu) {
    var lo = parseFloat(midCalc.ol), hi = parseFloat(midCalc.ul), op = parseFloat(midCalc.op), up = parseFloat(midCalc.up);
    if (!isFinite(lo) || !isFinite(hi)) return '<span class="dim">Type an over number and an under number (the prices default to -110) and the pair is priced off the market\'s number ' + esc(String(mu)) + '.</span>';
    var m = nbaMiddleEv(lo, isFinite(op) ? op : -110, hi, isFinite(up) ? up : -110, mu);
    if (!m) return '<span class="dim">The under number has to sit above the over number.</span>';
    var pc = function (p) { return (100 * p).toFixed(1) + "%"; };
    return '<b>' + (m.pays ? 'Pays' : m.ev > 0 ? 'Positive, but under a three-point gap' : 'The book\'s price') + '</b>: a ' + (+m.gap.toFixed(1)) + '-point window, both win ' + pc(m.pBoth) + (m.pHalf > 0.001 ? ', one pushes and one wins ' + pc(m.pHalf) : '') +
           ', the pair needs ' + pc(m.need) + ' at these prices: ' + sgn(100 * m.ev, 1) + '% of the stake expected (' + sgn(2 * m.ev, 3) + 'u on a unit each).';
  }
  function nbaMidCalcHtml(mu) {
    return '<div class="midcalc"><b>Any pair</b> <span class="dim">· the over number and price, the under number and price</span><div class="midcalcrow">' +
           '<input id="midOverLine" inputmode="decimal" placeholder="over 227.5" value="' + esc(midCalc.ol) + '"><input id="midOverPrice" inputmode="numeric" placeholder="-110" value="' + esc(midCalc.op) + '">' +
           '<input id="midUnderLine" inputmode="decimal" placeholder="under 231.5" value="' + esc(midCalc.ul) + '"><input id="midUnderPrice" inputmode="numeric" placeholder="-110" value="' + esc(midCalc.up) + '"></div>' +
           '<div id="midCalcOut">' + (mu === null ? '<span class="dim">No market number on the row yet: load the odds file.</span>' : nbaMidCalcOut(mu)) + '</div></div>';
  }
  function nbaMidPanel() {
    var el = $("nbaMidPanel"); if (!el) return;
    var f = readNba(), row = nbaSimTakeRow(f), inp = row ? row.inputs : snapshot();
    var P = nbaMiddlePairs(inp, 6), pc = function (p) { return (100 * p).toFixed(1) + "%"; };
    if (!P) { el.innerHTML = '<p class="note">No odds on the row — load the odds file (Run NBA odds) and the apps\' numbers come with it.</p>' + nbaMidCalcHtml(null); return; }
    var h = '<div class="midnow"><b>The apps now</b>' + (row && row.inputs.oddsAt ? ' <span class="dim">(the odds run of ' + esc(String(row.inputs.oddsAt).replace("T", " ").slice(0, 16)) + ' UTC)</span>' : '') + ', the market\'s number <b>' + esc(String(P.mu)) + '</b>: ' +
            P.mains.map(function (x) { return esc(bookName(x.book)) + ' ' + esc(String((x.over || x.under).point)) + ' (' + (x.over ? sgn(x.over.price, 0) : '?') + '/' + (x.under ? sgn(x.under.price, 0) : '?') + ')'; }).join(' · ') + '</div>';
    var W = row ? nbaMiddleWatch(row) : [];
    if (!row) h += '<p class="note">Add the game to the card and take a total (the sheet\'s pick, a sim call or the agreement rule): the watch then names the other leg once the number has run.</p>';
    else if (!W.length) h += '<p class="note">You hold no total on this game yet. Take one (the sheet\'s pick, a sim call or the agreement rule) and the watch names the other leg once the number has run three points or more from it.</p>';
    else W.forEach(function (x) { h += nbaMiddleWatchHtml(x, row); });
    /* the table fits the card at any width (29 Oct 2026, the user: "the table for middles is off"): five columns on fixed widths, the
       app on its own line over the number and price, the break-even under the both-win chance, the verdict in the last cell */
    var leg = function (x) { return '<span class="mbook">' + esc(bookName(x.book)) + (x.alt ? ' <span class="dim">alt</span>' : '') + '</span><span class="mnum">' + esc(String(x.point)) + ' ' + sgn(x.price, 0) + '</span>'; };
    h += '<table class="midtab"><colgroup><col class="c1"><col class="c1"><col class="c2"><col class="c3"><col class="c3"></colgroup><thead><tr><th>Over</th><th>Under</th><th>Gap</th><th>Both win</th><th>The pair</th></tr></thead><tbody>';
    P.pairs.forEach(function (x) {
      h += '<tr class="' + (x.m.pays ? 'pays' : '') + '"><td>' + leg(x.over) + '</td><td>' + leg(x.under) + '</td><td>' + (+x.m.gap.toFixed(1)) + '</td><td>' + pc(x.m.pBoth) + '<span class="mneed">needs ' + pc(x.m.need) + '</span></td>' +
           '<td class="' + (x.m.ev > 0 ? 'good' : 'bad') + '">' + sgn(100 * x.m.ev, 1) + '%<span class="mneed">' + (x.m.pays ? 'pays' : x.m.ev > 0 ? 'under three' : 'the book\'s price') + '</span></td></tr>';
    });
    h += '</tbody></table><div class="dim midnote">' + P.n + ' pair' + (P.n === 1 ? '' : 's') + ' across the apps\' main and alternate numbers, the best six shown; ' + (P.pays ? P.pays + ' pay' + (P.pays === 1 ? 's' : '') + ' at these prices.' : 'none pays at these prices, which is the usual night: the books agree with each other, and the window opens when a number you hold has moved.') + '</div>';
    h += nbaMidCalcHtml(P.mu);
    el.innerHTML = h;
  }
  /* the block on the record (reworked 22 Oct 2026, the user: "add some color... a little more organized"): one table by the
     crew's lean, one by official for everyone who has worked a graded game, the colours on the season's rate and the points */
  function nbaRefsWatchHtml() {
    var mk = function (lean) { return { lean: lean, n: 0, o: 0, u: 0, p: 0, says: 0, pts: 0, units: 0 }; };
    var g = { over: mk("over"), even: mk("even"), under: mk("under") }, byRef = {}, noCrew = 0, noClose = 0;
    var tally = function (s, res, diff, says) {
      if (res === "push") { s.p++; return; }
      s.n++; s.pts += diff; s.says += says;
      if (res === "over") s.o++; else s.u++;
    };
    card.forEach(function (r) {
      if (r.sport !== "NBA" || !r.finals || blank(r.finals.fa) || blank(r.finals.fh)) return;
      var cl = nbaCrewLean(r);
      if (!cl) { noCrew++; return; }
      var c = parseFloat((r.close || {}).ctot);
      if (!isFinite(c)) c = parseFloat((r.inputs || {}).line);   // no close attached: the row's own line, the last the odds run filled (23 Oct 2026)
      if (!isFinite(c)) { noClose++; return; }
      var total = (+r.finals.fa) + (+r.finals.fh), res = total > c ? "over" : total < c ? "under" : "push", says = cl.pastW + cl.pastL ? cl.pastW / (cl.pastW + cl.pastL) : 0.5;
      var s = g[cl.lean];
      tally(s, res, total - c, says);
      if (res !== "push" && cl.lean !== "even") s.units += ((cl.lean === "over") === (res === "over")) ? 100 / 110 : -1;
      cl.officials.forEach(function (o) {
        if (!o.d) return;
        var sr = byRef[o.name] || (byRef[o.name] = { name: o.name, lean: o.lean, z: o.z, pastW: o.pastW, pastL: o.pastL, n: 0, o: 0, u: 0, p: 0, pts: 0, says: 0, units: 0 });
        tally(sr, res, total - c, o.pastW + o.pastL ? o.pastW / (o.pastW + o.pastL) : 0.5);
      });
    });
    var any = g.over.n + g.even.n + g.under.n + g.over.p + g.even.p + g.under.p;
    var chip = function (lean) { return lean === "over" ? '<span class="chip over">OVER LEAN</span>' : lean === "under" ? '<span class="chip under">UNDER LEAN</span>' : '<span class="chip push">EVEN</span>'; };
    var pct = function (x) { return (x * 100).toFixed(1) + "%"; };
    var rateCell = function (s) { var r = s.o / s.n; return '<td class="' + (r > 0.5 ? "over" : r < 0.5 ? "under" : "") + '">' + pct(r) + '</td>'; };
    var ptsCell = function (s) { var v = s.pts / s.n; return '<td class="' + (v > 0 ? "over" : v < 0 ? "under" : "") + '">' + sgn(v, 1) + '</td>'; };
    var unitsCell = function (s, lean) { return lean === "even" ? '<td class="dim">no side</td>' : '<td class="' + (s.units > 0 ? "pos" : s.units < 0 ? "neg" : "") + '">' + sgn(s.units, 2) + 'u</td>'; };
    var h = '<div class="subhead" data-sport="REFS">The referees, as a watch <span class="tag">this season\'s graded totals against the close, by the crew\'s lean in the frozen two-season table · shown, never scored</span></div>';
    h += '<table class="form refs" id="refsLean"><thead><tr><th>Crew lean</th><th>Games</th><th>Over–under</th><th>Past says over</th><th>This season over</th><th>±</th><th>Pts v close</th><th>Flat on the lean</th></tr></thead><tbody>';
    ["over", "even", "under"].forEach(function (lean) {
      var s = g[lean];
      if (!s.n) { h += '<tr><td>' + chip(lean) + '</td><td>0</td><td class="dim" colspan="6">' + (s.p ? s.p + ' push' + (s.p === 1 ? '' : 'es') + ' only' : 'nothing graded with a crew and a close yet') + '</td></tr>'; return; }
      h += '<tr><td>' + chip(lean) + '</td><td>' + s.n + '</td><td>' + s.o + '-' + s.u + (s.p ? '-' + s.p : '') + '</td><td>' + pct(s.says / s.n) + '</td>' + rateCell(s) + '<td class="dim">' + (100 / Math.sqrt(s.n) / 2).toFixed(1) + '</td>' + ptsCell(s) + unitsCell(s, lean) + '</tr>';
    });
    h += '</tbody></table>';
    var refs = Object.keys(byRef).map(function (k) { return byRef[k]; }).sort(function (a, b) { return Math.abs(b.z) - Math.abs(a.z) || a.name.localeCompare(b.name); });
    var refTable = function (id, list) {
      return '<table class="form refs" id="' + id + '"><thead><tr><th>Official</th><th>Lean</th><th>Past two seasons</th><th>This season</th><th>Over rate</th><th>Pts v close</th></tr></thead><tbody>' + list.map(function (s) {
        return '<tr><td>' + esc(s.name) + '</td><td>' + chip(s.lean) + '</td><td>' + s.pastW + '-' + s.pastL + ' <span class="dim">z ' + sgn(s.z, 1) + '</span></td><td>' + s.o + '-' + s.u + (s.p ? '-' + s.p : '') + '</td>' + (s.n ? rateCell(s) : '<td>—</td>') + (s.n ? ptsCell(s) : '<td>—</td>') + '</tr>';
      }).join("") + '</tbody></table>';
    };
    var leaning = refs.filter(function (s) { return s.lean !== "even"; }), even = refs.filter(function (s) { return s.lean === "even"; });
    if (refs.length) {
      h += '<div class="subhead">The leaning officials <span class="tag">the ones the past table flags, who have worked a graded game on the card</span></div>';
      h += leaning.length ? refTable("refsRefs", leaning) : '<div class="verdict">None of the leaning officials has worked a graded game on the card yet.</div>';
      if (even.length) h += '<details class="fold refsfold"><summary><span>Officials with no lean</span> <span class="tag">' + even.length + ' within 1.5 sigma of even in the past table, by the size of the tilt</span></summary><div class="body">' + refTable("refsEven", even) + '</div></details>';
    }
    h += '<div class="verdict">An official 1.5 sigma or more over or under the close across 2024-25 and 2025-26 <b>leans</b> (eight officials over, 450-286 pooled; seven under, 175-270), and a crew leans by the sum of its three. ' +
         'The test is whether the past lean carries: if the over crews keep running over and the under crews under, the crew becomes an input at the season\'s end, scored at what this block says. Two seasons of closes said crews predict free throws (t 7.3) and the total does not follow (t −1.0), so expect both leans to drift toward the league\'s rate. ' +
         'One standard error at twenty games is eleven points; read nothing under a hundred a line. On the matchup, the Referee stats card carries the same lean as its badge.' +
         (any ? '' : ' Nothing graded yet with a crew in the Crew box and a close on the card.') +
         (noCrew ? ' ' + noCrew + ' graded game' + (noCrew === 1 ? '' : 's') + ' without a crew.' : '') + (noClose ? ' ' + noClose + ' without a close or a line.' : '') + '</div>';
    return h;
  }
  /* ===== END NBA BLOCK ===== */
