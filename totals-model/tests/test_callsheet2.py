"""Call Sheet 2.0: one matchup, four markets, ranked by edge.

The tests are organised around the claims the module docstring makes, in the
same spirit as the full-game suite: every constant is either inherited or a
fraction of the game, the total is Call Sheet #1's total to the last digit,
and every derivative market reproduces the market it was anchored on when
nothing else is entered.
"""

from __future__ import annotations

import math
import unittest

from totals.callsheet2 import (
    DEFAULT_RUN_LINE, F5_PHI, F5_SHARE, TEAM_PHI, WNBA_MARGIN_SD, day_board,
    forecast_matchup_mlb, forecast_matchup_wnba, grade, margin_probs,
    p_home_wins, run_line_probs, solve_split, spread_probs,
)
from totals.fullgame import DISPERSION_PHI, devig, forecast_mlb, forecast_wnba, implied

RAYS = dict(
    away_starter_era=2.94, home_starter_era=2.95, away_starter_ip=171.1,
    home_starter_ip=76.1, away_rpg=4.03, home_rpg=3.72, away_bullpen_era=4.16,
    home_bullpen_era=3.13, away_last10_total=6.7, home_last10_total=10.0,
    h2h_total=7.6, h2h_meetings=9, park_factor=103, wind_mph=15,
    wind_direction="in", temp_f=65,
)
BOARD = dict(total_line=6.5, over_price=-120, under_price=105, home_ml=-150,
             away_ml=130, run_line=-1.5, rl_home_price=120, rl_away_price=-140,
             f5_line=3.5, f5_over_price=-115, f5_under_price=-105)

SUN = dict(away_pace=80.39, home_pace=78.79, away_off_rating=97.6,
           home_off_rating=104.2, away_def_rating=109.7, home_def_rating=103.4,
           away_rest_days=1, home_rest_days=1, away_last5_total=175.0,
           home_last5_total=172.2)


class TestTheConstantsAreInheritedOrFractions(unittest.TestCase):
    def test_the_team_dispersion_is_the_total_dispersion(self):
        """Independence between the two teams implies it; nothing is fitted."""
        self.assertEqual(TEAM_PHI, DISPERSION_PHI["MLB"])
        self.assertEqual(F5_PHI, DISPERSION_PHI["MLB"])

    def test_the_f5_share_is_five_ninths(self):
        self.assertAlmostEqual(F5_SHARE, 5.0 / 9.0, places=12)

    def test_the_wnba_margin_sd_is_the_retired_models(self):
        from totals.wnba import MARGIN_SD
        self.assertEqual(WNBA_MARGIN_SD, MARGIN_SD)


class TestTheTotalIsCallSheetOnesToTheLastDigit(unittest.TestCase):
    def test_mlb(self):
        m = forecast_matchup_mlb("Rays", "Yankees", **BOARD, **RAYS)
        one = forecast_mlb("Rays @ Yankees", 6.5, -120, 105, **RAYS)
        t = next(mk for mk in m.markets if mk.key == "total")
        self.assertAlmostEqual(m.total.projected, one.projected, places=12)
        self.assertAlmostEqual(t.p, one.p_resolved, places=12)
        self.assertEqual(t.side, one.side)
        self.assertEqual(t.band, one.band)

    def test_wnba(self):
        w = forecast_matchup_wnba("Sun", "Mystics", total_line=162.5, over_price=118,
                                  under_price=-155, spread=-4.5, **SUN)
        one = forecast_wnba("Sun @ Mystics", 162.5, over_price=118, under_price=-155, **SUN)
        t = next(mk for mk in w.markets if mk.key == "total")
        self.assertAlmostEqual(t.p, one.p_resolved, places=12)
        self.assertEqual(t.band, one.band)


class TestTheSplitReproducesTheMarket(unittest.TestCase):
    """The pair of means is solved to give the home side exactly what the
    moneyline says. That is the anchor, and it has to be exact."""

    def test_even_money_is_an_even_split(self):
        lh, la = solve_split(9.04, 0.5)
        self.assertAlmostEqual(lh, la, places=6)
        self.assertAlmostEqual(p_home_wins(lh, la), 0.5, places=8)

    def test_any_target_is_reproduced(self):
        for total, p in ((7.0, 0.58), (9.5, 0.44), (11.0, 0.70)):
            lh, la = solve_split(total, p)
            self.assertAlmostEqual(lh + la, total, places=9)
            self.assertAlmostEqual(p_home_wins(lh, la), p, places=7)

    def test_a_favourite_scores_more(self):
        lh, la = solve_split(8.0, 0.62)
        self.assertGreater(lh, la)

    def test_with_no_total_move_the_moneyline_market_is_the_market(self):
        """Bare card: total prices and a moneyline, nothing else. The
        moneyline probability on the card must be the de-vigged moneyline."""
        m = forecast_matchup_mlb("a", "b", total_line=8.5, over_price=-110,
                                 under_price=-110, home_ml=-140, away_ml=120)
        ml = next(mk for mk in m.markets if mk.key == "ml")
        p_home, _ = devig(-140, 120)
        p = ml.p if ml.side == "HOME" else 1.0 - ml.p
        self.assertAlmostEqual(p, p_home, places=6)
        # and so its edge is nothing but the vig
        self.assertLess(ml.edge, 0.0)


class TestTheDistributionSumsToOne(unittest.TestCase):
    def test_margin(self):
        w, t, l, _ = margin_probs(4.9, 4.1)
        self.assertAlmostEqual(w + t + l, 1.0, places=9)

    def test_run_line_half(self):
        c, p, f = run_line_probs(4.9, 4.1, -1.5)
        self.assertAlmostEqual(c + p + f, 1.0, places=9)
        self.assertEqual(p, 0.0)

    def test_run_line_whole_can_push(self):
        c, p, f = run_line_probs(4.9, 4.1, -1.0)
        self.assertAlmostEqual(c + p + f, 1.0, places=9)
        self.assertGreater(p, 0.05)

    def test_a_tie_after_nine_never_survives(self):
        """The tied mass is moved to +1 / -1, so a -1.5 line sees none of it
        as a push and a -1 line sees it all as a decided one-run game."""
        c15, _, f15 = run_line_probs(4.5, 4.5, -1.5)
        c1, p1, f1 = run_line_probs(4.5, 4.5, -1.0)
        # symmetric means: home covers -1.5 exactly as often as away covers +1.5
        # would for the mirror, i.e. c15 == P(margin >= 2)
        _, tie, _, dist = margin_probs(4.5, 4.5)
        self.assertAlmostEqual(c15, sum(v for d, v in dist.items() if d >= 2), places=9)
        self.assertAlmostEqual(p1, dist[1] + tie / 2, places=9)

    def test_spread_probs(self):
        for line in (-4.5, -4.0, 0.0, 3.5):
            c, p, f = spread_probs(2.0, line)
            self.assertAlmostEqual(c + p + f, 1.0, places=9)
        c, p, f = spread_probs(0.0, 0.0)
        self.assertEqual(p, 0.0)
        self.assertAlmostEqual(c, 0.5, places=9)


class TestRankedByEdgeNotProbability(unittest.TestCase):
    def test_a_heavy_favourite_ranks_below_a_priced_underdog(self):
        """A -300 favourite is 72% to hit and a losing bet; a +105 under at
        55% is the best bet on the board. The order must say so."""
        m = forecast_matchup_mlb("Rays", "Yankees", total_line=6.5, over_price=-120,
                                 under_price=105, home_ml=-300, away_ml=240, **RAYS)
        r = m.ranked()
        total = next(mk for mk in r if mk.key == "total")
        ml = next(mk for mk in r if mk.key == "ml")
        self.assertGreater(ml.p if ml.side == "HOME" else 1 - ml.p, total.p)
        self.assertLess(r.index(ml), 99)
        self.assertLess(r.index(total), r.index(ml))

    def test_the_side_picked_is_the_one_with_the_better_price(self):
        """Both sides of a market are evaluated. The pick is the side with
        the higher EDGE when prices are in, which can be the less likely side."""
        m = forecast_matchup_mlb("a", "b", total_line=8.5, over_price=-160,
                                 under_price=130, home_ml=-110, away_ml=-110)
        t = next(mk for mk in m.markets if mk.key == "total")
        # the market says over (-160), so P(over) > 0.5 -- but at -160 the over
        # needs 61.5% and the under at +130 needs 43.5%
        self.assertGreater(t.other_side["p"] if t.side == "UNDER" else t.p, 0.5)
        self.assertEqual(t.side, "UNDER")
        self.assertGreater(t.edge, t.other_side["edge"])

    def test_no_prices_means_the_likelier_side(self):
        m = forecast_matchup_mlb("a", "b", total_line=8.5, home_ml=-140, away_ml=120)
        rl = next(mk for mk in m.markets if mk.key == "rl")
        self.assertIsNone(rl.price)
        self.assertIsNone(rl.edge)
        self.assertGreaterEqual(rl.p, 0.5)

    def test_edge_is_probability_minus_the_prices_implied(self):
        m = forecast_matchup_mlb("Rays", "Yankees", **BOARD, **RAYS)
        for mk in m.markets:
            if mk.price is not None:
                self.assertAlmostEqual(mk.edge, mk.p - implied(mk.price), places=12)
                self.assertAlmostEqual(mk.breakeven, implied(mk.price), places=12)

    def test_unpriced_markets_sink_below_every_priced_one(self):
        m = forecast_matchup_mlb("a", "b", total_line=8.5, over_price=-110, under_price=-110,
                                 home_ml=-140, away_ml=120)
        r = m.ranked()
        priced = [mk.edge is not None for mk in r]
        self.assertEqual(priced, sorted(priced, reverse=True))


class TestWhatNeedsAMoneyline(unittest.TestCase):
    def test_no_moneyline_no_side_markets(self):
        m = forecast_matchup_mlb("a", "b", total_line=8.5, over_price=-110, under_price=-110)
        self.assertEqual([mk.key for mk in m.markets], ["total"])
        self.assertIsNone(m.lam_home)
        self.assertTrue(any("No moneyline" in n for n in m.notes))

    def test_the_run_line_follows_the_favourite_by_default(self):
        fav = forecast_matchup_mlb("a", "b", total_line=8.5, home_ml=-150, away_ml=130)
        dog = forecast_matchup_mlb("a", "b", total_line=8.5, home_ml=130, away_ml=-150)
        self.assertIn(f"{-DEFAULT_RUN_LINE:+g}", next(mk.label for mk in fav.markets if mk.key == "rl"))
        self.assertIn(f"{DEFAULT_RUN_LINE:+g}", next(mk.label for mk in dog.markets if mk.key == "rl"))

    def test_the_total_forecast_scales_both_means_together(self):
        """Wind blowing in lowers both teams' means in the same ratio; the
        split -- who scores more of them -- is the market's and does not move."""
        calm = forecast_matchup_mlb("a", "b", total_line=8.5, over_price=-110,
                                    under_price=-110, home_ml=-140, away_ml=120)
        windy = forecast_matchup_mlb("a", "b", total_line=8.5, over_price=-110,
                                     under_price=-110, home_ml=-140, away_ml=120,
                                     wind_mph=20, wind_direction="in", temp_f=70)
        self.assertLess(windy.total.projected, calm.total.projected)
        self.assertAlmostEqual(windy.lam_home / windy.lam_away,
                               calm.lam_home / calm.lam_away, places=9)


class TestTheFirstFive(unittest.TestCase):
    def test_anchored_on_its_own_market(self):
        m = forecast_matchup_mlb("a", "b", total_line=8.5, over_price=-110, under_price=-110,
                                 f5_line=4.5, f5_over_price=-120, f5_under_price=100)
        f5 = next(mk for mk in m.markets if mk.key == "f5")
        self.assertTrue(f5.anchored)
        # no starters entered: the F5 number is the F5 market's, de-vigged
        p_over, _ = devig(-120, 100)
        p = f5.p if f5.side == "OVER" else 1 - f5.p
        self.assertAlmostEqual(p, p_over, places=4)

    def test_bullpens_do_not_touch_it(self):
        base = dict(total_line=8.5, over_price=-110, under_price=-110,
                    f5_line=4.5, f5_over_price=-110, f5_under_price=-110)
        a = forecast_matchup_mlb("a", "b", **base)
        b = forecast_matchup_mlb("a", "b", away_bullpen_era=7.0, home_bullpen_era=7.0, **base)
        fa = next(mk for mk in a.markets if mk.key == "f5")
        fb = next(mk for mk in b.markets if mk.key == "f5")
        self.assertAlmostEqual(fa.p, fb.p, places=12)
        # while the full-game total did move
        self.assertNotAlmostEqual(a.total.projected, b.total.projected, places=3)

    def test_starters_do(self):
        base = dict(total_line=8.5, over_price=-110, under_price=-110,
                    f5_line=4.5, f5_over_price=-110, f5_under_price=-110)
        a = forecast_matchup_mlb("a", "b", **base)
        b = forecast_matchup_mlb("a", "b", away_starter_era=2.0, home_starter_era=2.0, **base)
        fa = next(mk for mk in a.markets if mk.key == "f5")
        fb = next(mk for mk in b.markets if mk.key == "f5")
        p_a = fa.p if fa.side == "UNDER" else 1 - fa.p
        p_b = fb.p if fb.side == "UNDER" else 1 - fb.p
        self.assertGreater(p_b, p_a)

    def test_whole_number_f5_can_push(self):
        m = forecast_matchup_mlb("a", "b", total_line=8.5, f5_line=4.0,
                                 f5_over_price=-110, f5_under_price=-110)
        f5 = next(mk for mk in m.markets if mk.key == "f5")
        self.assertGreater(f5.p_push, 0.1)

    def test_no_line_no_market(self):
        m = forecast_matchup_mlb("a", "b", total_line=8.5)
        self.assertFalse(any(mk.key == "f5" for mk in m.markets))


class TestTheWnbaSideMarkets(unittest.TestCase):
    def test_a_spread_with_prices_is_reproduced(self):
        w = forecast_matchup_wnba("a", "b", total_line=165.5, spread=-4.5,
                                  spread_home_price=-120, spread_away_price=100)
        sp = next(mk for mk in w.markets if mk.key == "spread")
        p_cover, _ = devig(-120, 100)
        p = sp.p if sp.side == "HOME" else 1 - sp.p
        self.assertAlmostEqual(p, p_cover, places=5)

    def test_a_pick_em_spread_is_a_coin_flip_moneyline(self):
        w = forecast_matchup_wnba("a", "b", total_line=165.5, spread=0.0,
                                  spread_home_price=-110, spread_away_price=-110)
        ml = next(mk for mk in w.markets if mk.key == "ml")
        self.assertAlmostEqual(ml.p, 0.5, places=6)

    def test_moneyline_alone_gives_a_margin(self):
        w = forecast_matchup_wnba("a", "b", total_line=165.5, home_ml=-200, away_ml=170)
        self.assertIsNotNone(w.lam_home)
        self.assertGreater(w.lam_home, w.lam_away)
        ml = next(mk for mk in w.markets if mk.key == "ml")
        p_home, _ = devig(-200, 170)
        p = ml.p if ml.side == "HOME" else 1 - ml.p
        self.assertAlmostEqual(p, p_home, places=6)

    def test_the_total_does_not_move_the_margin(self):
        base = dict(total_line=165.5, spread=-4.5, spread_home_price=-110, spread_away_price=-110)
        a = forecast_matchup_wnba("a", "b", **base)
        b = forecast_matchup_wnba("a", "b", away_pace=90, home_pace=90, **base)
        self.assertNotAlmostEqual(a.total.projected, b.total.projected, places=2)
        self.assertAlmostEqual(a.lam_home - a.lam_away, b.lam_home - b.lam_away, places=9)


class TestTheDayBoard(unittest.TestCase):
    def test_best_edge_first_and_same_game_is_flagged(self):
        m = forecast_matchup_mlb("Rays", "Yankees", **BOARD, **RAYS)
        w = forecast_matchup_wnba("Sun", "Mystics", total_line=162.5, over_price=118,
                                  under_price=-155, home_ml=-190, away_ml=160, spread=-4.5,
                                  spread_home_price=-110, spread_away_price=-110, **SUN)
        rows = day_board([m, w])
        edges = [r.market.edge for r in rows]
        self.assertEqual(edges, sorted(edges, reverse=True))
        self.assertEqual([r.rank for r in rows], list(range(1, len(rows) + 1)))
        second_same_game = next(r for r in rows[1:] if r.matchup == rows[0].matchup)
        self.assertIn(1, second_same_game.correlated_with)
        self.assertEqual(rows[0].correlated_with, [])

    def test_unpriced_markets_are_not_on_the_board(self):
        m = forecast_matchup_mlb("a", "b", total_line=8.5)
        self.assertEqual([mk.key for mk in m.markets], ["total"])
        self.assertIsNone(m.markets[0].edge)
        self.assertEqual(day_board([m]), [])
        # a priced moneyline alone puts exactly the priced markets on it
        n = forecast_matchup_mlb("a", "b", total_line=8.5, home_ml=-140, away_ml=120)
        self.assertEqual([r.market.key for r in day_board([n])], ["ml"])


class TestGrading(unittest.TestCase):
    def setUp(self):
        self.m = forecast_matchup_mlb("Rays", "Yankees", **BOARD, **RAYS)
        self.by = {mk.key: mk for mk in self.m.markets}

    def test_total(self):
        t = self.by["total"]          # UNDER 6.5
        self.assertEqual(t.side, "UNDER")
        self.assertEqual(grade(t, home_runs=1, away_runs=1), "win")
        self.assertEqual(grade(t, home_runs=5, away_runs=2), "loss")
        self.assertIsNone(grade(t, home_runs=None, away_runs=None))

    def test_moneyline(self):
        ml = self.by["ml"]
        home = ml.side == "HOME"
        self.assertEqual(grade(ml, home_runs=3, away_runs=1), "win" if home else "loss")
        self.assertEqual(grade(ml, home_runs=1, away_runs=3), "loss" if home else "win")

    def test_run_line(self):
        rl = self.by["rl"]            # Rays +1.5 (away) or Yankees -1.5 (home)
        away = rl.side == "AWAY"
        self.assertEqual(grade(rl, home_runs=3, away_runs=2), "win" if away else "loss")
        self.assertEqual(grade(rl, home_runs=5, away_runs=2), "loss" if away else "win")

    def test_first_five_needs_its_own_score(self):
        f5 = self.by["f5"]
        self.assertIsNone(grade(f5, home_runs=3, away_runs=2))
        under = f5.side == "UNDER"
        self.assertEqual(grade(f5, home_runs=3, away_runs=2, f5_home=2, f5_away=1),
                         "win" if under else "loss")

    def test_a_first_five_above_the_final_is_invalid_not_graded(self):
        f5 = self.by["f5"]
        self.assertEqual(grade(f5, home_runs=9, away_runs=2, f5_home=1, f5_away=10), "invalid")
        self.assertEqual(grade(f5, home_runs=1, away_runs=5, f5_home=2, f5_away=2), "invalid")
        self.assertIn(grade(f5, home_runs=1, away_runs=4, f5_home=1, f5_away=4), ("win", "loss", "push"))
        self.assertIn(grade(f5, home_runs=None, away_runs=None, f5_home=8, f5_away=0), ("win", "loss", "push"))

    def test_whole_number_pushes(self):
        m = forecast_matchup_mlb("a", "b", total_line=8.0, over_price=-110, under_price=-110,
                                 home_ml=-140, away_ml=120, run_line=-1.0,
                                 rl_home_price=-110, rl_away_price=-110)
        by = {mk.key: mk for mk in m.markets}
        self.assertEqual(grade(by["total"], home_runs=5, away_runs=3), "push")
        self.assertEqual(grade(by["rl"], home_runs=4, away_runs=3), "push")


if __name__ == "__main__":
    unittest.main()


class TestTheBandStaysWithCallSheetOnesSide(unittest.TestCase):
    """Found on the first live card with a lopsided quote: the total's BET
    chip was printed on the side this sheet picked for PRICE, which was the
    opposite of the side #1 had named. A BET on the over is not a BET on the
    under."""

    def test_the_band_travels_when_the_sides_agree(self):
        m = forecast_matchup_mlb("Rays", "Yankees", **BOARD, **RAYS)
        t = next(mk for mk in m.markets if mk.key == "total")
        self.assertEqual(t.side, m.total.side)
        self.assertEqual(t.band, m.total.band)

    def test_and_does_not_when_they_differ(self):
        # -170/+140 on 8.5: the market leans over hard, two good starters pull
        # the blend back to a modest over. #1 names OVER 54.8% and bands it;
        # the under at +140 needs only 41.7% and is the better price.
        m = forecast_matchup_mlb("a", "b", total_line=8.5, over_price=-170, under_price=140,
                                 home_ml=-110, away_ml=-110,
                                 away_starter_era=2.5, home_starter_era=2.5)
        t = next(mk for mk in m.markets if mk.key == "total")
        self.assertEqual(m.total.side, "OVER")
        self.assertNotEqual(m.total.band, "NO BET")
        self.assertEqual(t.side, "UNDER")
        self.assertEqual(t.band, "")
        self.assertTrue(any("picked on PRICE" in n for n in t.notes))
        self.assertTrue(any(m.total.band in n for n in t.notes))
