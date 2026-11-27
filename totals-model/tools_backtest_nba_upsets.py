"""NBA upsets at the price actually paid (16 Oct 2026): the two odds-history files the
user pulled (slate.py odds-history --sports NBA: closing moneylines, one snapshot a game
day at 6:30 pm Eastern) joined to the backtest rows (tools_backtest_nba.run on the
ledgers and the KillerSports pages). The dog's wins against the market's own de-vigged
chance, by signal, with the dog's return at Pinnacle's price and at the best retail
price. Found the short dog (NBA.md): a dog the book makes 40% or better won 5.6 points
more than priced, both seasons alike.

    python3 tools_backtest_nba_upsets.py SCRATCH   (SCRATCH holds nba/ with the ledgers and pages, up4/ with the two history files)
"""
import sys, io, contextlib, math, json, datetime as dt, collections
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tools_backtest_nba as B

SCR = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
RETAIL = ("fanatics", "betmgm", "draftkings", "fanduel", "caesars", "espnbet", "betrivers")

def implied(a):
    return 100.0 / (a + 100.0) if a > 0 else -a / (-a + 100.0)

def payout(a):
    return a / 100.0 if a > 0 else 100.0 / -a

# --- the closes: per game, the latest snapshot at or before the start ----------------
closes = {}
for f in ("up4/oh2425.json", "up4/oh2526.json"):
    d = json.load(open(SCR + f))
    for k, g in d["games"].items():
        start = g.get("start") or ""
        snaps = sorted(g["snaps"].items())
        before = [s for s in snaps if s[0] <= start] or snaps[:1]
        if not before:
            continue
        ts, snap = before[-1]
        home_full, away_full = g["home"], g["away"]
        pin = snap.get("pinnacle")
        if pin and pin[3] is not None and pin[4] is not None:
            ih, ia = implied(pin[3]), implied(pin[4])
        else:
            hs = [r[3] for r in snap.values() if r[3] is not None]; as_ = [r[4] for r in snap.values() if r[4] is not None]
            if not hs or not as_:
                continue
            ih, ia = sum(implied(x) for x in hs) / len(hs), sum(implied(x) for x in as_) / len(as_)
        p_home = ih / (ih + ia)
        best_h = max([r[3] for b, r in snap.items() if b in RETAIL and r[3] is not None] or [None], key=lambda x: -1e9 if x is None else payout(x))
        best_a = max([r[4] for b, r in snap.items() if b in RETAIL and r[4] is not None] or [None], key=lambda x: -1e9 if x is None else payout(x))
        closes[(g["gdate"], away_full, home_full)] = {"p_home": p_home, "pin_h": pin[3] if pin else None, "pin_a": pin[4] if pin else None, "best_h": best_h, "best_a": best_a, "ts": ts, "hold": ih + ia - 1}
print("closes", len(closes))

# --- the backtest rows, by tricode; the history by nickname ------------------------------
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rows = B.run(SCR + 'nba')
NICK2TRI = dict(B.TEAMS)
def tri(nick):
    return NICK2TRI.get(nick) or NICK2TRI.get(B.NICK.get(nick, nick)) or nick

def ncdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

by_key = {}
for (gd, a, h), c in closes.items():
    by_key[(gd, tri(a), tri(h))] = c
joined, miss = [], 0
for r in rows:
    c = None
    for shift in (0, -1, 1):
        d2 = (dt.date.fromisoformat(r["date"]) + dt.timedelta(days=shift)).isoformat()
        c = by_key.get((d2, r["away"], r["home"]))
        if c: break
    if not c:
        miss += 1; continue
    r["mkt_home"] = c["p_home"]
    r["fav_home"] = c["p_home"] >= 0.5
    r["p_fav"] = max(c["p_home"], 1 - c["p_home"]); r["p_dog"] = 1 - r["p_fav"]
    r["upset"] = (r["margin"] < 0) if r["fav_home"] else (r["margin"] > 0)
    r["dog_pin"] = c["pin_a"] if r["fav_home"] else c["pin_h"]
    r["dog_best"] = c["best_a"] if r["fav_home"] else c["best_h"]
    r["hold"] = c["hold"]
    fh = r["fav_home"]
    r["fav_b2b"], r["dog_b2b"] = (r["h_b2b"], r["a_b2b"]) if fh else (r["a_b2b"], r["h_b2b"])
    r["fav_3in4"], r["dog_3in4"] = (r["h_3in4"], r["a_3in4"]) if fh else (r["a_3in4"], r["h_3in4"])
    r["fav_rest"], r["dog_rest"] = (r["hrest"], r["arest"]) if fh else (r["arest"], r["hrest"])
    r["fav_out"], r["dog_out"] = (r.get("h_miss_min"), r.get("a_miss_min")) if fh else (r.get("a_miss_min"), r.get("h_miss_min"))
    hs = -r["spread"]
    pm = r.get("proj_margin")
    r["ratings_dog"] = ((-(pm - hs)) if fh else (pm - hs)) if pm is not None else None
    # the spread's own model of the dog, for the comparison with dig4
    p_home_sp = 1 - ncdf((0 - hs) / 12.5)
    r["p_dog_spread"] = (1 - p_home_sp) if fh else p_home_sp
    joined.append(r)
print("rows", len(rows), "joined to a close", len(joined), "not joined", miss)
pr = joined
print("market: mean hold (Pinnacle) %.2f%%; the spread's model of the dog vs the moneyline's: mean %.3f vs %.3f" % (100 * sum(r["hold"] for r in pr) / len(pr), sum(r["p_dog_spread"] for r in pr) / len(pr), sum(r["p_dog"] for r in pr) / len(pr)))
obs = sum(1 for r in pr if r["upset"]); exp = sum(r["p_dog"] for r in pr)
print("all games: upsets %d (%.1f%%) vs the moneyline's %.1f%%; dog at Pinnacle %+.1fu, at the best retail price %+.1fu" % (
    obs, 100.0 * obs / len(pr), 100.0 * exp / len(pr),
    sum((payout(r["dog_pin"]) if r["upset"] else -1.0) for r in pr if r["dog_pin"] is not None),
    sum((payout(r["dog_best"]) if r["upset"] else -1.0) for r in pr if r["dog_best"] is not None)))
print("== by the favourite's price (the moneyline's chance of the dog)")
for lo, hi in ((0.0, 0.1), (0.1, 0.2), (0.2, 0.3), (0.3, 0.4), (0.4, 0.51)):
    v = [r for r in pr if lo <= r["p_dog"] < hi]
    if not v: continue
    o = sum(1 for r in v if r["upset"]); e = sum(r["p_dog"] for r in v)
    u = sum((payout(r["dog_best"]) if r["upset"] else -1.0) for r in v if r["dog_best"] is not None)
    print("  dog %.0f-%.0f%%  n %4d  wins %3d (%.1f%%)  priced %.1f%%  dog at best retail %+.1fu (%+.1f%% a bet)" % (lo * 100, hi * 100, len(v), o, 100.0 * o / len(v), 100.0 * e / len(v), u, 100.0 * u / len(v)))

def signal(label, pred, v=None):
    v = [r for r in (v or pr) if pred(r)]
    if len(v) < 25:
        print("  %-58s n %4d  (too few)" % (label, len(v))); return
    o = sum(1 for r in v if r["upset"]); e = sum(r["p_dog"] for r in v)
    var = sum(r["p_dog"] * (1 - r["p_dog"]) for r in v)
    z = (o - e) / math.sqrt(var) if var > 0 else 0
    up = sum((payout(r["dog_pin"]) if r["upset"] else -1.0) for r in v if r["dog_pin"] is not None)
    ub = sum((payout(r["dog_best"]) if r["upset"] else -1.0) for r in v if r["dog_best"] is not None)
    by = []
    for s in ("2024-25", "2025-26"):
        vv = [r for r in v if r["season"] == s]
        if vv: by.append("%+.1f" % (100.0 * (sum(1 for r in vv if r["upset"]) - sum(r["p_dog"] for r in vv)) / len(vv)))
    print("  %-58s n %4d  dog wins %3d vs %.1f  %+.1f pts (z %+.1f)  Pinnacle %+.1fu  best %+.1fu  by season %s" % (label, len(v), o, e, 100.0 * (o - e) / len(v), z, up, ub, " / ".join(by)))

print("== signals: the dog's wins against the moneyline's own chance")
signal("favourite on a back to back", lambda r: r["fav_b2b"])
signal("favourite on a back to back, dog rested 2+", lambda r: r["fav_b2b"] and r["dog_rest"] is not None and r["dog_rest"] >= 2)
signal("dog on a back to back", lambda r: r["dog_b2b"])
signal("favourite three in four", lambda r: r["fav_3in4"])
signal("favourite on the road", lambda r: not r["fav_home"])
signal("favourite rested 3+", lambda r: r["fav_rest"] is not None and r["fav_rest"] >= 3)
signal("dog rested 3+", lambda r: r["dog_rest"] is not None and r["dog_rest"] >= 3)
signal("favourite missing 20+ minutes of regulars", lambda r: (r["fav_out"] or 0) >= 20)
signal("favourite missing 40+ minutes of regulars", lambda r: (r["fav_out"] or 0) >= 40)
signal("favourite missing 60+ minutes of regulars", lambda r: (r["fav_out"] or 0) >= 60)
signal("dog missing 40+ minutes of regulars", lambda r: (r["dog_out"] or 0) >= 40)
signal("favourite missing 20+ more minutes than the dog", lambda r: ((r["fav_out"] or 0) - (r["dog_out"] or 0)) >= 20)
signal("big favourite (dog under 25%)", lambda r: r["p_dog"] < 0.25)
signal("big favourite on a back to back", lambda r: r["p_dog"] < 0.25 and r["fav_b2b"])
signal("big favourite missing 40+ minutes", lambda r: r["p_dog"] < 0.25 and (r["fav_out"] or 0) >= 40)
signal("coin flip (dog 45%+)", lambda r: r["p_dog"] >= 0.45)
signal("ratings like the dog 4+ pts more than the market", lambda r: r["ratings_dog"] is not None and r["ratings_dog"] >= 4)
signal("ratings like the dog 4+ pts more, first 30 games", lambda r: r["ratings_dog"] is not None and r["ratings_dog"] >= 4 and r["n"] < 30)
signal("ratings like the dog 4+ pts more, after 30 games", lambda r: r["ratings_dog"] is not None and r["ratings_dog"] >= 4 and r["n"] >= 30)
signal("post-deadline", lambda r: r["post_deadline"])
signal("last two weeks", lambda r: r["last_two_weeks"])
signal("October", lambda r: r["date"][5:7] == "10")
signal("away favourite moved 2+ zones west", lambda r: not r["fav_home"] and r["tz"] <= -2)
signal("dog at altitude (home in Denver or Utah)", lambda r: not r["fav_home"] is False and r["altitude"] and r["fav_home"] is False)
signal("two or more schedule signals against the favourite", lambda r: sum([r["fav_b2b"], r["fav_3in4"], not r["fav_home"], (r["fav_rest"] or 0) == 0 and (r["dog_rest"] or 0) >= 2]) >= 2)
signal("crew FTA to date 48+", lambda r: (r.get("crew_fta") or 0) >= 48)
# the spread's model against the moneyline: where do they disagree, and who is right?
print("== the spread's model of the dog against the moneyline's")
for lo, hi in ((-99, -0.04), (-0.04, -0.02), (-0.02, 0.02), (0.02, 0.04), (0.04, 99)):
    v = [r for r in pr if lo <= r["p_dog_spread"] - r["p_dog"] < hi]
    if len(v) < 20: continue
    o = sum(1 for r in v if r["upset"]); e = sum(r["p_dog"] for r in v); es = sum(r["p_dog_spread"] for r in v)
    print("  spread model minus moneyline in [%+.2f, %+.2f): n %4d  upsets %.1f%%  moneyline says %.1f%%  spread model says %.1f%%" % (lo, hi, len(v), 100.0 * o / len(v), 100.0 * e / len(v), 100.0 * es / len(v)))

print("== the short dog, finer: by the moneyline's chance of the dog, both seasons and each")
for lo, hi in ((0.30, 0.35), (0.35, 0.40), (0.40, 0.45), (0.45, 0.50), (0.40, 0.51), (0.42, 0.51), (0.45, 0.51)):
    v = [r for r in pr if lo <= r["p_dog"] < hi]
    o = sum(1 for r in v if r["upset"]); e = sum(r["p_dog"] for r in v); var = sum(r["p_dog"] * (1 - r["p_dog"]) for r in v)
    ub = sum((payout(r["dog_best"]) if r["upset"] else -1.0) for r in v if r["dog_best"] is not None)
    by = []
    for s in ("2024-25", "2025-26"):
        vv = [r for r in v if r["season"] == s]
        oo = sum(1 for r in vv if r["upset"]); ee = sum(r["p_dog"] for r in vv)
        uu = sum((payout(r["dog_best"]) if r["upset"] else -1.0) for r in vv if r["dog_best"] is not None)
        by.append("%d: %d-%d %+.1f pts %+.1fu" % (int(s[:4]), oo, len(vv) - oo, 100.0 * (oo - ee) / len(vv), uu))
    print("  dog %.0f-%.0f%%  n %4d  wins %.1f%% vs %.1f%%  %+.1f pts (z %+.1f)  best %+.1fu (%+.1f%%)  | %s" % (lo * 100, hi * 100, len(v), 100.0 * o / len(v), 100.0 * e / len(v), 100.0 * (o - e) / len(v), (o - e) / math.sqrt(var), ub, 100.0 * ub / len(v), " | ".join(by)))
print("== the short dog (40%+) split")
short = [r for r in pr if r["p_dog"] >= 0.40]
signal("short dog at home", lambda r: not r["fav_home"], short)
signal("short dog on the road", lambda r: r["fav_home"], short)
signal("short dog, the spread's model agrees within 2 pts", lambda r: abs(r["p_dog_spread"] - r["p_dog"]) < 0.02, short)
signal("short dog, the spread's model likes the dog 2+ more", lambda r: r["p_dog_spread"] - r["p_dog"] >= 0.02, short)
signal("short dog, the spread's model likes the dog 2+ less", lambda r: r["p_dog_spread"] - r["p_dog"] <= -0.02, short)
signal("short dog, favourite missing 20+ minutes", lambda r: (r["fav_out"] or 0) >= 20, short)
signal("short dog, favourite missing nothing", lambda r: (r["fav_out"] or 0) < 20, short)
signal("short dog before the deadline", lambda r: not r["post_deadline"], short)
signal("short dog after the deadline", lambda r: r["post_deadline"], short)
signal("short dog, first 30 games", lambda r: r["n"] < 30, short)
signal("short dog, after 30 games", lambda r: r["n"] >= 30, short)
signal("short dog by month Oct-Nov", lambda r: r["date"][5:7] in ("10", "11"), short)
signal("short dog by month Dec-Jan", lambda r: r["date"][5:7] in ("12", "01"), short)
signal("short dog by month Feb-Apr", lambda r: r["date"][5:7] in ("02", "03", "04"), short)
# the ML snapshot against the spread at the close: did the line move toward the dog after 6:30 pm?
print("== big dogs (under 25%): any save?")
big = [r for r in pr if r["p_dog"] < 0.25]
signal("big dog, favourite on a back to back", lambda r: r["fav_b2b"], big)
signal("big dog, favourite missing 40+ minutes", lambda r: (r["fav_out"] or 0) >= 40, big)
signal("big dog, dog rested 2+ and favourite 0", lambda r: (r["dog_rest"] or 0) >= 2 and (r["fav_rest"] or 9) == 0, big)
