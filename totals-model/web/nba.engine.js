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
    var away = canonTeam($("away").value, "NBA") || "Away", home = canonTeam($("home").value, "NBA") || "Home";
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
  function nbaCtxPanel() {
    var el = $("nbaCtxPanel"); if (!el) return;
    var raw = ($("nbactx") || {}).value || "", ctx = null;
    try { ctx = raw ? JSON.parse(raw) : null; } catch (e) { ctx = null; }
    if (!ctx || !ctx.length) {
      el.innerHTML = "No context on the row — load the slate and Fill form, and the lines come with it.";
      return;
    }
    var order = { scored: 0, faded: 1, shown: 2, label: 3 };
    var items = ctx.slice().sort(function (a, b) { return (order[a.s] || 0) - (order[b.s] || 0); });
    el.innerHTML = '<ul class="ctx">' + items.map(function (c) {
      var s = order[c.s] !== undefined ? c.s : "shown";
      return '<li class="ctx-' + s + '"><span class="cbadge">' + s + '</span> <span class="ctext">' + esc(c.t || "") + '</span>' +
             (c.tag ? ' <span class="ctag">' + esc(c.tag) + '</span>' : '') + '</li>';
    }).join("") + '</ul>';
  }
  function forecastMatchupNba() {
    nbaOutPanel();
    nbaCtxPanel();
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
      var pH = 1 - ncdf((0 - margin) / NBA.MARGIN_SD);
      markets.push(pickOf("ml", "Moneyline",
        [sideOf(home + " ML", "HOME", pH, 0, hml), sideOf(away + " ML", "AWAY", 1 - pH, 0, aml)],
        hml !== null && aml !== null, "",
        ["Read off the margin through a normal at " + NBA.MARGIN_SD + ", which fits the spread's home win rate within a few points at every bucket (big home dogs win a little less than it says). An edge here is only the book's moneyline disagreeing with its own spread."]));
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
        h += "<tr" + (isOut || ticked.indexOf(id) >= 0 ? ' class="out"' : "") + "><td>" + esc(p.n || "?") + "</td><td>" + esc(p.st || "") + "</td><td>" + (p.mpg !== undefined && p.mpg !== null ? (+p.mpg).toFixed(1) : "—") +
             "</td><td>" + (p.ppg !== undefined && p.ppg !== null ? (+p.ppg).toFixed(1) : "—") + "</td><td>" + (p.pm !== undefined && p.pm !== null ? sgn(+p.pm, 1) : "—") + "</td><td>" + esc(p.note || "") + "</td><td>" + box + "</td></tr>";
      });
      h += "</tbody></table>";
    });
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
  /* ===== END NBA BLOCK ===== */
