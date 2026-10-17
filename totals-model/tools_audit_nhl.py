"""Audit the hockey book's inputs against results, from a Call Sheet 3.0 backup.

    python3 tools_audit_nhl.py path/to/callsheet3-backup.json

For every graded NHL row, the residual is the final total minus the market
anchor (fair_total of the stored line and prices). Each input is then asked
one question, the one the MLB weights were earned on: when it said "over" --
when its estimate sat above the anchor -- did the game go over the anchor more
often than when it said "under"? The table prints, per input, how many rows
carried it, the record of its sign against the residual's sign, and the mean
residual on each side. It is a reading tool: nothing here changes a weight,
and under 100 rows it prints a warning that says so.
"""
from __future__ import annotations

import json
import sys

from totals import nhl as N
from totals.fullgame import fair_total


def n(v):
    try:
        return None if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return None


def inputs_for(i):
    return dict(
        over_price=n(i.get("op")), under_price=n(i.get("up")),
        away_goalie_sv=n(i.get("agsv")), home_goalie_sv=n(i.get("hgsv")),
        away_goalie_shots=n(i.get("agsh")), home_goalie_shots=n(i.get("hgsh")),
        away_shots_for=n(i.get("asf")), home_shots_for=n(i.get("hsf")),
        away_pp_pct=n(i.get("app")), home_pp_pct=n(i.get("hpp")),
        away_pk_pct=n(i.get("apk")), home_pk_pct=n(i.get("hpk")),
        away_xgf=n(i.get("axgf")), home_xgf=n(i.get("hxgf")), away_xga=n(i.get("axga")), home_xga=n(i.get("hxga")),
        league_xg=n(i.get("xglg")),
        away_last10_total=n(i.get("al10")), home_last10_total=n(i.get("hl10")),
        h2h_total=n(i.get("h2h")), h2h_meetings=n(i.get("h2hn")),
        away_rest_days=n(i.get("arest")), home_rest_days=n(i.get("hrest")),
        ticket_pct_over=n(i.get("ntick")), money_pct_over=n(i.get("ncash")), opened=n(i.get("opened")))


def main(path):
    d = json.load(open(path, encoding="utf-8"))
    rows = []
    for r in d.get("card", []):
        if r.get("sport") != "NHL":
            continue
        f, i = r.get("finals") or {}, r.get("inputs") or {}
        try:
            total = int(f["fa"]) + int(f["fh"])
            line = float(i["line"])
        except (KeyError, TypeError, ValueError):
            continue
        anchor, _ = fair_total("NHL", line, n(i.get("op")), n(i.get("up")))
        fc = N.forecast_nhl(r.get("matchup", "?"), line, **inputs_for(i))
        rows.append((r, total, anchor, fc))
    print(f"{len(rows)} graded NHL rows in {path}")
    if not rows:
        return
    if len(rows) < 100:
        print(f"UNDER 100 ROWS: read everything below as noise; one standard error on a hit rate is "
              f"{100 / (2 * len(rows) ** 0.5):.0f} points at this size.")
    names = []
    for _, _, _, fc in rows:
        for e in fc.estimates:
            if e.name != "Market" and e.name not in names:
                names.append(e.name)
    print(f"\n{'input':24s} {'rows':>5s} {'said over: W-L':>16s} {'said under: W-L':>16s} {'resid when over':>16s} {'resid when under':>17s}")
    for name in names:
        ow = ol = uw = ul = 0
        ro, ru = [], []
        for r, total, anchor, fc in rows:
            e = next((x for x in fc.estimates if x.name == name), None)
            if e is None:
                continue
            said = e.total - anchor
            resid = total - anchor
            if abs(said) < 1e-9 or abs(resid) < 1e-9:
                continue
            if said > 0:
                ro.append(resid)
                if resid > 0:
                    ow += 1
                else:
                    ol += 1
            else:
                ru.append(resid)
                if resid < 0:
                    uw += 1
                else:
                    ul += 1
        k = ow + ol + uw + ul
        mo = sum(ro) / len(ro) if ro else float("nan")
        mu = sum(ru) / len(ru) if ru else float("nan")
        print(f"{name:24s} {k:5d} {f'{ow}-{ol}':>16s} {f'{uw}-{ul}':>16s} {mo:+16.2f} {mu:+17.2f}")
    # the model as a whole
    pw = pl = 0
    for r, total, anchor, fc in rows:
        said, resid = fc.projected - anchor, total - anchor
        if abs(said) < 1e-9 or abs(resid) < 1e-9:
            continue
        if (said > 0) == (resid > 0):
            pw += 1
        else:
            pl += 1
    print(f"\nthe blend's lean against the residual: {pw}-{pl}")
    resids = [total - anchor for _, total, anchor, _ in rows]
    m = sum(resids) / len(resids)
    sd = (sum((x - m) ** 2 for x in resids) / max(1, len(resids) - 1)) ** 0.5
    print(f"residual: mean {m:+.2f}, sd {sd:.2f} (the engine assumes {N.RESIDUAL_SD:.2f})")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1])
