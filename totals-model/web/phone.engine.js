  /* ===== PHONE BLOCK: tonight's picks on your phone (26 Oct 2026) =====
     The user: "a QR code I can scan with my phone camera that has the model picks, view only." The picks live in
     this browser's storage, so the phone has to be handed them: the QR code carries the night's picks themselves,
     deflated and base64url'd into the link's hash, and the link opens m.html, a small read-only sheet published
     beside this page. Nothing is sent anywhere and nothing is stored: the code is the data, made fresh each time
     the button is pressed. The page is private, so the phone opens the link signed in to claude.ai. A code holds
     about 2,900 characters, so the sections are trimmed from the least important end when a night runs long. */
  var PHONE_MAX = 2600;
  function phoneChance(p) { return p === null || p === undefined ? undefined : Math.round(p * 1000) / 10; }
  function phonePayload(dateISO, keep) {
    keep = keep || {};
    var P = { v: 1, d: dateISO, at: new Date().toISOString(), take: [], four: [], bets: [], likely: [], props: [], sim: [] };
    var res = function (mk, row) { var r = gradeMarket(mk, row.finals); return r && r !== "invalid" ? r : undefined; };
    takesOn(dateISO).forEach(function (x) { P.take.push({ k: "card", s: x.row.sport, g: x.row.matchup, p: x.mk.pick, m: x.mk.label || x.mk.key, c: phoneChance(x.mk.p), pr: x.mk.price, r: res(x.mk, x.row) }); });
    simTakesOn(dateISO).forEach(function (x) { P.take.push({ k: "sim", s: "NBA", g: x.row.matchup, p: x.t.pick, m: "the simulation, " + nbaSimTakeViewLabel(x.t.view), c: phoneChance(x.t.p), w: phoneChance(x.t.worth), b: x.t.band, pr: x.t.price === null ? undefined : x.t.price, r: nbaSimTakeRes(x.t, x.row) || undefined }); });
    propsTakenOn(dateISO).forEach(function (r) { P.take.push({ k: "prop", s: "NBA", g: r.game, p: r.name + " " + r.side + " " + r.line + " " + (PROPS_LABEL[r.mk] || r.mk), m: "prop", c: phoneChance(r.chance), pr: r.price, b: r.band, r: propTakeRes(r) || undefined }); });
    parlayFour(dateISO).forEach(function (x) { P.four.push({ g: x.row.matchup, s: x.row.sport, p: x.mk.pick, m: x.mk.label, c: phoneChance(x.mk.p), pr: x.mk.price === null ? undefined : x.mk.price, b: bandOf(x.mk) || undefined, r: res(x.mk, x.row) }); });
    bestBets(dateISO).forEach(function (x) { P.bets.push({ g: x.row.matchup, s: x.row.sport, p: x.mk.pick, m: x.mk.label, c: phoneChance(x.mk.p), pr: x.mk.price, e: x.mk.edge === null || x.mk.edge === undefined ? undefined : Math.round(x.mk.edge * 1000) / 10, b: bandOf(x.mk) || undefined, r: res(x.mk, x.row) }); });
    if (keep.likely !== false) likeliestLegs(dateISO).forEach(function (x) { P.likely.push({ g: x.row.matchup, s: x.row.sport, p: x.mk.pick, c: phoneChance(x.mk.p), pr: x.mk.price, ok: x.mk.p >= x.need ? 1 : undefined, r: res(x.mk, x.row) }); });
    propsSource().filter(function (r) { return (r.gdate || "") === dateISO && propHas(r) && r.edge > 0; }).sort(function (a, b) { return b.edge - a.edge; }).slice(0, keep.props === undefined ? 12 : keep.props)
      .forEach(function (r) { P.props.push({ g: r.game, p: r.name + " " + r.side + " " + r.line + " " + (PROPS_LABEL[r.mk] || r.mk), c: phoneChance(r.chance), pr: r.price, e: Math.round(r.edge * 1000) / 10, b: r.band, pj: r.proj, r: propTakeRes(r) || undefined }); });
    if (keep.sim !== false) card.filter(function (r) { return r.sport === "NBA" && (r.gdate || "") === dateISO && r.inputs && r.inputs.nbasim && !isVoid(r); }).forEach(function (r) {
      var sim = null; try { sim = JSON.parse(r.inputs.nbasim); } catch (e) { sim = null; }
      if (!sim || !sim.own) return;
      var lines = nbaSimLinesFrom(r.inputs);
      ["own", "mkt"].forEach(function (view) {
        nbaSimCalls(sim, lines, view).forEach(function (c) {
          if (c.band !== "BET" && c.band !== "STRONG") return;
          P.sim.push({ g: r.matchup, p: nbaSimPickText(c.key, c.side, c.line, r.away, r.home), v: view === "own" ? "own view" : "anchored", c: phoneChance(c.p), w: phoneChance(c.worth), b: c.band });
        });
      });
      [["AWAY", lines.away_tt, r.away], ["HOME", lines.home_tt, r.home]].forEach(function (x) {
        var tt = x[1]; if (!tt || !tt.rule || !tt.rule.call) return;
        P.sim.push({ g: r.matchup, p: x[2] + " team total " + tt.rule.call + " " + tt.line, v: "gap rule", g2: tt.rule.gap, b: "gap rule" });
      });
    });
    return P;
  }
  function phoneB64url(bytes) { var s = ""; for (var i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]); return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, ""); }
  function phoneEncode(obj) {
    var raw = new TextEncoder().encode(JSON.stringify(obj));
    if (typeof CompressionStream === "undefined") return Promise.resolve("j" + phoneB64url(raw));
    try {
      var cs = new CompressionStream("deflate-raw"), w = cs.writable.getWriter();
      w.write(raw); w.close();
      return new Response(cs.readable).arrayBuffer().then(function (buf) { return "z" + phoneB64url(new Uint8Array(buf)); }).catch(function () { return "j" + phoneB64url(raw); });
    } catch (e) { return Promise.resolve("j" + phoneB64url(raw)); }
  }
  /* the code's size: the least important sections go first when a night runs long, and the sheet says what was left out */
  function phoneFit(dateISO) {
    var steps = [[{}, ""], [{ likely: false }, "the likeliest-at-any-price list"], [{ likely: false, sim: false }, "the likeliest list and the simulation's calls"], [{ likely: false, sim: false, props: 6 }, "the likeliest list, the simulation's calls and all but six props"],
                 [{ likely: false, sim: false, props: 0 }, "the likeliest list, the simulation's calls and the props list"]];
    var i = 0;
    var next = function () {
      var P = phonePayload(dateISO, steps[i][0]);
      if (steps[i][1]) P.cut = steps[i][1];
      return phoneEncode(P).then(function (enc) {
        if (enc.length <= PHONE_MAX || i === steps.length - 1) return { enc: enc, cut: steps[i][1], n: P.take.length + P.four.length + P.bets.length + P.likely.length + P.props.length + P.sim.length };
        i++; return next();
      });
    };
    return next();
  }
  /* the sheet's address: beside this page when the page is a file or a folder; under it when the page is served at a bare id */
  function phoneSheetUrl() {
    var u = new URL(location.href); u.hash = ""; u.search = "";
    if (/\/$/.test(u.pathname) || /\/[^\/]*\.[A-Za-z0-9]+$/.test(u.pathname)) return new URL("m.html", u.href).href;
    return u.href.replace(/\/?$/, "/") + "m.html";
  }
  function phoneUrlFor(enc) { return phoneSheetUrl() + "#" + enc; }
  function showPhone() {
    var dlg = $("phoneDlg"), body = $("phoneBody"); if (!dlg || !body) return;
    var dateISO = $("boardDate").value || todayISO();
    body.innerHTML = '<p class="note">Making the code…</p>'; dlg.hidden = false; document.body.classList.add("noscroll");
    phoneFit(dateISO).then(function (x) {
      var url = phoneUrlFor(x.enc), h = '<h3>Tonight on your phone <span class="tag">' + esc(gameDate(dateISO)) + '</span></h3>';
      if (!x.n) {
        h += '<p class="note">Nothing on the board for ' + esc(gameDate(dateISO)) + ' yet: add the matchups, load the props, and the code carries them.</p>';
      } else {
        var qr = qrcode(0, "L"); qr.addData(url, "Byte"); qr.make();
        h += '<div class="qrbox">' + qr.createSvgTag({ cellSize: 4, margin: 6, scalable: true }) + '</div>';
        h += '<p class="note"><b>Point your phone\'s camera at the code</b> and open the link. It shows ' + x.n + ' line' + (x.n === 1 ? '' : 's') + ': the bets you are taking, the parlay four, the best straight bets' +
             (x.cut ? '' : ', the likeliest sides, the best props and the simulation\'s calls') + ', view only.' + (x.cut ? ' The night ran long for one code, so ' + esc(x.cut) + ' stayed off it.' : '') +
             ' The picks are inside the code itself, nothing is uploaded; press the button again after a new run for a fresh code. The page is private, so the phone has to be signed in to claude.ai to open it.</p>';
        h += '<p class="note dim"><a href="' + esc(url) + '" target="_blank" rel="noopener">Open the phone sheet in a tab</a> · ' + x.enc.length + ' characters in the code · ' + qr.getModuleCount() + ' modules a side</p>';
      }
      body.innerHTML = h;
      if ($("phoneClose")) $("phoneClose").focus();
    }).catch(function (e) { body.innerHTML = '<p class="note">The code could not be made (' + esc(String(e && e.message || e)) + ').</p>'; });
  }
  function closePhone() { var dlg = $("phoneDlg"); if (!dlg) return; dlg.hidden = true; document.body.classList.remove("noscroll"); }
  if ($("phone")) {
    document.body.insertAdjacentHTML("beforeend",
      '<div id="phoneDlg" class="pdlg phone" hidden role="dialog" aria-modal="true" aria-label="Tonight on your phone"><div class="pdlg-box"><div class="pdlg-top"><button type="button" class="btn pdlg-close" id="phoneClose">Close</button></div><div id="phoneBody"></div></div></div>');
    $("phone").addEventListener("click", showPhone);
    $("phoneClose").addEventListener("click", closePhone);
    $("phoneDlg").addEventListener("click", function (e) { if (e.target === $("phoneDlg")) closePhone(); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !$("phoneDlg").hidden) closePhone(); });
  }
