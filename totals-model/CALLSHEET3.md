# Call Sheet 3.0 — MLB and NHL on one page

`web/callsheet3.html`, published as its own artifact. Built 1 October 2026,
a week before the NHL season, when the WNBA book was retired from the daily
routine (its totals leaned under by construction and the playoffs ran over;
its spreads were 14-1 on a rule the sheet could not know anything about).
The hockey book is priced from **BetMGM**.

- Engine, Python: `totals/nhl.py` (35 tests in `tests/test_nhl.py`)
- Engine, browser: `web/nhl.engine.js`, ported line for line
- Page: derived at build time by `tools_build_callsheet3.py`
- Fixtures: `tools_gen_callsheet3_cases.py` → `web/callsheet3-cases.json`
- Browser harness: `tools_check_callsheet3_page.js` (889 checks)

## How the page is built

3.0 is **derived from 2.0's sources, not copied**. The build reads
`web/callsheet2.head.html` and `web/callsheet2.tail.js`, applies a fixed
list of edits — each anchor must match exactly once, or the build stops and
names the one that did not — inserts the NHL form sections from
`web/callsheet3.nhl-fields.html`, and places the NHL block after Call Sheet
#1's engine block. So a fix to 2.0 reaches 3.0 on the next build, and a
change to 2.0 that would silently break 3.0 breaks the build loudly instead.
The page is head + ENGINE BLOCK (verbatim from `fullgame.html`, byte-checked
by the harness) + NHL BLOCK (verbatim from `nhl.engine.js`, byte-checked)
+ tail.

The NHL block changes nothing inside the engine block. The goal
distribution is registered by reassigning `splitFor` (a function declaration
is a mutable binding in the same scope), the plausibility windows are added
to the engine's `PLAUSIBLE` object, and the team table gets an NHL page the
same way. The Python does the equivalent through `fullgame.register_split`.

The MLB half is Call Sheet 2.0 to the digit: the MLB fixtures in
`callsheet3-cases.json` are 2.0's, unchanged. The WNBA code paths are
carried but the WNBA button is hidden; the WNBA log stays on 2.0. **Load a
backup** accepts a 2.0 backup and carries its MLB rows over, dropping the
WNBA rows with a message, so the baseball log moves here intact.

## The hockey book

Same architecture as baseball. The market total, de-vigged, is the anchor
and carries the dominant weight (4.0). Everything else is a differential.

**Goalies** are the starting pitcher. A save percentage is shrunk toward the
league (.905) by the shots behind it, exactly as an ERA is shrunk by its
innings, and the constant is derived the same way: goalie talent is spread
about .008 of save percentage, a proportion's noise over n shots is
p(1−p)/n, so a goalie's own number is worth half the league prior at about
1,340 shots. Each goalie then faces the *other* side's shot rate. Two
league-average goalies against two league-average shot rates move the
number by exactly zero. Weight 1.6, the starters' figure. Shots alone, with
no goalies, read as "Shot rates" through the same gap with league goalies.

**The one input a hockey market prices imperfectly is a late change in
net.** The sheet says out loud when a goalie is not confirmed, and the
slate names the likely starter; the user confirms on the daily sites.

**Special teams** (both power plays, both kills, over the league's 2.8
chances a side) are sized a priori and tagged, so they cannot buy a band.
**Last ten** and **head to head** are tagged as in MLB. **Back to back** is
shown, not scored: its usual consequence, the backup, already arrives
through the goalie line, and its effect on the total has a disputed sign.

**The goal total is a mixture**: a regulation count (negative binomial,
index 1.09, derived from an a-priori residual spread of 2.55 less the two
lumps) plus an empty-net goal with probability 0.25 plus the overtime goal
with probability 0.23. The mean of the mixture is the projection exactly.
A total of 6 pushes about 16% of the time, which is what hockey does.

**The moneyline and the puck line** are read off the book's own moneyline
through a two-team regulation distribution, with the empty net on the
margin — a one-goal lead becomes a two-goal win 45% of the time, a two-goal
lead a three-goal one 30% — and overtime decided by the regulation win share
compressed halfway toward even. An overtime win is by one and never covers
−1.5. Both markets are **shown, not picked** from the first game, on the run
line's record. **The first period** is the first five: its own market, its
own anchor, the goalie gap scaled by the 30% of regulation goals a first
period carries, a plain Poisson with no empty net and no overtime.

One known seam: the total's mixture uses the league overtime rate (0.23)
while the two-team distribution ties after sixty about 16% of the time —
real teams protect a tie late, which no independent-count model knows. Both
are a priori; the log will say which is nearer.

**Every constant is a priori and says so.** Nothing is fitted, because
there is no log yet. The log is the point; the sheet is what makes one
possible. The residual-spread check measures the total's dispersion as
games settle; the record measures the rest.

## What the user types, from BetMGM

Total and both prices; both moneylines; the home puck line and both prices;
the first-period total and both prices. The slate fills the rest: goalies
(likely starters, save percentage, shots faced), shots for per game, power
play and kill, last ten, head to head, rest days. Closes the next morning
as on 2.0.

## Grading

The final score includes overtime and the shootout — a shootout win is a
one-goal margin, as the league records it — which is what the moneyline and
the puck line settle on. The first period grades from the period score,
typed in the P1 boxes (stored as `f5a`/`f5h`, the period score fields the
card already had), and a period that exceeds the final is `invalid`. The
record keeps an NHL block in goals with tiles for the total, the first
period, the moneyline and the puck line, plus the two fours and beat the
close.
