"""Team totals: the same two-team split, read one side at a time."""

from __future__ import annotations

import math
import unittest

from totals.callsheet2 import (
    WNBA_MARGIN_SD, WNBA_TEAM_SD, forecast_matchup_mlb, forecast_matchup_wnba, grade,
    team_total_probs,
)
from totals.fullgame import WNBA_TOTAL_SD

BOARD = dict(total_line=6.5, over_price=-120, under_price=105, home_ml=-150, away_ml=130,
             away_tt_line=2.5, away_tt_over=-105, away_tt_under=-115,
             home_tt_line=3.5, home_tt_over=-120, home_tt_under=100)


class TestTheTeamSdIsDerived(unittest.TestCase):
    def test_from_the_total_and_margin_sds(self):
        self.assertAlmostEqual(WNBA_TEAM_SD, math.sqrt((WNBA_TOTAL_SD ** 2 + WNBA_MARGIN_SD ** 2) / 4), places=12)
        self.assertAlmostEqual(WNBA_TEAM_SD, 7.957, places=3)

    def test_the_implied_correlation_is_small_and_positive(self):
        rho = (WNBA_TOTAL_SD ** 2 - WNBA_MARGIN_SD ** 2) / (WNBA_TOTAL_SD ** 2 + WNBA_MARGIN_SD ** 2)
        self.assertGreater(rho, 0.0)
        self.assertLess(rho, 0.1)


class TestTheyComeOffTheSplit(unittest.TestCase):
    def test_both_appear_when_lines_are_given(self):
        m = forecast_matchup_mlb("Rays", "Yankees", **BOARD)
        keys = [mk.key for mk in m.markets]
        self.assertIn("tta", keys)
        self.assertIn("tth", keys)
        for mk in m.markets:
            if mk.key in ("tta", "tth"):
                self.assertFalse(mk.anchored)

    def test_the_probability_is_the_split_read_against_the_line(self):
        m = forecast_matchup_mlb("Rays", "Yankees", **BOARD)
        tta = next(mk for mk in m.markets if mk.key == "tta")
        o, pu, u = team_total_probs(m.lam_away, 2.5)
        p_under = u / (o + u)
        self.assertAlmostEqual(tta.p if tta.side == "UNDER" else 1 - tta.p, p_under, places=12)

    def test_a_better_side_scores_more_often_over_the_same_line(self):
        fav = forecast_matchup_mlb("a", "b", total_line=8.5, home_ml=-200, away_ml=170,
                                   home_tt_line=4.5, away_tt_line=4.5)
        by = {mk.key: mk for mk in fav.markets}
        p_home_over = by["tth"].p if by["tth"].side == "OVER" else 1 - by["tth"].p
        p_away_over = by["tta"].p if by["tta"].side == "OVER" else 1 - by["tta"].p
        self.assertGreater(p_home_over, p_away_over)

    def test_no_moneyline_no_team_total(self):
        m = forecast_matchup_mlb("a", "b", total_line=8.5, over_price=-110, under_price=-110,
                                 away_tt_line=4.5, away_tt_over=-110, away_tt_under=-110)
        self.assertEqual([mk.key for mk in m.markets], ["total"])
        self.assertTrue(any("cannot be priced without the moneyline" in n for n in m.notes))

    def test_a_whole_number_line_pushes(self):
        m = forecast_matchup_mlb("a", "b", total_line=8.5, home_ml=-110, away_ml=-110,
                                 away_tt_line=4.0, away_tt_over=-110, away_tt_under=-110)
        tta = next(mk for mk in m.markets if mk.key == "tta")
        self.assertGreater(tta.p_push, 0.1)

    def test_one_line_alone_is_fine(self):
        m = forecast_matchup_mlb("a", "b", total_line=8.5, home_ml=-110, away_ml=-110, home_tt_line=4.5)
        keys = [mk.key for mk in m.markets]
        self.assertIn("tth", keys)
        self.assertNotIn("tta", keys)
        self.assertIsNone(next(mk for mk in m.markets if mk.key == "tth").edge)

    def test_wnba_uses_the_derived_team_sd(self):
        w = forecast_matchup_wnba("Sun", "Mystics", total_line=162.5, spread=-4.5,
                                  spread_home_price=-110, spread_away_price=-110,
                                  home_tt_line=83.5, home_tt_over=-115, home_tt_under=-105)
        tth = next(mk for mk in w.markets if mk.key == "tth")
        # with the spread at -4.5 and total 162.5 the home mean is 83.5 exactly:
        # a discretised normal centred on a half-point line is a coin flip
        self.assertAlmostEqual(w.lam_home, 83.5, places=6)
        self.assertAlmostEqual(tth.p, 0.5, places=6)


class TestGradingTeamTotals(unittest.TestCase):
    def test_each_side_is_graded_on_its_own_runs(self):
        m = forecast_matchup_mlb("Rays", "Yankees", **BOARD)
        by = {mk.key: mk for mk in m.markets}
        tta, tth = by["tta"], by["tth"]
        # Rays 1, Yankees 1
        a_under = tta.side == "UNDER"
        h_under = tth.side == "UNDER"
        self.assertEqual(grade(tta, home_runs=1, away_runs=1), "win" if a_under else "loss")
        self.assertEqual(grade(tth, home_runs=1, away_runs=1), "win" if h_under else "loss")
        # Rays 6, Yankees 1: the away total is over, the home total under
        self.assertEqual(grade(tta, home_runs=1, away_runs=6), "loss" if a_under else "win")
        self.assertEqual(grade(tth, home_runs=1, away_runs=6), "win" if h_under else "loss")

    def test_needs_only_that_side(self):
        m = forecast_matchup_mlb("Rays", "Yankees", **BOARD)
        tta = next(mk for mk in m.markets if mk.key == "tta")
        self.assertIsNotNone(grade(tta, home_runs=None, away_runs=2))
        self.assertIsNone(grade(tta, home_runs=2, away_runs=None))

    def test_a_whole_number_pushes(self):
        m = forecast_matchup_mlb("a", "b", total_line=8.5, home_ml=-110, away_ml=-110,
                                 home_tt_line=4.0, home_tt_over=-110, home_tt_under=-110)
        tth = next(mk for mk in m.markets if mk.key == "tth")
        self.assertEqual(grade(tth, home_runs=4, away_runs=0), "push")


if __name__ == "__main__":
    unittest.main()
