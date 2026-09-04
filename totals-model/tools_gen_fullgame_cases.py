"""Regenerate web/fullgame-cases.json expectations from totals/fullgame.py.

Reads the existing case list, recomputes every `expect` block from the package,
and writes it back. Keeping the inputs and regenerating only the expectations
means a model change updates the fixtures without anyone hand-editing a
probability, which is how a fixture quietly stops testing anything.

    python3 tools_gen_fullgame_cases.py
"""
import json
import pathlib

from totals import fullgame as F

PATH = pathlib.Path(__file__).parent / "web" / "fullgame-cases.json"


def n(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def build(case):
    i, ln = case["inputs"], float(case["inputs"]["line"])
    name = f"{i.get('away') or 'A'} @ {i.get('home') or 'B'}"
    if case["sport"] == "MLB":
        return F.forecast_mlb(
            name, ln, over_price=n(i.get("op")), under_price=n(i.get("up")),
            away_starter_era=n(i.get("aera")), home_starter_era=n(i.get("hera")),
            away_rpg=n(i.get("arpg")), home_rpg=n(i.get("hrpg")),
            away_bullpen_era=n(i.get("abp")), home_bullpen_era=n(i.get("hbp")),
            away_last10_total=n(i.get("al10")), home_last10_total=n(i.get("hl10")),
            h2h_total=n(i.get("h2h")), h2h_meetings=n(i.get("h2hn")),
            park_factor=n(i.get("pf")), wind_mph=n(i.get("mph")),
            wind_direction=i.get("dir") or None, temp_f=n(i.get("temp")),
            dome=bool(i.get("dome")), ticket_pct_over=n(i.get("tick")),
            money_pct_over=n(i.get("cash")), opened=n(i.get("opened")))
    return F.forecast_wnba(
        name, ln, over_price=n(i.get("op")), under_price=n(i.get("up")),
        away_last10_total=n(i.get("wal10")), home_last10_total=n(i.get("whl10")),
        h2h_total=n(i.get("wh2h")), h2h_meetings=n(i.get("wh2hn")),
        away_starters_out=int(n(i.get("aout")) or 0),
        home_starters_out=int(n(i.get("hout")) or 0),
        away_leading_scorer_out=bool(i.get("alead")),
        home_leading_scorer_out=bool(i.get("hlead")),
        opened=n(i.get("opened")))


def main() -> None:
    cases = json.loads(PATH.read_text())
    for c in cases:
        f = build(c)
        c["expect"] = {
            "side": f.side, "band": f.band, "band_ungated": f.band_ungated,
            "p_side": round(f.p_side, 8), "p_resolved": round(f.p_resolved, 8),
            "p_corroborated": round(f.p_corroborated, 8),
            "p_push": round(f.p_push, 8), "projected": round(f.projected, 8),
            "projected_core": round(f.projected_corroborated, 8),
            "fair": round(f.fair_price, 4),
            "estimates": len(f.estimates), "deltas": len(f.deltas),
        }
    PATH.write_text(json.dumps(cases, indent=2) + "\n")
    print(f"{len(cases)} cases regenerated")


if __name__ == "__main__":
    main()
