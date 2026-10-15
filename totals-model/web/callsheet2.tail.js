
  /* ====================================================================
     Call Sheet 2.0 -- ported from totals/callsheet2.py. Everything above
     this line is Call Sheet #1's engine, byte-identical to fullgame.html;
     everything below is the two-team distribution, the derivative markets,
     the ranking and the day board. web/callsheet2-cases.json is replayed
     through this page against the package on every change.
  ==================================================================== */
  function priceFor(p) {
    if (Math.abs(p - 0.5) < 1e-9) return 100;
    return p > 0.5 ? -100 * p / (1 - p) : 100 * (1 - p) / p;
  }
  /* Strip the hold from a two-sided quote, regressing a wide one toward even
     exactly as the total's anchor does. Returns [p first, p second]. */
  function devig(a, b) {
    var ia = implied(a), ib = implied(b), s = ia + ib;
    var p = ia / s;
    p = 0.5 + (p - 0.5) * marketConfidence(s - 1);
    return [p, 1 - p];
  }
  function payout(price) { return price > 0 ? price / 100 : 100 / -price; }

  /* Each constant is inherited or a fraction of the game. See the module
     docstring in totals/callsheet2.py for what has NOT been measured. */
  var WNBA_MARGIN_SD = 11.0;      // the retired spread model's figure
  var WNBA_HOME_COURT = 2.5;      // its home court too, total-neutral
  /* The margin is anchored on the market the way the total is, and the one
     estimate that can move it is the four efficiency ratings the total
     already scores, so it carries the total's efficiency weight. Added 2 Oct
     2026 when the user asked for the WNBA book to lean on the spread and the
     moneyline; until then both were read off the book's own prices. */
  var WNBA_MARGIN_WEIGHTS = { market: WNBA_WEIGHTS.market, ratings: WNBA_WEIGHTS.efficiency };
  var F5_SHARE = 5 / 9;           // innings share; sizes the weather deltas only
  var F5_INNINGS = 5.0;
  var TEAM_PHI = PHI.MLB;         // independence between the teams implies it
  var F5_PHI = PHI.MLB;           // UNMEASURED and too wide: conservative
  var DEFAULT_RUN_LINE = 1.5;
  var KMAX = 40;

  function teamPmf(mu, phi) {
    var pm = [], s = 0;
    for (var k = 0; k <= KMAX; k++) { var v = nbPmf(k, mu, phi); pm.push(v); s += v; }
    return s > 0 ? pm.map(function (v) { return v / s; }) : pm;
  }
  function marginProbs(lh, la) {
    var h = teamPmf(lh, TEAM_PHI), a = teamPmf(la, TEAM_PHI), dist = {};
    for (var i = 0; i <= KMAX; i++) {
      if (h[i] < 1e-15) continue;
      for (var j = 0; j <= KMAX; j++) {
        if (a[j] < 1e-15) continue;
        dist[i - j] = (dist[i - j] || 0) + h[i] * a[j];
      }
    }
    var win = 0, lose = 0, tie = dist[0] || 0;
    Object.keys(dist).forEach(function (d) { d = +d; if (d > 0) win += dist[d]; else if (d < 0) lose += dist[d]; });
    return { win: win, tie: tie, lose: lose, dist: dist };
  }
  /* A game cannot end tied. Extras are a fresh contest between the same two
     sides, so the tie is split in the ratio the nine-inning result showed. */
  function pHomeWins(lh, la) {
    var m = marginProbs(lh, la), decided = m.win + m.lose;
    return m.win + m.tie * (decided > 0 ? m.win / decided : 0.5);
  }
  function solveSplit(total, pHome) {
    var lo = 0.35, hi = total - 0.35;
    for (var i = 0; i < 60; i++) {
      var mid = (lo + hi) / 2;
      if (pHomeWins(mid, total - mid) < pHome) lo = mid; else hi = mid;
    }
    var lh = (lo + hi) / 2;
    return [lh, total - lh];
  }
  /* (P home covers, P push, P away covers) for the HOME side at homeLine.
     The tied mass after nine is moved to +1 / -1 in the moneyline's ratio. */
  function runLineProbs(lh, la, homeLine) {
    var m = marginProbs(lh, la);
    var shareH = (m.win + m.lose) > 0 ? m.win / (m.win + m.lose) : 0.5;
    var cover = 0, push = 0, fail = 0;
    var entries = Object.keys(m.dist).map(function (d) { return [+d, m.dist[d]]; });
    entries.push([1, m.tie * shareH]); entries.push([-1, m.tie * (1 - shareH)]);
    entries.forEach(function (e) {
      if (e[0] === 0) return;
      var x = e[0] + homeLine;
      if (x > 1e-9) cover += e[1]; else if (x < -1e-9) fail += e[1]; else push += e[1];
    });
    return [cover, push, fail];
  }
  function spreadProbs(margin, homeLine, sd) {
    sd = sd || WNBA_MARGIN_SD;
    if (Math.abs(homeLine - Math.round(homeLine)) < 1e-9) {
      var k = -homeLine;
      var lo = ncdf((k - 0.5 - margin) / sd), hi = ncdf((k + 0.5 - margin) / sd);
      var push = hi - lo, cover = 1 - hi, fail = lo;
      if (Math.abs(k) < 1e-9) { cover += push / 2; fail += push / 2; push = 0; }
      return [cover, push, fail];
    }
    var c = 1 - ncdf((-homeLine - margin) / sd);
    return [c, 0, 1 - c];
  }
  function invNcdf(p) {
    var lo = -8, hi = 8;
    for (var i = 0; i < 80; i++) { var mid = (lo + hi) / 2; if (ncdf(mid) < p) lo = mid; else hi = mid; }
    return (lo + hi) / 2;
  }

  /* ---- one side of one market ------------------------------------------- */
  function sideOf(pick, side, pRaw, pPush, price) {
    var live = 1 - pPush, p = live > 0 ? pRaw / live : 0.5;
    var be = null, edge = null, ev = null;
    if (price !== null && price !== undefined) {
      be = implied(price); edge = p - be; ev = live * (p * payout(price) - (1 - p));
    }
    return { pick: pick, side: side, p: p, pPush: pPush, price: price === undefined ? null : price,
             breakeven: be, edge: edge, ev: ev };
  }
  /* With prices in, the side with the higher EDGE; without, the likelier side.
     Those can differ, and the difference is the point of this sheet. */
  function pickOf(key, label, sides, anchored, band, notes) {
    var priced = sides.filter(function (s) { return s.price !== null; }).length > 0;
    /* Ties break toward the FIRST side listed (over, home), and a tie is
       anything inside 1e-9 -- on a no-information card the two sides differ
       by a floating-point hair whose sign depends on the platform's erf. */
    var best = sides[0];
    sides.slice(1).forEach(function (s) {
      if (priced) {
        var eb = best.edge === null ? -9 : best.edge, es = s.edge === null ? -9 : s.edge;
        if (es > eb + 1e-9 || (Math.abs(es - eb) <= 1e-9 && s.p > best.p + 1e-9)) best = s;
      } else if (s.p > best.p + 1e-9) best = s;
    });
    var other = sides.filter(function (s) { return s !== best; })[0];
    var m = { key: key, label: label, pick: best.pick, side: best.side, p: best.p, pPush: best.pPush,
              price: best.price, breakeven: best.breakeven, edge: best.edge, ev: best.ev,
              fair: priceFor(best.p), anchored: anchored, band: band || "",
              notes: (notes || []).slice(),
              other: { pick: other.pick, p: other.p, price: other.price, edge: other.edge } };
    if (priced && best.edge !== null && best.edge <= 0) m.notes.push(
      "Neither side is priced below its probability. " + best.pick + " is the closer of the two at " +
      sgn(best.edge * 100, 1) + " points; the book is charging more than this number is worth on both sides.");
    return m;
  }

  /* Call Sheet #1's total as a 2.0 market. The BAND is #1's verdict on #1's
     SIDE, the likelier side; the side picked here is the better PRICE, which
     on a lopsided quote can be the other one. When they differ the band does
     not travel -- a BET on the over is not a BET on the under. band1/side1
     carry #1's verdict regardless, for the rank-by-probability view. */
  function totalMarket(f, line, op, up, dp) {
    var m = pickOf("total", "Full-game total " + line,
      [sideOf("OVER " + line, "OVER", f.pOver, f.pPush, op),
       sideOf("UNDER " + line, "UNDER", f.pUnder, f.pPush, up)],
      true, f.band, ["Call Sheet #1's number, unchanged: projected " + f.projected.toFixed(dp) + ", " + f.band + "."]);
    m.band1 = f.band; m.side1 = f.side;
    if (m.side !== f.side) {
      m.band = "";
      m.notes.push("Call Sheet #1 names <b>" + f.side + " " + line + "</b> at " + (f.pResolved * 100).toFixed(1) + "% (" + f.band +
        "). This side is picked on PRICE, not likelihood — the book is charging so much for the " + f.side.toLowerCase() +
        " that the " + m.side.toLowerCase() + " is the better bet even though it is the less likely result. #1's band stays with #1's side.");
    }
    return m;
  }

  /* The likelier side of a market, for the rank-by-probability view. The
     stored pick is the better PRICE; asked to rank by probability, the reader
     means the side more likely to hit, which can be the other one. */
  var FLIP = { OVER: "UNDER", UNDER: "OVER", HOME: "AWAY", AWAY: "HOME" };
  function likelier(mk) {
    if (!mk.other || mk.other.p <= mk.p + 1e-9) return mk;
    var o = mk.other, side = FLIP[mk.side] || mk.side;
    return { key: mk.key, label: mk.label, pick: o.pick, side: side, p: o.p, pPush: mk.pPush,
             price: o.price, breakeven: o.price === null || o.price === undefined ? null : implied(o.price),
             edge: o.edge === undefined ? null : o.edge, fair: priceFor(o.p), anchored: mk.anchored,
             band: (mk.side1 && side === mk.side1) ? (mk.band1 || "") : "",
             band1: mk.band1, side1: mk.side1, notes: mk.notes,
             other: { pick: mk.pick, p: mk.p, price: mk.price, edge: mk.edge }, flipped: true };
  }
  function viewOf(mk, byProb) { return byProb ? likelier(mk) : mk; }

  /* ---- MLB ---------------------------------------------------------------- */
  function forecastMatchupMlb() {
    var f = readMlb();
    var away = f.away, home = f.home, line = f.line;
    var op = num("op"), up = num("up"), hml = num("hml"), aml = num("aml");
    var rlIn = num("rl"), rlh = num("rlh"), rla = num("rla");
    var f5line = num("f5line"), f5op = num("f5op"), f5up = num("f5up");
    var notes = [], markets = [];

    markets.push(totalMarket(f, line, op, up, 2));

    var anchor = f.estimates.filter(function (e) { return e.name === "Market"; })[0].total;
    var lamH = null, lamA = null;
    if (hml !== null && aml !== null) {
      var dv = devig(hml, aml), pHomeMkt = dv[0];
      var mlHold = implied(hml) + implied(aml) - 1;
      var split = solveSplit(anchor, pHomeMkt);
      var scale = anchor > 0 ? f.projected / anchor : 1;
      lamH = split[0] * scale; lamA = split[1] * scale;
      notes.push(sgn(hml, 0) + "/" + sgn(aml, 0) + " de-vigs to <b>" + (pHomeMkt * 100).toFixed(1) +
        "% " + home + "</b> (" + (mlHold * 100).toFixed(1) + "% hold). With the market's total of " +
        anchor.toFixed(2) + " that puts the split at <b>" + split[1].toFixed(2) + " " + away + ", " +
        split[0].toFixed(2) + " " + home + "</b>; the total forecast moves both by ×" + scale.toFixed(3) +
        ". The moneyline already knows the starters, so nothing per-team moves this split — the split IS the market.");
      if (mlHold > HOLD_REFERENCE) notes.push("A " + (mlHold * 100).toFixed(1) +
        "% moneyline hold is wide for a main line; only " + (marketConfidence(mlHold) * 100).toFixed(0) +
        "% of the de-vigged lean is kept, the same regression Call Sheet #1 applies to a wide total.");

      var pH = pHomeWins(lamH, lamA);
      markets.push(pickOf("ml", "Moneyline",
        [sideOf(home + " ML", "HOME", pH, 0, hml), sideOf(away + " ML", "AWAY", 1 - pH, 0, aml)],
        true, "", ["Priced off the book's own moneyline; the only thing that can move it is the total " +
          "forecast changing how often the two means tie. An edge here is the distribution disagreeing " +
          "with the book about extra innings, and that is a small thing."]));

      var homeLine = rlIn !== null ? rlIn : (pHomeMkt >= 0.5 ? -DEFAULT_RUN_LINE : DEFAULT_RUN_LINE);
      var rp = runLineProbs(lamH, lamA, homeLine);
      markets.push(pickOf("rl", "Run line " + home + ": " + sgn(homeLine, 1).replace(".0", ""),
        [sideOf(home + " " + fmtLine(homeLine), "HOME", rp[0], rp[1], rlh),
         sideOf(away + " " + fmtLine(-homeLine), "AWAY", rp[2], rp[1], rla)],
        rlh !== null && rla !== null, "",
        ["Derived from the total and the moneyline: the run line is where a two-team run distribution " +
         "and a book's template can disagree, so this is the market most worth checking and the one most " +
         "likely to be the MODEL's error rather than the book's.",
         "Walk-offs truncate the home margin — a home side that wins in the ninth or later wins by exactly " +
         "what it needed — so this distribution overstates how often a home favourite covers −1.5. " +
         "Direction known, size unmeasured."]));
    } else {
      notes.push("No moneyline entered, so there is no split and no moneyline or run line on this card. " +
        "Both prices are needed — one side's price says the lean, both say the hold.");
    }

    if (f5line !== null) {
      var fa = fairTotal("MLB", f5line, f5op, f5up), muF5 = fa[0];
      var est5 = [[muF5, WEIGHTS.MLB.market]];
      var f5notes = ["Anchored on the first-five market: " + fa[1]];
      var starters = f.estimates.filter(function (e) { return e.name === "Starters"; })[0];
      if (starters) {
        var gap = (starters.total - anchor) * (F5_INNINGS / STARTER_INNINGS);
        est5.push([muF5 + gap, starters.weight]);
        f5notes.push("Starters: " + sgn(gap) + " runs over five innings, at weight " + starters.weight + ". The full " +
          "game stopped scoring the starters on 26 Sept (they flipped picks the wrong way there); here they are the " +
          "only thing on the mound, so they stay. No bullpens — they do not pitch in the first five, which is the whole reason " +
          "this market exists.");
      }
      var d5 = f.deltas.reduce(function (a, d) { return a + d.runs; }, 0) * F5_SHARE;
      var tw = est5.reduce(function (a, e) { return a + e[1]; }, 0);
      var proj5 = est5.reduce(function (a, e) { return a + e[0] * e[1]; }, 0) / tw + d5;
      if (f.deltas.length) f5notes.push("Weather and park deltas scaled by 5/9: " + sgn(d5) + ".");
      f5notes.push("Dispersion is the full-game figure, which is too wide for five innings with no pen and " +
        "no extras. That pulls this probability TOWARD 50%, so if anything it is understated. On the log to be measured.");
      var s5 = nbSplit(f5line, proj5, F5_PHI);
      markets.push(pickOf("f5", "First five total " + f5line,
        [sideOf("F5 OVER " + f5line, "OVER", s5[0], s5[1], f5op),
         sideOf("F5 UNDER " + f5line, "UNDER", s5[2], s5[1], f5up)],
        f5op !== null && f5up !== null, "", f5notes.concat(["Projected " + proj5.toFixed(2) + " against " + f5line + "."])));
    }
    return { sport: "MLB", away: away, home: home, matchup: away + " @ " + home, markets: markets,
             lamHome: lamH, lamAway: lamA, total: f, notes: notes, period: (typeof proj5 !== "undefined" ? proj5 : null) };
  }
  function fmtLine(v) { return (v >= 0 ? "+" : "") + (Math.abs(v - Math.round(v)) < 1e-9 ? String(v) : v.toFixed(1)); }

  /* ---- WNBA --------------------------------------------------------------- */
  /* The margin (home minus away) the four ratings imply, plus home court:
     each offence against the defence it faces, per 100 possessions, over the
     possessions the two paces give (the league pace when a pace is missing,
     since pace only scales the gap). Four league-average ratings give exactly
     the home court. The level problem the retired model documented -- pace
     and ratings off different possession counts -- is a level problem: in a
     difference a uniform shift of all four only rescales the gap, where in
     the total it set the whole number. That is why the margin can use the
     identity the total could not. */
  function ratingsMargin() {
    var ao = num("aort"), ho = num("hort"), ad = num("adrt"), hd = num("hdrt");
    if (![ao, ho, ad, hd].every(function (v) { return v !== null && ok(v, "rating"); })) return null;
    var ap = num("apace"), hp = num("hpace"), possessions = WNBA.PACE;
    if (ap !== null && hp !== null && ok(ap, "pace") && ok(hp, "pace")) possessions = ap * hp / WNBA.PACE;
    var hppp = ho * ad / WNBA.RATING, appp = ao * hd / WNBA.RATING;
    var gap = possessions * (hppp - appp) / 100;
    return { margin: gap + WNBA_HOME_COURT,
             why: "home " + ho.toFixed(1) + " into " + ad.toFixed(1) + " is " + hppp.toFixed(1) + " per 100, away " + ao.toFixed(1) +
                  " into " + hd.toFixed(1) + " is " + appp.toFixed(1) + "; over " + possessions.toFixed(1) + " possessions that is " +
                  sgn(gap, 1) + ", plus " + WNBA_HOME_COURT + " of home court" };
  }
  function forecastMatchupWnba() {
    var f = readWnba();
    var away = f.away, home = f.home, line = f.line;
    var op = num("op"), up = num("up"), hml = num("hml"), aml = num("aml");
    var sp = num("sp"), sph = num("sph"), spa = num("spa");
    var notes = [], markets = [];
    markets.push(totalMarket(f, line, op, up, 1));

    var margin = null, src = "";
    if (sp !== null) {
      if (sph !== null && spa !== null) {
        var pCover = devig(sph, spa)[0], lo = -40, hi = 40;
        for (var i = 0; i < 60; i++) {
          var mid = (lo + hi) / 2, pr = spreadProbs(mid, sp), live = pr[0] + pr[2];
          if ((live > 0 ? pr[0] / live : 0.5) < pCover) lo = mid; else hi = mid;
        }
        margin = (lo + hi) / 2;
        src = "spread " + fmtLine(sp) + " at " + sgn(sph, 0) + "/" + sgn(spa, 0) + ", which de-vigs to " +
          (pCover * 100).toFixed(1) + "% home and moves fair to " + sgn(margin, 1);
      } else { margin = -sp; src = "spread " + fmtLine(sp) + " taken as the mean margin (no prices)"; }
    } else if (hml !== null && aml !== null) {
      var pHm = devig(hml, aml)[0];
      margin = -WNBA_MARGIN_SD * invNcdf(1 - pHm);
      src = "moneyline " + sgn(hml, 0) + "/" + sgn(aml, 0) + ", " + (pHm * 100).toFixed(1) + "% home";
    }
    if (margin === null) {
      notes.push("No spread or moneyline entered, so no side markets on this card.");
      return { sport: "WNBA", away: away, home: home, matchup: away + " @ " + home, markets: markets,
               lamHome: null, lamAway: null, total: f, notes: notes };
    }
    var rm = ratingsMargin();
    if (rm) {
      var wm = WNBA_MARGIN_WEIGHTS.market, wr = WNBA_MARGIN_WEIGHTS.ratings;
      var blended = (wm * margin + wr * rm.margin) / (wm + wr);
      notes.push("Margin (home minus away) of <b>" + sgn(blended, 1) + "</b>: the market says " + sgn(margin, 1) + " from the " + src +
        ", at weight " + wm + "; the ratings say <b>" + sgn(rm.margin, 1) + "</b> (" + rm.why + "), at weight " + wr +
        ", the efficiency weight the total uses for the same four numbers. On a margin SD of " + WNBA_MARGIN_SD +
        ". The total forecast does not move it — pace and efficiency change how many points, not who scores more of them — " +
        "and the ratings move it only by how far they disagree with the book.");
      margin = blended;
    } else {
      notes.push("Margin (home minus away) of <b>" + sgn(margin, 1) + "</b> from the " + src + ", on a margin SD of " +
        WNBA_MARGIN_SD + ". The total forecast does not move it — pace and efficiency change how many points, " +
        "not who scores more of them. No ratings on the card, so the margin is the market's alone and the side markets " +
        "can only ever show the vig.");
    }
    var half = f.projected / 2, lamH = half + margin / 2, lamA = half - margin / 2;
    var pH = 1 - ncdf((0 - margin) / WNBA_MARGIN_SD);
    /* `informed`: the four ratings were on the card, so the side carries team
       information and may be picked. Without them the side is the book's own
       price read back, and stays shown, not picked (see pickable). */
    var mlm = pickOf("ml", "Moneyline",
      [sideOf(home + " ML", "HOME", pH, 0, hml), sideOf(away + " ML", "AWAY", 1 - pH, 0, aml)],
      hml !== null && aml !== null, "",
      ["Read off the margin: the book's spread or moneyline, moved by the four efficiency ratings when they are on " +
       "the card. With no ratings an edge here is only the book's moneyline disagreeing with its own spread, which " +
       "happens, and is small."]);
    mlm.informed = !!rm;
    markets.push(mlm);
    if (sp !== null) {
      var pr2 = spreadProbs(margin, sp);
      var spm = pickOf("spread", "Spread " + home + ": " + fmtLine(sp),
        [sideOf(home + " " + fmtLine(sp), "HOME", pr2[0], pr2[1], sph),
         sideOf(away + " " + fmtLine(-sp), "AWAY", pr2[2], pr2[1], spa)],
        sph !== null && spa !== null, "",
        ["The spread with both prices in is the anchor; the four efficiency ratings are the one estimate that can " +
         "move the margin off it, at the total's efficiency weight. With no ratings this side's edge is only ever the " +
         "vig regressed for a wide hold."]);
      spm.informed = !!rm;
      markets.push(spm);
    }
    return { sport: "WNBA", away: away, home: home, matchup: away + " @ " + home, markets: markets,
             lamHome: lamH, lamAway: lamA, total: f, notes: notes };
  }

  function rankMarkets(markets, byProb) {
    return markets.map(function (m) { return viewOf(m, byProb); }).sort(function (a, b) {
      if (byProb) return b.p - a.p;
      var an = a.edge === null ? 1 : 0, bn = b.edge === null ? 1 : 0;
      if (an !== bn) return an - bn;
      if (!an && a.edge !== b.edge) return b.edge - a.edge;
      return b.p - a.p;
    });
  }

  /* ---- grading ---------------------------------------------------------- */
  function lineOf(mk) {
    var m;
    if (mk.key === "total" || mk.key === "f5") { m = /([0-9]+(?:\.[0-9]+)?)\s*$/.exec(mk.pick); return m ? +m[1] : 0; }
    if (mk.key === "ml") return 0;
    m = /([+-][0-9]+(?:\.[0-9]+)?)\s*$/.exec(mk.pick);
    var v = m ? +m[1] : 0;
    return mk.side === "HOME" ? v : -v;
  }
  function gradeMarket(mk, fin) {
    var fh = fin ? parseFloat(fin.fh) : NaN, fa = fin ? parseFloat(fin.fa) : NaN;
    var f5h = fin ? parseFloat(fin.f5h) : NaN, f5a = fin ? parseFloat(fin.f5a) : NaN;
    var line = lineOf(mk), total;
    if (mk.key === "total" || mk.key === "f5") {
      if (mk.key === "f5") {
        if (!isFinite(f5h) || !isFinite(f5a)) return null;
        /* A side's runs after five cannot exceed its final. Five rows on the
           first graded night had exactly that, so the market refuses to grade
           and says so rather than scoring a number that cannot have happened. */
        if ((isFinite(fa) && f5a > fa + 1e-9) || (isFinite(fh) && f5h > fh + 1e-9)) return "invalid";
        total = f5h + f5a;
      }
      else { if (!isFinite(fh) || !isFinite(fa)) return null; total = fh + fa; }
      if (Math.abs(total - line) < 1e-9) return "push";
      return ((mk.side === "OVER") ? total > line : total < line) ? "win" : "loss";
    }
    if (!isFinite(fh) || !isFinite(fa)) return null;
    var margin = fh - fa;
    if (mk.key === "ml") return ((margin > 0) === (mk.side === "HOME")) ? "win" : "loss";
    var x = margin + line;
    if (Math.abs(x) < 1e-9) return "push";
    return ((x > 0) === (mk.side === "HOME")) ? "win" : "loss";
  }
  function resText(res) { return res === "invalid" ? "F5 > final — recheck" : res; }
  /* ---- the closing line ---------------------------------------------------
     How far the pick beat the number the market closed at, in runs (points
     in the WNBA): positive when the close moved AWAY from the side taken --
     an over at 7 that closed 7.5, an under at 6.5 that closed 6. A pick that
     beats the close on average is an edge whatever last night did; one that
     loses to it on average is luck however the week went. Totals and first
     fives only, because those are the picks; the close is typed on the card
     the next morning with the finals. Nothing here moves a number. 30 Sept. */
  function clvOf(mk, row) {
    var c = (row && row.close) || {};
    var v = mk.key === "total" ? parseFloat(c.ctot) : mk.key === "f5" ? parseFloat(c.cf5) : NaN;
    if (!isFinite(v)) return null;
    var line = lineOf(mk);
    return mk.side === "OVER" ? v - line : line - v;
  }
  function unitsOf(mk, res) {
    if (res === null || res === "push" || res === "invalid" || mk.price === null) return 0;
    return res === "win" ? payout(mk.price) : -1;
  }

  /* ---- reading the form / storage ---------------------------------------- */
  var MLB_IDS = ["away","home","line","op","up","opened","gdate","aera","hera","aip","hip","arpg","hrpg",
                 "abp","hbp","al10","hl10","h2h","h2hn","pf","mph","dir","temp","tick","cash",
                 "hml","aml","rl","rlh","rla","f5line","f5op","f5up",
                 /* shown, not scored: the last five starts, recorded since 28 Sept so
                    recent form can be tested against the record rather than assumed */
                 "al5era","hl5era","al5ip","hl5ip",
                 /* the shop: every book's price on each side, JSON from the odds file (12 Oct 2026) */
                 "odds","sharp"];
  var WNBA_IDS = ["away","home","line","op","up","opened","gdate","apace","hpace","aort","hort","adrt","hdrt",
                  "arest","hrest","al5","hl5","hml","aml","sp","sph","spa"];
  var ALL = MLB_IDS.concat(WNBA_IDS).filter(function (v, i, a) { return a.indexOf(v) === i; });
  var CHECKS = ["dome","playoff"];
  function snapshot() {
    var s = {};
    ALL.forEach(function (id) { s[id] = $(id).value; });
    CHECKS.forEach(function (id) { s[id] = $(id).checked; });
    return s;
  }
  function scoreMatchup(sp, inputs) {
    var prev = SRC; SRC = inputs || null;
    try { return sp === "WNBA" ? forecastMatchupWnba() : forecastMatchupMlb(); }
    catch (e) { return null; }
    finally { SRC = prev; }
  }
  function slimMarkets(ms) {
    return ms.map(function (m) {
      return { key: m.key, label: m.label, pick: m.pick, side: m.side, p: +m.p.toFixed(5), pPush: +m.pPush.toFixed(5),
               price: m.price, edge: m.edge === null ? null : +m.edge.toFixed(5), fair: +m.fair.toFixed(1),
               anchored: m.anchored, band: m.band, band1: m.band1, side1: m.side1, other: m.other,
               informed: m.informed === undefined ? undefined : !!m.informed };
    });
  }

  var KEY = "callsheet2.card.v1", DRAFT_KEY = "callsheet2.draft.v1";
  var card = [];
  try { card = JSON.parse(localStorage.getItem(KEY) || "[]"); } catch (e) { card = []; }
  /* A card written before 29 Sept could hold the same ungraded game twice with
     identical inputs (Add pressed twice). Drop the later copy once, on load. */
  (function () {
    var seen = [], keep = [];
    card.forEach(function (r) {
      var twin = !rowGraded(r) && seen.some(function (s) { return !rowGraded(s) && sameGame(s, { sport: r.sport, gdate: r.gdate, away: r.away, home: r.home }) &&
                                                                   JSON.stringify(s.inputs) === JSON.stringify(r.inputs); });
      if (!twin) { seen.push(r); keep.push(r); }
    });
    if (keep.length !== card.length) { card = keep; try { localStorage.setItem(KEY, JSON.stringify(card)); } catch (e) {} }
  })();
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(card)); }
    catch (e) { $("saveState").textContent = "this browser is not storing anything"; }
  }
  function saveDraft() {
    try { localStorage.setItem(DRAFT_KEY, JSON.stringify({ sport: sport, inputs: snapshot() })); $("saveState").textContent = "draft saved"; }
    catch (e) { $("saveState").textContent = "this browser is not storing anything"; }
  }
  function loadDraft() {
    var d = null;
    try { d = JSON.parse(localStorage.getItem(DRAFT_KEY) || "null"); } catch (e) { d = null; }
    if (!d || !d.inputs) return false;
    setSport(d.sport === "WNBA" ? "WNBA" : "MLB", true);
    restore(d.inputs);
    return true;
  }
  function restore(inputs) {
    ALL.forEach(function (id) { $(id).value = inputs[id] === undefined || inputs[id] === null ? "" : inputs[id]; });
    CHECKS.forEach(function (id) { $(id).checked = !!inputs[id]; });
  }
  function todayISO() {
    var d = new Date(), z = function (n) { return (n < 10 ? "0" : "") + n; };
    return d.getFullYear() + "-" + z(d.getMonth() + 1) + "-" + z(d.getDate());
  }
  var MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  function gameDate(iso) {
    if (!iso) return "";
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
    return m ? MONTHS[+m[2] - 1] + " " + (+m[3]) : iso;
  }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function sideClass(side) { return side.toLowerCase(); }

  /* ---- render: this matchup ------------------------------------------------ */
  var last = null;
  /* ---- the forecast, betting aside (11 Oct 2026) ----------------------------
     What the sheet expects to happen, apart from any price: the projected
     total, each side's expected score where the sides are modelled, the
     period projection, and the winner's chance from the moneyline market.
     Stored on the row as `proj` when it is added (t total, h/a the sides,
     q the period, ph the home side's chance), so the record can keep the
     forecast's accuracy against the market's line and the favourite. Asked
     for by the user: "a machine that can provide the best prediction
     outcome for a matchup", with the bets set aside. */
  function projOf(m) {
    if (!m || !m.total) return null;
    var r = function (v) { return v === null || v === undefined || !isFinite(v) ? null : +(+v).toFixed(3); };
    var ml = (m.markets || []).filter(function (mk) { return mk.key === "ml"; })[0], pHome = null;
    if (ml && ml.side === "HOME") pHome = ml.p; else if (ml && ml.side === "AWAY") pHome = 1 - ml.p;
    return { t: r(m.total.projected), h: r(m.lamHome), a: r(m.lamAway), q: r(m.period), ph: r(pHome) };
  }
  function forecastText(m, sp) {
    var pj = projOf(m); if (!pj || pj.t === null) return "";
    var unit = sp === "WNBA" ? "points" : sp === "NHL" ? "goals" : "runs", dp = sp === "WNBA" ? 0 : 1, parts = [];
    if (pj.h !== null && pj.a !== null) parts.push(esc(m.away) + " " + pj.a.toFixed(dp) + " – " + esc(m.home) + " " + pj.h.toFixed(dp));
    parts.push("total " + pj.t.toFixed(dp) + " " + unit);
    if (pj.q !== null) parts.push((sp === "NHL" ? "first period " : "first five ") + pj.q.toFixed(dp));
    if (pj.ph !== null) { var hf = pj.ph >= 0.5; parts.push(esc(hf ? m.home : m.away) + " to win, " + Math.round((hf ? pj.ph : 1 - pj.ph) * 100) + "%"); }
    return "<b>Forecast</b> · " + parts.join(" · ") + ". <span class=\"dim\">What the sheet expects, betting aside; the record below keeps how close it lands against the market's line and the favourite.</span>";
  }
  /* the forecast's record for one sport: the projected total against the final
     and against the market's line, the winner against the favourite, the
     period projection against its line. Rows logged before the forecast line
     are re-scored from their inputs with today's engine and say so. */
  function backfillProj() {
    var changed = false;
    card.forEach(function (r) {
      if (r.proj || !r.inputs) return;
      var m = scoreMatchup(r.sport, r.inputs), pj = m ? projOf(m) : null;
      r.proj = pj || { t: null, h: null, a: null, q: null, ph: null }; r.proj.re = true; changed = true;
    });
    if (changed) save();
  }
  function forecastStats(sp) {
    var s = { n: 0, mae: 0, mkt: 0, closer: 0, tie: 0, bias: 0, mbias: 0, nW: 0, w: 0, nF: 0, fav: 0, nQ: 0, qmae: 0, qmkt: 0, re: 0 };
    card.forEach(function (r) {
      if (r.sport !== sp || !r.proj || r.proj.t === null || !hasFinals(r.finals)) return;
      var fa = parseFloat(r.finals.fa), fh = parseFloat(r.finals.fh), line = numOf(r.inputs.line);
      if (!isFinite(fa) || !isFinite(fh) || line === null) return;
      var tot = fa + fh, e = Math.abs(r.proj.t - tot), em = Math.abs(line - tot);
      s.n++; s.mae += e; s.mkt += em; s.bias += r.proj.t - tot; s.mbias += line - tot;
      if (e < em - 1e-9) s.closer++; else if (Math.abs(e - em) <= 1e-9) s.tie++;
      if (r.proj.re) s.re++;
      if (r.proj.h !== null && r.proj.a !== null && fh !== fa) { s.nW++; if ((r.proj.h > r.proj.a) === (fh > fa)) s.w++; }
      var hml = numOf(r.inputs.hml), aml = numOf(r.inputs.aml);
      if (hml !== null && aml !== null && hml !== aml && fh !== fa) { s.nF++; if ((hml < aml) === (fh > fa)) s.fav++; }
      var qa = parseFloat(r.finals.f5a), qh = parseFloat(r.finals.f5h), qline = numOf(sp === "NHL" ? r.inputs.p1line : r.inputs.f5line);
      if (r.proj.q !== null && isFinite(qa) && isFinite(qh) && qline !== null) { s.nQ++; s.qmae += Math.abs(r.proj.q - (qa + qh)); s.qmkt += Math.abs(qline - (qa + qh)); }
    });
    return s;
  }
  function forecastBlock(sp) {
    var s = forecastStats(sp); if (!s.n) return "";
    var unit = sp === "WNBA" ? "points" : sp === "NHL" ? "goals" : "runs", dp = sp === "WNBA" ? 1 : 2;
    /* colour for recognition (14 Oct 2026): the sheet's figure goes green when it beats the market's, red when it trails it */
    var tone = function (good, bad, text) { return good ? '<span class="up">' + text + '</span>' : bad ? '<span class="down">' + text + '</span>' : text; };
    var further = s.n - s.closer - s.tie;
    var t = '<b>Forecast</b> · ' + s.n + ' graded game' + (s.n === 1 ? '' : 's') + ': the projected total lands ' + tone(s.mae < s.mkt - 1e-9, s.mae > s.mkt + 1e-9, (s.mae / s.n).toFixed(dp) + ' ' + unit) +
      ' from the final on average, the market\'s line ' + (s.mkt / s.n).toFixed(dp) + '; closer than the line in ' + tone(s.closer > further, s.closer < further, String(s.closer)) + ', further in ' + further + (s.tie ? ', even in ' + s.tie : '') +
      '; the projection runs ' + sgn(s.bias / s.n, dp) + ' against the final, the line ' + sgn(s.mbias / s.n, dp) + '.';
    if (s.nW) {
      var wr = s.w / s.nW, fr = s.nF ? s.fav / s.nF : null;
      t += ' Winner called ' + tone(fr !== null && wr > fr + 1e-9, fr !== null && wr < fr - 1e-9, s.w + ' of ' + s.nW + ' (' + Math.round(100 * wr) + '%)') + (s.nF ? ', the favourite ' + s.fav + ' of ' + s.nF + ' (' + Math.round(100 * fr) + '%)' : '') + '.';
    }
    if (s.nQ) t += ' ' + (sp === "NHL" ? 'First period' : 'First five') + ' projected ' + tone(s.qmae < s.qmkt - 1e-9, s.qmae > s.qmkt + 1e-9, (s.qmae / s.nQ).toFixed(dp)) + ' from the score, the line ' + (s.qmkt / s.nQ).toFixed(dp) + '.';
    if (s.re) t += ' <span class="dim">' + s.re + ' row' + (s.re === 1 ? '' : 's') + ' re-scored with today\'s engine (logged before the forecast line).</span>';
    return '<div class="verdict forecast" data-sport="' + sp + '">' + t + '</div>';
  }
  function render() {
    var m;
    try { m = sport === "WNBA" ? forecastMatchupWnba() : forecastMatchupMlb(); }
    catch (e) { m = null; }
    last = m;
    var box = $("markets"), why = $("why");
    if (!m) { box.innerHTML = '<div class="empty">Enter a total to start. Add both moneyline prices for the sides.</div>'; why.innerHTML = ""; return; }
    /* The rail ranks by EDGE, always: the toggle on the day board orders the
       table, not this list. Probability stays the big number on every row. */
    var byProb = false;
    $("rankTag").textContent = "the pick, then the rest by edge";
    var ranked = rankMarkets(m.markets, false), html = "", rows = "";
    var railMarks = markChips(marksOf(sport, snapshot(), m.markets), "cap tagm");
    var gradedRow = openedFinals(), fin = gradedRow ? gradedRow.finals : null;
    if (gradedRow) {
      var w = 0, l = 0, pu = 0;
      ranked.forEach(function (mk) { var r = gradeMarket(mk, fin); if (r === "win") w++; else if (r === "loss") l++; else if (r === "push") pu++; });
      var f5 = (fin.f5a !== undefined && fin.f5a !== "" && fin.f5h !== undefined && fin.f5h !== "")
        ? ' · after five ' + esc(fin.f5a) + '–' + esc(fin.f5h) : '';
      html += '<div class="final"><b>Final: ' + esc(m.away) + ' ' + esc(fin.fa || "?") + ', ' + esc(m.home) + ' ' + esc(fin.fh || "?") + '</b>' + f5 +
        ' · this card went <b>' + w + '-' + l + (pu ? '-' + pu : '') + '</b>.' +
        (formLocked ? ' <b>Locked</b> — a graded row is a record. Press Clear to start a new card.' : ' Edit anything and the grading clears.') + '</div>';
    }
    var fl = $("forecastLine");
    if (fl) { var ft = forecastText(m, sport); fl.innerHTML = ft; fl.hidden = !ft; }
    /* The parlay leg for this game -- gameLeg(): Call Sheet #1's BET on the
       total when it clears its price, else the best value side at any price,
       and nothing when no side clears its price. The leg can sit on the side
       opposite the one this list shows (the list shows the better price), so
       the mark names its pick. */
    var leg = gameLeg(m.markets, sport).leg;
    /* the call (11-12 Oct): the hockey total's likelier side, named on the total's row whatever the band says */
    var callView = sport === "NHL" ? callOf({ sport: "NHL", gdate: ($("gdate") || {}).value || "" }, m.markets.filter(function (k) { return k.key === "total"; })[0]) : null;
    /* 11-12 Oct, at the user's request: a hockey matchup's list is the full-game
       total alone, over or under; the other three markets stay scored and on the
       row. From 13 Oct the hockey rail shows the pick like every other sport. */
    if (callView) { ranked = ranked.filter(function (mk) { return mk.key === "total"; }); $("rankTag").textContent = "the total only, " + NHL_TOTAL_ONLY_LABEL; }
    ranked.forEach(function (mk, i) {
      var shade = shadeOf(mk), shadeRec = shade ? shadeRecord() : null;
      var top = i === 0 && mk.edge !== null && mk.edge > 0;
      var isLeg = leg && mk.key === leg.key;
      var res = fin ? gradeMarket(mk, fin) : null;
      var eCls = mk.edge === null ? "" : (mk.edge > 0 ? "pos" : "neg");
      rows += '<div class="mk' + (top ? " top" : "") + (isLeg ? " alt" : "") + (mk.edge !== null && mk.edge <= 0 ? " neg" : "") +
        (res ? " " + res : "") + '" data-key="' + mk.key + '"' + (res ? ' data-result="' + res + '"' : '') + '>' +
        '<div class="rk">' + (i + 1) + '</div>' +
        '<div><div class="pick ' + sideClass(mk.side) + '">' + esc(mk.pick) +
          (mk.band ? '<span class="band' + (mk.band === "NO BET" ? "" : " hot") + '">' + esc(mk.band) + '</span>' : "") +
          (!mk.anchored ? '<span class="derived">derived</span>' : "") +
          (mk.key === "total" ? railMarks : "") +
          (mk.key === "total" && callView ? '<span class="cap" style="color:var(--go);border-color:var(--go)" title="11-12 Oct: every hockey total got a side, over or under, at the user\'s request">the call: ' + esc(callView.pick) + ' ' + (callView.p * 100).toFixed(1) + '%</span>' : "") +
          (!pickable(mk, sport) ? '<span class="cap tagm" title="' + esc(notPickedWhy(sport, mk)) + '">shown, not picked</span>' : "") +
          (shade ? '<span class="cap" style="color:var(--go);border-color:var(--go)" title="The side the book priced cheaper. The book shades its price toward the side it wants money on, so this is betting with the book against the crowd: a rule, not a probability, kept on its own record line.">book\'s cheaper side: ' + esc(shade.pick) + ' at ' + sgn(shade.price, 0) + ' · ' + recText(shadeRec) + ' on the record</span>' : "") +
          (function () { var best = bestPriceOf(mk, txt("odds")); if (!best || mk.price === null || implied(best.price) >= implied(mk.price) - 1e-9) return ""; return '<span class="cap" style="color:var(--go);border-color:var(--go)" title="The best price on this side at the same number across the books in the odds file, and the edge there">best ' + sgn(best.price, 0) + ' at ' + esc(bookName(best.book)) + ' · edge there ' + sgn((mk.p - implied(best.price)) * 100, 1) + '</span>'; })() +
          shopChips(mk, m) +
          (isLeg ? '<span class="cap" style="color:var(--go);border-color:var(--go)">parlay leg: ' + esc(leg.pick) + ' ' + (leg.p * 100).toFixed(1) + '% at ' + sgn(leg.price, 0) + ' · ' + valueRatio(leg).toFixed(3) + '× its price' + (bandOf(leg) ? ' · #1 says ' + esc(bandOf(leg)) : '') + '</span>' : "") +
          (res ? '<span class="chip ' + res + '" style="margin-left:8px;vertical-align:2px">' + resText(res) + '</span>' : "") + '</div>' +
          '<div class="lab">' + esc(mk.label) + '</div></div>' +
        '<div class="nums"><div class="p">' + (mk.p * 100).toFixed(1) + '%</div>' +
          '<div class="e ' + eCls + '">' + (mk.edge === null ? "no price" :
            "edge " + sgn(mk.edge * 100, 1) + " · " + sgn(mk.price, 0) + " needs " + (mk.breakeven * 100).toFixed(1) + "%") + '</div>' +
          '<div class="e">fair ' + sgn(mk.fair, 0) + (mk.pPush > 0.005 ? ' · push ' + (mk.pPush * 100).toFixed(1) + '%' : '') + '</div></div>' +
        '</div>' +
        '<div class="mkdetail"><span class="other">Other side: ' + esc(mk.other.pick) + ' ' + (mk.other.p * 100).toFixed(1) + '%' +
          (mk.other.edge !== null ? ' at ' + sgn(mk.other.price, 0) + ', edge ' + sgn(mk.other.edge * 100, 1) : '') + '.</span> ' +
          mk.notes.map(function (n) { return n; }).join(" ") + '</div>';
    });
    /* THE PICK above, the rest folded under it (12 Oct 2026, at the user's
       request). In the hockey window the call row is the list, as before. */
    var pk = callView ? null : thePick(m.markets, sport, ($("gdate") || {}).value || "");
    if (pk) {
      if (pk.none) $("rankTag").textContent = "no pick yet";
      html += pickBlock(pk, m, sport) +
        '<details class="others"' + (pk.none ? ' open' : '') + '><summary>' + (pk.none ? 'the markets, by edge' : 'the other markets, listed and graded, by edge') + '</summary>' + rows + '</details>';
    } else html += rows;
    if (m.lamHome !== null) {
      var t = m.lamHome + m.lamAway, ha = m.lamAway / t * 100;
      html += '<div class="split"><i class="a" style="width:' + ha.toFixed(1) + '%">' + esc(m.away) + ' ' + m.lamAway.toFixed(sport === "WNBA" ? 1 : 2) + '</i>' +
              '<i class="h" style="width:' + (100 - ha).toFixed(1) + '%">' + m.lamHome.toFixed(sport === "WNBA" ? 1 : 2) + ' ' + esc(m.home) + '</i></div>';
    }
    box.innerHTML = html;
    why.innerHTML = m.notes.concat(m.total.notes).concat(lastFiveNote()).concat(shopNotes(m)).map(function (n) { return "<li>" + n + "</li>"; }).join("");
  }
  /* The last five starts ride along on the row and the rail but touch no
     number. The line names them so a reader knows they were seen. */
  function lastFiveNote() {
    if (sport !== "MLB") return [];
    var a = $("al5era").value, h = $("hl5era").value, ai = $("al5ip").value, hi = $("hl5ip").value;
    if (a === "" && h === "") return [];
    var part = function (nm, era, ip) { return era === "" ? esc(nm) + " —" : esc(nm) + " " + esc(era) + (ip !== "" ? " in " + esc(ip) + " IP" : ""); };
    return ["<b>Last five starts, shown, not scored:</b> " + part($("away").value || "away", a, ai) + "; " + part($("home").value || "home", h, hi) +
            ". Recorded so recent form can be tested against the record; the season line is what the first five scores."];
  }

  /* ---- the day board ------------------------------------------------------- */
  /* One leg per game, in two tiers. First: Call Sheet #1's verdict -- a
     full-game total #1 calls BET, STRONG BET or MAX BET, on #1's side, when
     that side also clears its price. The verdict is the one mark on the board
     that carries #1's corroboration gate, and the user asked for these legs
     by name on 25 Sept ("the ones saying bet or strong bet"). Second, on a
     game with no such total: the side, of any priced market, with the best
     chance-to-breakeven ratio. In both tiers only a side whose ratio clears
     one qualifies: a parlay's return is the product over its legs of (chance
     / what the price needs), the boost multiplies the whole thing, and a leg
     priced above its chance drags it down however often it hits. Fewer than
     four games qualifying means fewer legs, and the card says so. Across
     games the verdict legs rank first, then by ratio. Over the two nights
     logged, #1's verdict totals went 6-3 and this rule's legs 5-3 against
     4-3-1 for value ratio alone -- not evidence, but not against it either;
     the record tile keeps score. The value tier came first, on 24 Sept, from
     White Sox @ Royals: over 8.5 at -120 (55.3%, ratio 1.014, #1: BET)
     against Royals +1.5 at -155 (61.3%, ratio 1.008) -- the likelier leg was
     the worse one, 9-1 White Sox.
     There is no price cap. The board carried one (-170, set on the board)
     from 24 Sept to 1 Oct, when the user asked for it to go: a side priced
     steeper than -170 that still clears its price is a leg on the same terms
     as any other, and the ratio test already refuses the side that does not.
     Pickable markets are totals and first fives, so the steep moneyline the
     cap was written against never reaches this rule anyway. */
  var TIERS = { "MAX BET": 3, "STRONG BET": 2, "BET": 1 };
  /* Call Sheet #1's verdict on a side: the full-game total only, and only on
     #1's side. Rows logged before band1/side1 were stored carry the band on
     the stored pick alone, and bothSides() gives the flipped side no band. */
  function bandOf(v) {
    if (v.key !== "total") return "";
    var b = v.side1 ? (v.side === v.side1 ? (v.band1 || "") : "") : (v.band || "");
    return b === "NO BET" ? "" : b;   // NO BET is the absence of a verdict, not one
  }
  function bandTier(v) { return TIERS[bandOf(v)] || 0; }
  function valueRatio(mk) { return mk.price === null || mk.price === undefined ? 0 : mk.p / implied(mk.price); }
  function betterLeg(b, v) {
    var tb = bandTier(b) > 0, tv = bandTier(v) > 0;
    if (tb !== tv) return tv ? v : b;
    var rb = valueRatio(b), rv = valueRatio(v);
    return (rv > rb + 1e-12 || (Math.abs(rv - rb) <= 1e-12 && v.p > b.p)) ? v : b;
  }
  /* One game's leg, with what it passed over: the likeliest priced side and,
     for a verdict leg, the richer-priced side. `priced` says whether anything
     pickable had a price at all, so a game whose sides are all priced above
     their chance counts as passed over, not as unpriced. */
  function gameLeg(markets, sp, gdate) {
    var priced = [], clears = [];
    (markets || []).forEach(function (mk) {
      if (!pickable(mk, sp, gdate)) return;   // a market shown, not picked, is never a leg
      bothSides(mk).forEach(function (v) {
        if (v.price === null || v.price === undefined) return;
        priced.push(v);
        if (valueRatio(v) > 1) clears.push(v);
      });
    });
    if (!clears.length) return { leg: null, priced: priced.length > 0, likeliest: null, richer: null };
    var leg = clears.reduce(betterLeg);
    var likeliest = priced.reduce(function (b, v) { return v.p > b.p ? v : b; });
    var richer = clears.reduce(function (b, v) { return valueRatio(v) > valueRatio(b) ? v : b; });
    return { leg: leg, priced: true,
             likeliest: likeliest.pick !== leg.pick ? likeliest : null,
             richer: richer.pick !== leg.pick ? richer : null };
  }
  function bothSides(mk) {
    var o = mk.other;
    if (!o) return [mk];
    return [mk, { key: mk.key, label: mk.label, pick: o.pick, side: FLIP[mk.side] || mk.side, p: o.p, pPush: mk.pPush,
                  price: o.price === undefined ? null : o.price, edge: o.edge === undefined ? null : o.edge,
                  fair: priceFor(o.p), anchored: mk.anchored, band: "", band1: mk.band1, side1: mk.side1, notes: mk.notes,
                  other: { pick: mk.pick, p: mk.p, price: mk.price, edge: mk.edge } }];
  }
  /* THE CALL (12-13 Oct 2026, at the user's request): on those two days every
     hockey total gets a side, over or under, no NO BET -- the side the sheet
     thinks likelier, whatever the price says. A view of that side, or null
     when the row is not a hockey total in the window. It lists in the
     straight bets as its own tier and the total tile keeps its record. */
  function callOf(row, mk) {
    if (!row || row.sport !== "NHL" || !mk || mk.key !== "total" || NHL_TOTAL_ONLY.indexOf(row.gdate || "") < 0) return null;
    var vs = bothSides(mk).slice().sort(function (a, b) { return b.p - a.p; });
    return vs.length ? vs[0] : null;
  }
  /* ---- the shop (12 Oct 2026) ------------------------------------------------
     The odds file writes every book's price on each side into the hidden
     `odds` box as JSON: {total: {OVER: [[book, price, point], ...], UNDER: ...},
     ml: {HOME, AWAY}, spread: {HOME, AWAY}, period: {OVER, UNDER}}. The rail
     names the best price on the listed side at the same number, and the edge
     there, so a -135 that is -118 somewhere else is seen before the bet. */
  var BOOK_NAMES = { fanatics: "Fanatics", betmgm: "BetMGM", draftkings: "DraftKings", fanduel: "FanDuel", caesars: "Caesars", espnbet: "ESPN BET", betrivers: "BetRivers", bovada: "Bovada", williamhill_us: "Caesars", pointsbetus: "PointsBet", pinnacle: "Pinnacle" };
  function bookName(k) { return BOOK_NAMES[k] || String(k || ""); }
  function shopKey(mk) {
    if (mk.key === "total") return "total";
    if (mk.key === "ml") return "ml";
    if (mk.key === "spread" || mk.key === "pl" || mk.key === "rl") return "spread";
    if (mk.key === "f5" || mk.key === "p1" || mk.key === "h1") return "period";
    return null;
  }
  function bestPriceOf(mk, raw) {
    var sk = shopKey(mk); if (!sk || !raw) return null;
    var shop = null; try { shop = JSON.parse(raw); } catch (e) { return null; }
    var list = shop && shop[sk] && shop[sk][mk.side]; if (!list || !list.length) return null;
    var line = mk.key === "ml" ? null : Math.abs(lineOf(mk)), best = null;
    list.forEach(function (x) {
      var price = +x[1], point = x[2] === null || x[2] === undefined ? null : Math.abs(+x[2]);
      if (!isFinite(price)) return;
      if (line !== null && point !== null && Math.abs(point - line) > 1e-9) return;   // the same number only
      if (!best || implied(price) < implied(best.price)) best = { book: x[0], price: price };
    });
    return best;
  }
  /* The rest of the odds file (13 Oct 2026, "make sure we aren't leaving
     anything on the table"): the SHARP book's number beside the carded one
     (the hidden `sharp` box: {book, line, op, up, hml, aml}), the ALTERNATE
     totals priced by the sheet's own projection (splitFor() on the row's
     projected total, so the under at 6.5 and the over at 5.5 are seen with
     their edge while the Line box stays on the book's main number), and the
     book's SPLIT of the total between the sides (team totals). All three are
     shown, not scored: the row still ranks the main number; the chips say
     where the same lean is priced better or worse. */
  function shopOf(raw) { if (!raw) return null; try { return JSON.parse(raw); } catch (e) { return null; } }
  function sharpOf(raw) { var s = shopOf(raw); return s && s.line !== undefined && s.line !== null && isFinite(+s.line) ? s : null; }
  /* Pinnacle's SHADE (13 Oct 2026, measured on the 2025-26 history pull):
     the side the sharp book prices shorter, by the gap between its two
     prices in POINTS of implied chance (-125/+105 is 6.8 points; cents
     mislead across even). At the best retail price at the same number that
     side went 650-534-59 (54.9%, +2.5% a bet) over 1,243 closes, flat under
     two points, and 372-289-32 (56.3%, +3.8% a bet) over the 693 with a
     shade of three points or more; at the opener a shade of 2+ went 54.9%
     on 172. A rule with its own record line, like the WNBA's cheaper side:
     it moves no number until the record here says what the history said. */
  var SHARP_SHADE_PTS = 3;
  function sharpShadeOf(raw) {
    var s = sharpOf(raw); if (!s || s.op === undefined || s.up === undefined || !isFinite(+s.op) || !isFinite(+s.up)) return null;
    var pts = 100 * Math.abs(implied(+s.op) - implied(+s.up));
    if (pts < SHARP_SHADE_PTS) return null;
    return { side: +s.op < +s.up ? "OVER" : "UNDER", pts: pts };
  }
  function altLines(m, raw) {
    var shop = shopOf(raw), f = m && m.total;
    if (!shop || !shop.alt || !f || f.projected === undefined || f.line === undefined || f.line === null) return [];
    var main = +f.line, out = {};
    ["OVER", "UNDER"].forEach(function (side) {
      (shop.alt[side] || []).concat((shop.total || {})[side] || []).forEach(function (x) {
        var price = +x[1], point = x[2] === null || x[2] === undefined ? null : +x[2];
        if (!isFinite(price) || point === null || !isFinite(point) || Math.abs(point - main) < 1e-9) return;   // the main number is the row itself
        var k = side + "@" + point, cur = out[k];
        if (!cur || implied(price) < implied(cur.price)) out[k] = { side: side, point: point, price: price, book: x[0] };
      });
    });
    return Object.keys(out).map(function (k) {
      var a = out[k], sp = splitFor(sport, a.point, f.projected), live = sp[0] + sp[2];
      a.p = live > 0 ? (a.side === "OVER" ? sp[0] : sp[2]) / live : 0.5;
      a.edge = a.p - implied(a.price); a.dist = Math.abs(a.point - main);
      return a;
    }).sort(function (x, y) { return x.dist - y.dist || x.point - y.point; });
  }
  function splitOf(raw) {
    var shop = shopOf(raw), t = shop && shop.team; if (!t) return null;
    /* the books post different team-total numbers (13 Oct 2026: Fanatics 3.5 at +135, FanDuel
       2.5 at -172, BetMGM 3.0 at -118 on one side of one game); the main one is the most
       evenly priced pair, the carded book on a tie, a lone over as the last resort */
    var pick = function (side) {
      var over = (t[side] || {}).OVER || [], under = (t[side] || {}).UNDER || []; if (!over.length) return null;
      var best = null;
      over.forEach(function (o) {
        var u = under.filter(function (x) { return x[0] === o[0] && Math.abs(+x[2] - +o[2]) < 1e-9; })[0];
        var cand = { book: o[0], price: +o[1], point: +o[2], gap: u ? Math.abs(implied(+o[1]) - implied(+u[1])) : 1, carded: o[0] === shop.book ? 0 : 1 };
        if (!best || cand.gap < best.gap - 1e-9 || (Math.abs(cand.gap - best.gap) <= 1e-9 && cand.carded < best.carded)) best = cand;
      });
      return best;
    };
    var a = pick("AWAY"), h = pick("HOME");
    return a || h ? { away: a, home: h } : null;
  }
  function shopChips(mk, m) {
    if (mk.key !== "total" || !m || !m.total) return "";
    var out = "", line = lineOf(mk), sh = sharpOf(txt("sharp"));
    if (sh) {
      var off = line !== null && Math.abs(+sh.line - line) > 1e-9;
      out += '<span class="cap' + (off ? '' : ' tagm') + '"' + (off ? ' style="color:var(--go);border-color:var(--go)"' : '') +
        ' title="Pinnacle, the sharp book, read beside the carded line. Shown, not scored: the odds log keeps the gap nightly and it is measured before it can move a number.">' +
        (off ? 'sharp line ' + esc(String(sh.line)) + ' (' + sgn(+sh.op, 0) + '/' + sgn(+sh.up, 0) + '), here ' + esc(String(line))
             : 'Pinnacle agrees at ' + esc(String(sh.line)) + ' (' + sgn(+sh.op, 0) + '/' + sgn(+sh.up, 0) + ')') + '</span>';
      var ss = sharpShadeOf(txt("sharp"));
      if (ss) out += '<span class="cap" style="color:var(--go);border-color:var(--go)" title="The side Pinnacle prices shorter, by three points of implied chance or more. Measured on the 2025-26 history: at the best retail price at the same number it went 56.3% (+3.8% a bet) over 693 closes, and 54.9% at the opener. A rule with its own record line on the total tile; it moves no number.">Pinnacle shades ' + esc(ss.side) + ' by ' + ss.pts.toFixed(1) + ' points</span>';
    }
    altLines(m, txt("odds")).filter(function (a) { return a.side === mk.side; }).slice(0, 2).forEach(function (a) {
      out += '<span class="cap' + (a.edge > 0 ? '' : ' tagm') + '"' + (a.edge > 0 ? ' style="color:var(--go);border-color:var(--go)"' : '') +
        ' title="An alternate number at the book, priced by the sheet\'s own projection of ' + m.total.projected.toFixed(2) + '. Shown, not picked: the row ranks the main number; this says where the same lean is priced better or worse.">alt ' +
        esc(a.side) + ' ' + esc(String(a.point)) + ' ' + sgn(a.price, 0) + ' at ' + esc(bookName(a.book)) + ' · sheet ' + (a.p * 100).toFixed(1) + '% · edge ' + sgn(a.edge * 100, 1) + '</span>';
    });
    var sp = splitOf(txt("odds"));
    if (sp) {
      var part = function (nm, x) { return x ? esc(nm) + ' ' + esc(String(x.point)) + ' (o ' + sgn(x.price, 0) + ')' : esc(nm) + ' —'; };
      out += '<span class="cap tagm" title="The book\'s own total for each side (team totals), shown, not scored. The sheet\'s own split is the bar under the list.">book\'s split: ' + part(m.away, sp.away) + ' · ' + part(m.home, sp.home) + '</span>';
    }
    return out;
  }
  function shopNotes(m) {
    if (!m || !m.total || m.total.line === undefined || m.total.line === null) return [];
    var notes = [], line = +m.total.line, sh = sharpOf(txt("sharp"));
    if (sh) {
      var off = Math.abs(+sh.line - line) > 1e-9;
      notes.push("<b>Pinnacle, the sharp book:</b> " + esc(String(sh.line)) + " (" + sgn(+sh.op, 0) + "/" + sgn(+sh.up, 0) + ")" +
        (sh.hml !== undefined && sh.aml !== undefined ? ", moneyline " + sgn(+sh.aml, 0) + "/" + sgn(+sh.hml, 0) : "") +
        (off ? ", <b>" + (+sh.line > line ? "above" : "below") + " the carded " + line + "</b>" : ", the same number as the card") +
        ". Shown, not scored: the odds log keeps the gap nightly and it is measured before it can move a number." +
        (function () { var ss = sharpShadeOf(txt("sharp")); return ss ? " <b>It shades the " + ss.side.toLowerCase() + " by " + ss.pts.toFixed(1) + " points</b>: on the 2025-26 history that side went 56.3% at the best retail price over 693 closes with a shade of three points or more (+3.8% a bet), and 54.9% at the opener. A rule with its own record line on the total tile, not a weight." : ""; })());
    }
    var alts = altLines(m, txt("odds")), side = m.total.side, mine = alts.filter(function (a) { return a.side === side; });
    if (mine.length) {
      notes.push("<b>Alternates on the " + esc(String(side).toLowerCase()) + ", priced by the sheet's projection of " + m.total.projected.toFixed(2) + ", shown, not picked:</b> " +
        mine.map(function (a) { return esc(String(a.point)) + " at " + sgn(a.price, 0) + " (" + esc(bookName(a.book)) + ") " + (a.p * 100).toFixed(1) + "%, edge " + sgn(a.edge * 100, 1); }).join("; ") +
        ". The Line box stays on the book's main number; an alternate is shopped here, not typed there.");
    }
    var sp = splitOf(txt("odds"));
    if (sp) {
      var part = function (nm, x) { return x ? esc(nm) + " " + x.point + " (over " + sgn(x.price, 0) + ")" : esc(nm) + " —"; };
      notes.push("<b>The book's split, shown, not scored:</b> " + part(m.away, sp.away) + ", " + part(m.home, sp.home) + ".");
    }
    return notes;
  }
  /* why the sheet likes this one most: the row re-scored from its inputs, each
     scored input's lean against the market's own fair number, and every delta
     on the line, in one sentence a reader can argue with. */
  /* the lean of the full-game total as a list a reader can argue with: the
     market's own fair number against the line, each scored estimate's lean at
     its weight, every delta, and the trend note. Shared by the call's why and
     the pick's why. */
  function totalLean(f, line) {
    var mkt = (f.estimates || []).filter(function (e) { return e.name === "Market"; })[0];
    if (!mkt || line === null || line === undefined) return null;
    var parts = ["the market's own fair number is " + mkt.total.toFixed(2) + " against the " + line + " line" +
      (mkt.total > line + 0.05 ? " (the over is the juiced side)" : mkt.total < line - 0.05 ? " (the under is the juiced side)" : "")];
    (f.estimates || []).forEach(function (e) {
      if (e.name === "Market" || e.scored === false) return;
      parts.push(e.name.toLowerCase() + " " + sgn(e.total - mkt.total, 2) + " at weight " + e.weight + (e.mechanism === false ? " (tagged)" : ""));
    });
    (f.deltas || []).forEach(function (d) { parts.push(d.name.toLowerCase() + " " + sgn(d.runs, 2) + " on the line" + (d.mechanism === false ? " (tagged)" : "")); });
    var trend = (f.notes || []).filter(function (n) { return /^Last five:/.test(String(n)); })[0] || "";
    return { parts: parts, trend: trend ? String(trend).replace(/\.?\s*Shown, not scored.*$/, '.') : "" };
  }
  function callWhy(x) {
    var m = scoreMatchup(x.row.sport, x.row.inputs); if (!m || !m.total) return "";
    var f = m.total, line = numOf(x.row.inputs.line), lean = totalLean(f, line);
    if (!lean) return "";
    var side = x.mk.side === "OVER" ? "over" : "under";
    return '<div class="swap why"><b>' + (x.fav ? "Why the sheet likes this one most tonight" : "Why this side") + '</b>: projected ' + f.projected.toFixed(2) + ' against ' + line + ', so the ' + side + ' at ' +
      (x.mk.p * 100).toFixed(1) + '%' + (x.fav ? ', the strongest lean among tonight\'s hockey totals' : '') + '. Behind it: ' + lean.parts.join("; ") + '.' +
      (lean.trend ? ' ' + lean.trend : '') +
      (x.mk.price !== null ? (x.mk.edge > 0 ? ' The price agrees.' : ' The price asks more than that chance, so this is the sheet\'s pick, not a bet.') : '') + '</div>';
  }
  /* THE PICK (12 Oct 2026, at the user's request: "pick the best, most likely
     ... this is the pick because of xyz and this is an overs, unders, spread,
     moneyline or upset type of game"). One side per matchup: the LIKELIEST
     side of any market on the board, the chance to hit the only key, a tie
     inside a point breaking toward the better price. Not the edge: a 63% run
     line at -130 outranks a 56% under at -110 here, and the user knows that a
     side the sheet has no team information on (the moneyline and the run or
     puck line in baseball and hockey) is the book's own number read back --
     the why says so when it is. The record tile keeps the pick's own line so
     the approach is measured, not assumed. The other markets stay scored and
     graded, folded under the pick. Below PICK_MIN nothing separates the
     sides and the block says so instead of naming a coin flip. */
  /* Later the same night, at the user's word ("I don't want it to pick solely
     because it looks the best ... we have plenty of data ... make sure this
     is the focus"): the pick is the likeliest side AMONG THE MARKETS THE
     SHEET'S INPUTS INFORM (pickable: the total and the period in baseball
     and hockey, the sides in the WNBA when the ratings are on the card), and
     only where those inputs MOVE THE CHANCE OFF THE BOOK'S OWN NUMBER by a
     point or more toward that side. A side the sheet has no information on
     is never the pick, however likely it looks: that would be the book's
     number read back, and the hockey sides were measured that night to be
     exactly that. When nothing on the card moves a number, the block says
     so. The why states the book's number, the sheet's, and the lean. */
  var PICK_MIN = 0.505, PICK_INFO = 0.01;
  function marketChance(mk) {   // the book's own de-vigged chance of the listed side; 0.5 without both prices
    var a = mk.price, b = mk.other ? mk.other.price : null;
    if (a === null || a === undefined || b === null || b === undefined) return 0.5;
    var ia = implied(a), ib = implied(b);
    return ia + ib > 0 ? ia / (ia + ib) : 0.5;
  }
  function thePick(markets, sp, gdate) {
    var views = rankMarkets((markets || []).filter(function (mk) { return pickable(mk, sp, gdate); }), true);
    if (!views.length) return null;
    views.forEach(function (v) { v.pMkt = marketChance(v); v.lean = v.p - v.pMkt; });
    var cands = views.filter(function (v) { return v.p >= PICK_MIN && v.lean >= PICK_INFO; });
    if (!cands.length) {
      var top = views[0], moved = views.filter(function (v) { return Math.abs(v.lean) >= PICK_INFO; });
      var msg = !moved.length
        ? "Nothing on the card moves a number off the book's: on every market the sheet informs, its chance is the book's own (" + esc(top.pick) + " " + (top.p * 100).toFixed(1) + "% here). Type the inputs and a side will show."
        : "The sheet's inputs lean against the side the book favours without reaching the other side: " + esc(top.pick) + " is " + (top.p * 100).toFixed(1) + "% on the sheet against " + (top.pMkt * 100).toFixed(1) + "% at the book. Nothing here to take.";
      return { none: true, mk: top, msg: msg };
    }
    var best = cands[0];
    cands.slice(1).forEach(function (v) { if (Math.abs(v.p - best.p) <= 0.01 && v.lean > best.lean + 1e-9) best = v; });
    return { mk: best, type: gameType(best) };
  }
  function gameType(mk) {
    var k = mk.key;
    if (k === "total" || k === "f5" || k === "p1" || k === "h1") {
      return (mk.side === "OVER" ? "an OVER" : "an UNDER") + " game" + (k === "f5" ? ", first five" : k === "p1" ? ", first period" : k === "h1" ? ", first half" : "");
    }
    if (k === "ml") return (mk.price !== null && mk.price !== undefined && mk.price > 0) ? "an UPSET game" : "a MONEYLINE game";
    if (k === "rl") return "a RUN LINE game";
    if (k === "pl") return "a PUCK LINE game";
    return "a SPREAD game";
  }
  function periodName(k) { return k === "f5" ? "first five" : k === "p1" ? "first period" : "first half"; }
  function pickWhy(pk, m, sp) {
    var mk = pk.mk, dp = sp === "WNBA" ? 1 : 2, unit = sp === "WNBA" ? "points" : sp === "NHL" ? "goals" : "runs", s;
    var price = mk.price !== null && mk.price !== undefined
      ? ' At ' + sgn(mk.price, 0) + ' it needs ' + (mk.breakeven * 100).toFixed(1) + '%: ' + (mk.edge > 0 ? 'the price agrees.' : 'the price asks more than that chance, so this is the likeliest side, not a value bet.')
      : ' No price typed.';
    /* the information behind the pick: the book's own chance, the sheet's, and the lean between them */
    if (mk.pMkt !== undefined && mk.lean !== undefined) {
      var toward = mk.key === "ml" ? esc(mk.side === "HOME" ? m.home : m.away) : (mk.side === "OVER" || mk.side === "UNDER") ? 'the ' + String(mk.side).toLowerCase() : esc(mk.pick);
      price = ' The book\'s own number makes it ' + (mk.pMkt * 100).toFixed(1) + '%; the sheet\'s inputs move it to ' + (mk.p * 100).toFixed(1) + '%, a ' + (mk.lean * 100).toFixed(1) + '-point lean toward ' + toward + '.' + price;
    }
    if (mk.key === "total") {
      var f = m.total, lean = totalLean(f, f.line);
      s = 'Projected ' + f.projected.toFixed(dp) + ' ' + unit + ' against the ' + f.line + ' line, so the ' + String(mk.side).toLowerCase() + ' at ' + (mk.p * 100).toFixed(1) + '%' +
          (lean ? '. Behind it: ' + lean.parts.join('; ') + '.' + (lean.trend ? ' ' + lean.trend : '') : '.');
    } else if (mk.key === "f5" || mk.key === "p1" || mk.key === "h1") {
      s = 'Projected ' + periodName(mk.key) + (m.period !== undefined && m.period !== null && isFinite(+m.period) ? ' ' + (+m.period).toFixed(dp) + ' ' + unit : '') + ' against the ' + lineOf(mk) + ' line, so the ' +
          String(mk.side).toLowerCase() + ' at ' + (mk.p * 100).toFixed(1) + '%. ' + (mk.notes || []).join(' ');
    } else {
      var home = mk.side === "HOME", team = home ? m.home : m.away;
      var split = (m.lamHome !== null && m.lamHome !== undefined && m.lamAway !== null && m.lamAway !== undefined) ? m.lamHome - m.lamAway : null;
      s = esc(mk.key === "ml" ? team + ' to win' : mk.pick) + ' at ' + (mk.p * 100).toFixed(1) + '%' +
          (split !== null ? ': the sheet\'s split projects ' + esc(split >= 0 ? m.home : m.away) + ' by ' + Math.abs(split).toFixed(dp) + ' ' + unit + ' (' + esc(m.away) + ' ' + m.lamAway.toFixed(dp) + ', ' + esc(m.home) + ' ' + m.lamHome.toFixed(dp) + ')' : '') + '.' +
          (sp === "WNBA" && mk.informed ? ' The four ratings move the margin off the book\'s number.'
            : ' The sides carry no team information on this sheet in ' + (sp === "NHL" ? 'hockey (measured 12 Oct 2026 on two seasons: goals, shots, expected goals, form and the goalies added nothing to the moneyline, and the favourite lost four to seven cents on the dollar at the close)' : sp === "MLB" ? 'baseball (the pitchers and the pens score the total, not the margin)' : 'this game') +
              ': this is the book\'s own number read back, and it is the likeliest thing on the board.') +
          ' ' + (mk.notes || []).join(' ');
    }
    return s + price;
  }
  /* the likeliest side on the whole card at ANY price (15 Oct 2026, the user: "if the
     model thinks another market is likelier, that is the type of bet I want it to
     recommend"): named under the pick with its break-even, so a 57% side at a price
     that needs 61% reads as the book's price and not an edge. Both sides of every
     priced market are in the running; the pick is still the likeliest side the sheet
     has moved a point off the book. */
  function likeliestLine(markets, pk) {
    var best = null, bestUnpriced = null;
    (markets || []).forEach(function (mk) {
      [{ pick: mk.pick, p: mk.p, price: mk.price }, mk.other ? { pick: mk.other.pick, p: mk.other.p, price: mk.other.price } : null].forEach(function (c) {
        if (!c || c.p === null || c.p === undefined) return;
        if (c.price !== null && c.price !== undefined) { if (!best || c.p > best.p + 1e-9) best = c; }
        else if (!bestUnpriced || c.p > bestUnpriced.p + 1e-9) bestUnpriced = c;
      });
    });
    best = best || bestUnpriced;   // a side with a price first: the line is about the price
    if (!best) return "";
    var isPick = pk && !pk.none && pk.mk && pk.mk.pick === best.pick;
    var priced = best.price !== null && best.price !== undefined;
    var need = priced ? implied(best.price) : null;
    var verdict = !priced ? "no price typed" : (best.p >= need ? "the price agrees" : "the book's price, not an edge");
    return '<b>Likeliest on the card at any price</b>: ' + esc(best.pick) + ' at ' + (best.p * 100).toFixed(1) + '%' +
      (priced ? ', ' + sgn(best.price, 0) + ' needs ' + (need * 100).toFixed(1) + '%' : '') + ': ' + verdict + (isPick ? ', and it is the pick.' : '.') +
      (!isPick && priced && best.p < need ? ' A high chance at a steep price is the book knowing it, and you paying for it.' : '');
  }
  function pickBlock(pk, m, sp) {
    var mk = pk.mk, also = likeliestLine(m && m.markets, pk);
    var alsoHtml = also ? '<div class="also">' + also + '</div>' : '';
    if (pk.none) return '<div class="pickcard none"><div class="lab">The pick</div><div class="pick">No pick yet</div>' +
      '<div class="why">' + (pk.msg || ('Nothing on the card separates the sides: ' + esc(mk.pick) + ' at ' + (mk.p * 100).toFixed(1) + '% is a coin flip. Type the inputs and a side will show.')) + '</div>' + alsoHtml + '</div>';
    return '<div class="pickcard" data-key="' + esc(mk.key) + '" data-side="' + esc(mk.side) + '">' +
      '<div class="lab">The pick · ' + esc(pk.type) + '</div>' +
      '<div class="head"><div class="pick ' + sideClass(mk.side) + '">' + esc(mk.pick) + (mk.band ? '<span class="band' + (mk.band === "NO BET" ? "" : " hot") + '">' + esc(mk.band) + '</span>' : '') + '</div>' +
      '<div class="p">' + (mk.p * 100).toFixed(1) + '%</div></div>' +
      '<div class="why"><b>Why</b>: ' + pickWhy(pk, m, sp) + '</div>' + alsoHtml + '</div>';
  }
  function parlayFour(dateISO, sport) {
    var legs = [], skipped = 0;
    card.forEach(function (r) {
      if ((r.gdate || "") !== dateISO) return;
      if (sport && r.sport !== sport) return;
      var g = gameLeg(r.markets, r.sport, r.gdate);
      if (!g.leg) { if (g.priced) skipped++; return; }
      legs.push({ row: r, mk: g.leg, ratio: valueRatio(g.leg), tier: bandTier(g.leg), band: bandOf(g.leg),
                  likeliest: g.likeliest, richer: g.richer, rank: 0, corr: [] });
    });
    legs.sort(function (a, b) { return ((b.tier > 0) - (a.tier > 0)) || (b.ratio - a.ratio) || (b.mk.p - a.mk.p); });
    legs.forEach(function (l, i) { l.rank = i + 1; });
    var out = legs.slice(0, 4);
    out.skipped = skipped;
    return out;
  }
  /* Straight bets: the stored picks (better price per market), positive edge
     only, best edge first. Same-game rows are flagged, not removed. */
  /* Straight bets, up to eight, in two tiers. First, Call Sheet #1's VERDICT:
     every full-game total #1 calls BET or better on #1's side, best edge
     first -- including one whose price is steeper than its chance, which is
     listed with the green chip and a line saying the price is the problem,
     because the verdict tier has been the sheet's best record (39-23 on #1,
     7-2 here) and a verdict at -125 that won (Guardians @ Royals, 25 Sept,
     over 7, 54.1%, edge -1.5) used to be left off for the edge alone. Second,
     VALUE: every other stored pick with a positive edge, best edge first --
     first fives and run lines, usually. Asked for on 26 Sept: "show the market
     it chose that shows the green BET next to it, and give me up to eight." */
  /* SHOWN, NOT PICKED: the moneyline and the run line (and the WNBA spread).
     They are derived from the book's own moneyline with no team information
     behind them, and on the first 52 graded MLB games the run line said 52.5%
     and did 42.3% (22-30, -10.15u); the picks with a positive edge, the ones
     that reached the straight bets, said 60.6% and did 45.0% (9-11). The
     moneyline is calibrated (42.2% said, 42.3% done) and, being read off its
     own price, never clears it. So neither can be a straight bet or a parlay
     leg from 27 Sept. They stay on the rail, the board and the record, chipped
     "shown, not picked", so the tally keeps running; if the run line reads
     calibrated at 150 picks it comes back. The totals and the first five --
     the two markets the model has inputs for -- are the pickable ones:
     62.7% and 62.5% over the same games.
     The WNBA turned the other way on 2 Oct, at the user's call: its spread
     and moneyline carry the four ratings from that day (see ratingsMargin),
     its totals leaned under by construction and went 6-7 (says 54.8%, does
     46.2%), and the user asked for the book to lean on the sides. So in the
     WNBA the spread and the moneyline are pickable and the total is shown,
     not picked -- still on the rail, the board and the record, so it can
     come back the same way the run line can. The NHL entry is for Call Sheet
     3.0, which is built from this file: the total and the first period. */
  var PICKABLE = { MLB: ["total", "f5"], WNBA: ["spread", "ml"], NHL: ["total", "p1"] };
  /* 12 Oct 2026, at the user's request, for a week with last night as the
     first test: the hockey book picks the FULL-GAME TOTAL only, and every
     hockey total gets a side (callOf). Cut short the same day, once the odds
     feed was in ("scratch the week trial"): the window is the two days whose
     calls were already made, 11 and 12 Oct, so those rows keep grading as
     calls and the tile keeps their record; from 13 Oct the hockey rail shows
     THE PICK (thePick) like every other sport, and the first period picks
     as before. */
  var NHL_TOTAL_ONLY = ["2026-10-11", "2026-10-12"];
  var NHL_TOTAL_ONLY_LABEL = "11-12 Oct";
  function pickable(mk, sp, gdate) {
    if ((PICKABLE[sp] || PICKABLE.MLB).indexOf(mk.key) < 0) return false;
    if (sp === "NHL" && mk.key === "p1") {
      var d = gdate || (($("gdate") || {}).value) || todayISO();
      if (NHL_TOTAL_ONLY.indexOf(d) >= 0) return false;
    }
    /* A WNBA side is picked only when the four ratings were on the card: a
       row stored without them (every row before 2 Oct, or one typed with the
       boxes empty) carries no team information on its sides and keeps the
       chip. Rescore an ungraded row to give it the flag. */
    return sp !== "WNBA" || !!mk.informed;
  }
  function notPickedWhy(sp, mk) {
    if (sp === "WNBA" && mk.key !== "total") return "This side was stored without the four ratings, so it is the book's own price read back and carries no team information. Type the ratings (paste the stats.wnba.com table) and press Rescore, and the spread and the moneyline become pickable.";
    if (sp === "WNBA") return "The WNBA total leaned under by construction and went 6-7 on the first 13 (says 54.8%, does 46.2%); from 2 Oct the WNBA book picks the spread and the moneyline, which carry the ratings, and the total is listed and graded but never a straight bet or a parlay leg.";
    if (sp === "NHL" && mk.key === "p1") return "For games on 11 and 12 Oct the hockey book picked the full-game total only, at the user's request (a week's trial, cut short once the odds feed was in). The first period is listed and graded, never a straight bet or a parlay leg, on those two days.";
    if (sp === "NHL") return "Derived from the book's own moneyline with no team information behind it, like the run line, which said 52.5% and did 42.3% on its first 52. Listed and graded, never a straight bet or a parlay leg, until the record says otherwise.";
    return "Derived from the book's own moneyline with no team information behind it. On the first 52 graded games the run line said 52.5% and did 42.3%, so it is listed and graded but never a straight bet or a parlay leg.";
  }
  /* ---- the book's cheaper side (WNBA spread) --------------------------------
     A RULE, not a probability. On a spread priced -105/-115 the book has
     shaded its price toward the side it wants money on, so taking the
     cheaper side is betting with the book against the crowd. That has a
     mechanism and a modest literature (a point or two over a coin, long
     run), and on this card it went 12-1 on the first thirteen WNBA spreads
     with a shaded price (24 Sept to 1 Oct 2026); the three at -110/-110 are
     not the rule and are not counted. It moves no number: the chip names the
     side, the spread tile keeps its record, and it sits on the straight bets
     as its own tier between #1's verdicts and the value picks, chipped so a
     reader knows which tier they are looking at. Reviewed at 40 picks. */
  var SHADE_MIN_GAP = 10;
  function shadeOf(mk) {
    if (!mk || mk.key !== "spread" || !mk.other) return null;
    var a = mk.price, b = mk.other.price;
    if (a === null || a === undefined || b === null || b === undefined || Math.abs(a - b) < SHADE_MIN_GAP) return null;
    var sides = bothSides(mk);
    return sides[0].price > sides[1].price ? sides[0] : sides[1];
  }
  function shadeRecord() {
    var c = { w: 0, l: 0, p: 0 };
    card.forEach(function (r) {
      if (r.sport !== "WNBA") return;
      (r.markets || []).forEach(function (mk) {
        var s = shadeOf(mk); if (!s) return;
        var res = gradeMarket(s, r.finals); if (res === null || res === "invalid") return;
        if (res === "push") c.p++; else if (res === "win") c.w++; else c.l++;
      });
    });
    return c;
  }
  function recText(c) { return c.w + "-" + c.l + (c.p ? "-" + c.p : ""); }
  function bestBets(dateISO, sport) {
    var all = boardRows(dateISO, false).filter(function (x) { return !sport || x.row.sport === sport; });
    var verdict = all.filter(function (x) { return x.mk.key === "total" && pickable(x.mk, x.row.sport, x.row.gdate) && bandOf(x.mk); });
    var rule = [];
    card.forEach(function (r) {
      if ((r.gdate || "") !== dateISO || r.sport !== "WNBA" || (sport && r.sport !== sport)) return;
      (r.markets || []).forEach(function (mk) { var s = shadeOf(mk); if (s) rule.push({ row: r, mk: s }); });
    });
    var value = all.filter(function (x) {
      return pickable(x.mk, x.row.sport, x.row.gdate) && !(x.mk.key === "total" && bandOf(x.mk)) && x.mk.edge > 0 &&
             !callOf(x.row, x.mk) &&
             !rule.some(function (y) { return y.row.id === x.row.id && y.mk.pick === x.mk.pick; });
    });
    verdict.forEach(function (x) { x.tier = "verdict"; x.thin = x.mk.edge <= 0; });
    /* A verdict whose price is steeper than its chance stays on the list on
       the strength of the MLB record (12-7 on #1's bands). Hockey has no such
       record -- its bands were 3-5 on the first 31 games, every one of them
       a thin over on a league save percentage that read every goalie cold --
       so a hockey verdict lists only when it also clears its price. Asked for
       on 5 Oct: "it gives a bet signal at 53% but doesn't cover". */
    verdict = verdict.filter(function (x) { return !(x.thin && x.row.sport === "NHL"); });
    /* the call: every hockey total in the window that is not a LISTED verdict
       (a hockey verdict dropped for its price becomes a call), on the sheet's
       likelier side, whatever the price */
    var call = [];
    card.forEach(function (r) {
      if ((r.gdate || "") !== dateISO || r.sport !== "NHL" || (sport && r.sport !== sport)) return;
      var tot = (r.markets || []).filter(function (mk) { return mk.key === "total"; })[0], cv = callOf(r, tot);
      if (cv && !verdict.some(function (y) { return y.row.id === r.id; })) call.push({ row: r, mk: cv });
    });
    call.forEach(function (x) { x.tier = "call"; x.thin = x.mk.edge === null || x.mk.edge <= 0; });
    rule.forEach(function (x) { x.tier = "rule"; x.thin = x.mk.edge === null || x.mk.edge <= 0; });
    value.forEach(function (x) { x.tier = "value"; x.thin = false; });
    var rows = verdict.concat(call).concat(rule).concat(value).slice(0, Math.max(8, verdict.length + call.length));
    /* the one it likes most tonight: among the hockey totals in the window
       (verdicts and calls), the strongest lean -- highest chance, then edge.
       Its card gets a colour and a why (callWhy). Asked for 12 Oct. */
    var fav = null;
    rows.forEach(function (x) {
      if (x.row.sport !== "NHL" || x.mk.key !== "total" || !(x.tier === "verdict" || x.tier === "call") || !callOf(x.row, x.mk)) return;
      if (!fav || x.mk.p > fav.mk.p + 1e-9 || (Math.abs(x.mk.p - fav.mk.p) <= 1e-9 && (x.mk.edge || 0) > (fav.mk.edge || 0))) fav = x;
    });
    if (fav) fav.fav = true;
    rows.forEach(function (x, i) {
      x.rank = i + 1;
      x.corr = rows.slice(0, i).filter(function (o) { return o.row.id === x.row.id; }).map(function (o) { return o.rank; });
    });
    return rows;
  }
  function betNote(x) {
    if (x.tier === "verdict" && x.thin) {
      return '<div class="swap">#1 says <b>' + esc(bandOf(x.mk)) + '</b>, but ' + sgn(x.mk.price, 0) + ' needs ' + (implied(x.mk.price) * 100).toFixed(1) +
        '% and the sheet says ' + (x.mk.p * 100).toFixed(1) + '%. The verdict is there; the price is not. Shop it, or size it down.</div>';
    }
    if (x.tier === "rule") {
      var rc = shadeRecord();
      return '<div class="swap">The book\'s <b>cheaper side</b> — a rule, not a probability: <b>' + recText(rc) + '</b> on the record. The sheet says ' +
        (x.mk.p * 100).toFixed(1) + '%' + (x.mk.price !== null ? ' and ' + sgn(x.mk.price, 0) + ' needs ' + (implied(x.mk.price) * 100).toFixed(1) + '%' : '') +
        (x.thin ? '; the rule is carrying this one, not the number.' : '; the number agrees.') + ' Reviewed at 40 picks.</div>';
    }
    if (x.tier === "call") {
      return '<div class="swap"><b>The call</b> — on 11 and 12 Oct every hockey total got a side, at your request: this is the side the sheet thinks likelier, ' +
        (x.mk.p * 100).toFixed(1) + '%' + (x.mk.price !== null ? ', and ' + sgn(x.mk.price, 0) + ' needs ' + (implied(x.mk.price) * 100).toFixed(1) + '%' + (x.thin ? ': the price is steeper than the chance, so this is a call, not a bet.' : ': the price agrees.') : '.') +
        ' The total tile keeps the calls\' own record.</div>';
    }
    if (x.tier === "value") return '<div class="swap">No verdict on this market — it is here on the price alone.</div>';
    return '';
  }
  function boardRows(dateISO, byProb) {
    var rows = [];
    card.forEach(function (r) {
      if ((r.gdate || "") !== dateISO) return;
      (r.markets || []).forEach(function (mk0) {
        var mk = viewOf(mk0, byProb);
        if (mk.edge === null || mk.edge === undefined) return;
        rows.push({ row: r, mk: mk });
      });
    });
    rows.sort(function (a, b) {
      if (byProb) return b.mk.p - a.mk.p;
      return (b.mk.edge - a.mk.edge) || (b.mk.p - a.mk.p);
    });
    rows.forEach(function (x, i) {
      x.rank = i + 1;
      x.corr = rows.slice(0, i).filter(function (o) { return o.row.id === x.row.id; }).map(function (o) { return o.rank; });
    });
    return rows;
  }
  function legNote(x) {
    var s = '';
    if (x.band) {
      s += '<div class="swap">Call Sheet #1 says <b>' + esc(x.band) + '</b> on this total and it clears its price' +
        (x.richer ? ' — ' + esc(x.richer.pick) + ' ' + (x.richer.p * 100).toFixed(1) + '% at ' + sgn(x.richer.price, 0) + ' (' + valueRatio(x.richer).toFixed(3) + '×) is the richer price on this game but carries no verdict' : '') + '.</div>';
    }
    if (x.likeliest) {
      s += '<div class="swap">Likelier on this game: ' + esc(x.likeliest.pick) + ' ' + (x.likeliest.p * 100).toFixed(1) + '% at ' + sgn(x.likeliest.price, 0) +
        ' — but it needs ' + (implied(x.likeliest.price) * 100).toFixed(1) + '%, so this leg is the better value.</div>';
    }
    return s;
  }
  function parlayCard(legs, nRows, wide) {
    if (legs.length >= 2) {
      var pAll = legs.reduce(function (a, x) { return a * x.mk.p; }, 1);
      var rAll = legs.reduce(function (a, x) { return a * x.ratio; }, 1);
      var pushes = legs.filter(function (x) { return x.mk.pPush > 0.005; }).length;
      var verdicts = legs.filter(function (x) { return x.tier > 0; }).length;
      return '<div class="pk parlay" style="' + (wide ? 'grid-column:1/-1;' : '') + 'border-style:dashed"><div class="n1">ALL ' + legs.length + ' HIT</div>' +
        '<div class="n2">' + (pAll * 100).toFixed(1) + '% · fair parlay ' + sgn(priceFor(pAll), 0) + ' (' + (1 / pAll).toFixed(2) + '×) · worth <b>' + rAll.toFixed(2) + '×</b> what the prices say</div>' +
        '<div class="n4">' + (verdicts === legs.length ? 'Every leg' : verdicts === 0 ? 'No leg' : verdicts + ' of the ' + legs.length + ' legs') + (verdicts >= 2 && verdicts < legs.length ? ' carry' : ' carries') + ' Call Sheet #1\'s BET or better' +
        (verdicts < legs.length ? (verdicts ? '; the rest are' : '; these are') + ' the best value side on their game' : '') +
        '. Every leg clears its own price, so the parlay is worth more than the book\'s multiplied odds before any boost' +
        (legs.skipped ? '; ' + legs.skipped + ' game' + (legs.skipped === 1 ? '' : 's') + ' had no side that clears its price' : '') +
        (pushes ? '; ' + pushes + ' can push, which most apps void to a smaller parlay' : '') +
        '. A boosted payout above ' + (1 / pAll).toFixed(2) + '× beats fair outright.</div></div>';
    }
    if (!legs.length && nRows) return '<div class="empty">No leg on this date clears its price. Nothing to parlay tonight.</div>';
    if (legs.length === 1) return '<div class="empty">Only one leg clears its price — not a parlay; it is under best straight bets if the edge is there.</div>';
    return '';
  }
  function pickCard(x, cls, extra) {
    var res = gradeMarket(x.mk, x.row.finals);
    return '<div class="pk ' + cls + (x.fav ? ' fav' : '') + '" data-open="' + x.row.id + '" title="Load ' + esc(x.row.matchup) + ' into the form">' +
      '<div class="n1">#' + x.rank + (x.corr && x.corr.length ? ' · same game as #' + x.corr.join(', #') : '') + (x.fav ? ' · <b>the one it likes most tonight</b>' : '') + '</div>' +
      '<div class="n2">' + esc(x.mk.pick) + (bandOf(x.mk) ? ' <span class="band hot">' + esc(bandOf(x.mk)) + '</span>' : '') +
        (x.fav ? ' <span class="band favb" title="The strongest lean among tonight\'s hockey totals">★ LIKES MOST</span>' : '') +
        (x.tier === "rule" ? ' <span class="band hot" title="The side the book priced cheaper: a rule, not a probability">CHEAPER SIDE</span>' : '') +
        (x.tier === "call" ? ' <span class="band hot" title="11-12 Oct: every hockey total got a side, over or under, at the user\'s request">CALL</span>' : '') + '</div>' +
      '<div class="n3">' + (x.mk.p * 100).toFixed(1) + '% · ' + (x.mk.price !== null ? sgn(x.mk.price, 0) + ' · edge ' + sgn(x.mk.edge * 100, 1) : 'no price') +
        (res ? ' · <span class="chip ' + res + '">' + resText(res) + '</span>' : '') + '</div>' +
      '<div class="n4">' + esc(x.row.matchup) + ' · ' + esc(x.mk.label) +
        (x.mk.key === "total" && marksOf(x.row.sport, x.row.inputs, x.row.markets).grain ? ' <span class="tagm warn">over against the grain</span>' : '') + '</div>' + (extra || '') + (callOf(x.row, x.mk) ? callWhy(x) : '') + '</div>';
  }
  function renderBoard() {
    var dateISO = $("boardDate").value || todayISO(), byProb = !$("byEdge").checked;
    var rows = boardRows(dateISO, byProb);
    $("boardCount").textContent = rows.length ? rows.length + " priced markets on " + gameDate(dateISO) : "nothing logged for " + gameDate(dateISO);

    // --- the parlay four ---
    var legs = parlayFour(dateISO), ph = "";
    legs.forEach(function (x) { ph += pickCard(x, "", legNote(x)); });
    ph += parlayCard(legs, rows.length, true);
    $("picks").innerHTML = ph;

    // --- best straight bets ---
    var bets = bestBets(dateISO), bh = "";
    bets.forEach(function (x) { bh += pickCard(x, "straight" + (x.thin ? " thin" : ""), betNote(x)); });
    if (!bets.length && rows.length) bh = '<div class="empty">No market on this date is priced below its chance. The book has every side covered tonight.</div>';
    $("bestBets").innerHTML = bh;

    // --- by sport: the same two rules, one sport at a time ---
    /* Only when the date has BOTH sports. With one, the columns repeat the
       two lists above word for word, which read as duplicates (29 Sept). */
    var sh = "";
    var sportsOn = ["MLB", "WNBA"].filter(function (sp) { return card.some(function (r) { return (r.gdate || "") === dateISO && r.sport === sp; }); });
    $("bySportHead").hidden = sportsOn.length < 2;
    (sportsOn.length < 2 ? [] : sportsOn).forEach(function (sp) {
      var games = card.filter(function (r) { return (r.gdate || "") === dateISO && r.sport === sp; }).length;
      if (!games) return;
      var sl = parlayFour(dateISO, sp), sb = bestBets(dateISO, sp);
      var col = '<div class="sportcol" data-sport="' + sp + '"><div class="subhead">' + sp + ' <span class="tag">' + games + ' game' + (games === 1 ? '' : 's') + ' logged</span></div>';
      col += '<div class="lbl">Parlay legs</div><div class="picks one">';
      sl.forEach(function (x) { col += pickCard(x, "", legNote(x)); });
      col += parlayCard(sl, games, false);
      col += '</div><div class="lbl">Straight bets</div><div class="picks one">';
      sb.forEach(function (x) { col += pickCard(x, "straight" + (x.thin ? " thin" : ""), betNote(x)); });
      if (!sb.length) col += '<div class="empty">No positive edge in ' + sp + ' tonight.</div>';
      col += '</div></div>';
      sh += col;
    });
    $("bySport").innerHTML = sh;

    if (!rows.length) { $("board").innerHTML = '<div class="empty">Add today\'s matchups to the card and every priced market lands here, best edge first.</div>'; return; }
    var h = '<table><thead><tr><th>#</th><th>Matchup</th><th>Market</th><th>Pick</th><th>Chance</th><th>Price</th><th>Needs</th><th>Edge</th><th>Fair</th><th>Result</th></tr></thead><tbody>';
    rows.forEach(function (x) {
      var mk = x.mk, res = gradeMarket(mk, x.row.finals);
      var inFour = (byProb ? legs : bets).some(function (y) { return y.row.id === x.row.id && y.mk.pick === mk.pick; });
      h += '<tr class="' + (inFour ? 'pick4' : '') + '" data-open="' + x.row.id + '" title="Load ' + esc(x.row.matchup) + ' into the form">' +
        '<td><span class="rank">' + x.rank + '</span>' + (x.corr.length ? '<span class="chip corr">corr #' + x.corr.join(' #') + '</span>' : '') + '</td>' +
        '<td>' + esc(x.row.matchup) + ' <span class="gdate">' + esc(x.row.sport) + '</span></td>' +
        '<td>' + esc(mk.label) + (!mk.anchored ? ' <span class="chip dim">derived</span>' : '') + (!pickable(mk, x.row.sport, x.row.gdate) ? ' <span class="chip dim">not picked</span>' : '') + '</td>' +
        '<td><span class="chip ' + sideClass(mk.side) + '">' + esc(mk.pick) + '</span>' + (mk.band && mk.band !== "NO BET" ? ' <span class="chip">' + esc(mk.band) + '</span>' : '') + '</td>' +
        '<td class="n">' + (mk.p * 100).toFixed(1) + '%</td>' +
        '<td class="n">' + sgn(mk.price, 0) + '</td>' +
        '<td class="n">' + (implied(mk.price) * 100).toFixed(1) + '%</td>' +
        '<td class="n"><span class="edge ' + (mk.edge > 0 ? 'pos' : 'neg') + '">' + sgn(mk.edge * 100, 1) + '</span></td>' +
        '<td class="n">' + sgn(mk.fair, 0) + '</td>' +
        '<td>' + (res ? '<span class="chip ' + res + '">' + resText(res) + '</span>' : '<span class="gdate">—</span>') + '</td></tr>';
    });
    $("board").innerHTML = h + '</tbody></table>';
  }
  /* The row last opened into the form. While the form still holds exactly
     that row's inputs, the rail grades itself against the row's finals; the
     first edit turns the rail back into a hypothetical and the grading goes. */
  var opened = null;
  function openRow(id) {
    var row = card.filter(function (r) { return String(r.id) === String(id); })[0]; if (!row) return;
    setSport(row.sport, true); restore(row.inputs);
    opened = { id: row.id, snap: JSON.stringify(snapshot()), row: row };
    setFormLock(rowLocked(row));
    onEdit();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  /* A graded row opened into the form is a record, so the form is read-only
     until Clear. Add is off too: a locked row must not be logged twice. */
  var formLocked = false;
  function setFormLock(on) {
    formLocked = !!on;
    ALL.concat(CHECKS).forEach(function (id) { $(id).disabled = formLocked; });
    ["paste", "pasteFill", "add", "example", "m-mlb", "m-wnba"].forEach(function (id) { $(id).disabled = formLocked; });
    $("lockNote").hidden = !formLocked;
  }
  function openedFinals() {
    if (!opened) return null;
    if (JSON.stringify(snapshot()) !== opened.snap) return null;
    var fin = opened.row.finals || {};
    var has = ["fa", "fh", "f5a", "f5h"].some(function (k) { return fin[k] !== undefined && fin[k] !== ""; });
    return has ? opened.row : null;
  }

  /* ---- the card ------------------------------------------------------------ */
  /* A row is LOCKED once both finals are in. Its score boxes go read-only and
     it cannot be removed; the only way back is the row's own unlock, which is
     for correcting a typo and lasts until the page is reloaded. Nothing about
     the lock is stored -- the finals are the lock. */
  function rowLocked(r) {
    var fin = r.finals || {};
    return fin.fa !== undefined && fin.fa !== "" && fin.fh !== undefined && fin.fh !== "" && !unlocked[r.id];
  }
  var unlocked = {};
  function renderCard() {
    if (typeof renderSlate === "function") renderSlate();
    $("cardCount").textContent = card.length ? card.length + " matchups" : "";
    if (!card.length) { $("cardTable").innerHTML = '<div class="empty">Nothing on the card yet.</div>'; return; }
    var today = todayISO();
    var rows = card.slice().sort(function (a, b) { return (b.gdate || "").localeCompare(a.gdate || "") || (b.id - a.id); });
    var h = '<table><thead><tr><th>Date</th><th>Matchup</th><th>Markets logged (frozen when added)</th><th>Finals</th><th></th></tr></thead><tbody>';
    rows.forEach(function (r) {
      var fin = r.finals || {};
      var mks = (r.markets || []).map(function (mk) {
        var res = gradeMarket(mk, fin);
        return '<span class="m' + (mk.edge !== null && mk.edge > 0 ? ' pos' : '') + '"><span class="chip ' + sideClass(mk.side) + '">' + esc(mk.pick) + '</span>' +
          (mk.p * 100).toFixed(1) + '%' + (mk.price !== null ? ' ' + sgn(mk.price, 0) + ' <span class="edge ' + (mk.edge > 0 ? 'pos' : 'neg') + '">' + sgn(mk.edge * 100, 1) + '</span>' : '') +
          (res ? ' <span class="chip ' + res + '">' + resText(res) + '</span>' : '') + '</span>';
      }).join("");
      var lk = rowLocked(r), ro = lk ? ' readonly' : '';
      var cl = r.close || {};
      /* The close is never read-only: it is typed the morning after, often
         after the finals have already locked the row. */
      var close = '<span class="finals"><span class="l">CLOSE</span><input class="grade close" data-id="' + r.id + '" data-k="ctot" value="' + esc(cl.ctot || "") + '" placeholder="' + (r.sport === "WNBA" ? "tot" : "tot") + '" inputmode="decimal" title="The full-game total the market closed at">' +
        (r.sport === "MLB" ? '<input class="grade close" data-id="' + r.id + '" data-k="cf5" value="' + esc(cl.cf5 || "") + '" placeholder="F5" inputmode="decimal" title="The first-five total the market closed at">' : '') + '</span>';
      var f5 = r.sport === "MLB"
        ? '<span class="finals"><span class="l">F5</span><input class="grade" data-id="' + r.id + '" data-k="f5a" value="' + esc(fin.f5a || "") + '" placeholder="A" inputmode="numeric"' + ro + '>' +
          '<input class="grade" data-id="' + r.id + '" data-k="f5h" value="' + esc(fin.f5h || "") + '" placeholder="H" inputmode="numeric"' + ro + '></span>' : '';
      h += '<tr><td><span class="gdate' + (r.gdate === today ? ' today' : '') + '">' + esc(gameDate(r.gdate)) + '</span></td>' +
        '<td><button type="button" class="openbtn" data-open="' + r.id + '" title="Load into the form"><b>' + esc(r.matchup) + '</b><br><span class="gdate">' + esc(r.sport) + '</span>' +
          markChips(marksOf(r.sport, r.inputs, r.markets), "tagm") + '</button></td>' +
        '<td><div class="rowmk">' + mks + '</div></td>' +
        '<td' + (lk ? ' class="locked"' : '') + '><span class="finals"><span class="l">FINAL</span><input class="grade" data-id="' + r.id + '" data-k="fa" value="' + esc(fin.fa || "") + '" placeholder="A" inputmode="numeric"' + ro + '>' +
          '<input class="grade" data-id="' + r.id + '" data-k="fh" value="' + esc(fin.fh || "") + '" placeholder="H" inputmode="numeric"' + ro + '></span> ' + f5 +
          (lk ? ' <span class="lock" title="Graded and locked">&#128274;</span>' : '') + '<br>' + close + '</td>' +
        '<td>' + (lk
          ? '<button type="button" class="x unlock" data-unlock="' + r.id + '" title="Unlock to correct the score">unlock</button>'
          : (unlocked[r.id] ? '<button type="button" class="x unlock" data-relock="' + r.id + '" title="Lock again">lock</button>' : '') +
            '<button type="button" class="x" data-del="' + r.id + '" title="Remove">×</button>') + '</td></tr>';
    });
    $("cardTable").innerHTML = h + '</tbody></table>';
  }

  /* ---- is it working, per market ------------------------------------------- */
  /* One block per sport. The markets differ (first five and run line are
     baseball; the spread is basketball), the distributions differ, and a
     record that pooled them would hide which book is working. The two fours
     are split the same way: each leg is credited to the sport it came from. */
  /* ---- two LABELS, never adjustments --------------------------------------
     Both are read off the stored inputs and markets, so every row already on
     the card carries them, and neither moves a number. They exist so the
     record can be split by them; if a split holds up over enough games it
     earns a coefficient then, the way the wind did. Added 25 Sept 2026.

     cold-under profile (MLB): total 7 or lower, wind in (in or quartering in)
     at 10 mph or more, both bullpens under 3.75, and at least one team's last
     ten below the line. Guardians @ Red Sox on 23 and 24 Sept -- 1-0 both
     nights -- is the archetype; Rays @ Yankees the same nights looked alike,
     failed on the Rays' pen and the Yankees' form, and went 11 and 10.

     same / split lean (MLB): whether the sheet's pick on the full-game total
     and its pick on the first five are the same side. On the first 21 games
     the full-game pick went 11-4 when they agreed and 2-4 when they split. */
  /* numOf, not num: the engine block owns num(id), which reads a form field. */
  function numOf(v) { var x = parseFloat(v); return isFinite(x) ? x : null; }
  /* over against the grain (MLB): the sheet's pick is the OVER, and at least
     one of three things the market can see leans under -- the book's two
     prices (implied over below implied under by a point), the two last-ten
     averages (a run or more under the line), or 80%+ of the money. On the 224
     graded MLB totals across both sheets (2-25 Sept 2026) an over with none
     of those against it went 79-44 (64%); an over with any of them against it
     went 11-15 (42%). The same three signals say nothing about unders, which
     ran 37-38 with or without them, so unders get no chip. Sept 12 and 20,
     the two best days on record, were over-heavy nights with every signal
     agreeing. A label, not an adjustment: it has its own record line. */
  function grainOf(side, inputs) {
    if (side !== "OVER") return "";
    var line = numOf(inputs.line), op = numOf(inputs.op), up = numOf(inputs.up);
    var al = numOf(inputs.al10), hl = numOf(inputs.hl10), cash = numOf(inputs.cash);
    var against = 0;
    if (op !== null && up !== null && implied(up) - implied(op) > 0.01) against++;
    if (al !== null && hl !== null && line !== null && (al + hl) / 2 <= line - 1) against++;
    if (cash !== null && cash <= 20) against++;
    return against ? "over against the grain" : "";
  }
  /* the last word of a goalie's name, lower-cased, accents dropped: "Igor Shesterkin" and "I. Shesterkin" agree */
  function lastName(s) {
    var w = String(s || "").trim().split(/\s+/); if (!w.length) return "";
    return w[w.length - 1].normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  }
  function marksOf(sp, inputs, markets) {
    var out = { profile: "", lean: "", grain: "", crowd: "", b2b: "", backup: "", goalie: "" };
    if (!inputs) return out;
    /* the crowd (NHL): where the money is, against the sheet's pick on the
       total. 65%+ of the money on one side is a crowd; the pick is WITH it
       or AGAINST it. A label with its own record line, asked for on 5 Oct
       ("add the over/under % for tickets to help the model... can we test
       this?"): in MLB no threshold beat a coin, so it is shown, not scored,
       and the hockey record will say whether hockey is different. */
    if (sp === "NHL") {
      var cash = numOf(inputs.ncash), tot = null;
      (markets || []).forEach(function (mk) { if (mk.key === "total") tot = mk; });
      if (tot && cash !== null && (cash >= 65 || cash <= 35)) {
        var crowdSide = cash >= 65 ? "OVER" : "UNDER";
        out.crowd = tot.side === crowdSide ? "with the crowd" : "against the crowd";
      }
      /* back to back (NHL): a side on no rest. Shown, not scored; the total
         tile keeps the UNDER's record on these games whatever the pick was,
         because the first 12 on the card went under 8-4 (7 Oct 2026) and a
         tired team is a mechanism with a disputed sign. The line is the test. */
      var ar = numOf(inputs.arest), hr = numOf(inputs.hrest);
      if ((ar !== null && ar <= 0) || (hr !== null && hr <= 0)) out.b2b = "back to back";
      /* a backup in ONE net (NHL): the market over-bumps the total; the
         engine puts a tagged delta on the under (nhl.engine.js) and the
         total tile keeps the UNDER's record on these games. Two backups:
         no label, nothing moves. Measured 7 Oct 2026 on two seasons. */
      if ((inputs.agbk === true) !== (inputs.hgbk === true)) out.backup = "backup in net";
      /* the goalie on the card against the goalie who played (from the grade
         file): both right, or a line that was the other goalie's. 11 Oct 2026. */
      var oks = [inputs.agok, inputs.hgok].filter(function (v) { return v === "yes" || v === "no"; });
      if (oks.length === 2 && oks[0] === "yes" && oks[1] === "yes") out.goalie = "goalies right";
      else if (oks.indexOf("no") >= 0) out.goalie = "goalie line wrong";
      return out;
    }
    if (sp !== "MLB") return out;
    (markets || []).forEach(function (mk) { if (mk.key === "total") out.grain = grainOf(mk.side, inputs); });
    var line = numOf(inputs.line), mph = numOf(inputs.mph), dir = String(inputs.dir || "");
    var abp = numOf(inputs.abp), hbp = numOf(inputs.hbp), al = numOf(inputs.al10), hl = numOf(inputs.hl10);
    if (line !== null && line <= 7 && (dir === "in" || dir === "quarter-in") && mph !== null && mph >= 10 &&
        abp !== null && hbp !== null && abp < 3.75 && hbp < 3.75 &&
        ((al !== null && al < line) || (hl !== null && hl < line))) out.profile = "cold-under profile";
    var tot = null, f5 = null;
    (markets || []).forEach(function (mk) { if (mk.key === "total") tot = mk; if (mk.key === "f5") f5 = mk; });
    if (tot && f5) out.lean = tot.side === f5.side ? "same lean" : "split lean";
    return out;
  }
  function markChips(tg, cls) {
    var h = "";
    if (tg.grain) h += '<span class="' + cls + ' warn">' + esc(tg.grain) + '</span>';
    if (tg.profile) h += '<span class="' + cls + '">' + esc(tg.profile) + '</span>';
    if (tg.lean) h += '<span class="' + cls + '">' + esc(tg.lean) + '</span>';
    if (tg.crowd) h += '<span class="' + cls + '">' + esc(tg.crowd) + '</span>';
    if (tg.b2b) h += '<span class="' + cls + '">' + esc(tg.b2b) + '</span>';
    if (tg.backup) h += '<span class="' + cls + '">' + esc(tg.backup) + '</span>';
    if (tg.goalie) h += '<span class="' + cls + (tg.goalie === "goalie line wrong" ? ' warn' : '') + '">' + esc(tg.goalie) + '</span>';
    return h;
  }
  /* ---- the favourite, by price (12 Oct 2026) ----------------------------------
     Asked for the night the hockey sides were measured ("I like how you put
     this together. Can we track this on the model near the 'is it working'
     section"): every graded row with both moneyline prices typed, bucketed
     by the favourite's price: how often the favourite won against what its
     price implied, how often the dog covered +1.5 and the favourite -1.5,
     and the favourite's moneyline return. The two-season baseline at the
     close (tools_backtest_nhl_sides.py, 2,616 games) sits in grey beside the
     hockey block. Nothing here moves a number; it is the base rate the pick
     is read against. */
  var FAV_BUCKETS = [[-100000, -200, "−200 or more"], [-199, -150, "−199 to −150"], [-149, -120, "−149 to −120"], [-119, -101, "−119 to −101"]];
  var FAV_BASE_NHL = { "−200 or more": [566, 68.2, 71.5, 55.5, 44.5, -4.8], "−199 to −150": [859, 58.2, 62.6, 62.9, 37.1, -7.1],
                       "−149 to −120": [828, 54.0, 57.1, 68.6, 31.4, -5.5], "−119 to −101": [281, 50.2, 52.2, 70.5, 29.5, -4.0] };
  var FAV_COLOR_MIN = 10, FAV_COLOR_PTS = 2;   // colour needs ten games and two points of daylight from the reference (14 Oct 2026)
  function favBlock(sp) {
    var b = {};
    card.forEach(function (r) {
      if (r.sport !== sp || !r.finals) return;
      var fh = parseFloat(r.finals.fh), fa = parseFloat(r.finals.fa);
      if (!isFinite(fh) || !isFinite(fa)) return;
      var hml = numOf((r.inputs || {}).hml), aml = numOf((r.inputs || {}).aml);
      if (hml === null || aml === null || hml === aml) return;
      var favHome = hml < aml, favp = favHome ? hml : aml, margin = favHome ? fh - fa : fa - fh;
      var bk = FAV_BUCKETS.filter(function (x) { return favp >= x[0] && favp <= x[1]; })[0];
      if (!bk) return;
      var s = b[bk[2]] || (b[bk[2]] = { n: 0, w: 0, imp: 0, dog: 0, fav15: 0, units: 0 });
      s.n++; s.imp += implied(favp);
      if (margin > 0) { s.w++; s.units += payout(favp); } else s.units -= 1;
      if (margin <= 1) s.dog++;
      if (margin >= 2) s.fav15++;
    });
    if (!Object.keys(b).length && sp !== "NHL") return "";
    var h = '<div class="verdict favs" data-sport="' + sp + '"><b>The favourite, by price.</b> The favourite\'s record against what its price implied, the dog +1.5 and the favourite −1.5, and the favourite\'s moneyline return, over this card\'s graded games with both prices typed' +
      (sp === "NHL" ? '; in grey, two seasons at the close (2,616 games, measured 12 Oct 2026)' : '') + '. The base rate the pick is read against; nothing here moves a number. ' +
      '<span class="dim">Green beats its reference by ' + FAV_COLOR_PTS + ' points or more, red trails it: the implied chance for the favourite, ' + (sp === "NHL" ? 'the two-season rate for the spreads, ' : '') + 'zero for the return. Colour after ' + FAV_COLOR_MIN + ' games.</span>' +
      '<table class="favt"><tr><th>favourite\'s price</th><th>n</th><th>fav won</th><th>implied</th><th>dog +1.5</th><th>fav −1.5</th><th>fav ML</th></tr>';
    var cell = function (pct, ref, n, text) {
      var cls = (ref === null || n < FAV_COLOR_MIN) ? '' : pct >= ref + FAV_COLOR_PTS ? ' class="up"' : pct <= ref - FAV_COLOR_PTS ? ' class="down"' : '';
      return '<td' + cls + '>' + text + '</td>';
    };
    FAV_BUCKETS.forEach(function (x) {
      var s = b[x[2]], base = sp === "NHL" ? FAV_BASE_NHL[x[2]] : null;
      if (!s && !base) return;
      var won = s ? 100 * s.w / s.n : 0, imp = s ? 100 * s.imp / s.n : 0, dog = s ? 100 * s.dog / s.n : 0, f15 = s ? 100 * s.fav15 / s.n : 0, ret = s ? 100 * s.units / s.n : 0;
      h += '<tr><td>' + x[2] + '</td>' + (s
        ? '<td>' + s.n + '</td>' + cell(won, imp, s.n, won.toFixed(1) + '%') + '<td class="ref">' + imp.toFixed(1) + '%</td>' +
          cell(dog, base ? base[3] : null, s.n, dog.toFixed(1) + '%') + cell(f15, base ? base[4] : null, s.n, f15.toFixed(1) + '%') + cell(ret, 0, s.n, sgn(ret, 1) + '%')
        : '<td>0</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td>') + '</tr>';
      if (base) h += '<tr class="base"><td>two seasons at the close</td><td>' + base[0] + '</td><td>' + base[1].toFixed(1) + '%</td><td>' + base[2].toFixed(1) + '%</td><td>' + base[3].toFixed(1) + '%</td><td>' + base[4].toFixed(1) + '%</td><td>' + sgn(base[5], 1) + '%</td></tr>';
    });
    return h + '</table></div>';
  }
  function renderCalib() {
    var KEYS = { MLB: [["total","Full-game total"],["f5","First five"],["ml","Moneyline"],["rl","Run line"]],
                 WNBA: [["total","Full-game total"],["ml","Moneyline"],["spread","Spread"]] };
    var box = $("calibBox");
    backfillProj();
    /* Each tile also keeps the record BY SIDE -- over against under, home
       against away -- and the full-game total keeps the record of the rows
       that carried Call Sheet #1's verdict, because the parlay legs lean on
       it. Asked for on 25 Sept: "how many of the 17-10 went over vs under". */
    var fresh = function (label) { return { n: 0, w: 0, l: 0, p: 0, says: 0, units: 0, label: label, sides: {}, verdict: null, profile: null, lean: {}, grain: null, crowd: {}, high: null, b2b: null, backup: null, goalie: {}, call: null,
                                            clv: { n: 0, beat: 0, lost: 0, even: 0, runs: 0 } }; };
    var bySport = {};
    ["MLB", "WNBA"].forEach(function (sp) {
      var b = { stats: {}, pick: fresh("The pick"), top: fresh("The parlay four"), topE: fresh("Best straight bets"), any: false };
      KEYS[sp].forEach(function (k) { b.stats[k[0]] = fresh(k[1]); });
      bySport[sp] = b;
    });
    var count = function (c, res) { if (res === "push") c.p++; else if (res === "win") c.w++; else c.l++; };
    var tally = function (t, mk, res, row, clvRow) {
      var cl = clvOf(mk, clvRow || row);
      if (cl !== null) { t.clv.n++; t.clv.runs += cl; if (cl > 1e-9) t.clv.beat++; else if (cl < -1e-9) t.clv.lost++; else t.clv.even++; }
      if (row) {
        var sd = t.sides[mk.side] || (t.sides[mk.side] = { w: 0, l: 0, p: 0 });
        count(sd, res);
        /* the 54%+ line: every pick the sheet called 54% or better, whatever
           its price. Asked for on 5 Oct ("54% or higher even without an edge
           should be considered a bet... let's test it"): the record is the
           test, and this line is it -- if these hit 54% they are still losing
           bets at -140, and if they hit 60% the price was wrong, not the rule. */
        if (mk.p >= 0.54) count(t.high || (t.high = { w: 0, l: 0, p: 0 }), res);
        if (mk.key === "total" && bandOf(mk)) { count(t.verdict || (t.verdict = { w: 0, l: 0, p: 0 }), res); }
        if (mk.key === "spread") {
          var sh = shadeOf(mk), shRes = sh ? gradeMarket(sh, row.finals) : null;
          if (shRes !== null && shRes !== "invalid") count(t.shade || (t.shade = { w: 0, l: 0, p: 0 }), shRes);
        }
        if (mk.key === "total" || mk.key === "f5") {
          var tg = marksOf(row.sport, row.inputs, row.markets);
          if (tg.profile) count(t.profile || (t.profile = { w: 0, l: 0, p: 0 }), res);
          if (tg.grain && mk.key === "total") count(t.grain || (t.grain = { w: 0, l: 0, p: 0 }), res);
          if (tg.lean) count(t.lean[tg.lean] || (t.lean[tg.lean] = { w: 0, l: 0, p: 0 }), res);
          if (tg.crowd && mk.key === "total") count(t.crowd[tg.crowd] || (t.crowd[tg.crowd] = { w: 0, l: 0, p: 0 }), res);
          if (tg.goalie && mk.key === "total") count(t.goalie[tg.goalie] || (t.goalie[tg.goalie] = { w: 0, l: 0, p: 0 }), res);
          if (mk.key === "total") {
            var cv = callOf(row, mk), cr = cv ? gradeMarket(cv, row.finals) : null;
            if (cr !== null && cr !== "invalid") count(t.call || (t.call = { w: 0, l: 0, p: 0 }), cr);
            /* Pinnacle's shade (13 Oct 2026): the side the sharp book prices shorter by 20+ cents, on its own line */
            var ss = sharpShadeOf((row.inputs || {}).sharp), sv = ss ? bothSides(mk).filter(function (v) { return v.side === ss.side; })[0] : null;
            var sr = sv ? gradeMarket(sv, row.finals) : null;
            if (sr !== null && sr !== "invalid") count(t.sharpShade || (t.sharpShade = { w: 0, l: 0, p: 0 }), sr);
          }
          if ((tg.b2b || tg.backup) && mk.key === "total") {
            var uv = bothSides(mk).filter(function (v) { return v.side === "UNDER"; })[0];
            var ur = uv ? gradeMarket(uv, row.finals) : null;
            if (ur !== null && ur !== "invalid") {
              if (tg.b2b) count(t.b2b || (t.b2b = { w: 0, l: 0, p: 0 }), ur);
              if (tg.backup) count(t.backup || (t.backup = { w: 0, l: 0, p: 0 }), ur);
              /* the HOME club on a back to back with a backup in net (13 Oct 2026): the cell the
                 backup rule's edge sits in on two seasons (the under 65.2% on 115, split 50% and
                 73.5% by season), watched on its own line before it can size anything */
              var hr = numOf((row.inputs || {}).hrest);
              if (tg.backup && hr !== null && hr <= 0) count(t.hb2bBackup || (t.hb2bBackup = { w: 0, l: 0, p: 0 }), ur);
            }
          }
        }
      }
      if (res === "push") { t.p++; return; }
      t.n++; t.says += mk.p; t.w += res === "win" ? 1 : 0; t.l += res === "loss" ? 1 : 0; t.units += unitsOf(mk, res);
    };
    var dates = {};
    card.forEach(function (r) {
      var b = bySport[r.sport]; if (!b) return;
      (r.markets || []).forEach(function (mk) {
        var res = gradeMarket(mk, r.finals);
        if (res === null || res === "invalid") return;
        var st = b.stats[mk.key]; if (!st) return;
        b.any = true; tally(st, mk, res, r);
      });
      /* the pick's own record (12 Oct 2026): the likeliest side of any market
         on the row, graded like the rest, every row on the card so the
         approach is read against the whole book. The hockey window's rows
         were calls, not picks, and stay out. */
      if (!(r.sport === "NHL" && NHL_TOTAL_ONLY.indexOf(r.gdate || "") >= 0)) {
        var pk = thePick(r.markets, r.sport, r.gdate), pres = pk && !pk.none ? gradeMarket(pk.mk, r.finals) : null;
        if (pres !== null && pres !== "invalid") { b.any = true; tally(b.pick, pk.mk, pres, null, r); }
      }
      if (r.gdate) dates[r.gdate] = true;
    });
    Object.keys(dates).forEach(function (d) {
      [[parlayFour(d), "top"], [bestBets(d), "topE"]].forEach(function (rule) {
        rule[0].forEach(function (x) {
          var res = gradeMarket(x.mk, x.row.finals), b = bySport[x.row.sport];
          if (res === null || res === "invalid" || !b) return;
          tally(b[rule[1]], x.mk, res, null, x.row);
        });
      });
    });
    /* Every sport gets a block, graded or not: a sport with nothing graded
       shows its heading and what to type, so the section always says which
       books it keeps (asked for on 1 Oct, when the WNBA and NHL blocks were
       invisible until their first graded game). */
    var EMPTY_NOTE = { MLB: "Nothing graded yet. Type the final and the first-five score on the card and the four markets grade themselves.",
                       WNBA: "Nothing graded yet. Type the final on the card and the three markets grade themselves." };
    var h = '';
    if (!bySport.MLB.any && !bySport.WNBA.any) {
      h += '<p class="note">Enter finals on the card — away and home runs, and the first-five runs for MLB — and every market grades itself, one block per sport.</p>';
    }
    var tiles = function (s, unit) {
      if (!s.n && !s.p) return '';
      var says = s.n ? s.says / s.n * 100 : 0, does = s.n ? s.w / s.n * 100 : 0;
      var se = s.n ? Math.sqrt(Math.max(does / 100 * (1 - does / 100), 1e-9) / s.n) * 100 : 0;
      var rec = function (c) { return c.w + '-' + c.l + (c.p ? '-' + c.p : ''); };
      var order = ["OVER", "UNDER", "HOME", "AWAY"], parts = [];
      order.forEach(function (sd) { if (s.sides[sd]) parts.push(sd.toLowerCase() + ' ' + rec(s.sides[sd])); });
      if (s.verdict) parts.push('#1 BET or better ' + rec(s.verdict));
      if (s.high) parts.push('54%+ picks ' + rec(s.high));
      if (s.shade) parts.push('cheaper side ' + rec(s.shade));
      if (s.profile) parts.push('cold-under profile ' + rec(s.profile));
      if (s.grain) parts.push('over against the grain ' + rec(s.grain));
      ["same lean", "split lean"].forEach(function (k) { if (s.lean[k]) parts.push(k + ' ' + rec(s.lean[k])); });
      ["with the crowd", "against the crowd"].forEach(function (k) { if (s.crowd[k]) parts.push(k + ' ' + rec(s.crowd[k])); });
      if (s.b2b) parts.push('back to back, the under ' + rec(s.b2b));
      if (s.backup) parts.push('backup in net, the under ' + rec(s.backup));
      if (s.hb2bBackup) parts.push('home back to back with a backup, the under ' + rec(s.hb2bBackup));
      ["goalies right", "goalie line wrong"].forEach(function (k) { if (s.goalie[k]) parts.push(k + ' ' + rec(s.goalie[k])); });
      if (s.call) parts.push('the call, ' + NHL_TOTAL_ONLY_LABEL + ' ' + rec(s.call));
      if (s.sharpShade) parts.push("Pinnacle's shade, 3+ points " + rec(s.sharpShade));
      if (s.clv.n) parts.push('beat the close ' + s.clv.beat + '-' + s.clv.lost + (s.clv.even ? '-' + s.clv.even : '') + ' · ' + sgn(s.clv.runs / s.clv.n, 2) + ' ' + (unit || 'runs') + ' avg');
      return '<div><p class="k">' + esc(s.label) + '</p><p class="v">' + s.w + '-' + s.l + (s.p ? '-' + s.p : '') + '</p>' +
        '<p class="s">' + (s.n ? 'says ' + says.toFixed(1) + '% · does ' + does.toFixed(1) + '% (±' + se.toFixed(1) + ') · ' + sgn(s.units, 2) + 'u' : 'pushes only') + '</p>' +
        (parts.length ? '<p class="s sides">' + esc(parts.join(' · ')) + '</p>' : '') + '</div>';
    };
    ["MLB", "WNBA"].forEach(function (sp) {
      var b = bySport[sp];
      if (!b.any) {
        h += '<div class="subhead" data-sport="' + sp + '">' + sp + ' <span class="tag">nothing graded yet</span></div>' +
             '<div class="verdict" data-sport="' + sp + '">' + esc(EMPTY_NOTE[sp]) + '</div>';
        return;
      }
      var totalN = KEYS[sp].reduce(function (a, k) { return a + b.stats[k[0]].n; }, 0);
      var graded = card.filter(function (r) { return r.sport === sp && (r.markets || []).some(function (mk) { return gradeMarket(mk, r.finals) !== null; }); }).length;
      h += '<div class="subhead" data-sport="' + sp + '">' + sp + ' <span class="tag">' + graded + ' graded game' + (graded === 1 ? '' : 's') + ' · ' + totalN + ' graded markets</span></div>';
      h += forecastBlock(sp);
      h += favBlock(sp);
      var unit = sp === "WNBA" ? "pts" : "runs";
      h += '<div class="calib" data-sport="' + sp + '">' + tiles(b.pick, unit) + KEYS[sp].map(function (k) { return tiles(b.stats[k[0]], unit); }).join('') + tiles(b.top, unit) + tiles(b.topE, unit) + '</div>';
      h += '<div class="verdict">' + (totalN < 30
        ? '<b>' + totalN + ' graded ' + sp + ' markets.</b> Nothing here can be read yet — one standard error on a hit rate is ' +
          (totalN ? (100 / Math.sqrt(totalN) / 2).toFixed(0) : '—') + ' points at this size. ' +
          (sp === "MLB" ? 'The run line and the moneyline are shown, not picked, since 27 Sept: watch whether the run line\'s <i>does</i> climbs back toward its <i>says</i>; it comes back at 150 picks if it does. The two fours are the reason the sheet exists.'
                        : 'With seven games in the season book and this sheet newer than that, the WNBA block will read as noise for weeks; it is here so the two sports never get pooled.')
        : '<b>' + totalN + ' graded ' + sp + ' markets.</b> Compare each market\'s <i>does</i> against its <i>says</i> before believing either; ' +
          'and compare each four against the blind rate of everything logged, not against 50%. The parlay four and the straight bets will differ most nights; the units column is the referee.') + '</div>';
    });
    box.innerHTML = h;
  }


  /* ---- the WNBA paste ------------------------------------------------------ */
  function parseWnbaPaste(text) {
    var lines = text.split(/\r?\n/).map(function (l) { return l.trim(); }).filter(Boolean);
    var split = function (l) { return l.indexOf("\t") >= 0 ? l.split("\t") : l.split(/\s{2,}/); };
    var head = -1, cols = null;
    for (var i = 0; i < lines.length; i++) {
      var c = split(lines[i]).map(function (x) { return x.trim().toUpperCase(); });
      if (c.indexOf("OFFRTG") >= 0 && c.indexOf("DEFRTG") >= 0) { head = i; cols = c; break; }
    }
    if (head < 0) return { error: "No header row with OFFRTG and DEFRTG found. Copy the whole table, header included." };
    var iO = cols.indexOf("OFFRTG"), iD = cols.indexOf("DEFRTG"), iP = cols.indexOf("PACE/40"), iT = cols.indexOf("TEAM");
    if (iP < 0) return { error: "The paste has no PACE/40 column. The model is calibrated on PACE/40, not PACE — pick the column on the site and copy again." };
    var rows = {};
    for (var j = head + 1; j < lines.length; j++) {
      var cells = split(lines[j]).map(function (x) { return x.trim(); });
      if (cells.length <= Math.max(iO, iD, iP)) continue;
      var name = (iT >= 0 ? cells[iT] : cells[0]).replace(/^\d+\s+/, "");
      var o = parseFloat(cells[iO]), d = parseFloat(cells[iD]), p = parseFloat(cells[iP]);
      if (!isFinite(o) || !isFinite(d) || !isFinite(p)) continue;
      rows[name.toLowerCase()] = { name: name, off: o, def: d, pace: p };
    }
    return { rows: rows };
  }
  function findTeam(rows, typed) {
    var t = String(typed || "").toLowerCase().trim();
    if (!t) return null;
    var keys = Object.keys(rows);
    for (var i = 0; i < keys.length; i++) if (keys[i] === t) return rows[keys[i]];
    for (i = 0; i < keys.length; i++) if (keys[i].indexOf(t) >= 0 || t.indexOf(keys[i]) >= 0) return rows[keys[i]];
    var last = t.split(/\s+/).pop();
    for (i = 0; i < keys.length; i++) if (keys[i].split(/\s+/).pop() === last) return rows[keys[i]];
    return null;
  }
  function pasteFill() {
    var r = parseWnbaPaste($("paste").value), msg = $("pasteMsg");
    if (r.error) { msg.textContent = r.error; return; }
    var a = findTeam(r.rows, $("away").value), h = findTeam(r.rows, $("home").value), got = [];
    if (a) { $("apace").value = a.pace; $("aort").value = a.off; $("adrt").value = a.def; got.push(a.name); }
    if (h) { $("hpace").value = h.pace; $("hort").value = h.off; $("hdrt").value = h.def; got.push(h.name); }
    var n = Object.keys(r.rows).length;
    msg.textContent = (got.length ? "Filled " + got.join(" and ") : "Neither team name matched a row") +
      " from " + n + " rows. " + (got.length < 2 ? "Type the team names as the site spells them." : "Check them against the site once.");
    onEdit();
  }

  /* ---- wiring -------------------------------------------------------------- */
  function setSport(s, quiet) {
    sport = s;
    $("m-mlb").setAttribute("aria-pressed", s === "MLB" ? "true" : "false");
    $("m-wnba").setAttribute("aria-pressed", s === "WNBA" ? "true" : "false");
    $("mlbFields").hidden = s !== "MLB"; $("wnbaFields").hidden = s !== "WNBA";
    $("rlFields").hidden = s !== "MLB"; $("f5Fields").hidden = s !== "MLB"; $("spFields").hidden = s !== "WNBA";
    $("eyebrow").textContent = s === "MLB" ? "MLB · every market on the game" : "WNBA · every market on the game";
    $("lineLabel").textContent = s === "WNBA" ? "Total (points)" : "Total (runs)";
    $("line").placeholder = s === "WNBA" ? "165.5" : "8.5";
    var dl = $("teamList"); dl.innerHTML = teamsFor(s).map(function (t) { return '<option value="' + esc(t) + '">'; }).join("");
    if (!quiet) onEdit();
  }
  function onEdit() { render(); if (!formLocked) saveDraft(); }
  function nextId() { return card.reduce(function (m, r) { return Math.max(m, r.id || 0); }, 0) + 1; }
  /* One row per matchup per date. Adding a game that is already on the card
     REPLACES that row's inputs and picks rather than logging it twice -- a
     second Add is a corrected line, not a second game -- and a graded row is
     refused, because it is a record. Cubs @ Padres reached the 29 Sept board
     twice, and every straight bet on it with it. */
  function addToCard() {
    if (!last || formLocked) return;
    var inputs = snapshot();
    var gdate = inputs.gdate || todayISO();
    var dup = card.filter(function (r) { return sameGame(r, { sport: sport, gdate: gdate, away: last.away, home: last.home }); })[0];
    if (dup && rowGraded(dup)) {
      say("<b>" + esc(last.matchup) + "</b> on " + esc(gameDate(gdate)) + " is already on the card and graded. A graded row is a record, so nothing was added; press Clear to start a new card.");
      return;
    }
    if (dup) {
      dup.inputs = inputs; dup.markets = slimMarkets(last.markets); dup.away = last.away; dup.home = last.home; dup.matchup = last.matchup; dup.proj = projOf(last);
      save(); renderCard(); renderBoard(); renderCalib();
      say("Updated <b>" + esc(dup.matchup) + "</b>, already on the card for " + esc(gameDate(gdate)) + ": its inputs and picks were replaced with what is in the form. One row per matchup per date, so nothing was logged twice.");
      return;
    }
    var row = { id: nextId(), sport: sport, away: last.away, home: last.home, matchup: last.matchup,
                gdate: gdate, inputs: inputs, markets: slimMarkets(last.markets), finals: {}, proj: projOf(last) };
    card.push(row); save(); renderCard(); renderBoard(); renderCalib();
    say("Added <b>" + esc(row.matchup) + "</b> with " + row.markets.length + " market" + (row.markets.length === 1 ? "" : "s") + ". Picks are frozen as logged; enter finals to grade them.");
  }
  function say(msg) { var el = $("saveMsg"); el.hidden = false; el.innerHTML = msg; }
  function clearForm() {
    setFormLock(false); opened = null;
    ALL.forEach(function (id) { if (id !== "gdate") $(id).value = ""; });
    CHECKS.forEach(function (id) { $(id).checked = false; });
    onEdit();
  }
  function example() {
    clearForm();
    if (sport === "MLB") {
      restore({ away: "Rays", home: "Yankees", line: "6.5", op: "-120", up: "105", gdate: $("gdate").value,
        aml: "130", hml: "-150", rl: "-1.5", rlh: "120", rla: "-140", f5line: "3.5", f5op: "-115", f5up: "-105",
        aera: "2.94", hera: "2.95", aip: "171.1", hip: "76.1", arpg: "4.03", hrpg: "3.72", abp: "4.16", hbp: "3.13",
        al10: "6.7", hl10: "10", h2h: "7.6", h2hn: "9", pf: "103", mph: "15", dir: "quarter-in", temp: "65", tick: "94", cash: "92" });
    } else {
      restore({ away: "Sun", home: "Mystics", line: "162.5", op: "118", up: "-155", gdate: $("gdate").value,
        aml: "160", hml: "-190", sp: "-4.5", sph: "-110", spa: "-110",
        apace: "80.39", hpace: "78.79", aort: "97.6", hort: "104.2", adrt: "109.7", hdrt: "103.4",
        arest: "1", hrest: "1", al5: "175.0", hl5: "172.2" });
    }
    onEdit();
  }
  function backupBlob() {
    return JSON.stringify({ format: "callsheet2.backup", version: 1, savedAt: new Date().toISOString(),
                            card: card, draft: { sport: sport, inputs: snapshot() } }, null, 2);
  }
  function boardAsText() {
    var dateISO = $("boardDate").value || todayISO(), rows = boardRows(dateISO, !$("byEdge").checked);
    var out = ["Call Sheet 2.0 — " + gameDate(dateISO)];
    out.push("THE PARLAY FOUR (one leg per game, any price it clears)");
    parlayFour(dateISO).forEach(function (x) {
      out.push("  " + x.rank + ". " + x.row.matchup + " — " + x.mk.pick + "  " + (x.mk.p * 100).toFixed(1) + "%  " + sgn(x.mk.price, 0) +
        "  " + x.ratio.toFixed(3) + "x" + (x.band ? "  [#1: " + x.band + "]" : "") + (x.likeliest ? "  (likelier: " + x.likeliest.pick + " at " + sgn(x.likeliest.price, 0) + ")" : ""));
    });
    out.push("BEST STRAIGHT BETS (#1's verdicts first, then the WNBA cheaper side, then by edge)");
    bestBets(dateISO).forEach(function (x) {
      out.push("  " + x.rank + ". " + (x.fav ? "★ " : "") + x.row.matchup + " — " + x.mk.pick + "  " + (x.mk.p * 100).toFixed(1) + "%  " + sgn(x.mk.price, 0) + "  edge " + sgn(x.mk.edge * 100, 1) + (x.fav ? "  [the one it likes most tonight]" : "") +
        (x.tier === "verdict" ? "  [#1: " + bandOf(x.mk) + (x.thin ? ", price steeper than the chance" : "") + "]" : x.tier === "call" ? "  [the call, " + NHL_TOTAL_ONLY_LABEL + ": the likelier side" + (x.thin ? ", price steeper than the chance" : "") + "]" : x.tier === "rule" ? "  [cheaper side, a rule: " + recText(shadeRecord()) + "]" : "  [value]"));
    });
    ["MLB", "WNBA"].forEach(function (sp) {
      var sl = parlayFour(dateISO, sp), sb = bestBets(dateISO, sp);
      if (!sl.length && !sb.length) return;
      out.push(sp + " ONLY");
      sl.forEach(function (x) { out.push("  leg " + x.rank + ". " + x.row.matchup + " — " + x.mk.pick + "  " + (x.mk.p * 100).toFixed(1) + "%  " + sgn(x.mk.price, 0)); });
      sb.forEach(function (x) { out.push("  bet " + x.rank + ". " + x.row.matchup + " — " + x.mk.pick + "  " + (x.mk.p * 100).toFixed(1) + "%  " + sgn(x.mk.price, 0) + "  edge " + sgn(x.mk.edge * 100, 1)); });
    });
    out.push("EVERY PRICED MARKET — ranked by " + (!$("byEdge").checked ? "chance to hit" : "edge"));
    rows.forEach(function (x) {
      out.push((x.rank <= 4 ? "* " : "  ") + x.rank + ". " + x.row.matchup + " — " + x.mk.pick + "  " + (x.mk.p * 100).toFixed(1) + "%  " +
        sgn(x.mk.price, 0) + "  edge " + sgn(x.mk.edge * 100, 1) + (x.corr.length ? "  (same game as #" + x.corr.join(", #") + ")" : ""));
    });
    return out.join("\n");
  }

  $("m-mlb").addEventListener("click", function () { setSport("MLB"); });
  $("m-wnba").addEventListener("click", function () { setSport("WNBA"); });
  ALL.forEach(function (id) { $(id).addEventListener("input", onEdit); $(id).addEventListener("change", onEdit); });
  CHECKS.forEach(function (id) { $(id).addEventListener("change", onEdit); });
  $("byEdge").addEventListener("change", function () { renderBoard(); });
  $("picks").addEventListener("click", function (e) { var t = e.target.closest("[data-open]"); if (t) openRow(t.dataset.open); });
  $("bestBets").addEventListener("click", function (e) { var t = e.target.closest("[data-open]"); if (t) openRow(t.dataset.open); });
  $("bySport").addEventListener("click", function (e) { var t = e.target.closest("[data-open]"); if (t) openRow(t.dataset.open); });
  $("board").addEventListener("click", function (e) { var t = e.target.closest("tr[data-open]"); if (t) openRow(t.dataset.open); });
  $("boardDate").addEventListener("change", renderBoard);
  $("add").addEventListener("click", addToCard);
  $("clear").addEventListener("click", clearForm);
  $("example").addEventListener("click", example);
  $("pasteFill").addEventListener("click", pasteFill);
  $("cardTable").addEventListener("input", function (e) {
    var t = e.target; if (!t.classList.contains("grade")) return;
    var row = card.filter(function (r) { return String(r.id) === t.dataset.id; })[0]; if (!row) return;
    if (t.dataset.k === "ctot" || t.dataset.k === "cf5") {
      row.close = row.close || {}; row.close[t.dataset.k] = t.value; save(); renderCalib(); return;
    }
    if (t.readOnly) return;
    row.finals = row.finals || {}; row.finals[t.dataset.k] = t.value;
    save(); renderBoard(); renderCalib();
    // re-grade the chips in place without re-rendering the input being typed in
    var tr = t.closest("tr"), fin = row.finals;
    tr.querySelectorAll(".rowmk").forEach(function (box) {
      box.innerHTML = (row.markets || []).map(function (mk) {
        var res = gradeMarket(mk, fin);
        return '<span class="m' + (mk.edge !== null && mk.edge > 0 ? ' pos' : '') + '"><span class="chip ' + sideClass(mk.side) + '">' + esc(mk.pick) + '</span>' +
          (mk.p * 100).toFixed(1) + '%' + (mk.price !== null ? ' ' + sgn(mk.price, 0) + ' <span class="edge ' + (mk.edge > 0 ? 'pos' : 'neg') + '">' + sgn(mk.edge * 100, 1) + '</span>' : '') +
          (res ? ' <span class="chip ' + res + '">' + resText(res) + '</span>' : '') + '</span>';
      }).join("");
    });
  });
  $("cardTable").addEventListener("change", function (e) {
    var t = e.target; if (!t.classList.contains("grade")) return;
    if (t.classList.contains("close")) return;
    var row = card.filter(function (r) { return String(r.id) === t.dataset.id; })[0]; if (!row) return;
    if (rowLocked(row)) { renderCard(); if (opened && opened.id === row.id) { opened.row = row; render(); } }
  });
  $("cardTable").addEventListener("click", function (e) {
    var b = e.target.closest("button"); if (!b) return;
    if (b.dataset.unlock) {
      unlocked[b.dataset.unlock] = true; renderCard();
      say("Unlocked <b>one row</b> to correct its score. It locks again when you press lock, or when the page is reopened.");
    } else if (b.dataset.relock) {
      delete unlocked[b.dataset.relock]; renderCard();
    } else if (b.dataset.del) {
      var victim = card.filter(function (r) { return String(r.id) === b.dataset.del; })[0];
      if (victim && rowLocked(victim)) return;
      card = card.filter(function (r) { return String(r.id) !== b.dataset.del; });
      save(); renderCard(); renderBoard(); renderCalib();
    } else if (b.dataset.open) {
      openRow(b.dataset.open);
    }
  });
  $("backup").addEventListener("click", function () {
    var text = backupBlob(), name = "callsheet2-" + todayISO() + ".json";
    var done = function () { say("Backup saved as <b>" + name + "</b> — " + card.length + " matchups."); };
    var fallback = function () {
      navigator.clipboard && navigator.clipboard.writeText(text).then(function () {
        say("This viewer blocks downloads, so the backup was <b>copied to the clipboard</b> instead. Paste it into a file named " + name + ".");
      }, function () { say("This viewer blocks downloads and the clipboard. Use the Copy board as text button or open the page in a browser tab."); });
    };
    if (window.claude && window.claude.use) {
      window.claude.use("downloads").then(function (dl) {
        if (!dl) return fallback();
        dl.save({ filename: name, data: text }).then(done, fallback);
      }, fallback);
    } else {
      try {
        var a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([text], { type: "application/json" }));
        a.download = name; document.body.appendChild(a); a.click(); document.body.removeChild(a); done();
      } catch (e) { fallback(); }
    }
  });
  $("restore").addEventListener("click", function () { $("restoreFile").click(); });
  $("restoreFile").addEventListener("change", function () {
    var f = this.files && this.files[0]; if (!f) return;
    var rd = new FileReader();
    rd.onload = function () {
      try {
        var d = JSON.parse(rd.result);
        if (d.format !== "callsheet2.backup" || !Array.isArray(d.card)) throw new Error("not a Call Sheet 2.0 backup");
        card = d.card; save(); renderCard(); renderBoard(); renderCalib();
        if (d.draft && d.draft.inputs) { setSport(d.draft.sport === "WNBA" ? "WNBA" : "MLB", true); restore(d.draft.inputs); onEdit(); }
        say("Loaded <b>" + card.length + "</b> matchups from " + esc(f.name) + ".");
      } catch (e) { say("Could not load that file: " + esc(e.message) + ". Call Sheet #1 backups do not load here — the two sheets keep separate logs."); }
    };
    rd.readAsText(f);
    this.value = "";
  });
  /* ---- the slate --------------------------------------------------------------
     A file written by slate/slate.py on the user's own machine -- this page
     cannot fetch anything -- holding today's games with the inputs the model
     wants already filled (starters, pens, runs per game, last tens, weather
     resolved to a direction) and, the next morning, the finals. The loader
     never overwrites a typed value and never touches a graded row: it fills
     BLANKS on ungraded rows and rescores them (as Rescore would), writes
     finals only where a row has none, and lists the games not yet on the
     card so one click puts each into the form with everything but the lines
     and prices filled. Lines and prices are never in a slate. 28 Sept 2026. */
  var SLATE_KEY = "callsheet2.slate.v1";
  var slate = null;
  try { slate = JSON.parse(localStorage.getItem(SLATE_KEY) || "null"); } catch (e) { slate = null; }
  var SLATE_FIELDS = ["aera","hera","aip","hip","al5era","hl5era","al5ip","hl5ip","arpg","hrpg","abp","hbp","al10","hl10","h2h","h2hn","pf","mph","dir","temp","tick","cash",
                      "apace","hpace","aort","hort","adrt","hdrt","arest","hrest","al5","hl5",
                      /* the odds file (12 Oct 2026): the book's lines and prices, the opener, and
                         every book's price for the shop -- blank boxes fill, typed ones stay */
                      "line","op","up","opened","hml","aml","rl","rlh","rla","f5line","f5op","f5up","odds","sharp"];
  function blank(v) { return v === undefined || v === null || String(v).trim() === ""; }
  function sameGame(row, g) {
    var sp = g.sport === "WNBA" ? "WNBA" : "MLB";
    return (row.gdate || "") === (g.gdate || "") && row.sport === sp &&
      canonTeam(row.away, sp) === canonTeam(g.away, sp) && canonTeam(row.home, sp) === canonTeam(g.home, sp);
  }
  function rowGraded(r) { return (r.markets || []).some(function (mk) { return gradeMarket(mk, r.finals) !== null; }); }
  function hasFinals(fin) { return !!fin && !blank(fin.fa) && !blank(fin.fh); }
  function saveSlate() { try { if (slate) localStorage.setItem(SLATE_KEY, JSON.stringify(slate)); else localStorage.removeItem(SLATE_KEY); } catch (e) {} }
  function applySlate(d, name) {
    if (!d || d.format !== "callsheet2.slate" || !Array.isArray(d.games)) throw new Error("not a Call Sheet 2.0 slate");
    var filled = 0, graded = 0, frozen = 0, pending = 0;
    d.games.forEach(function (g) {
      var row = card.filter(function (r) { return sameGame(r, g); })[0];
      if (!row) { if (g.inputs) pending++; return; }
      var isGraded = rowGraded(row);
      if (g.inputs) {
        if (isGraded) { frozen++; }
        else {
          var changed = false;
          SLATE_FIELDS.forEach(function (k) {
            if (blank(g.inputs[k]) || !blank(row.inputs[k])) return;
            row.inputs[k] = String(g.inputs[k]); changed = true;
          });
          if (g.inputs.dome === true && !row.inputs.dome) { row.inputs.dome = true; changed = true; }
          /* The slate marks a postseason game at the game level; the row's
             Playoff box is shown, not scored, so it only splits the record. */
          if (g.playoff === true && !row.inputs.playoff) { row.inputs.playoff = true; changed = true; }
          if (changed) { var m = scoreMatchup(row.sport, row.inputs); if (m) { row.markets = slimMarkets(m.markets); row.proj = projOf(m); } filled++; }
        }
      }
      if (hasFinals(g.finals)) {
        if (hasFinals(row.finals)) { if (!g.inputs) frozen++; }
        else {
          var fin = {};
          ["fa","fh","f5a","f5h"].forEach(function (k) { if (!blank(g.finals[k])) fin[k] = String(g.finals[k]); });
          row.finals = fin; graded++;
        }
        /* who actually started in net (hockey): the grade file names each
           side's starter from the box score; the row keeps him and whether
           he is the goalie whose line was carded, so the record can split on
           it. Last names decide: the slate writes "Igor Shesterkin", the
           box score "I. Shesterkin". 11 Oct 2026. */
        /* the close (12 Oct 2026): the grade run attaches the last number the
           odds run saw before the game; the CLOSE box fills if it is blank */
        if (g.close) {
          row.close = row.close || {};
          ["ctot", "cf5"].forEach(function (k) { if (!blank(g.close[k]) && blank(row.close[k])) row.close[k] = String(g.close[k]); });
        }
        if (g.starters && row.inputs) {
          [["away", "agname", "agstart", "agok"], ["home", "hgname", "hgstart", "hgok"]].forEach(function (s) {
            var st = g.starters[s[0]]; if (blank(st)) return;
            row.inputs[s[2]] = String(st);
            var nm = row.inputs[s[1]];
            row.inputs[s[3]] = blank(nm) ? "" : (lastName(nm) === lastName(st) ? "yes" : "no");
          });
        }
      }
    });
    /* The pending list carries over: a finals file has no inputs and must not
       empty it, and a fresh slate replaces only the games it names. */
    var incoming = d.games.filter(function (g) { return !!g.inputs; });
    /* a second file for the same game (the odds file after the slate, or the
       slate after the odds) MERGES into the pending entry: the new file's
       blank boxes fill from what was already there, so nothing one feed
       wrote is lost to the other. 12 Oct 2026. */
    var prior = ((slate && slate.games) || []);
    incoming.forEach(function (g) {
      prior.forEach(function (k) {
        var ksp = k.sport === "WNBA" ? "WNBA" : (k.sport === "NHL" ? "NHL" : "MLB");
        if ((k.gdate || "") !== (g.gdate || "") || !sameGame({ gdate: k.gdate, sport: ksp, away: k.away, home: k.home }, g)) return;
        Object.keys(k.inputs || {}).forEach(function (key) { if (blank(g.inputs[key]) && !blank(k.inputs[key])) g.inputs[key] = k.inputs[key]; });
        ["starters", "goalies", "form"].forEach(function (f) { if (g[f] === undefined && k[f] !== undefined) g[f] = k[f]; });
        if (k.notes && k.notes.length) g.notes = (g.notes || []).concat(k.notes.filter(function (n) { return (g.notes || []).indexOf(n) < 0; }));
      });
    });
    var kept = ((slate && slate.games) || []).filter(function (k) {
      return !incoming.some(function (g) { return (k.gdate || "") === (g.gdate || "") && sameGame({ gdate: k.gdate, sport: k.sport === "WNBA" ? "WNBA" : "MLB", away: k.away, home: k.home }, g); });
    });
    slate = { name: name || (slate && slate.name) || "", date: d.date || (slate && slate.date) || "", generated: d.generated || "", games: kept.concat(incoming) };
    saveSlate(); save(); renderCard(); renderBoard(); renderCalib();
    say("Slate " + (name ? "<b>" + esc(name) + "</b> " : "") + "loaded: <b>" + filled + "</b> row" + (filled === 1 ? "" : "s") + " filled in, <b>" + graded + "</b> graded, " +
        "<b>" + pending + "</b> not yet on the card" + (frozen ? ", " + frozen + " graded row" + (frozen === 1 ? "" : "s") + " left exactly as logged" : "") +
        ". Typed values were not overwritten; lines and prices are never in a slate.");
  }
  function renderSlate() {
    var box = $("slateCard"); if (!box) return;
    if (!slate || !slate.games || !slate.games.length) { box.hidden = true; return; }
    var pend = slate.games.map(function (g, i) { return { g: g, i: i }; }).filter(function (x) { return !card.some(function (r) { return sameGame(r, x.g); }); });
    box.hidden = false;
    $("slateTag").textContent = (slate.date ? gameDate(slate.date) + " · " : "") + pend.length + " not yet on the card" + (slate.name ? " · " + slate.name : "");
    $("slateList").innerHTML = pend.length ? pend.map(function (x) {
      var g = x.g, i = g.inputs || {}, st = g.starters || {};
      var meta = [];
      if (st.away || st.home) meta.push(esc(st.away || "?") + " v " + esc(st.home || "?"));
      if (!blank(i.aera) && !blank(i.hera)) meta.push("ERA " + esc(i.aera) + "/" + esc(i.hera));
      if (!blank(i.al5era) && !blank(i.hl5era)) meta.push("last 5 " + esc(i.al5era) + "/" + esc(i.hl5era));
      if (!blank(i.abp) && !blank(i.hbp)) meta.push("pens " + esc(i.abp) + "/" + esc(i.hbp));
      if (!blank(i.al10) && !blank(i.hl10)) meta.push("L10 " + esc(i.al10) + "/" + esc(i.hl10));
      if (i.dome) meta.push("roof"); else if (!blank(i.mph)) meta.push("wind " + esc(i.mph) + (i.dir ? " " + esc(i.dir) : "") + (!blank(i.temp) ? " · " + esc(i.temp) + "°F" : ""));
      var notes = (g.notes || []).map(function (n) { return '<div class="sn">' + esc(n) + '</div>'; }).join("");
      return '<div class="sg"><div><b>' + esc(g.away) + ' @ ' + esc(g.home) + '</b> <span class="gdate">' + esc(g.sport || "MLB") + '</span>' +
        '<div class="meta">' + meta.join(" · ") + '</div>' + notes + '</div>' +
        '<button type="button" class="btn" data-slate="' + x.i + '">Fill form</button></div>';
    }).join("") : '<div class="empty">Every game in this slate is on the card.</div>';
  }
  function fillFromSlate(i) {
    var g = slate && slate.games && slate.games[i]; if (!g) return;
    setSport(g.sport === "WNBA" ? "WNBA" : "MLB", true);
    clearForm();
    var v = { away: g.away, home: g.home, gdate: g.gdate || todayISO() };
    SLATE_FIELDS.forEach(function (k) { if (!blank((g.inputs || {})[k])) v[k] = String(g.inputs[k]); });
    if (g.inputs && g.inputs.dome === true) v.dome = true;
    if (g.playoff === true) v.playoff = true;
    restore(v); onEdit();
    say("<b>" + esc(g.away) + " @ " + esc(g.home) + "</b> is in the form with the slate's inputs. Type the total, the prices and the side lines, then Add to card.");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  $("loadSlate").addEventListener("click", function () { $("slateFile").click(); });
  $("slateFile").addEventListener("change", function () {
    var f = this.files && this.files[0]; if (!f) return;
    var rd = new FileReader();
    rd.onload = function () {
      try { applySlate(JSON.parse(rd.result), f.name); }
      catch (e) { say("Could not load that slate: " + esc(e.message) + ". A slate is the file slate/slate.py writes; a backup goes under Load a backup."); }
    };
    rd.readAsText(f);
    this.value = "";
  });
  $("slateList").addEventListener("click", function (e) { var t = e.target.closest("[data-slate]"); if (t) fillFromSlate(+t.dataset.slate); });
  $("slateClear").addEventListener("click", function () { slate = null; saveSlate(); renderSlate(); });

  $("rescore").addEventListener("click", function () {
    var n = 0, kept = 0;
    card.forEach(function (r) {
      var graded = (r.markets || []).some(function (mk) { return gradeMarket(mk, r.finals) !== null; });
      if (graded) { kept++; return; }
      var m = scoreMatchup(r.sport, r.inputs); if (!m) return;
      r.markets = slimMarkets(m.markets); n++;
    });
    save(); renderCard(); renderBoard(); renderCalib();
    say("Rescored <b>" + n + "</b> ungraded matchup" + (n === 1 ? "" : "s") + " through the model as it stands today." +
        (kept ? " " + kept + " graded row" + (kept === 1 ? " was" : "s were") + " left frozen — a pick that has been graded is a record, not a draft." : ""));
  });
  $("copy").addEventListener("click", function () {
    var text = boardAsText();
    var ok = function () { say("Board copied."); };
    var no = function () { var ta = document.createElement("textarea"); ta.value = text; document.body.appendChild(ta); ta.select(); say("Select-all and copy from the box below."); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(ok, no); else no();
  });

  if (!$("gdate").value) $("gdate").value = todayISO();
  $("boardDate").value = todayISO();
  if (!loadDraft()) setSport("MLB", true);
  else if ($("gdate").value === "") $("gdate").value = todayISO();
  render(); renderCard(); renderBoard(); renderCalib();
})();
</script>
