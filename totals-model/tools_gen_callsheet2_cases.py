"""Build web/callsheet2-cases.json from totals/callsheet2.py.

Every Call Sheet #1 fixture is reused as a Call Sheet 2.0 fixture with a board
of side-market prices added on top, plus a handful written for this sheet.
The inputs are kept; the expectations are regenerated from the package, so a
model change updates the fixtures without anyone hand-editing a probability.

    python3 tools_gen_callsheet2_cases.py
"""
from __future__ import annotations

import json
import pathlib

from totals import callsheet2 as C

HERE = pathlib.Path(__file__).parent
SRC = HERE / "web" / "fullgame-cases.json"
OUT = HERE / "web" / "callsheet2-cases.json"


def n(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def total_kwargs(sport, i):
    if sport == "MLB":
        return dict(
            away_starter_era=n(i.get("aera")), home_starter_era=n(i.get("hera")),
            away_starter_ip=n(i.get("aip")), home_starter_ip=n(i.get("hip")),
            away_rpg=n(i.get("arpg")), home_rpg=n(i.get("hrpg")),
            away_bullpen_era=n(i.get("abp")), home_bullpen_era=n(i.get("hbp")),
            away_last10_total=n(i.get("al10")), home_last10_total=n(i.get("hl10")),
            h2h_total=n(i.get("h2h")), h2h_meetings=n(i.get("h2hn")),
            park_factor=n(i.get("pf")), wind_mph=n(i.get("mph")),
            wind_direction=i.get("dir") or None, temp_f=n(i.get("temp")),
            dome=bool(i.get("dome")), ticket_pct_over=n(i.get("tick")),
            money_pct_over=n(i.get("cash")), opened=n(i.get("opened")))
    return dict(
        away_pace=n(i.get("apace")), home_pace=n(i.get("hpace")),
        away_off_rating=n(i.get("aort")), home_off_rating=n(i.get("hort")),
        away_def_rating=n(i.get("adrt")), home_def_rating=n(i.get("hdrt")),
        away_rest_days=n(i.get("arest")), home_rest_days=n(i.get("hrest")),
        away_last5_total=n(i.get("al5")), home_last5_total=n(i.get("hl5")),
        playoff=bool(i.get("playoff")))


def tt_kwargs(i):
    return dict(away_tt_line=n(i.get("atl")), away_tt_over=n(i.get("atop")), away_tt_under=n(i.get("atup")),
                home_tt_line=n(i.get("htl")), home_tt_over=n(i.get("htop")), home_tt_under=n(i.get("htup")))


def build(case):
    i = case["inputs"]
    away, home = i.get("away") or "Away", i.get("home") or "Home"
    if case["sport"] == "MLB":
        return C.forecast_matchup_mlb(
            away, home, total_line=float(i["line"]), over_price=n(i.get("op")),
            under_price=n(i.get("up")), home_ml=n(i.get("hml")), away_ml=n(i.get("aml")),
            run_line=n(i.get("rl")), rl_home_price=n(i.get("rlh")), rl_away_price=n(i.get("rla")),
            f5_line=n(i.get("f5line")), f5_over_price=n(i.get("f5op")), f5_under_price=n(i.get("f5up")),
            **tt_kwargs(i), **total_kwargs("MLB", i))
    return C.forecast_matchup_wnba(
        away, home, total_line=float(i["line"]), over_price=n(i.get("op")),
        under_price=n(i.get("up")), home_ml=n(i.get("hml")), away_ml=n(i.get("aml")),
        spread=n(i.get("sp")), spread_home_price=n(i.get("sph")), spread_away_price=n(i.get("spa")),
        **tt_kwargs(i), **total_kwargs("WNBA", i))


#: Boards laid over the #1 fixtures, cycled so every shape gets covered:
#: full board, moneyline only, no sides at all, dog at home, whole-number lines.
MLB_BOARDS = [
    dict(hml="-150", aml="130", rl="-1.5", rlh="120", rla="-140", f5line="3.5", f5op="-115", f5up="-105",
         atl="2.5", atop="-105", atup="-115", htl="3.5", htop="-120", htup="100"),
    dict(hml="-120", aml="100"),
    dict(),
    dict(hml="140", aml="-160", rl="1.5", rlh="-170", rla="145", f5line="4.5", f5op="-110", f5up="-110"),
    dict(hml="-110", aml="-110", rl="-1", rlh="-105", rla="-115", f5line="4", f5op="-120", f5up="100",
         atl="4", atop="-110", atup="-110", htl="4.5"),
    dict(hml="-250", aml="210", f5line="5.5", f5op="100", f5up="-120"),
]
WNBA_BOARDS = [
    dict(hml="-190", aml="160", sp="-4.5", sph="-110", spa="-110",
         atl="77.5", atop="-110", atup="-110", htl="83.5", htop="-115", htup="-105"),
    dict(sp="-2", sph="-115", spa="-105"),
    dict(hml="-135", aml="115"),
    dict(),
    dict(hml="120", aml="-140", sp="3.5", sph="-120", spa="100"),
]

EXTRA = [
    {"sport": "MLB", "name": "heavy favourite: 72% to hit and a losing bet",
     "inputs": {"away": "Rockies", "home": "Dodgers", "line": "8.5", "op": "-110", "up": "-110",
                "hml": "-300", "aml": "240", "rl": "-1.5", "rlh": "-130", "rla": "110"}},
    {"sport": "MLB", "name": "the side picked is the better price, not the likelier side",
     "inputs": {"away": "A", "home": "B", "line": "8.5", "op": "-160", "up": "130", "hml": "-110", "aml": "-110"}},
    {"sport": "MLB", "name": "no prices anywhere: probabilities, no ranking",
     "inputs": {"away": "A", "home": "B", "line": "8.5"}},
    {"sport": "MLB", "name": "team totals need the moneyline",
     "inputs": {"away": "A", "home": "B", "line": "8.5", "op": "-110", "up": "-110",
                "atl": "4.5", "atop": "-110", "atup": "-110"}},
    {"sport": "WNBA", "name": "pick-em spread is a coin-flip moneyline",
     "inputs": {"away": "A", "home": "B", "line": "165.5", "op": "-110", "up": "-110",
                "sp": "0", "sph": "-110", "spa": "-110", "hml": "-105", "aml": "-115"}},
]


def main() -> None:
    base = json.loads(SRC.read_text())
    cases = []
    mi = wi = 0
    for c in base:
        inputs = dict(c["inputs"])
        if c["sport"] == "MLB":
            inputs.update(MLB_BOARDS[mi % len(MLB_BOARDS)]); mi += 1
        else:
            inputs.update(WNBA_BOARDS[wi % len(WNBA_BOARDS)]); wi += 1
        cases.append({"sport": c["sport"], "name": c["name"], "inputs": inputs})
    cases.extend({"sport": e["sport"], "name": e["name"], "inputs": dict(e["inputs"])} for e in EXTRA)
    for c in cases:
        m = build(c)
        c["expect"] = {
            "lam_home": None if m.lam_home is None else round(m.lam_home, 8),
            "lam_away": None if m.lam_away is None else round(m.lam_away, 8),
            "projected": round(m.total.projected, 8),
            "markets": [{
                "key": mk.key, "pick": mk.pick, "side": mk.side, "p": round(mk.p, 8),
                "p_push": round(mk.p_push, 8), "price": mk.price,
                "edge": None if mk.edge is None else round(mk.edge, 8),
                "fair": round(mk.fair, 4), "anchored": mk.anchored, "band": mk.band,
            } for mk in m.ranked()],
        }
    OUT.write_text(json.dumps(cases, indent=2) + "\n")
    print(f"{len(cases)} cases written")


if __name__ == "__main__":
    main()
