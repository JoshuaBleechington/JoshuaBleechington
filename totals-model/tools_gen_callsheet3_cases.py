"""Build web/callsheet3-cases.json from the package.

The MLB and WNBA cases are Call Sheet 2.0's, unchanged, because 3.0 carries
2.0's baseball and basketball pages verbatim and must reach the same
numbers. The NHL cases are
written here and their expectations come from totals/nhl.py, so a change to
the hockey model regenerates them without anyone hand-editing a probability.

    python3 tools_gen_callsheet3_cases.py
"""
from __future__ import annotations

import json
import pathlib

from totals import nba as NB
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
        away_p1_last10=n(i.get("ap1l10")), home_p1_last10=n(i.get("hp1l10")),
        away_xgf=n(i.get("axgf")), home_xgf=n(i.get("hxgf")), away_xga=n(i.get("axga")), home_xga=n(i.get("hxga")), league_xg=n(i.get("xglg")),
        game_month=(int(i["gdate"][5:7]) if i.get("gdate") else None),
        away_goalie_sv=n(i.get("agsv")), home_goalie_sv=n(i.get("hgsv")),
        away_goalie_shots=n(i.get("agsh")), home_goalie_shots=n(i.get("hgsh")),
        away_shots_for=n(i.get("asf")), home_shots_for=n(i.get("hsf")),
        away_pp_pct=n(i.get("app")), home_pp_pct=n(i.get("hpp")),
        away_pk_pct=n(i.get("apk")), home_pk_pct=n(i.get("hpk")),
        away_last10_total=n(i.get("al10")), home_last10_total=n(i.get("hl10")),
        h2h_total=n(i.get("h2h")), h2h_meetings=n(i.get("h2hn")),
        away_rest_days=n(i.get("arest")), home_rest_days=n(i.get("hrest")),
        away_goalie_confirmed=bool(i.get("agconf")), home_goalie_confirmed=bool(i.get("hgconf")),
        away_goalie_backup=bool(i.get("agbk")), home_goalie_backup=bool(i.get("hgbk")),
        ticket_pct_over=n(i.get("ntick")), money_pct_over=n(i.get("ncash")), opened=n(i.get("opened")),
        away_gf=n(i.get("agf")), away_ga=n(i.get("aga")), home_gf=n(i.get("hgf")), home_ga=n(i.get("hga")),
        league_gpg=n(i.get("lgg")), away_games=n(i.get("angp")), home_games=n(i.get("hngp")),
        away_en_conceded=n(i.get("aenc")), away_en_scored=n(i.get("aens")), home_en_conceded=n(i.get("henc")), home_en_scored=n(i.get("hens")))


def build_nba(i: dict):
    away, home = i.get("away") or "Away", i.get("home") or "Home"
    out = {"away": 0.0, "home": 0.0}
    try:
        lst = json.loads(i["nbaout"]) if i.get("nbaout") else {}
        ticked = set(x for x in str(i.get("nbaq") or "").split(",") if x)
        for side in ("away", "home"):
            for p in lst.get(side) or []:
                is_out = str(p.get("st", "")).lower().startswith("out") or str(p.get("id", p.get("n"))) in ticked
                if is_out and float(p.get("mpg") or 0) >= NB.REGULAR_MPG:
                    out[side] += float(p["mpg"])
    except (TypeError, ValueError):
        pass
    return NB.forecast_matchup_nba(
        away, home, total_line=float(i["line"]), over_price=n(i.get("op")), under_price=n(i.get("up")),
        home_ml=n(i.get("hml")), away_ml=n(i.get("aml")),
        spread=n(i.get("sp")), spread_home_price=n(i.get("sph")), spread_away_price=n(i.get("spa")),
        h1_line=n(i.get("h1line")), h1_over_price=n(i.get("h1op")), h1_under_price=n(i.get("h1up")),
        away_ort=n(i.get("naort")), home_ort=n(i.get("nhort")), away_drt=n(i.get("nadrt")), home_drt=n(i.get("nhdrt")),
        away_pace=n(i.get("napace")), home_pace=n(i.get("nhpace")), away_games=n(i.get("nagp")), home_games=n(i.get("nhgp")),
        league_rating=n(i.get("nlrtg")), league_pace=n(i.get("nlpace")),
        away_rest_days=n(i.get("narest")), home_rest_days=n(i.get("nhrest")),
        away_out_minutes=out["away"] or None, home_out_minutes=out["home"] or None,
        game_date=i.get("gdate"))


NBA_FULL = dict(naort="116.0", nadrt="113.5", nhort="118.2", nhdrt="109.8", napace="99.8", nhpace="97.9", nagp="20", nhgp="21")
NBA_CASES = [
    {"name": "the example card: total, half, spread and moneyline, the ratings faded",
     "inputs": dict(away="Knicks", home="Celtics", line="228.5", op="-110", up="-110", hml="-250", aml="205", sp="-6.5", sph="-110", spa="-110",
                    h1line="114.5", h1op="-110", h1up="-110", narest="0", nhrest="2", **NBA_FULL)},
    {"name": "nothing but the number: a coin flip on a whole-number line with a real push",
     "inputs": dict(away="A", home="B", line="228")},
    {"name": "a half line, prices leaning over, no ratings",
     "inputs": dict(away="Lakers", home="Warriors", line="232.5", op="-125", up="105", hml="120", aml="-140")},
    {"name": "two high-rated offences pull the line DOWN: the fade, tagged, no band",
     "inputs": dict(away="Pacers", home="Hawks", line="235.5", op="-110", up="-110", naort="121.0", nadrt="116.0", nhort="120.0", nhdrt="117.0",
                    napace="104.0", nhpace="103.0", nagp="15", nhgp="14")},
    {"name": "the same ratings past fifty games: shown, not scored",
     "inputs": dict(away="Pacers", home="Hawks", line="235.5", op="-110", up="-110", naort="121.0", nadrt="116.0", nhort="120.0", nhdrt="117.0",
                    napace="104.0", nhpace="103.0", nagp="55", nhgp="52")},
    {"name": "the same ratings on nine games: shown until ten",
     "inputs": dict(away="Pacers", home="Hawks", line="235.5", op="-110", up="-110", naort="121.0", nadrt="116.0", nhort="120.0", nhdrt="117.0",
                    napace="104.0", nhpace="103.0", nagp="9", nhgp="12")},
    {"name": "after the trade deadline: +1.0 on the line, tagged",
     "inputs": dict(away="Bulls", home="Heat", line="222.5", op="-110", up="-110", gdate="2027-03-01")},
    {"name": "the last two weeks: +2.0 on the line, tagged, with the half carrying its share",
     "inputs": dict(away="Bulls", home="Heat", line="222.5", op="-110", up="-110", gdate="2027-04-06", h1line="111.5", h1op="-115", h1up="-105")},
    {"name": "a priced spread moves fair off the number; the home favourite of ten is watched",
     "inputs": dict(away="Wizards", home="Thunder", line="226.5", op="-110", up="-110", sp="-14.5", sph="-120", spa="100", hml="-1000", aml="650")},
    {"name": "the early-season side watch: the ratings' margin twelve points off the spread in the first thirty games, a note and nothing moved",
     "inputs": dict(away="Hornets", home="Bucks", line="229.5", op="-110", up="-110", sp="-3.5", sph="-110", spa="-110",
                    naort="110.0", nadrt="118.0", nhort="118.0", nhdrt="110.0", napace="100.0", nhpace="100.0", nagp="15", nhgp="16")},
    {"name": "the same gap at thirty-five games: no watch",
     "inputs": dict(away="Hornets", home="Bucks", line="229.5", op="-110", up="-110", sp="-3.5", sph="-110", spa="-110",
                    naort="110.0", nadrt="118.0", nhort="118.0", nhdrt="110.0", napace="100.0", nhpace="100.0", nagp="35", nhgp="36")},
    {"name": "the moneyline alone gives the margin",
     "inputs": dict(away="Spurs", home="Rockets", line="224.5", op="-105", up="-115", hml="-180", aml="150")},
    {"name": "who is out: the regulars' minutes shown, not scored; the Nuggets watched",
     "inputs": dict(away="Nuggets", home="Jazz", line="236.5", op="-110", up="-110", nagp="12", nhgp="12",
                    nbaout=json.dumps({"away": [{"id": "1", "n": "Nikola Jokic", "st": "Out", "mpg": 36.2, "ppg": 28.1, "pm": 9.4, "note": "rest"},
                                                {"id": "2", "n": "Bench Guy", "st": "Out", "mpg": 8.0, "ppg": 2.0, "pm": -1.0}],
                                       "home": [{"id": "3", "n": "Lauri Markkanen", "st": "Questionable", "mpg": 33.0, "ppg": 24.0, "pm": 1.0}]}), nbaq="3")},
    {"name": "a wide hold on the total is regressed as an alternate",
     "inputs": dict(away="Magic", home="Pistons", line="214.5", op="-150", up="120", hml="-105", aml="-115")},
    {"name": "one price only: the other side is rebuilt",
     "inputs": dict(away="Kings", home="Suns", line="230.5", op="-120")},
]


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
    {"name": "special teams shown, not scored; form only is tagged, so no band",
     "inputs": dict(away="Devils", home="Islanders", line="5.5", op="-110", up="-110", app="30", hpp="30", apk="70", hpk="70",
                    al10="7.5", hl10="7.0")},
    {"name": "backup in one net: the tagged delta on the under",
     "inputs": dict(away="Kraken", home="Canucks", line="6", op="-110", up="-110", agsv="0.905", hgsv="0.912", agsh="900", hgsh="1800",
                    agbk="1", hgconf="1")},
    {"name": "a cold backup in one net: the bigger tagged delta",
     "inputs": dict(away="Kraken", home="Canucks", line="6", op="-110", up="-110", agsv="0.870", hgsv="0.912", agsh="900", hgsh="1800",
                    agbk="1", hgconf="1")},
    {"name": "backups in both nets: nothing moves",
     "inputs": dict(away="Kraken", home="Canucks", line="6", op="-110", up="-110", agsv="0.905", hgsv="0.912", agsh="900", hgsh="1800",
                    agbk="1", hgbk="1")},
    {"name": "shots and no goalies: the shot rates read as a differential",
     "inputs": dict(away="Jets", home="Wild", line="6", op="-115", up="-105", hml="-105", aml="-115", asf="34.0", hsf="33.0")},
    # Not a dead-even card on purpose: with every market at exactly 0.5 the
    # ranking between them is decided by floating-point hairs that differ
    # between the Python and the browser, which is noise, not a disagreement.
    {"name": "the puck line at +1.5 on a near pick-em, priced",
     "inputs": dict(away="Stars", home="Kings", line="5.5", op="-108", up="-112", hml="-105", aml="-115",
                    pl="1.5", plh="-240", pla="195", p1line="1.5", p1op="-102", p1up="-118")},
    {"name": "first-period form from the ledger: two hot first periods pull the period over",
     "inputs": dict(away="Avalanche", home="Senators", line="6.5", op="-110", up="-110", p1line="1.5", p1op="-130", p1up="100",
                    ap1l10="2.30", hp1l10="2.10", **FULL)},
    {"name": "expected goals: two high-event clubs, shown against the table's own league mean, not scored",
     "inputs": dict(away="Oilers", home="Devils", line="6.5", op="-110", up="-110", hml="-130", aml="110",
                    axgf="3.40", axga="3.10", hxgf="3.30", hxga="2.90", xglg="3.05", **FULL)},
    {"name": "October: no seasonal delta since 11 Oct 2026, a note only",
     "inputs": dict(away="Wild", home="Blues", line="6", op="-110", up="-110", gdate="2026-10-20")},
    {"name": "shots alone move nothing now: shown, not scored",
     "inputs": dict(away="Jets", home="Wild", line="6", op="-115", up="-105", asf="36.0", hsf="34.0")},
    {"name": "a wide moneyline hold is regressed",
     "inputs": dict(away="Lightning", home="Capitals", line="6.5", op="-110", up="-110", hml="-200", aml="150", **FULL)},
    {"name": "season scoring rates, faded: two high-scoring clubs pull the line DOWN",
     "inputs": dict(away="Oilers", home="Devils", line="6.5", op="-110", up="-110", hml="-130", aml="110",
                    agf="3.60", aga="3.20", hgf="3.40", hga="3.10", lgg="6.10", angp="12", hngp="11", **FULL)},
    {"name": "scoring rates on four games: shown, not scored until five",
     "inputs": dict(away="Kraken", home="Canucks", line="6", op="-110", up="-110",
                    agf="3.60", aga="3.20", hgf="3.40", hga="3.10", lgg="6.10", angp="4", hngp="11")},
    {"name": "empty-net habits: two clubs that trail late push the line UP, tagged",
     "inputs": dict(away="Sabres", home="Ducks", line="6", op="-110", up="-110", hml="-115", aml="-105",
                    aenc="0.55", aens="0.25", henc="0.50", hens="0.30", angp="20", hngp="18", **FULL)},
]


def main() -> None:
    cases = [c for c in json.loads(SRC.read_text()) if c["sport"] in ("MLB", "WNBA")]
    for c in cases:
        c.pop("expect", None)
    # every hockey case carries a date, because October carries a delta: November unless the case says
    cases.extend({"sport": "NHL", "name": c["name"], "inputs": dict({"gdate": "2026-11-15"}, **c["inputs"])} for c in NHL_CASES)
    # every basketball case carries a date, because the stage of the season carries a delta: December unless the case says
    cases.extend({"sport": "NBA", "name": c["name"], "inputs": dict({"gdate": "2026-12-10"}, **c["inputs"])} for c in NBA_CASES)
    from tools_gen_callsheet2_cases import build as build_mlb
    for c in cases:
        m = build_nhl(c["inputs"]) if c["sport"] == "NHL" else build_nba(c["inputs"]) if c["sport"] == "NBA" else build_mlb(c)
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
    by = {sp: sum(1 for c in cases if c["sport"] == sp) for sp in ("MLB", "NHL", "NBA", "WNBA")}
    print(f"{len(cases)} cases written ({by['MLB']} MLB, {by['NHL']} NHL, {by['NBA']} NBA, {by['WNBA']} WNBA)")


if __name__ == "__main__":
    main()
