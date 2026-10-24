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
    if (!SRC) { nbaOutPanel(); nbaLineupPanel(); nbaFormPanel(); nbaCrewPanel(); nbaCtxPanel(); }   // the form's panels: not while a card row is being re-scored
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
