  /* ===== PROPS BLOCK: NBA player props (19 Oct 2026) =====
     The user: "set up another tab for player props". slate.py's nba-props run
     writes one file a day with every prop The Odds API lists on the day's
     games and, beside each, the slate's own projection (rate x minutes, the
     regulars out, pace, defence v position) blended with the book's own
     chance. This tab lists them, keeps them, grades them from the nba-grade
     file's box lines, and keeps a record tile. The page scores NOTHING here: a
     prop row is the slate's call as made, so the record is of what was shown
     at the price it was shown. */
  var PROPS_KEY = "callsheet3.props.v1";
  var PROPS_LABEL = { pts: "points", reb: "rebounds", ast: "assists", tpm: "threes", pra: "pts + reb + ast" };
  var props = [];
  try { props = JSON.parse(localStorage.getItem(PROPS_KEY) || "[]"); if (!Array.isArray(props)) props = []; } catch (e) { props = []; }
  var propsView = false;
  /* the example (19 Oct 2026, the user: "put an example on the NBA props model
     like you did for the NBA"): one game's props computed at build time through
     the slate's own projection, previewed in the tab and never saved -- a real
     file, Clear this date or a sport button puts it away */
  var PROPS_EXAMPLE_GAMES = /*PROPS_EXAMPLE*/[];
  var propsPreview = null;
  function propsSource() { return propsPreview || props; }
  function saveProps() { try { localStorage.setItem(PROPS_KEY, JSON.stringify(props)); } catch (e) {} }
  function propsSay(msg) { var el = $("propsMsg"); if (!el) return; el.hidden = false; el.innerHTML = msg; }
  function propKey(r) { return (r.gdate || "") + "|" + r.pid + "|" + r.mk; }
  function propsDates() { var d = {}; propsSource().forEach(function (r) { if (r.gdate) d[r.gdate] = true; }); return Object.keys(d).sort(); }
  /* one row per player per market from a props file's games */
  function propsRowsFrom(d) {
    var rows = [];
    (d.games || []).forEach(function (g) {
      (g.props || []).forEach(function (x) {
        rows.push({ id: 0, gdate: d.date || "", game: g.away + " @ " + g.home, away: g.away, home: g.home, aab: g.aab, hab: g.hab, spread: g.spread, total: g.total, pace: g.pace,
                    pid: String(x.pid), name: x.name, team: x.team, opp: x.opp, athome: !!x.home, pos: x.pos || "", mk: x.mk, line: x.line, op: x.op, up: x.up, book: x.book, books: x.books || {},
                    proj: x.proj, sd: x.sd, pm: x.pm, pb: x.pb, p: x.p, push: x.push, side: x.side, chance: x.chance, price: x.price, need: x.need, edge: x.edge, band: x.band,
                    mins: x.mins, rate36: x.rate36, why: x.why || [], log: x.log || [], actual: null, result: null });
      });
    });
    return rows;
  }
  function propsExample() {
    var doc = { format: "callsheet3.props", date: todayISO(), games: PROPS_EXAMPLE_GAMES };
    propsPreview = propsRowsFrom(doc).map(function (r, i) { r.id = 90001 + i; return r; });
    if ($("propsDate")) $("propsDate").value = doc.date;
    showProps(true);
    propsSay("<b>An example</b>, one game's props as a real file lists them, with the projection built the slate's way. Nothing here is saved or graded: load a real props file, press Clear this date or a sport button, and it goes.");
  }
  function propsCanon(s) { return String(s || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim(); }
  function propHas(r) { return r.p !== null && r.p !== undefined; }
  /* the tab: the matchup columns go, the props section comes, the sport buttons read unpressed */
  function showProps(on) {
    propsView = !!on;
    if (!propsView) propsPreview = null;
    var cols = document.querySelector(".cols"); if (cols) cols.hidden = propsView;
    var v = $("propsView"); if (v) v.hidden = !propsView;
    var b = $("m-props"); if (b) b.setAttribute("aria-pressed", propsView ? "true" : "false");
    ["m-mlb", "m-nhl", "m-nba", "m-wnba"].forEach(function (id) { if (propsView && $(id)) $(id).setAttribute("aria-pressed", "false"); });
    if (!propsView && typeof sport === "string") { var sb = $("m-" + sport.toLowerCase()); if (sb) sb.setAttribute("aria-pressed", "true"); }
    if (propsView) { $("eyebrow").textContent = "NBA · player props"; renderProps(); }
    else if (typeof sport === "string") $("eyebrow").textContent = sport + " · every market on the game";
  }
  /* the file: one row per player per market per date; a row already graded is a record and stays */
  function applyProps(d, name) {
    if (!d || d.format !== "callsheet3.props" || !Array.isArray(d.games)) throw new Error("not a Super Model props file");
    var added = 0, replaced = 0, kept = 0, nextP = props.reduce(function (m, r) { return Math.max(m, r.id || 0); }, 0) + 1;
    var have = {}; props.forEach(function (r, i) { have[propKey(r)] = i; });
    propsPreview = null;
    propsRowsFrom(d).forEach(function (row) {
      var k = propKey(row), i = have[k];
      if (i !== undefined) { if (props[i].result) { kept++; return; } row.id = props[i].id; props[i] = row; replaced++; }
      else { row.id = nextP++; have[k] = props.length; props.push(row); added++; }
    });
    saveProps();
    if ($("propsDate") && d.date) $("propsDate").value = d.date;
    showProps(true); renderCalib();
    propsSay("Props " + (name ? "<b>" + esc(name) + "</b> " : "") + "loaded: <b>" + added + "</b> new, " + replaced + " replaced, " + kept + " graded and left as " +
             (kept === 1 ? "it was" : "they were") + ". A prop is the slate's call as made; the page does not rescore it.");
    return { added: added, replaced: replaced, kept: kept };
  }
  /* the grade: the nba-grade file carries each game's box by ESPN id,
     [name, minutes, points, rebounds, assists, threes]; a player with a prop
     and no box line did not play, and the row is void, as the books void it */
  function propActual(r, box) {
    var b = box[r.pid]; if (!b) return null;
    var v = { pts: b[2], reb: b[3], ast: b[4], tpm: b[5] }[r.mk];
    if (r.mk === "pra") v = (b[2] === null || b[2] === undefined || b[3] === null || b[3] === undefined || b[4] === null || b[4] === undefined) ? null : b[2] + b[3] + b[4];
    return (v === null || v === undefined) ? undefined : v;
  }
  function gradeProps(d) {
    if (!d || !Array.isArray(d.games)) return 0;
    var n = 0;
    d.games.forEach(function (g) {
      if (!g.box) return;
      props.forEach(function (r) {
        if (r.result || (r.gdate || "") !== (g.gdate || d.date || "")) return;
        if (propsCanon(r.away) !== propsCanon(g.away) || propsCanon(r.home) !== propsCanon(g.home)) return;
        var v = propActual(r, g.box);
        if (v === undefined) return;
        if (v === null) { r.result = "void"; r.actual = null; n++; return; }
        r.actual = v;
        r.result = !r.side ? "graded" : (v === r.line ? "push" : ((v > r.line) === (r.side === "OVER") ? "win" : "loss"));
        n++;
      });
    });
    if (n) { saveProps(); renderProps(); }
    return n;
  }
  /* the record tile: every graded prop with a side, by market, by band, by side; says is the blended chance */
  function propsRecordHtml() {
    var graded = props.filter(function (r) { return r.result && r.result !== "graded"; });
    if (!graded.length) return "";
    var mk = function () { return { n: 0, w: 0, l: 0, p: 0, v: 0, says: 0, units: 0 }; };
    var all = mk(), byMk = {}, byBand = {}, bySide = {};
    var dec = function (price) { return price > 0 ? 1 + price / 100 : 1 + 100 / (-price); };
    graded.forEach(function (r) {
      [all, byMk[r.mk] || (byMk[r.mk] = mk()), byBand[r.band] || (byBand[r.band] = mk()), bySide[r.side] || (bySide[r.side] = mk())].forEach(function (s) {
        if (r.result === "void") { s.v++; return; }
        if (r.result === "push") { s.p++; return; }
        s.n++; s.says += r.chance;
        if (r.result === "win") { s.w++; s.units += dec(r.price) - 1; } else { s.l++; s.units -= 1; }
      });
    });
    var rec = function (s) { return s.w + "-" + s.l + (s.p ? "-" + s.p : ""); };
    var line = function (s) {
      if (!s.n) return "pushes only";
      return "says " + (s.says / s.n * 100).toFixed(1) + "% · does " + (s.w / s.n * 100).toFixed(1) + "% (±" + (100 / Math.sqrt(s.n) / 2).toFixed(1) + ") · " + sgn(s.units, 2) + "u";
    };
    var tile = function (label, s, parts) {
      return '<div><p class="k">' + esc(label) + '</p><p class="v">' + rec(s) + '</p><p class="s">' + line(s) + (s.v ? ' · ' + s.v + ' void' : '') + '</p>' +
        (parts && parts.length ? '<p class="s sides">' + esc(parts.join(" · ")) + '</p>' : '') + '</div>';
    };
    var parts = [];
    ["OVER", "UNDER"].forEach(function (sd) { if (bySide[sd]) parts.push(sd.toLowerCase() + " " + rec(bySide[sd])); });
    ["BET", "LEAN", "no edge"].forEach(function (b) { if (byBand[b]) parts.push(b + " " + rec(byBand[b]) + (byBand[b].n ? " " + sgn(byBand[b].units, 1) + "u" : "")); });
    var h = '<div class="subhead" data-sport="PROPS">NBA player props <span class="tag">' + graded.length + ' graded · the slate\'s call as made, at the price posted · says is the blended chance</span></div>';
    h += '<div class="calib" data-sport="PROPS">' + tile("Every prop with a side", all, parts);
    ["pts", "reb", "ast", "tpm", "pra"].forEach(function (k) { if (byMk[k]) h += tile(PROPS_LABEL[k], byMk[k], []); });
    h += '</div>';
    h += '<div class="verdict">The props are a priori: the pooled rules behind them were measured on last season\'s box scores, the blend\'s weights were not. Read the BET band against the rest and <i>does</i> against <i>says</i>; under 100 graded props nothing here is a reading.</div>';
    return h;
  }
  function renderProps() {
    var v = $("propsView"); if (!v) return;
    var dates = propsDates(), sel = $("propsDate");
    if (!sel.value || dates.indexOf(sel.value) < 0) sel.value = dates.length ? dates[dates.length - 1] : "";
    var date = sel.value;
    var rows = propsSource().filter(function (r) { return (r.gdate || "") === date; });
    $("propsCount").textContent = (propsPreview ? "EXAMPLE · " : "") + (rows.length ? rows.length + " props on " + gameDate(date) + " · " + dates.length + " date" + (dates.length === 1 ? "" : "s") + " kept"
                                              : (propsSource().length ? "no props on this date" : "no props loaded"));
    var resChip = function (r) {
      if (!r.result) return '';
      var cls = r.result === "win" ? "win" : r.result === "loss" ? "loss" : "push";
      return ' <span class="chip ' + cls + '">' + esc(r.result === "void" ? "VOID · did not play" : r.result.toUpperCase()) + (r.actual !== null && r.actual !== undefined ? " · " + r.actual : "") + '</span>';
    };
    var picks = rows.filter(function (r) { return propHas(r) && r.edge > 0; }).sort(function (a, b) { return b.edge - a.edge; });
    $("propsBest").innerHTML = picks.length ? picks.slice(0, 12).map(function (r, i) {
      return '<div class="pk' + (r.band === "BET" ? ' scored' : '') + '" data-prop="' + r.id + '"><div class="n1">#' + (i + 1) + ' · ' + esc(r.band) + '</div>' +
        '<div class="n2">' + esc(r.name) + ' ' + esc(r.side) + ' ' + r.line + ' ' + esc(PROPS_LABEL[r.mk] || r.mk) + '</div>' +
        '<div class="n3">' + (r.chance * 100).toFixed(1) + '% · ' + sgn(r.price, 0) + ' needs ' + (r.need * 100).toFixed(1) + '% · edge ' + sgn(r.edge * 100, 1) + resChip(r) + '</div>' +
        '<div class="n4">' + esc(r.game) + ' · projected ' + r.proj + ' (±' + r.sd + ') · ' + esc(r.book) + '</div></div>';
    }).join("") : '<div class="empty">' + (rows.length ? 'No prop on this date clears its price.' : 'Load a props file: Run NBA props.bat writes nba-props-DATE.json.') + '</div>';
    var list = ($("propsAll").checked ? rows : rows.filter(propHas)).slice().sort(function (a, b) {
      return (a.game < b.game ? -1 : a.game > b.game ? 1 : 0) || ((propHas(b) ? b.edge : -9) - (propHas(a) ? a.edge : -9));
    });
    var h = '<table class="form props"><thead><tr><th>Game</th><th>Player</th><th>Market</th><th>Line</th><th>Pick</th><th>Chance</th><th>Price</th><th>Needs</th><th>Edge</th><th>Proj</th><th>Band</th><th>Result</th></tr></thead><tbody>';
    list.forEach(function (r) {
      h += '<tr data-prop="' + r.id + '" class="' + (r.result || '') + '"><td>' + esc(r.game) + '</td><td>' + esc(r.name) + (r.pos ? ' <span class="tag">' + esc(r.pos) + '</span>' : '') + '</td>' +
        '<td>' + esc(PROPS_LABEL[r.mk] || r.mk) + '</td><td>' + r.line + ' (' + sgn(r.op, 0) + '/' + sgn(r.up, 0) + ')</td>' +
        (propHas(r) ? '<td>' + esc(r.side) + '</td><td>' + (r.chance * 100).toFixed(1) + '%</td><td>' + sgn(r.price, 0) + '</td><td>' + (r.need * 100).toFixed(1) + '%</td>' +
                      '<td class="' + (r.edge > 0 ? 'pos' : 'neg') + '">' + sgn(r.edge * 100, 1) + '</td><td>' + r.proj + '</td><td>' + esc(r.band) + '</td>'
                    : '<td colspan="7" class="dim">' + esc((r.why && r.why[0]) || 'no projection') + '</td>') +
        '<td>' + (r.result ? esc(r.result) + (r.actual !== null && r.actual !== undefined ? ' · ' + r.actual : '') : '') + '</td></tr>';
      h += '<tr class="why" data-why="' + r.id + '" hidden><td colspan="12"><ul>' + (r.why || []).map(function (w) { return '<li>' + esc(w) + '</li>'; }).join('') +
        (r.log && r.log.length ? '<li>last games: ' + esc(r.log.map(function (g) { return String(g[0] || "").slice(5) + " " + (g[2] ? "v " : "@ ") + g[1] + " " + g[3] + "m " + (g[4] === null || g[4] === undefined ? "?" : g[4]); }).join(" · ")) + '</li>' : '') +
        (r.books && Object.keys(r.books).length > 1 ? '<li>books: ' + esc(Object.keys(r.books).map(function (b) { return b + " " + r.books[b][0] + " (" + sgn(r.books[b][1], 0) + "/" + sgn(r.books[b][2], 0) + ")"; }).join(" · ")) + '</li>' : '') +
        '</ul></td></tr>';
    });
    h += '</tbody></table>';
    $("propsTable").innerHTML = rows.length ? h : '';
  }
  function propsAsText() {
    var date = $("propsDate").value;
    var rows = props.filter(function (r) { return (r.gdate || "") === date && propHas(r); }).sort(function (a, b) { return b.edge - a.edge; });
    var out = ["The Super Model — NBA props — " + gameDate(date)];
    rows.forEach(function (r, i) {
      out.push((i + 1) + ". " + r.name + " " + r.side + " " + r.line + " " + (PROPS_LABEL[r.mk] || r.mk) + " " + sgn(r.price, 0) + " · " + (r.chance * 100).toFixed(1) + "% needs " +
               (r.need * 100).toFixed(1) + "% · " + r.band + " · " + r.game + " · proj " + r.proj + (r.result ? " · " + r.result.toUpperCase() + (r.actual !== null && r.actual !== undefined ? " " + r.actual : "") : ""));
    });
    return out.join("\n");
  }
  if ($("m-props")) {
    $("m-props").addEventListener("click", function () { showProps(!propsView); });
    $("loadProps").addEventListener("click", function () { $("slateFile").click(); });
    $("propsDate").addEventListener("change", renderProps);
    $("propsAll").addEventListener("change", renderProps);
    $("propsExample").addEventListener("click", propsExample);
    $("propsClear").addEventListener("click", function () {
      if (propsPreview) { propsPreview = null; renderProps(); propsSay("The example is gone. Load a real props file when you have one."); return; }
      var date = $("propsDate").value, before = props.length;
      props = props.filter(function (r) { return (r.gdate || "") !== date || r.result; });
      saveProps(); renderProps(); renderCalib();
      propsSay("Cleared <b>" + (before - props.length) + "</b> ungraded prop" + (before - props.length === 1 ? "" : "s") + " on " + esc(gameDate(date)) + "; graded ones are records and stay.");
    });
    $("propsText").addEventListener("click", function () {
      var text = propsAsText();
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(function () { propsSay("Copied the props as text."); }, function () { propsSay("The clipboard is blocked here; the text is below.<pre>" + esc(text) + "</pre>"); });
      else propsSay("<pre>" + esc(text) + "</pre>");
    });
    var toggleWhy = function (e) {
      var t = e.target.closest("[data-prop]"); if (!t) return;
      var w = document.querySelector('#propsTable tr[data-why="' + t.getAttribute("data-prop") + '"]');
      if (w) { w.hidden = !w.hidden; if (!w.hidden && w.scrollIntoView) w.scrollIntoView({ block: "nearest" }); }
    };
    $("propsTable").addEventListener("click", toggleWhy);
    $("propsBest").addEventListener("click", toggleWhy);
  }
  /* ===== END PROPS BLOCK ===== */
