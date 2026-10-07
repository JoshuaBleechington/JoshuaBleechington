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
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).parent / "web"
OPEN = "  /* ===== ENGINE BLOCK."
CLOSE = "  /* ===== END ENGINE BLOCK ===== */"
STAMP = "2026-10-07"   # bumped by hand when 3.0's own sources change (the harness checks it)


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
    h = once(h, "<title>Call Sheet 2.0</title>", "<title>Call Sheet 3.0</title>", "title")
    h = once(h, "<h1>Call Sheet <em>2.0</em></h1>", "<h1>Call Sheet <em>3.0</em></h1>", "h1")
    h = once(h, '<button type="button" id="m-mlb" aria-pressed="true">MLB</button>\n      <button type="button" id="m-wnba" aria-pressed="false">WNBA</button>',
             '<button type="button" id="m-mlb" aria-pressed="true">MLB</button>\n      <button type="button" id="m-nhl" aria-pressed="false">NHL</button>\n'
             '      <button type="button" id="m-wnba" aria-pressed="false">WNBA</button>', "sport buttons")
    h = once(h, '          <div id="spFields" hidden>', board + '          <div id="spFields" hidden>', "board sections")
    h = once(h, '      <div id="wnbaFields" class="stack" hidden>', fields + '      <div id="wnbaFields" class="stack" hidden>', "NHL fields")
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
             "  @media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }\n</style>", "fold css")
    h = once(h, "<p>One matchup, every market the book posts on it — the full-game total, the first five,\n         the moneyline and the run line — priced off",
             "<p>One matchup, every market the book posts on it — in baseball the full-game total, the first five,\n         the moneyline and the run line; in hockey the total, the first period, the moneyline and the puck line;\n         in basketball the total, the moneyline and the spread — priced off", "header copy")
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
             '                 "hml","aml","pl","plh","pla","p1line","p1op","p1up","nhlform","ntick","ncash","ap1l10","hp1l10","axgf","axga","hxgf","hxga","xglg"];\n'
             '  var ALL = MLB_IDS.concat(WNBA_IDS).concat(NHL_IDS).filter(function (v, i, a) { return a.indexOf(v) === i; });\n'
             '  var CHECKS = ["dome","playoff","agconf","hgconf","agbk","hgbk"];\n'
             '  function sportOf(s) { return s === "WNBA" ? "WNBA" : s === "NHL" ? "NHL" : "MLB"; }\n'
             '  /* the period market: the first five in baseball, the first period in hockey */\n'
             '  function isPeriod(mk) { return mk.key === "f5" || mk.key === "p1"; }', "ids")
    t = every(t, 'sp === "WNBA" ? forecastMatchupWnba() : forecastMatchupMlb()',
              'sp === "NHL" ? forecastMatchupNhl() : sp === "WNBA" ? forecastMatchupWnba() : forecastMatchupMlb()', "dispatch (stored)", 1)
    t = every(t, 'sport === "WNBA" ? forecastMatchupWnba() : forecastMatchupMlb()',
              'sport === "NHL" ? forecastMatchupNhl() : sport === "WNBA" ? forecastMatchupWnba() : forecastMatchupMlb()', "dispatch (live)", 1)
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
             "? (sport === \"NHL\" ? ' · after one ' : ' · after five ') + esc(fin.f5a) + '–' + esc(fin.f5h) : '';", "after five")
    t = once(t, "(r.sport === \"MLB\" ? '<input class=\"grade close\" data-id=\"' + r.id + '\" data-k=\"cf5\" value=\"' + esc(cl.cf5 || \"\") + '\" placeholder=\"F5\"",
             "(r.sport !== \"WNBA\" ? '<input class=\"grade close\" data-id=\"' + r.id + '\" data-k=\"cf5\" value=\"' + esc(cl.cf5 || \"\") + '\" placeholder=\"' + (r.sport === \"NHL\" ? \"P1\" : \"F5\") + '\"", "close box")
    t = once(t, "      var f5 = r.sport === \"MLB\"\n        ? '<span class=\"finals\"><span class=\"l\">F5</span>",
             "      var f5 = r.sport !== \"WNBA\"\n        ? '<span class=\"finals\"><span class=\"l\">' + (r.sport === \"NHL\" ? \"P1\" : \"F5\") + '</span>", "period finals")
    t = once(t, 'WNBA: [["total","Full-game total"],["ml","Moneyline"],["spread","Spread"]] };',
             'NHL: [["total","Full-game total"],["p1","First period"],["ml","Moneyline"],["pl","Puck line"]],\n'
             '                 WNBA: [["total","Full-game total"],["ml","Moneyline"],["spread","Spread"]] };', "calib keys")
    t = every(t, '["MLB", "WNBA"]', '["MLB", "NHL", "WNBA"]', "sport loops", 4)
    t = once(t, 'if (!bySport.MLB.any && !bySport.WNBA.any)', 'if (!bySport.MLB.any && !bySport.NHL.any && !bySport.WNBA.any)', "any graded")
    t = once(t, '                       WNBA: "Nothing graded yet. Type the final on the card and the three markets grade themselves." };',
             '                       NHL: "Nothing graded yet. Type the final and the first-period score on the card and the four markets grade themselves; a shootout win grades as a one-goal margin.",\n'
             '                       WNBA: "Nothing graded yet. Type the final on the card and the three markets grade themselves. The WNBA log on 2.0 comes over with Load a backup." };', "empty notes")
    t = once(t, 'var unit = sp === "WNBA" ? "pts" : "runs";', 'var unit = sp === "WNBA" ? "pts" : sp === "NHL" ? "goals" : "runs";', "unit")
    t = once(t, ": 'With seven games in the season book",
             ": sp === \"NHL\" ? 'The puck line and the moneyline are shown, not picked, from the first game: every constant in the hockey book is a priori, and the record decides which earns a weight. The total and the first period are the pickable markets.' : 'With seven games in the season book", "calib verdict")
    t = once(t, '    $("m-wnba").setAttribute("aria-pressed", s === "WNBA" ? "true" : "false");\n'
                '    $("mlbFields").hidden = s !== "MLB"; $("wnbaFields").hidden = s !== "WNBA";\n'
                '    $("rlFields").hidden = s !== "MLB"; $("f5Fields").hidden = s !== "MLB"; $("spFields").hidden = s !== "WNBA";\n'
                '    $("eyebrow").textContent = s === "MLB" ? "MLB · every market on the game" : "WNBA · every market on the game";\n'
                '    $("lineLabel").textContent = s === "WNBA" ? "Total (points)" : "Total (runs)";\n'
                '    $("line").placeholder = s === "WNBA" ? "165.5" : "8.5";',
             '    $("m-wnba").setAttribute("aria-pressed", s === "WNBA" ? "true" : "false");\n'
             '    $("m-nhl").setAttribute("aria-pressed", s === "NHL" ? "true" : "false");\n'
             '    $("mlbFields").hidden = s !== "MLB"; $("wnbaFields").hidden = s !== "WNBA"; $("nhlFields").hidden = s !== "NHL";\n'
             '    $("rlFields").hidden = s !== "MLB"; $("f5Fields").hidden = s !== "MLB"; $("spFields").hidden = s !== "WNBA";\n'
             '    $("plFields").hidden = s !== "NHL"; $("p1Fields").hidden = s !== "NHL";\n'
             '    $("eyebrow").textContent = s + " · every market on the game";\n'
             '    $("lineLabel").textContent = s === "WNBA" ? "Total (points)" : s === "NHL" ? "Total (goals)" : "Total (runs)";\n'
             '    $("line").placeholder = s === "WNBA" ? "165.5" : s === "NHL" ? "6" : "8.5";\n'
             '    $("opened").placeholder = s === "WNBA" ? "165.5" : s === "NHL" ? "6" : "8.5";', "setSport")
    t = once(t, '["paste", "pasteFill", "add", "example", "m-mlb", "m-wnba"]', '["paste", "pasteFill", "add", "example", "m-mlb", "m-nhl", "m-wnba"]', "lock list")
    t = once(t, '  $("m-wnba").addEventListener("click", function () { setSport("WNBA"); });',
             '  $("m-wnba").addEventListener("click", function () { setSport("WNBA"); });\n'
             '  $("m-nhl").addEventListener("click", function () { setSport("NHL"); });', "nhl button")
    t = once(t, '    } else {\n      restore({ away: "Sun", home: "Mystics"',
             '    } else if (sport === "NHL") {\n'
             '      restore({ away: "Rangers", home: "Bruins", line: "6", op: "-110", up: "-110", gdate: $("gdate").value,\n'
             '        aml: "130", hml: "-150", pl: "-1.5", plh: "180", pla: "-220", p1line: "1.5", p1op: "-120", p1up: "100",\n'
             '        agsv: "0.912", hgsv: "0.921", agsh: "1400", hgsh: "1900", asf: "31.2", hsf: "33.4",\n'
             '        app: "22.1", hpp: "24.8", apk: "80.2", hpk: "78.1", al10: "5.9", hl10: "6.4", h2h: "6.3", h2hn: "3", arest: "0", hrest: "2" });\n'
             '    } else {\n      restore({ away: "Sun", home: "Mystics"', "example")
    t = every(t, '"callsheet2.card.v1"', '"callsheet3.card.v1"', "card key", 1)
    t = every(t, '"callsheet2.draft.v1"', '"callsheet3.draft.v1"', "draft key", 1)
    t = every(t, '"callsheet2.slate.v1"', '"callsheet3.slate.v1"', "slate key", 1)
    t = once(t, 'format: "callsheet2.backup"', 'format: "callsheet3.backup"', "backup format")
    t = once(t, 'name = "callsheet2-" + todayISO() + ".json"', 'name = "callsheet3-" + todayISO() + ".json"', "backup name")
    t = once(t, '        if (d.format !== "callsheet2.backup" || !Array.isArray(d.card)) throw new Error("not a Call Sheet 2.0 backup");\n'
                '        card = d.card; save(); renderCard(); renderBoard(); renderCalib();\n'
                '        if (d.draft && d.draft.inputs) {',
             '        if ((d.format !== "callsheet3.backup" && d.format !== "callsheet2.backup") || !Array.isArray(d.card)) throw new Error("not a Call Sheet 3.0 or 2.0 backup");\n'
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
    t = once(t, '  var SLATE_FIELDS = ["aera","hera","aip","hip","al5era","hl5era","al5ip","hl5ip","arpg","hrpg","abp","hbp","al10","hl10","h2h","h2hn","pf","mph","dir","temp","tick","cash",\n'
                '                      "apace","hpace","aort","hort","adrt","hdrt","arest","hrest","al5","hl5"];',
             '  var SLATE_FIELDS = ["aera","hera","aip","hip","al5era","hl5era","al5ip","hl5ip","arpg","hrpg","abp","hbp","al10","hl10","h2h","h2hn","pf","mph","dir","temp","tick","cash",\n'
             '                      "apace","hpace","aort","hort","adrt","hdrt","arest","hrest","al5","hl5",\n'
             '                      "agsv","hgsv","agsh","hgsh","asf","hsf","app","hpp","apk","hpk","nhlform","ap1l10","hp1l10","axgf","axga","hxgf","hxga","xglg"];', "slate fields")
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


def build() -> str:
    return head() + engine_block() + (ROOT / "nhl.engine.js").read_text() + tail()


if __name__ == "__main__":
    out = ROOT / "callsheet3.html"
    out.write_text(build())
    print(f"wrote {out} ({out.stat().st_size:,} bytes)")
