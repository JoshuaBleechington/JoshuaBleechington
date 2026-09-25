
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
        f5notes.push("Starters: " + sgn(gap) + " runs over five innings, at the same weight the full-game " +
          "blend gives them. No bullpens — they do not pitch in the first five, which is the whole reason " +
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
             lamHome: lamH, lamAway: lamA, total: f, notes: notes };
  }
  function fmtLine(v) { return (v >= 0 ? "+" : "") + (Math.abs(v - Math.round(v)) < 1e-9 ? String(v) : v.toFixed(1)); }

  /* ---- WNBA --------------------------------------------------------------- */
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
    notes.push("Margin (home minus away) of <b>" + sgn(margin, 1) + "</b> from the " + src + ", on a margin SD of " +
      WNBA_MARGIN_SD + ". The total forecast does not move it — pace and efficiency change how many points, " +
      "not who scores more of them.");
    var half = f.projected / 2, lamH = half + margin / 2, lamA = half - margin / 2;
    var pH = 1 - ncdf((0 - margin) / WNBA_MARGIN_SD);
    markets.push(pickOf("ml", "Moneyline",
      [sideOf(home + " ML", "HOME", pH, 0, hml), sideOf(away + " ML", "AWAY", 1 - pH, 0, aml)],
      hml !== null && aml !== null, "",
      ["Read off the spread through the margin distribution when a spread is in, so an edge here is the " +
       "book's moneyline disagreeing with its own spread. That happens, and it is small."]));
    if (sp !== null) {
      var pr2 = spreadProbs(margin, sp);
      markets.push(pickOf("spread", "Spread " + home + ": " + fmtLine(sp),
        [sideOf(home + " " + fmtLine(sp), "HOME", pr2[0], pr2[1], sph),
         sideOf(away + " " + fmtLine(-sp), "AWAY", pr2[2], pr2[1], spa)],
        sph !== null && spa !== null, "",
        ["A spread with both prices in is the anchor, so this side's edge is only ever the vig regressed " +
         "for a wide hold. It is here so the day board can rank it against the totals honestly, not because " +
         "it can find value on its own."]));
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
  function unitsOf(mk, res) {
    if (res === null || res === "push" || res === "invalid" || mk.price === null) return 0;
    return res === "win" ? payout(mk.price) : -1;
  }

  /* ---- reading the form / storage ---------------------------------------- */
  var MLB_IDS = ["away","home","line","op","up","opened","gdate","aera","hera","aip","hip","arpg","hrpg",
                 "abp","hbp","al10","hl10","h2h","h2hn","pf","mph","dir","temp","tick","cash",
                 "hml","aml","rl","rlh","rla","f5line","f5op","f5up"];
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
               anchored: m.anchored, band: m.band, band1: m.band1, side1: m.side1, other: m.other };
    });
  }

  var KEY = "callsheet2.card.v1", DRAFT_KEY = "callsheet2.draft.v1";
  var card = [];
  try { card = JSON.parse(localStorage.getItem(KEY) || "[]"); } catch (e) { card = []; }
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
    $("rankTag").textContent = "by edge";
    var ranked = rankMarkets(m.markets, false), html = "", cap = legCap();
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
    /* The parlay-leg marks are about the LIKELIEST side of each market, which
       is not always the side this list shows (the list shows the better
       price). So they are computed on the likelier views and printed with the
       pick named: the likeliest thing on the game, whether it is inside the
       cap, and if not, which market is the second choice for a leg. */
    /* The parlay leg for this game -- gameLeg(): Call Sheet #1's BET on the
       total when it clears its price, else the best value side inside the
       cap, and nothing when no side clears its price. */
    var leg = gameLeg(m.markets, cap).leg;
    var beyondLikely = m.markets.map(likelier).filter(function (v) { return v.price !== null && !withinCap(v.price, cap); })
      .sort(function (a, b) { return b.p - a.p; })[0];
    ranked.forEach(function (mk, i) {
      var top = i === 0 && mk.edge !== null && mk.edge > 0;
      var isLeg = leg && mk.key === leg.key;
      var res = fin ? gradeMarket(mk, fin) : null;
      var eCls = mk.edge === null ? "" : (mk.edge > 0 ? "pos" : "neg");
      html += '<div class="mk' + (top ? " top" : "") + (isLeg ? " alt" : "") + (mk.edge !== null && mk.edge <= 0 ? " neg" : "") +
        (res ? " " + res : "") + '" data-key="' + mk.key + '"' + (res ? ' data-result="' + res + '"' : '') + '>' +
        '<div class="rk">' + (i + 1) + '</div>' +
        '<div><div class="pick ' + sideClass(mk.side) + '">' + esc(mk.pick) +
          (mk.band ? '<span class="band' + (mk.band === "NO BET" ? "" : " hot") + '">' + esc(mk.band) + '</span>' : "") +
          (!mk.anchored ? '<span class="derived">derived</span>' : "") +
          (mk.key === "total" ? railMarks : "") +
          (isLeg ? '<span class="cap" style="color:var(--go);border-color:var(--go)">parlay leg: ' + esc(leg.pick) + ' ' + (leg.p * 100).toFixed(1) + '% at ' + sgn(leg.price, 0) + ' · ' + valueRatio(leg).toFixed(3) + '× its price' + (bandOf(leg) ? ' · #1 says ' + esc(bandOf(leg)) : '') + '</span>' : "") +
          (beyondLikely && mk.key === beyondLikely.key ? '<span class="cap">likeliest: ' + esc(beyondLikely.pick) + ' ' + (beyondLikely.p * 100).toFixed(1) + '% at ' + sgn(beyondLikely.price, 0) + ' · beyond ' + sgn(cap, 0) + '</span>' : "") +
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
    if (m.lamHome !== null) {
      var t = m.lamHome + m.lamAway, ha = m.lamAway / t * 100;
      html += '<div class="split"><i class="a" style="width:' + ha.toFixed(1) + '%">' + esc(m.away) + ' ' + m.lamAway.toFixed(sport === "WNBA" ? 1 : 2) + '</i>' +
              '<i class="h" style="width:' + (100 - ha).toFixed(1) + '%">' + m.lamHome.toFixed(sport === "WNBA" ? 1 : 2) + ' ' + esc(m.home) + '</i></div>';
    }
    box.innerHTML = html;
    why.innerHTML = m.notes.concat(m.total.notes).map(function (n) { return "<li>" + n + "</li>"; }).join("");
  }

  /* ---- the day board ------------------------------------------------------- */
  /* The price a parlay leg may not be worse than. American odds, so "within
     the cap" means price >= cap: -150 is inside -170, -200 is not, +120 is. */
  var CAP_KEY = "callsheet2.cap.v1", DEFAULT_CAP = -170;
  function legCap() {
    var v = parseFloat($("legCap").value);
    return isFinite(v) ? v : DEFAULT_CAP;
  }
  function withinCap(price, cap) { return price !== null && price !== undefined && price >= cap; }

  /* One leg per game, in two tiers. First: Call Sheet #1's verdict -- a
     full-game total #1 calls BET, STRONG BET or MAX BET, on #1's side, when
     that side also clears its price inside the cap. The verdict is the one
     mark on the board that carries #1's corroboration gate, and the user
     asked for these legs by name on 25 Sept ("the ones saying bet or strong
     bet"). Second, on a game with no such total: the side, of any priced
     market inside the cap, with the best chance-to-breakeven ratio. In both
     tiers only a side whose ratio clears one qualifies: a parlay's return is
     the product over its legs of (chance / what the price needs), the boost
     multiplies the whole thing, and a leg priced above its chance drags it
     down however often it hits. Fewer than four games qualifying means fewer
     legs, and the card says so. Across games the verdict legs rank first,
     then by ratio. Over the two nights logged, #1's verdict totals went 6-3
     and this rule's legs 5-3 against 4-3-1 for value ratio alone -- not
     evidence, but not against it either; the record tile keeps score. The
     value tier came first, on 24 Sept, from White Sox @ Royals: over 8.5 at
     -120 (55.3%, ratio 1.014, #1: BET) against Royals +1.5 at -155 (61.3%,
     ratio 1.008) -- the likelier leg was the worse one, 9-1 White Sox. */
  var TIERS = { "MAX BET": 3, "STRONG BET": 2, "BET": 1 };
  /* Call Sheet #1's verdict on a side: the full-game total only, and only on
     #1's side. Rows logged before band1/side1 were stored carry the band on
     the stored pick alone, and bothSides() gives the flipped side no band. */
  function bandOf(v) {
    if (v.key !== "total") return "";
    if (v.side1) return v.side === v.side1 ? (v.band1 || "") : "";
    return v.band || "";
  }
  function bandTier(v) { return TIERS[bandOf(v)] || 0; }
  function valueRatio(mk) { return mk.price === null || mk.price === undefined ? 0 : mk.p / implied(mk.price); }
  function betterLeg(b, v) {
    var tb = bandTier(b) > 0, tv = bandTier(v) > 0;
    if (tb !== tv) return tv ? v : b;
    var rb = valueRatio(b), rv = valueRatio(v);
    return (rv > rb + 1e-12 || (Math.abs(rv - rb) <= 1e-12 && v.p > b.p)) ? v : b;
  }
  /* One game's leg, with what it passed over: the likeliest side inside the
     cap and, for a verdict leg, the richer-priced side. `inCap` says whether
     anything was priced inside the cap at all, so a game whose sides are all
     priced above their chance counts as passed over, not as unpriced. */
  function gameLeg(markets, cap) {
    var inCap = [], clears = [];
    (markets || []).forEach(function (mk) {
      bothSides(mk).forEach(function (v) {
        if (!withinCap(v.price, cap)) return;
        inCap.push(v);
        if (valueRatio(v) > 1) clears.push(v);
      });
    });
    if (!clears.length) return { leg: null, inCap: inCap.length > 0, likeliest: null, richer: null };
    var leg = clears.reduce(betterLeg);
    var likeliest = inCap.reduce(function (b, v) { return v.p > b.p ? v : b; });
    var richer = clears.reduce(function (b, v) { return valueRatio(v) > valueRatio(b) ? v : b; });
    return { leg: leg, inCap: true,
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
  function parlayFour(dateISO, cap, sport) {
    var legs = [], skipped = 0;
    card.forEach(function (r) {
      if ((r.gdate || "") !== dateISO) return;
      if (sport && r.sport !== sport) return;
      var g = gameLeg(r.markets, cap);
      if (!g.leg) { if (g.inCap) skipped++; return; }
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
  function bestBets(dateISO, sport) {
    var rows = boardRows(dateISO, false).filter(function (x) { return x.mk.edge > 0 && (!sport || x.row.sport === sport); });
    rows.forEach(function (x, i) {
      x.rank = i + 1;
      x.corr = rows.slice(0, i).filter(function (o) { return o.row.id === x.row.id; }).map(function (o) { return o.rank; });
    });
    return rows.slice(0, 4);
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
  function parlayCard(legs, cap, nRows, wide) {
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
        (legs.skipped ? '; ' + legs.skipped + ' game' + (legs.skipped === 1 ? '' : 's') + ' had no leg worth taking inside ' + sgn(cap, 0) : '') +
        (pushes ? '; ' + pushes + ' can push, which most apps void to a smaller parlay' : '') +
        '. A boosted payout above ' + (1 / pAll).toFixed(2) + '× beats fair outright.</div></div>';
    }
    if (!legs.length && nRows) return '<div class="empty">No leg on this date clears its price inside ' + sgn(cap, 0) + '. Nothing to parlay tonight.</div>';
    if (legs.length === 1) return '<div class="empty">Only one leg clears its price inside ' + sgn(cap, 0) + ' — not a parlay; it is under best straight bets if the edge is there.</div>';
    return '';
  }
  function pickCard(x, cls, extra) {
    var res = gradeMarket(x.mk, x.row.finals);
    return '<div class="pk ' + cls + '" data-open="' + x.row.id + '" title="Load ' + esc(x.row.matchup) + ' into the form">' +
      '<div class="n1">#' + x.rank + (x.corr && x.corr.length ? ' · same game as #' + x.corr.join(', #') : '') + '</div>' +
      '<div class="n2">' + esc(x.mk.pick) + (bandOf(x.mk) ? ' <span class="band hot">' + esc(bandOf(x.mk)) + '</span>' : '') + '</div>' +
      '<div class="n3">' + (x.mk.p * 100).toFixed(1) + '% · ' + (x.mk.price !== null ? sgn(x.mk.price, 0) + ' · edge ' + sgn(x.mk.edge * 100, 1) : 'no price') +
        (res ? ' · <span class="chip ' + res + '">' + resText(res) + '</span>' : '') + '</div>' +
      '<div class="n4">' + esc(x.row.matchup) + ' · ' + esc(x.mk.label) + '</div>' + (extra || '') + '</div>';
  }
  function renderBoard() {
    var dateISO = $("boardDate").value || todayISO(), byProb = !$("byEdge").checked, cap = legCap();
    try { localStorage.setItem(CAP_KEY, String(cap)); } catch (e) {}
    var rows = boardRows(dateISO, byProb);
    $("boardCount").textContent = rows.length ? rows.length + " priced markets on " + gameDate(dateISO) : "nothing logged for " + gameDate(dateISO);

    // --- the parlay four ---
    var legs = parlayFour(dateISO, cap), ph = "";
    legs.forEach(function (x) { ph += pickCard(x, "", legNote(x)); });
    ph += parlayCard(legs, cap, rows.length, true);
    $("picks").innerHTML = ph;

    // --- best straight bets ---
    var bets = bestBets(dateISO), bh = "";
    bets.forEach(function (x) { bh += pickCard(x, "straight"); });
    if (!bets.length && rows.length) bh = '<div class="empty">No market on this date is priced below its chance. The book has every side covered tonight.</div>';
    $("bestBets").innerHTML = bh;

    // --- by sport: the same two rules, one sport at a time ---
    var sh = "";
    ["MLB", "WNBA"].forEach(function (sp) {
      var games = card.filter(function (r) { return (r.gdate || "") === dateISO && r.sport === sp; }).length;
      if (!games) return;
      var sl = parlayFour(dateISO, cap, sp), sb = bestBets(dateISO, sp);
      var col = '<div class="sportcol" data-sport="' + sp + '"><div class="subhead">' + sp + ' <span class="tag">' + games + ' game' + (games === 1 ? '' : 's') + ' logged</span></div>';
      col += '<div class="lbl">Parlay legs</div><div class="picks one">';
      sl.forEach(function (x) { col += pickCard(x, "", legNote(x)); });
      col += parlayCard(sl, cap, games, false);
      col += '</div><div class="lbl">Straight bets</div><div class="picks one">';
      sb.forEach(function (x) { col += pickCard(x, "straight"); });
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
        '<td>' + esc(mk.label) + (!mk.anchored ? ' <span class="chip dim">derived</span>' : '') + '</td>' +
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
      var f5 = r.sport === "MLB"
        ? '<span class="finals"><span class="l">F5</span><input class="grade" data-id="' + r.id + '" data-k="f5a" value="' + esc(fin.f5a || "") + '" placeholder="A" inputmode="numeric"' + ro + '>' +
          '<input class="grade" data-id="' + r.id + '" data-k="f5h" value="' + esc(fin.f5h || "") + '" placeholder="H" inputmode="numeric"' + ro + '></span>' : '';
      h += '<tr><td><span class="gdate' + (r.gdate === today ? ' today' : '') + '">' + esc(gameDate(r.gdate)) + '</span></td>' +
        '<td><button type="button" class="openbtn" data-open="' + r.id + '" title="Load into the form"><b>' + esc(r.matchup) + '</b><br><span class="gdate">' + esc(r.sport) + '</span>' +
          markChips(marksOf(r.sport, r.inputs, r.markets), "tagm") + '</button></td>' +
        '<td><div class="rowmk">' + mks + '</div></td>' +
        '<td' + (lk ? ' class="locked"' : '') + '><span class="finals"><span class="l">FINAL</span><input class="grade" data-id="' + r.id + '" data-k="fa" value="' + esc(fin.fa || "") + '" placeholder="A" inputmode="numeric"' + ro + '>' +
          '<input class="grade" data-id="' + r.id + '" data-k="fh" value="' + esc(fin.fh || "") + '" placeholder="H" inputmode="numeric"' + ro + '></span> ' + f5 +
          (lk ? ' <span class="lock" title="Graded and locked">&#128274;</span>' : '') + '</td>' +
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
  function marksOf(sp, inputs, markets) {
    var out = { profile: "", lean: "" };
    if (sp !== "MLB" || !inputs) return out;
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
    if (tg.profile) h += '<span class="' + cls + '">' + esc(tg.profile) + '</span>';
    if (tg.lean) h += '<span class="' + cls + '">' + esc(tg.lean) + '</span>';
    return h;
  }
  function renderCalib() {
    var KEYS = { MLB: [["total","Full-game total"],["f5","First five"],["ml","Moneyline"],["rl","Run line"]],
                 WNBA: [["total","Full-game total"],["ml","Moneyline"],["spread","Spread"]] };
    var box = $("calibBox"), cap = legCap();
    /* Each tile also keeps the record BY SIDE -- over against under, home
       against away -- and the full-game total keeps the record of the rows
       that carried Call Sheet #1's verdict, because the parlay legs lean on
       it. Asked for on 25 Sept: "how many of the 17-10 went over vs under". */
    var fresh = function (label) { return { n: 0, w: 0, l: 0, p: 0, says: 0, units: 0, label: label, sides: {}, verdict: null, profile: null, lean: {} }; };
    var bySport = {};
    ["MLB", "WNBA"].forEach(function (sp) {
      var b = { stats: {}, top: fresh("The parlay four"), topE: fresh("Best straight bets"), any: false };
      KEYS[sp].forEach(function (k) { b.stats[k[0]] = fresh(k[1]); });
      bySport[sp] = b;
    });
    var count = function (c, res) { if (res === "push") c.p++; else if (res === "win") c.w++; else c.l++; };
    var tally = function (t, mk, res, row) {
      if (row) {
        var sd = t.sides[mk.side] || (t.sides[mk.side] = { w: 0, l: 0, p: 0 });
        count(sd, res);
        if (mk.key === "total" && bandOf(mk)) { count(t.verdict || (t.verdict = { w: 0, l: 0, p: 0 }), res); }
        if (mk.key === "total" || mk.key === "f5") {
          var tg = marksOf(row.sport, row.inputs, row.markets);
          if (tg.profile) count(t.profile || (t.profile = { w: 0, l: 0, p: 0 }), res);
          if (tg.lean) count(t.lean[tg.lean] || (t.lean[tg.lean] = { w: 0, l: 0, p: 0 }), res);
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
      if (r.gdate) dates[r.gdate] = true;
    });
    Object.keys(dates).forEach(function (d) {
      [[parlayFour(d, cap), "top"], [bestBets(d), "topE"]].forEach(function (rule) {
        rule[0].forEach(function (x) {
          var res = gradeMarket(x.mk, x.row.finals), b = bySport[x.row.sport];
          if (res === null || res === "invalid" || !b) return;
          tally(b[rule[1]], x.mk, res);
        });
      });
    });
    if (!bySport.MLB.any && !bySport.WNBA.any) {
      box.innerHTML = '<p class="note">Enter finals on the card — away and home runs, and the first-five runs for MLB — and every market grades itself, one block per sport.</p>';
      return;
    }
    var tiles = function (s) {
      if (!s.n && !s.p) return '';
      var says = s.n ? s.says / s.n * 100 : 0, does = s.n ? s.w / s.n * 100 : 0;
      var se = s.n ? Math.sqrt(Math.max(does / 100 * (1 - does / 100), 1e-9) / s.n) * 100 : 0;
      var rec = function (c) { return c.w + '-' + c.l + (c.p ? '-' + c.p : ''); };
      var order = ["OVER", "UNDER", "HOME", "AWAY"], parts = [];
      order.forEach(function (sd) { if (s.sides[sd]) parts.push(sd.toLowerCase() + ' ' + rec(s.sides[sd])); });
      if (s.verdict) parts.push('#1 BET or better ' + rec(s.verdict));
      if (s.profile) parts.push('cold-under profile ' + rec(s.profile));
      ["same lean", "split lean"].forEach(function (k) { if (s.lean[k]) parts.push(k + ' ' + rec(s.lean[k])); });
      return '<div><p class="k">' + esc(s.label) + '</p><p class="v">' + s.w + '-' + s.l + (s.p ? '-' + s.p : '') + '</p>' +
        '<p class="s">' + (s.n ? 'says ' + says.toFixed(1) + '% · does ' + does.toFixed(1) + '% (±' + se.toFixed(1) + ') · ' + sgn(s.units, 2) + 'u' : 'pushes only') + '</p>' +
        (parts.length ? '<p class="s sides">' + esc(parts.join(' · ')) + '</p>' : '') + '</div>';
    };
    var h = '';
    ["MLB", "WNBA"].forEach(function (sp) {
      var b = bySport[sp];
      if (!b.any) return;
      var totalN = KEYS[sp].reduce(function (a, k) { return a + b.stats[k[0]].n; }, 0);
      var graded = card.filter(function (r) { return r.sport === sp && (r.markets || []).some(function (mk) { return gradeMarket(mk, r.finals) !== null; }); }).length;
      h += '<div class="subhead" data-sport="' + sp + '">' + sp + ' <span class="tag">' + graded + ' graded game' + (graded === 1 ? '' : 's') + ' · ' + totalN + ' graded markets</span></div>';
      h += '<div class="calib" data-sport="' + sp + '">' + KEYS[sp].map(function (k) { return tiles(b.stats[k[0]]); }).join('') + tiles(b.top) + tiles(b.topE) + '</div>';
      h += '<div class="verdict">' + (totalN < 30
        ? '<b>' + totalN + ' graded ' + sp + ' markets.</b> Nothing here can be read yet — one standard error on a hit rate is ' +
          (totalN ? (100 / Math.sqrt(totalN) / 2).toFixed(0) : '—') + ' points at this size. ' +
          (sp === "MLB" ? 'The number to watch first is the run line, because it is the market this sheet derives rather than anchors, and the two fours, because choosing between them is the reason the sheet exists.'
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
  function addToCard() {
    if (!last || formLocked) return;
    var inputs = snapshot();
    var row = { id: nextId(), sport: sport, away: last.away, home: last.home, matchup: last.matchup,
                gdate: inputs.gdate || todayISO(), inputs: inputs, markets: slimMarkets(last.markets), finals: {} };
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
    out.push("THE PARLAY FOUR (one leg per game, within " + sgn(legCap(), 0) + ")");
    parlayFour(dateISO, legCap()).forEach(function (x) {
      out.push("  " + x.rank + ". " + x.row.matchup + " — " + x.mk.pick + "  " + (x.mk.p * 100).toFixed(1) + "%  " + sgn(x.mk.price, 0) +
        "  " + x.ratio.toFixed(3) + "x" + (x.band ? "  [#1: " + x.band + "]" : "") + (x.likeliest ? "  (likelier: " + x.likeliest.pick + " at " + sgn(x.likeliest.price, 0) + ")" : ""));
    });
    out.push("BEST STRAIGHT BETS (by edge)");
    bestBets(dateISO).forEach(function (x) {
      out.push("  " + x.rank + ". " + x.row.matchup + " — " + x.mk.pick + "  " + (x.mk.p * 100).toFixed(1) + "%  " + sgn(x.mk.price, 0) + "  edge " + sgn(x.mk.edge * 100, 1));
    });
    ["MLB", "WNBA"].forEach(function (sp) {
      var sl = parlayFour(dateISO, legCap(), sp), sb = bestBets(dateISO, sp);
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
  $("legCap").addEventListener("input", function () { render(); renderBoard(); renderCalib(); });
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
  try { var savedCap = parseFloat(localStorage.getItem(CAP_KEY)); if (isFinite(savedCap)) $("legCap").value = savedCap; } catch (e) {}
  if (!loadDraft()) setSport("MLB", true);
  else if ($("gdate").value === "") $("gdate").value = todayISO();
  render(); renderCard(); renderBoard(); renderCalib();
})();
</script>
