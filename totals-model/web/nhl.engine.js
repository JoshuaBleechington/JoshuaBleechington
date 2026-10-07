  /* ===== NHL BLOCK. Ported from totals/nhl.py; web/callsheet3-cases.json is
     replayed through this page against the package on every change. It sits
     OUTSIDE Call Sheet #1's engine block and changes nothing inside it: the
     goal distribution is registered by reassigning splitFor (a function
     declaration is a mutable binding in the same scope), the plausibility
     windows are added to the engine's PLAUSIBLE object, and the team table
     gets an NHL page. Everything the Python docstring says is a priori is a
     priori here too. 1 Oct 2026. ===== */
  var NHL = {
    /* measured 7 Oct 2026 on 2,624 games, the 2024-25 and 2025-26 ledgers (totals/nhl.py has each figure's story) */
    GOALS: 6.17,            // per game, both sides, empty-netters and the OT goal in (was 6.10)
    ENG: 0.39,              // expected empty-net goals a game, the lump's mean (was 0.25)
    OT: 0.23,               // P(tied after sixty): measured 0.228
    SHOTS: 28.1,            // per team per game (was 30)
    SV: 0.898,              // league save percentage: measured on the card's first 62 goalie lines (37,931 shots), 5 Oct 2026; was .905 a priori
    XG: 3.05,               // expected goals per team per game, a fallback: the slate writes the table's own mean
    PP_PER_GAME: 2.8, PP_PCT: 0.21,
    TALENT_SD: 0.008,       // spread of goalie true-talent save percentage
    RESIDUAL_SD: 2.45,      // Poisson floor: the raw spread of totals is 2.31, narrower than Poisson (was 2.55)
    P1_SHARE: 0.314, P1_PHI: 1.0,   // first-period share of regulation goals, measured (was 0.30); Poisson to the decimal
    ENG_ONE: 0.45, ENG_TWO: 0.30,   // P(empty-net goal | leading by one / by two)
    OT_COMPRESSION: 0.5,
    H2H_FULL_AT: 4, DEFAULT_PUCK_LINE: 1.5, KMAX: 25
  };
  NHL.PK_PCT = 1.0 - NHL.PP_PCT;
  NHL.REG_GOALS = NHL.GOALS - NHL.ENG - NHL.OT;
  NHL.SV_STABLE_AT = NHL.SV * (1.0 - NHL.SV) / (NHL.TALENT_SD * NHL.TALENT_SD);
  NHL.REG_PHI = (NHL.RESIDUAL_SD * NHL.RESIDUAL_SD - NHL.ENG * (1.0 - NHL.ENG) - NHL.OT * (1.0 - NHL.OT)) / NHL.REG_GOALS;
  var NHL_WEIGHTS = { market: 4.0, goalies: 1.6, xg: 1.2, special: 0.8, form: 0.6, h2h: 0.5 };   // form 0.6 measured 7 Oct 2026 (totals/nhl.py)
  NHL.OCTOBER_DELTA = 0.25;   // the October over: 6.41 scored against a 6.07 close over two seasons, 178-146 blind; half the excess, tagged
  PLAUSIBLE.nhl_total = [3.5, 9.5]; PLAUSIBLE.nhl_period = [0.5, 4.5];
  PLAUSIBLE.save_pct = [0.850, 0.960]; PLAUSIBLE.shots = [15, 45]; PLAUSIBLE.shots_faced = [0, 3000]; PLAUSIBLE.xg_rate = [1.0, 5.5];

  /* ---- the goal distribution: regulation count + empty-net lump + OT goal ---- */
  function nhlRegMean(mu) { return Math.max(0.05, mu - NHL.OT - NHL.ENG); }
  function nhlTotalPmf(mu, kmax) {
    kmax = kmax || 40;
    var mr = nhlRegMean(mu), pEng = NHL.ENG / (1.0 - NHL.OT);
    var reg = [], s = 0, k;
    for (k = 0; k <= kmax; k++) { var v = nbPmf(k, mr, NHL.REG_PHI); reg.push(v); s += v; }
    if (s > 0) reg = reg.map(function (v) { return v / s; });
    var out = [];
    for (k = 0; k <= kmax; k++) {
      var prev = k >= 1 ? reg[k - 1] : 0;
      out.push(NHL.OT * prev + (1.0 - NHL.OT) * ((1.0 - pEng) * reg[k] + pEng * prev));
    }
    return out;
  }
  function nhlSplit(line, mu) {
    if (mu <= 0) return [0, 0, 1];
    var pm = nhlTotalPmf(mu), under = 0, push = 0;
    for (var k = 0; k < pm.length; k++) { if (k < line) under += pm[k]; else if (k === line) push += pm[k]; }
    return [Math.max(0, 1 - under - push), push, under];
  }
  function nhlP1Split(line, mu) { return nbSplit(line, mu, NHL.P1_PHI); }
  /* The first-period anchor with the hold regression OFF (totals/nhl.py,
     p1_anchor). fairTotal pulls a wide-hold lean toward even because on a main
     total a wide hold means an alternate line; a first-period market carries a
     wide hold as a matter of course, so the regression had the sheet a point or
     two under the book on every period and the under always the better price:
     25 of the first 26 picks under, 10-15. Turned off 4 Oct 2026 at the user's
     call. One price or none still goes through fairTotal. */
  function nhlP1Anchor(line, op, up) {
    if (op === null || up === null) return fairTotal("NHL_P1", line, op, up);
    var o = implied(op), u = implied(up), pOver = o / (o + u);
    var lo = Math.max(0.5, line - 4), hi = line + 4;
    for (var i = 0; i < 80; i++) {
      var mid = (lo + hi) / 2, sp = nhlP1Split(line, mid);
      var live = sp[0] + sp[2], conditional = live > 0 ? sp[0] / live : 0.5;
      if (conditional < pOver) lo = mid; else hi = mid;
    }
    var mu = (lo + hi) / 2;
    return [mu, sgn(op, 0) + "/" + sgn(up, 0) + " de-vigs to " + (pOver * 100).toFixed(1) + "% over and puts fair at " + mu.toFixed(2) +
      " against the " + line + " posted. The " + ((o + u - 1) * 100).toFixed(1) + "% hold is read straight, not regressed: a first-period market " +
      "carries a wide hold as a matter of course, and regressing it had the sheet calling the under the better price on 25 of its first 26 periods. Off since 4 Oct 2026."];
  }
  var splitForBase = splitFor;
  splitFor = function (sport, line, mu) {
    if (sport === "NHL") return nhlSplit(line, mu);
    if (sport === "NHL_P1") return nhlP1Split(line, mu);
    return splitForBase(sport, line, mu);
  };

  /* ---- the goalie, as a differential --------------------------------------- */
  function svWeight(shots) {
    if (shots === null || !ok(shots, "shots_faced") || shots <= 0) return 1;
    return shots / (shots + NHL.SV_STABLE_AT);
  }
  function shrinkSv(sv, shots) { return sv === null ? null : NHL.SV + svWeight(shots) * (sv - NHL.SV); }
  /* a goalie over a league goalie, both facing the league's shots. The
     opponent's shot rate was removed 7 Oct 2026: against two seasons of
     closing totals the shot lean ran the wrong way (totals/nhl.py). */
  function goalieGap(svUsed) {
    if (svUsed === null || !ok(svUsed, "save_pct")) return null;
    return NHL.SHOTS * (NHL.SV - svUsed);
  }
  function nhlH2hWeight(base, n) { return base * Math.min(1, Math.max(0, n) / NHL.H2H_FULL_AT); }

  /* ---- the total ------------------------------------------------------------ */
  function readNhl() {
    var line = num("line");
    if (!ok(line, "nhl_total")) return null;
    var w = NHL_WEIGHTS, notes = [];
    var fa = fairTotal("NHL", line, num("op"), num("up")), anchor = fa[0];
    var estimates = [est("Market", anchor, w.market, fa[1])], deltas = [];

    var asv = num("agsv"), hsv = num("hgsv"), ash = num("agsh"), hsh = num("hgsh");
    var asf = num("asf"), hsf = num("hsf");
    var aw = svWeight(ash), hw = svWeight(hsh);
    var aUsedSv = shrinkSv(asv, ash), hUsedSv = shrinkSv(hsv, hsh);
    var haveGoalies = aUsedSv !== null && hUsedSv !== null;
    if (aUsedSv !== null || hUsedSv !== null) {
      var aU = aUsedSv !== null ? aUsedSv : NHL.SV, hU = hUsedSv !== null ? hUsedSv : NHL.SV;
      var aGap = goalieGap(aU), hGap = goalieGap(hU);
      if (aGap !== null && hGap !== null) {
        var gap = aGap + hGap, parts = [];
        if (aUsedSv !== null) parts.push("away " + asv.toFixed(3) + (aw < 1 ? " over " + ash.toFixed(0) + " shots is worth " + Math.round(aw * 100) + "% of itself, so it enters at " + aUsedSv.toFixed(3) : ""));
        if (hUsedSv !== null) parts.push("home " + hsv.toFixed(3) + (hw < 1 ? " over " + hsh.toFixed(0) + " shots is worth " + Math.round(hw * 100) + "% of itself, so it enters at " + hUsedSv.toFixed(3) : ""));
        estimates.push(est("Goalies", anchor + gap, w.goalies,
          (parts.length ? parts.join("; ") + ". " : "") + "Each goalie against the league's " + NHL.SHOTS.toFixed(1) + " shots, against a ." +
          Math.round(NHL.SV * 1000) + " goalie: " + sgn(gap) + " goals on the line. A save percentage is worth half the league prior at " +
          NHL.SV_STABLE_AT.toFixed(0) + " shots, which is why a backup's hot month cannot carry a card."));
        if ((aUsedSv !== null) !== (hUsedSv !== null)) notes.push("One goalie's save percentage is in and the other's is not; the missing side is scored as a league-average goalie. Fill in both once the starters are confirmed.");
      }
    }
    if (asf !== null || hsf !== null) notes.push("Shots for per game are <b>SHOWN, NOT SCORED</b>: against two seasons of closing totals the shot-rate lean ran the wrong way (49.1% betting with it). A team that shoots more shoots from everywhere, and the market knows it.");
    var gdv = ($("gdate") || {}).value || "", gmonth = gdv.length >= 7 ? parseInt(gdv.slice(5, 7), 10) : null;
    if (gmonth === 10) {
      var octWhy = "October: both backtest seasons scored 6.41 a game against a 6.07 closing line, the over 178-146 blind. Half the excess, " + sgn(NHL.OCTOBER_DELTA) +
        ", goes on the line this month. Tagged: it cannot buy a band, and the tile keeps October's record.";
      deltas.push(delta("October", NHL.OCTOBER_DELTA, octWhy, false));
      notes.push("<b>" + octWhy.replace("October:", "October</b>:"));
    }
    var unconfirmed = [];
    if (!checked("agconf")) unconfirmed.push("away");
    if (!checked("hgconf")) unconfirmed.push("home");
    if (haveGoalies && unconfirmed.length) notes.push("The " + unconfirmed.join(" and ") + " goalie is <b>NOT confirmed</b>. The book priced the expected starter; the one input a hockey market prices imperfectly is a late change in net. Confirm on the daily sites before betting, and re-enter the backup's line if it is the backup.");

    var st = [num("app"), num("hpp"), num("apk"), num("hpk")];
    if (st.every(function (v) { return v !== null && ok(v, "percent"); })) {
      var sgap = ((st[0] / 100 - NHL.PP_PCT) + (st[1] / 100 - NHL.PP_PCT) + (NHL.PK_PCT - st[2] / 100) + (NHL.PK_PCT - st[3] / 100)) * NHL.PP_PER_GAME;
      estimates.push(est("Special teams", anchor + sgap, w.special,
        "Power plays " + st[0].toFixed(1) + "% and " + st[1].toFixed(1) + "% against a league " + Math.round(NHL.PP_PCT * 100) + "%, kills " +
        st[2].toFixed(1) + "% and " + st[3].toFixed(1) + "% against " + Math.round(NHL.PK_PCT * 100) + "%, over " + NHL.PP_PER_GAME.toFixed(1) +
        " chances a side: " + sgn(sgap) + " goals. Sized a priori and tagged, so it cannot buy a band on its own.", false));
    } else if (st.some(function (v) { return v !== null; })) {
      notes.push("Special teams need all four figures — both power plays and both kills — and a partial set has been dropped rather than half-applied.");
    }

    /* expected goals (MoneyPuck, all situations): each side's offence against
       the other's defence per game, against the league mean of the same table.
       Tagged (totals/nhl.py); added 6 Oct 2026. */
    var xg = [num("axgf"), num("hxgf"), num("axga"), num("hxga")];
    if (xg.every(function (v) { return v !== null && ok(v, "xg_rate"); })) {
      var lgIn = num("xglg"), lg = (lgIn !== null && ok(lgIn, "xg_rate")) ? lgIn : NHL.XG;
      var xtot = (xg[0] + xg[3]) / 2 + (xg[1] + xg[2]) / 2, xgap = xtot - 2 * lg;
      estimates.push(est("Expected goals", anchor + xgap, w.xg,
        "Away " + xg[0].toFixed(2) + " for into " + xg[3].toFixed(2) + " against, home " + xg[1].toFixed(2) + " into " + xg[2].toFixed(2) + ": " +
        xtot.toFixed(2) + " expected goals against a league " + (2 * lg).toFixed(2) + " (" + (lgIn !== null ? "the table's own mean" : "assumed") + "), " +
        sgn(xgap) + " on the line. Weight " + w.xg + ", tagged: it cannot buy a band until the record says so.", false));
    } else if (xg.some(function (v) { return v !== null; })) {
      notes.push("Expected goals need all four figures — both sides' for and against — and a partial set has been dropped rather than half-applied.");
    }

    var a10 = num("al10"), h10 = num("hl10");
    if (a10 !== null && h10 !== null) {
      var avg = (a10 + h10) / 2;
      estimates.push(est("Last 10", avg, w.form, "Last-ten combined totals average " + avg.toFixed(1) + ". Measured against 2,445 closing totals: a slope of 0.14, an implied weight of 0.6, which is the weight; tagged.", false));
    }
    var hv = num("h2h"), hn = num("h2hn");
    if (hv !== null && hn) {
      estimates.push(est("Head to head (" + hn + ")", hv, nhlH2hWeight(w.h2h, hn),
        hn + " meetings averaging " + hv.toFixed(1) + "." + (hn < NHL.H2H_FULL_AT ? " Discounted to " + hn + "/" + NHL.H2H_FULL_AT + " of its weight on " + hn + " meeting(s)." : ""), false));
    }
    var b2b = [];
    var ar = num("arest"), hr = num("hrest");
    if (ar !== null && ar <= 0) b2b.push("away");
    if (hr !== null && hr <= 0) b2b.push("home");
    if (b2b.length) notes.push("Back to back for the " + b2b.join(" and ") + " side. <b>SHOWN, NOT SCORED</b>: the goalie line already carries the usual consequence (the backup), and the rest effect on the total itself is unmeasured. It is on the row so the record can split on it.");

    var tk = num("ntick"), cs = num("ncash");
    if (ok(tk, "percent") && ok(cs, "percent") && Math.abs(tk - cs) >= 20) notes.push("Over holds " + tk.toFixed(0) + "% of tickets but " + cs.toFixed(0) + "% of money. Shown, not scored, for the reason the MLB book stopped scoring it: no threshold beat a coin.");
    var opened = num("opened");
    if (opened !== null && Math.abs(opened - line) > 1e-9) notes.push("The number moved " + opened + " to " + line + " (" + sgn(line - opened, 1) + "). Not scored — the current line is the anchor and the move is already inside it.");
    return assemble("NHL", teamName("away", "NHL") || "Away", teamName("home", "NHL") || "Home", line, estimates, deltas, notes);
  }

  /* ---- the two-team distribution, with the empty net on the margin ---------- */
  function nhlRegMarginDist(lh, la) {
    var h = teamPmf(lh, NHL.REG_PHI), a = teamPmf(la, NHL.REG_PHI), dist = {};
    for (var i = 0; i < h.length; i++) {
      if (h[i] < 1e-15) continue;
      for (var j = 0; j < a.length; j++) {
        if (a[j] < 1e-15) continue;
        dist[i - j] = (dist[i - j] || 0) + h[i] * a[j];
      }
    }
    return dist;
  }
  function nhlOtHomeShare(dist) {
    var win = 0, lose = 0;
    Object.keys(dist).forEach(function (d) { d = +d; if (d > 0) win += dist[d]; else if (d < 0) lose += dist[d]; });
    var share = (win + lose) > 0 ? win / (win + lose) : 0.5;
    return 0.5 + NHL.OT_COMPRESSION * (share - 0.5);
  }
  function nhlFinalMarginDist(lh, la) {
    var reg = nhlRegMarginDist(lh, la), ot = nhlOtHomeShare(reg), out = {};
    var add = function (d, v) { out[d] = (out[d] || 0) + v; };
    Object.keys(reg).forEach(function (k) {
      var d = +k, v = reg[k];
      if (d === 0) { add(1, v * ot); add(-1, v * (1 - ot)); }
      else if (Math.abs(d) === 1) { add(d + (d > 0 ? 1 : -1), v * NHL.ENG_ONE); add(d, v * (1 - NHL.ENG_ONE)); }
      else if (Math.abs(d) === 2) { add(d + (d > 0 ? 1 : -1), v * NHL.ENG_TWO); add(d, v * (1 - NHL.ENG_TWO)); }
      else add(d, v);
    });
    return out;
  }
  function nhlPHomeWins(lh, la) {
    var dist = nhlFinalMarginDist(lh, la), p = 0;
    Object.keys(dist).forEach(function (d) { if (+d > 0) p += dist[d]; });
    return p;
  }
  function nhlSolveSplit(regTotal, pHome) {
    var lo = 0.25, hi = Math.max(0.3, regTotal - 0.25);
    for (var i = 0; i < 60; i++) {
      var mid = (lo + hi) / 2;
      if (nhlPHomeWins(mid, regTotal - mid) < pHome) lo = mid; else hi = mid;
    }
    var lh = (lo + hi) / 2;
    return [lh, regTotal - lh];
  }
  function puckLineProbs(lh, la, homeLine) {
    var dist = nhlFinalMarginDist(lh, la), cover = 0, push = 0, fail = 0;
    Object.keys(dist).forEach(function (k) {
      var x = +k + homeLine, v = dist[k];
      if (x > 1e-9) cover += v; else if (x < -1e-9) fail += v; else push += v;
    });
    return [cover, push, fail];
  }

  /* ---- the matchup ---------------------------------------------------------- */
  /* The one line the user reads before ticking the boxes: each side's goalie
     line as the sheet will score it, or that there is none. */
  function nhlGoalieSummary() {
    var el = $("goalieSummary"); if (!el) return;
    var parts = [];
    [["Away", "agsv", "agsh"], ["Home", "hgsv", "hgsh"]].forEach(function (s) {
      var sv = num(s[1]), sh = num(s[2]);
      if (sv === null) { parts.push("<b>" + s[0] + "</b>: no goalie line (league average)"); return; }
      var used = shrinkSv(sv, sh), w = svWeight(sh);
      parts.push("<b>" + s[0] + "</b> " + sv.toFixed(3) + (sh !== null ? " on " + sh.toFixed(0) + " shots" : ", shots blank") +
                 (w < 1 ? " → scored as " + used.toFixed(3) : " → trusted in full"));
    });
    el.innerHTML = parts.join(" · ") + ". Open the boxes below to change a line.";
  }
  /* ---- recent form: shown, not scored --------------------------------------
     The slate writes each side's last five finals (score, shots for and
     against, the starter, how the game ended) as JSON into the hidden
     `nhlform` box, so it rides through snapshot, restore, the draft and the
     row like any other input. Built 5 Oct 2026 at the user's request. */
  function nhlFormPanel() {
    var el = $("formPanel"); if (!el) return;
    var raw = ($("nhlform") || {}).value || "", form = null;
    try { form = raw ? JSON.parse(raw) : null; } catch (e) { form = null; }
    if (!form || (!(form.away || []).length && !(form.home || []).length)) {
      el.innerHTML = "No recent games on the row — load the slate and Fill form, and each side's last five come with it.";
      return;
    }
    var h = "";
    [["away", $("away").value || "Away"], ["home", $("home").value || "Home"]].forEach(function (s) {
      var games = form[s[0]] || [];
      if (!games.length) { h += "<p><b>" + esc(s[1]) + "</b>: no finals yet.</p>"; return; }
      var tot = 0, sf = 0, sa = 0, nSf = 0, w = 0, goalies = {}, p1f = 0, p1a = 0, nP1 = 0;
      var rows = games.map(function (g) {
        var gf = +g.gf, ga = +g.ga, res = isFinite(gf) && isFinite(ga) ? (gf > ga ? "W" : (g.end && g.end !== "REG" ? "OTL" : "L")) : "";
        if (res === "W") w++;
        if (isFinite(gf) && isFinite(ga)) tot += gf + ga;
        if (g.sf !== null && g.sf !== undefined && g.sa !== null && g.sa !== undefined) { sf += +g.sf; sa += +g.sa; nSf++; }
        if (g.goalie) goalies[g.goalie] = (goalies[g.goalie] || 0) + 1;
        var hasP1 = g.p1f !== null && g.p1f !== undefined && g.p1a !== null && g.p1a !== undefined;
        if (hasP1) { p1f += +g.p1f; p1a += +g.p1a; nP1++; }
        return "<tr><td>" + esc(String(g.date || "").slice(5)) + "</td><td>" + (g.home ? "v " : "@ ") + esc(g.opp || "?") + "</td>" +
               "<td>" + res + (g.end && g.end !== "REG" ? " (" + esc(g.end) + ")" : "") + " " + esc(g.gf) + "–" + esc(g.ga) + "</td>" +
               "<td>" + (hasP1 ? esc(g.p1f) + "–" + esc(g.p1a) : "—") + "</td>" +
               "<td>" + (g.sf !== null && g.sf !== undefined ? esc(g.sf) + "–" + esc(g.sa) : "—") + "</td><td>" + esc(g.goalie || "—") + "</td></tr>";
      });
      var names = Object.keys(goalies).sort(function (a, b) { return goalies[b] - goalies[a]; });
      var flags = [];
      if (nSf && sa / nSf >= 35) flags.push("giving up " + (sa / nSf).toFixed(1) + " shots a night");
      if (nSf && sf / nSf <= 25) flags.push("only " + (sf / nSf).toFixed(1) + " shots for");
      if (names.length > 1) flags.push("two goalies used (" + names.map(function (n) { return esc(n) + " ×" + goalies[n]; }).join(", ") + ")");
      h += "<p><b>" + esc(s[1]) + "</b> last " + games.length + ": " + w + "-" + (games.length - w) + ", " + (games.length ? (tot / games.length).toFixed(1) : "—") +
           " goals a game" + (nP1 ? ", first period " + ((p1f + p1a) / nP1).toFixed(1) + " (" + (p1f / nP1).toFixed(1) + " for, " + (p1a / nP1).toFixed(1) + " against)" : "") +
           (nSf ? ", shots " + (sf / nSf).toFixed(1) + " for / " + (sa / nSf).toFixed(1) + " against" : "") +
           (names.length ? ", in net " + names.map(function (n) { return esc(n); }).join(" and ") : "") + "." +
           (flags.length ? " <b>" + flags.join("; ") + ".</b>" : "") + "</p>" +
           "<table class=\"form\"><thead><tr><th>Date</th><th>Opp</th><th>Result</th><th>After one</th><th>Shots</th><th>In net</th></tr></thead><tbody>" + rows.join("") + "</tbody></table>";
    });
    el.innerHTML = h;
  }
  function forecastMatchupNhl() {
    nhlGoalieSummary();
    nhlFormPanel();
    var f = readNhl();
    var away = f.away, home = f.home, line = f.line;
    var op = num("op"), up = num("up"), hml = num("hml"), aml = num("aml");
    var plIn = num("pl"), plh = num("plh"), pla = num("pla");
    var p1line = num("p1line"), p1op = num("p1op"), p1up = num("p1up");
    var notes = [], markets = [];
    markets.push(totalMarket(f, line, op, up, 2));
    var anchor = f.estimates.filter(function (e) { return e.name === "Market"; })[0].total;
    var lamH = null, lamA = null;
    if (hml !== null && aml !== null) {
      var dv = devig(hml, aml), pHomeMkt = dv[0];
      var mlHold = implied(hml) + implied(aml) - 1;
      var split = nhlSolveSplit(nhlRegMean(anchor), pHomeMkt);
      var scale = nhlRegMean(f.projected) / nhlRegMean(anchor);
      lamH = split[0] * scale; lamA = split[1] * scale;
      notes.push(sgn(hml, 0) + "/" + sgn(aml, 0) + " de-vigs to <b>" + (pHomeMkt * 100).toFixed(1) + "% " + home + "</b> (" + (mlHold * 100).toFixed(1) +
        "% hold). On the market's " + nhlRegMean(anchor).toFixed(2) + " regulation goals that puts the split at <b>" + split[1].toFixed(2) + " " + away + ", " +
        split[0].toFixed(2) + " " + home + "</b>; the total forecast moves both by ×" + scale.toFixed(3) + ". The moneyline already knows the goalies, so nothing per-team moves this split — the split IS the market.");
      if (mlHold > HOLD_REFERENCE) notes.push("A " + (mlHold * 100).toFixed(1) + "% moneyline hold is wide for a main line; only " + (marketConfidence(mlHold) * 100).toFixed(0) + "% of the de-vigged lean is kept.");
      var pH = nhlPHomeWins(lamH, lamA);
      markets.push(pickOf("ml", "Moneyline",
        [sideOf(home + " ML", "HOME", pH, 0, hml), sideOf(away + " ML", "AWAY", 1 - pH, 0, aml)],
        true, "", ["Priced off the book's own moneyline, overtime and the shootout included. The only thing that can move it is the total forecast changing how often the game is tied after sixty, and that is a small thing."]));
      var homeLine = plIn !== null ? plIn : (pHomeMkt >= 0.5 ? -NHL.DEFAULT_PUCK_LINE : NHL.DEFAULT_PUCK_LINE);
      var pr = puckLineProbs(lamH, lamA, homeLine);
      markets.push(pickOf("pl", "Puck line " + home + ": " + fmtLine(homeLine),
        [sideOf(home + " " + fmtLine(homeLine), "HOME", pr[0], pr[1], plh),
         sideOf(away + " " + fmtLine(-homeLine), "AWAY", pr[2], pr[1], pla)],
        plh !== null && pla !== null, "",
        ["Derived from the total and the moneyline through the goal distribution, with the empty net on the margin: a one-goal regulation lead becomes a two-goal win " +
         Math.round(NHL.ENG_ONE * 100) + "% of the time, and an overtime win is by one and never covers −1.5. Both figures are a priori. The run line's record says to treat this as shown, not picked, until the log says otherwise."]));
    } else {
      notes.push("No moneyline entered, so there is no split and no moneyline or puck line on this card. Both prices are needed.");
    }
    if (p1line !== null) {
      if (!ok(p1line, "nhl_period")) throw new Error("first-period total out of range");
      var fa1 = nhlP1Anchor(p1line, p1op, p1up), muP1 = fa1[0];
      var est1 = [[muP1, NHL_WEIGHTS.market]], p1notes = ["Anchored on the first-period market: " + fa1[1]];
      var goalies = f.estimates.filter(function (e) { return e.name === "Goalies" || e.name === "Shot rates"; })[0];
      if (goalies) {
        var gap1 = (goalies.total - anchor) * NHL.P1_SHARE;
        est1.push([muP1 + gap1, goalies.weight]);
        p1notes.push(goalies.name + ": " + sgn(gap1) + " goals over the first period, the full-game gap scaled by the " + Math.round(NHL.P1_SHARE * 100) + "% of regulation goals a first period carries. No empty net, no overtime: a period is a plain count.");
      }
      /* first-period form from the league ledger: each club's last ten
         first-period totals, an absolute weighted like the full game's form
         and tagged the same way (totals/nhl.py). */
      var a1 = num("ap1l10"), h1 = num("hp1l10");
      if (a1 !== null || h1 !== null) {
        p1notes.push("First-period last ten: " + (a1 !== null ? a1.toFixed(2) : "—") + " and " + (h1 !== null ? h1.toFixed(2) : "—") +
          " a game, from the league ledger. <b>SHOWN, NOT SCORED</b>: measured against 2,445 first periods on 7 Oct 2026 and null (slope -0.003). A period's recent past says nothing about tonight's.");
      }
      var tw1 = est1.reduce(function (a, e) { return a + e[1]; }, 0);
      var proj1 = est1.reduce(function (a, e) { return a + e[0] * e[1]; }, 0) / tw1;
      var s1 = nhlP1Split(p1line, proj1);
      markets.push(pickOf("p1", "First period total " + p1line,
        [sideOf("P1 OVER " + p1line, "OVER", s1[0], s1[1], p1op), sideOf("P1 UNDER " + p1line, "UNDER", s1[2], s1[1], p1up)],
        p1op !== null && p1up !== null, "", p1notes.concat(["Projected " + proj1.toFixed(2) + " against " + p1line + "."])));
    }
    return { sport: "NHL", away: away, home: home, matchup: away + " @ " + home, markets: markets, lamHome: lamH, lamAway: lamA, total: f, notes: notes };
  }

  /* ---- the team table: an NHL page, same ordered first-hit-wins rule ------- */
  TEAM_PATTERNS.NHL = [
    ["Maple Leafs",    /maple|leafs?|toronto|\btor\b/],
    ["Red Wings",      /red\s*wing|detroit|\bdet\b/],
    ["Blue Jackets",   /blue\s*jacket|columbus|\bcbj\b/],
    ["Golden Knights", /golden|knights?|vegas|\bvgk\b/],
    ["Ducks",          /duck|anaheim|\bana\b/],
    ["Bruins",         /bruin|boston|\bbos\b/],
    ["Sabres",         /sabre|buffalo|\bbuf\b/],
    ["Flames",         /flame|calgary|\bcgy\b/],
    ["Hurricanes",     /hurricane|\bcanes\b|carolina|\bcar\b/],
    ["Blackhawks",     /blackhawk|\bhawks\b|chicago|\bchi\b/],
    ["Avalanche",      /avalanche|\bavs\b|colorado|\bcol\b/],
    ["Stars",          /\bstars?\b|dallas|\bdal\b/],
    ["Oilers",         /oiler|edmonton|\bedm\b/],
    ["Panthers",       /panther|florida|\bfla\b/],
    ["Kings",          /\bkings?\b|los angeles|\blak\b/],
    ["Wild",           /\bwild\b|minnesota|\bmin\b/],
    ["Canadiens",      /canadien|\bhabs\b|montreal|\bmtl\b/],
    ["Predators",      /predator|\bpreds\b|nashville|\bnsh\b/],
    ["Devils",         /devil|new jersey|\bnjd\b|\bnj\b/],
    ["Islanders",      /islander|\bisles\b|\bnyi\b/],
    ["Rangers",        /ranger|\bnyr\b/],
    ["Senators",       /senator|\bsens\b|ottawa|\bott\b/],
    ["Flyers",         /flyer|philadelphia|\bphi\b/],
    ["Penguins",       /penguin|\bpens\b|pittsburgh|\bpit\b/],
    ["Sharks",         /shark|san jose|\bsjs\b|\bsj\b/],
    ["Kraken",         /kraken|seattle|\bsea\b/],
    ["Blues",          /\bblues\b|st\.?\s*louis|\bstl\b/],
    ["Lightning",      /lightning|\bbolts\b|tampa|\btbl\b|\btb\b/],
    ["Mammoth",        /mammoth|\butah\b|\buta\b/],
    ["Canucks",        /canuck|vancouver|\bvan\b/],
    ["Capitals",       /capital|\bcaps\b|washington|\bwsh\b/],
    ["Jets",           /\bjets?\b|winnipeg|\bwpg\b/]
  ];
  var canonTeamBase = canonTeam, teamsForBase = teamsFor;
  canonTeam = function (sRaw, sport) {
    if (sport !== "NHL") return canonTeamBase(sRaw, sport);
    var s = String(sRaw === undefined || sRaw === null ? "" : sRaw).trim();
    if (!s) return "";
    var low = s.toLowerCase(), list = TEAM_PATTERNS.NHL;
    for (var i = 0; i < list.length; i++) if (list[i][1].test(low)) return list[i][0];
    return s;
  };
  teamsFor = function (sport) {
    if (sport !== "NHL") return teamsForBase(sport);
    return TEAM_PATTERNS.NHL.map(function (p) { return p[0]; }).sort();
  };
  /* ===== END NHL BLOCK ===== */
