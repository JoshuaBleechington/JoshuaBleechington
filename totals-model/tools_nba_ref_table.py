"""Each NBA referee's games against the close over the backtest's two seasons.

Reads the two ledgers and the two KillerSports pages the way tools_backtest_nba
does (the same folder, the same join), grades every joined game with a crew
against its closing total, and prints a Python dict literal for slate.py's
NBA_REF_OU: {name: [games, over, under, push]}. The slate ships that table
and adds this season's record from the odds log beside it (nba_referee_tables).

    python3 tools_nba_ref_table.py /path/to/folder > table.txt

Measured 15 Oct 2026 for the user's "over the close 61-55 across 2024-25 and
2025-26" line on the Context card. Shown, not scored: the crew's own over/under
residual to date measured +0.17 (t 1.0) against the close (NBA.md).
"""
from __future__ import annotations

import collections
import sys

import tools_backtest_nba as B


def table(folder: str) -> dict[str, list[int]]:
    seasons = B.load(folder)
    out: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0, 0, 0])
    for s in seasons:
        for g in s["joined"]:
            if not g.get("off") or g.get("fa") is None or g.get("fh") is None or g.get("total") is None:
                continue
            tot, close = g["fa"] + g["fh"], g["total"]
            for name in g["off"]:
                d = out[str(name)]
                d[0] += 1
                if tot > close:
                    d[1] += 1
                elif tot < close:
                    d[2] += 1
                else:
                    d[3] += 1
    return dict(sorted(out.items()))


def main() -> int:
    folder = sys.argv[1] if len(sys.argv) > 1 else "."
    t = table(folder)
    games = sum(v[0] for v in t.values()) // 3
    print("# %d officials over %d joined games with a crew; [games, over, under, push] against the closing total" % (len(t), games))
    print("NBA_REF_OU = {")
    items = list(t.items())
    for i in range(0, len(items), 3):
        print("    " + " ".join('"%s": [%d, %d, %d, %d],' % (k, v[0], v[1], v[2], v[3]) for k, v in items[i:i + 3]))
    print("}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
