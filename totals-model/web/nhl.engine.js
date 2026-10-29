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
    P1_ALT_GAP: 0.25,               // a period line whose two prices sit this far apart in implied chance reads as an alternate number (13 Oct 2026; totals/nhl.py)
    ENG_ONE: 0.49, ENG_TWO: 0.70,   // P(empty-net goal | leading by one / by two): measured 13 Oct 2026 on 877 and 509 regulation wins (were 0.45 / 0.30 a priori; totals/nhl.py)
    OT_COMPRESSION: 0.5,
    H2H_FULL_AT: 4, DEFAULT_PUCK_LINE: 1.5, KMAX: 25
  };
  NHL.PK_PCT = 1.0 - NHL.PP_PCT;
  NHL.REG_GOALS = NHL.GOALS - NHL.ENG - NHL.OT;
  NHL.SV_STABLE_AT = NHL.SV * (1.0 - NHL.SV) / (NHL.TALENT_SD * NHL.TALENT_SD);
  NHL.REG_PHI = (NHL.RESIDUAL_SD * NHL.RESIDUAL_SD - NHL.ENG * (1.0 - NHL.ENG) - NHL.OT * (1.0 - NHL.OT)) / NHL.REG_GOALS;
  var NHL_WEIGHTS = { market: 4.0, goalies: 1.6, form: 0.6, h2h: 0.5, p1mkt: 0.5 };   // goalies 1.6 and form 0.6 measured 7 Oct 2026; special teams and expected goals out; p1mkt a priori, tagged (totals/nhl.py)
  NHL.OCTOBER_DELTA = 0.0;    // RETIRED 11 Oct 2026: the 2026 market carried the October excess (card: 6.11 closed, 6.08 scored, blind over 33-39-3 on 75)
  NHL.BACKUP_DELTA = -0.15;   // one backup in net: 0.18 under the close on 737 games (53.7%), both seasons; sized under it, tagged
  NHL.BACKUP_DELTA_COLD = -0.25;   // ...a COLD backup (his shrunk line costs > BACKUP_COLD_GAP goals): 0.44 under on 182 games, the under 57.5%
  NHL.DOG_BACKUP_LIFT = 0.05;   // the upset signal (16 Oct 2026, totals/nhl.py): the DOG with a backup in net won +7.4 points more than priced on 327 games (z 2.7, +6.3 and +8.3 by season, the dog's moneyline +39u); two-thirds of it on the dog's win chance, tagged, the moneyline pickable
  var NHL_UPSET_WATCH = { dog_b2b: "+5.7 points on 173 games (z 1.5; +5.1 and +6.6 by season)", fav_road: "+2.6 points on 931 games (z 1.6; +2.8 and +2.3 by season)" };
  NHL.BACKUP_COLD_GAP = 0.05;
  NHL.SCORING_FADE = -0.25;   // season scoring rates, FADED, tagged (13 Oct 2026): the market over-moves with them, -0.29 and -0.33 a goal of lean two seasons running, -0.38 against Pinnacle, pooled t -2.0 (totals/nhl.py)
  NHL.SCORING_MIN_GAMES = 5;
  NHL.EN_PULL = 0.40;         // empty-net habits, tagged (13 Oct 2026): both clubs' net empty-netters a game, conceded minus scored, +1.03 and +0.56 a goal of lean, pooled t 2.9; half the slope (totals/nhl.py)
  NHL.EN_MIN_GAMES = 10;
  PLAUSIBLE.nhl_total = [3.5, 9.5]; PLAUSIBLE.nhl_period = [0.5, 4.5];
  PLAUSIBLE.save_pct = [0.850, 0.960]; PLAUSIBLE.shots = [15, 45]; PLAUSIBLE.shots_faced = [0, 3000]; PLAUSIBLE.xg_rate = [1.0, 5.5];

  /* ---- the goal distribution: regulation count + empty-net lump + OT goal ---- */
  function nhlRegMean(mu) { return Math.max(0.05, mu - NHL.OT - NHL.ENG); }
  /* PARITY IN (13 Oct 2026, totals/nhl.py total_pmf): a game tied after sixty
     has an even regulation total and ends with exactly one more goal, so
     overtime lands on the odd numbers, and the empty-net goal is added only
     to the games that were not tied. Against 2,616 finals the old mixture
     put 16.3% on six goals where 10.9% landed and 15.8% on five where 22.6%
     did; the sharp-line pull found it through phantom edges at the number
     next to Pinnacle's. The tie share of an even count is the even split of
     a coin (1, 1/2, 3/8, 5/16 ...), scaled on the counts above zero so the
     tie rate is NHL.OT exactly. The mean stays mu exactly. */
  function nhlTieShare(t) {
    if (t % 2) return 0;
    var share = 1;
    for (var i = 1; i <= t / 2; i++) share *= (2 * i - 1) / (2 * i);
    return share;
  }
  function nhlTotalPmf(mu, kmax) {
    kmax = kmax || 40;
    var mr = nhlRegMean(mu), pEng = NHL.ENG / (1.0 - NHL.OT);
    var reg = [], s = 0, k;
    for (k = 0; k <= kmax; k++) { var v = nbPmf(k, mr, NHL.REG_PHI); reg.push(v); s += v; }
    if (s > 0) reg = reg.map(function (v) { return v / s; });
    var raw = reg.map(function (v, t) { return v * nhlTieShare(t); }), above = 0;
    for (k = 2; k <= kmax; k++) above += raw[k];
    var c = above > 0 ? Math.max(0, (NHL.OT - raw[0]) / above) : 0;
    var tie = reg.map(function (v, t) { return t === 0 ? raw[0] : Math.min(v, raw[t] * c); });
    var notie = reg.map(function (v, t) { return v - tie[t]; });
    var out = [];
    for (k = 0; k <= kmax; k++) {
      var tiePrev = k >= 1 ? tie[k - 1] : 0, notiePrev = k >= 1 ? notie[k - 1] : 0;
      out.push(tiePrev + (1.0 - pEng) * notie[k] + pEng * notiePrev);
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
    var anyBackup = checked("agbk") || checked("hgbk");
    if ((aUsedSv !== null || hUsedSv !== null) && anyBackup) {
      /* measured 7 Oct 2026 on 767 one-backup games: neither goalie's line had a direction against the close (totals/nhl.py) */
      notes.push("Goalies are <b>NOT SCORED</b> with a backup in net: in 767 backtest games with one, neither goalie's line had a direction against the close. The backup flag carries what did.");
    } else if (aUsedSv !== null || hUsedSv !== null) {
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
      /* retired 11 Oct 2026: the 2026 market carried the October excess (totals/nhl.py) */
      notes.push("<b>October</b>: NO seasonal delta since 11 Oct 2026. The backtest's two Octobers ran 0.34 a game over the close; the 2026 market carries it (the card's first 75 October games closed at 6.11 and scored 6.08, the blind over 33-39-3). Shown, not scored.");
    }
    var unconfirmed = [];
    if (!checked("agconf")) unconfirmed.push("away");
    if (!checked("hgconf")) unconfirmed.push("home");
    if (haveGoalies && unconfirmed.length) notes.push("The " + unconfirmed.join(" and ") + " goalie is <b>NOT confirmed</b>. The book priced the expected starter; the one input a hockey market prices imperfectly is a late change in net. Confirm on the daily sites before betting, and re-enter the backup's line if it is the backup.");

    /* a backup in net (totals/nhl.py BACKUP_DELTA): one backup, the market
       over-bumps the total, a tagged delta on the under; two, nothing moves */
    var backups = [];
    if (checked("agbk")) backups.push("away");
    if (checked("hgbk")) backups.push("home");
    if (backups.length === 1) {
      var bkSv = backups[0] === "away" ? aUsedSv : hUsedSv, bkGap = bkSv !== null ? goalieGap(bkSv) : null;
      var cold = bkGap !== null && bkGap > NHL.BACKUP_COLD_GAP, bkSize = cold ? NHL.BACKUP_DELTA_COLD : NHL.BACKUP_DELTA;
      var bkWhy = "Backup in net for the " + backups[0] + " side. Against two seasons of closing totals a game with ONE backup starting landed 0.18 under the close (737 games, the under 53.7%): the market bumps the total for a backup and bumps it too far. " +
        (cold ? "This backup reads <b>COLD</b> (his line costs " + sgn(bkGap) + " goals against a league goalie), and a cold backup over-bumped harder: 182 games landed 0.44 under, the under 57.5%. " : "") +
        sgn(bkSize) + " on the line, tagged: it cannot buy a band, and the tile keeps the under's record on these games.";
      deltas.push(delta("Backup in net", bkSize, bkWhy, false));
      notes.push("<b>Backup in net</b>" + bkWhy.slice("Backup in net".length));
    } else if (backups.length === 2) {
      notes.push("A backup in <b>both</b> nets. Measured on 105 games with no direction (the one-backup under did not carry), so nothing moves; the record will say.");
    }
    /* a Backup tick on a goalie who has most of his club's starts (13 Oct 2026: ten of
       sixteen rows ticked by hand, three of them on starters, and four of the night's
       seven picks stood on those ticks). The slate's goalie list says who the backup is. */
    var gl = null;
    try { gl = JSON.parse(txt("ngoalies") || "null"); } catch (e) { gl = null; }
    [["away", "agname", "agbk"], ["home", "hgname", "hgbk"]].forEach(function (s) {
      if (!checked(s[2]) || !gl) return;
      var nm = txt(s[1]), g = ((gl[s[0]] || []).filter(function (x) { return x.n === nm; })[0]);
      if (g && g.cs >= 3 && g.gs >= 0.5 * g.cs) {
        notes.push("<b>Backup in net is ticked for " + esc(nm) + "</b>, who has " + g.gs + " of the club's " + g.cs + " starts. The box means the club's BACKUP goalie: ticked, the goalie lines are not scored and a tagged " +
          sgn(NHL.BACKUP_DELTA) + " (" + sgn(NHL.BACKUP_DELTA_COLD) + " cold) goes on the under. Untick it unless RotoWire or CBS names a different starter, and then pick that goalie in the list instead.");
      }
    });

    /* season scoring rates, FADED (13 Oct 2026, totals/nhl.py SCORING_FADE): each
       club's goals for and against per game to date against the ledger's league
       goals a game; the market over-moves with them two seasons running, so the
       lean goes on the line with the opposite sign. All four or nothing; five
       games a side. */
    var rates = [num("agf"), num("aga"), num("hgf"), num("hga")];
    if (rates.every(function (v) { return v !== null && ok(v, "xg_rate"); })) {
      var few = [], agp = num("angp"), hgp = num("hngp");
      if (agp !== null && agp < NHL.SCORING_MIN_GAMES) few.push("away");
      if (hgp !== null && hgp < NHL.SCORING_MIN_GAMES) few.push("home");
      var lggIn = num("lgg"), lgg = (lggIn !== null && ok(lggIn, "nhl_total")) ? lggIn : NHL.GOALS;
      var rtot = (rates[0] + rates[3]) / 2 + (rates[2] + rates[1]) / 2, rgap = rtot - lgg;
      if (few.length) {
        notes.push("Scoring rates: " + rtot.toFixed(2) + " against the league's " + lgg.toFixed(2) + " (" + sgn(rgap) + "), on under " + NHL.SCORING_MIN_GAMES + " games for the " + few.join(" and ") + " side: shown, not scored until then.");
      } else {
        var rsize = NHL.SCORING_FADE * rgap;
        var rwhy = "Scoring rates: the clubs' goals for and against to date project " + rtot.toFixed(2) + " against the league's " + lgg.toFixed(2) + " (" + sgn(rgap) + "). The market over-moves with them: against two seasons of closing totals the final ran 0.29 and 0.33 of a goal the OTHER way per goal of lean (t −1.5 and −1.6, pooled −2.0), and 0.38 against Pinnacle's number. Faded at " + sgn(NHL.SCORING_FADE) + " a goal: " + sgn(rsize) + " on the line, tagged: it cannot buy a band on its own.";
        deltas.push(delta("Scoring rates, faded", rsize, rwhy, false));
        notes.push("<b>Scoring rates, faded</b>" + rwhy.slice("Scoring rates".length));
      }
    } else if (rates.some(function (v) { return v !== null; })) {
      notes.push("Scoring rates need all four figures (each side's goals for and against per game); a partial set scores nothing.");
    }

    /* empty-net habits, tagged (13 Oct 2026, totals/nhl.py EN_PULL): both clubs' net
       empty-net goals a game to date, conceded minus scored -- trailing late minus
       leading late. All four or nothing; ten games a side. */
    var en = [num("aenc"), num("aens"), num("henc"), num("hens")];
    if (en.every(function (v) { return v !== null && v >= 0 && v <= 2; })) {
      var fewEn = [], agpE = num("angp"), hgpE = num("hngp");
      if (agpE !== null && agpE < NHL.EN_MIN_GAMES) fewEn.push("away");
      if (hgpE !== null && hgpE < NHL.EN_MIN_GAMES) fewEn.push("home");
      var conceded = en[0] + en[2], scoredEn = en[1] + en[3], netEn = conceded - scoredEn;
      if (fewEn.length) {
        notes.push("Empty-net habits: a net " + sgn(netEn) + " a game (conceded minus scored, both clubs), on under " + NHL.EN_MIN_GAMES + " games for the " + fewEn.join(" and ") + " side: shown, not scored until then.");
      } else {
        var esize = NHL.EN_PULL * netEn;
        var ewhy = "Empty-net habits: between them the two clubs concede " + conceded.toFixed(2) + " empty-net goals a game and score " + scoredEn.toFixed(2) + ", a net of " + sgn(netEn) + ". A club that trails late pulls the goalie and concedes, and the market does not price the habit: against two seasons of closing totals the final ran 1.03 and 0.56 of a goal per goal of net lean (t 2.7 and 1.4, pooled 2.9). At " + sgn(NHL.EN_PULL) + " a goal, half the pooled slope: " + sgn(esize) + " on the line, tagged: it cannot buy a band on its own.";
        deltas.push(delta("Empty-net habits", esize, ewhy, false));
        notes.push("<b>Empty-net habits</b>" + ewhy.slice("Empty-net habits".length));
      }
    } else if (en.some(function (v) { return v !== null; })) {
      notes.push("Empty-net habits need all four figures (each side's empty-net goals conceded and scored per game); a partial set scores nothing.");
    }

    /* special teams: SHOWN, NOT SCORED since 7 Oct 2026 (totals/nhl.py): each
       side's power play and kill to date ran the wrong way against 2,445 closes */
    var st = [num("app"), num("hpp"), num("apk"), num("hpk")];
    if (st.some(function (v) { return v !== null; })) {
      notes.push("Special teams are <b>SHOWN, NOT SCORED</b>: each side's power play and kill to date, against two seasons of closing totals, ran the wrong way (slopes −0.20 and −0.51; both halves negative both seasons). The market has them.");
    }

    /* expected goals (MoneyPuck, all situations): each side's offence against
       the other's defence per game, against the league mean of the same table.
       Tagged (totals/nhl.py); added 6 Oct 2026. */
    /* SHOWN, NOT SCORED since 7 Oct 2026: this season's xG to date, built the slate's way, ran the wrong way
       against 1,223 closes of 2024-25 (slope -0.31), and last season's flipped sign between seasons (totals/nhl.py) */
    var xg = [num("axgf"), num("hxgf"), num("axga"), num("hxga")];
    if (xg.every(function (v) { return v !== null && ok(v, "xg_rate"); })) {
      var lgIn = num("xglg"), lg = (lgIn !== null && ok(lgIn, "xg_rate")) ? lgIn : NHL.XG;
      var xtot = (xg[0] + xg[3]) / 2 + (xg[1] + xg[2]) / 2, xgap = xtot - 2 * lg;
      notes.push("Expected goals " + xtot.toFixed(2) + " against a league " + (2 * lg).toFixed(2) + " (" + sgn(xgap) + "). <b>SHOWN, NOT SCORED</b>: built the slate's way against 1,223 closing totals, this season's xG to date ran the wrong way (slope −0.31), and last season's flipped sign between seasons. The market has it.");
    } else if (xg.some(function (v) { return v !== null; })) {
      notes.push("Expected goals are shown, not scored, and a partial set (not all four figures) is not even shown.");
    }

    var a10 = num("al10"), h10 = num("hl10");
    if (a10 !== null && h10 !== null) {
      var avg = (a10 + h10) / 2;
      estimates.push(est("Last 10", avg, w.form, "Last-ten combined totals average " + avg.toFixed(1) + ". Measured against 2,445 closing totals: a slope of 0.14, an implied weight of 0.6, which is the weight; tagged.", false));
    }
    var hv = num("h2h"), hn = num("h2hn");
    if (hv !== null && hn) {
      /* shown, not scored since 7 Oct 2026: null against 814 closing totals (totals/nhl.py) */
      notes.push("Head to head: " + hn + " meeting(s) averaging " + hv.toFixed(1) + ". <b>SHOWN, NOT SCORED</b>: measured against 814 closing totals and null (slope 0.02).");
    }
    var b2b = [];
    var ar = num("arest"), hr = num("hrest");
    if (ar !== null && ar <= 0) b2b.push("away");
    if (hr !== null && hr <= 0) b2b.push("home");
    if (b2b.length) notes.push("Back to back for the " + b2b.join(" and ") + " side. <b>SHOWN, NOT SCORED</b>: the goalie line already carries the usual consequence (the backup), and the rest effect on the total itself is unmeasured. It is on the row so the record can split on it.");

    /* the first-period market as a second read of the game (12 Oct 2026, totals/nhl.py):
       its de-vigged mean over the measured period share, plus the empty net and
       overtime, is what the period price implies for sixty minutes; weight 0.5, tagged */
    var p1l = num("p1line"), p1o = num("p1op"), p1u = num("p1up");
    if (p1l !== null && p1o !== null && p1u !== null && ok(p1l, "nhl_period")) {
      var gap1 = Math.abs(implied(p1o) - implied(p1u));
      if (gap1 >= NHL.P1_ALT_GAP) {
        /* an alternate number is not read at all (13 Oct 2026): the de-vigged read off one sat
           +0.24 above the full-game anchor on 16 games against +0.08 off a main line on 81 */
        notes.push("The first-period line " + p1l + " at " + sgn(p1o, 0) + "/" + sgn(p1u, 0) + " reads as an <b>ALTERNATE</b> number: its two prices sit " + Math.round(gap1 * 100) +
          " points of implied chance apart, where a main period line sits within 15. The main first-period total is the number most books post near even. " +
          "<b>NOT READ</b>: a de-vigged alternate reads the game a quarter of a goal high (measured on the card, 13 Oct 2026), so the first-period market is left out of the projection " +
          "and the period row is priced against a number the market does not treat as its main line. Retype the main line and its prices, or ignore the first-period row.");
      } else {
        var a1 = nhlP1Anchor(p1l, p1o, p1u), implied1 = a1[0] / NHL.P1_SHARE + NHL.ENG + NHL.OT;
        var why1 = "The period line: " + a1[1] + " Over the first period's " + Math.round(NHL.P1_SHARE * 100) + "% share of regulation goals, plus the empty net and overtime, that is " +
          implied1.toFixed(2) + " for sixty minutes against the market's " + anchor.toFixed(2) + ". Weight " + w.p1mkt + ", tagged: a second market's read of the same game, untested against any history.";
        estimates.push(est("First-period market", implied1, w.p1mkt, why1, false));
        notes.push("<b>First-period market</b> as a second read of the game: " + why1);
      }
    }
    /* the last five from the form panel, read against tonight's line: shown, not
       scored -- the last ten carries the scored form; this names the trend */
    var rawForm = txt("nhlform"), form5 = null;   // txt() reads the row being re-scored, not the form on screen
    try { form5 = rawForm ? JSON.parse(rawForm) : null; } catch (e) { form5 = null; }
    if (form5) {
      var trend = [];
      [["away", teamName("away", "NHL") || "Away"], ["home", teamName("home", "NHL") || "Home"]].forEach(function (s) {
        var gs = (form5[s[0]] || []).filter(function (g) { return isFinite(+g.gf) && isFinite(+g.ga); });
        if (!gs.length) return;
        var tots = gs.map(function (g) { return +g.gf + +g.ga; }), over = tots.filter(function (t) { return t > line; }).length, avg = tots.reduce(function (a, b) { return a + b; }, 0) / tots.length;
        trend.push(esc(s[1]) + " games averaged " + avg.toFixed(1) + " (" + over + " of " + gs.length + " over tonight's " + line + ")");
      });
      if (trend.length) notes.push("Last five: " + trend.join("; ") + ". Shown, not scored; the last ten carries the scored form.");
    }
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
  /* THE TIE RATE IS SCALED (13 Oct 2026, totals/nhl.py final_margin_dist): two
     independent counts tie 16-18% at these means; hockey ties 22.7%. The tie
     mass is set to NHL.OT and the decided mass scaled to fill the rest, the
     same scaling the total's parity fix applies, so the margin and the goal
     distributions tie at one rate. The moneyline stays anchored on the market
     through nhlSolveSplit; the puck line moves toward the dog +1.5. */
  function nhlFinalMarginDist(lh, la) {
    var reg = nhlRegMarginDist(lh, la), ot = nhlOtHomeShare(reg), out = {};
    var tieRaw = reg[0] || 0, cTie = (tieRaw > 0 && tieRaw < 1) ? NHL.OT / tieRaw : 1, cDec = (tieRaw > 0 && tieRaw < 1) ? (1 - NHL.OT) / (1 - tieRaw) : 1;
    var add = function (d, v) { out[d] = (out[d] || 0) + v; };
    Object.keys(reg).forEach(function (k) {
      var d = +k, v = reg[k];
      if (d === 0) { v *= cTie; add(1, v * ot); add(-1, v * (1 - ot)); return; }
      v *= cDec;
      if (Math.abs(d) === 1) { add(d + (d > 0 ? 1 : -1), v * NHL.ENG_ONE); add(d, v * (1 - NHL.ENG_ONE)); }
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
    [["Away", "agsv", "agsh", "agname", "agstart", "agok"], ["Home", "hgsv", "hgsh", "hgname", "hgstart", "hgok"]].forEach(function (s) {
      var sv = num(s[1]), sh = num(s[2]), nm = ($(s[3]) || {}).value || "", st = ($(s[4]) || {}).value || "", ok = ($(s[5]) || {}).value || "";
      var who = nm ? " <b>" + esc(nm) + "</b>" : "";
      if (sv === null) { parts.push("<b>" + s[0] + "</b>" + who + ": no goalie line (league average)"); return; }
      var used = shrinkSv(sv, sh), w = svWeight(sh);
      parts.push("<b>" + s[0] + "</b>" + who + " " + sv.toFixed(3) + (sh !== null ? " on " + sh.toFixed(0) + " shots" : ", shots blank") +
                 (w < 1 ? " → scored as " + used.toFixed(3) : " → trusted in full") +
                 (st ? (ok === "no" ? " — <b>" + esc(st) + " started</b>, not this line" : ok === "yes" ? " — started, as carded" : " — " + esc(st) + " started") : ""));
    });
    el.innerHTML = parts.join(" · ") + ". Pick who is in net above, or open the boxes below to change a line.";
  }
  /* ---- the goalie picker (11 Oct 2026) ---------------------------------------
     The slate writes every goalie on each club into the hidden `ngoalies` box
     with the line the sheet would score (n name, sv, sh shots, gs starts, cs
     the club's starts, ls last season's line). Picking one fills his line,
     writes his name on the row, and sets the Backup box by the rule (under
     30% of the club's starts, ten starts in). 42 of the first 150 goalie boxes
     on the card had carried the other goalie's line. */
  function nhlGoaliePicker() {
    var raw = ($("ngoalies") || {}).value || "", data = null;
    try { data = raw ? JSON.parse(raw) : null; } catch (e) { data = null; }
    [["away", "agpick", "agname", "agsv", "agsh", "agbk"], ["home", "hgpick", "hgname", "hgsv", "hgsh", "hgbk"]].forEach(function (s) {
      var sel = $(s[1]); if (!sel) return;
      var list = (data && data[s[0]]) || [], nameBox = $(s[2]), current = nameBox ? nameBox.value : "";
      var key = JSON.stringify(list);
      if (sel.getAttribute("data-key") !== key) {
        sel.setAttribute("data-key", key);
        var h = '<option value="">' + (list.length ? "— type the line by hand —" : "— load the slate —") + '</option>';
        list.forEach(function (g) {
          var line = g.sv !== null && g.sv !== undefined ? Number(g.sv).toFixed(3) + " on " + g.sh : "no line";
          var starts = g.cs ? g.gs + " of " + g.cs + " starts" : (g.ls ? "last season's line" : "no starts yet");
          h += '<option value="' + esc(g.n) + '">' + esc(g.n) + " — " + line + " (" + starts + ")</option>";
        });
        sel.innerHTML = h;
      }
      sel.value = list.some(function (g) { return g.n === current; }) ? current : "";
      sel.disabled = !list.length || (typeof formLocked !== "undefined" && formLocked);
      if (!sel.getAttribute("data-bound")) {
        sel.setAttribute("data-bound", "1");
        sel.addEventListener("change", function () {
          var picked = list.filter(function (g) { return g.n === sel.value; })[0];
          var raw2 = ($("ngoalies") || {}).value || "", d2 = null;
          try { d2 = raw2 ? JSON.parse(raw2) : null; } catch (e) { d2 = null; }
          picked = ((d2 && d2[s[0]]) || []).filter(function (g) { return g.n === sel.value; })[0];
          if (nameBox) nameBox.value = picked ? picked.n : "";
          if (picked) {
            $(s[3]).value = picked.sv !== null && picked.sv !== undefined ? Number(picked.sv).toFixed(3) : "";
            $(s[4]).value = picked.sh ? String(picked.sh) : "";
            var bk = $(s[5]);
            if (bk) bk.checked = !!(picked.cs && picked.cs >= NHL.BACKUP_MIN_STARTS && picked.gs < NHL.BACKUP_SHARE * picked.cs && !picked.ls);
          }
          [s[3], s[4]].forEach(function (id) { $(id).dispatchEvent(new Event("input", { bubbles: true })); });
          if ($(s[5])) $(s[5]).dispatchEvent(new Event("change", { bubbles: true }));
        });
      }
    });
  }
  NHL.BACKUP_SHARE = 0.30; NHL.BACKUP_MIN_STARTS = 10;   // the slate's rule (slate.py nhl_is_backup), applied again on a pick
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
  /* ---- the context card (14 Oct 2026, at the user's word: "little bits of info like
     Bruins have the 4th worst defense in the league"). The slate writes each club's
     league ranks as JSON into the hidden `nhlctx` box, each line with a status
     (scored / faded / shown / label) and the tag that says what the sheet did with
     the fact. Rendered, never read by the engine. */
  var CTX_BADGE = { scored: "scored", faded: "faded", shown: "shown", label: "label" };
  function nhlCtxPanel() {
    var el = $("ctxPanel"); if (!el) return;
    var raw = ($("nhlctx") || {}).value || "", ctx = null;
    try { ctx = raw ? JSON.parse(raw) : null; } catch (e) { ctx = null; }
    if (!ctx || !ctx.length) {
      el.innerHTML = "No context on the row — load the slate and Fill form, and the lines come with it.";
      return;
    }
    var order = { scored: 0, faded: 1, shown: 2, label: 3 };
    var items = ctx.slice().sort(function (a, b) { return (order[a.s] || 0) - (order[b.s] || 0); });
    el.innerHTML = '<ul class="ctx">' + items.map(function (c) {
      var s = CTX_BADGE[c.s] ? c.s : "shown";
      return '<li class="ctx-' + s + '"><span class="cbadge">' + CTX_BADGE[s] + '</span> <span class="ctext">' + esc(c.t || "") + '</span>' +
             (c.tag ? ' <span class="ctag">' + esc(c.tag) + '</span>' : '') + '</li>';
    }).join("") + '</ul>';
  }
  function altBandFor(p) { for (var i = 0; i < BANDS.length; i++) if (p >= BANDS[i][0]) return BANDS[i][1]; return NOBET; }
  function nhlAltMarket(f) {
    if (!f || f.side === undefined || f.projected === undefined || f.projected === null) return null;
    var alts;
    try { alts = altLines({ total: f }, txt("odds")); } catch (e) { return null; }
    if (!alts || !alts.length) return null;
    var best = null;
    alts.forEach(function (a) {
      if (a.side !== f.side || a.edge === null || a.edge === undefined || a.edge <= 0) return;
      if ((TIERS[altBandFor(a.p)] || 0) < 2) return;   // STRONG BET or MAX BET only
      if (!best || a.edge > best.edge + 1e-9) best = a;
    });
    if (!best) return null;
    var opp = alts.filter(function (a) { return a.side !== best.side && Math.abs(a.point - best.point) < 1e-9; })[0];
    var sp = splitFor("NHL", best.point, f.projected);
    var mine = sideOf(best.side + " " + best.point, best.side, best.side === "OVER" ? sp[0] : sp[2], sp[1], best.price);
    var theirs = sideOf(FLIP[best.side] + " " + best.point, FLIP[best.side], best.side === "OVER" ? sp[2] : sp[0], sp[1], opp ? opp.price : null);
    var band = altBandFor(mine.p);
    return { key: "alt", label: "Alternate total " + best.point, pick: mine.pick, side: mine.side, p: mine.p, pPush: mine.pPush, price: mine.price,
             breakeven: mine.breakeven, edge: mine.edge, ev: mine.ev, fair: priceFor(mine.p), anchored: true, band: band, band1: band, side1: mine.side,
             point: best.point, book: best.book,
             notes: ["An alternate number at " + bookName(best.book) + ", priced by the same projection of " + f.projected.toFixed(2) + " split at " + best.point + ": " +
                     mine.pick + " " + (mine.p * 100).toFixed(1) + "% against " + sgn(best.price, 0) + ", which needs " + (mine.breakeven * 100).toFixed(1) + "%. " +
                     "<b>The band is the chance, as on the main number; at this price the book already asks for most of it, so the edge is the figure to read.</b> " +
                     "Shown here, on the board and on its own record line; never the pick, never a parlay leg. The Line box stays on the main number."],
             other: { pick: theirs.pick, p: theirs.p, price: theirs.price, edge: theirs.edge } };
  }
  function forecastMatchupNhl() {
    nhlGoaliePicker();
    nhlGoalieSummary();
    nhlFormPanel();
    nhlCtxPanel();
    var f = readNhl();
    var away = f.away, home = f.home, line = f.line;
    var op = num("op"), up = num("up"), hml = num("hml"), aml = num("aml");
    var plIn = num("pl"), plh = num("plh"), pla = num("pla");
    var p1line = num("p1line"), p1op = num("p1op"), p1up = num("p1up");
    var notes = [], markets = [];
    /* the simulation decides the totals (29 Oct 2026): the sheet's own number becomes the note beside the sim's call */
    var simD = nhlSim(), simLines = simD ? nhlSimLinesFrom({ line: txt("line"), p1line: txt("p1line"), pl: txt("pl"), odds: txt("odds") }) : null;
    var tm = totalMarket(f, line, op, up, 2), simTotal = simD ? nhlSimDecide(simD, simLines, "total") : null;
    if (simTotal) tm = nhlSimMarket(tm, simTotal, "total", line, op, up, "Full-game total " + line);
    markets.push(tm);
    nhlSimPanel();
    /* the alternate totals (19 Oct 2026, the user: "add the strong bets, max bets to the
       cards"): every alternate number the books post on the sheet's side, priced by the
       same projection split; the one that reads STRONG BET or MAX BET with an edge
       becomes a market of its own, "alt" -- on the rail, the board and its own record
       line, never the pick and never a leg. The band is the chance, as on the main
       number; at a heavy price the book already asks for most of it, so the edge is the
       figure to read, and the record decides. */
    var altM = nhlAltMarket(f);
    if (altM) markets.push(altM);
    var anchor = f.estimates.filter(function (e) { return e.name === "Market"; })[0].total;
    var lamH = null, lamA = null;
    if (hml !== null && aml !== null && hml >= 140) notes.push("A big road favourite (the home side +140 or longer): two seasons of closing totals ran under 55.5% in these games (277 of them). Watched, not scored.");
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
      /* the upset signal (totals/nhl.py DOG_BACKUP_LIFT): the DOG's backup in net lifts the dog, tagged; the watch names the rest */
      var favHome = pHomeMkt >= 0.5, dog = favHome ? away : home, fav = favHome ? home : away;
      var aBk = checked("agbk"), hBk = checked("hgbk"), dogBk = favHome ? aBk : hBk, favBk = favHome ? hBk : aBk, lifted = !!(dogBk && !favBk);
      var mlNotes = ["Priced off the book's own moneyline, overtime and the shootout included. The only thing that can move it is the total forecast changing how often the game is tied after sixty, and that is a small thing."];
      if (lifted) {
        pH = favHome ? pH - NHL.DOG_BACKUP_LIFT : pH + NHL.DOG_BACKUP_LIFT;
        mlNotes.push("<b>UPSET SIGNAL</b>: " + esc(dog) + " start a backup and the market has moved the price for it too far. Against two seasons of closing moneylines the dog with a backup in net won 158 of 327 against 134 priced (+7.4 points, z 2.7, +6.3 and +8.3 by season; the dog's moneyline +39 units). " +
          sgn(NHL.DOG_BACKUP_LIFT * 100, 0) + " points to " + esc(dog) + ", tagged: this side is pickable on the record's own line.");
      }
      var aRest = num("arest"), hRest = num("hrest"), dogRest = favHome ? aRest : hRest, favRest = favHome ? hRest : aRest, watch = [];
      if (lifted) watch.push(esc(dog) + " start a backup (scored, " + sgn(NHL.DOG_BACKUP_LIFT * 100, 0) + " points)");
      if (dogRest !== null && dogRest <= 0) watch.push(esc(dog) + " on a back to back: dogs won " + NHL_UPSET_WATCH.dog_b2b);
      if (!favHome) watch.push(esc(fav) + " favoured on the road: dogs won " + NHL_UPSET_WATCH.fav_road);
      if (favBk && !dogBk) watch.push(esc(fav) + " start a backup: NOT an upset signal, the dog won 1.3 points LESS than priced (440 games); the market over-bumps the dog");
      if (favRest !== null && favRest <= 0 && !(dogRest !== null && dogRest <= 0)) watch.push(esc(fav) + " on a back to back: NOT an upset signal, the dog won 3.0 points less than priced (390 games); the market over-bumps the dog");
      if (watch.length) notes.push("<b>Upset watch</b>, " + esc(dog) + " at " + sgn(favHome ? aml : hml, 0) + ": " + watch.join("; ") + ". " + (lifted ? "The scored signal is the dog's own backup; the rest are watched on the record." : "Watched, not scored: nothing here moves the dog's chance."));
      var mlm = pickOf("ml", "Moneyline",
        [sideOf(home + " ML", "HOME", pH, 0, hml), sideOf(away + " ML", "AWAY", 1 - pH, 0, aml)],
        true, "", mlNotes);
      mlm.informed = lifted;
      markets.push(mlm);
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
      var p1m = pickOf("p1", "First period total " + p1line,
        [sideOf("P1 OVER " + p1line, "OVER", s1[0], s1[1], p1op), sideOf("P1 UNDER " + p1line, "UNDER", s1[2], s1[1], p1up)],
        p1op !== null && p1up !== null, "", p1notes.concat(["Projected " + proj1.toFixed(2) + " against " + p1line + "."]));
      var simP1 = simD ? nhlSimDecide(simD, simLines, "p1") : null;
      if (simP1) { p1m.side1 = p1m.side; p1m = nhlSimMarket(p1m, simP1, "p1", p1line, p1op, p1up, "First period total " + p1line); }
      markets.push(p1m);
    }
    return { sport: "NHL", away: away, home: home, matchup: away + " @ " + home, markets: markets, lamHome: lamH, lamAway: lamA, total: f, notes: notes,
             period: (typeof proj1 !== "undefined" ? proj1 : null) };
  }

  /* ===== the hockey simulation (29 Oct 2026, slate/nhlsim.py). The user: "a simulation for the NHL model too, same
     set up as the NBA one, focused on total goals, first period totals and full game totals", and "the NHL simulation
     will be the final decision for the recommendation on the totals; taking in consideration all elements, the
     simulation holds the heaviest weight." The slate plays each game shot by shot 10,000 times, twice (the sim's own
     view; anchored to the carded book's number and price), and the row carries both as histograms in the nhlsim box.
     The page reads the chance of any line off them, shows the Simulation card, lets any call be taken, and lets the
     sim DECIDE the full-game and first-period totals: the sheet's own projection is shown beside it, not scored. The
     chance shown is the sim's raw count; the WORTH is that chance shrunk by what the replay of 2025-26 found it worth
     against the closes (nhlsim.SHRINK, carried in the box), and the band reads the worth. ===== */
  var NHL_SIM_DECIDES = { total: "own", p1: "own" };   // the view that decides each total (tools_backtest_nhl_sim.py)
  var NHL_SIM_BAND_WORDS = { STRONG: "STRONG BET", BET: "BET", LEAN: "LEAN" };
  /* the replay of 2025-26 (tools_backtest_nhl_sim.py, 1,312 games): the own view's lean on the full-game total is worth a
     quarter of itself against Pinnacle's close (slope 0.25; the leans at 58%+ went 207-174, and with the market's own
     price in the model the sim's weight was nil); on DraftKings' first-period 1.5 it is worth 61% (slope 0.61), the
     anchored view 78%, and the book's price itself read sharper (slope 1.52; the own view against the price by three
     points went 49-56). The rest had no closes to measure and keep a priori halves. A row run before this carries its
     own shrink in the box; these stand in when the box has none. */
  var NHL_SIM_SHRINK_DEFAULT = { total: 0.75, p1: 0.39, p1_mkt: 0.22, team: 0.5, ml: 0.5, pl: 0.5, period: 0.5 };
  var NHL_SIM_REPLAY = "the replay of 2025-26: the own view's full-game lean worth a quarter of itself against Pinnacle's close, its first-period lean 61% against DraftKings' 1.5, the book's price the sharper read";
  function nhlSimRaw() {
    var v = "";
    try { v = txt("nhlsim"); } catch (e) { v = ""; }   // the row being re-scored, else the form
    if (!v) { var el = $("nhlsim"); v = el ? el.value : ""; }
    return v || "";
  }
  function nhlSimParse(raw) { var d = null; try { d = raw ? JSON.parse(raw) : null; } catch (e) { d = null; } return d && d.own ? d : null; }
  function nhlSim() { return nhlSimParse(nhlSimRaw()); }
  function nhlHistOver(h, line) {
    if (!h || line === null || line === undefined || line === "" || isNaN(+line)) return null;
    var n = 0, over = 0, push = 0, L = +line;
    h.c.forEach(function (c, i) { n += c; var v = h.lo + i; if (v > L) over += c; else if (v === L) push += c; });
    if (!n) return null;
    var live = n - push;
    return { over: live ? over / live : 0.5, push: push / n, n: n };
  }
  function nhlHistQ(h, p) {
    if (!h) return null;
    var n = h.c.reduce(function (a, b) { return a + b; }, 0), acc = 0;
    for (var i = 0; i < h.c.length; i++) { acc += h.c[i]; if (acc >= p * n) return h.lo + i; }
    return h.lo + h.c.length - 1;
  }
  function nhlHistMean(h) {
    if (!h) return null;
    var n = 0, s = 0;
    h.c.forEach(function (c, i) { n += c; s += c * (h.lo + i); });
    return n ? s / n : null;
  }
  /* the worth: the raw chance pulled toward a coin by the market's shrink (a fraction: 0.5 keeps half the lean) */
  function nhlSimWorth(p, kind, shrink) {
    var s = (shrink || {})[kind]; if (s === undefined || s === null) s = NHL_SIM_SHRINK_DEFAULT[kind]; if (s === undefined || s === null) s = 0.5;
    return Math.max(0, Math.min(1, 0.5 + (p - 0.5) * (1 - s)));
  }
  function nhlSimBand(worth, bands) {
    var c = Math.max(worth, 1 - worth), b = bands || [[0.62, "STRONG"], [0.58, "BET"], [0.55, "LEAN"]];
    for (var i = 0; i < b.length; i++) if (c >= b[i][0] - 1e-9) return b[i][1];
    return "no call";
  }
  /* the team totals' main line on each side from the row's odds JSON, the carded book first (the point whose two prices sit closest) */
  function nhlTeamTotalLine(oddsRaw, side) {
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
  function nhlSimLinesFrom(inputs) {
    var oddsRaw = inputs.odds || "";
    return { total: blank(inputs.line) ? null : +inputs.line, p1: blank(inputs.p1line) ? null : +inputs.p1line, pl: blank(inputs.pl) ? null : +inputs.pl,
             away_tt: nhlTeamTotalLine(oddsRaw, "AWAY"), home_tt: nhlTeamTotalLine(oddsRaw, "HOME") };
  }
  function nhlSimLinesFromForm() { return nhlSimLinesFrom({ line: $("line").value, p1line: $("p1line").value, pl: $("pl").value, odds: ($("odds") || {}).value || "" }); }
  /* every call the row's lines allow, from one view's histograms: {key, view, label, line, side, p, worth, band, push} */
  function nhlSimCalls(sim, lines, view) {
    var H = sim[view]; if (!H) return [];
    var out = [], bands = sim.bands, shrink = sim.shrink || {};
    var add = function (key, kind, label, line, r, first, second) {
      if (!r) return;
      var p = r.over, side = p >= 0.5 ? first : second, prob = p >= 0.5 ? p : 1 - p, worth = nhlSimWorth(prob, kind, shrink);
      out.push({ key: key, view: view, label: label, line: line, side: side, p: prob, worth: worth, band: nhlSimBand(worth, bands), push: r.push });
    };
    add("total", "total", "Full-game total", lines.total, nhlHistOver(H.total, lines.total), "OVER", "UNDER");
    add("p1", view === "mkt" && (shrink.p1_mkt !== undefined || NHL_SIM_SHRINK_DEFAULT.p1_mkt !== undefined) ? "p1_mkt" : "p1", "First period", lines.p1, nhlHistOver(H.p && H.p[0], lines.p1), "OVER", "UNDER");
    if (lines.pl !== null && lines.pl !== undefined && !isNaN(+lines.pl)) add("pl", "pl", "Puck line (home)", +lines.pl, nhlHistOver(H.margin, -(+lines.pl)), "HOME", "AWAY");
    if (view === "own") add("ml", "ml", "Moneyline", null, nhlHistOver(H.margin, 0), "HOME", "AWAY");
    if (lines.away_tt) add("away_total", "team", "Away team total", lines.away_tt.line, nhlHistOver(H.away, lines.away_tt.line), "OVER", "UNDER");
    if (lines.home_tt) add("home_total", "team", "Home team total", lines.home_tt.line, nhlHistOver(H.home, lines.home_tt.line), "OVER", "UNDER");
    return out;
  }
  /* the decision on a total: the deciding view's call at the row's line, or null when the sim or the line is missing */
  function nhlSimDecide(sim, lines, key) {
    var view = NHL_SIM_DECIDES[key] || "own";
    if (!sim[view]) view = "own";
    return nhlSimCalls(sim, lines, view).filter(function (c) { return c.key === key; })[0] || null;
  }
  /* the market built from the sim's decision: the chance is the WORTH (the shrunk count), the band reads it, the sheet's
     own read rides along as a note and in m.sheet; the better price can still be the other side, as on every market */
  function nhlSimMarket(sheet, dec, key, line, op, up, label) {
    var push = dec.push || 0, pO = dec.side === "OVER" ? dec.worth : 1 - dec.worth;
    var pre = key === "p1" ? "P1 " : "";
    var band = dec.band === "no call" ? "NO BET" : (NHL_SIM_BAND_WORDS[dec.band] || dec.band);
    var sheetSide = sheet ? (sheet.side1 || sheet.side) : null, sheetBand = sheet ? (sheet.band1 || sheet.band || "") : "";
    var sheetP = sheet ? (sheet.side1 && sheet.side1 !== sheet.side && sheet.other ? sheet.other.p : sheet.p) : null;
    var notes = ["<b>The simulation decides this " + (key === "p1" ? "first-period" : "full-game") + " total</b> (29 Oct 2026): its " + (dec.view === "own" ? "own view" : "market-anchored view") +
                 " puts the <b>" + esc(dec.side) + "</b> at " + (100 * dec.p).toFixed(1) + "% raw, worth <b>" + (100 * dec.worth).toFixed(1) + "%</b> after the replay's shrink (" +
                 (key === "p1" ? "the first-period lean kept 61% of itself against DraftKings' 1.5 over 1,311 games of 2025-26, and the book's price read sharper, so the price decides the side where they differ"
                               : "the full-game lean kept a quarter of itself against Pinnacle's close over 1,250 games of 2025-26: the leans at 58% and up went 207-174, and the close already carried the rest") + "): " + esc(band) + "." +
                 (sheet ? " The sheet's own number says " + esc(sheetSide) + (sheetP !== null && sheetP !== undefined ? " " + (100 * sheetP).toFixed(1) + "%" : "") + (sheetBand ? " (" + esc(sheetBand) + ")" : "") +
                          (sheetSide && sheetSide !== dec.side ? ": <b>they disagree</b>, and the sim's call stands; the record keeps both." : ": shown beside it, not scored.") : "")];
    var m = pickOf(key, label, [sideOf(pre + "OVER " + line, "OVER", pO * (1 - push), push, op), sideOf(pre + "UNDER " + line, "UNDER", (1 - pO) * (1 - push), push, up)],
                   true, band === "NO BET" ? "" : band, notes.concat(sheet && sheet.notes ? sheet.notes.slice(0, 1) : []));
    m.band1 = band; m.side1 = dec.side; m.decided = "sim"; m.simView = dec.view; m.simRaw = +dec.p.toFixed(4); m.simWorth = +dec.worth.toFixed(4);
    m.sheet = { side: sheetSide, band: sheetBand, p: sheetP === null || sheetP === undefined ? null : +(+sheetP).toFixed(4) };
    if (m.side !== dec.side) {
      m.band = "";
      m.notes.push("The simulation names <b>" + esc(dec.side) + " " + line + "</b> (" + esc(band) + "). This side is picked on PRICE, not likelihood: the book is charging so much for the " + dec.side.toLowerCase() + " that the " + m.side.toLowerCase() + " is the better bet. The sim's band stays with the sim's side.");
    }
    return m;
  }
  function nhlSimChip(c) {
    if (!c) return '<span class="dim">—</span>';
    var cls = c.band === "no call" ? "simno" : c.band === "LEAN" ? "simlean" : c.band === "BET" ? "simbet" : "simstrong";
    return '<span class="simchip ' + cls + '"><b>' + esc(c.side) + '</b> ' + (100 * c.p).toFixed(0) + '%</span>';
  }
  function nhlSimPanel() {
    var el = $("nhlSimPanel"); if (!el) return;
    var sim = nhlSimParse(($("nhlsim") || {}).value || "");
    if (!sim) { el.innerHTML = "No simulation on the row — load the slate and Fill form, and the game's runs come with it."; return; }
    var away = teamName("away", "NHL") || "Away", home = teamName("home", "NHL") || "Home";
    var lines = nhlSimLinesFromForm(), own = sim.own, mkt = sim.mkt;
    var calls = { own: {}, mkt: {} };
    nhlSimCalls(sim, lines, "own").forEach(function (c) { calls.own[c.key] = c; });
    if (mkt) nhlSimCalls(sim, lines, "mkt").forEach(function (c) { calls.mkt[c.key] = c; });
    var fmt2 = function (x) { return x === null || x === undefined ? "?" : (+x).toFixed(2); };
    var mA = nhlHistMean(own.away), mH = nhlHistMean(own.home), mg = nhlHistMean(own.margin), p1m = nhlHistMean(own.p && own.p[0]);
    var tile = function (k, v, s, cls) { return '<div class="simtile' + (cls ? ' ' + cls : '') + '"><div class="k">' + k + '</div><div class="v">' + v + '</div>' + (s ? '<div class="s">' + s + '</div>' : '') + '</div>'; };
    var h = '<div class="simtiles">' +
            tile("Total", fmt2(nhlHistMean(own.total)), 'median ' + nhlHistQ(own.total, 0.5) + ' · middle half ' + nhlHistQ(own.total, 0.25) + '–' + nhlHistQ(own.total, 0.75)) +
            tile("First period", fmt2(p1m), 'scoreless ' + (100 * ((nhlHistOver(own.p[0], 0) || {}).push || 0)).toFixed(0) + '% · over 1.5 ' + (100 * ((nhlHistOver(own.p[0], 1.5) || {}).over || 0)).toFixed(0) + '%') +
            tile("Margin", esc(mg >= 0 ? home : away) + ' by ' + fmt2(Math.abs(mg)), esc(away) + ' ' + fmt2(mA) + ' · ' + esc(home) + ' ' + fmt2(mH) + ' · ' + esc(home) + ' wins ' + (100 * ((nhlHistOver(own.margin, 0) || {}).over || 0)).toFixed(0) + '%') +
            tile("Overtime", (100 * (own.ot || 0)).toFixed(0) + '%', 'the shootout ' + (100 * (own.so || 0)).toFixed(0) + '% · empty-netters ' + fmt2(own.en)) + '</div>';
    h += '<div class="simmeta"><b>' + String(sim.runs).replace(/\B(?=(\d{3})+(?!\d))/g, ",") + ' games</b>, the sim\'s own view. ' +
         (sim.anchor ? 'Anchored to ' + esc(sim.anchor.book) + '\'s ' + esc(String(sim.anchor.line)) + ' (' + esc(String(sim.anchor.op)) + '/' + esc(String(sim.anchor.up)) + ')' + (sim.anchor.p_home !== null && sim.anchor.p_home !== undefined ? ' and a ' + (100 * sim.anchor.p_home).toFixed(0) + '% home moneyline' : '') + ' for the market view.' : 'No odds run for this game when the slate ran: no market view.') +
         ' <b>The sim decides the full-game and first-period totals</b> from its ' + (NHL_SIM_DECIDES.total === "own" ? 'own view' : 'market-anchored view') + '.</div>';
    var takeRow = nhlSimTakeRow();
    var cell = function (c) {
      if (!c) return '<span class="dim">—</span>';
      return nhlSimChip(c) + '<div class="simsub">' + (c.band !== "no call" ? esc(c.band) + ' · ' : '') + 'worth ' + (100 * c.worth).toFixed(0) + '%</div>' +
             '<div class="simtake">' + nhlSimTakeBtn(takeRow, c.view, c.key, c.side) + '</div>';
    };
    h += '<table class="form simtab"><thead><tr><th>Market</th><th>The sim\'s own view</th><th>Anchored to the market</th></tr></thead><tbody>';
    [["total", "Full-game total", lines.total, true], ["p1", "First period", lines.p1, true], ["pl", "Puck line (home)", lines.pl, false], ["ml", "Moneyline", null, false],
     ["away_total", esc(away) + " team total", lines.away_tt ? lines.away_tt.line : null, false], ["home_total", esc(home) + " team total", lines.home_tt ? lines.home_tt.line : null, false]].forEach(function (m) {
      var first = '<div class="mkname">' + m[1] + (m[3] ? ' <span class="tag">the sim decides</span>' : '') + '</div>';
      if (m[2] === null || m[2] === undefined) {
        if (m[0] !== "ml") first += '<div class="mkline dim">no line on the row' + (/_total$/.test(m[0]) ? ' (the odds run brings it)' : '') + '</div>';
      } else {
        first += '<div class="mkline">' + esc(String(m[2]));
        if (/_total$/.test(m[0])) { var tt = m[0] === "away_total" ? lines.away_tt : lines.home_tt; first += ' <span class="dim">' + esc(tt.book) + ' ' + (tt.op > 0 ? '+' : '') + tt.op + '/' + (tt.up > 0 ? '+' : '') + tt.up + '</span>'; }
        first += '</div>';
      }
      h += '<tr><td>' + first + '</td><td>' + cell(calls.own[m[0]]) + '</td><td>' + (m[0] === "ml" ? '<span class="dim">the own view\'s</span>' : cell(calls.mkt[m[0]])) + '</td></tr>';
    });
    h += '</tbody></table>';
    var V = mkt || own, tag = mkt ? "anchored to the market" : "the own view";
    h += '<table class="form simq"><thead><tr><th>Means, ' + tag + '</th><th>P1</th><th>P2</th><th>P3</th><th>Regulation</th><th>' + esc(away) + '</th><th>' + esc(home) + '</th></tr></thead><tbody><tr><td class="dim">' +
         'the first period ' + (100 * nhlHistMean(V.p[0]) / Math.max(1e-9, nhlHistMean(V.reg))).toFixed(1) + '% of regulation</td>' +
         (V.p || []).map(function (q) { return '<td>' + fmt2(nhlHistMean(q)) + '</td>'; }).join('') +
         '<td>' + fmt2(nhlHistMean(V.reg)) + '</td><td>' + fmt2(nhlHistMean(V.away)) + '</td><td>' + fmt2(nhlHistMean(V.home)) + '</td></tr></tbody></table>';
    var pa = sim.prof && sim.prof.away, ph = sim.prof && sim.prof.home;
    if (pa && ph) {
      var side = function (p, nick) {
        return esc(nick) + ' shots ×' + (+p.rf).toFixed(2) + ' for / ×' + (+p.ra).toFixed(2) + ' against, quality ×' + (+p.qf).toFixed(2) + ' / ×' + (+p.qa).toFixed(2) + ', PP ×' + (+p.ppr).toFixed(2) + ', PK ×' + (+p.pkr).toFixed(2) +
               ', minors ×' + (+p.pen).toFixed(2) + (p.b2b ? ', back to back' : '') + ' (' + p.n + ' games)' + (p.gk_shots ? '; ' + esc(p.gk_name || 'the goalie') + ' ' + (+p.gk).toFixed(3) + ' goals against expected on ' + p.gk_shots + ' shots' : '; no goalie line, a league goalie');
      };
      h += '<div class="simprof dim">Profiles, against the league: ' + side(pa, away) + ' · ' + side(ph, home) +
           (sim.crew && Math.abs(sim.crew - 1) >= 0.01 ? ' · the crew\'s whistle ×' + (+sim.crew).toFixed(2) + (sim.refs && sim.refs.length ? ' (' + sim.refs.map(function (r) { return esc(r[0]) + ' ' + (+r[2]).toFixed(1) + ' a game'; }).join(', ') + ')' : '') : ' · no crew named') +
           (sim.credit ? ' · ' + esc(sim.credit) : '') + '</div>';
    }
    el.innerHTML = h;
  }
  /* the calls you take (the mark lives on the card row as row.simTakes, as the NBA's) */
  function nhlSimTakeRow() {
    var away = teamName("away", "NHL"), home = teamName("home", "NHL"), gdate = $("gdate").value;
    if (!away || !home) return null;
    return card.filter(function (r) { return r.sport === "NHL" && sameGame(r, { sport: "NHL", gdate: gdate, away: away, home: home }); })[0] || null;
  }
  function nhlSimTakeId(view, key, side) { return view + "|" + key + "|" + side; }
  function nhlSimTakeOf(row, view, key, side) { var id = nhlSimTakeId(view, key, side); return ((row && row.simTakes) || []).filter(function (t) { return t.id === id; })[0] || null; }
  function nhlSimTakeBtn(row, view, key, side) {
    if (!row) return '<button type="button" class="takebtn off" disabled title="Add the game to the card first (Add, or Fill form from the slate and Add); the mark lives on the card row">Take</button>';
    var t = nhlSimTakeOf(row, view, key, side);
    if (isVoid(row) || rowGraded(row)) return t ? '<span class="chip taken">TAKEN</span>' : '';
    return '<button type="button" class="takebtn' + (t ? ' on' : '') + '" data-stake="' + row.id + '|' + view + '|' + key + '|' + side + '" title="' +
           (t ? 'Marked as a bet you are placing: click to unmark it' : 'Mark this call as a bet you are placing') + '">' + (t ? '&#10003; Taking' : 'Take') + '</button>';
  }
  function nhlSimPriceOf(key, side, lines, inp) {
    var v = key === "total" ? (side === "OVER" ? inp.op : inp.up) : key === "p1" ? (side === "OVER" ? inp.p1op : inp.p1up) : key === "pl" ? (side === "HOME" ? inp.plh : inp.pla)
          : key === "ml" ? (side === "HOME" ? inp.hml : inp.aml) : (function () { var tt = key === "away_total" ? lines.away_tt : lines.home_tt; return tt ? (side === "OVER" ? tt.op : tt.up) : null; })();
    return v === null || v === undefined || v === "" || isNaN(+v) ? null : +v;
  }
  function nhlSimPickText(key, side, line, away, home) {
    if (key === "total") return "Total " + side + " " + line;
    if (key === "p1") return "First period " + side + " " + line;
    if (key === "pl") return (side === "HOME" ? home + " " + fmtLine(+line) : away + " " + fmtLine(-(+line)));
    if (key === "ml") return (side === "HOME" ? home : away) + " ML";
    return (key === "away_total" ? away : home) + " team total " + side + " " + line;
  }
  /* toggleSimTake (the NBA block) hands an NHL row here; returns true when the row changed */
  function nhlToggleSimTake(row, view, key, side, id) {
    if (nhlSimTakeOf(row, view, key, side)) { row.simTakes = row.simTakes.filter(function (t) { return t.id !== id; }); return true; }
    var sim = nhlSimParse(($("nhlsim") || {}).value || ""), lines = nhlSimLinesFromForm();
    var c = sim ? nhlSimCalls(sim, lines, view).filter(function (x) { return x.key === key && x.side === side; })[0] : null;
    if (!c) { say("That call is not on the card as shown now; put the line back and take it again."); return false; }
    var inp = { op: $("op").value, up: $("up").value, p1op: $("p1op").value, p1up: $("p1up").value, plh: $("plh").value, pla: $("pla").value, hml: $("hml").value, aml: $("aml").value };
    var away = teamName("away", "NHL") || row.away, home = teamName("home", "NHL") || row.home;
    row.simTakes = (row.simTakes || []).concat([{ id: id, view: view, key: key, side: side, line: c.line, price: nhlSimPriceOf(key, side, lines, inp),
      p: +(+c.p).toFixed(4), worth: +(+c.worth).toFixed(4), band: c.band, pick: nhlSimPickText(key, side, c.line, away, home), at: new Date().toISOString() }]);
    return true;
  }
  function nhlSimTakeRes(t, row) {
    var fin = (row && row.finals) || {};
    if (fin.void) return null;
    var fa = parseFloat(fin.fa), fh = parseFloat(fin.fh);
    if (!isFinite(fa) || !isFinite(fh)) return null;
    var cmp = function (v, line, over) { if (v === line) return "push"; return ((v > line) === over) ? "win" : "loss"; };
    if (t.key === "total") return cmp(fa + fh, +t.line, t.side === "OVER");
    if (t.key === "p1") { var p1a = parseFloat(fin.f5a), p1h = parseFloat(fin.f5h); if (!isFinite(p1a) || !isFinite(p1h)) return null; return cmp(p1a + p1h, +t.line, t.side === "OVER"); }
    if (t.key === "pl") { var m = fh - fa + +t.line; if (m === 0) return "push"; return ((m > 0) === (t.side === "HOME")) ? "win" : "loss"; }
    if (t.key === "ml") { if (fa === fh) return "push"; return ((fh > fa) === (t.side === "HOME")) ? "win" : "loss"; }
    if (t.key === "away_total") return cmp(fa, +t.line, t.side === "OVER");
    if (t.key === "home_total") return cmp(fh, +t.line, t.side === "OVER");
    return null;
  }
  function nhlSimUnits(price, win) { var p = +price; if (!p || isNaN(p)) p = -110; return win ? (p > 0 ? p / 100 : 100 / -p) : -1; }
  /* the record: every call at LEAN or better from either view on graded rows, says against does; and the totals the sim decided */
  function nhlSimRecordHtml() {
    var rows = card.filter(function (r) { return r.sport === "NHL" && rowGraded(r) && r.inputs && r.inputs.nhlsim; });
    if (!rows.length) return '';
    var T = {}, n = 0, D = { total: { n: 0, w: 0, units: 0, says: 0, agree: 0, sheetW: 0, sheetN: 0 }, p1: { n: 0, w: 0, units: 0, says: 0, agree: 0, sheetW: 0, sheetN: 0 } }, dn = 0;
    rows.forEach(function (r) {
      var fin = r.finals || {}, fa = +fin.fa, fh = +fin.fh, p1 = (fin.f5a !== undefined && fin.f5a !== "" && fin.f5h !== undefined && fin.f5h !== "") ? (+fin.f5a + +fin.f5h) : null;
      var sim = nhlSimParse(r.inputs.nhlsim); if (!sim) return;
      var lines = nhlSimLinesFrom(r.inputs);
      (r.markets || []).forEach(function (m) {
        if (m.decided !== "sim" || !m.side1) return;
        var landed = m.key === "p1" ? p1 : fa + fh, line = lineOf(m);
        if (landed === null || !isFinite(line) || landed === line) return;
        var won = (landed > line) === (m.side1 === "OVER"), d = D[m.key]; if (!d) return;
        var price = m.side1 === "OVER" ? (m.key === "p1" ? r.inputs.p1op : r.inputs.op) : (m.key === "p1" ? r.inputs.p1up : r.inputs.up);
        d.n++; d.w += won ? 1 : 0; d.units += nhlSimUnits(price, won); d.says += m.simWorth || 0.5; dn++;
        if (m.sheet && m.sheet.side) { d.sheetN++; if ((landed > line) === (m.sheet.side === "OVER")) d.sheetW++; if (m.sheet.side === m.side1) d.agree++; }
      });
      ["own", "mkt"].forEach(function (view) {
        nhlSimCalls(sim, lines, view).forEach(function (c) {
          if (c.band === "no call") return;
          var won = null, price = -110;
          if (c.key === "total") { if (fa + fh === c.line) return; won = (fa + fh > c.line) === (c.side === "OVER"); price = c.side === "OVER" ? r.inputs.op : r.inputs.up; }
          else if (c.key === "p1") { if (p1 === null || p1 === c.line) return; won = (p1 > c.line) === (c.side === "OVER"); price = c.side === "OVER" ? r.inputs.p1op : r.inputs.p1up; }
          else if (c.key === "pl") { var mg = fh - fa + c.line; if (mg === 0) return; won = (mg > 0) === (c.side === "HOME"); price = c.side === "HOME" ? r.inputs.plh : r.inputs.pla; }
          else if (c.key === "ml") { if (fa === fh) return; won = (fh > fa) === (c.side === "HOME"); price = c.side === "HOME" ? r.inputs.hml : r.inputs.aml; }
          else if (c.key === "away_total" || c.key === "home_total") {
            var g = c.key === "away_total" ? fa : fh, tt = c.key === "away_total" ? lines.away_tt : lines.home_tt;
            if (g === c.line) return;
            won = (g > c.line) === (c.side === "OVER"); price = c.side === "OVER" ? tt.op : tt.up;
          }
          if (won === null) return;
          var k = view + "|" + c.key + "|" + c.band;
          var d = T[k] || (T[k] = { view: view, key: c.key, band: c.band, n: 0, w: 0, says: 0, units: 0 });
          d.n++; d.w += won ? 1 : 0; d.says += c.p; d.units += nhlSimUnits(price, won); n++;
        });
      });
    });
    if (!n && !dn) return '';
    var order = { total: 0, p1: 1, pl: 2, ml: 3, away_total: 4, home_total: 5 }, bandOrder = { STRONG: 0, BET: 1, LEAN: 2 },
        label = { total: "Full-game total", p1: "First period", pl: "Puck line", ml: "Moneyline", away_total: "Away team total", home_total: "Home team total" };
    var h = '<div class="simrec"><div class="calibhead">SIMULATION · says against does, every call at LEAN or better</div>';
    if (dn) {
      h += '<div class="simrecview">The totals the sim decided <span class="tag">the row\'s pick on the total and the first period, from the sim; the sheet\'s own read beside it</span></div><table class="form simrectab"><thead><tr><th>Market</th><th>Record</th><th>Says</th><th>Does</th><th>Units</th><th>The sheet alone</th><th>Agreed</th></tr></thead><tbody>';
      ["total", "p1"].forEach(function (k) {
        var d = D[k]; if (!d.n) return;
        var cls = d.units > 0 ? "good" : d.units < 0 ? "bad" : "";
        h += '<tr><td>' + label[k] + '</td><td>' + d.w + '-' + (d.n - d.w) + '</td><td>' + (100 * d.says / d.n).toFixed(1) + '%</td><td class="' + cls + '">' + (100 * d.w / d.n).toFixed(1) + '%</td><td class="' + cls + '">' + (d.units >= 0 ? '+' : '') + d.units.toFixed(1) + 'u</td>' +
             '<td>' + (d.sheetN ? d.sheetW + '-' + (d.sheetN - d.sheetW) : '—') + '</td><td>' + (d.sheetN ? (100 * d.agree / d.sheetN).toFixed(0) + '%' : '—') + '</td></tr>';
      });
      h += '</tbody></table>';
    }
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
    h += '<div class="note dim">A call is the sim\'s side on the line the row carried whose WORTH (the raw chance shrunk by what the replay found it worth) reads LEAN (55%) or better; "says" is the sim\'s own chance, "does" the share that landed. ' + esc(NHL_SIM_REPLAY) + '. The sim decides the full-game and first-period totals on every hockey row that carries a run; the sheet\'s own read is kept beside it so the record can say which of the two was right.</div></div>';
    return h;
  }
  /* ===== end of the hockey simulation ===== */

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
