  /* ===== PHONE BLOCK: tonight's picks on your phone (26 Oct 2026) =====
     The user: "a QR code I can scan with my phone camera that has the model picks, view only." The picks live in
     this browser's storage, so the phone has to be handed them: the QR code carries the night's picks themselves,
     deflated and base64url'd into the link's hash, and the link opens m.html, a small read-only sheet published
     beside this page. Nothing is sent anywhere and nothing is stored: the code is the data, made fresh each time
     the button is pressed. The page is private, so the phone opens the link signed in to claude.ai. A code holds
     about 2,900 characters, so the sections are trimmed from the least important end when a night runs long.

     THE STORE (11 Nov 2026). The user: "I saved the log for today for what I am betting and then took the picture
     with my phone and it brings up the model but nothing in it." On claude.ai the page is private and is shown
     inside the viewer. A phone that follows a link to m.html on the page's own host is sent to the viewer and the
     main page, with a phone's empty storage, and the picks in the link's hash never arrive. So where the viewer
     gives the page its store (the db capability), the button SAVES the night's sheet there, whole, at phone/latest,
     under a rule only the page's owner meets, and the code carries the page's own address on claude.ai (read from
     phone/config, written beside the publish and never in the source). A view the width of a phone, or one with no
     card and no props of its own, watches that document and opens the sheet over the page by itself; a view with a
     card never asks the store until the button is pressed, so the desktop sees no prompt it did not ask for. Off
     claude.ai there is no store, and the code carries the picks to m.html as before. The sheet also carries the
     tickets you are taking and the night's tickets, which the code never had.

     SHARED, VIEW ONLY (the same day, the user: "what if I want to share the QR or have someone else see it too
     without changing" anything). The store's rule lets everyone the page is shared with READ the sheet and only its
     owner WRITE it. Someone the owner shares the page with (the Share menu on claude.ai, Viewer is enough, signed in
     to Claude) scans the same code and gets the sheet and nothing else: no button to the model behind it, no way
     to save over it. The card, the props and the record never leave the owner's browser, so there is nothing of
     his for them to change. For someone with no Claude account the dialog copies the sheet as plain text.

     THE DETAIL (the same day, the user: "I'd like to be able to see the prop cards when I select it so I can see the
     graphs and info too"). The phone has no props of its own to draw a panel from, and a panel reads more than its
     row (the tells off the record, his other markets' floors, the one bet a man). So the computer draws each prop's
     own panel as it stands there, propsDetailHtml, for every prop on the sheet: the ones you are taking, the best
     props, the legs of the tickets and the pairs. It takes the buttons and anything that would act out of the
     markup, packs the lot (deflate, base64) and saves it in the same document, the ones you are taking first when
     the store's limit would be passed. On the phone a card that has detail opens it over the sheet, a ticket or a
     pair its legs one under the other. The markup is cleaned again where it is shown.

     THE FILE (the same day, the user: "if I want to share my picks for the day with someone, and have them see the
     details behind the pick without them changing" anything "but able to see from their phone"). Someone the page
     is shared with gets all of that through the store, signed in to Claude. For someone with no account the dialog
     saves the same sheet as one file to send: the picks, and under each one its detail, folded, to open with a
     tap. It is a still copy, markup and style and no script, so it opens in any phone's browser or preview and
     there is nothing in it to change. */
  var PHONE_MAX = 2600, PHONE_DOC = "phone/latest", PHONE_CONFIG = "phone/config", PHONE_SMALL = "(max-width: 760px)";
  var PHONE_PANELS_MAX = 190000;   // characters of packed panels a save carries: the store takes 256 KiB a document, the sheet rides beside them
  var phoneShutAt = "";   // the sheet closed by hand stays closed until a newer one lands
  var phonePanelSrc = { enc: null, map: null };   // the detail behind the open sheet: packed as the store holds it, or already a map of id to markup
  function phoneTicket(t) {   // a ticket as one line of the sheet: the legs, the app, the games, the chance all land, the parlay price
    var games = [];
    t.legs.forEach(function (l) { if (games.indexOf(l.r.game) < 0) games.push(l.r.game); });
    return { n: t.legs.length, s: "NBA", g: games.join(" · "), p: t.legs.map(function (l) { return propsT3LegText(l); }).join(" + "), m: "at " + bookName(t.app), c: phoneChance(t.chance), pr: t.price, r: propsT3Res(t) || undefined };
  }
  /* the props behind a line of the sheet, for the detail: the line keeps their ids, and the rows queue up by how much they matter
     (what you are taking, then the best props, then the night's tickets, then the pairs) */
  function phoneRefs(keep, x, rows, rank) {
    if (!keep.detail) return x;
    var ids = [];
    rows.forEach(function (r) {
      if (!r || r.id === undefined || r.id === null) return;
      var id = String(r.id), had = keep.detail.seen[id];
      ids.push(id);
      if (!had) { had = keep.detail.seen[id] = { r: r, rank: rank, n: keep.detail.rows.length }; keep.detail.rows.push(had); }
      else if (rank < had.rank) had.rank = rank;   // a prop met first in a pair and then among the ones you are taking counts as one you are taking
    });
    if (ids.length) x.ids = ids;
    return x;
  }
  function phoneChance(p) { return p === null || p === undefined ? undefined : Math.round(p * 1000) / 10; }
  function phonePayload(dateISO, keep) {
    keep = keep || {};
    var P = { v: 1, d: dateISO, at: new Date().toISOString(), take: [], four: [], bets: [], likely: [], props: [], sim: [], pairs: [], t3: [] };
    if (typeof propsPairs === "function") propsPairs(dateISO).slice(0, 6).forEach(function (t) {
      var res = propsPairRes(t);
      P.pairs.push(phoneRefs(keep, { g: t.game, p: t.legs.map(function (r) { return r.name + " " + r.side + " " + r.line + " " + (PROPS_LABEL[r.mk] || r.mk); }).join(" + "), c: phoneChance(t.chance), pr: t.price, ok: t.chance >= t.need ? 1 : undefined, r: res || undefined }, t.legs, 3));
    });
    var res = function (mk, row) { var r = gradeMarket(mk, row.finals); return r && r !== "invalid" ? r : undefined; };
    takesOn(dateISO).forEach(function (x) { P.take.push({ k: "card", s: x.row.sport, g: x.row.matchup, p: x.mk.pick, m: x.mk.label || x.mk.key, c: phoneChance(x.mk.p), pr: x.mk.price, r: res(x.mk, x.row) }); });
    simTakesOn(dateISO).forEach(function (x) { P.take.push({ k: "sim", s: "NBA", g: x.row.matchup, p: x.t.pick, m: "the simulation, " + nbaSimTakeViewLabel(x.t.view), c: phoneChance(x.t.p), w: phoneChance(x.t.worth), b: x.t.band === "no call" ? undefined : x.t.band, pr: x.t.price === null ? undefined : x.t.price, r: nbaSimTakeRes(x.t, x.row) || undefined }); });
    propsTakenOn(dateISO).forEach(function (r) { P.take.push(phoneRefs(keep, { k: "prop", s: "NBA", g: r.game, p: r.name + " " + r.side + " " + r.line + " " + (PROPS_LABEL[r.mk] || r.mk), m: "prop", c: phoneChance(r.chance), pr: r.price, b: r.band, r: propTakeRes(r) || undefined }, [r], 0)); });
    if (typeof pairTakesOn === "function") pairTakesOn(dateISO).forEach(function (t) { P.take.push(phoneRefs(keep, { k: "pair", s: "NBA", g: t.game, p: t.legs.map(function (r) { return r.name + " " + r.side + " " + r.line + " " + (PROPS_LABEL[r.mk] || r.mk); }).join(" + "), m: "same-game pair at the parlay price", c: phoneChance(t.chance), pr: t.price, r: propsPairRes(t) || undefined }, t.legs, 0)); });
    if (typeof propsT3TakesOn === "function") propsT3TakesOn(dateISO).forEach(function (t) { var x = phoneTicket(t); x.k = "ticket"; P.take.push(phoneRefs(keep, x, t.legs.map(function (l) { return l.r; }), 0)); });   // 11 Nov 2026: a ticket you are taking is a bet you are taking
    if (keep.t3 !== false && typeof propsTrebles === "function" && propsBelow !== "leans") propsTrebles(dateISO, null, propsT3Mode(), propsLegs).slice(0, 6).forEach(function (t) { P.t3.push(phoneRefs(keep, phoneTicket(t), t.legs.map(function (l) { return l.r; }), 2)); });
    parlayFour(dateISO).forEach(function (x) { P.four.push({ g: x.row.matchup, s: x.row.sport, p: x.mk.pick, m: x.mk.label, c: phoneChance(x.mk.p), pr: x.mk.price === null ? undefined : x.mk.price, b: bandOf(x.mk) || undefined, r: res(x.mk, x.row) }); });
    bestBets(dateISO).forEach(function (x) { P.bets.push({ g: x.row.matchup, s: x.row.sport, p: x.mk.pick, m: x.mk.label, c: phoneChance(x.mk.p), pr: x.mk.price, e: x.mk.edge === null || x.mk.edge === undefined ? undefined : Math.round(x.mk.edge * 1000) / 10, b: bandOf(x.mk) || undefined, r: res(x.mk, x.row) }); });
    if (keep.likely !== false) likeliestLegs(dateISO).forEach(function (x) { P.likely.push({ g: x.row.matchup, s: x.row.sport, p: x.mk.pick, c: phoneChance(x.mk.p), pr: x.mk.price, ok: x.mk.p >= x.need ? 1 : undefined, r: res(x.mk, x.row) }); });
    propsSource().filter(function (r) { return (r.gdate || "") === dateISO && propHas(r) && r.edge > 0; }).sort(function (a, b) { return b.edge - a.edge; }).slice(0, keep.props === undefined ? 12 : keep.props)
      .forEach(function (r) { var sr = typeof propSimRead === "function" ? propSimRead(r) : null; P.props.push(phoneRefs(keep, { g: r.game, p: r.name + " " + r.side + " " + r.line + " " + (PROPS_LABEL[r.mk] || r.mk), c: phoneChance(r.chance), pr: r.price, e: Math.round(r.edge * 1000) / 10, b: r.band, pj: r.proj, sr: sr === null ? undefined : sr, r: propTakeRes(r) || undefined }, [r], 1)); });
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
      // the gap rode in this list as a call until 11 Nov 2026. It is a watch now (the two seasons behind it read a line the season
      // pull had kept wrong), and this list is the calls at BET or better, so the phone does not carry it. m.html still reads an
      // old code's "gap rule" entries
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
  function phoneDecode(enc) {   // what phoneEncode packed: "z" deflated, "j" plain
    var b = String(enc).slice(1).replace(/-/g, "+").replace(/_/g, "/"); while (b.length % 4) b += "=";
    var bin = atob(b), bytes = new Uint8Array(bin.length); for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    if (String(enc).charAt(0) !== "z") return Promise.resolve(JSON.parse(new TextDecoder().decode(bytes)));
    if (typeof DecompressionStream === "undefined") return Promise.reject(new Error("this browser cannot unpack the detail"));
    var ds = new DecompressionStream("deflate-raw"), w = ds.writable.getWriter();
    w.write(bytes); w.close();
    return new Response(ds.readable).arrayBuffer().then(function (buf) { return JSON.parse(new TextDecoder().decode(new Uint8Array(buf))); });
  }
  /* a panel's markup made fit to carry and to show: the buttons and anything else that would act taken out, with every attribute
     that could run something or reach the page's own click handlers. Parsed in a template, where nothing loads and nothing runs.
     Done on the computer before the save and again on the phone before it is shown: the store is written by the owner alone,
     and what comes out of it is still not trusted to be what went in */
  function phoneClean(html) {
    var t = document.createElement("template");
    t.innerHTML = String(html === undefined || html === null ? "" : html);
    var kill = t.content.querySelectorAll("script, style, iframe, object, embed, link, meta, base, form, input, button, select, textarea, a, img, video, audio, source, svg, math, .pd-take");
    for (var i = 0; i < kill.length; i++) if (kill[i].parentNode) kill[i].parentNode.removeChild(kill[i]);
    var all = t.content.querySelectorAll("*");
    for (var j = 0; j < all.length; j++) {
      var el = all[j], at = el.attributes;
      for (var k = at.length - 1; k >= 0; k--) {
        var n = at[k].name.toLowerCase(), v = String(at[k].value || "");
        if (n === "class" || n === "title" || n === "colspan" || n === "rowspan") continue;
        if (n === "style" && !/url\s*\(|expression|@import|javascript:|behavior/i.test(v)) continue;
        el.removeAttribute(at[k].name);
      }
    }
    return t.innerHTML;
  }
  /* every prop of the sheet as its own panel, packed: {id: markup} through phoneEncode. Over the limit, the least important go
     (the queue is in that order) and it is packed again; what did not fit is counted, and its card on the phone says so */
  function phonePanels(detail) {
    var rows = detail.rows.slice().sort(function (a, b) { return (a.rank - b.rank) || (a.n - b.n); }), map = {}, order = [];
    rows.forEach(function (x) { var id = String(x.r.id), h = ""; try { h = phoneClean(propsDetailHtml(x.r)); } catch (e) { h = ""; } if (h) { map[id] = h; order.push(id); } });
    var pack = function (n, tries) {
      var m = {}; order.slice(0, n).forEach(function (id) { m[id] = map[id]; });
      return phoneEncode(m).then(function (enc) {
        if (enc.length <= PHONE_PANELS_MAX || n <= 1 || tries >= 5) return { enc: enc.length <= PHONE_PANELS_MAX ? enc : "", n: enc.length <= PHONE_PANELS_MAX ? n : 0, of: order.length, map: m };
        return pack(Math.max(1, Math.floor(n * PHONE_PANELS_MAX / enc.length * 0.95)), tries + 1);
      });
    };
    if (!order.length) return Promise.resolve({ enc: "", n: 0, of: 0, map: {} });
    return pack(order.length, 0);
  }
  function phoneLines(P) { return P.take.length + P.four.length + P.bets.length + P.likely.length + P.props.length + P.sim.length + (P.t3 || []).length; }
  /* the code's size: the least important sections go first when a night runs long, and the sheet says what was left out */
  function phoneFit(dateISO) {
    var steps = [[{}, ""], [{ likely: false }, "the likeliest-at-any-price list"], [{ likely: false, t3: false }, "the likeliest list and the tickets"], [{ likely: false, t3: false, sim: false }, "the likeliest list, the tickets and the simulation's calls"],
                 [{ likely: false, t3: false, sim: false, props: 6 }, "the likeliest list, the tickets, the simulation's calls and all but six props"], [{ likely: false, t3: false, sim: false, props: 0 }, "the likeliest list, the tickets, the simulation's calls and the props list"]];
    var i = 0;
    var next = function () {
      var P = phonePayload(dateISO, steps[i][0]);
      if (steps[i][1]) P.cut = steps[i][1];
      return phoneEncode(P).then(function (enc) {
        if (enc.length <= PHONE_MAX || i === steps.length - 1) return { enc: enc, cut: steps[i][1], n: phoneLines(P) };
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
  /* ---- the store: the artifact's own database on claude.ai, or nothing ---- */
  function phoneInViewer() { return !!(window.claude && typeof window.claude.use === "function"); }
  function phoneStore() {
    if (!phoneInViewer()) return Promise.resolve(null);
    try { return Promise.resolve(window.claude.use("db")).then(function (db) { return db || null; }, function () { return null; }); }
    catch (e) { return Promise.resolve(null); }
  }
  function phoneOwner() {   // true: the page's owner; false: someone it is shared with; null: nobody to ask (off claude.ai, or the viewer did not say)
    if (!phoneInViewer()) return Promise.resolve(null);
    try {
      return Promise.resolve(window.claude.use("user")).then(function (u) {
        if (!u || typeof u.isOwner !== "function") return null;
        return Promise.resolve(u.isOwner()).then(function (v) { return !!v; }, function () { return null; });
      }, function () { return null; });
    } catch (e) { return Promise.resolve(null); }
  }
  function phoneSave(db, P, panels) {   // the whole sheet and the packed detail, one write a press; an unavailable store gets one more try after a short wait
    var body = JSON.parse(JSON.stringify({ v: 3, d: P.d, at: P.at, sheet: P, panels: panels || "" })), put = function () { return db.doc(PHONE_DOC).set(body); };
    return put().then(null, function (e) {
      if (!e || e.code !== "unavailable") throw e;
      return new Promise(function (go) { setTimeout(go, 400 + Math.floor(Math.random() * 600)); }).then(put);
    });
  }
  function phoneViewerUrl(db) {   // the page's address on claude.ai, kept in the store beside the sheet; "" when it has not been written
    return db.doc(PHONE_CONFIG).get().then(function (snap) {
      var c = snap && snap.exists ? snap.data() : null, u = c && typeof c.url === "string" ? c.url : "";
      return /^https:\/\/claude\.ai\/[A-Za-z0-9\/_-]+$/.test(u) ? u : "";
    }, function () { return ""; });
  }
  function phoneWhyNot(e) {
    var code = e && e.code ? String(e.code) : "";
    if (code === "not_granted" || code === "capability_disabled" || code === "capability_removed" || code === "revoked") return "this view was not given the page's store";
    if (code === "invalid_argument") return "the store refused it: only the page's owner saves the sheet";
    if (code === "quota_exceeded") return "the page's store is full";
    if (code === "resource_exhausted") return "the store is busy";
    return "the store did not answer" + (code ? " (" + code + ")" : "");
  }
  /* ---- the sheet itself, as the phone shows it: the same lines m.html draws, kept in step with it (the harness reads both) ---- */
  function phoneLine3(x) {
    var parts = [];
    if (x.c !== undefined && x.c !== null) parts.push((+x.c).toFixed(1) + "%" + (x.w !== undefined && x.w !== null ? " · worth " + (+x.w).toFixed(0) + "%" : ""));
    if (x.pr !== undefined && x.pr !== null) parts.push(sgn(+x.pr, 0) + " needs " + (implied(+x.pr) * 100).toFixed(1) + "%");
    if (x.e !== undefined && x.e !== null) parts.push("edge " + sgn(+x.e, 1));
    if (x.pj !== undefined && x.pj !== null) parts.push("proj " + x.pj);
    if (x.sr !== undefined && x.sr !== null) parts.push("sim " + x.sr);
    if (x.g2 !== undefined && x.g2 !== null) parts.push("gap " + sgn(+x.g2, 1));
    if (x.ok) parts.push("the price agrees");
    return parts.join(" · ");
  }
  function phoneCard(x, cls, n1, tap) {   // tap: true where a press opens the detail over the sheet; a function where the detail is folded under the card (the file)
    var ids = tap && x.ids && x.ids.length ? x.ids.map(String) : null, fold = typeof tap === "function" && ids ? tap(ids) : "";
    if (typeof tap === "function" && !fold) ids = null;
    var h = '<div class="pshk' + (cls ? ' ' + cls : '') + (ids ? ' tap' + (fold ? '' : '" data-pids="' + esc(ids.join(",")) + '" role="button" tabindex="0" title="Open the detail') : '') + '"><div class="a1">' + esc(n1) + (x.b ? ' <span class="pshc band">' + esc(x.b) + '</span>' : '') + '</div>' +
      '<div class="a2">' + esc(x.p) + (x.r ? ' <span class="pshc ' + esc(x.r) + '">' + esc(x.r) + '</span>' : '') + '</div>' +
      '<div class="a3">' + esc(phoneLine3(x)) + '</div><div class="a4">' + esc(x.g) + (x.m ? ' · ' + esc(x.m) : '') + (x.v ? ' · ' + esc(x.v) : '') + '</div></div>';
    return fold ? '<details class="pfd"><summary>' + h + '</summary><div class="pdlg ppanel inl"><div class="pdlg-box">' + fold + '</div></div></details>' : h;
  }
  function phoneLegsHtml(ids, m, missing) {   // the detail of a card: one panel, or a ticket's or a pair's legs one under the other
    var any = false, h = ids.map(function (id, k) {
      var one = m && typeof m[id] === "string" ? phoneClean(m[id]) : "";
      if (one) any = true;
      return '<div class="pp-leg">' + (ids.length > 1 ? '<div class="pp-legn">Leg ' + (k + 1) + ' of ' + ids.length + '</div>' : '') + (one || missing) + '</div>';
    }).join("");
    return any ? h : "";
  }
  function phoneTakeLabel(x) { return "TAKING · " + (x.k === "prop" ? "NBA PROP" : x.k === "sim" ? "NBA · SIMULATION" : x.k === "pair" ? "NBA · SAME-GAME PAIR" : x.k === "ticket" ? "NBA · " + (x.n || 2) + "-LEG TICKET" : x.s); }
  function phoneDate(iso) { try { return new Date(iso + "T12:00:00").toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" }); } catch (e) { return String(iso); } }   // the weekday with it, as m.html writes it
  function phoneSheetHtml(P, tap) {
    var sec = function (title, items, fn) { if (!items || !items.length) return ''; return '<h2>' + esc(title) + ' <span class="pshc">' + items.length + '</span></h2>' + items.map(fn).join(''); };
    var any = false;
    var made = ""; try { made = new Date(P.at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }); } catch (e) { made = ""; }
    var h = '';
    h += sec("Taking tonight", P.take, function (x) { return phoneCard(x, "take", phoneTakeLabel(x), tap); });
    h += sec("The parlay four", P.four, function (x, i) { return phoneCard(x, "", "#" + (i + 1) + " · " + x.s); });
    h += sec("Best straight bets", P.bets, function (x, i) { return phoneCard(x, "", "#" + (i + 1) + " · " + x.s); });
    h += sec("Likeliest at any price", P.likely, function (x, i) { return phoneCard(x, "", "#" + (i + 1) + " · " + x.s); });
    h += sec("Best props", P.props, function (x, i) { return phoneCard(x, "", "#" + (i + 1) + " · NBA PROP", tap); });
    h += sec((P.t3 && P.t3[0] && P.t3[0].n === 3 ? "Three" : "Two") + "-leg tickets, to test", P.t3, function (x, i) { return phoneCard(x, "", "TICKET #" + (i + 1), tap); });
    h += sec("Same-game pairs", P.pairs, function (x, i) { return phoneCard(x, "", "PAIR #" + (i + 1), tap); });
    h += sec("The simulation's calls, BET or better", P.sim, function (x) { return phoneCard(x, "", "NBA · " + String(x.v || "").toUpperCase()); });
    if (!h) h = '<p class="psh-empty">Nothing on the board for this date.</p>';
    if (P.cut) h += '<p class="psh-empty">The night ran long for one code: ' + esc(P.cut) + ' stayed off it.</p>';
    any = /class="pshk[^"]* tap/.test(h);   // a card somewhere opens its detail
    return { sub: phoneDate(P.d) + (made ? " · made " + made : "") + " · view only", html: h, old: !!(P.d && P.d < todayISO()), tap: any };
  }
  function phoneSheetText(P) {   // the same sheet as plain text: for a message to someone with no Claude account
    var out = ["The Super Model · " + phoneDate(P.d) + " · view only"], sec = function (title, items, fn) {
      if (!items || !items.length) return;
      out.push("", title.toUpperCase());
      items.forEach(function (x, i) { var l3 = phoneLine3(x); out.push(fn(x, i) + " " + x.p + (x.b ? " [" + x.b + "]" : "") + (x.r ? " · " + String(x.r).toUpperCase() : "") + (l3 ? " · " + l3 : "") + " · " + x.g + (x.m ? " · " + x.m : "") + (x.v ? " · " + x.v : "")); });
    };
    sec("Taking tonight", P.take, function (x, i) { return (i + 1) + "."; });
    sec("The parlay four", P.four, function (x, i) { return "#" + (i + 1); });
    sec("Best straight bets", P.bets, function (x, i) { return "#" + (i + 1); });
    sec("Likeliest at any price", P.likely, function (x, i) { return "#" + (i + 1); });
    sec("Best props", P.props, function (x, i) { return "#" + (i + 1); });
    sec((P.t3 && P.t3[0] && P.t3[0].n === 3 ? "Three" : "Two") + "-leg tickets, to test", P.t3, function (x, i) { return "#" + (i + 1); });
    sec("Same-game pairs", P.pairs, function (x, i) { return "#" + (i + 1); });
    sec("The simulation's calls, BET or better", P.sim, function (x, i) { return "#" + (i + 1); });
    return out.join("\n");
  }
  /* the sheet as one file to send (the note at the top of this block): a still copy with the page's own style, each pick's
     detail folded under it. No script in it and nothing to press but the folds */
  function phoneFileHtml(P, map) {
    var css = "", st = document.querySelectorAll("style");
    for (var i = 0; i < st.length; i++) css += (st[i].textContent || "") + "\n";
    css = css.replace(/<\/style/gi, "<\\/style").replace(/@import[^;]*;/gi, "");
    var miss = '<p class="note">The detail of this one was not kept with the sheet.</p>';
    var x = phoneSheetHtml(P, function (ids) { return phoneLegsHtml(ids, map, miss); });
    var made = ""; try { made = new Date(P.at).toLocaleString([], { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }); } catch (e) { made = ""; }
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="light dark">' +
      '<title>The Super Model · ' + esc(phoneDate(P.d)) + '</title><style>' + css +
      'body.pfile { margin: 0; overflow: auto; } .pfile .psh { position: static; overflow: visible; min-height: 100vh; }' +
      '.pfile details.pfd { margin: 0 0 8px; } .pfile details.pfd > summary { list-style: none; cursor: pointer; display: block; } .pfile details.pfd > summary::-webkit-details-marker { display: none; }' +
      '.pfile details.pfd > summary .pshk { margin: 0; } .pfile details.pfd[open] > summary .pshk { border-color: var(--ink); } .pfile details.pfd[open] > summary .pshk.tap::after { transform: translateY(-50%) rotate(90deg); }' +
      '.pfile .pdlg.inl { position: static; inset: auto; z-index: auto; background: none; padding: 0; display: block; overflow: visible; }' +
      '.pfile .pdlg.inl .pdlg-box { max-width: none; width: auto; margin: 6px 0 14px; box-shadow: none; border: 1px solid var(--rule-firm); }' +
      '</style></head><body class="pfile"><div class="psh"><div class="psh-in"><div class="psh-top"><div><h1>The <em>Super</em> Model</h1><p class="psh-sub">' + esc(x.sub) + '</p></div><span class="pshc band">a copy</span></div>' +
      (x.tap ? '<p class="psh-tip">Tap a prop, a ticket or a pair for its detail.</p>' : '') +
      '<div class="psh-body">' + x.html + '</div>' +
      '<p class="psh-foot">View only: a copy of the sheet as it stood' + (made ? ' on ' + esc(made) : '') + '. Nothing in this file changes anything. The chance is the sheet\'s; the band is a priori and the record decides.</p></div></div></body></html>';
  }
  function phoneFileSave(P, map, say) {
    var name = "super-model-" + String(P.d || "sheet") + ".html", html = "";
    try { html = phoneFileHtml(P, map); } catch (e) { say("The file could not be made (" + esc(String(e && e.message || e)) + ")."); return; }
    var done = function () { say("Saved <b>" + esc(name) + "</b>. Send it as it is: it opens on any phone, view only, with the detail under each pick."); };
    var text = "Copy the sheet as text instead.";
    if (!phoneInViewer()) {
      try { var a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([html], { type: "text/html" })); a.download = name; document.body.appendChild(a); a.click(); document.body.removeChild(a); done(); }
      catch (e) { say("The file could not be saved here. " + text); }
      return;
    }
    Promise.resolve(window.claude.use("downloads")).then(function (dl) {
      if (!dl) { say("This view cannot save files. " + text); return; }
      return dl.save({ filename: name, data: html }).then(done, function (e) {
        var c = e && e.code ? String(e.code) : "";
        say(c === "declined" ? "Not saved." : c === "extension_not_enabled" || c === "rejected_extension" ? "This view does not save a file of this kind. " + text : c === "rate_limited" ? "A save is already waiting for an answer." : "The file could not be saved" + (c ? " (" + esc(c) + ")" : "") + ". " + text);
      });
    }, function () { say("This view cannot save files. " + text); });
  }
  function phoneSheetShow(P, how, src) {   // src: the detail behind the sheet, {enc} as the store holds it or {map} as the computer just drew it
    var el = $("phoneSheet");
    if (!el) {
      document.body.insertAdjacentHTML("beforeend", '<div id="phoneSheet" class="psh" hidden role="dialog" aria-modal="true" aria-label="Tonight on your phone"></div>');
      el = $("phoneSheet");
      var openFrom = function (e) { var c = e.target && e.target.closest ? e.target.closest("[data-pids]") : null; if (!c) return false; phonePanelOpen(String(c.getAttribute("data-pids") || "").split(",").filter(Boolean)); return true; };
      el.addEventListener("click", function (e) { if (e.target && e.target.closest && e.target.closest("[data-pshclose]")) { phoneSheetShut(); return; } openFrom(e); });
      el.addEventListener("keydown", function (e) { if ((e.key === "Enter" || e.key === " ") && openFrom(e)) e.preventDefault(); });
    }
    phonePanelSrc = { enc: src && typeof src.enc === "string" && src.enc ? src.enc : null, map: src && src.map && typeof src.map === "object" ? src.map : null };
    var x = phoneSheetHtml(P, !!(phonePanelSrc.enc || phonePanelSrc.map));
    el.innerHTML = '<div class="psh-in"><div class="psh-top"><div><h1>The <em>Super</em> Model</h1><p class="psh-sub">' + esc(x.sub) + '</p></div>' +
      (how === "guest" ? '<span class="pshc band">shared with you</span>' : '<button type="button" class="btn" data-pshclose>' + (how === "auto" ? "Open the full model" : "Close") + '</button>') + '</div>' +
      (x.tap ? '<p class="psh-tip">Tap a prop, a ticket or a pair for its detail.</p>' : '') +
      (x.old ? '<p class="psh-old">This sheet is for ' + esc(phoneDate(P.d)) + (how === "guest" ? ': the owner has not saved a newer one.' : '. Press Phone QR on the day board of the computer for tonight\'s.') + '</p>' : '') +
      '<div class="psh-body">' + x.html + '</div>' +
      '<p class="psh-foot">' + (how === "guest" ? 'View only: this is the owner\'s sheet for the night, and it follows when they save a new one. ' : 'View only: the card lives in the browser it was made in. Press Phone QR there after a new run and this sheet follows. ') +
      'The chance is the sheet\'s; the band is a priori and the record decides.</p></div>';
    el.dataset.at = P.at || ""; el.dataset.how = how || "";
    el.hidden = false; el.scrollTop = 0; document.body.classList.add("noscroll");
  }
  function phonePanelMap() {   // the detail unpacked once a sheet: {id: markup}, or null when the sheet carries none
    var src = phonePanelSrc;
    if (src.map) return Promise.resolve(src.map);
    if (!src.enc) return Promise.resolve(null);
    return phoneDecode(src.enc).then(function (m) { src.map = m && typeof m === "object" ? m : {}; return src.map; });
  }
  function phonePanelOpen(ids) {
    var dlg = $("phonePanel");
    if (!dlg) {
      document.body.insertAdjacentHTML("beforeend", '<div id="phonePanel" class="pdlg ppanel" hidden role="dialog" aria-modal="true" aria-label="The detail"><div class="pdlg-box"><div class="pdlg-top"><button type="button" class="btn pdlg-close" data-ppclose>Close</button></div><div id="phonePanelBody"></div></div></div>');
      dlg = $("phonePanel");
      dlg.addEventListener("click", function (e) { if (e.target === dlg || (e.target && e.target.closest && e.target.closest("[data-ppclose]"))) phonePanelShut(); });
    }
    var body = $("phonePanelBody");
    body.innerHTML = '<p class="note">Opening the detail…</p>'; dlg.hidden = false; dlg.scrollTop = 0; document.body.classList.add("noscroll");
    phonePanelMap().then(function (m) {
      var miss = '<p class="note">The detail of this one is not in the save. Press Phone QR on the computer again, or open it there.</p>';
      body.innerHTML = phoneLegsHtml(ids, m, miss) || miss;
      dlg.scrollTop = 0;
      var c = dlg.querySelector("[data-ppclose]"); if (c) c.focus();
    }, function (e) { body.innerHTML = '<p class="note">The detail could not be opened here (' + esc(String(e && e.message || e)) + ').</p>'; });
  }
  function phonePanelShut() {
    var dlg = $("phonePanel"); if (!dlg || dlg.hidden) return false;
    dlg.hidden = true;
    if ((!$("phoneSheet") || $("phoneSheet").hidden) && (!$("phoneDlg") || $("phoneDlg").hidden)) document.body.classList.remove("noscroll");
    return true;
  }
  function phoneSheetShut() {
    var el = $("phoneSheet"); if (!el || el.hidden || el.dataset.how === "guest") return;   // a guest's sheet has no way past it
    phoneShutAt = el.dataset.at || ""; el.hidden = true;
    if (!$("phoneDlg") || $("phoneDlg").hidden) document.body.classList.remove("noscroll");
  }
  /* a line across the top of a phone's view when there is no sheet to open, saying why and what to do: the page behind it is an
     empty model on a phone, which is what the user met ("it brings up the model but nothing in it") */
  function phoneHint(msg) {
    var el = $("phoneHint");
    if (!msg) { if (el) el.hidden = true; return; }
    if (!el) {
      document.body.insertAdjacentHTML("afterbegin", '<div id="phoneHint" class="phint" role="status"><span></span><button type="button" class="btn" data-phintx>Close</button></div>');
      el = $("phoneHint");
      el.addEventListener("click", function (e) { if (e.target && e.target.closest && e.target.closest("[data-phintx]")) el.hidden = true; });
    }
    el.firstChild.textContent = msg; el.hidden = false;
  }
  /* a phone-width view, or one with nothing of its own, watches the store and opens the sheet when one is there. The owner at a
     desk with a card asks the store nothing until the button is pressed. Someone the page is shared with gets the sheet with no
     way past it; the owner's phone gets a button to the model behind it */
  function phoneWatch() {
    var small = false; try { small = !!(window.matchMedia && window.matchMedia(PHONE_SMALL).matches); } catch (e) { small = false; }
    if (!small && (card.length || propsSource().length)) return;
    phoneStore().then(function (db) {
      if (!db) {
        if (small && phoneInViewer()) phoneHint("Tonight's sheet is kept in this page's store on claude.ai, and this view was not given it. Open the page in your phone's browser signed in to claude.ai, and allow it if a box asks.");
        return;
      }
      phoneOwner().then(function (owner) {
        try {
          db.doc(PHONE_DOC).onSnapshot(function (snap) {
            var d = snap && snap.exists ? snap.data() : null, P = d && d.sheet;
            if (!P || typeof P !== "object" || !P.at || !P.d) {
              if (small && snap && !snap.exists && !(snap.metadata && snap.metadata.fromCache))   // nothing saved, and the store has said so itself
                phoneHint(owner === false ? "The owner has not saved a sheet yet. It opens here by itself when they do." : "No sheet saved for the phone yet. On the computer, press Phone QR on the day board and it opens here by itself.");
              return;
            }
            phoneHint("");
            if (P.at === phoneShutAt) return;   // shut by hand: it stays shut until a newer sheet lands
            var open = $("phoneSheet");
            if (open && !open.hidden && open.dataset.at === P.at) return;   // the same sheet again: nothing to redraw
            phoneSheetShow(P, owner === false ? "guest" : "auto", { enc: typeof d.panels === "string" ? d.panels : "" });
          }, function () { if (small) phoneHint("Tonight's sheet could not be read from the page's store just now. Close the page and open it again."); });
        } catch (e) {}
      });
    });
  }
  function showPhone() {
    var dlg = $("phoneDlg"), body = $("phoneBody"); if (!dlg || !body) return;
    var dateISO = $("boardDate").value || todayISO();
    body.innerHTML = '<p class="note">Making the sheet…</p>'; dlg.hidden = false; document.body.classList.add("noscroll");
    var head = '<h3>Tonight on your phone <span class="tag">' + esc(gameDate(dateISO)) + '</span></h3>';
    var nothing = '<p class="note">Nothing on the board for ' + esc(gameDate(dateISO)) + ' yet: add the matchups, load the props, and the sheet carries them.</p>';
    var focus = function () { if ($("phoneClose")) $("phoneClose").focus(); };
    phoneStore().then(function (db) {
      if (!db) {
        if (phoneInViewer()) {   // on claude.ai without the store: the code's link cannot carry the picks here, so say so and do not draw one
          body.innerHTML = head + '<p class="note"><b>The sheet could not be saved for the phone</b>: this view was not given the page\'s store on claude.ai. Reload the page and press the button again, and allow it if a box asks. Until then, Copy as text under Taking tonight carries your bets.</p>';
          focus(); return;
        }
        return showPhoneCode(dateISO, head, nothing, focus);
      }
      var keep = { detail: { rows: [], seen: {} } }, P = phonePayload(dateISO, keep), n = phoneLines(P) + P.pairs.length, pk = { enc: "", n: 0, of: 0, map: {} };
      if (!n) { body.innerHTML = head + nothing; focus(); return; }
      return phonePanels(keep.detail).then(function (x) { pk = x; }, function () { pk = { enc: "", n: 0, of: 0, map: {} }; }).then(function () { return phoneSave(db, P, pk.enc); }).then(function () { return phoneViewerUrl(db); }).then(function (url) {
        var made = ""; try { made = new Date(P.at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }); } catch (e) { made = ""; }
        var h = head + '<p class="note phonesaved"><b>Saved for your phone</b>' + (made ? ' at ' + esc(made) : '') + ': ' + n + ' line' + (n === 1 ? '' : 's') +
                ', the bets and tickets you are taking first, then the parlay four, the best straight bets, the likeliest sides, the best props, the night\'s tickets and the simulation\'s calls.' +
                (pk.n ? ' Tap a prop, a ticket or a pair on the phone and its detail opens as it reads here: ' + pk.n + ' prop' + (pk.n === 1 ? '' : 's') + (pk.n < pk.of ? ' of ' + pk.of + ', the ones you are taking first (the rest did not fit one save)' : '') + '.' : '') + '</p>';
        if (url) {
          var qr = qrcode(0, "M"); qr.addData(url, "Byte"); qr.make();
          h += '<div class="qrbox small">' + qr.createSvgTag({ cellSize: 6, margin: 4, scalable: true }) + '</div>';
          h += '<p class="note"><b>Point your phone\'s camera at the code</b>, or open The Super Model in the Claude app on your phone. Tonight\'s sheet opens by itself, view only. Press this button again after a new run and the phone\'s sheet follows.</p>';
        } else {
          h += '<p class="note"><b>Open The Super Model in the Claude app on your phone</b>, or in its browser signed in to claude.ai. Tonight\'s sheet opens by itself, view only. Press this button again after a new run and the phone\'s sheet follows.</p>';
        }
        h += '<p class="note"><b>For someone else to see it</b>: share this page with them from the Share menu on claude.ai (Viewer is enough). Signed in to Claude, they scan the same code and get tonight\'s sheet with the detail behind each pick and nothing else, view only: only you can save over it, and your card never leaves this browser. For someone with no Claude account, <a href="#" id="phoneFile">save the sheet as a file</a> to send (the detail is folded under each pick, and it opens on any phone), or <a href="#" id="phoneCopy">copy it as text</a>. <span id="phoneSaid"></span></p>';
        h += '<p class="note dim">The sheet is kept in this page\'s own store on claude.ai, readable by you and by anyone you share the page with, and each save replaces the last. <a href="#" id="phonePreview">See the sheet as the phone shows it</a>' + (url ? ' · the code is this page\'s address, ' + qr.getModuleCount() + ' modules a side' : '') + '</p>';
        body.innerHTML = h;
        if ($("phonePreview")) $("phonePreview").addEventListener("click", function (e) { e.preventDefault(); phoneSheetShow(P, "preview", { map: pk.map }); });
        var said = function (msg) { if ($("phoneSaid")) $("phoneSaid").innerHTML = msg; };
        if ($("phoneCopy")) $("phoneCopy").addEventListener("click", function (e) { e.preventDefault(); copyText(phoneSheetText(P), said, "the sheet as text"); });
        if ($("phoneFile")) $("phoneFile").addEventListener("click", function (e) { e.preventDefault(); phoneFileSave(P, pk.map, said); });
        focus();
      }, function (e) {
        body.innerHTML = head + '<p class="note"><b>The sheet could not be saved for the phone</b>: ' + esc(phoneWhyNot(e)) + '. Press the button again in a moment. Until then, Copy as text under Taking tonight carries your bets.</p>';
        focus();
      });
    }).catch(function (e) { body.innerHTML = head + '<p class="note">The sheet could not be made (' + esc(String(e && e.message || e)) + ').</p>'; focus(); });
  }
  /* off claude.ai: the code carries the picks themselves to m.html beside this page, as it has since 26 Oct 2026 */
  function showPhoneCode(dateISO, head, nothing, focus) {
    var body = $("phoneBody");
    return phoneFit(dateISO).then(function (x) {
      var url = phoneUrlFor(x.enc), h = head;
      if (!x.n) {
        h += nothing;
      } else {
        var qr = qrcode(0, "L"); qr.addData(url, "Byte"); qr.make();
        h += '<div class="qrbox">' + qr.createSvgTag({ cellSize: 4, margin: 6, scalable: true }) + '</div>';
        h += '<p class="note"><b>Point your phone\'s camera at the code</b> and open the link. It shows ' + x.n + ' line' + (x.n === 1 ? '' : 's') + ': the bets you are taking, the parlay four, the best straight bets' +
             (x.cut ? '' : ', the likeliest sides, the best props, the night\'s tickets and the simulation\'s calls') + ', view only.' + (x.cut ? ' The night ran long for one code, so ' + esc(x.cut) + ' stayed off it.' : '') +
             ' The picks are inside the code itself, nothing is uploaded; press the button again after a new run for a fresh code. The page is private, so the phone has to be signed in to claude.ai to open it.</p>';
        h += '<p class="note dim"><a href="' + esc(url) + '" target="_blank" rel="noopener">Open the phone sheet in a tab</a> · ' + x.enc.length + ' characters in the code · ' + qr.getModuleCount() + ' modules a side</p>';
      }
      body.innerHTML = h;
      focus();
    });
  }
  function closePhone() { var dlg = $("phoneDlg"); if (!dlg) return; dlg.hidden = true; document.body.classList.remove("noscroll"); }
  if ($("phone")) {
    document.body.insertAdjacentHTML("beforeend",
      '<div id="phoneDlg" class="pdlg phone" hidden role="dialog" aria-modal="true" aria-label="Tonight on your phone"><div class="pdlg-box"><div class="pdlg-top"><button type="button" class="btn pdlg-close" id="phoneClose">Close</button></div><div id="phoneBody"></div></div></div>');
    $("phone").addEventListener("click", showPhone);
    $("phoneClose").addEventListener("click", closePhone);
    $("phoneDlg").addEventListener("click", function (e) { if (e.target === $("phoneDlg")) closePhone(); });
    document.addEventListener("keydown", function (e) {
      if (e.key !== "Escape") return;
      if (phonePanelShut()) return;   // the detail sits over the sheet: it closes first
      if ($("phoneSheet") && !$("phoneSheet").hidden) { phoneSheetShut(); return; }   // the sheet sits over the dialog: it closes next
      if (!$("phoneDlg").hidden) closePhone();
    });
  }
  setTimeout(phoneWatch, 0);   // after the page's first draw, so the card and the props are read
