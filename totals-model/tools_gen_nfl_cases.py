"""Regenerates the `expect` block of web/nfl-cases.json from totals/nfl.py.

Only the expectations are recomputed; the inputs are hand-written and stay put.
A model change therefore never means hand-editing a probability into a test.

    python tools_gen_nfl_cases.py
"""
from __future__ import annotations

import json
from pathlib import Path

from totals import nfl

PATH = Path(__file__).parent / "web" / "nfl-cases.json"


def n(v):
    return None if v in (None, "") else float(v)


def build(case):
    i = case["inputs"]
    return nfl.forecast_nfl(
        matchup=f"{i.get('away', 'Away')} @ {i.get('home', 'Home')}",
        spread=n(i.get("line")),
        home_price=n(i.get("op")), away_price=n(i.get("up")),
        home_net_ppg=n(i.get("hnet")), away_net_ppg=n(i.get("anet")),
        games_played=n(i.get("gp")),
        home_qb_out=bool(i.get("hqb")), away_qb_out=bool(i.get("aqb")),
        opened=n(i.get("nopened")))


def main() -> None:
    cases = json.loads(PATH.read_text())
    for c in cases:
        f = build(c)
        c["expect"] = {
            "side": f.side, "band": f.band,
            "p_resolved": round(f.p_resolved, 8),
            "p_push": round(f.p_push, 8),
            "projected": round(f.projected, 8),
            "expected_margin": round(f.expected_margin, 8),
            "fair": round(f.fair_price, 4),
            "half_point_cents": round(f.half_point["cents"], 4),
            "estimates": len(f.estimates),
        }
    PATH.write_text(json.dumps(cases, indent=2) + "\n")
    print(f"{len(cases)} NFL cases regenerated")


if __name__ == "__main__":
    main()
