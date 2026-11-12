  /* ===== TAKE BLOCK: the bets you are placing (26 Oct 2026) =====
     The user: "add a select or picked option for the props or bets I take, that way I can see on
     the page the ones I will place." A Take button sits on every priced market on the day board,
     on the pick cards and on every projected prop. It marks the bet on the stored row: a market's
     `take` keeps the side, the pick, the price and the chance as shown when it was marked (the
     board can show either side of a market, so the mark says which one); a prop's `take` was a flag,
     and from 12 Nov 2026 the mark keeps the prop's side, line, price, chance and band too (`took`, in
     the props block), so a props file loaded after the mark does not re-read the bet.
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
  function propsTakenOn(dateISO) { return (typeof propsSource === "function" ? propsSource() : []).filter(function (r) { return (r.gdate || "") === dateISO && r.take && propHas(r); }).map(propTook); }   // each as it was marked (12 Nov 2026)
  /* the simulation's calls taken on NBA rows (26 Oct 2026): the mark lives on the row as row.simTakes */
  function simTakesOn(dateISO) {
    var out = [];
    card.forEach(function (r) {
      if ((r.gdate || "") !== dateISO || isVoid(r) || r.sport !== "NBA") return;
      (r.simTakes || []).forEach(function (t) { out.push({ row: r, t: t }); });
    });
    return out;
  }
  function simTakeResOf(t, row) { return nbaSimTakeRes(t, row); }
  function simTakeBtnOf(row, view, key, side) { return nbaSimTakeBtn(row, view, key, side); }
  function simTakeCard(x) {
    var t = x.t, res = simTakeResOf(t, x.row), price = t.price === null || t.price === undefined ? -110 : t.price;
    return '<div class="pk taking sim" data-open="' + x.row.id + '" title="Load ' + esc(x.row.matchup) + ' into the form">' +
      '<div class="n1">TAKING · ' + esc(x.row.sport) + ' · SIMULATION' + (t.at ? ' · marked ' + esc(takeWhen(t.at)) : '') + '</div>' +
      '<div class="n2">' + esc(t.pick) + '</div>' +
      '<div class="n3">' + (t.p === null || t.p === undefined ? esc(t.band) : (100 * t.p).toFixed(0) + '% by the sim' + (t.worth === null || t.worth === undefined ? '' : ' · worth ' + (100 * t.worth).toFixed(0) + '%') + (t.band === "no call" ? ' (no call by its worth)' : ' · ' + esc(t.band))) +
        ' · ' + (t.price === null || t.price === undefined ? 'no price on the row (−110 assumed)' : sgn(t.price, 0) + ' needs ' + (implied(price) * 100).toFixed(1) + '%') + (res ? ' · <span class="chip ' + res + '">' + esc(res) + '</span>' : '') + '</div>' +
      '<div class="n4">' + esc(x.row.matchup) + ' · ' + esc(nbaSimTakeViewLabel(t.view)) + '</div>' +
      '<div class="n6">' + simTakeBtnOf(x.row, t.view, t.key, t.side) + '</div></div>';
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
  /* a two- or three-leg ticket you take (11 Nov 2026): kept on its rows with what each leg read at the app, graded on those lines */
  function t3Word(n) { return n === 2 ? "two" : "three"; }
  function t3TakesList(dateISO) { return typeof propsT3TakesOn === "function" ? propsT3TakesOn(dateISO) : []; }
  function t3TakeTally(s, t) {
    var res = propsT3Res(t); if (!res || res === "void") return;
    if (res === "push") { s.p++; return; }
    s.n++; if (s.says !== undefined) s.says += t.chance;
    if (res === "win") { s.w++; s.units += propsT3Units(t, res); } else { s.l++; s.units -= 1; }
  }
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
    var bets = takesOn(dateISO), sims = simTakesOn(dateISO), ps = propsTakenOn(dateISO), prs = pairTakesList(dateISO), t3s = t3TakesList(dateISO), n = bets.length + sims.length + ps.length + prs.length + t3s.length;
    $("takingHead").hidden = !n; box.hidden = !n;
    if (!n) { box.innerHTML = ""; $("takingCount").textContent = ""; return; }
    var s = { n: 0, w: 0, l: 0, p: 0, units: 0 }, h = "";
    bets.forEach(function (x) { takeTally(s, gradeMarket(x.mk, x.row.finals), x.mk.price); h += takeCard(x); });
    sims.forEach(function (x) { takeTally(s, simTakeResOf(x.t, x.row), x.t.price === null || x.t.price === undefined ? -110 : x.t.price); h += simTakeCard(x); });
    ps.forEach(function (r) { takeTally(s, propTakeRes(r), r.price); h += propTakeCard(r); });
    prs.forEach(function (t, i) { pairTakeTally(s, t); h += propsPairCard(t, i, true); });
    t3s.forEach(function (t, i) { t3TakeTally(s, t); h += propsT3Card(t, i, true); });
    h += '<div class="pk taking sum"><div class="n1">TONIGHT</div><div class="n2">' + n + ' bet' + (n === 1 ? '' : 's') + ' marked</div>' +
         '<div class="n3">' + (s.n || s.p ? 'graded ' + s.w + '-' + s.l + (s.p ? '-' + s.p : '') + ' · ' + sgn(s.units, 2) + 'u at one unit each' : 'none graded yet · one unit each') + '</div>' +
         '<div class="n4">' + bets.length + ' on the card, ' + sims.length + ' from the simulation, ' + ps.length + ' prop' + (ps.length === 1 ? '' : 's') + (prs.length ? ', ' + prs.length + ' same-game pair' + (prs.length === 1 ? '' : 's') : '') +
         [2, 3].map(function (k) { var c = t3s.filter(function (t) { return t.legs.length === k; }).length; return c ? ', ' + c + ' ' + t3Word(k) + '-leg ticket' + (c === 1 ? '' : 's') : ''; }).join("") + '</div></div>';
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
      var t = x.t, res = simTakeResOf(t, x.row);
      out.push((++k) + ". " + t.pick + " " + (t.price === null || t.price === undefined ? "(no price)" : sgn(t.price, 0)) + " · the simulation, " + nbaSimTakeViewLabel(t.view) + (t.p === null ? "" : ": " + (100 * t.p).toFixed(0) + "%" + (t.worth === null || t.worth === undefined ? "" : ", worth " + (100 * t.worth).toFixed(0) + "%")) + " · " + t.band + " · " + x.row.matchup + (res ? " · " + String(res).toUpperCase() : ""));
    });
    propsTakenOn(dateISO).forEach(function (r) {
      out.push((++k) + ". " + r.name + " " + r.side + " " + r.line + " " + (PROPS_LABEL[r.mk] || r.mk) + " " + sgn(r.price, 0) + " · " + (r.chance * 100).toFixed(1) + "% needs " + (r.need * 100).toFixed(1) + "% · " + r.game + (r.result ? " · " + r.result.toUpperCase() : ""));
    });
    pairTakesList(dateISO).forEach(function (t) {
      var res = propsPairRes(t);
      out.push((++k) + ". SAME-GAME PAIR " + t.legs.map(function (r) { return r.name + " " + r.side + " " + r.line + " " + (PROPS_LABEL[r.mk] || r.mk); }).join(" + ") + " " + sgn(t.price, 0) + " · both land " + (t.chance * 100).toFixed(1) + "% needs " + (t.need * 100).toFixed(1) + "% · " + t.game + (res ? " · " + res.toUpperCase() : ""));
    });
    t3TakesList(dateISO).forEach(function (t) {
      var res = propsT3Res(t);
      out.push((++k) + ". " + t.legs.length + "-LEG TICKET at " + bookName(t.app) + ": " + t.legs.map(function (l) { return propsT3LegText(l) + " " + sgn(l.price, 0); }).join(" + ") + " · pays " + sgn(t.price, 0) + " · " + (t.legs.length === 2 ? "both" : "all three") + " land " + (t.chance * 100).toFixed(1) + "% needs " + (t.need * 100).toFixed(1) + "%" + (res ? " · " + res.toUpperCase() : ""));
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
        var res = simTakeResOf(t, r); if (!res) return;
        takeTally(sims, res, t.price === null || t.price === undefined ? -110 : t.price); if (res !== "push") sims.says += (t.p === null || t.p === undefined ? 0.5 : t.p);
      });
    });
    (typeof props === "undefined" ? [] : props).forEach(function (r0) {
      if (!r0.take) return;
      var r = propTook(r0), res = propTakeRes(r); if (!res) return;   // as it was marked: its own line, price and chance
      takeTally(pr, res, r.price); if (res !== "push") pr.says += r.chance;
    });
    var prs = mk(), t3r = { 2: mk(), 3: mk() };
    if (typeof pairTakesAll === "function") pairTakesAll().forEach(function (t) { pairTakeTally(prs, t); });
    if (typeof propsT3TakesAll === "function") propsT3TakesAll().forEach(function (t) { t3TakeTally(t3r[t.legs.length], t); });
    if (!bets.n && !bets.p && !sims.n && !sims.p && !pr.n && !pr.p && !prs.n && !prs.p && !t3r[2].n && !t3r[2].p && !t3r[3].n && !t3r[3].p) return "";
    var tile = function (label, s) {
      if (!s.n && !s.p) return "";
      var says = s.n ? s.says / s.n * 100 : 0, does = s.n ? s.w / s.n * 100 : 0;
      return '<div class="' + (s.n ? (s.units > 0 ? 'good' : s.units < 0 ? 'bad' : '') : '') + '"><p class="k">' + esc(label) + '</p><p class="v">' + s.w + '-' + s.l + (s.p ? '-' + s.p : '') + '</p>' +
             '<p class="s">' + (s.n ? 'says ' + says.toFixed(1) + '% · does ' + does.toFixed(1) + '% (±' + (100 / Math.sqrt(s.n) / 2).toFixed(1) + ') · ' + sgn(s.units, 2) + 'u' : 'pushes only') + '</p></div>';
    };
    var h = '<div class="subhead" data-sport="TAKEN">What you took <span class="tag">every bet marked Taking before its game, graded at the price shown when it was marked · one unit each · says is the sheet\'s chance</span></div>' +
            '<div class="calib" data-sport="TAKEN">' + tile("Game bets taken", bets) + tile("Simulation calls taken", sims) + tile("Props taken", pr) + tile("Same-game pairs taken", prs) + tile("Two-leg tickets taken", t3r[2]) + tile("Three-leg tickets taken", t3r[3]) + '</div>';
    /* your picks (3 Nov 2026, the user: "is there a way to have the props that I select taken be graded or tracked so I can
       see how I'm picking the bets?"): every marked bet that has graded, night by night with the sheet's own BET and LEAN
       props that night beside it, the props you took by side, band, market and price, and the list of every pick, newest
       first. Says is the sheet's chance on what you took; a gap between says and does here that the sheet's own tiles do
       not show is selection, the picks you choose from its list landing less (or more) often than their chances say */
    var picks = [], payOf = function (price, res) { return res === "win" ? payout(price) : res === "loss" ? -1 : 0; };
    card.forEach(function (r) {
      if (isVoid(r)) return;
      (r.markets || []).forEach(function (m) {
        if (!m.take) return;
        var v = takeView(m), res = gradeMarket(v, r.finals);
        if (res === null || res === "invalid") return;
        picks.push({ d: r.gdate || "", kind: "game bet", text: v.pick + " · " + r.matchup, p: v.p, price: v.price, res: res, units: payOf(v.price, res) });
      });
      if (r.sport === "NBA") (r.simTakes || []).forEach(function (t) {
        var res = simTakeResOf(t, r); if (!res) return;
        var price = t.price === null || t.price === undefined ? -110 : t.price;
        picks.push({ d: r.gdate || "", kind: "simulation call", text: t.pick + " · " + r.matchup, p: t.p === null || t.p === undefined ? 0.5 : t.p, price: price, res: res, units: payOf(price, res) });
      });
    });
    (typeof props === "undefined" ? [] : props).forEach(function (r0) {
      if (!r0.take) return;
      var r = propTook(r0), res = propTakeRes(r); if (!res) return;
      picks.push({ d: r.gdate || "", kind: "prop", text: r.name + " " + r.side + " " + r.line + " " + (PROPS_LABEL[r.mk] || r.mk) + " · " + r.game, p: r.chance, price: r.price, res: res, units: payOf(r.price, res), mk: r.mk, side: r.side, band: r.band || "no edge" });
    });
    if (typeof pairTakesAll === "function") pairTakesAll().forEach(function (t) {
      var res = propsPairRes(t); if (!res) return;
      picks.push({ d: t.legs[0].gdate || "", kind: "same-game pair", text: t.legs.map(function (r) { return r.name + " " + r.side + " " + r.line + " " + (PROPS_LABEL[r.mk] || r.mk); }).join(" + ") + " · " + t.game, p: t.chance, price: t.price, res: res, units: res === "win" ? propsPairUnits(t, res) : res === "loss" ? -1 : 0 });
    });
    if (typeof propsT3TakesAll === "function") propsT3TakesAll().forEach(function (t) {
      var res = propsT3Res(t); if (!res || res === "void") return;
      picks.push({ d: t.gdate || "", kind: t3Word(t.legs.length) + "-leg ticket", text: t.legs.map(propsT3LegText).join(" + ") + " · at " + bookName(t.app), p: t.chance, price: t.price, res: res, units: res === "win" ? propsT3Units(t, res) : res === "loss" ? -1 : 0 });
    });
    if (!picks.length) return h;
    var agg = function () { return { n: 0, w: 0, l: 0, p: 0, says: 0, units: 0 }; };
    var put = function (s, x) { if (x.res === "push") { s.p++; return; } s.n++; s.says += x.p; if (x.res === "win") s.w++; else s.l++; s.units += x.units; };
    var byNight = {}, sheetNight = {};
    picks.forEach(function (x) { put(byNight[x.d] || (byNight[x.d] = agg()), x); });
    (typeof props === "undefined" ? [] : props).forEach(function (r) {   // the sheet's own BET and LEAN props each night, the comparison
      if (!r.gdate || (r.band !== "BET" && r.band !== "LEAN") || !r.result || r.result === "graded" || r.result === "void") return;
      put(sheetNight[r.gdate] || (sheetNight[r.gdate] = agg()), { res: r.result, p: r.chance, units: payOf(r.price, r.result) });
    });
    var line = function (s) { return s.w + "-" + s.l + (s.p ? "-" + s.p : ""); }, pc = function (v) { return (100 * v).toFixed(1) + "%"; };
    var cls = function (s) { return s.n ? (s.units > 0 ? "pos" : s.units < 0 ? "neg" : "") : ""; }, upcls = function (s) { return s.n ? (s.w / s.n >= s.says / s.n ? "pos" : "neg") : ""; };
    var nights = Object.keys(byNight).sort().reverse();
    h += '<div class="subhead" data-sport="TAKEN-NIGHTS">Your picks, night by night <span class="tag">every bet you marked, graded at the price marked · says is the sheet\'s chance on it · beside it, what the sheet\'s own BET and LEAN props did that night</span></div>' +
         '<table class="form" id="takenNights"><thead><tr><th>Night</th><th>Graded</th><th>Record</th><th>Says</th><th>Does</th><th>Units</th><th>The sheet\'s BET + LEAN props</th></tr></thead><tbody>' +
         nights.map(function (d) {
           var s = byNight[d], sh = sheetNight[d], kinds = {};
           picks.forEach(function (x) { if (x.d === d) kinds[x.kind] = (kinds[x.kind] || 0) + 1; });
           return '<tr><td>' + esc(gameDate(d)) + '</td><td>' + (s.n + s.p) + ' <span class="dim">' + esc(Object.keys(kinds).map(function (k) { return kinds[k] + " " + k + (kinds[k] === 1 ? "" : "s"); }).join(", ")) + '</span></td>' +
                  '<td class="' + cls(s) + '">' + line(s) + '</td><td>' + (s.n ? pc(s.says / s.n) : "—") + '</td><td class="' + upcls(s) + '">' + (s.n ? pc(s.w / s.n) : "—") + '</td><td class="' + cls(s) + '">' + sgn(s.units, 1) + 'u</td>' +
                  '<td class="' + (sh ? cls(sh) : '') + '">' + (sh && sh.n ? line(sh) + ' · ' + pc(sh.w / sh.n) + ' · ' + sgn(sh.units, 1) + 'u' : '—') + '</td></tr>';
         }).join("") + '</tbody></table>';
    var pp = picks.filter(function (x) { return x.kind === "prop"; });
    if (pp.length) {
      var groups = [], add = function (label, sel) { var s = agg(); pp.forEach(function (x) { if (sel(x)) put(s, x); }); if (s.n || s.p) groups.push([label, s]); };
      add("Overs", function (x) { return x.side === "OVER"; }); add("Unders", function (x) { return x.side === "UNDER"; });
      ["BET", "LEAN", "no edge"].forEach(function (b) { add(b === "no edge" ? "No edge: the book's own side" : b + " band", function (x) { return x.band === b; }); });
      PROPS_ORDER.forEach(function (k) { add(PROPS_LABEL[k], function (x) { return x.mk === k; }); });
      [["−150 and heavier", -99999, -150], ["−120 to −150", -150, -120], ["−120 to +100", -120, 101], ["plus money", 101, 99999]].forEach(function (b) { add(b[0], function (x) { return x.price >= b[1] && x.price < b[2]; }); });
      h += '<div class="subhead" data-sport="TAKEN-PROPS">Your props, by side, band, market and price <span class="tag">the breakdown the sheet keeps of its own calls, on the props you took</span></div>' +
           '<table class="form" id="takenProps"><thead><tr><th>Cut</th><th>Record</th><th>Says</th><th>Does</th><th>Units</th></tr></thead><tbody>' +
           groups.map(function (g) { var s = g[1]; return '<tr><td>' + esc(g[0]) + '</td><td class="' + cls(s) + '">' + line(s) + '</td><td>' + (s.n ? pc(s.says / s.n) : "—") + '</td><td class="' + upcls(s) + '">' + (s.n ? pc(s.w / s.n) : "—") + '</td><td class="' + cls(s) + '">' + sgn(s.units, 1) + 'u</td></tr>'; }).join("") + '</tbody></table>';
    }
    picks.sort(function (a, b) { return (b.d < a.d ? -1 : b.d > a.d ? 1 : 0) || (b.p - a.p); });
    h += '<details class="takenlist"><summary>Every pick you marked, newest night first · ' + picks.length + ' graded</summary><table class="form" id="takenList"><thead><tr><th>Night</th><th>Bet</th><th>Kind</th><th>Says</th><th>Price</th><th>Result</th><th>Units</th></tr></thead><tbody>' +
         picks.map(function (x) { return '<tr class="' + esc(x.res) + '"><td>' + esc(gameDate(x.d)) + '</td><td>' + esc(x.text) + '</td><td>' + esc(x.kind) + '</td><td>' + pc(x.p) + '</td><td>' + sgn(x.price, 0) + '</td><td><span class="chip ' + esc(x.res) + '">' + esc(String(x.res).toUpperCase()) + '</span></td><td class="' + (x.units > 0 ? 'pos' : x.units < 0 ? 'neg' : '') + '">' + sgn(x.units, 2) + 'u</td></tr>'; }).join("") + '</tbody></table></details>';
    h += '<div class="verdict">Says is the sheet\'s chance on what you took, does how often it landed. The sheet\'s own tiles say whether its chances are honest; a gap here that is not there is selection, the picks you choose from its list landing less (or more) often than their chances say. Nothing reads under a hundred picks.</div>';
    return h;
  }
  /* the buttons: caught before the card or the row underneath opens anything */
  document.addEventListener("click", function (e) {
    var t = e.target && e.target.closest ? e.target.closest("[data-take],[data-ptake],[data-stake],[data-ttake],[data-t3take],[data-t3copy]") : null; if (!t) return;
    e.stopPropagation(); e.preventDefault();
    if (t.hasAttribute("data-take")) toggleTake(t.getAttribute("data-take"));
    else if (t.hasAttribute("data-stake")) toggleSimTake(t.getAttribute("data-stake"));
    else if (t.hasAttribute("data-ttake")) togglePairTake(t.getAttribute("data-ttake"));
    else if (t.hasAttribute("data-t3take")) { if (typeof toggleT3Take === "function") toggleT3Take(t.getAttribute("data-t3take")); }   // a three-leg ticket (11 Nov 2026)
    else if (t.hasAttribute("data-t3copy")) { var t3c = typeof propsT3Find === "function" ? propsT3Find(t.getAttribute("data-t3copy")) : null; if (t3c) copyText(propsT3Text(t3c), typeof propsSay === "function" && $("propsView") && !$("propsView").hidden ? propsSay : say, "the ticket"); }
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
