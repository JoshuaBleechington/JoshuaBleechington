"""Build web/callsheet3-cases.json from the package.

The MLB cases are Call Sheet 2.0's, unchanged, because 3.0 carries 2.0's
baseball page verbatim and must reach the same numbers. The NHL cases are
written here and their expectations come from totals/nhl.py, so a change to
the hockey model regenerates them without anyone hand-editing a probability.

    python3 tools_gen_callsheet3_cases.py
"""
from __future__ import annotations

import json
import pathlib

from totals import nhl as N

HERE = pathlib.Path(__file__).parent
SRC = HERE / "web" / "callsheet2-cases.json"
OUT = HERE / "web" / "callsheet3-cases.json"


def n(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def build_nhl(i: dict):
    away, home = i.get("away") or "Away", i.get("home") or "Home"
    return N.forecast_matchup_nhl(
        away, home, total_line=float(i["line"]), over_price=n(i.get("op")), under_price=n(i.get("up")),
        home_ml=n(i.get("hml")), away_ml=n(i.get("aml")),
        puck_line=n(i.get("pl")), pl_home_price=n(i.get("plh")), pl_away_price=n(i.get("pla")),
        p1_line=n(i.get("p1line")), p1_over_price=n(i.get("p1op")), p1_under_price=n(i.get("p1up")),
        away_goalie_sv=n(i.get("agsv")), home_goalie_sv=n(i.get("hgsv")),
        away_goalie_shots=n(i.get("agsh")), home_goalie_shots=n(i.get("hgsh")),
        away_shots_for=n(i.get("asf")), home_shots_for=n(i.get("hsf")),
        away_pp_pct=n(i.get("app")), home_pp_pct=n(i.get("hpp")),
        away_pk_pct=n(i.get("apk")), home_pk_pct=n(i.get("hpk")),
        away_last10_total=n(i.get("al10")), home_last10_total=n(i.get("hl10")),
        h2h_total=n(i.get("h2h")), h2h_meetings=n(i.get("h2hn")),
        away_rest_days=n(i.get("arest")), home_rest_days=n(i.get("hrest")),
        away_goalie_confirmed=bool(i.get("agconf")), home_goalie_confirmed=bool(i.get("hgconf")),
        ticket_pct_over=n(i.get("tick")), money_pct_over=n(i.get("cash")), opened=n(i.get("opened")))


FULL = dict(agsv="0.912", hgsv="0.921", agsh="1400", hgsh="1900", asf="31.2", hsf="33.4",
            app="22.1", hpp="24.8", apk="80.2", hpk="78.1", al10="5.9", hl10="6.4", h2h="6.3", h2hn="3")
NHL_CASES = [
    {"name": "the example card: full board, two goalies, everything in",
     "inputs": dict(away="Rangers", home="Bruins", line="6", op="-110", up="-110", hml="-150", aml="130",
                    pl="-1.5", plh="180", pla="-220", p1line="1.5", p1op="-120", p1up="100", arest="0", hrest="2", **FULL)},
    {"name": "nothing but the number: a coin flip on a whole-number line with a real push",
     "inputs": dict(away="A", home="B", line="6")},
    {"name": "a half line, prices leaning over, no goalies",
     "inputs": dict(away="Oilers", home="Flames", line="6.5", op="-125", up="105", hml="110", aml="-130")},
    {"name": "a hot goalie on a short sample is shrunk; the under still leads",
     "inputs": dict(away="Kraken", home="Canucks", line="5.5", op="-110", up="-110", hml="-140", aml="120",
                    agsv="0.935", hgsv="0.905", agsh="300", hgsh="1600", asf="29.0", hsf="31.0", agconf="1", hgconf="1")},
    {"name": "a cold goalie against a heavy shot team: the over, with the first period reading it",
     "inputs": dict(away="Sharks", home="Avalanche", line="6.5", op="-105", up="-115", hml="-260", aml="215",
                    pl="-1.5", plh="105", pla="-125", p1line="1.5", p1op="-135", p1up="110",
                    agsv="0.885", hgsv="0.915", agsh="900", hgsh="1700", asf="27.5", hsf="35.0")},
    {"name": "home dog: the default puck line flips to +1.5",
     "inputs": dict(away="Panthers", home="Blackhawks", line="6", op="-110", up="-110", hml="150", aml="-180")},
    {"name": "special teams and form only: tagged, so no band",
     "inputs": dict(away="Devils", home="Islanders", line="5.5", op="-110", up="-110", app="30", hpp="30", apk="70", hpk="70",
                    al10="7.5", hl10="7.0")},
    {"name": "shots and no goalies: the shot rates read as a differential",
     "inputs": dict(away="Jets", home="Wild", line="6", op="-115", up="-105", hml="-105", aml="-115", asf="34.0", hsf="33.0")},
    # Not a dead-even card on purpose: with every market at exactly 0.5 the
    # ranking between them is decided by floating-point hairs that differ
    # between the Python and the browser, which is noise, not a disagreement.
    {"name": "the puck line at +1.5 on a near pick-em, priced",
     "inputs": dict(away="Stars", home="Kings", line="5.5", op="-108", up="-112", hml="-105", aml="-115",
                    pl="1.5", plh="-240", pla="195", p1line="1.5", p1op="-105", p1up="-115")},
    {"name": "a wide moneyline hold is regressed",
     "inputs": dict(away="Lightning", home="Capitals", line="6.5", op="-110", up="-110", hml="-200", aml="150", **FULL)},
]


def main() -> None:
    cases = [c for c in json.loads(SRC.read_text()) if c["sport"] == "MLB"]
    for c in cases:
        c.pop("expect", None)
    cases.extend({"sport": "NHL", "name": c["name"], "inputs": dict(c["inputs"])} for c in NHL_CASES)
    from tools_gen_callsheet2_cases import build as build_mlb
    for c in cases:
        m = build_mlb(c) if c["sport"] == "MLB" else build_nhl(c["inputs"])
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
    print(f"{len(cases)} cases written ({sum(1 for c in cases if c['sport'] == 'NHL')} NHL)")


if __name__ == "__main__":
    main()
