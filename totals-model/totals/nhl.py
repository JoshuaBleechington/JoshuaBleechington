"""NHL -- the total, and every market the book posts on one game.

Built 1 October 2026, a week before the season, on the architecture the MLB
book earned over September: anchor on what the two prices really say, move
off that anchor by DIFFERENTIALS only, tag every input whose size is a guess
so it cannot buy a band on its own, and price every other market off the
book's own numbers. Nothing here is fitted, because there is no log yet. The
log is the point; this file is what makes one possible.

What is the same as baseball
----------------------------
* The market total, de-vigged, is the anchor and carries the dominant weight.
* The goalie is the starting pitcher: one player, one number, a sample size
  that says how much of that number to believe. A save percentage is shrunk
  toward the league by the shots behind it exactly as an ERA is shrunk by
  its innings, and the constant falls out of the same two facts (how spread
  goalie talent is, how noisy a proportion is over n shots).
* The first period is the first five: its own market, its own anchor, the
  goalie gap scaled to the share of the game it covers, no empty nets.
* The moneyline and the puck line are read off the book's own moneyline and
  the goal distribution, which makes them relative judgements between the
  book's quotes and nothing more. Shown, graded, and -- on the run line's
  record -- not to be trusted until the log says otherwise.

What is different, and handled explicitly
-----------------------------------------
* EMPTY NETS. About a quarter of games end with a goal into an empty net.
  That goal lands on a total of 5.5 or 6 like a thumb on the scale, and it
  lands on the puck line harder: a one-goal lead becomes a two-goal win. The
  goal total here is a regulation count PLUS an empty-net lump PLUS the
  overtime goal, as a mixture, so the push on 6 and the side on 5.5 see it.
* OVERTIME AND THE SHOOTOUT. A tie after sixty is not a result: one more
  goal is scored, by someone, and the moneyline includes it. The puck line
  does not care who, because an overtime win is by one goal and never covers
  -1.5. Overtime is closer to a coin flip than regulation strength says, so
  the regulation share is compressed toward even there.
* PUSHES. Totals of 6 sit on a whole number and push often. Inherited
  machinery; nothing new.
* NO WEATHER, no park. The one unpriced input baseball had is gone. What a
  hockey market prices imperfectly is the GOALIE NEWS -- a backup announced
  after the line posts -- and the back-to-back, both of which arrive on the
  slate.

What is a guess (read before trusting a number)
-----------------------------------------------
Every constant below marked A PRIORI. The league goal rate, the empty-net
rate, the overtime rate, the first-period share and the overtime compression
are reasonable figures for a modern season and not measured from anything
in this project. The residual-spread check on the sheet measures the total's
dispersion as games settle; the record measures the rest.

One known seam: the total's mixture uses the league overtime rate (0.23),
while the two-team distribution behind the moneyline and puck line produces
its own tie rate from the two means, and a near-Poisson pair ties after sixty
about 16% of the time, not 23% -- real teams protect a tie late, which no
independent-count model knows. The total is anchored and blended on the
league figure; the sides are read off the pair. Both are a priori; the log
will say which is nearer.
"""

from __future__ import annotations

from typing import Any

from .callsheet2 import Market, Matchup, _pick, _side, _total_market, team_pmf
from .fullgame import (
    BANDS, HOLD_REFERENCE, Delta, Estimate, Forecast, PLAUSIBLE, _assemble, _ok,
    devig, fair_total, hold, market_confidence, nb_pmf, nb_split, register_split,
)

# ===========================================================================
# League constants -- MEASURED 7 Oct 2026 on the league ledger: every
# regular-season final of 2024-25 and 2025-26, 2,624 games (slate.py
# nhl-ledger --season). A priori from 1 Oct until then; each line says
# what it was and what it measured.
# ===========================================================================

LEAGUE_SOURCE = "measured on 2,624 games, the 2024-25 and 2025-26 ledgers, 7 Oct 2026"

#: Goals per game, both teams, everything included: empty-netters and the
#: one goal that decides overtime or the shootout. Was 6.10; measured 6.08
#: and 6.25 by season, 6.17 together. October runs 6.4 both years, the
#: highest month, and settles to 6.0-6.1 by November.
LEAGUE_GOALS_PER_GAME = 6.17
#: The empty-net lump: expected empty-net goals a game. Was 0.25 as "the
#: chance of one"; measured 0.396 and 0.382 goals a game (36% of games have
#: at least one, some have two), so the lump carries the mean, 0.39.
EMPTY_NET_RATE = 0.39
#: Tied after sixty. Was 0.23; measured 0.207 and 0.248, 0.228 together
#: (15.3% decided in overtime, 7.5% in the shootout).
OT_RATE = 0.23
#: Regulation goals with the goalies in the net: what the goalie and shot
#: inputs are a differential against.
LEAGUE_REG_GOALS = LEAGUE_GOALS_PER_GAME - EMPTY_NET_RATE - OT_RATE
#: Shots per team per game, and the league save percentage. Shots were 30
#: a priori; measured 28.3 and 27.8, 28.1 together. 28.1 * .102 * 2 = 5.73
#: against 5.55 regulation goals; the gap is the shots at an empty net.
#: The save percentage was .905 a priori until 5 Oct 2026, when the first
#: four nights of the slate's goalie lines -- 62 of them, 37,931 shots, this
#: season blended with half of last -- averaged .898 shots-weighted. Against
#: .905 every goalie on the card read cold, every total leaned over, and
#: Call Sheet #1 called BET on the over in 8 of 31 games (3-5). Measured on
#: the card's own starters, so it is the prior for a named starter, not for
#: the league's backups; re-measure at the end of the month.
#: The ledger then measured the league at .901 and .896, .898 together,
#: which is the figure already here.
LEAGUE_SHOTS = 28.1
LEAGUE_SAVE_PCT = 0.898
#: Power plays per team per game, and the league conversion either side.
LEAGUE_PP_PER_GAME = 2.8
LEAGUE_PP_PCT = 0.21
LEAGUE_PK_PCT = 1.0 - LEAGUE_PP_PCT
#: Expected goals per team per game, the level MoneyPuck's xG is calibrated
#: to (it tracks the league's scoring). A FALLBACK: the slate writes the
#: league mean of the same table it took the clubs' figures from, and that
#: is what the sheet uses when it is there -- the WNBA pace lesson, that a
#: league constant must come from the table the inputs come from.
LEAGUE_XG_PER_TEAM = 3.05

# --- how much a goalie's save percentage is worth knowing -----------------
# Same derivation as the ERA shrinkage in fullgame.py. A save percentage is a
# proportion, so its measurement variance over n shots is p(1-p)/n; goalie
# true talent is spread about .008 of save percentage. The shots at which the
# goalie's own number is worth exactly as much as the league prior:
#   n = p(1-p) / talent_sd^2  ~  1,430 shots, about 48 starts.
# A backup with 300 shots keeps 17% of his number; a starter at 1,500 keeps
# 51%. Nobody keeps 100%, which is correct.
GOALIE_TALENT_SD = 0.008
SV_STABLE_AT = LEAGUE_SAVE_PCT * (1.0 - LEAGUE_SAVE_PCT) / GOALIE_TALENT_SD ** 2

# --- dispersion ------------------------------------------------------------
#: Spread of a final goal total around its projection. Was 2.55 a priori.
#: The ledger measured the RAW spread of totals at 2.32 and 2.30 (variance
#: 5.34 on a mean of 6.17): a hockey total is narrower than a Poisson, not
#: wider, and the residual against a market can only be narrower still.
#: The regulation count cannot be made narrower than Poisson in this
#: family, so Poisson is the floor: 2.45^2 = 6.00 less the two lumps
#: (0.39*0.61 + 0.23*0.77 = 0.415) is 5.59 over 5.55 regulation goals, an
#: index of 1.01. The probabilities this gives lean a touch toward 50%,
#: which is the conservative side. The first period, by contrast, is Poisson
#: to the decimal: mean 1.745, variance 1.702.
RESIDUAL_SD = 2.45
REG_PHI = (RESIDUAL_SD ** 2
           - EMPTY_NET_RATE * (1.0 - EMPTY_NET_RATE)
           - OT_RATE * (1.0 - OT_RATE)) / LEAGUE_REG_GOALS
#: The first period's share of the regulation goals scored with the goalies
#: in. Was 0.30; measured 0.316 and 0.312, 0.314 together (1.74 goals a
#: period, 0 / 1 / 2+ in 17.6 / 29.2 / 53.1% of games, where a Poisson at
#: that mean says 2+ in 52.0%). Poisson, no empty net, no overtime.
P1_SHARE = 0.314
P1_PHI = 1.0

# --- the empty net, on the margin -----------------------------------------
#: P(the leading side scores into the empty net | it leads by one at the end
#: of regulation play), and by two. The pull happens in close games, so the
#: one-goal case carries most of it. Together with how often regulation ends
#: one or two goals apart these reproduce EMPTY_NET_RATE roughly, not exactly.
ENG_GIVEN_ONE_GOAL_LEAD = 0.45
ENG_GIVEN_TWO_GOAL_LEAD = 0.30
#: Overtime and the shootout are nearer a coin flip than regulation. The
#: regulation win share is pulled this far toward even before it decides a
#: tied game. 0.5 is a guess with the right sign.
OT_COMPRESSION = 0.5

#: The weights. Market 4.0 as in baseball. Goalies 1.6: measured on 7 Oct
#: 2026 against 2,616 closing totals of two seasons with the starters'
#: lines built the way the sheet builds them (this season to date plus
#: half of last season, shrunk). Over every game the lean was near null
#: (+0.31 in 2025-26, -0.25 in 2024-25), and the split explained it: with
#: two REGULAR starters the lean ran the right way both seasons (slopes
#: +0.07 and +0.92; pooled +0.55 on 1,744 games, 53.1% betting a tenth of
#: a goal of lean), and with a BACKUP in net it ran against (both
#: seasons). So goalies are scored at 1.6 with two regular starters and
#: NOT SCORED with a backup in net, where BACKUP_DELTA carries what the
#: backtest found. Form 0.6, measured: last-ten lean against 2,445 closing
#: totals ran at a slope of 0.14, an implied weight of 0.6. REMOVED from
#: scoring on 7 Oct 2026, all shown, not scored: shots (season shot-rate
#: lean ran the WRONG way, slope -0.72, 49.1% betting with it); special
#: teams (the detail pass put each side's power play and kill to date
#: against 2,445 closes: slopes -0.20 and -0.51, the power-play half
#: -0.06/-0.47 and the kill half -0.43/-0.54 by season -- the market has
#: them); expected goals (this season's xG to date, built the slate's way
#: from Natural Stat Trick's game table, slope -0.31 against 1,223 closes
#: of 2024-25, and last season's xG +0.45/-0.46 by season: a coin); head
#: to head (slope 0.02 on 814); the first-period last ten (slope -0.003).
WEIGHTS = {"market": 4.0, "goalies": 1.6, "form": 0.6, "h2h": 0.5}
#: A backup in net. The detail pass named every starter over two seasons;
#: a starter with fewer than 30% of his club's starts, ten starts in, is a
#: backup. With ONE backup in a game the total landed 0.18 under the close
#: (737 games, the under 396-341, 53.7%; -0.19 and -0.18 by season, at every
#: threshold tried): the market bumps the total for a backup and bumps it
#: too far. With a backup in BOTH nets (105 games) the sign flipped and the
#: sample is nothing, so nothing moves. Sized under the measurement, as a
#: tagged delta: it cannot buy a band, and the tile keeps the under's record.
BACKUP_DELTA = -0.15
#: ...and when the backup's own line reads COLD (his shrunk save percentage
#: costs more than BACKUP_COLD_GAP goals against a league goalie) the
#: market over-bumps harder: 182 such games landed 0.44 under the close,
#: the under 100-74 (57.5%; -0.53 and -0.39 by season). The warm or even
#: backup: 585 games, 0.10 under, 52.6%. Sized under both measurements.
BACKUP_DELTA_COLD = -0.25
BACKUP_COLD_GAP = 0.05
BACKUP_SHARE = 0.30     # a starter under this share of his club's starts is a backup
BACKUP_MIN_STARTS = 10  # ...once the club has this many starts to share
#: October: RETIRED 11 Oct 2026. Both backtest seasons scored 6.41 a game
#: in October against a 6.07 closing line, the over 178-146 blind, and a
#: +0.25 tagged delta went on every October line from 7 Oct. The 2026
#: market carried it: the card's first 75 October games closed at 6.11 and
#: scored 6.08, the blind over 33-39-3, and the delta pushed the sheet's
#: picks over in 58 of 75 games. A seasonal excess the market has priced is
#: not an input. October now gets a note and nothing on the line.
OCTOBER_DELTA = 0.0
H2H_FULL_WEIGHT_AT = 4
DEFAULT_PUCK_LINE = 1.5
_KMAX = 25


# ===========================================================================
# The goal distribution: regulation count + empty-net lump + overtime goal
# ===========================================================================

def reg_mean(total_mean: float) -> float:
    """The regulation, goalies-in, mean that a given TOTAL mean implies.

    E[total] = E[regulation] + P(tie) * 1 + P(not tied) * P(empty net | not
    tied) * 1, and the last term is EMPTY_NET_RATE by construction."""
    return max(0.05, total_mean - OT_RATE - EMPTY_NET_RATE)


def total_pmf(mu: float, kmax: int = 40) -> list[float]:
    """P(final total = k) for a TOTAL mean of `mu`, as the mixture.

    With probability OT_RATE the game is tied after sixty and exactly one
    more goal is scored; otherwise an empty-net goal is added with the
    probability that makes the unconditional rate EMPTY_NET_RATE. The mean
    of the mixture is `mu` exactly; there is a test at twelve decimals.
    """
    mr = reg_mean(mu)
    p_eng = EMPTY_NET_RATE / (1.0 - OT_RATE)
    reg = [nb_pmf(k, mr, REG_PHI) for k in range(kmax + 1)]
    s = sum(reg)
    reg = [v / s for v in reg] if s > 0 else reg
    out = []
    for k in range(kmax + 1):
        prev = reg[k - 1] if k >= 1 else 0.0
        out.append(OT_RATE * prev + (1.0 - OT_RATE) * ((1.0 - p_eng) * reg[k] + p_eng * prev))
    return out


def nhl_split(line: float, mu: float) -> tuple[float, float, float]:
    """(P over, P push, P under) on a goal total, empty nets and overtime in."""
    if mu <= 0:
        return 0.0, 0.0, 1.0
    pm = total_pmf(mu)
    under = sum(v for k, v in enumerate(pm) if k < line)
    push = sum(v for k, v in enumerate(pm) if k == line)
    over = max(0.0, 1.0 - under - push)
    return over, push, under


def p1_split(line: float, mu: float) -> tuple[float, float, float]:
    return nb_split(line, mu, P1_PHI)


register_split("NHL", nhl_split)
register_split("NHL_P1", p1_split)


def p1_anchor(line: float, over_price: float | None, under_price: float | None
              ) -> tuple[float, str]:
    """The first-period market's mean, with the hold regression OFF.

    `fair_total` pulls a de-vigged lean toward even when the hold is wide,
    because on a main total a wide hold means an alternate line. A
    first-period total carries a wide hold as a matter of course (BetMGM runs
    about seven cents on it), so the regression read every first-period
    market as half a lean: the sheet sat a point or two under the book on all
    of them, the under was always the better price, and the pick went under
    on 25 of the first 26 periods (10-15). Never a bet -- a regressed lean
    never clears its price -- but a tile that bled for a reason that was not
    hockey. Turned off here on 4 Oct 2026 at the user's call: both prices
    read straight, same bisection, same split. With one price or none this
    defers to `fair_total`, which reconstructs or assumes the pair.
    """
    if over_price is None or under_price is None:
        return fair_total("NHL_P1", line, over_price, under_price)
    p_over, _ = devig(over_price, under_price, shrink=False)
    lo, hi = max(0.5, line - 4.0), line + 4.0
    for _ in range(80):
        mid = (lo + hi) / 2.0
        o, _push, u = p1_split(line, mid)
        live = o + u
        conditional = o / live if live > 0 else 0.5
        if conditional < p_over:
            lo = mid
        else:
            hi = mid
    mu = (lo + hi) / 2.0
    return mu, (
        f"{over_price:+.0f}/{under_price:+.0f} de-vigs to {p_over * 100:.1f}% over and puts fair "
        f"at {mu:.2f} against the {line:g} posted. The {hold(over_price, under_price) * 100:.1f}% "
        f"hold is read straight, not regressed: a first-period market carries a wide hold as a "
        f"matter of course, and regressing it had the sheet calling the under the better price on "
        f"25 of its first 26 periods. Off since 4 Oct 2026.")


# ===========================================================================
# The goalie, as a differential
# ===========================================================================

def sv_weight(shots_faced: float | None) -> float:
    """How much of a goalie's own save percentage survives, on his shots.
    Blank shots means trust it in full, which keeps a card typed without
    them scoring as typed."""
    if shots_faced is None or not _ok(shots_faced, "shots_faced") or shots_faced <= 0:
        return 1.0
    return shots_faced / (shots_faced + SV_STABLE_AT)


def shrink_sv(sv: float | None, shots_faced: float | None) -> float | None:
    if sv is None:
        return None
    return LEAGUE_SAVE_PCT + sv_weight(shots_faced) * (sv - LEAGUE_SAVE_PCT)


def goalie_gap(sv_used: float | None, opp_shots: float | None = None) -> float | None:
    """Goals this goalie allows per game over a league goalie, both facing
    the league's shot rate. A league-average goalie gives exactly zero.
    `opp_shots` is accepted and IGNORED since 7 Oct 2026: the backtest read
    the shot-rate lean against 2,445 closing totals and it ran the wrong
    way (slope -0.72 both seasons; betting with it 49.1%). A team that
    shoots more is a team that shoots from everywhere, and the market
    knows it. Shots stay on the card, shown, not scored."""
    if sv_used is None or not _ok(sv_used, "save_pct"):
        return None
    return LEAGUE_SHOTS * (LEAGUE_SAVE_PCT - sv_used)


def h2h_weight(base: float, meetings: float) -> float:
    return base * min(1.0, max(0.0, meetings) / H2H_FULL_WEIGHT_AT)


# ===========================================================================
# The total
# ===========================================================================

def forecast_nhl(
    matchup: str,
    line: float,
    over_price: float | None = None,
    under_price: float | None = None,
    away_goalie_sv: float | None = None,
    home_goalie_sv: float | None = None,
    away_goalie_shots: float | None = None,
    home_goalie_shots: float | None = None,
    away_shots_for: float | None = None,     # shown, not scored since 7 Oct 2026
    home_shots_for: float | None = None,
    game_month: int | None = None,           # the October delta
    away_pp_pct: float | None = None,
    home_pp_pct: float | None = None,
    away_pk_pct: float | None = None,
    home_pk_pct: float | None = None,
    away_last10_total: float | None = None,
    home_last10_total: float | None = None,
    h2h_total: float | None = None,
    h2h_meetings: float | None = None,
    away_xgf: float | None = None,       # expected goals for per game (MoneyPuck, all situations)
    home_xgf: float | None = None,
    away_xga: float | None = None,       # expected goals against per game
    home_xga: float | None = None,
    league_xg: float | None = None,      # the same table's league mean per team-game
    away_rest_days: float | None = None,
    home_rest_days: float | None = None,
    away_goalie_confirmed: bool = False,
    home_goalie_confirmed: bool = False,
    away_goalie_backup: bool = False,        # the starter is his club's backup (BACKUP_SHARE)
    home_goalie_backup: bool = False,
    ticket_pct_over: float | None = None,
    money_pct_over: float | None = None,
    opened: float | None = None,
) -> Forecast:
    if not _ok(line, "nhl_total"):
        raise ValueError(f"total {line!r} is outside {PLAUSIBLE['nhl_total']}")
    w = WEIGHTS
    notes: list[str] = []
    anchor, anchor_detail = fair_total("NHL", line, over_price, under_price)
    estimates = [Estimate("Market", anchor, w["market"], anchor_detail)]
    deltas: list[Delta] = []

    # --- goalies and shots, as one differential ----------------------------
    # Each goalie's save percentage is pulled toward the league by the shots
    # behind it; each then faces the OTHER side's shot rate. A goalie with no
    # number is given the league's, so a card with shots and no goalies still
    # reads the shot rates, and a card with neither reads nothing.
    aw, hw = sv_weight(away_goalie_shots), sv_weight(home_goalie_shots)
    a_sv = shrink_sv(away_goalie_sv, away_goalie_shots)
    h_sv = shrink_sv(home_goalie_sv, home_goalie_shots)
    have_goalies = a_sv is not None and h_sv is not None
    any_backup = bool(away_goalie_backup or home_goalie_backup)
    if (a_sv is not None or h_sv is not None) and any_backup:
        # Measured 7 Oct 2026 on 767 one-backup games: neither the backup's
        # own line nor the regular starter's had a direction against the
        # close (slopes -0.94 and -0.84 pooled, signs 43% and 53%). The
        # backup delta below carries the one thing that did.
        notes.append("Goalies are NOT SCORED with a backup in net: in 767 backtest games with one, "
                     "neither goalie's line had a direction against the close. The backup flag "
                     "carries what did.")
    elif a_sv is not None or h_sv is not None:
        a_used = a_sv if a_sv is not None else LEAGUE_SAVE_PCT
        h_used = h_sv if h_sv is not None else LEAGUE_SAVE_PCT
        a_gap = goalie_gap(a_used)
        h_gap = goalie_gap(h_used)
        if a_gap is not None and h_gap is not None:
            gap = a_gap + h_gap
            parts = []
            if a_sv is not None:
                parts.append(f"away {away_goalie_sv:.3f}" + (f" over {away_goalie_shots:.0f} shots is worth "
                             f"{aw:.0%} of itself, so it enters at {a_sv:.3f}" if aw < 1.0 else ""))
            if h_sv is not None:
                parts.append(f"home {home_goalie_sv:.3f}" + (f" over {home_goalie_shots:.0f} shots is worth "
                             f"{hw:.0%} of itself, so it enters at {h_sv:.3f}" if hw < 1.0 else ""))
            estimates.append(Estimate(
                "Goalies", anchor + gap, w["goalies"],
                (f"{'; '.join(parts) + '. ' if parts else ''}"
                 f"Each goalie against the league's {LEAGUE_SHOTS:.1f} shots, against a "
                 f".{LEAGUE_SAVE_PCT * 1000:.0f} goalie: {gap:+.2f} goals on the line. A save "
                 f"percentage is worth half the league prior at {SV_STABLE_AT:.0f} shots, which is why "
                 "a backup's hot month cannot carry a card.")))
            if (a_sv is not None) != (h_sv is not None):
                notes.append("One goalie's save percentage is in and the other's is not; the missing "
                             "side is scored as a league-average goalie. Fill in both once the "
                             "starters are confirmed.")
    if away_shots_for is not None or home_shots_for is not None:
        notes.append("Shots for per game are SHOWN, NOT SCORED: against two seasons of closing totals "
                     "the shot-rate lean ran the wrong way (49.1% betting with it). A team that shoots "
                     "more shoots from everywhere, and the market knows it.")
    if game_month == 10:
        notes.append("October: NO seasonal delta since 11 Oct 2026. The backtest's two Octobers ran 0.34 a game "
                     "over the close; the 2026 market carries it (the card's first 75 October games closed at "
                     "6.11 and scored 6.08, the blind over 33-39-3). Shown, not scored.")
    unconfirmed = [s for s, c in (("away", away_goalie_confirmed), ("home", home_goalie_confirmed))
                   if not c]
    if have_goalies and unconfirmed:
        notes.append(f"The {' and '.join(unconfirmed)} goalie is NOT confirmed. The book priced the "
                     "expected starter; the one input a hockey market prices imperfectly is a "
                     "late change in net. Confirm on the daily sites before betting, and re-enter "
                     "the backup's line if it is the backup.")

    # --- a backup in net: a tagged delta on the under ------------------------
    # See BACKUP_DELTA. One backup: the market over-bumps the total. Two: the
    # sign flipped on 105 games, which is no sample; nothing moves.
    backups = [s for s, b in (("away", away_goalie_backup), ("home", home_goalie_backup)) if b]
    if len(backups) == 1:
        bk_sv = a_sv if backups[0] == "away" else h_sv
        bk_gap = goalie_gap(bk_sv) if bk_sv is not None else None
        cold = bk_gap is not None and bk_gap > BACKUP_COLD_GAP
        size = BACKUP_DELTA_COLD if cold else BACKUP_DELTA
        bk_why = (f"Backup in net for the {backups[0]} side. Against two seasons of closing totals a "
                  "game with ONE backup starting landed 0.18 under the close (737 games, the under "
                  "53.7%): the market bumps the total for a backup and bumps it too far. "
                  + (f"This backup reads COLD (his line costs {bk_gap:+.2f} goals against a league goalie), and a "
                     "cold backup over-bumped harder: 182 games landed 0.44 under, the under 57.5%. "
                     if cold else "")
                  + f"{size:+.2f} on the line, tagged: it cannot buy a band, and the tile keeps the under's "
                  "record on these games.")
        deltas.append(Delta("Backup in net", size, bk_why, mechanism=False))
        notes.append(bk_why)
    elif len(backups) == 2:
        notes.append("A backup in BOTH nets. Measured on 105 games with no direction (the one-backup "
                     "under did not carry), so nothing moves; the record will say.")

    # --- special teams: SHOWN, NOT SCORED since 7 Oct 2026 -------------------
    # The detail pass carried every power-play goal and penalty of two
    # seasons. Each side's power play and kill to date, through the gap
    # this block used to score, against 2,445 closing totals: slope -0.20
    # and -0.51 by season; the power-play half -0.06/-0.47, the kill half
    # -0.43/-0.54. The market has them. The boxes stay on the card.
    st = [away_pp_pct, home_pp_pct, away_pk_pct, home_pk_pct]
    if any(v is not None for v in st):
        notes.append("Special teams are SHOWN, NOT SCORED: each side's power play and kill to date, "
                     "against two seasons of closing totals, ran the wrong way (slopes -0.20 and -0.51; "
                     "both halves negative both seasons). The market has them.")

    # --- form and head to head, tagged as in MLB ----------------------------
    # --- expected goals -----------------------------------------------------
    # MoneyPuck's xG: every shot attempt weighted by where it came from and
    # how, so a backdoor tap-in is not a sixty-foot wrister. Each side's
    # offence against the other's defence, both per game, against the league
    # mean of the same table; the gap goes on the line. Added 6 Oct 2026 from
    # the user's download of the team file. Tagged: it is the best-supported
    # team input in hockey analytics, and it still has no record here.
    # SHOWN, NOT SCORED since 7 Oct 2026. Natural Stat Trick's game table
    # let the input be built the way the slate builds it -- each club's xG
    # for and against per game to date, five games in, against the table's
    # own league mean -- and against 1,223 closing totals of 2024-25 it ran
    # the WRONG way (slope -0.31; betting a half-goal of lean 19-34). Last
    # season's xG flipped sign between seasons (+0.45 in 2025-26, -0.46 in
    # 2024-25), high-danger chances to date were null (-0.03), last-ten xG
    # null (-0.20). The market has it. The gap is still computed and shown.
    xg = [away_xgf, home_xgf, away_xga, home_xga]
    if all(v is not None and _ok(v, "xg_rate") for v in xg):
        lg = league_xg if (league_xg is not None and _ok(league_xg, "xg_rate")) else LEAGUE_XG_PER_TEAM
        xtot = (away_xgf + home_xga) / 2.0 + (home_xgf + away_xga) / 2.0
        xgap = xtot - 2.0 * lg
        notes.append(f"Expected goals {xtot:.2f} against a league {2 * lg:.2f} ({xgap:+.2f}). SHOWN, NOT SCORED: "
                     "built the slate's way against 1,223 closing totals, this season's xG to date ran the "
                     "wrong way (slope -0.31), and last season's flipped sign between seasons. The market has it.")
    elif any(v is not None for v in xg):
        notes.append("Expected goals are shown, not scored, and a partial set (not all four figures) is not "
                     "even shown.")

    if away_last10_total is not None and home_last10_total is not None:
        avg = (away_last10_total + home_last10_total) / 2.0
        estimates.append(Estimate(
            "Last 10", avg, w["form"],
            f"Last-ten combined totals average {avg:.1f}. Measured against 2,445 closing totals: a "
            "slope of 0.14, an implied weight of 0.6, which is the weight; tagged.",
            mechanism=False))
    if h2h_total is not None and h2h_meetings:
        # SHOWN, NOT SCORED since 7 Oct 2026: against 814 closing totals with
        # an earlier meeting behind them, the head-to-head lean had a slope
        # of 0.02 (an implied weight of 0.08). Two teams' last game together
        # says nothing about their next.
        notes.append(f"Head to head: {h2h_meetings:g} meeting(s) averaging {h2h_total:.1f}. SHOWN, NOT "
                     "SCORED: measured against 814 closing totals and null (slope 0.02).")

    # --- rest: SHOWN, NOT SCORED -------------------------------------------
    # A back-to-back changes who is in net more than it changes the score,
    # and the goalie input already carries that. Its own effect on the total
    # has a disputed sign in the literature. Logged on the row so the record
    # can split on it; nothing moves.
    b2b = [s for s, d in (("away", away_rest_days), ("home", home_rest_days))
           if d is not None and d <= 0]
    if b2b:
        notes.append(f"Back to back for the {' and '.join(b2b)} side. SHOWN, NOT SCORED: the "
                     "goalie line already carries the usual consequence (the backup), and the "
                     "rest effect on the total itself is unmeasured. It is on the row so the "
                     "record can split on it.")

    # --- the ticket / money split, shown as in MLB ----------------------------
    tk = ticket_pct_over if _ok(ticket_pct_over, "percent") else None
    cs = money_pct_over if _ok(money_pct_over, "percent") else None
    if tk is not None and cs is not None and abs(tk - cs) >= 20.0:
        notes.append(f"Over holds {tk:.0f}% of tickets but {cs:.0f}% of money. Shown, not scored, "
                     "for the reason the MLB book stopped scoring it: no threshold beat a coin.")
    if opened is not None and abs(opened - line) > 1e-9:
        notes.append(f"The number moved {opened:g} to {line:g} ({line - opened:+.1f}). Not scored -- "
                     "the current line is the anchor and the move is already inside it.")

    return _assemble("NHL", matchup, line, estimates, deltas, notes)


# ===========================================================================
# The two-team distribution, with the empty net on the margin
# ===========================================================================

def reg_margin_dist(lam_home: float, lam_away: float, phi: float = REG_PHI) -> dict[int, float]:
    """P(home regulation goals - away regulation goals = d), goalies in."""
    h, a = team_pmf(lam_home, phi, _KMAX), team_pmf(lam_away, phi, _KMAX)
    dist: dict[int, float] = {}
    for i, ph in enumerate(h):
        if ph < 1e-15:
            continue
        for j, pa in enumerate(a):
            if pa < 1e-15:
                continue
            dist[i - j] = dist.get(i - j, 0.0) + ph * pa
    return dist


def ot_home_share(dist: dict[int, float]) -> float:
    """Who wins a tied game: the regulation win share, compressed toward even."""
    win = sum(v for d, v in dist.items() if d > 0)
    lose = sum(v for d, v in dist.items() if d < 0)
    share = win / (win + lose) if (win + lose) > 0 else 0.5
    return 0.5 + OT_COMPRESSION * (share - 0.5)


def final_margin_dist(lam_home: float, lam_away: float, phi: float = REG_PHI) -> dict[int, float]:
    """P(final margin = d): regulation, then the empty net for a side leading
    by one or two, then the overtime goal for a tie. Every final margin is
    nonzero, which is what a hockey game is."""
    reg = reg_margin_dist(lam_home, lam_away, phi)
    ot = ot_home_share(reg)
    out: dict[int, float] = {}

    def add(d: int, v: float) -> None:
        out[d] = out.get(d, 0.0) + v

    for d, v in reg.items():
        if d == 0:
            add(1, v * ot)
            add(-1, v * (1.0 - ot))
        elif abs(d) == 1:
            add(d + (1 if d > 0 else -1), v * ENG_GIVEN_ONE_GOAL_LEAD)
            add(d, v * (1.0 - ENG_GIVEN_ONE_GOAL_LEAD))
        elif abs(d) == 2:
            add(d + (1 if d > 0 else -1), v * ENG_GIVEN_TWO_GOAL_LEAD)
            add(d, v * (1.0 - ENG_GIVEN_TWO_GOAL_LEAD))
        else:
            add(d, v)
    return out


def p_home_wins(lam_home: float, lam_away: float, phi: float = REG_PHI) -> float:
    return sum(v for d, v in final_margin_dist(lam_home, lam_away, phi).items() if d > 0)


def solve_split(reg_total: float, p_home: float, phi: float = REG_PHI) -> tuple[float, float]:
    """The pair of REGULATION means with the given sum that gives the home
    side exactly `p_home` to win the game. Monotone, so bisection."""
    lo, hi = 0.25, max(0.3, reg_total - 0.25)
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if p_home_wins(mid, reg_total - mid, phi) < p_home:
            lo = mid
        else:
            hi = mid
    lam_h = (lo + hi) / 2.0
    return lam_h, reg_total - lam_h


def puck_line_probs(lam_home: float, lam_away: float, home_line: float,
                    phi: float = REG_PHI) -> tuple[float, float, float]:
    """(P home covers, P push, P away covers) for the HOME side at home_line."""
    cover = push = fail = 0.0
    for d, v in final_margin_dist(lam_home, lam_away, phi).items():
        x = d + home_line
        if x > 1e-9:
            cover += v
        elif x < -1e-9:
            fail += v
        else:
            push += v
    return cover, push, fail


# ===========================================================================
# The matchup
# ===========================================================================

def forecast_matchup_nhl(
    away: str,
    home: str,
    *,
    total_line: float,
    over_price: float | None = None,
    under_price: float | None = None,
    home_ml: float | None = None,
    away_ml: float | None = None,
    puck_line: float | None = None,         # HOME side's line, e.g. -1.5
    pl_home_price: float | None = None,
    pl_away_price: float | None = None,
    p1_line: float | None = None,
    p1_over_price: float | None = None,
    p1_under_price: float | None = None,
    away_p1_last10: float | None = None,
    home_p1_last10: float | None = None,
    **total_inputs: Any,
) -> Matchup:
    notes: list[str] = []
    f = forecast_nhl(f"{away} @ {home}", total_line, over_price, under_price, **total_inputs)
    markets: list[Market] = [_total_market(f, total_line, over_price, under_price, 2)]

    anchor = next(e.total for e in f.estimates if e.name == "Market")
    lam_h = lam_a = None
    if home_ml is not None and away_ml is not None:
        p_home_mkt, _ = devig(home_ml, away_ml)
        ml_hold = hold(home_ml, away_ml)
        # The split is solved on the REGULATION means the anchor implies; the
        # empty net and overtime are added back by the margin distribution.
        lam_h0, lam_a0 = solve_split(reg_mean(anchor), p_home_mkt)
        scale = reg_mean(f.projected) / reg_mean(anchor)
        lam_h, lam_a = lam_h0 * scale, lam_a0 * scale
        notes.append(
            f"{home_ml:+.0f}/{away_ml:+.0f} de-vigs to {p_home_mkt * 100:.1f}% home "
            f"({ml_hold * 100:.1f}% hold). On the market's {reg_mean(anchor):.2f} regulation goals "
            f"that puts the split at {lam_a0:.2f} away, {lam_h0:.2f} home; the total forecast "
            f"moves both by x{scale:.3f}. The moneyline already knows the goalies, so nothing "
            "per-team moves this split -- the split IS the market.")
        if ml_hold > HOLD_REFERENCE:
            notes.append(f"A {ml_hold * 100:.1f}% moneyline hold is wide for a main line; only "
                         f"{market_confidence(ml_hold) * 100:.0f}% of the de-vigged lean is kept.")

        p_h = p_home_wins(lam_h, lam_a)
        markets.append(_pick(
            "ml", "Moneyline",
            [_side(f"{home} ML", "HOME", p_h, 0.0, home_ml),
             _side(f"{away} ML", "AWAY", 1.0 - p_h, 0.0, away_ml)],
            anchored=True,
            notes=["Priced off the book's own moneyline, overtime and the shootout included. "
                   "The only thing that can move it is the total forecast changing how often "
                   "the game is tied after sixty, and that is a small thing."]))

        pl = DEFAULT_PUCK_LINE if puck_line is None else puck_line
        home_line = puck_line if puck_line is not None else (-abs(pl) if p_home_mkt >= 0.5 else abs(pl))
        c, pu, fl = puck_line_probs(lam_h, lam_a, home_line)
        markets.append(_pick(
            "pl", f"Puck line {home}: {home_line:+g}",
            [_side(f"{home} {home_line:+g}", "HOME", c, pu, pl_home_price),
             _side(f"{away} {-home_line:+g}", "AWAY", fl, pu, pl_away_price)],
            anchored=pl_home_price is not None and pl_away_price is not None,
            notes=["Derived from the total and the moneyline through the goal distribution, "
                   "with the empty net on the margin: a one-goal regulation lead becomes a "
                   f"two-goal win {ENG_GIVEN_ONE_GOAL_LEAD:.0%} of the time, and an overtime "
                   "win is by one and never covers -1.5. Both figures are a priori. The run "
                   "line's record says to treat this as shown, not picked, until the log "
                   "says otherwise."]))
    else:
        notes.append("No moneyline entered, so there is no split and no moneyline or puck line "
                     "on this card. Both prices are needed.")

    if p1_line is not None:
        if not _ok(p1_line, "nhl_period"):
            raise ValueError(f"first-period total {p1_line!r} is outside {PLAUSIBLE['nhl_period']}")
        mu_p1, how = p1_anchor(p1_line, p1_over_price, p1_under_price)
        est: list[tuple[float, float]] = [(mu_p1, WEIGHTS["market"])]
        p1_notes = [f"Anchored on the first-period market: {how}"]
        goalies = next((e for e in f.estimates if e.name in ("Goalies", "Shot rates")), None)
        if goalies is not None:
            gap = (goalies.total - anchor) * P1_SHARE
            est.append((mu_p1 + gap, goalies.weight))
            p1_notes.append(f"{goalies.name}: {gap:+.2f} goals over the first period, the full-game "
                            f"gap scaled by the {P1_SHARE:.0%} of regulation goals a first period "
                            "carries. No empty net, no overtime: a period is a plain count.")
        # --- first-period form, from the league ledger -----------------------
        # Each club's last ten first-period totals (for plus against), the
        # first period's own last ten: an absolute, weighted like the full
        # game's form and tagged the same way. Fed by the slate from
        # nhl-ledger-<season>.json; blank until a club has MIN_TEAM_GAMES.
        # Added 5 Oct 2026 as the hockey counterpart of the F5 starters.
        if away_p1_last10 is not None or home_p1_last10 is not None:
            p1_notes.append(f"First-period last ten: {away_p1_last10 if away_p1_last10 is not None else '—'} and "
                            f"{home_p1_last10 if home_p1_last10 is not None else '—'} a game, from the league "
                            "ledger. SHOWN, NOT SCORED: measured against 2,445 first periods on 7 Oct 2026 "
                            "and null (slope -0.003). A period's recent past says nothing about tonight's.")
        tw = sum(wt for _, wt in est)
        proj_p1 = sum(t * wt for t, wt in est) / tw
        o, pu, u = p1_split(p1_line, proj_p1)
        markets.append(_pick(
            "p1", f"First period total {p1_line:g}",
            [_side(f"P1 OVER {p1_line:g}", "OVER", o, pu, p1_over_price),
             _side(f"P1 UNDER {p1_line:g}", "UNDER", u, pu, p1_under_price)],
            anchored=p1_over_price is not None and p1_under_price is not None,
            notes=p1_notes + [f"Projected {proj_p1:.2f} against {p1_line:g}."]))

    return Matchup("NHL", away, home, markets, lam_h, lam_a, f, notes)


# ===========================================================================
# Grading
# ===========================================================================

def _line_of(market: Market) -> float:
    import re
    if market.key in ("total", "p1"):
        m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*$", market.pick)
        return float(m.group(1)) if m else 0.0
    if market.key == "ml":
        return 0.0
    m = re.search(r"([+-][0-9]+(?:\.[0-9]+)?)\s*$", market.pick)
    v = float(m.group(1)) if m else 0.0
    return v if market.side == "HOME" else -v


def grade(market: Market, *, home_goals: float | None, away_goals: float | None,
          p1_home: float | None = None, p1_away: float | None = None) -> str | None:
    """'win' | 'loss' | 'push' | 'invalid' | None. The final score includes
    overtime and the shootout (a shootout win is a one-goal margin, as the
    league records it), which is what the moneyline and the puck line settle
    on. A first period that exceeds the final is 'invalid'."""
    key, side = market.key, market.side
    line = _line_of(market)
    if key in ("total", "p1"):
        if key == "p1":
            if p1_home is None or p1_away is None:
                return None
            if ((home_goals is not None and p1_home > home_goals + 1e-9)
                    or (away_goals is not None and p1_away > away_goals + 1e-9)):
                return "invalid"
            total = p1_home + p1_away
        else:
            if home_goals is None or away_goals is None:
                return None
            total = home_goals + away_goals
        if abs(total - line) < 1e-9:
            return "push"
        return "win" if ((total > line) if side == "OVER" else (total < line)) else "loss"
    if home_goals is None or away_goals is None:
        return None
    margin = home_goals - away_goals
    if key == "ml":
        return "win" if (margin > 0) == (side == "HOME") else "loss"
    x = margin + line
    if abs(x) < 1e-9:
        return "push"
    return "win" if (x > 0) == (side == "HOME") else "loss"
