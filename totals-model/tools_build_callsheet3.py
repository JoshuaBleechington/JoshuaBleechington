"""Assemble web/callsheet3.html -- Call Sheet 3.0: MLB, NHL and WNBA on one page.

    python3 tools_build_callsheet3.py

3.0 is DERIVED from 2.0's sources rather than copied: the head and the tail
are read from web/callsheet2.head.html and web/callsheet2.tail.js, a fixed
list of edits is applied (each anchor must match EXACTLY ONCE, or the build
stops and says which one did not), the NHL form sections come from
web/callsheet3.nhl-fields.html, and the NHL engine from web/nhl.engine.js is
placed after Call Sheet #1's engine block. So a fix to 2.0 reaches 3.0 on
the next build, and a change to 2.0 that would silently break 3.0 breaks
this script loudly instead. The page is head + ENGINE BLOCK (verbatim from
fullgame.html) + NHL BLOCK + tail.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).parent / "web"
OPEN = "  /* ===== ENGINE BLOCK."
CLOSE = "  /* ===== END ENGINE BLOCK ===== */"
STAMP = "2026-10-17"   # bumped by hand when 3.0's own sources change (the harness checks it)


def engine_block() -> str:
    src = (ROOT / "fullgame.html").read_text().split("\n")
    start = next(i for i, l in enumerate(src) if l.startswith(OPEN))
    end = next(i for i, l in enumerate(src) if l.startswith(CLOSE))
    return "\n".join(src[start:end + 1]) + "\n"


def once(text: str, old: str, new: str, what: str) -> str:
    n = text.count(old)
    if n != 1:
        sys.exit(f"build stopped: anchor for '{what}' matched {n} times, expected 1:\n  {old[:90]!r}")
    return text.replace(old, new)


def every(text: str, old: str, new: str, what: str, expect: int) -> str:
    n = text.count(old)
    if n != expect:
        sys.exit(f"build stopped: anchor for '{what}' matched {n} times, expected {expect}:\n  {old[:90]!r}")
    return text.replace(old, new)


def head() -> str:
    h = (ROOT / "callsheet2.head.html").read_text()
    frag = (ROOT / "callsheet3.nhl-fields.html").read_text()
    board, fields = frag.split("<!-- ===== FIELDS:")[0], "<!-- ===== FIELDS:" + frag.split("<!-- ===== FIELDS:")[1]
    board = board.split("-->\n", 1)[1]
    fields = fields.split("-->\n", 1)[1]
    nfrag = (ROOT / "callsheet3.nba-fields.html").read_text()
    nboard, nfields = nfrag.split("<!-- ===== FIELDS:")[0], "<!-- ===== FIELDS:" + nfrag.split("<!-- ===== FIELDS:")[1]
    nboard = nboard.split("-->\n", 1)[1]
    nfields = nfields.split("-->\n", 1)[1]
    # "The Super Model": the user's name for the page, 15 Oct 2026, on the eve of the basketball book
    h = once(h, "<title>Call Sheet 2.0</title>", "<title>The Super Model</title>", "title")
    h = once(h, "<h1>Call Sheet <em>2.0</em></h1>", "<h1>The <em>Super</em> Model</h1>", "h1")
    h = once(h, '<button type="button" id="m-mlb" aria-pressed="true">MLB</button>\n      <button type="button" id="m-wnba" aria-pressed="false">WNBA</button>',
             '<button type="button" id="m-mlb" aria-pressed="true">MLB</button>\n      <button type="button" id="m-nhl" aria-pressed="false">NHL</button>\n'
             '      <button type="button" id="m-nba" aria-pressed="false">NBA</button>\n'
             '      <button type="button" id="m-wnba" aria-pressed="false">WNBA</button>', "sport buttons")
    h = once(h, '          <div id="spFields" hidden>', board + nboard + '          <div id="spFields" hidden>', "board sections")
    h = once(h, '      <div id="wnbaFields" class="stack" hidden>', fields + nfields + '      <div id="wnbaFields" class="stack" hidden>', "NHL and NBA fields")
    h = re.sub(r'<span id="build">\d{4}-\d{2}-\d{2}</span>', f'<span id="build">{STAMP}</span>', h, count=1)
    h = once(h, "  @media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }\n</style>",
             "  /* the folded card: what the slate fills, out of the way until it is wanted */\n"
             "  details.fold > summary { cursor: pointer; list-style: none; padding: 12px 15px; font-size: 11.5px; font-weight: 700; text-transform: uppercase;\n"
             "    letter-spacing: .12em; color: var(--ink-2); display: flex; align-items: baseline; justify-content: space-between; gap: 10px; flex-wrap: wrap; }\n"
             "  details.fold > summary::-webkit-details-marker { display: none; }\n"
             "  details.fold > summary::after { content: \"+\"; font: 700 15px var(--mono); color: var(--muted); }\n"
             "  details.fold[open] > summary::after { content: \"\\2212\"; }\n"
             "  details.fold[open] > summary { border-bottom: 1px solid var(--rule); }\n"
             "  details.fold > summary .tag { font-size: 10px; letter-spacing: .09em; color: var(--muted); font-weight: 600; text-transform: none; }\n"
             "  table.form { width: 100%; border-collapse: collapse; margin: 6px 0 12px; font-size: 12px; font-family: var(--mono); }\n"
             "  table.form th, table.form td { text-align: left; padding: 3px 6px; border-bottom: 1px solid var(--rule); white-space: nowrap; }\n"
             "  table.form th { font-size: 10px; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); font-weight: 600; }\n"
             "  table.form td .dim { white-space: normal; max-width: 360px; font: 11px/1.4 var(--sans); color: var(--muted); }\n"
             "  #nbaOutPanel table.form td { white-space: normal; vertical-align: top; }\n"
             "  #nbaOutPanel table.form td:first-child { min-width: 150px; }\n"
             "  #nbaOutPanel table.form td:nth-child(6) { min-width: 120px; }\n"
             "  @media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }\n</style>", "fold css")
    h = once(h, "<p>One matchup, every market the book posts on it — the full-game total, the first five,\n         the moneyline and the run line — priced off",
             "<p>One matchup, every market the book posts on it — in baseball the full-game total, the first five,\n         the moneyline and the run line; in hockey the total, the first period, the moneyline and the puck line;\n         in the NBA the total, the first half, the moneyline and the spread; in the WNBA the total, the moneyline and the spread — priced off", "header copy")
    h = once(h, "Call Sheet #1 is untouched; its total is this sheet's total to the last digit.</p>",
             "Call Sheet #1 is untouched; its MLB total is this sheet's total to the last digit. The hockey book is new on 1 Oct 2026 and every constant in it is a priori; the record decides.</p>", "header tail")
    h = once(h, "<b>Separate from Call Sheet #1.</b> This page keeps its own card in this browser\n            and its own backup format. Nothing here reads or writes #1's log.",
             "<b>Separate from Call Sheet #1 and 2.0.</b> This page keeps its own card in this browser.\n            Load a backup accepts a 2.0 backup too: its rows, baseball and basketball alike, join the card here, and a\n            matchup already on the card is left as it is, so the 2.0 log can be brought over more than once without doubling.", "saving note")
    h = once(h, "the same two rules, MLB and WNBA apart — only on a night with both",
             "the same two rules, one sport at a time — only on a night with more than one", "by-sport head")
    h = once(h, "its own line in the record below, so it can earn one.</p>",
             "its own line in the record below, so it can earn one. The three labels are baseball's; the hockey book "
             "starts with none and earns its own from the record.</p>", "rail note")
    # NHL links on the board card
    h = once(h, '<a href="https://app.outlier.bet/MLB/games" target="_blank" rel="noopener">Outlier · games</a>',
             '<a href="https://app.outlier.bet/MLB/games" target="_blank" rel="noopener">Outlier · MLB</a>\n'
             '            <a href="https://app.outlier.bet/NHL/games" target="_blank" rel="noopener">Outlier · NHL</a>\n'
             '            <a href="https://app.outlier.bet/NBA/games" target="_blank" rel="noopener">Outlier · NBA</a>\n'
             '            <a href="https://sports.betmgm.com/en/sports/hockey-12" target="_blank" rel="noopener">BetMGM · NHL</a>', "board links")
    return h


def tail() -> str:
    t = (ROOT / "callsheet2.tail.js").read_text()
    t = once(t, '  var WNBA_IDS = ["away","home","line","op","up","opened","gdate","apace","hpace","aort","hort","adrt","hdrt",\n'
                '                  "arest","hrest","al5","hl5","hml","aml","sp","sph","spa"];\n'
                '  var ALL = MLB_IDS.concat(WNBA_IDS).filter(function (v, i, a) { return a.indexOf(v) === i; });\n'
                '  var CHECKS = ["dome","playoff"];',
             '  var WNBA_IDS = ["away","home","line","op","up","opened","gdate","apace","hpace","aort","hort","adrt","hdrt",\n'
             '                  "arest","hrest","al5","hl5","hml","aml","sp","sph","spa"];\n'
             '  var NHL_IDS = ["away","home","line","op","up","opened","gdate","agsv","hgsv","agsh","hgsh","asf","hsf",\n'
             '                 "app","hpp","apk","hpk","al10","hl10","h2h","h2hn","arest","hrest","tick","cash",\n'
             '                 "hml","aml","pl","plh","pla","p1line","p1op","p1up","nhlform","nhlctx","ntick","ncash","ap1l10","hp1l10","axgf","axga","hxgf","hxga","xglg",\n'
             '                 "ngoalies","agname","hgname","agstart","hgstart","agok","hgok",\n'
             '                 "odds","sharp","agf","aga","hgf","hga","lgg","angp","hngp","aenc","aens","henc","hens"];\n'
             '  var NBA_IDS = ["away","home","line","op","up","opened","gdate","hml","aml","sp","sph","spa","h1line","h1op","h1up",\n'
             '                 "naort","nhort","nadrt","nhdrt","napace","nhpace","nagp","nhgp","nlrtg","nlpace","narest","nhrest","nbaout","nbaq","nbactx","ncrew","nbarefs","odds","sharp"];\n'
             '  var ALL = MLB_IDS.concat(WNBA_IDS).concat(NHL_IDS).concat(NBA_IDS).filter(function (v, i, a) { return a.indexOf(v) === i; });\n'
             '  var CHECKS = ["dome","playoff","agconf","hgconf","agbk","hgbk"];\n'
             '  function sportOf(s) { return s === "WNBA" ? "WNBA" : s === "NHL" ? "NHL" : s === "NBA" ? "NBA" : "MLB"; }\n'
             '  /* the period market: the first five in baseball, the first period in hockey, the first half in the NBA */\n'
             '  function isPeriod(mk) { return mk.key === "f5" || mk.key === "p1" || mk.key === "h1"; }', "ids")
    t = every(t, 'sp === "WNBA" ? forecastMatchupWnba() : forecastMatchupMlb()',
              'sp === "NHL" ? forecastMatchupNhl() : sp === "NBA" ? forecastMatchupNba() : sp === "WNBA" ? forecastMatchupWnba() : forecastMatchupMlb()', "dispatch (stored)", 1)
    t = every(t, 'sport === "WNBA" ? forecastMatchupWnba() : forecastMatchupMlb()',
              'sport === "NHL" ? forecastMatchupNhl() : sport === "NBA" ? forecastMatchupNba() : sport === "WNBA" ? forecastMatchupWnba() : forecastMatchupMlb()', "dispatch (live)", 1)
    t, n = re.subn(r'([A-Za-z_.]+) === "WNBA" \? "WNBA" : "MLB"', r'sportOf(\1)', t)
    if n != 5:
        sys.exit(f"build stopped: sport normalisation matched {n} times, expected 5")
    t = every(t, 'mk.key === "total" || mk.key === "f5"', 'mk.key === "total" || isPeriod(mk)', "period keys", 3)
    t = once(t, '      if (mk.key === "f5") {\n        if (!isFinite(f5h) || !isFinite(f5a)) return null;',
             '      if (isPeriod(mk)) {\n        if (!isFinite(f5h) || !isFinite(f5a)) return null;', "grade period")
    t = once(t, 'mk.key === "f5" ? parseFloat(c.cf5)', 'isPeriod(mk) ? parseFloat(c.cf5)', "close period")
    t = once(t, 'if (mk.key === "total") tot = mk; if (mk.key === "f5") f5 = mk;', 'if (mk.key === "total") tot = mk; if (isPeriod(mk)) f5 = mk;', "lean period")
    t = once(t, 'function resText(res) { return res === "invalid" ? "F5 > final — recheck" : res; }',
             'function resText(res) { return res === "invalid" ? "period > final — recheck" : res; }', "invalid text")
    t = once(t, "? ' · after five ' + esc(fin.f5a) + '–' + esc(fin.f5h) : '';",
             "? (sport === \"NHL\" ? ' · after one ' : sport === \"NBA\" ? ' · at the half ' : ' · after five ') + esc(fin.f5a) + '–' + esc(fin.f5h) : '';", "after five")
    t = once(t, "(r.sport === \"MLB\" ? '<input class=\"grade close\" data-id=\"' + r.id + '\" data-k=\"cf5\" value=\"' + esc(cl.cf5 || \"\") + '\" placeholder=\"F5\"",
             "(r.sport !== \"WNBA\" ? '<input class=\"grade close\" data-id=\"' + r.id + '\" data-k=\"cf5\" value=\"' + esc(cl.cf5 || \"\") + '\" placeholder=\"' + (r.sport === \"NHL\" ? \"P1\" : r.sport === \"NBA\" ? \"1H\" : \"F5\") + '\"", "close box")
    t = once(t, "      var f5 = r.sport === \"MLB\"\n        ? '<span class=\"finals\"><span class=\"l\">F5</span>",
             "      var f5 = r.sport !== \"WNBA\"\n        ? '<span class=\"finals\"><span class=\"l\">' + (r.sport === \"NHL\" ? \"P1\" : r.sport === \"NBA\" ? \"1H\" : \"F5\") + '</span>", "period finals")
    t = once(t, 'WNBA: [["total","Full-game total"],["ml","Moneyline"],["spread","Spread"]] };',
             'NHL: [["total","Full-game total"],["p1","First period"],["ml","Moneyline"],["pl","Puck line"]],\n'
             '                 NBA: [["total","Full-game total"],["h1","First half"],["ml","Moneyline"],["spread","Spread"]],\n'
             '                 WNBA: [["total","Full-game total"],["ml","Moneyline"],["spread","Spread"]] };', "calib keys")
    t = every(t, '["MLB", "WNBA"]', '["MLB", "NHL", "NBA", "WNBA"]', "sport loops", 4)
    t = once(t, 'if (!bySport.MLB.any && !bySport.WNBA.any)', 'if (!bySport.MLB.any && !bySport.NHL.any && !bySport.NBA.any && !bySport.WNBA.any)', "any graded")
    t = once(t, '                       WNBA: "Nothing graded yet. Type the final on the card and the three markets grade themselves." };',
             '                       NHL: "Nothing graded yet. Type the final and the first-period score on the card and the four markets grade themselves; a shootout win grades as a one-goal margin.",\n'
             '                       NBA: "Nothing graded yet. Type the final and the half-time score on the card and the four markets grade themselves.",\n'
             '                       WNBA: "Nothing graded yet. Type the final on the card and the three markets grade themselves. The WNBA log on 2.0 comes over with Load a backup." };', "empty notes")
    t = once(t, 'var unit = sp === "WNBA" ? "pts" : "runs";', 'var unit = (sp === "WNBA" || sp === "NBA") ? "pts" : sp === "NHL" ? "goals" : "runs";', "unit")
    t = once(t, ": 'With seven games in the season book",
             ": sp === \"NHL\" ? 'The puck line and the moneyline are shown, not picked, from the first game: every constant in the hockey book is a priori, and the record decides which earns a weight. The total and the first period are the pickable markets.' : "
             "sp === \"NBA\" ? 'The spread and the moneyline are shown, not picked: measured priced against everything in the box score over two seasons of closes, with one exception, the short dog (a dog the book makes 40% or better, +5.6 points on 626 games, both seasons), which lifts the dog and makes its moneyline pickable on its own record line. The total and the first half are the pickable markets; the ratings fade and the stage deltas are tagged, and the record decides what they earn.' : 'With seven games in the season book", "calib verdict")
    # units and decimals: the NBA is a points sport like the WNBA (one decimal on a total, none on a forecast line)
    t = every(t, 'sp === "WNBA" ? "points"', '(sp === "WNBA" || sp === "NBA") ? "points"', "points unit", 3)
    t = every(t, 'sp === "WNBA" ? 1 : 2', '(sp === "WNBA" || sp === "NBA") ? 1 : 2', "decimals (sp)", 2)
    t = every(t, 'sp === "WNBA" ? 0 : 1', '(sp === "WNBA" || sp === "NBA") ? 0 : 1', "decimals (forecast line)", 1)
    t = every(t, 'sport === "WNBA" ? 1 : 2', '(sport === "WNBA" || sport === "NBA") ? 1 : 2', "decimals (split)", 2)
    t = once(t, 'sp === "NHL" ? r.inputs.p1line : r.inputs.f5line', 'sp === "NHL" ? r.inputs.p1line : sp === "NBA" ? r.inputs.h1line : r.inputs.f5line', "forecast period line")
    t = once(t, '(sp === "NHL" ? "first period " : "first five ")', '(sp === "NHL" ? "first period " : sp === "NBA" ? "first half " : "first five ")', "forecast line period")
    t = once(t, "(sp === \"NHL\" ? 'First period' : 'First five')", "(sp === \"NHL\" ? 'First period' : sp === \"NBA\" ? 'First half' : 'First five')", "record period")
    t = once(t, 'NHL: ["total", "p1", "ml"] };', 'NHL: ["total", "p1", "ml"], NBA: ["total", "h1", "ml"] };', "pickable")
    t = once(t, "sp === \"MLB\" ? 'baseball (the pitchers and the pens score the total, not the margin)' : 'this game'",
             "sp === \"MLB\" ? 'baseball (the pitchers and the pens score the total, not the margin)' : sp === \"NBA\" ? 'the NBA (measured 15 Oct 2026 on two seasons of closes: the pace and efficiency margin projection read 0.00 against the spread, and rest, travel, time zones and announced absences sat inside the number)' : 'this game'", "pick why sides")
    t = once(t, 'if (sp === "NHL") return "Derived from the book',
             'if (sp === "NBA") return "The spread and the moneyline are the book\'s own number through a normal margin at 12.5 points: measured priced against everything in the box score over two seasons of closes (15 Oct 2026). Listed and graded, never a straight bet or a parlay leg, until the record says otherwise.";\n'
             '    if (sp === "NHL") return "Derived from the book', "not picked why")
    t = once(t, 'if (!Object.keys(b).length && sp !== "NHL") return "";', 'if (sp === "NBA") return "";   // the +1.5 columns are hockey\'s; the NBA favourite reads on the spread\n    if (!Object.keys(b).length && sp !== "NHL") return "";', "favourite table")
    t = once(t, 'k.sport === "WNBA" ? "WNBA" : (k.sport === "NHL" ? "NHL" : "MLB")', 'sportOf(k.sport)', "slate sport key")
    t = once(t, '    $("m-wnba").setAttribute("aria-pressed", s === "WNBA" ? "true" : "false");\n'
                '    $("mlbFields").hidden = s !== "MLB"; $("wnbaFields").hidden = s !== "WNBA";\n'
                '    $("rlFields").hidden = s !== "MLB"; $("f5Fields").hidden = s !== "MLB"; $("spFields").hidden = s !== "WNBA";\n'
                '    $("eyebrow").textContent = s === "MLB" ? "MLB · every market on the game" : "WNBA · every market on the game";\n'
                '    $("lineLabel").textContent = s === "WNBA" ? "Total (points)" : "Total (runs)";\n'
                '    $("line").placeholder = s === "WNBA" ? "165.5" : "8.5";',
             '    $("m-wnba").setAttribute("aria-pressed", s === "WNBA" ? "true" : "false");\n'
             '    $("m-nhl").setAttribute("aria-pressed", s === "NHL" ? "true" : "false");\n'
             '    $("m-nba").setAttribute("aria-pressed", s === "NBA" ? "true" : "false");\n'
             '    $("mlbFields").hidden = s !== "MLB"; $("wnbaFields").hidden = s !== "WNBA"; $("nhlFields").hidden = s !== "NHL"; $("nbaFields").hidden = s !== "NBA";\n'
             '    $("rlFields").hidden = s !== "MLB"; $("f5Fields").hidden = s !== "MLB"; $("spFields").hidden = s !== "WNBA" && s !== "NBA";\n'
             '    $("plFields").hidden = s !== "NHL"; $("p1Fields").hidden = s !== "NHL"; $("h1Fields").hidden = s !== "NBA";\n'
             '    $("eyebrow").textContent = s + " · every market on the game";\n'
             '    $("lineLabel").textContent = (s === "WNBA" || s === "NBA") ? "Total (points)" : s === "NHL" ? "Total (goals)" : "Total (runs)";\n'
             '    $("line").placeholder = s === "WNBA" ? "165.5" : s === "NBA" ? "228.5" : s === "NHL" ? "6" : "8.5";\n'
             '    $("opened").placeholder = s === "WNBA" ? "165.5" : s === "NBA" ? "228.5" : s === "NHL" ? "6" : "8.5";', "setSport")
    t = once(t, '["paste", "pasteFill", "add", "example", "m-mlb", "m-wnba"]', '["paste", "pasteFill", "add", "example", "m-mlb", "m-nhl", "m-nba", "m-wnba"]', "lock list")
    t = once(t, '  $("m-wnba").addEventListener("click", function () { setSport("WNBA"); });',
             '  $("m-wnba").addEventListener("click", function () { setSport("WNBA"); });\n'
             '  $("m-nhl").addEventListener("click", function () { setSport("NHL"); });\n'
             '  $("m-nba").addEventListener("click", function () { setSport("NBA"); });', "nhl and nba buttons")
    t = once(t, '    } else {\n      restore({ away: "Sun", home: "Mystics"',
             '    } else if (sport === "NHL") {\n'
             '      restore({ away: "Rangers", home: "Bruins", line: "6", op: "-110", up: "-110", gdate: $("gdate").value,\n'
             '        aml: "130", hml: "-150", pl: "-1.5", plh: "180", pla: "-220", p1line: "1.5", p1op: "-120", p1up: "100",\n'
             '        agsv: "0.912", hgsv: "0.921", agsh: "1400", hgsh: "1900", asf: "31.2", hsf: "33.4",\n'
             '        app: "22.1", hpp: "24.8", apk: "80.2", hpk: "78.1", al10: "5.9", hl10: "6.4", h2h: "6.3", h2hn: "3", arest: "0", hrest: "2" });\n'
             '    } else if (sport === "NBA") {\n' + nba_example_js() +
             '    } else {\n      restore({ away: "Sun", home: "Mystics"', "example")
    t = every(t, '"callsheet2.card.v1"', '"callsheet3.card.v1"', "card key", 1)
    t = every(t, '"callsheet2.draft.v1"', '"callsheet3.draft.v1"', "draft key", 1)
    t = every(t, '"callsheet2.slate.v1"', '"callsheet3.slate.v1"', "slate key", 1)
    t = once(t, 'format: "callsheet2.backup"', 'format: "callsheet3.backup"', "backup format")
    t = once(t, 'name = "callsheet2-" + todayISO() + ".json"', 'name = "the-super-model-" + todayISO() + ".json"', "backup name")   # 17 Oct 2026, the user: "can it say The Super Model"
    t = once(t, 'var out = ["Call Sheet 2.0 — " + gameDate(dateISO)];', 'var out = ["The Super Model — " + gameDate(dateISO)];', "board text header")
    t = once(t, '        if (d.format !== "callsheet2.backup" || !Array.isArray(d.card)) throw new Error("not a Call Sheet 2.0 backup");\n'
                '        card = d.card; save(); renderCard(); renderBoard(); renderCalib();\n'
                '        if (d.draft && d.draft.inputs) {',
             '        if ((d.format !== "callsheet3.backup" && d.format !== "callsheet2.backup") || !Array.isArray(d.card)) throw new Error("not a Super Model or Call Sheet backup");\n'
             '        /* A 3.0 backup is a restore: it replaces the card. A 2.0 backup is a\n'
             '           move: its rows join the card, baseball and basketball alike, and a\n'
             '           matchup already here (same sport, teams and date) is left as it\n'
             '           is, so the 2.0 log can be brought over more than once without\n'
             '           doubling. Incoming rows take fresh ids; 2.0 and 3.0 number their\n'
             '           rows apart. */\n'
             '        var moved = d.format === "callsheet2.backup", added = 0, kept = 0;\n'
             '        if (moved) {\n'
             '          var have = {}; card.forEach(function (r) { have[r.sport + "|" + r.matchup + "|" + (r.gdate || "")] = true; });\n'
             '          var id = nextId();\n'
             '          d.card.forEach(function (r) {\n'
             '            var k = r.sport + "|" + r.matchup + "|" + (r.gdate || "");\n'
             '            if (have[k]) { kept++; return; }\n'
             '            have[k] = true; r.id = id++; card.push(r); added++;\n'
             '          });\n'
             '        } else card = d.card;\n'
             '        save(); renderCard(); renderBoard(); renderCalib();\n'
             '        if (moved) say("Brought <b>" + added + "</b> matchup" + (added === 1 ? "" : "s") + " over from the 2.0 backup " + esc(f.name) +\n'
             '          (kept ? "; " + kept + " already here " + (kept === 1 ? "was" : "were") + " left as " + (kept === 1 ? "it is" : "they are") : "") + ".");\n'
             '        if (!moved && d.draft && d.draft.inputs) {', "restore")
    t = once(t, 'say("Loaded <b>" + card.length + "</b> matchups from " + esc(f.name) + ".");',
             'if (!moved) say("Loaded <b>" + card.length + "</b> matchups from " + esc(f.name) + ".");', "restore message")
    t = once(t, '                      "line","op","up","opened","hml","aml","rl","rlh","rla","f5line","f5op","f5up","odds","sharp"];',
             '                      "line","op","up","opened","hml","aml","rl","rlh","rla","f5line","f5op","f5up","odds","sharp",\n'
             '                      "agsv","hgsv","agsh","hgsh","asf","hsf","app","hpp","apk","hpk","nhlform","nhlctx","ap1l10","hp1l10","axgf","axga","hxgf","hxga","xglg",\n'
             '                      "ngoalies","agname","hgname",\n'
             '                      "pl","plh","pla","p1line","p1op","p1up",\n'
             '                      "agf","aga","hgf","hga","lgg","angp","hngp","aenc","aens","henc","hens",\n'
             '                      "sp","sph","spa","h1line","h1op","h1up","naort","nhort","nadrt","nhdrt","napace","nhpace","nagp","nhgp","nlrtg","nlpace","narest","nhrest","nbaout","nbactx","ncrew","nbarefs"];', "slate fields")
    # the slate's backup-in-net flags are booleans, carried like the roof: into a
    # row's inputs when the card already has the game, into the form otherwise
    t = once(t, '          if (g.inputs.dome === true && !row.inputs.dome) { row.inputs.dome = true; changed = true; }',
             '          if (g.inputs.dome === true && !row.inputs.dome) { row.inputs.dome = true; changed = true; }\n'
             '          ["agbk", "hgbk"].forEach(function (k) { if (g.inputs[k] === true && !row.inputs[k]) { row.inputs[k] = true; changed = true; } });', "slate backup flags into rows")
    t = once(t, '    if (g.inputs && g.inputs.dome === true) v.dome = true;',
             '    if (g.inputs && g.inputs.dome === true) v.dome = true;\n'
             '    ["agbk", "hgbk"].forEach(function (k) { if (g.inputs && g.inputs[k] === true) v[k] = true; });', "slate backup flags into the form")
    t = once(t, '      if (!blank(i.aera) && !blank(i.hera)) meta.push("ERA " + esc(i.aera) + "/" + esc(i.hera));',
             '      if (!blank(i.aera) && !blank(i.hera)) meta.push("ERA " + esc(i.aera) + "/" + esc(i.hera));\n'
             '      if (!blank(i.agsv) && !blank(i.hgsv)) meta.push("SV " + esc(i.agsv) + "/" + esc(i.hgsv));', "slate meta")
    return t


# The NBA example: a game-day row as the slate and the odds run would leave it
# three weeks into the season. 76ers @ Knicks on opening night 2026-27 with
# DraftKings' real numbers off ESPN's scoreboard (15 Oct 2026, with the
# openers), ratings at fifteen and sixteen games (the fade live, the ratings'
# margin five points off the spread for the early-season side watch), the
# Knicks on a back to back, the who-is-out list in the slate's shape (the page's
# comment and return date, a traded man on last season's line) and the context
# lines with their tags.
NBA_EXAMPLE_OUT = {
    "away": [
        {"id": "3059318", "n": "Joel Embiid", "st": "Out", "note": "Knee", "c": "Embiid (knee) has been ruled out for Tuesday's game against the Knicks.", "ret": "2026-11-18", "pos": "C",
         "mpg": 31.5, "ppg": 26.9, "pm": 4.1, "src": "this season", "g": 12},
        {"id": "4351851", "n": "Anfernee Simons", "st": "Questionable", "note": "Hamstring; with Bulls last season", "c": "Simons (hamstring) is listed as questionable for Tuesday's game in New York.", "ret": "2026-11-10", "pos": "G",
         "mpg": 24.9, "ppg": 14.3, "pm": 1.8, "src": "last season", "g": 55},
        {"id": "4870562", "n": "Dominick Barlow", "st": "Day-To-Day", "note": "Back", "c": "Barlow (back) was unable to practice Monday.", "ret": "2026-11-12", "pos": "F",
         "mpg": 11.8, "ppg": 4.2, "pm": -0.6, "src": "this season", "g": 9}],
    "home": [
        {"id": "4066648", "n": "Mitchell Robinson", "st": "Out", "note": "Ankle", "c": "Robinson (ankle) will miss Tuesday's game against the 76ers.", "ret": "2026-11-20", "pos": "C",
         "mpg": 22.4, "ppg": 5.6, "pm": 3.1, "src": "this season", "g": 10},
        {"id": "4065804", "n": "Josh Hart", "st": "Questionable", "note": "Knee", "c": "Hart (knee) is questionable for Tuesday's game, Ian Begley of SNY reports.", "ret": "2026-11-10", "pos": "G",
         "mpg": 33.1, "ppg": 13.4, "pm": 5.2, "src": "this season", "g": 16}]}
NBA_EXAMPLE_CTX = [
    {"side": "home", "k": "ratings_faded", "s": "faded", "t": "Knicks score 118.0 per 100 possessions, 3rd best in the league (16 games).", "tag": "faded: the market over-moves with early-season ratings, so the projection's lean goes on the line at −0.25 a point until fifty games, tagged"},
    {"side": "home", "k": "ratings_faded", "s": "faded", "t": "Knicks allow 109.0 per 100 possessions, 4th best in the league (16 games).", "tag": "faded: the market over-moves with early-season ratings, so the projection's lean goes on the line at −0.25 a point until fifty games, tagged"},
    {"side": "away", "k": "ratings_faded", "s": "faded", "t": "76ers allow 115.0 per 100 possessions, 6th worst in the league (15 games).", "tag": "faded: the market over-moves with early-season ratings, so the projection's lean goes on the line at −0.25 a point until fifty games, tagged"},
    {"side": "home", "k": "pace", "s": "shown", "t": "Knicks play at 98.0 possessions a game, 5th slowest in the league.", "tag": "shown, not scored: pace alone measured null against the close; it feeds the projection"},
    {"side": "home", "k": "record", "s": "shown", "t": "Knicks are 7-1 at home.", "tag": "shown, not scored: the spread is priced against the box score"},
    {"side": "game", "k": "move", "s": "shown", "t": "DraftKings: the total opened 229.5 and sits 231.5, up 2; Knicks opened -3.5 and sit -5.5.", "tag": "shown, not scored: the current line is the anchor and the move is already inside it"},
    {"side": "home", "k": "rest", "s": "label", "t": "Knicks on a back to back.", "tag": "a label: rest measured inside the number against two seasons of closes"},
    {"side": "away", "k": "out", "s": "shown", "t": "76ers without Joel Embiid: 32 minutes a game of regulars.", "tag": "shown, not scored: announced absences are in the close; the card measures the late ones"},
    {"side": "home", "k": "out", "s": "shown", "t": "Knicks without Mitchell Robinson: 22 minutes a game of regulars.", "tag": "shown, not scored: announced absences are in the close; the card measures the late ones"}]
# the referee table the slate writes from the ledger: each official's games, free throws and points a game, and the league's
NBA_EXAMPLE_REFS = {"lg": [2462, 44.0, 228.8], "r": {"Scott Foster": [118, 46.2, 229.1, 66, 41, 4, 2], "Tony Brothers": [95, 43.1, 226.0, 56, 54, 3, 3], "Marc Davis": [102, 44.8, 230.3, 71, 51, 0, 0], "Zach Zarba": [110, 42.9, 227.4, 58, 60, 2, 5]}}


def nba_example_js() -> str:
    return ('      restore({ away: "76ers", home: "Knicks", line: "231.5", op: "-110", up: "-110", opened: "229.5", gdate: $("gdate").value,\n'
            '        aml: "164", hml: "-198", sp: "-5.5", sph: "-108", spa: "-112", h1line: "115.5", h1op: "-110", h1up: "-110",\n'
            '        naort: "113.5", nadrt: "115.0", nhort: "118.0", nhdrt: "109.0", napace: "99.5", nhpace: "98.0", nagp: "15", nhgp: "16", nlrtg: "113.0", nlpace: "100.5", narest: "1", nhrest: "0",\n'
            '        nbaout: ' + json.dumps(json.dumps(NBA_EXAMPLE_OUT, separators=(",", ":"))) + ',\n'
            '        nbactx: ' + json.dumps(json.dumps(NBA_EXAMPLE_CTX, separators=(",", ":"))) + ',\n'
            '        ncrew: "Scott Foster, Tony Brothers, Marc Davis", nbarefs: ' + json.dumps(json.dumps(NBA_EXAMPLE_REFS, separators=(",", ":"))) + ' });\n')


def build() -> str:
    return head() + engine_block() + (ROOT / "nhl.engine.js").read_text() + (ROOT / "nba.engine.js").read_text() + tail()


if __name__ == "__main__":
    out = ROOT / "callsheet3.html"
    out.write_text(build())
    print(f"wrote {out} ({out.stat().st_size:,} bytes)")
