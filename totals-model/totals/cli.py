"""Command line front end.

    python -m totals mlb  examples/mlb_slate.json
    python -m totals wnba examples/wnba_slate.json --min-ev 0.02
    python -m totals mlb  game.json --format json
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from . import DEFAULT_MAX_STAKE_PCT, DEFAULT_MODEL_WEIGHT, run_slate


def _load(path: str) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, dict):
        # Either a single game or a {"games": [...]} wrapper.
        data = data.get("games", [data])
    if not isinstance(data, list):
        raise ValueError("Input must be a game object or a list of game objects")
    return data


def _format_row(r: dict[str, Any]) -> str:
    head = f"{r['matchup']:<28} model {r['model_total']:>6.2f}"
    if "line" not in r:
        return head + "   (no market posted)"
    tag = "  *" if r["ev_per_unit"] > 0 else "   "
    return (
        f"{head}  line {r['line']:>6}  proj {r['projected_total']:>6.2f}  "
        f"{r['best_side']:<5} {r['best_side_odds']:>6}  "
        f"win% {100 * r['best_side_prob']:>5.1f}  "
        f"EV {100 * r['ev_per_unit']:>+6.2f}%  "
        f"stake {r['kelly_stake_pct']:>5.2f}%{tag}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="totals", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("sport", choices=["mlb", "wnba"])
    parser.add_argument("file", help='JSON file: one game, a list of games, or {"games": [...]}')
    parser.add_argument(
        "--min-ev",
        type=float,
        default=None,
        help="only show plays with at least this EV per unit, e.g. 0.02 for 2%%",
    )
    parser.add_argument(
        "--kelly", type=float, default=0.25, help="fractional Kelly multiplier (default 0.25)"
    )
    parser.add_argument(
        "--model-weight",
        type=float,
        default=DEFAULT_MODEL_WEIGHT,
        help="how far to trust the model over the posted line, 0-1 (default %(default)s)",
    )
    parser.add_argument(
        "--max-stake",
        type=float,
        default=DEFAULT_MAX_STAKE_PCT,
        help="cap on a single stake, %% of bankroll (default %(default)s)",
    )
    parser.add_argument("--format", choices=["table", "json"], default="table")
    args = parser.parse_args(argv)

    games = _load(args.file)
    results = run_slate(args.sport, games, args.kelly, args.model_weight, args.max_stake)

    if args.min_ev is not None:
        results = [r for r in results if r.get("ev_per_unit", -1) >= args.min_ev]

    if args.format == "json":
        print(json.dumps(results, indent=2))
        return 0

    if not results:
        print("No games cleared the filter.")
        return 0

    print(f"\n{args.sport.upper()} totals -- {len(results)} game(s), model weight {args.model_weight}\n")
    for r in results:
        print("  " + _format_row(r))
    print("\n  * = positive expected value at the posted price\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
