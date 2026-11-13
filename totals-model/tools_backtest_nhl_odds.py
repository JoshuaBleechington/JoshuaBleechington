"""Measure the odds history against the season ledger.

    python3 tools_backtest_nhl_odds.py FOLDER SEASON [CLOSES.html]
    python3 tools_backtest_nhl_odds.py --selftest

FOLDER holds odds-history-NHL-SEASON.json (slate.py odds-history --season,
the books' totals at two moments a day) and nhl-ledger-SEASON.json (slate.py
nhl-ledger --season, the finals). CLOSES.html, optional, is KillerSports'
closing-total page (tools_backtest_nhl.py) to check the feed's close
against. Per game: the OPENER is the first snapshot before the start and
the CLOSE the last, for the retail book (the first in the file's book list
that priced it, Pinnacle never) and for Pinnacle. Prints the share of lines
that moved and which way; the over's record when the line rose and the
under's when it fell, at the opener's number and at the close's; the over's
record when Pinnacle sat above the retail number and the under's when
below, at the opener and at the close; Pinnacle's juiced side against the
final; and the opener's error against the final beside the close's. Every
record is W-L-P with the win share of decided games; the market needs
52.4% at -110. Written 13 Oct 2026 for the history mode; not yet run on a
season (the user pulls the file). CALLSHEET3.md takes the table.
"""
import json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tools_backtest_nhl import NICK, ks_rows   # noqa: E402

SHARP = "pinnacle"
MOVE = 0.5          # a half goal or more is a move; a quarter-goal shade is not
GAP = 0.5           # the sharp book a half goal or more off the retail number


def retail_book(books, snap):
    for b in books:
        if b != SHARP and b in snap and snap[b][0] is not None:
            return b
    for b in snap:
        if b != SHARP and snap[b][0] is not None:
            return b
    return None


def open_close(game, books):
    """(opener, close) as {book, line, op, up, sharp: [line, op, up] or None} from the
    snapshots before the start, or (None, None)."""
    snaps = sorted((ts, s) for ts, s in (game.get("snaps") or {}).items() if ts < (game.get("start") or "9"))
    rows = []
    for ts, s in snaps:
        b = retail_book(books, s)
        if not b:
            continue
        sh = s.get(SHARP)
        rows.append({"at": ts, "book": b, "line": float(s[b][0]), "op": s[b][1], "up": s[b][2],
                     "sharp": [float(sh[0]), sh[1], sh[2]] if sh and sh[0] is not None else None})
    return (rows[0], rows[-1]) if rows else (None, None)


def result(side, line, total):
    if abs(total - line) < 1e-9:
        return "P"
    return "W" if ((total > line) == (side == "over")) else "L"


class Rec:
    def __init__(self):
        self.w = self.l = self.p = 0

    def add(self, r):
        if r == "W":
            self.w += 1
        elif r == "L":
            self.l += 1
        else:
            self.p += 1

    def text(self):
        n = self.w + self.l
        return "%d-%d-%d (%s on %d)" % (self.w, self.l, self.p, ("%.1f%%" % (100.0 * self.w / n)) if n else "-", n + self.p)


def measure(hist, led, closes=None):
    books = hist.get("books") or []
    byk = {(g["date"], NICK.get(g["away"], g["away"]), NICK.get(g["home"], g["home"])): g for g in led.get("games") or [] if g.get("fa") is not None}
    ks = {(r["date"], r["away"], r["home"]): r["total"] for r in (closes or [])}
    out = {"games": 0, "joined": 0, "both": 0, "up": 0, "down": 0, "flat": 0,
           "over_up_open": Rec(), "over_up_close": Rec(), "under_down_open": Rec(), "under_down_close": Rec(),
           "sharp_n_open": 0, "sharp_n_close": 0, "over_sharp_above_open": Rec(), "under_sharp_below_open": Rec(),
           "over_sharp_above_close": Rec(), "under_sharp_below_close": Rec(), "sharp_lean": Rec(), "sharp_lean_n": 0,
           "err_open": 0.0, "err_close": 0.0, "err_sharp_close": 0.0, "err_sharp_n": 0, "ks_same": 0, "ks_n": 0}
    for g in hist.get("games", {}).values():
        out["games"] += 1
        f = byk.get((g["gdate"], g["away"], g["home"]))
        if not f:
            continue
        o, c = open_close(g, books)
        if not o:
            continue
        out["joined"] += 1
        tot = f["fa"] + f["fh"]
        out["err_open"] += abs(o["line"] - tot)
        out["err_close"] += abs(c["line"] - tot)
        k = (g["gdate"], g["away"], g["home"])
        if k in ks:
            out["ks_n"] += 1
            out["ks_same"] += 1 if abs(ks[k] - c["line"]) < 1e-9 else 0
        if c["at"] != o["at"]:
            out["both"] += 1
            d = c["line"] - o["line"]
            if d >= MOVE:
                out["up"] += 1
                out["over_up_open"].add(result("over", o["line"], tot))
                out["over_up_close"].add(result("over", c["line"], tot))
            elif d <= -MOVE:
                out["down"] += 1
                out["under_down_open"].add(result("under", o["line"], tot))
                out["under_down_close"].add(result("under", c["line"], tot))
            else:
                out["flat"] += 1
        for tag, row in (("open", o), ("close", c)):
            if not row["sharp"]:
                continue
            out["sharp_n_" + tag] += 1
            gap = row["sharp"][0] - row["line"]
            if gap >= GAP:
                out["over_sharp_above_" + tag].add(result("over", row["line"], tot))
            elif gap <= -GAP:
                out["under_sharp_below_" + tag].add(result("under", row["line"], tot))
        if c["sharp"]:
            out["err_sharp_close"] += abs(c["sharp"][0] - tot)
            out["err_sharp_n"] += 1
            sop, sup = c["sharp"][1], c["sharp"][2]
            if sop is not None and sup is not None and sop != sup:
                out["sharp_lean_n"] += 1
                out["sharp_lean"].add(result("over" if sop < sup else "under", c["sharp"][0], tot))
    return out


def report(m, log=print):
    n = m["joined"]
    log("games on the feed %d, joined to a final %d, with an opener and a later close %d" % (m["games"], n, m["both"]))
    if not n:
        return
    log("the line moved up (%.1f+) in %d, down in %d, held in %d" % (MOVE, m["up"], m["down"], m["flat"]))
    log("  over when the line rose:   at the opener %s · at the close %s" % (m["over_up_open"].text(), m["over_up_close"].text()))
    log("  under when the line fell:  at the opener %s · at the close %s" % (m["under_down_open"].text(), m["under_down_close"].text()))
    log("Pinnacle priced %d openers and %d closes" % (m["sharp_n_open"], m["sharp_n_close"]))
    log("  over when Pinnacle sat %.1f+ above the retail number:  opener %s · close %s" % (GAP, m["over_sharp_above_open"].text(), m["over_sharp_above_close"].text()))
    log("  under when Pinnacle sat %.1f+ below:                   opener %s · close %s" % (GAP, m["under_sharp_below_open"].text(), m["under_sharp_below_close"].text()))
    log("  Pinnacle's juiced side at the close, at its own number: %s" % m["sharp_lean"].text())
    log("mean error against the final: opener %.3f, close %.3f%s" % (
        m["err_open"] / n, m["err_close"] / n, (", Pinnacle's close %.3f" % (m["err_sharp_close"] / m["err_sharp_n"])) if m["err_sharp_n"] else ""))
    if m["ks_n"]:
        log("the feed's close equals KillerSports' in %d of %d" % (m["ks_same"], m["ks_n"]))


def selftest():
    hist = {"books": ["fanatics", "betmgm", "pinnacle"], "games": {
        # rose a goal, over at the opener hits (final 7 > 5.5), pushes at the close (6.5? no: 7 > 6.5 wins); Pinnacle above at the open
        "a": {"gdate": "2025-10-08", "away": "Rangers", "home": "Bruins", "start": "2025-10-08T23:00:00Z", "snaps": {
            "2025-10-08T16:00:00Z": {"fanatics": [5.5, -110, -110], "pinnacle": [6.0, -105, -115]},
            "2025-10-08T22:55:00Z": {"fanatics": [6.5, -110, -110], "pinnacle": [6.5, -120, 100]}}},
        # fell a half, under at the opener loses (final 6 < 6.5 wins!) -> under 6.5 wins, under 6 pushes; Pinnacle below at the close
        "b": {"gdate": "2025-10-08", "away": "Bruins", "home": "Rangers", "start": "2025-10-08T23:00:00Z", "snaps": {
            "2025-10-08T16:00:00Z": {"betmgm": [6.5, -110, -110]},
            "2025-10-08T22:55:00Z": {"betmgm": [6.0, -110, -110], "pinnacle": [5.5, -110, -110]}}},
        # a snapshot after the start is ignored; one opener only
        "c": {"gdate": "2025-10-09", "away": "Rangers", "home": "Bruins", "start": "2025-10-09T23:00:00Z", "snaps": {
            "2025-10-09T16:00:00Z": {"fanatics": [6.0, -110, -110]}, "2025-10-10T01:00:00Z": {"fanatics": [7.5, -110, -110]}}},
        # no final in the ledger
        "d": {"gdate": "2025-10-09", "away": "Bruins", "home": "Rangers", "start": "2025-10-09T23:00:00Z", "snaps": {"2025-10-09T16:00:00Z": {"fanatics": [6.0, -110, -110]}}},
    }}
    led = {"games": [{"date": "2025-10-08", "away": "NYR", "home": "BOS", "fa": 4, "fh": 3}, {"date": "2025-10-08", "away": "BOS", "home": "NYR", "fa": 2, "fh": 4},
                     {"date": "2025-10-09", "away": "NYR", "home": "BOS", "fa": 1, "fh": 2}]}
    m = measure(hist, led, [{"date": "2025-10-08", "away": "Rangers", "home": "Bruins", "total": 6.5, "hml": None}])
    fails = []

    def check(name, cond):
        print(("  ok   " if cond else "  FAIL ") + name)
        if not cond:
            fails.append(name)
    check("joins by date and nickname, skips a game with no final", m["games"] == 4 and m["joined"] == 3 and m["both"] == 2)
    check("the move: one up, one down", m["up"] == 1 and m["down"] == 1 and m["flat"] == 0)
    check("over when the line rose: 7 beats 5.5 at the opener and 6.5 at the close", m["over_up_open"].text().startswith("1-0-0") and m["over_up_close"].text().startswith("1-0-0"))
    check("under when the line fell: 6 under 6.5 wins at the opener, pushes at 6", m["under_down_open"].text().startswith("1-0-0") and m["under_down_close"].text().startswith("0-0-1"))
    check("Pinnacle above the retail opener: over 5.5 hit", m["sharp_n_open"] == 1 and m["over_sharp_above_open"].text().startswith("1-0-0"))
    check("Pinnacle below the retail close: under 6 pushed", m["sharp_n_close"] == 2 and m["under_sharp_below_close"].text().startswith("0-0-1"))
    check("Pinnacle's juiced side at the close: the over at -120 on 6.5, 7 scored", m["sharp_lean_n"] == 1 and m["sharp_lean"].text().startswith("1-0-0"))
    check("a snapshot after the start is ignored", open_close(hist["games"]["c"], hist["books"])[1]["line"] == 6.0)
    check("the errors and the KillerSports check", abs(m["err_open"] / 3 - (1.5 + 0.5 + 3.0) / 3) < 1e-9 and m["ks_n"] == 1 and m["ks_same"] == 1)
    report(m)
    print("all checks passed" if not fails else "%d FAILED" % len(fails))
    return 1 if fails else 0


def main(argv):
    if "--selftest" in argv:
        return selftest()
    if len(argv) < 2:
        print(__doc__)
        return 2
    folder, season = argv[0], argv[1]
    hist = json.load(open(os.path.join(folder, "odds-history-NHL-%s.json" % season), encoding="utf-8"))
    led = json.load(open(os.path.join(folder, "nhl-ledger-%s.json" % season), encoding="utf-8"))
    closes = ks_rows(argv[2]) if len(argv) > 2 else None
    print("%s: %d snapshots pulled (%s), books %s" % (season, len(hist.get("pulled") or {}), ", ".join(hist.get("times") or []), ", ".join(hist.get("books") or [])))
    report(measure(hist, led, closes))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
