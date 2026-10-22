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
  var propsOrder = [], propDetailId = null;   // the Every-prop table's order, and the prop the panel shows (22 Oct 2026)
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
                    mins: x.mins, rate36: x.rate36, base: x.base, parts: x.parts || [], why: x.why || [], log: x.log || [], actual: null, result: null });
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
    if (!propsView) { propsPreview = null; closePropDetail(); }
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
  /* the record: every graded prop with a side, by market, by band, by side; says is the blended chance.
     propsRecordHtml() is the block on the card's "Is it working" section; propsRecordHtml(true) is the
     fuller one on the Props tab itself (22 Oct 2026, the user: "a section at the top similar to the
     'is this working' on the other models"): the bands as tiles, the edge the sheet claimed, the centre
     the chance was read around (the mean to 21 Oct, the median from 22 Oct), night by night, and
     says against does by the chance claimed */
  var PROPS_EDGE_BUCKETS = ["10+ points of edge", "6 to 10 points", "3 to 6 points", "under 3 points", "no edge"];
  var PROPS_CHANCE_BUCKETS = ["50 to 55%", "55 to 60%", "60 to 65%", "65% and up"];
  function propsEdgeBucket(r) { var e = (r.edge || 0) * 100; return e >= 10 ? PROPS_EDGE_BUCKETS[0] : e >= 6 ? PROPS_EDGE_BUCKETS[1] : e >= 3 ? PROPS_EDGE_BUCKETS[2] : e > 0 ? PROPS_EDGE_BUCKETS[3] : PROPS_EDGE_BUCKETS[4]; }
  function propsChanceBucket(r) { var c = (r.chance || 0) * 100; return c < 55 ? PROPS_CHANCE_BUCKETS[0] : c < 60 ? PROPS_CHANCE_BUCKETS[1] : c < 65 ? PROPS_CHANCE_BUCKETS[2] : PROPS_CHANCE_BUCKETS[3]; }
  function propsCentre(r) { return (r.why || []).some(function (w) { return /around the median/.test(String(w)); }) ? "median" : "mean"; }
  function propsRecordHtml(full) {
    var graded = props.filter(function (r) { return r.result && r.result !== "graded"; });
    if (!graded.length) return "";
    var mk = function () { return { n: 0, w: 0, l: 0, p: 0, v: 0, says: 0, units: 0 }; };
    var all = mk(), byMk = {}, byBand = {}, bySide = {}, byEdge = {}, byChance = {}, byDate = {}, byDateBet = {}, byCentre = {};
    var dec = function (price) { return price > 0 ? 1 + price / 100 : 1 + 100 / (-price); };
    graded.forEach(function (r) {
      var d = r.gdate || "?";
      var sinks = [all, byMk[r.mk] || (byMk[r.mk] = mk()), byBand[r.band] || (byBand[r.band] = mk()), bySide[r.side] || (bySide[r.side] = mk()),
                   byEdge[propsEdgeBucket(r)] || (byEdge[propsEdgeBucket(r)] = mk()), byChance[propsChanceBucket(r)] || (byChance[propsChanceBucket(r)] = mk()),
                   byDate[d] || (byDate[d] = mk()), byCentre[propsCentre(r)] || (byCentre[propsCentre(r)] = mk())];
      if (r.band === "BET") sinks.push(byDateBet[d] || (byDateBet[d] = mk()));
      sinks.forEach(function (s) {
        if (r.result === "void") { s.v++; return; }
        if (r.result === "push") { s.p++; return; }
        s.n++; s.says += r.chance;
        if (r.result === "win") { s.w++; s.units += dec(r.price) - 1; } else { s.l++; s.units -= 1; }
      });
    });
    var rec = function (s) { return s.w + "-" + s.l + (s.p ? "-" + s.p : ""); };
    var says = function (s) { return s.n ? (s.says / s.n * 100).toFixed(1) + "%" : "—"; };
    var does = function (s) { return s.n ? (s.w / s.n * 100).toFixed(1) + "%" : "—"; };
    var line = function (s) {
      if (!s.n) return "pushes only";
      return "says " + says(s) + " · does " + does(s) + " (±" + (100 / Math.sqrt(s.n) / 2).toFixed(1) + ") · " + sgn(s.units, 2) + "u";
    };
    /* the tab's tiles carry colour (22 Oct 2026, the user: "jazz that up with some colors"): the record
       green when the units are up and red when down, does marked against says the same way */
    var tile = function (label, s, parts) {
      var cls = full && s.n ? (s.units > 0 ? ' class="good"' : s.units < 0 ? ' class="bad"' : '') : '';
      var body = line(s);
      if (full && s.n) body = "says " + says(s) + ' · does <span class="does ' + (s.w / s.n >= s.says / s.n ? 'up' : 'down') + '">' + does(s) + '</span> (±' + (100 / Math.sqrt(s.n) / 2).toFixed(1) + ') · <span class="units">' + sgn(s.units, 2) + 'u</span>';
      return '<div' + cls + '><p class="k">' + esc(label) + '</p><p class="v">' + rec(s) + '</p><p class="s">' + body + (s.v ? ' · ' + s.v + ' void' : '') + '</p>' +
        (parts && parts.length ? '<p class="s sides">' + esc(parts.join(" · ")) + '</p>' : '') + '</div>';
    };
    var parts = [];
    ["OVER", "UNDER"].forEach(function (sd) { if (bySide[sd]) parts.push(sd.toLowerCase() + " " + rec(bySide[sd])); });
    ["BET", "LEAN", "no edge"].forEach(function (b) { if (byBand[b]) parts.push(b + " " + rec(byBand[b]) + (byBand[b].n ? " " + sgn(byBand[b].units, 1) + "u" : "")); });
    var markets = ["pts", "reb", "ast", "tpm", "pra"].map(function (k) { return byMk[k] ? tile(PROPS_LABEL[k], byMk[k], []) : ""; }).join("");
    var verdict = 'The props are a priori: the pooled rules behind them were measured on last season\'s box scores, the blend\'s weights were not. Read the BET band against the rest and <i>does</i> against <i>says</i>; under 100 graded props nothing here is a reading.';
    if (!full) {
      var h = '<div class="subhead" data-sport="PROPS">NBA player props <span class="tag">' + graded.length + ' graded · the slate\'s call as made, at the price posted · says is the blended chance</span></div>';
      h += '<div class="calib" data-sport="PROPS">' + tile("Every prop with a side", all, parts) + markets + '</div>';
      h += '<div class="verdict">' + verdict + '</div>';
      return h;
    }
    var dates = Object.keys(byDate).sort();
    var h2 = '<div class="calib" data-sport="PROPS-TAB">' + tile("Every prop with a side", all, parts.slice(0, 2));
    ["BET", "LEAN", "no edge"].forEach(function (b) { if (byBand[b]) h2 += tile(b === "no edge" ? "No edge: the book's own side" : b + " band", byBand[b], []); });
    h2 += '</div>';
    h2 += '<div class="subhead">By market</div><div class="calib" data-sport="PROPS-MK">' + markets + '</div>';
    h2 += '<div class="subhead">By the edge the sheet claimed <span class="tag">the chance less what the price needs</span></div><div class="calib" data-sport="PROPS-EDGE">' +
          PROPS_EDGE_BUCKETS.map(function (b) { return byEdge[b] ? tile(b, byEdge[b], []) : ""; }).join("") + '</div>';
    h2 += '<div class="subhead">By the centre the chance was read around <span class="tag">the mean to 21 Oct 2026, the median from the 22nd: a box-score stat skews right</span></div><div class="calib" data-sport="PROPS-CENTRE">' +
          (byCentre.mean ? tile("Called at the mean, to 21 Oct", byCentre.mean, []) : "") + (byCentre.median ? tile("Called at the median, from 22 Oct", byCentre.median, []) : "") + '</div>';
    h2 += '<div class="subhead">Night by night <span class="tag">' + dates.length + ' night' + (dates.length === 1 ? '' : 's') + ' graded</span></div>' +
          '<table class="form" id="propsNights"><thead><tr><th>Night</th><th>Record</th><th>Says</th><th>Does</th><th>Units</th><th>BET band</th></tr></thead><tbody>' +
          dates.slice().reverse().map(function (d) {
            var s = byDate[d], b = byDateBet[d];
            var up = s.n && s.w / s.n >= s.says / s.n;
            return '<tr><td>' + esc(gameDate(d)) + '</td><td class="' + (s.units >= 0 ? 'pos' : 'neg') + '">' + rec(s) + (s.v ? ' <span class="dim">' + s.v + ' void</span>' : '') + '</td><td>' + says(s) + '</td><td class="' + (up ? 'pos' : 'neg') + '">' + does(s) + '</td><td class="' + (s.units >= 0 ? 'pos' : 'neg') + '">' + sgn(s.units, 1) + 'u</td>' +
                   '<td class="' + (b ? (b.units >= 0 ? 'pos' : 'neg') : '') + '">' + (b ? rec(b) + ' ' + sgn(b.units, 1) + 'u' : '—') + '</td></tr>';
          }).join("") + '</tbody></table>';
    h2 += '<div class="subhead">Says against does, by the chance claimed <span class="tag">a calibrated sheet reads the same in both columns</span></div>' +
          '<table class="form" id="propsLadder"><thead><tr><th>Chance claimed</th><th>Props</th><th>Says</th><th>Does</th><th>±</th><th>Units</th></tr></thead><tbody>' +
          PROPS_CHANCE_BUCKETS.map(function (b) {
            var s = byChance[b]; if (!s || !s.n) return "";
            var up = s.w / s.n >= s.says / s.n;
            return '<tr><td>' + esc(b) + '</td><td>' + s.n + '</td><td>' + says(s) + '</td><td class="' + (up ? 'pos' : 'neg') + '">' + does(s) + '</td><td>' + (100 / Math.sqrt(s.n) / 2).toFixed(1) + '</td><td class="' + (s.units >= 0 ? 'pos' : 'neg') + '">' + sgn(s.units, 1) + 'u</td></tr>';
          }).join("") + '</tbody></table>';
    h2 += '<div class="verdict">' + verdict + ' The first two nights (829 props) were called at the mean and read 423-406, the sheet saying 55.7% and doing 51.0%; ' +
          're-scored at the median they read 452-377 with the say-so within a point of the done. The median tile is the one to read from here, on its own, once it has a hundred props.</div>';
    return h2;
  }
  function propResChip(r) {
    if (!r.result) return '';
    var cls = r.result === "win" ? "win" : r.result === "loss" ? "loss" : "push";
    return ' <span class="chip ' + cls + '">' + esc(r.result === "void" ? "VOID · did not play" : r.result.toUpperCase()) + (r.actual !== null && r.actual !== undefined ? " · " + r.actual : "") + '</span>';
  }
  /* the last games (20 Oct 2026, the user: "highlight their scored numbers so it's easy to see"):
     the stat of each game in its own mark, green over the prop's line, red under it, grey on it,
     and a tally at the end of how many of them cleared the number */
  function propsLogMark(v, line) {
    var val = (v === null || v === undefined || v === "") ? null : +v;
    var cls = val === null || line === null || line === undefined || isNaN(+line) ? "" : (val > +line ? " over" : val < +line ? " under" : " push");
    return '<b class="lg' + cls + '">' + (val === null ? "?" : esc(String(v))) + '</b>';
  }
  function propsLogTally(r) {
    var vals = (r.log || []).map(function (g) { return g[4]; }).filter(function (v) { return v !== null && v !== undefined && v !== "" && !isNaN(+v); });
    if (!vals.length || r.line === null || r.line === undefined || isNaN(+r.line)) return "";
    var over = vals.filter(function (v) { return +v > +r.line; }).length, push = vals.filter(function (v) { return +v === +r.line; }).length;
    return ' <span class="dim">(' + over + " of " + vals.length + " over " + r.line + (push ? ", " + push + " on it" : "") + ")</span>";
  }
  /* ---- the detail panel (21 Oct 2026, the user: "when I click one, could you have it open a
     page or something with the details of the prop instead of in the list below"): a best-prop
     card opens the prop on its own panel over the page, the numbers as tiles, the why as a
     list, the last games as a table with the marks, every book's line; a table row still folds
     its why open below it. Escape, the Close button or a click outside puts it away ---- */
  function propById(id) {
    var s = propsSource();
    for (var i = 0; i < s.length; i++) if (String(s[i].id) === String(id)) return s[i];
    return null;
  }
  /* what moves it (21 Oct 2026, the user: "highlight the areas of the prop bet that are helping
     with the prediction the most"): the slate writes each factor's push on the projection in the
     stat's units (parts: regulars out, pace, the defence, last season's prior, the minutes
     trend), each pointing at its why line. Ranked by size, largest first; a push toward the
     pick's side helps, away from it hurts */
  function propsLevers(r) {
    return (r.parts || []).filter(function (p) { return p && isFinite(+p.eff); }).slice().sort(function (a, b) { return Math.abs(b.eff) - Math.abs(a.eff); });
  }
  function propsLeverHelps(r, eff) { return r.side === "UNDER" ? eff < 0 : eff > 0; }
  function propsLeversLine(r) {
    var lv = propsLevers(r).slice(0, 2);
    return lv.length ? lv.map(function (p) { return esc(p.t) + " " + sgn(+p.eff, 1); }).join(" · ") : "";
  }
  function propsDetailHtml(r) {
    var has = propHas(r), lab = PROPS_LABEL[r.mk] || r.mk;
    var tile = function (k, v, s, cls) { return '<div class="pd-tile' + (cls ? ' ' + cls : '') + '"><div class="k">' + esc(k) + '</div><div class="v">' + v + '</div>' + (s ? '<div class="s">' + s + '</div>' : '') + '</div>'; };
    var h = '<div class="pd-band">' + esc(has ? r.band : "no projection") + '</div>';
    h += '<h3>' + esc(r.name) + (r.pos ? ' <span class="tag">' + esc(r.pos) + '</span>' : '') + (r.team ? ' <span class="tag">' + esc(r.team) + '</span>' : '') + '</h3>';
    h += '<div class="pd-pick">' + (has ? esc(r.side) + ' ' : '') + esc(String(r.line)) + ' ' + esc(lab) + propResChip(r) + '</div>';
    h += '<div class="pd-sub">' + esc(r.game) + ' · ' + esc(gameDate(r.gdate)) + (r.opp ? ' · ' + (r.athome ? 'at home against ' : 'on the road at ') + esc(r.opp) : '') +
         ' · ' + esc(r.book || "the book") + ' ' + esc(String(r.line)) + ' (' + sgn(r.op, 0) + '/' + sgn(r.up, 0) + ')</div>';
    if (has) {
      h += '<div class="pd-tiles">' +
        tile("Chance", (r.chance * 100).toFixed(1) + "%", "blended: the over is " + (r.pm * 100).toFixed(1) + "% by the model, " + (r.pb * 100).toFixed(1) + "% by the book") +
        tile("Price", sgn(r.price, 0), "needs " + (r.need * 100).toFixed(1) + "%") +
        tile("Edge", sgn(r.edge * 100, 1), "points of chance over the price", r.edge > 0 ? "good" : "bad") +
        tile("Projection", esc(String(r.proj)), "± " + esc(String(r.sd)) + " one sigma") +
        tile("Minutes", esc(String(r.mins)), "projected") +
        tile("Per 36", esc(String(r.rate36)), esc(lab) + " per 36 minutes") +
        '</div>';
    } else {
      h += '<p class="note">' + esc((r.why && r.why[0]) || "No projection on this prop.") + '</p>';
    }
    var levers = has ? propsLevers(r) : [], top = levers.slice(0, 2).map(function (p) { return +p.i; });
    if (levers.length && r.base !== undefined && r.base !== null) {
      var maxE = Math.max.apply(null, levers.map(function (p) { return Math.abs(+p.eff); }).concat([0.01])), gap = r.proj - r.line;
      h += '<h4>What moves it</h4><p class="pd-base">Starts from <b>' + esc(String(r.base)) + '</b>, his ' + esc(String(r.rate36)) + ' per 36 at his minutes; the regulars out, pace and the defence take it to <b>' + esc(String(r.proj)) +
           '</b>, ' + sgn(gap, 1) + ' against the line. Green pushes toward the ' + esc(r.side || "pick") + ', red away from it. The prior and the minutes trend say what sits inside the start.</p>';
      h += '<div class="pd-levers">' + levers.map(function (p, i) {
        var helps = propsLeverHelps(r, +p.eff), w = Math.max(3, Math.round(Math.abs(+p.eff) / maxE * 100));
        return '<div class="lever' + (helps ? ' helps' : ' hurts') + (i === 0 ? ' top' : '') + '"><div class="lt">' + esc(p.t) + (i === 0 ? ' <span class="tag">biggest lever</span>' : '') + '</div>' +
               '<div class="lb"><span style="width:' + w + '%"></span></div><div class="lv">' + sgn(+p.eff, 1) + '</div></div>';
      }).join("") + '</div>';
    }
    if (r.why && r.why.length) h += '<h4>Why</h4><ul class="pd-why">' + r.why.map(function (w, i) { return '<li' + (top.indexOf(i) >= 0 ? ' class="lever-line"' : '') + '>' + esc(w) + '</li>'; }).join("") + '</ul>';
    if (r.log && r.log.length) {
      h += '<h4>Last games' + propsLogTally(r) + '</h4><table class="form pd-log"><thead><tr><th>Date</th><th>Opp</th><th>Min</th><th>' + esc(lab) + '</th></tr></thead><tbody>' +
        r.log.map(function (g) {
          return '<tr><td>' + esc(String(g[0] || "").slice(5)) + '</td><td>' + esc((g[2] ? "v " : "@ ") + (g[1] || "")) + '</td><td>' + esc(String(g[3] === null || g[3] === undefined ? "" : g[3])) + '</td><td>' + propsLogMark(g[4], r.line) + '</td></tr>';
        }).join("") + '</tbody></table>';
    }
    var bks = Object.keys(r.books || {});
    if (bks.length) {
      h += '<h4>Every book</h4><table class="form pd-books"><thead><tr><th>Book</th><th>Line</th><th>Over</th><th>Under</th></tr></thead><tbody>' + bks.map(function (b) {
        var x = r.books[b] || [];
        return '<tr' + (b === r.book ? ' class="carded"' : '') + '><td>' + esc(b) + (b === r.book ? ' <span class="tag">carded</span>' : '') + '</td><td>' + esc(String(x[0])) + '</td><td>' + (x[1] === null || x[1] === undefined ? "" : sgn(+x[1], 0)) + '</td><td>' + (x[2] === null || x[2] === undefined ? "" : sgn(+x[2], 0)) + '</td></tr>';
      }).join("") + '</tbody></table>';
    }
    h += '<p class="note">A prop is the slate\'s call as made at the price posted; the page does not rescore it, and the Props record tile is the test.</p>';
    return h;
  }
  /* a best-prop card or a row of the Every-prop table opens the panel (22 Oct 2026, the user:
     "the same for the entries on the list so they are easy to review"); Previous / Next and the
     arrow keys walk the table's order from there */
  function openPropDetail(id) {
    var r = propById(id), dlg = $("propDetail"); if (!r || !dlg) return;
    propDetailId = String(id);
    $("propDetailBody").innerHTML = propsDetailHtml(r);
    var i = propsOrder.indexOf(propDetailId), nav = $("propDetailNav");
    if (nav) {
      nav.hidden = i < 0 || propsOrder.length < 2;
      $("propDetailPos").textContent = i >= 0 ? (i + 1) + " of " + propsOrder.length : "";
      $("propDetailPrev").disabled = i <= 0;
      $("propDetailNext").disabled = i < 0 || i >= propsOrder.length - 1;
    }
    dlg.hidden = false; dlg.scrollTop = 0;
    document.body.classList.add("noscroll");
    if ($("propDetailClose")) $("propDetailClose").focus();
  }
  function stepPropDetail(d) {
    var i = propsOrder.indexOf(propDetailId); if (i < 0) return;
    var j = i + d; if (j < 0 || j >= propsOrder.length) return;
    openPropDetail(propsOrder[j]);
  }
  function closePropDetail() {
    var dlg = $("propDetail"); if (!dlg) return;
    dlg.hidden = true; propDetailId = null;
    document.body.classList.remove("noscroll");
  }
  function renderProps() {
    var v = $("propsView"); if (!v) return;
    var dates = propsDates(), sel = $("propsDate");
    if (!sel.value || dates.indexOf(sel.value) < 0) sel.value = dates.length ? dates[dates.length - 1] : "";
    var date = sel.value;
    var rows = propsSource().filter(function (r) { return (r.gdate || "") === date; });
    if ($("propsCalib")) $("propsCalib").innerHTML = propsRecordHtml(true) || '<div class="verdict">Nothing graded yet. The morning\'s grade file (Grade NBA yesterday.bat, then Load slate) grades every prop with a side against the box score, and the record builds here: by band, by market, by the edge claimed, night by night, and says against does.</div>';
    $("propsCount").textContent =(propsPreview ? "EXAMPLE · " : "") + (rows.length ? rows.length + " props on " + gameDate(date) + " · " + dates.length + " date" + (dates.length === 1 ? "" : "s") + " kept"
                                              : (propsSource().length ? "no props on this date" : "no props loaded"));
    var resChip = propResChip;
    var picks = rows.filter(function (r) { return propHas(r) && r.edge > 0; }).sort(function (a, b) { return b.edge - a.edge; });
    $("propsBest").innerHTML = picks.length ? picks.slice(0, 12).map(function (r, i) {
      return '<div class="pk' + (r.band === "BET" ? ' scored' : '') + '" data-prop="' + r.id + '"><div class="n1">#' + (i + 1) + ' · ' + esc(r.band) + '</div>' +
        '<div class="n2">' + esc(r.name) + ' ' + esc(r.side) + ' ' + r.line + ' ' + esc(PROPS_LABEL[r.mk] || r.mk) + '</div>' +
        '<div class="n3">' + (r.chance * 100).toFixed(1) + '% · ' + sgn(r.price, 0) + ' needs ' + (r.need * 100).toFixed(1) + '% · edge ' + sgn(r.edge * 100, 1) + resChip(r) + '</div>' +
        '<div class="n4">' + esc(r.game) + ' · projected ' + r.proj + ' (±' + r.sd + ') · ' + esc(r.book) + '</div>' +
        (propsLeversLine(r) ? '<div class="n5">Moves it: ' + propsLeversLine(r) + '</div>' : '') + '</div>';
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
    });
    h += '</tbody></table>';
    propsOrder = list.map(function (r) { return String(r.id); });   // the panel's Previous / Next walk the table's order
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
    var openFrom = function (e) { var t = e.target.closest("[data-prop]"); if (t) openPropDetail(t.getAttribute("data-prop")); };
    $("propsTable").addEventListener("click", openFrom);
    $("propsBest").addEventListener("click", openFrom);
    if ($("propDetail")) {
      $("propDetailClose").addEventListener("click", closePropDetail);
      $("propDetailPrev").addEventListener("click", function () { stepPropDetail(-1); });
      $("propDetailNext").addEventListener("click", function () { stepPropDetail(1); });
      $("propDetail").addEventListener("click", function (e) { if (e.target === $("propDetail")) closePropDetail(); });
      document.addEventListener("keydown", function (e) {
        if ($("propDetail").hidden) return;
        var tag = e.target && e.target.tagName ? e.target.tagName.toLowerCase() : "";
        if (e.key === "Escape") closePropDetail();
        else if (e.key === "ArrowLeft" && tag !== "input" && tag !== "textarea") stepPropDetail(-1);
        else if (e.key === "ArrowRight" && tag !== "input" && tag !== "textarea") stepPropDetail(1);
      });
    }
  }
  /* ===== END PROPS BLOCK ===== */
