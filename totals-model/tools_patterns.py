"""Hunt the logged games for anything that predicts over vs under.

Deliberately runs MANY splits and reports them all, including the ones that
found nothing, because reporting only the winners is how noise becomes a
'trend'. With ~25 splits tested at n=116, roughly one crossing |t|=2 by pure
chance is the EXPECTED result, not a discovery.
"""
import json, math, statistics as st, collections, datetime

E=[x for x in json.load(open("log-0823.json"))["entries"]
   if x["sport"]=="MLB" and isinstance(x.get("final"),(int,float)) and x.get("values")]

def n(v):
    try: return float(v)
    except: return None

rows=[]
for x in E:
    v=x["values"]; ln=n(v.get("line"))
    if ln is None: continue
    f=float(x["final"])
    d={"resid": f-ln, "line": ln, "final": f,
       "over": 1 if f>ln else (0 if f<ln else None),
       "park": n(v.get("parkFactor")), "temp": n(v.get("tempF")),
       "dome": bool(v.get("dome")),
       "away": (v.get("away-name") or "").strip(),
       "home": (v.get("home-name") or "").strip(),
       "ts": x.get("ts")}
    rows.append(d)

def tstat(vals):
    """One-sample t against zero on the residual."""
    vals=[v for v in vals if v is not None]
    if len(vals)<8: return None
    m=st.mean(vals); s=st.pstdev(vals)
    if s==0: return None
    se=s/math.sqrt(len(vals))
    return m, len(vals), m/se

def rate(sub):
    d=[r["over"] for r in sub if r["over"] is not None]
    if len(d)<8: return None
    o=sum(d); u=len(d)-o
    p=o/len(d)
    se=math.sqrt(0.25/len(d))
    return o,u,p,(p-0.5)/se

print(f"n = {len(rows)} settled MLB games\n")
print(f"{'split':38s} {'n':>4s} {'over-under':>11s} {'over%':>7s} {'t':>6s}")
print("-"*72)

def report(label, sub):
    r=rate(sub)
    if not r:
        print(f"{label:38s} {len(sub):>4d}  {'too few':>10s}")
        return
    o,u,p,t=r
    flag = "  <-- |t|>2" if abs(t)>2 else ""
    print(f"{label:38s} {o+u:>4d} {f'{o}-{u}':>11s} {p*100:6.1f}% {t:+6.2f}{flag}")

report("ALL", rows)
print()
for lo,hi,lab in [(0,7.75,"line <= 7.5"),(7.75,8.25,"line 8"),(8.25,8.75,"line 8.5"),
                  (8.75,9.25,"line 9"),(9.25,99,"line >= 9.5")]:
    report(lab, [r for r in rows if lo<=r["line"]<hi])
print()
report("dome / roof", [r for r in rows if r["dome"]])
report("outdoors", [r for r in rows if not r["dome"]])
print()
for lo,hi,lab in [(0,96,"park <= 95"),(96,100,"park 96-99"),(100,104,"park 100-103"),
                  (104,999,"park >= 104")]:
    report(lab, [r for r in rows if r["park"] is not None and lo<=r["park"]<hi])
print()
for lo,hi,lab in [(0,70,"temp < 70"),(70,80,"temp 70-79"),(80,999,"temp 80+")]:
    report(lab, [r for r in rows if r["temp"] is not None and lo<=r["temp"]<hi])
print()
for lo,hi,lab in [(0,10,"logged before 10am"),(10,12,"logged 10am-noon"),
                  (12,24,"logged after noon")]:
    sub=[r for r in rows if r["ts"] and
         lo<=datetime.datetime.fromtimestamp(r["ts"]/1000).hour<hi]
    report(lab, sub)
print()
# Teams that appear most, both sides pooled
cnt=collections.Counter()
for r in rows: cnt[r["away"]]+=1; cnt[r["home"]]+=1
print("most-logged teams:")
for team,c in cnt.most_common(8):
    sub=[r for r in rows if r["away"]==team or r["home"]==team]
    report("  " + team[:34], sub)
