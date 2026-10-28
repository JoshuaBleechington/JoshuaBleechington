  /* ===== TAKE BLOCK: the bets you are placing (26 Oct 2026) =====
     The user: "add a select or picked option for the props or bets I take, that way I can see on
     the page the ones I will place." A Take button sits on every priced market on the day board,
     on the pick cards and on every projected prop. It marks the bet on the stored row: a market's
     `take` keeps the side, the pick, the price and the chance as shown when it was marked (the
     board can show either side of a market, so the mark says which one); a prop's `take` is a flag.
     The marked bets for the date are listed under Taking tonight on the board and under Taking on
     the Props tab, with a copy button, and the mark rides through a slate reload and a rescore
     (carryTakes). Nothing here scores or grades anything: "What you took" in Is it working reads
     the marks against the finals the card already has, at the price shown when the bet was marked,
     one unit each. A graded row cannot be marked after the fact, so that record is of bets marked
     before the game. */
  function takeView(m) { return { key: m.key, label: m.label, pick: m.take.pick, side: m.take.side, price: m.take.price, p: m.take.p, point: m.point, book: m.book, taken: true }; }
  function storedIndexOf(row, view) {
    var ms = (row && row.markets) || [];
    for (var i = 0; i < ms.length; i++) {
      if (ms[i].key !== view.key) continue;
      if (view.key === "alt" && Math.abs(lineOf(ms[i]) - lineOf(view)) > 1e-9) continue;   // the alternate's own number names it
      return i;
    }
    return -1;
  }
  function isTaken(row, view) { var i = storedIndexOf(row, view); return i >= 0 && !!(row.markets[i].take && row.markets[i].take.side === view.side); }
  function takeBtn(row, view) {
    if (!row || !view || view.price === null || view.price === undefined) return "";
    var i = storedIndexOf(row, view); if (i < 0) return "";
    var on = isTaken(row, view);
    if (isVoid(row) || gradeMarket(view, row.finals) !== null) return on ? ' <span class="chip taken">TAKEN</span>' : "";
    return '<button type="button" class="takebtn' + (on ? ' on' : '') + '" data-take="' + row.id + '|' + i + '|' + view.side + '" title="' +
           (on ? 'Marked as a bet you are placing: click to unmark it' : 'Mark this as a bet you are placing') + '">' + (on ? '&#10003; Taking' : 'Take') + '</button>';
  }
  function toggleTake(spec) {
    var p = String(spec).split("|"), row = card.filter(function (r) { return String(r.id) === p[0]; })[0]; if (!row) return;
    var mk0 = (row.markets || [])[+p[1]]; if (!mk0) return;
    if (rowGraded(row) || isVoid(row)) { say("<b>" + esc(row.matchup) + "</b> is graded: a bet is marked before the game, not after."); return; }
    if (mk0.take && mk0.take.side === p[2]) delete mk0.take;
    else {
      var v = bothSides(mk0).filter(function (s) { return s.side === p[2]; })[0] || mk0;
      mk0.take = { side: v.side, pick: v.pick, price: v.price, p: +(+v.p).toFixed(4), at: new Date().toISOString() };
    }
    save(); renderCard(); renderBoard(); renderCalib();
  }
  /* a row's markets are rebuilt by a rescore, a second Add of the same game and a slate that fills a blank box: the marks move over by market */
  function carryTakes(oldMs, newMs) {
    (oldMs || []).forEach(function (m) {
      if (!m.take) return;
      var j = storedIndexOf({ markets: newMs }, m);
      if (j >= 0) newMs[j].take = m.take;
    });
    return newMs;
  }
  function takesOn(dateISO) {
    var out = [];
    card.forEach(function (r) {
      if ((r.gdate || "") !== dateISO || isVoid(r)) return;
      (r.markets || []).forEach(function (m, i) { if (m.take) out.push({ row: r, i: i, mk: takeView(m) }); });
    });
    return out;
  }
  function propsTakenOn(dateISO) { return (typeof propsSource === "function" ? propsSource() : []).filter(function (r) { return (r.gdate || "") === dateISO && r.take && propHas(r); }); }
  /* the simulation's calls taken on NBA rows (26 Oct 2026): the mark lives on the row as row.simTakes */
  function simTakesOn(dateISO) {
    var out = [];
    card.forEach(function (r) {
      if ((r.gdate || "") !== dateISO || isVoid(r) || r.sport !== "NBA") return;
      (r.simTakes || []).forEach(function (t) { out.push({ row: r, t: t }); });
    });
    return out;
  }
  function simTakeCard(x) {
    var t = x.t, res = nbaSimTakeRes(t, x.row), price = t.price === null || t.price === undefined ? -110 : t.price;
    return '<div class="pk taking sim" data-open="' + x.row.id + '" title="Load ' + esc(x.row.matchup) + ' into the form">' +
      '<div class="n1">TAKING · NBA · SIMULATION' + (t.at ? ' · marked ' + esc(takeWhen(t.at)) : '') + '</div>' +
      '<div class="n2">' + esc(t.pick) + '</div>' +
      '<div class="n3">' + (t.p === null || t.p === undefined ? esc(t.band) : (100 * t.p).toFixed(0) + '% by the sim · worth ' + (100 * t.worth).toFixed(0) + '%' + (t.band === "no call" ? ' (no call by its worth)' : ' · ' + esc(t.band))) +
        ' · ' + (t.price === null || t.price === undefined ? 'no price on the row (−110 assumed)' : sgn(t.price, 0) + ' needs ' + (implied(price) * 100).toFixed(1) + '%') + (res ? ' · <span class="chip ' + res + '">' + esc(res) + '</span>' : '') + '</div>' +
      '<div class="n4">' + esc(x.row.matchup) + ' · ' + esc(nbaSimTakeViewLabel(t.view)) + '</div>' +
      '<div class="n6">' + nbaSimTakeBtn(x.row, t.view, t.key, t.side) + '</div></div>';
  }
  function propTakeRes(r) { return !r.result || r.result === "graded" || r.result === "void" ? null : r.result; }
  /* a same-game pair you take (26 Oct 2026): rebuilt from its two legs, graded as the Same-game pairs tile grades every ticket */
  function pairTakeTally(s, t) {
    var res = propsPairRes(t); if (!res) return;
    if (res === "push") { s.p++; return; }
    s.n++; if (s.says !== undefined) s.says += t.chance;
    if (res === "win") { s.w++; s.units += propsPairUnits(t, res); } else { s.l++; s.units -= 1; }
  }
  function pairTakesList(dateISO) { return typeof pairTakesOn === "function" ? pairTakesOn(dateISO) : []; }
  function takeTally(s, res, price) {
    if (res === null || res === undefined || res === "invalid") return;
    if (res === "push") { s.p++; return; }
    s.n++; if (res === "win") { s.w++; s.units += payout(price); } else { s.l++; s.units -= 1; }
  }
  function takeWhen(iso) { var d = iso ? new Date(iso) : null; return d && !isNaN(d.getTime()) ? d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : ""; }
  function takeCard(x) {
    var res = gradeMarket(x.mk, x.row.finals), need = implied(x.mk.price);
    return '<div class="pk taking" data-open="' + x.row.id + '" title="Load ' + esc(x.row.matchup) + ' into the form">' +
      '<div class="n1">TAKING · ' + esc(x.row.sport) + (x.row.markets[x.i].take.at ? ' · marked ' + esc(takeWhen(x.row.markets[x.i].take.at)) : '') + '</div>' +
      '<div class="n2">' + esc(x.mk.pick) + '</div>' +
      '<div class="n3">' + (x.mk.p * 100).toFixed(1) + '% · ' + sgn(x.mk.price, 0) + ' needs ' + (need * 100).toFixed(1) + '%' + (res ? ' · <span class="chip ' + res + '">' + resText(res) + '</span>' : '') + '</div>' +
      '<div class="n4">' + esc(x.row.matchup) + ' · ' + esc(x.mk.label || x.mk.key) + '</div>' +
      '<div class="n6">' + takeBtn(x.row, x.mk) + '</div></div>';
  }
  function renderTaking(dateISO) {
    var box = $("taking"); if (!box) return;
    var bets = takesOn(dateISO), sims = simTakesOn(dateISO), ps = propsTakenOn(dateISO), prs = pairTakesList(dateISO), n = bets.length + sims.length + ps.length + prs.length;
    $("takingHead").hidden = !n; box.hidden = !n;
    if (!n) { box.innerHTML = ""; $("takingCount").textContent = ""; return; }
    var s = { n: 0, w: 0, l: 0, p: 0, units: 0 }, h = "";
    bets.forEach(function (x) { takeTally(s, gradeMarket(x.mk, x.row.finals), x.mk.price); h += takeCard(x); });
    sims.forEach(function (x) { takeTally(s, nbaSimTakeRes(x.t, x.row), x.t.price === null || x.t.price === undefined ? -110 : x.t.price); h += simTakeCard(x); });
    ps.forEach(function (r) { takeTally(s, propTakeRes(r), r.price); h += propTakeCard(r); });
    prs.forEach(function (t, i) { pairTakeTally(s, t); h += propsPairCard(t, i, true); });
    h += '<div class="pk taking sum"><div class="n1">TONIGHT</div><div class="n2">' + n + ' bet' + (n === 1 ? '' : 's') + ' marked</div>' +
         '<div class="n3">' + (s.n || s.p ? 'graded ' + s.w + '-' + s.l + (s.p ? '-' + s.p : '') + ' · ' + sgn(s.units, 2) + 'u at one unit each' : 'none graded yet · one unit each') + '</div>' +
         '<div class="n4">' + bets.length + ' on the card, ' + sims.length + ' from the simulation, ' + ps.length + ' prop' + (ps.length === 1 ? '' : 's') + (prs.length ? ', ' + prs.length + ' same-game pair' + (prs.length === 1 ? '' : 's') : '') + '</div></div>';
    box.innerHTML = h;
    $("takingCount").textContent = n + " marked";
  }
  function takingAsText(dateISO) {
    var out = ["The Super Model — taking " + gameDate(dateISO)], k = 0;
    takesOn(dateISO).forEach(function (x) {
      var res = gradeMarket(x.mk, x.row.finals);
      out.push((++k) + ". " + x.mk.pick + " " + sgn(x.mk.price, 0) + " · " + (x.mk.p * 100).toFixed(1) + "% needs " + (implied(x.mk.price) * 100).toFixed(1) + "% · " + x.row.matchup + " · " + (x.mk.label || x.mk.key) + (res ? " · " + String(res).toUpperCase() : ""));
    });
    simTakesOn(dateISO).forEach(function (x) {
      var t = x.t, res = nbaSimTakeRes(t, x.row);
      out.push((++k) + ". " + t.pick + " " + (t.price === null || t.price === undefined ? "(no price)" : sgn(t.price, 0)) + " · the simulation, " + nbaSimTakeViewLabel(t.view) + (t.p === null ? "" : ": " + (100 * t.p).toFixed(0) + "%" + (t.worth === null || t.worth === undefined ? "" : ", worth " + (100 * t.worth).toFixed(0) + "%")) + " · " + t.band + " · " + x.row.matchup + (res ? " · " + String(res).toUpperCase() : ""));
    });
    propsTakenOn(dateISO).forEach(function (r) {
      out.push((++k) + ". " + r.name + " " + r.side + " " + r.line + " " + (PROPS_LABEL[r.mk] || r.mk) + " " + sgn(r.price, 0) + " · " + (r.chance * 100).toFixed(1) + "% needs " + (r.need * 100).toFixed(1) + "% · " + r.game + (r.result ? " · " + r.result.toUpperCase() : ""));
    });
    pairTakesList(dateISO).forEach(function (t) {
      var res = propsPairRes(t);
      out.push((++k) + ". SAME-GAME PAIR " + t.legs.map(function (r) { return r.name + " " + r.side + " " + r.line + " " + (PROPS_LABEL[r.mk] || r.mk); }).join(" + ") + " " + sgn(t.price, 0) + " · both land " + (t.chance * 100).toFixed(1) + "% needs " + (t.need * 100).toFixed(1) + "% · " + t.game + (res ? " · " + res.toUpperCase() : ""));
    });
    return out.join("\n");
  }
  function copyText(text, sayFn, what) {
    var ok = function () { sayFn("Copied " + what + "."); };
    var no = function () { sayFn("The clipboard is blocked here; the text is below.<pre>" + esc(text) + "</pre>"); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(ok, no); else no();
  }
  /* the record: every marked bet that has graded, at the price shown when it was marked */
  function takenRecordHtml() {
    var mk = function () { return { n: 0, w: 0, l: 0, p: 0, says: 0, units: 0 }; }, bets = mk(), sims = mk(), pr = mk();
    card.forEach(function (r) {
      if (isVoid(r)) return;
      (r.markets || []).forEach(function (m) {
        if (!m.take) return;
        var v = takeView(m), res = gradeMarket(v, r.finals);
        if (res === null || res === "invalid") return;
        takeTally(bets, res, v.price); if (res !== "push") bets.says += v.p;
      });
      if (r.sport === "NBA") (r.simTakes || []).forEach(function (t) {
        var res = nbaSimTakeRes(t, r); if (!res) return;
        takeTally(sims, res, t.price === null || t.price === undefined ? -110 : t.price); if (res !== "push") sims.says += (t.p === null || t.p === undefined ? 0.5 : t.p);
      });
    });
    (typeof props === "undefined" ? [] : props).forEach(function (r) {
      var res = propTakeRes(r); if (!r.take || !res) return;
      takeTally(pr, res, r.price); if (res !== "push") pr.says += r.chance;
    });
    var prs = mk();
    if (typeof pairTakesAll === "function") pairTakesAll().forEach(function (t) { pairTakeTally(prs, t); });
    if (!bets.n && !bets.p && !sims.n && !sims.p && !pr.n && !pr.p && !prs.n && !prs.p) return "";
    var tile = function (label, s) {
      if (!s.n && !s.p) return "";
      var says = s.n ? s.says / s.n * 100 : 0, does = s.n ? s.w / s.n * 100 : 0;
      return '<div class="' + (s.n ? (s.units > 0 ? 'good' : s.units < 0 ? 'bad' : '') : '') + '"><p class="k">' + esc(label) + '</p><p class="v">' + s.w + '-' + s.l + (s.p ? '-' + s.p : '') + '</p>' +
             '<p class="s">' + (s.n ? 'says ' + says.toFixed(1) + '% · does ' + does.toFixed(1) + '% (±' + (100 / Math.sqrt(s.n) / 2).toFixed(1) + ') · ' + sgn(s.units, 2) + 'u' : 'pushes only') + '</p></div>';
    };
    return '<div class="subhead" data-sport="TAKEN">What you took <span class="tag">every bet marked Taking before its game, graded at the price shown when it was marked · one unit each · says is the sheet\'s chance</span></div>' +
           '<div class="calib" data-sport="TAKEN">' + tile("Game bets taken", bets) + tile("Simulation calls taken", sims) + tile("Props taken", pr) + tile("Same-game pairs taken", prs) + '</div>';
  }
  /* the buttons: caught before the card or the row underneath opens anything */
  document.addEventListener("click", function (e) {
    var t = e.target && e.target.closest ? e.target.closest("[data-take],[data-ptake],[data-stake],[data-ttake]") : null; if (!t) return;
    e.stopPropagation(); e.preventDefault();
    if (t.hasAttribute("data-take")) toggleTake(t.getAttribute("data-take"));
    else if (t.hasAttribute("data-stake")) toggleSimTake(t.getAttribute("data-stake"));
    else if (t.hasAttribute("data-ttake")) togglePairTake(t.getAttribute("data-ttake"));
    else togglePropTake(t.getAttribute("data-ptake"));
  }, true);
  /* Add puts the game on the card, and the Simulation card's greyed buttons come alive once the row exists: redraw it after the add */
  if ($("add") && $("nbaSimPanel")) $("add").addEventListener("click", function () { setTimeout(function () { if (sport === "NBA") nbaSimPanel(); }, 0); });
  if ($("taking")) {
    $("taking").addEventListener("click", function (e) {
      var t = e.target.closest("[data-open]"); if (t) { openRow(t.dataset.open); return; }
      var pr = e.target.closest("[data-pair]"); if (pr) { openPairDetail(pr.getAttribute("data-pair")); return; }
      var q = e.target.closest("[data-prop]"); if (q) openPropDetail(q.getAttribute("data-prop"));
    });
    $("takingText").addEventListener("click", function () { copyText(takingAsText($("boardDate").value || todayISO()), say, "the bets you are taking"); });
  }
