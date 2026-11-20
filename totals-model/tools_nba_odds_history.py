"""What the full-game lines history says (26 Oct 2026): the sharp line and the move.

    python3 tools_nba_odds_history.py LEDGER.json odds-history-NBA-SEASON.json [more pairs...]

Two snapshots a game day, noon and 6:30 pm Eastern, every book with the
total, the spread and the moneyline, Pinnacle among them. Asked here:

  the shade: Pinnacle's closing total less the US books' mean, against the
             final's residual on the books' mean (does the game land on
             Pinnacle's side?);
  the move:  the close less the earliest snapshot the file holds for the
             game (the opener), against the final's residual on the close
             (does a total that moved keep going, or come back?);
  the same two for the spread, on the home margin.

Slope, t and the record each way, per season. A sharp shade or a move that
predicts the residual is a lever; one that does not stays a chip.
"""
import json
import sys
from collections import defaultdict

from tools_backtest_nba import ols, avg, sd

US = ("fanatics", "betmgm", "draftkings", "fanduel", "caesars", "espnbet", "betrivers")


def load_ledger(path):
    return {(g["date"], g.get("an"), g.get("hn")): g for g in json.load(open(path))["games"] if g.get("fa") is not None}


def consensus(snap, idx):
    xs = [row[idx] for b, row in snap.items() if b in US and len(row) > idx and row[idx] is not None]
    return avg(xs) if xs else None


def main(argv):
    if len(argv) < 2 or len(argv) % 2:
        print(__doc__)
        return 2
    for i in range(0, len(argv), 2):
        led = load_ledger(argv[i])
        hist = json.load(open(argv[i + 1]))
        season = hist.get("season")
        shade_t, move_t, shade_s, move_s = [], [], [], []
        joined = 0
        for k, g in hist["games"].items():
            lg = led.get((g["gdate"], g["away"], g["home"]))
            if not lg or not g.get("snaps"):
                continue
            stamps = sorted(g["snaps"])
            # the close: the last snapshot before tip; the opener: the first the file holds
            pre = [s for s in stamps if s < g["start"]]
            if not pre:
                continue
            close, first = g["snaps"][pre[-1]], g["snaps"][stamps[0]]
            tot_c, sp_c = consensus(close, 0), consensus(close, 5)
            tot_o, sp_o = consensus(first, 0), consensus(first, 5)
            final, margin = lg["fa"] + lg["fh"], lg["fh"] - lg["fa"]
            joined += 1
            pin = close.get("pinnacle")
            if tot_c is not None and pin and pin[0] is not None:
                shade_t.append((pin[0] - tot_c, final - tot_c))
            if tot_c is not None and tot_o is not None and stamps[0] != pre[-1]:
                move_t.append((tot_c - tot_o, final - tot_c))
            if sp_c is not None and pin and len(pin) > 5 and pin[5] is not None:
                shade_s.append((pin[5] - sp_c, margin + sp_c))     # a home spread is negative when favoured; the residual is the home cover margin
            if sp_c is not None and sp_o is not None and stamps[0] != pre[-1]:
                move_s.append((sp_c - sp_o, margin + sp_c))
        print("%s: %d games joined to the ledger" % (season, joined))
        for name, rows, what in (("TOTAL, Pinnacle's shade", shade_t, "over"), ("TOTAL, the move opener to close", move_t, "over"),
                                 ("SPREAD, Pinnacle's shade", shade_s, "home cover"), ("SPREAD, the move opener to close", move_s, "home cover")):
            if len(rows) < 30:
                continue
            xs, ys = [r[0] for r in rows], [r[1] for r in rows]
            o = ols(xs, ys)
            big = [r for r in rows if abs(r[0]) >= (1.0 if "shade" in name else 2.0)]
            w = sum(1 for r in big if (r[1] > 0) == (r[0] > 0))
            l = sum(1 for r in big if (r[1] < 0) == (r[0] > 0))
            print("  %-34s n %4d  lean sd %.2f  slope of the residual on it %+.3f (t %.1f)  with the lean %d-%d when it is %s+ (%s side)" % (
                name, len(rows), sd(xs), o[0], o[1], w, l, "1" if "shade" in name else "2", what))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
