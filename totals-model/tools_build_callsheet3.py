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
STAMP = "2026-10-28"   # bumped by hand when 3.0's own sources change (the harness checks it)


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
    pfrag = (ROOT / "callsheet3.props.html").read_text().split("-->\n", 1)[1]   # the Props tab (19 Oct 2026)
    # "The Super Model": the user's name for the page, 15 Oct 2026, on the eve of the basketball book
    h = once(h, "<title>Call Sheet 2.0</title>", "<title>The Super Model</title>", "title")
    h = once(h, "<h1>Call Sheet <em>2.0</em></h1>", "<h1>The <em>Super</em> Model</h1>", "h1")
    # the sport buttons (22 Oct 2026, the user: "Player props 1st, NBA 2nd and then the rest"): the props tab leads, then the
    # NBA card, then the others in their old order; the MLB button still starts pressed, since MLB is the page's default sport
    h = once(h, '<button type="button" id="m-mlb" aria-pressed="true">MLB</button>\n      <button type="button" id="m-wnba" aria-pressed="false">WNBA</button>',
             '<button type="button" id="m-props" aria-pressed="false">NBA PROPS</button>\n'
             '      <button type="button" id="m-nba" aria-pressed="false">NBA</button>\n'
             '      <button type="button" id="m-mlb" aria-pressed="true">MLB</button>\n      <button type="button" id="m-nhl" aria-pressed="false">NHL</button>\n'
             '      <button type="button" id="m-wnba" aria-pressed="false">WNBA</button>', "sport buttons")
    h = once(h, '          <div id="spFields" hidden>', board + nboard + '          <div id="spFields" hidden>', "board sections")
    # the Props tab (19 Oct 2026): a fifth button, and the section that stands in for the matchup columns
    h = once(h, '  <section class="card" style="margin-top:20px">\n    <h2>Day board', pfrag + '  <section class="card" style="margin-top:20px">\n    <h2>Day board', "props section")
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
             "  /* the starting five beside the who-is-out list (20 Oct 2026) */\n"
             "  #nbaLineupPanel .fives { margin: 6px 0 2px; } #nbaLineupPanel .five p { margin: 4px 0; }\n"
             "  #nbaLineupPanel table.form { margin: 2px 0 6px; } #nbaLineupPanel table.form td.pos { color: var(--muted); font-size: 10.5px; letter-spacing: .08em; width: 34px; }\n"
             "  #nbaLineupPanel .lbadge { display: inline-block; margin-left: 6px; padding: 1px 6px; border-radius: 3px; font: 700 9.5px/1.6 var(--sans); letter-spacing: .06em; text-transform: uppercase; vertical-align: 1px; }\n"
             "  #nbaLineupPanel .lbadge.conf { color: var(--go); background: var(--go-wash); } #nbaLineupPanel .lbadge.exp { color: var(--edge); background: var(--edge-wash); }\n"
             "  #nbaLineupPanel .lbadge.none { color: var(--muted); background: var(--surface-2); }\n"
             "  .pdlg .pd-fives .lbadge { display: inline-block; margin-left: 6px; padding: 1px 6px; border-radius: 3px; font: 700 9.5px/1.6 var(--sans); letter-spacing: .06em; text-transform: uppercase; vertical-align: 1px; }\n"
             "  .pdlg .pd-fives .lbadge.conf { color: var(--go); background: var(--go-wash); } .pdlg .pd-fives .lbadge.exp { color: var(--edge); background: var(--edge-wash); } .pdlg .pd-fives .lbadge.none { color: var(--muted); background: var(--surface-2); }\n"
             "  @media (max-width: 640px) { #nbaLineupPanel .fives { grid-template-columns: 1fr; } }\n"
             "  /* the referees (22 Oct 2026): the watch on the record as two tables, the crew line on the matchup highlighted */\n"
             "  #calibBox table.refs { margin: 6px 0 10px; } #calibBox table.refs td, #calibBox table.refs th { white-space: nowrap; }\n"
             "  #calibBox table.refs td.over { color: var(--over); font-weight: 700; } #calibBox table.refs td.under { color: var(--under); font-weight: 700; }\n"
             "  #calibBox table.refs td.pos { color: var(--go); font-weight: 700; } #calibBox table.refs td.neg { color: var(--bad); font-weight: 700; }\n"
             "  #calibBox table.refs .chip.push { background: var(--surface-2); color: var(--ink-2); }\n"
             "  .crewblock { display: block; padding: 10px 12px 10px 14px; margin: 2px 0 10px; border-radius: 8px; background: var(--surface-2); box-shadow: inset 3px 0 0 var(--muted); font-size: 12.5px; line-height: 1.5; color: var(--ink); }\n"
             "  .crewblock.lean-over { background: rgba(184, 84, 31, 0.10); box-shadow: inset 3px 0 0 var(--over); }\n"
             "  .crewblock.lean-under { background: rgba(43, 106, 143, 0.10); box-shadow: inset 3px 0 0 var(--under); }\n"
             "  .crewblock .cbadge { display: inline-block; min-width: 52px; text-align: center; margin-right: 6px; padding: 1px 6px; border-radius: 3px; font: 700 9.5px/1.6 var(--sans); letter-spacing: .06em; text-transform: uppercase; vertical-align: 1px; color: var(--muted); background: var(--surface); }\n"
             "  .crewblock .ctag { display: block; margin: 4px 0 0; font-size: 11px; color: var(--muted); }\n"
             "  .crewblock .crewcall { margin: 9px 0 2px; padding: 7px 9px; border-radius: 6px; background: var(--surface); font-size: 12.5px; line-height: 1.5; }\n"
             "  .crewalert { display: inline-block; font: 800 10px/1.7 var(--sans); letter-spacing: .08em; text-transform: uppercase; padding: 1px 7px; border-radius: 3px; margin-right: 6px; vertical-align: 1px; }\n"
             "  .crewalert.over { background: var(--over); color: #fff; } .crewalert.under { background: var(--under); color: #fff; } .crewalert.even { background: var(--surface); color: var(--muted); border: 1px solid var(--rule); }\n"
             # the three voices on the total (28 Oct 2026): the block on the Simulation card, green when the agreement rule fires
             "  .voices { display: block; padding: 9px 12px 9px 14px; margin: 8px 0 10px; border-radius: 8px; background: var(--surface-2); box-shadow: inset 3px 0 0 var(--muted); font-size: 12.5px; line-height: 1.5; color: var(--ink); }\n"
             "  .voices.fires { background: var(--go-wash); box-shadow: inset 3px 0 0 var(--go); }\n"
             "  .voices .vbadge { display: inline-block; min-width: 52px; text-align: center; margin-right: 6px; padding: 1px 7px; border-radius: 3px; font: 800 10px/1.7 var(--sans); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); background: var(--surface); border: 1px solid var(--rule); vertical-align: 1px; }\n"
             "  .voices .vbadge.bet { background: var(--go); color: #fff; border-color: var(--go); }\n"
             "  .voices .vline { margin-top: 3px; } .voices .vtake { margin-top: 6px; } .voices .vtag { margin-top: 4px; font-size: 11px; }\n"
             # middles on the total (28 Oct 2026): the panel on the rail, the watch block green when a pair pays, the pairs table, the calculator
             "  #nbaMidPanel .midnow { font-size: 12.5px; line-height: 1.5; margin: 2px 0 8px; }\n"
             "  .midwatch { display: block; padding: 9px 12px 9px 14px; margin: 8px 0 10px; border-radius: 8px; background: var(--surface-2); box-shadow: inset 3px 0 0 var(--muted); font-size: 12.5px; line-height: 1.5; color: var(--ink); }\n"
             "  .midwatch.pays { background: var(--go-wash); box-shadow: inset 3px 0 0 var(--go); } .midwatch .mwline { margin-top: 3px; } .midwatch .mwtake { margin-top: 6px; }\n"
             "  .midwatch .vbadge { display: inline-block; min-width: 52px; text-align: center; margin-right: 6px; padding: 1px 7px; border-radius: 3px; font: 800 10px/1.7 var(--sans); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); background: var(--surface); border: 1px solid var(--rule); vertical-align: 1px; }\n"
             "  .midwatch .vbadge.bet { background: var(--go); color: #fff; border-color: var(--go); }\n"
             "  table.midtab td.good { color: var(--go); } table.midtab td.bad { color: var(--muted); } table.midtab tr.pays td { font-weight: 600; } #nbaMidPanel .midnote { margin: 4px 0 8px; font-size: 11.5px; }\n"
             "  .midcalc { margin-top: 8px; font-size: 12.5px; } .midcalc .midcalcrow { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 6px; margin: 6px 0; } .midcalc input { width: 100%; box-sizing: border-box; } #midCalcOut { font-size: 12.5px; line-height: 1.5; }\n"
             "  .simrec .midrectab td.good { color: var(--go); } .simrec .midrectab td.bad { color: var(--bad); }\n"
             "  .crewchips { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0 2px; }\n"
             "  .refchip { font: 600 11px/1.5 var(--sans); padding: 2px 9px; border-radius: 12px; border: 1px solid var(--rule); background: var(--surface); color: var(--ink-2); } .refchip b { color: var(--ink); }\n"
             "  .refchip.over { border-color: var(--over); color: var(--over); } .refchip.under { border-color: var(--under); color: var(--under); }\n"
             "  /* recent form, basketball (22 Oct 2026): the chips carry the colour */\n"
             "  #nbaFormPanel table.form td { vertical-align: middle; } #nbaFormPanel .chip { padding: 2px 5px; margin-right: 2px; font-size: 9px; }\n"
             "  #nbaFormPanel table.form { margin: 4px 0 10px; font-size: 11.5px; } #nbaFormPanel table.form th, #nbaFormPanel table.form td { padding: 3px 5px; }\n"
             "  #nbaFormPanel .chip.push { background: var(--surface-2); color: var(--ink-2); }\n"
             "  /* the Props tab (19 Oct 2026) */\n"
             "  #propsView .propsctl { align-items: center; margin: 2px 0 8px; } #propsView .propsctl select, #propsView .propsctl input { padding: 6px 8px; font-size: 13px; }\n"
             "  /* the Every-prop table fits the page (26 Oct 2026, the user: the Take button was cut off): a touch smaller, tighter cells, and the three word columns may wrap before the table overflows */\n"
             "  table.props { font-size: 11.5px; } table.props th, table.props td { padding: 3px 5px; } table.props td:nth-child(1), table.props td:nth-child(2), table.props td:nth-child(3) { white-space: normal; }\n"
             "  table.props th.sortable { cursor: pointer; user-select: none; } table.props th.sortable:hover { color: var(--ink); } table.props th.sortable.on { color: var(--ink); border-bottom-color: var(--ink-2); }\n"
             "  table.props td.pos { color: var(--go); font-weight: 700; } table.props td.neg { color: var(--muted); }\n"
             "  table.props tr[data-prop] { cursor: pointer; } table.props tr.win td:first-child { border-left: 3px solid var(--go); }\n"
             "  table.props tr.loss td:first-child { border-left: 3px solid var(--bad); } table.props tr.void td, table.props tr.push td { color: var(--muted); }\n"
             "  #propsView b.lg, .pdlg b.lg { display: inline-block; min-width: 18px; text-align: center; padding: 0 5px; border-radius: 3px; font: 700 11.5px/1.5 var(--mono); background: var(--surface-2); color: var(--ink); }\n"
             "  #propsView b.lg.over, .pdlg b.lg.over { background: var(--go-wash); color: var(--go); } #propsView b.lg.under, .pdlg b.lg.under { background: var(--bad-wash); color: var(--bad); }\n"
             "  #propsView b.lg.push, .pdlg b.lg.push { background: var(--edge-wash); color: var(--edge); }\n"
             "  .pdlg .pd-log tr.this td { font-weight: 700; border-top: 2px solid color-mix(in srgb, var(--ink) 35%, transparent); } .pdlg .pd-log tr.this .tag { margin-left: 4px; }\n"
             "  /* the simulation card and its record (25 Oct 2026) */\n"
             "  #nbaSimPanel .simtiles { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin: 2px 0 8px; }\n"
             "  @media (max-width: 720px) { #nbaSimPanel .simtiles { grid-template-columns: repeat(2, minmax(0, 1fr)); } }\n"
             "  #nbaSimPanel .simtile { border: 1px solid var(--rule); border-radius: 8px; padding: 8px 10px; background: var(--surface-2); min-width: 0; }\n"
             "  #nbaSimPanel .simtile .k { font: 600 10px/1.4 var(--sans); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }\n"
             "  #nbaSimPanel .simtile .v { font: 700 18px/1.25 var(--mono); color: var(--ink); } #nbaSimPanel .simtile .s { font: 11px/1.4 var(--sans); color: var(--muted); }\n"
             "  #nbaSimPanel .simmeta { font: 12px/1.5 var(--sans); color: var(--ink-2); margin: 0 0 6px; }\n"
             "  #nbaSimPanel table.simtab { table-layout: fixed; margin: 4px 0 10px; } #nbaSimPanel .simtab th:first-child, #nbaSimPanel .simtab td:first-child { width: 40%; }\n"
             "  #nbaSimPanel .simtab td, #nbaSimPanel .simtab th { white-space: normal; vertical-align: top; padding: 6px 6px; }\n"
             "  #nbaSimPanel .mkname { font: 700 12.5px/1.4 var(--sans); color: var(--ink); } #nbaSimPanel .mkline { font: 12px/1.5 var(--mono); } #nbaSimPanel .mkline .dim { font: 11px/1.4 var(--sans); }\n"
             "  .simchip { display: inline-block; padding: 1px 7px; border-radius: 4px; font: 600 12px/1.6 var(--mono); background: var(--surface-2); color: var(--ink); white-space: nowrap; }\n"
             "  .simchip.simlean { background: var(--edge-wash); color: var(--edge); } .simchip.simbet { background: var(--go-wash); color: var(--go); } .simchip.simstrong { background: var(--go); color: #fff; }\n"
             "  #nbaSimPanel .simsub { font: 11px/1.4 var(--sans); color: var(--muted); margin-top: 2px; }\n"
             "  #nbaSimPanel table.simq { margin: 2px 0 8px; } #nbaSimPanel table.simq th, #nbaSimPanel table.simq td { text-align: center; padding: 3px 4px; } #nbaSimPanel table.simq th:first-child, #nbaSimPanel table.simq td:first-child { text-align: left; white-space: normal; font-family: var(--sans); }\n"
             "  #nbaSimPanel .simprof { margin-top: 4px; font-size: 11.5px; line-height: 1.5; }\n"
             "  .simrec { margin-top: 10px; } .simrec .simrecview { font-weight: 700; margin: 8px 0 4px; } .simrec .simrectab td.good { color: var(--go); } .simrec .simrectab td.bad { color: var(--bad); }\n"
             "  #nbaSimPanel .ttgap { margin-top: 3px; font: 11.5px/1.5 var(--sans); } .simchip.gaprule { font-size: 11px; }\n"
             "  /* the Props tab's own Is it working block, in colour (22 Oct 2026) */\n"
             "  #propsCalib .calib > div.good { box-shadow: inset 3px 0 0 var(--go); } #propsCalib .calib > div.bad { box-shadow: inset 3px 0 0 var(--bad); }\n"
             "  #propsCalib .calib > div.good .v, #propsCalib .calib > div.good .units { color: var(--go); } #propsCalib .calib > div.bad .v, #propsCalib .calib > div.bad .units { color: var(--bad); }\n"
             "  #propsCalib .calib .units { font-weight: 700; } #propsCalib .does.up { color: var(--go); font-weight: 700; } #propsCalib .does.down { color: var(--bad); font-weight: 700; }\n"
             "  #propsCalib table.form td.pos { color: var(--go); font-weight: 700; } #propsCalib table.form td.neg { color: var(--bad); font-weight: 700; }\n"
             "  #propsCalib .subhead { margin-top: 14px; } #propsCalib .verdict { margin-top: 12px; }\n"
             "  /* the prop's own panel (21 Oct 2026) */\n"
             "  body.noscroll { overflow: hidden; }\n"
             "  .pdlg { position: fixed; inset: 0; z-index: 60; background: rgba(8, 12, 11, 0.58); display: flex; align-items: flex-start; justify-content: center; padding: 28px 16px; overflow-y: auto; }\n"
             "  .pdlg[hidden] { display: none; }\n"
             "  .pdlg-box { position: relative; width: min(780px, 100%); background: var(--surface); color: var(--ink); border: 1px solid var(--rule); border-radius: 12px; padding: 20px 22px 22px; box-shadow: 0 24px 70px rgba(0, 0, 0, 0.4); }\n"
             "  .pdlg-top { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin: -4px 0 10px; }\n"
             "  .pdlg-nav { display: flex; align-items: center; gap: 8px; } .pdlg-nav[hidden] { display: none; } .pdlg-nav .btn[disabled] { opacity: .45; cursor: default; }\n"
             "  .pdlg-close { margin-left: auto; }\n"
             "  .pdlg .pd-band { font: 900 11px/1 var(--sans); letter-spacing: .1em; text-transform: uppercase; color: var(--edge); }\n"
             "  .pdlg h3 { margin: 4px 0 2px; font: 800 23px/1.15 var(--sans); } .pdlg h3 .tag { vertical-align: middle; }\n"
             "  .pdlg .pd-pick { font: 700 17px/1.3 var(--sans); margin: 2px 0; } .pdlg .pd-pick .chip { vertical-align: middle; margin-left: 6px; }\n"
             "  .pdlg .pd-sub { color: var(--muted); font-size: 12.5px; line-height: 1.5; margin: 0 0 6px; }\n"
             "  .pdlg .pd-tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(118px, 1fr)); gap: 8px; margin: 12px 0 6px; }\n"
             "  .pdlg .pd-tile { border: 1px solid var(--rule); border-radius: 8px; padding: 8px 10px; background: var(--surface-2); }\n"
             "  .pdlg .pd-tile .k { font: 600 10px/1.4 var(--sans); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }\n"
             "  .pdlg .pd-tile .v { font: 700 19px/1.25 var(--mono); } .pdlg .pd-tile .s { font: 11px/1.4 var(--sans); color: var(--muted); }\n"
             "  .pdlg .pd-tile.good .v { color: var(--go); } .pdlg .pd-tile.bad .v { color: var(--bad); }\n"
             "  .pdlg .pd-simtiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(128px, 1fr)); gap: 8px; margin: 4px 0 8px; } .pdlg .pd-simtiles .pd-tile .v { font-size: 17px; }\n"
             "  .pdlg h4 { margin: 16px 0 6px; font: 700 11px/1.4 var(--sans); letter-spacing: .1em; text-transform: uppercase; color: var(--ink-2); } .pdlg h4 .dim { text-transform: none; letter-spacing: 0; font-weight: 500; }\n"
             "  .pdlg ul.pd-why { margin: 0; padding-left: 18px; font: 13px/1.55 var(--sans); color: var(--ink); } .pdlg ul.pd-why li { margin: 4px 0; }\n"
             "  .pdlg table.form { margin: 4px 0 4px; } .pdlg table.form td, .pdlg table.form th { white-space: normal; } .pdlg table.form tr.carded td { font-weight: 700; }\n"
             "  .pdlg .note { margin: 14px 0 0; }\n"
             "  .pdlg .pd-base, .pdlg .pd-floors { font: 12.5px/1.5 var(--sans); color: var(--ink-2); margin: 0 0 8px; }\n"
             "  .pdlg .pd-levers { display: grid; gap: 6px; }\n"
             "  .pdlg .lever { display: grid; grid-template-columns: minmax(150px, 1.2fr) 2fr 56px; gap: 10px; align-items: center; font: 12.5px/1.4 var(--sans); }\n"
             "  .pdlg .lever .lb { height: 10px; background: var(--surface-2); border-radius: 5px; overflow: hidden; } .pdlg .lever .lb span { display: block; height: 100%; border-radius: 5px; background: var(--muted); }\n"
             "  .pdlg .lever.helps .lb span { background: var(--go); } .pdlg .lever.hurts .lb span { background: var(--bad); }\n"
             "  .pdlg .lever .lv { font: 700 13px/1 var(--mono); text-align: right; } .pdlg .lever.helps .lv { color: var(--go); } .pdlg .lever.hurts .lv { color: var(--bad); }\n"
             "  .pdlg .lever.top .lt { font-weight: 700; }\n"
             "  .pdlg ul.pd-why li.lever-line { font-weight: 600; color: var(--go); } .pdlg ul.pd-why li.lever-line::marker { color: var(--go); }\n"
             "  .pdlg ul.pd-why li.lever-against::marker { color: var(--bad); } .pdlg ul.pd-why li .tag.hurts { background: var(--bad); color: #fff; margin-left: 4px; } .pdlg ul.pd-why li .tag.helps { background: var(--go); color: #fff; margin-left: 4px; }\n"
             "  .pk .n5 { font-size: 11px; color: var(--ink-2); }\n"
             "  /* the bets you take (26 Oct 2026): a Take button on every priced market and prop, the marked ones listed and lit */\n"
             "  .takebtn { font: 700 10.5px/1 var(--sans); letter-spacing: .06em; text-transform: uppercase; padding: 5px 10px; border-radius: 999px; border: 1.5px solid var(--rule); background: transparent; color: var(--ink-2); cursor: pointer; }\n"
             "  .takebtn:hover { border-color: var(--ink); color: var(--ink); } .takebtn.on { background: var(--go); border-color: var(--go); color: #fff; } .takebtn.big { font-size: 12px; padding: 7px 14px; }\n"
             "  .pk .n6 { margin-top: 8px; } .pdlg .pd-take { margin: 6px 0 2px; } table.props td.take, #board td:last-child { white-space: nowrap; }\n"
             "  .takebtn.off { opacity: .45; cursor: not-allowed; } .simtab .simtake { margin-top: 5px; } .ttgap .takebtn { margin-left: 4px; vertical-align: middle; }\n"
             "  table.props td.agree { font-family: var(--mono); white-space: nowrap; } .pk .tag.agree { background: var(--go); color: #fff; }\n"
             "  /* the simulation's stats on the Props page (26 Oct 2026): a card a game, the Sim column, the best cards' last line */\n"
             "  table.props td.usgc { font-family: var(--mono); white-space: nowrap; } table.props td.usgc .tag { font-size: 9px; padding: 1px 4px; margin-left: 2px; vertical-align: middle; }\n"
             "  table.props td.simc { font-family: var(--mono); white-space: nowrap; } .pk .n5.simline.pos { color: var(--go); } .pk .n5.simline.neg { color: var(--bad); }\n"
             "  .pk.simg .n2 { font-family: var(--mono); } .pk.simg .n2 .dim { font-weight: 500; font-size: 13px; } .pk.simg.dim { opacity: .7; } .pk.simg .n5 b { color: var(--ink); }\n"
             "  .pk.pair.agrees { border-color: var(--go); } .pk.pair.win { box-shadow: inset 4px 0 0 var(--go); } .pk.pair.loss { box-shadow: inset 4px 0 0 var(--bad); } .pdlg h3 .tag.role { background: var(--ink-2); color: var(--bg, #fff); }\n"
             "  /* what happened on each of his last games (26 Oct 2026): the first factor bold, red under the line and green over it */\n"
             "  .pdlg .pd-log td:not(.pd-what) { white-space: nowrap; } .pdlg .pd-log td.pd-what { font-size: 11.5px; color: var(--ink-2); white-space: normal; min-width: 220px; } .pdlg .pd-log td.pd-what b { font-weight: 600; } .pdlg .pd-log td.pd-what b.under { color: var(--bad); } .pdlg .pd-log td.pd-what b.over { color: var(--go); }\n"
             "  /* the fives and the matchup on the prop (27 Oct 2026): both clubs' starting fives on the panel with the man marked, and a way to the game on the NBA card */\n"
             "  .pdlg .pd-fives { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; margin: 6px 0 4px; } .pdlg .pd-fives .five p { margin: 0 0 4px; } .pdlg .pd-fives table.form { margin: 0; } .pdlg .pd-fives tr.me td { font-weight: 700; color: var(--go); }\n"
             "  .pdlg .pd-go { margin: 8px 0 2px; display: flex; gap: 8px; flex-wrap: wrap; align-items: center; } .pk .n6 .btn.go { margin-left: 6px; padding: 4px 10px; font-size: 10.5px; }\n"
             "  /* the pair's own panel (26 Oct 2026): the ticket opens like a prop, each leg in a box of its own with a way to its panel */\n"
             "  .pk[data-pair] { cursor: pointer; } .pk[data-pair]:hover { border-color: var(--ink); } .pdlg h3 .amp { color: var(--muted); font-weight: 500; }\n"
             "  .pdlg .pd-leg { border: 1px solid var(--rule); border-radius: 8px; padding: 6px 12px 10px; margin: 10px 0; } .pdlg .pd-leg h4 { margin: 6px 0 2px; } .pdlg .pd-leg .pd-tiles { margin: 8px 0 6px; }\n"
             "  .pdlg .pd-leg .pd-base .pos { color: var(--go); } .pdlg .pd-leg .pd-base .neg { color: var(--bad); } .pdlg .pd-leg .row { gap: 8px; align-items: center; }\n"
             "  .pdlg.phone .pdlg-box { max-width: 640px; } .pdlg.phone h3 { margin: 4px 0 10px; font: 800 20px/1.2 var(--sans); } .pdlg.phone h3 .tag { vertical-align: middle; }\n"
             "  .qrbox { background: #fff; padding: 10px; border-radius: 10px; width: min(100%, 520px); margin: 0 auto 10px; } .qrbox svg { display: block; width: 100%; height: auto; }\n"
             "  .pk.taking, tr.taking { box-shadow: inset 4px 0 0 var(--go); } .pk.taking.sum { border-style: dashed; } .chip.taken { background: var(--go); color: #fff; }\n"
             "  #calibBox .calib[data-sport=\"TAKEN\"] > div.good { box-shadow: inset 3px 0 0 var(--go); } #calibBox .calib[data-sport=\"TAKEN\"] > div.bad { box-shadow: inset 3px 0 0 var(--bad); }\n"
             "  @media (max-width: 640px) { .pdlg .lever { grid-template-columns: 1fr 1fr 50px; } }\n"
             "  @media (max-width: 640px) { .pdlg { padding: 10px 8px; } .pdlg-box { padding: 16px 14px 18px; } .pdlg h3 { font-size: 20px; } }\n"
             "  #propsView .picks .pk.scored { border-color: var(--go); }\n"
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
    # Links on the board card: Outlier is off the Super Model (19 Oct 2026), BetMGM's hockey board takes its place
    h = once(h, '<a href="https://app.outlier.bet/MLB/games" target="_blank" rel="noopener">Outlier · games</a>',
             '<a href="https://sports.betmgm.com/en/sports/hockey-12" target="_blank" rel="noopener">BetMGM · NHL</a>', "board links")
    h = once(h, '              <a href="https://app.outlier.bet/MLB/games" target="_blank" rel="noopener">Outlier · matchup panel</a>\n',
             '', "outlier matchup link")
    h = once(h, '              <a href="https://app.outlier.bet/MLB/games" target="_blank" rel="noopener">Outlier · L10 / H2H</a>\n',
             '', "outlier l10 link")
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
             '                 "naort","nhort","nadrt","nhdrt","napace","nhpace","nagp","nhgp","nlrtg","nlpace","narest","nhrest","nbaout","nbaq","nbactx","ncrew","nbarefs","nbalineup","nbaform","nbasim","odds","sharp"];\n'
             '  var ALL = MLB_IDS.concat(WNBA_IDS).concat(NHL_IDS).concat(NBA_IDS).filter(function (v, i, a) { return a.indexOf(v) === i; });\n'
             '  var CHECKS = ["dome","playoff","agconf","hgconf","agbk","hgbk"];\n'
             '  function sportOf(s) { return s === "WNBA" ? "WNBA" : s === "NHL" ? "NHL" : s === "NBA" ? "NBA" : "MLB"; }\n'
             '  /* the period market: the first five in baseball, the first period in hockey, the first half in the NBA */\n'
             '  function isPeriod(mk) { return mk.key === "f5" || mk.key === "p1" || mk.key === "h1"; }', "ids")
    t = once(t, '    if (keep.length !== card.length) { card = keep; try { localStorage.setItem(KEY, JSON.stringify(card)); } catch (e) {} }\n'
                '  })();\n'
                '  function save() {',
             '    if (keep.length !== card.length) { card = keep; try { localStorage.setItem(KEY, JSON.stringify(card)); } catch (e) {} }\n'
             '  })();\n'
             '  /* An NBA row re-scored while another game sat in the form (a slate or odds file merged\n'
             '     into the card) carried that game\'s names on its moneyline and spread until 21 Oct 2026\n'
             '     (the user\'s backup: "Islanders ML" on Celtics @ Pistons); the sides and the grades were\n'
             '     right. Relabel such rows by side from the row\'s own clubs, once, on load. */\n'
             '  (function () {\n'
             '    var fixed = 0;\n'
             '    card.forEach(function (r) {\n'
             '      if (r.sport !== "NBA" || !r.markets) return;\n'
             '      var away = String(r.away || ""), home = String(r.home || ""), sp = parseFloat((r.inputs || {}).sp);\n'
             '      r.markets.forEach(function (m) {\n'
             '        if (m.key !== "ml" && m.key !== "spread") return;\n'
             '        var pick = String(m.pick || "");\n'
             '        if ((away && pick.indexOf(away) === 0) || (home && pick.indexOf(home) === 0)) return;\n'
             '        var mine = m.side === "HOME" ? home : away, theirs = m.side === "HOME" ? away : home;\n'
             '        if (!mine || !theirs) return;\n'
             '        if (m.key === "ml") {\n'
             '          m.pick = mine + " ML"; if (m.other) m.other.pick = theirs + " ML";\n'
             '        } else {\n'
             '          if (!isFinite(sp)) return;\n'
             '          var mineLine = m.side === "HOME" ? sp : -sp;\n'
             '          m.pick = mine + " " + fmtLine(mineLine); m.label = "Spread " + home + ": " + fmtLine(sp);\n'
             '          if (m.other) m.other.pick = theirs + " " + fmtLine(-mineLine);\n'
             '        }\n'
             '        fixed++;\n'
             '      });\n'
             '    });\n'
             '    if (fixed) { try { localStorage.setItem(KEY, JSON.stringify(card)); } catch (e) {} }\n'
             '  })();\n'
             '  function save() {', "relabel")
    t = once(t, "the units column is the referee.') + '</div>';\n    });",
             "the units column is the referee.') + '</div>';\n      if (sp === \"NBA\") h += nbaRefsWatchHtml();   // the referees as a watch (22 Oct 2026)\n      if (sp === \"NBA\") h += nbaSimRecordHtml();   // the simulation's calls, says against does (25 Oct 2026)\n    });", "refs watch")
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
             'NHL: [["total","Full-game total"],["p1","First period"],["ml","Moneyline"],["pl","Puck line"],["alt","Alternate totals"]],\n'
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
             '                      "sp","sph","spa","h1line","h1op","h1up","naort","nhort","nadrt","nhdrt","napace","nhpace","nagp","nhgp","nlrtg","nlpace","narest","nhrest","nbaout","nbactx","ncrew","nbarefs","nbalineup","nbaform","nbasim"];', "slate fields")
    # the slate's backup-in-net flags are booleans, carried like the roof: into a
    # row's inputs when the card already has the game, into the form otherwise.
    # The Confirmed boxes travel the same way (19 Oct 2026): the slate ticks one
    # when RotoWire marks the start confirmed; it never unticks a box.
    t = once(t, '          if (g.inputs.dome === true && !row.inputs.dome) { row.inputs.dome = true; changed = true; }',
             '          if (g.inputs.dome === true && !row.inputs.dome) { row.inputs.dome = true; changed = true; }\n'
             '          ["agbk", "hgbk", "agconf", "hgconf"].forEach(function (k) { if (g.inputs[k] === true && !row.inputs[k]) { row.inputs[k] = true; changed = true; } });', "slate backup flags into rows")
    # a later slate refreshes the starting five on a row already carded (23 Oct 2026): the lineup is display only and
    # changes through the day (expected to confirmed, a scratch), so the newer file's box replaces the older one; every
    # other box keeps the loader's rule, blanks fill and typed values stay, so the record is of the row as logged
    t = once(t, '          ["agbk", "hgbk", "agconf", "hgconf"].forEach(function (k) { if (g.inputs[k] === true && !row.inputs[k]) { row.inputs[k] = true; changed = true; } });',
             '          ["agbk", "hgbk", "agconf", "hgconf"].forEach(function (k) { if (g.inputs[k] === true && !row.inputs[k]) { row.inputs[k] = true; changed = true; } });\n'
             '          ["nbalineup", "nbaout", "nbasim"].forEach(function (k) { if (!blank(g.inputs[k]) && String(g.inputs[k]) !== String(row.inputs[k] || "")) { row.inputs[k] = String(g.inputs[k]); changed = true; } });   // the starting five follows the newest slate (23 Oct 2026); so do the injury report and the simulation run from it (26 Oct 2026), shown and recorded, never scored by the engine', "lineup refresh")
    t = once(t, '    if (g.inputs && g.inputs.dome === true) v.dome = true;',
             '    if (g.inputs && g.inputs.dome === true) v.dome = true;\n'
             '    ["agbk", "hgbk", "agconf", "hgconf"].forEach(function (k) { if (g.inputs && g.inputs[k] === true) v[k] = true; });', "slate backup flags into the form")
    t = once(t, '      if (!blank(i.aera) && !blank(i.hera)) meta.push("ERA " + esc(i.aera) + "/" + esc(i.hera));',
             '      if (!blank(i.aera) && !blank(i.hera)) meta.push("ERA " + esc(i.aera) + "/" + esc(i.hera));\n'
             '      if (!blank(i.agsv) && !blank(i.hgsv)) meta.push("SV " + esc(i.agsv) + "/" + esc(i.hgsv));', "slate meta")
    # the Props tab (19 Oct 2026): the backup carries the props and a restore brings them back; the slate
    # loader takes a props file too and grades the props from a grade file's box lines; the record block
    # ends with the props tile; a sport button leaves the tab
    t = once(t, '                            card: card, draft: { sport: sport, inputs: snapshot() } }, null, 2);',
             '                            card: card, props: props, draft: { sport: sport, inputs: snapshot() } }, null, 2);', "backup props")
    t = once(t, '        } else card = d.card;\n        save(); renderCard(); renderBoard(); renderCalib();',
             '        } else card = d.card;\n'
             '        if (!moved && Array.isArray(d.props)) { props = d.props; saveProps(); renderProps(); }\n'
             '        save(); renderCard(); renderBoard(); renderCalib();', "restore props")
    t = once(t, '    saveSlate(); save(); renderCard(); renderBoard(); renderCalib();\n    say("Slate "',
             '    saveSlate(); save(); renderCard(); renderBoard(); renderCalib();\n'
             '    var propsGraded = gradeProps(d); if (propsGraded) { renderCalib(); renderBoard(); }   // the board\'s Taking tonight carries the props\' and the pairs\' results (26 Oct 2026)\n'
             '    say("Slate "', "grade props")
    t = once(t, '". Typed values were not overwritten; lines and prices are never in a slate.");',
             '". Typed values were not overwritten; lines and prices are never in a slate." + (propsGraded ? " <b>" + propsGraded + "</b> prop" + (propsGraded === 1 ? "" : "s") + " graded on the Props tab." : "")'
             ' + (propsMinsFilled ? " Minutes filled in on <b>" + propsMinsFilled + "</b> graded prop" + (propsMinsFilled === 1 ? "" : "s") + " from the box lines." : ""));', "grade props message")
    t = once(t, '      try { applySlate(JSON.parse(rd.result), f.name); }',
             '      try { var sd = JSON.parse(rd.result); if (sd && sd.format === "callsheet3.props") applyProps(sd, f.name); else applySlate(sd, f.name); }', "props file")
    t = once(t, '    box.innerHTML = h;\n  }\n\n\n  /* ---- the WNBA paste', '    h += propsRecordHtml();\n    box.innerHTML = h;\n  }\n\n\n  /* ---- the WNBA paste', "props record")
    t = once(t, '    $("opened").placeholder = s === "WNBA" ? "165.5" : s === "NBA" ? "228.5" : s === "NHL" ? "6" : "8.5";',
             '    $("opened").placeholder = s === "WNBA" ? "165.5" : s === "NBA" ? "228.5" : s === "NHL" ? "6" : "8.5";\n'
             '    if (propsView) showProps(false);', "props off on a sport")
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
# the starting fives as the slate writes them from RotoWire (20 Oct 2026): the 76ers' expected
# without Embiid, the Knicks' confirmed without Robinson, the may-not-play men under each
NBA_EXAMPLE_LINEUP = {
    "away": {"status": "expected", "five": [["PG", "Tyrese Maxey"], ["SG", "VJ Edgecombe"], ["SF", "Paul George"], ["PF", "Kelly Oubre Jr."], ["C", "Adem Bona"]],
             "maybe": [["G", "Anfernee Simons", "Ques"], ["F", "Dominick Barlow", "GTD"], ["C", "Joel Embiid", "Out"]]},
    "home": {"status": "confirmed", "five": [["PG", "Jalen Brunson"], ["SG", "Mikal Bridges"], ["SF", "Josh Hart"], ["PF", "OG Anunoby"], ["C", "Karl-Anthony Towns"]],
             "maybe": [["C", "Mitchell Robinson", "Out"]]},
    "src": "RotoWire"}
# the referee table the slate writes from the ledger: each official's games, free throws and points a game, and the league's
NBA_EXAMPLE_REFS ={"lg": [2462, 44.0, 228.8], "r": {"Scott Foster": [118, 46.2, 229.1, 66, 41, 4, 2], "Tony Brothers": [95, 43.1, 226.0, 56, 54, 3, 3], "Marc Davis": [102, 44.8, 230.3, 71, 51, 0, 0], "Zach Zarba": [110, 42.9, 227.4, 58, 60, 2, 5]}}


# each side's last five as the slate writes them (22 Oct 2026): the score, the half, and the close the odds run saw
# (the total, the first-half total, the home spread); one game without a close
NBA_EXAMPLE_FORM = {
    "away": [{"date": "2026-10-30", "opp": "Celtics", "home": False, "pf": 104, "pa": 112, "h1f": 51, "h1a": 58, "end": "REG", "ctot": 221.5, "ch1": 110.5, "csp": -6.5},
             {"date": "2026-11-01", "opp": "Hornets", "home": True, "pf": 118, "pa": 109, "h1f": 60, "h1a": 52, "end": "REG", "ctot": 224.0, "ch1": 112.0, "csp": -7.5},
             {"date": "2026-11-03", "opp": "Bulls", "home": True, "pf": 112, "pa": 115, "h1f": 55, "h1a": 57, "end": "OT", "ctot": 226.5, "ch1": 113.0, "csp": -4.0},
             {"date": "2026-11-05", "opp": "Heat", "home": False, "pf": 99, "pa": 101, "h1f": 48, "h1a": 50, "end": "REG", "ctot": None, "ch1": None, "csp": None},
             {"date": "2026-11-08", "opp": "Magic", "home": True, "pf": 121, "pa": 108, "h1f": 63, "h1a": 49, "end": "REG", "ctot": 219.5, "ch1": 109.5, "csp": -3.5}],
    "home": [{"date": "2026-10-31", "opp": "Nets", "home": True, "pf": 124, "pa": 106, "h1f": 64, "h1a": 50, "end": "REG", "ctot": 228.5, "ch1": 114.5, "csp": -9.5},
             {"date": "2026-11-02", "opp": "Bucks", "home": False, "pf": 110, "pa": 117, "h1f": 52, "h1a": 61, "end": "REG", "ctot": 230.0, "ch1": 115.0, "csp": -2.5},
             {"date": "2026-11-04", "opp": "Pacers", "home": True, "pf": 131, "pa": 120, "h1f": 68, "h1a": 59, "end": "REG", "ctot": 235.5, "ch1": 118.0, "csp": -5.5},
             {"date": "2026-11-06", "opp": "Cavaliers", "home": False, "pf": 103, "pa": 98, "h1f": 49, "h1a": 47, "end": "REG", "ctot": 222.0, "ch1": 111.5, "csp": 3.0},
             {"date": "2026-11-09", "opp": "Raptors", "home": True, "pf": 115, "pa": 100, "h1f": 57, "h1a": 46, "end": "REG", "ctot": 225.0, "ch1": 112.5, "csp": -8.0}]}


def nba_example_sim() -> dict:
    """The example row's simulation block, built by nbasim itself (seeded, so the page's example never changes between builds)."""
    sys.path.insert(0, str(pathlib.Path(__file__).parent / "slate"))
    import nbasim  # noqa: E402  (slate/nbasim.py)
    def setup():
        lg = dict(nbasim.LEAGUE)
        away = {"ab": "PHI", "ortg": 113.5, "drtg": 115.0, "pace": 99.5, "tov": 0.135, "trip": 0.10, "ft": 0.79, "a3": 0.41, "p3": 0.36, "p2": 0.55, "oreb": 0.27, "b2b": False, "out_adj": -2.1, "out_dadj": 1.4, "n": 15}
        home = {"ab": "NYK", "ortg": 118.0, "drtg": 109.0, "pace": 98.0, "tov": 0.125, "trip": 0.11, "ft": 0.80, "a3": 0.44, "p3": 0.37, "p2": 0.56, "oreb": 0.29, "b2b": True, "out_adj": -1.0, "out_dadj": 0.7, "n": 16}
        return {"league": lg, "away": away, "home": home, "ft_factor": 1.03}
    s = setup()
    own = nbasim.simulate(s, n=3000, seed=5)
    mkt = nbasim.simulate_anchored(setup(), 231.5, -5.5, n=3000, seed=6)
    return {"v": nbasim.VERSION, "runs": 3000, "own": nbasim.histograms(own), "mkt": nbasim.histograms(mkt), "anchor": {"total": 231.5, "sp": -5.5, "book": "DraftKings"},
            "ft_factor": 1.03, "shrink": nbasim.SHRINK, "bands": nbasim.BANDS,
            "prof": {"away": {"ortg": 113.5, "drtg": 115.0, "pace": 99.5, "n": 15, "b2b": False, "out": -2.1, "a3": 0.41},
                     "home": {"ortg": 118.0, "drtg": 109.0, "pace": 98.0, "n": 16, "b2b": True, "out": -1.0, "a3": 0.44}}}


def nba_example_js() -> str:
    return ('      restore({ away: "76ers", home: "Knicks", line: "231.5", op: "-110", up: "-110", opened: "229.5", gdate: $("gdate").value,\n'
            '        aml: "164", hml: "-198", sp: "-5.5", sph: "-108", spa: "-112", h1line: "115.5", h1op: "-110", h1up: "-110",\n'
            '        naort: "113.5", nadrt: "115.0", nhort: "118.0", nhdrt: "109.0", napace: "99.5", nhpace: "98.0", nagp: "15", nhgp: "16", nlrtg: "113.0", nlpace: "100.5", narest: "1", nhrest: "0",\n'
            '        nbaout: ' + json.dumps(json.dumps(NBA_EXAMPLE_OUT, separators=(",", ":"))) + ',\n'
            '        nbactx: ' + json.dumps(json.dumps(NBA_EXAMPLE_CTX, separators=(",", ":"))) + ',\n'
            '        nbalineup: ' + json.dumps(json.dumps(NBA_EXAMPLE_LINEUP, separators=(",", ":"))) + ',\n'
            '        nbaform: ' + json.dumps(json.dumps(NBA_EXAMPLE_FORM, separators=(",", ":"))) + ',\n'
            '        nbasim: ' + json.dumps(json.dumps(nba_example_sim(), separators=(",", ":"))) + ',\n'
            '        ncrew: "Scott Foster, Tony Brothers, Marc Davis", nbarefs: ' + json.dumps(json.dumps(NBA_EXAMPLE_REFS, separators=(",", ":"))) + ' });\n')


def props_example_games() -> list:
    """One game's props for the Props tab's Example button (19 Oct 2026, the
    user: "put an example on the NBA props model like you did for the NBA"),
    computed through the slate's own projection on made-up but plausible game
    logs, so the example reads exactly as a real file does: 76ers @ Knicks, the
    NBA example's game, Embiid out, eight props across the five markets."""
    import random
    sys.path.insert(0, str(pathlib.Path(__file__).parent / "slate"))
    import slate  # noqa: E402
    rng = random.Random(19)
    rng2 = random.Random(23)   # the box behind each line (26 Oct 2026) draws from its own stream, so the example's stats stay as they were
    opps = ["BOS", "MIA", "CHI", "TOR", "CLE", "ATL", "ORL", "DET", "BKN", "MIL", "IND", "WAS"]

    def logs(n, start, mins, per36, home_first, starts=True):
        out = []
        for k in range(n):
            m = max(8.0, min(44.0, rng.gauss(mins, 3.5)))
            g = {"d": (start + dt.timedelta(days=2 * k + rng.randint(0, 1))).isoformat(), "opp": rng.choice(opps), "home": (k + (0 if home_first else 1)) % 2 == 0,
                 "min": round(m, 1), "st": 1 if starts else 0, "full": True}
            for mk, r36 in per36.items():
                mu = r36 * m / 36.0
                g[mk] = max(0, int(round(rng.gauss(mu, slate.PROPS_SD_K[mk] * (mu ** 0.5) if mu > 0 else 0.5))))
            # the box behind the line (26 Oct 2026, the panel's what-happened column): his shots and makes, the margin, the pace
            pts = g.get("pts", 0)
            fga = max(1, int(round(pts / 1.15 * rng2.uniform(0.85, 1.15))))
            fta = max(0, int(round(pts * 0.22 * rng2.uniform(0.5, 1.5))))
            g.update({"fga": fga, "fgm": max(0, min(fga, int(round(fga * rng2.uniform(0.36, 0.56))))), "fta": fta, "ftm": max(0, int(round(fta * 0.8))), "tov": rng2.randint(0, 4),
                      "mg": int(round(rng2.gauss(0, 13))) or 1, "pace": round(rng2.gauss(100.5, 4.0), 1), "ot": rng2.random() < 0.06,
                      "treb": int(round(rng2.gauss(44, 5))), "tast": int(round(rng2.gauss(25, 4)))})
            out.append(g)
        return out
    this_start, last_start = dt.date(2026, 10, 21), dt.date(2025, 11, 1)
    players = {
        "Jalen Brunson": ("NYK", "G", logs(15, this_start, 34.8, {"pts": 28.9, "reb": 3.2, "ast": 7.4, "tpm": 2.6}, True), logs(60, last_start, 35.0, {"pts": 27.1, "reb": 3.0, "ast": 7.0, "tpm": 2.4}, False)),
        "Karl-Anthony Towns": ("NYK", "C", logs(16, this_start, 33.5, {"pts": 24.5, "reb": 13.0, "ast": 3.3, "tpm": 1.9}, True), logs(62, last_start, 34.0, {"pts": 25.6, "reb": 13.2, "ast": 3.3, "tpm": 2.0}, False)),
        "Mikal Bridges": ("NYK", "F", logs(16, this_start, 36.0, {"pts": 18.0, "reb": 3.4, "ast": 3.7, "tpm": 2.0}, True), logs(64, last_start, 36.5, {"pts": 17.6, "reb": 3.2, "ast": 3.6, "tpm": 1.9}, False)),
        "OG Anunoby": ("NYK", "F", logs(14, this_start, 34.0, {"pts": 17.5, "reb": 4.9, "ast": 2.0, "tpm": 2.3}, True), logs(55, last_start, 35.0, {"pts": 16.9, "reb": 4.8, "ast": 2.2, "tpm": 2.2}, False)),
        "Tyrese Maxey": ("PHI", "G", logs(15, this_start, 36.5, {"pts": 27.0, "reb": 3.3, "ast": 6.1, "tpm": 3.0}, False), logs(52, last_start, 37.0, {"pts": 26.5, "reb": 3.3, "ast": 6.0, "tpm": 2.9}, True)),
        "Paul George": ("PHI", "F", logs(12, this_start, 33.0, {"pts": 17.0, "reb": 5.9, "ast": 4.2, "tpm": 2.4}, False), logs(41, last_start, 32.0, {"pts": 17.2, "reb": 5.8, "ast": 4.3, "tpm": 2.3}, True)),
        "Kelly Oubre Jr.": ("PHI", "F", logs(15, this_start, 31.0, {"pts": 16.9, "reb": 6.4, "ast": 1.5, "tpm": 1.4}, False), logs(60, last_start, 31.5, {"pts": 16.4, "reb": 6.2, "ast": 1.6, "tpm": 1.5}, True)),
        "Joel Embiid": ("PHI", "C", logs(9, this_start, 31.2, {"pts": 27.5, "reb": 9.5, "ast": 3.8, "tpm": 1.2}, False), logs(19, last_start, 30.5, {"pts": 23.8, "reb": 8.2, "ast": 4.5, "tpm": 1.1}, True)),
    }
    # a regular out or back on some nights, as the ledger would say (26 Oct 2026)
    for name, (team, _pos, this, _last) in players.items():
        mate = ("Paul George" if name == "Joel Embiid" else "Joel Embiid") if team == "PHI" else "Josh Hart"
        for k, g in enumerate(this):
            if k % 5 == 3:
                g["out"], g["back"] = [[mate, 31.2]], []
            elif k % 5 == 4:
                g["out"], g["back"] = [], [[mate, 31.2]]
            if k % 4 == 1:
                g["grab"] = [mate, 12, 6.5]
            elif k % 4 == 2:
                g["dish"] = [mate, 7, 3.5]
    lines = [("Jalen Brunson", "pts", 27.5, -110, -110), ("Karl-Anthony Towns", "reb", 11.5, -115, -105), ("Mikal Bridges", "pra", 24.5, -110, -110), ("OG Anunoby", "ast", 2.5, 100, -120),
             ("Tyrese Maxey", "pts", 25.5, -110, -110), ("Paul George", "tpm", 2.5, -120, 100), ("Kelly Oubre Jr.", "pts", 14.5, -105, -115), ("Joel Embiid", "reb", 9.5, -110, -110)]
    dvp = {"NYK": {"G": {"f": 0.97, "f_this": 0.95, "n_this": 16, "f_last": 0.99, "n_last": 82}, "F": {"f": 1.02, "f_this": 1.03, "n_this": 16, "f_last": 1.01, "n_last": 82}, "C": {"f": 1.05, "f_this": 1.07, "n_this": 16, "f_last": 1.03, "n_last": 82}},
           "PHI": {"G": {"f": 1.06, "f_this": 1.08, "n_this": 15, "f_last": 1.02, "n_last": 82}, "F": {"f": 1.01, "f_this": 1.00, "n_this": 15, "f_last": 1.02, "n_last": 82}, "C": {"f": 0.93, "f_this": 0.90, "n_this": 15, "f_last": 0.96, "n_last": 82}}}
    htb = {("PHI", "G", "pts"): "HashtagBasketball: 76ers allow 24.0 points a game to PGs (116th of 150, 1 the fewest), 22.6 points a game to SGs (61st of 150, 1 the fewest); shown, not scored",
           ("PHI", "C", "reb"): "HashtagBasketball: 76ers allow 11.9 rebounds a game to Cs (40th of 150, 1 the fewest); shown, not scored",
           ("PHI", "F", "pts"): "HashtagBasketball: 76ers allow 21.4 points a game to SFs (24th of 150, 1 the fewest), 22.9 points a game to PFs (88th of 150, 1 the fewest); shown, not scored",
           ("PHI", "F", "ast"): "HashtagBasketball: 76ers allow 3.9 assists a game to SFs (70th of 150, 1 the fewest), 3.1 assists a game to PFs (45th of 150, 1 the fewest); shown, not scored",
           ("NYK", "G", "pts"): "HashtagBasketball: Knicks allow 21.9 points a game to PGs (34th of 150, 1 the fewest), 22.1 points a game to SGs (42nd of 150, 1 the fewest); shown, not scored",
           ("NYK", "F", "tpm"): "HashtagBasketball: Knicks allow 2.9 threes a game to SFs (87th of 150, 1 the fewest), 2.2 threes a game to PFs (61st of 150, 1 the fewest); shown, not scored",
           ("NYK", "F", "pts"): "HashtagBasketball: Knicks allow 22.1 points a game to SFs (43rd of 150, 1 the fewest), 21.6 points a game to PFs (38th of 150, 1 the fewest); shown, not scored",
           ("NYK", "C", "reb"): "HashtagBasketball: Knicks allow 13.4 rebounds a game to Cs (125th of 150, 1 the fewest); shown, not scored"}
    out = {"PHI": (31.2, [("Joel Embiid", 31.2, "Out")], [("Andre Drummond", "Questionable")]), "NYK": (0.0, [], [("Josh Hart", "Day-To-Day")])}
    outc = {"PHI": (31.2, [("Joel Embiid", 31.2)]), "NYK": (0.0, [])}   # the club's centres out, read by the other side's bigs (28 Oct 2026)
    # the simulation on the props (26 Oct 2026): the NBA example's two profiles, the game played by nbasim at build
    # time (seeded) and read for each prop, and the matchup lever from the same profiles, as a real file carries them
    import nbasim  # noqa: E402
    prof = {"league": dict(nbasim.LEAGUE), "last": {},
            "teams": {"PHI": {"ab": "PHI", "ortg": 113.5, "drtg": 115.0, "pace": 99.5, "tov": 0.135, "trip": 0.10, "ft": 0.79, "a3": 0.41, "p3": 0.36, "p2": 0.55, "oreb": 0.27, "n": 15},
                      "NYK": {"ab": "NYK", "ortg": 118.0, "drtg": 109.0, "pace": 98.0, "tov": 0.125, "trip": 0.11, "ft": 0.80, "a3": 0.44, "p3": 0.37, "p2": 0.56, "oreb": 0.29, "n": 16}}}
    gs = slate.nba_props_game_sim(prof, "PHI", "NYK", "2026-10-26", 3000, seed=7, out={"away": [{"n": "Joel Embiid", "st": "Out", "mpg": 31.2, "ppg": 27.5}], "home": []})

    def club_match(team, opp, home_side):
        o, d = dict(prof["teams"][team]), prof["teams"][opp]
        ppp = nbasim._target(o, d, prof["league"], home_side)
        return {"f": round(ppp * 100.0 / o["ortg"], 4), "ortg": o["ortg"], "drtg": d["drtg"], "lg": round(prof["league"]["ortg"], 1), "home": bool(home_side), "b2b": False, "n": o["n"]}
    # his usage and his role (26 Oct 2026): the sigma's factor, as a real file carries them; Oubre off the bench for the harness's sake
    usage = {"Jalen Brunson": 29.5, "Karl-Anthony Towns": 26.0, "Mikal Bridges": 17.0, "OG Anunoby": 16.5, "Tyrese Maxey": 29.0, "Paul George": 22.5, "Kelly Oubre Jr.": 19.0, "Joel Embiid": 31.0}
    props = []
    for k, (name, mk, line, op, up) in enumerate(lines):
        team, pos, this, last = players[name]
        opp = "NYK" if team == "PHI" else "PHI"
        dmk = "pts" if mk == "pra" else mk
        pr = {"name": name, "mk": mk, "line": line, "op": op, "up": up, "book": "fanatics"}
        ctx = {"out_mpg": out[team][0], "out_names": out[team][1], "maybe": out[team][2], "pace": 98.75, "league_pace": 100.5, "home": team == "NYK", "pos": pos,
               "pace_team": prof["teams"][team]["pace"], "pace_opp": prof["teams"][opp]["pace"], "match": club_match(team, opp, team == "NYK"),
               "usage": usage[name], "usage_src": "this season", "starter": name != "Kelly Oubre Jr.", "start_src": "his last game this season" if name == "Kelly Oubre Jr." else "RotoWire's expected five",
               "opp_nick": slate.NBA_NICK[opp], "dvp": dvp[opp][pos], "htb": htb.get((opp, pos, dmk)),
               "opp_out_mpg": out[opp][0], "opp_out_names": out[opp][1], "opp_out_c_mpg": outc[opp][0], "opp_out_c_names": outc[opp][1], "self_out": "Out" if name == "Joel Embiid" else ""}
        proj, why = slate.props_project(pr, this, last, ctx)
        item = {"pid": "x%d" % (k + 1), "name": name, "team": team, "opp": opp, "home": team == "NYK", "pos": pos, "mk": mk, "line": line, "op": op, "up": up, "book": "fanatics",
                "books": {"fanatics": [line, op, up], "draftkings": [line + (0.5 if k % 3 == 0 else 0.0), op - 5, up + 5], "fanduel": [line, op + 2, up - 2]},
                "log": [[g["d"], g["opp"], 1 if g["home"] else 0, g["min"], slate.props_stat(g, mk), slate.props_game_factors(g, this or last, mk, 100.5, last if this else None)] for g in (this or last)[-10:]], "why": why}
        if proj:
            item.update(proj)
            item["sim"] = slate.nba_prop_sim_read(gs, team == "NYK", proj)
        props.append(item)
    props.sort(key=lambda x: (-(x.get("edge") if x.get("edge") is not None else -9), x["name"], x["mk"]))
    return [{"gid": "example", "away": "76ers", "home": "Knicks", "aab": "PHI", "hab": "NYK", "tip": None, "spread": -5.5, "total": 231.5, "pace": 98.75, "league_pace": 100.5,
             "out": {"PHI": [["Joel Embiid", 31.2, "Out"]], "NYK": []}, "sim": gs,
             "fives": {"away": {"status": "expected", "five": [["PG", "Tyrese Maxey"], ["SG", "VJ Edgecombe"], ["SF", "Paul George"], ["PF", "Kelly Oubre Jr."], ["C", "Adem Bona"]], "maybe": [["C", "Andre Drummond", "Questionable"]]},
                       "home": {"status": "confirmed", "five": [["PG", "Jalen Brunson"], ["SG", "Mikal Bridges"], ["SF", "OG Anunoby"], ["PF", "Josh Hart"], ["C", "Karl-Anthony Towns"]], "maybe": []}},
             "props": props, "unmatched": []}]


def build() -> str:
    props_js = once((ROOT / "props.engine.js").read_text(), "/*PROPS_EXAMPLE*/[]", json.dumps(props_example_games(), separators=(",", ":")), "props example")
    # the phone sheet (26 Oct 2026): the QR encoder (Kazuhiko Arase's qrcode-generator 1.4.4, MIT, vendored) and the phone block
    html = head() + engine_block() + (ROOT / "nhl.engine.js").read_text() + (ROOT / "nba.engine.js").read_text() + props_js + (ROOT / "take.engine.js").read_text() + \
        (ROOT / "vendor" / "qrcode.js").read_text() + (ROOT / "phone.engine.js").read_text() + tail()
    # the store (25 Oct 2026): the card, the props and the slate outgrew localStorage's 10 MB, so every storage call goes
    # through smStore (web/store.js), which keeps those three in IndexedDB behind a cache filled before the page's code
    # runs; the page's one closure waits for that cache. The shim itself keeps its own localStorage calls, so it goes in after
    html = every(html, "localStorage.", "smStore.", "storage shim", 14)
    html = once(html, '<script>\n(function () {\n  "use strict";\n',
                '<script>\n' + (ROOT / "store.js").read_text() + 'smStore.ready.then(function () {\n(function () {\n  "use strict";\n', "store start")
    html = once(html, '  render(); renderCard(); renderBoard(); renderCalib();\n})();\n</script>',
                '  render(); renderCard(); renderBoard(); renderCalib();\n})();\n});\n</script>', "store end")
    return html


if __name__ == "__main__":
    out = ROOT / "callsheet3.html"
    out.write_text(build())
    print(f"wrote {out} ({out.stat().st_size:,} bytes)")
