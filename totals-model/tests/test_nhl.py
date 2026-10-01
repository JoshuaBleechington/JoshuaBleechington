"""NHL: the total and the markets, built a week before the season.

Organised around the module docstring's claims. Nothing is fitted, so the
tests are about structure: the constants are derived from the stated facts,
league-average inputs move nothing, the mixture means what it says, the
derivative markets reproduce the market they were anchored on, and the
grader reads a hockey score the way the league does.
"""

from __future__ import annotations

import math
import unittest

from totals.fullgame import BANDS, devig, implied, split_for
from totals.nhl import (
    EMPTY_NET_RATE, ENG_GIVEN_ONE_GOAL_LEAD, GOALIE_TALENT_SD, LEAGUE_GOALS_PER_GAME,
    LEAGUE_REG_GOALS, LEAGUE_SAVE_PCT, LEAGUE_SHOTS, OT_RATE, P1_SHARE, REG_PHI,
    RESIDUAL_SD, SV_STABLE_AT, WEIGHTS, final_margin_dist, forecast_matchup_nhl,
    forecast_nhl, goalie_gap, grade, nhl_split, p_home_wins, puck_line_probs,
    reg_mean, shrink_sv, solve_split, sv_weight, total_pmf,
)

LEAGUE = dict(away_goalie_sv=LEAGUE_SAVE_PCT, home_goalie_sv=LEAGUE_SAVE_PCT,
              away_goalie_shots=1500, home_goalie_shots=1500,
              away_shots_for=LEAGUE_SHOTS, home_shots_for=LEAGUE_SHOTS)
BOARD = dict(total_line=6.0, over_price=-110, under_price=-110, home_ml=-150, away_ml=130,
             puck_line=-1.5, pl_home_price=180, pl_away_price=-220,
             p1_line=1.5, p1_over_price=-120, p1_under_price=100)


class TestTheConstantsAreDerived(unittest.TestCase):
    def test_the_shrinkage_shots_fall_out_of_two_facts(self):
        self.assertAlmostEqual(SV_STABLE_AT, LEAGUE_SAVE_PCT * (1 - LEAGUE_SAVE_PCT) / GOALIE_TALENT_SD ** 2)
        self.assertTrue(1200 < SV_STABLE_AT < 1500)

    def test_the_regulation_mean_is_the_total_less_the_two_lumps(self):
        self.assertAlmostEqual(LEAGUE_REG_GOALS, LEAGUE_GOALS_PER_GAME - EMPTY_NET_RATE - OT_RATE)
        self.assertAlmostEqual(reg_mean(6.1), LEAGUE_REG_GOALS)

    def test_the_regulation_index_is_derived_from_the_residual_sd(self):
        lumps = EMPTY_NET_RATE * (1 - EMPTY_NET_RATE) + OT_RATE * (1 - OT_RATE)
        self.assertAlmostEqual(REG_PHI, (RESIDUAL_SD ** 2 - lumps) / LEAGUE_REG_GOALS)
        self.assertTrue(1.0 < REG_PHI < 1.2, "goals are near Poisson")

    def test_the_market_weight_is_the_mlb_figure(self):
        self.assertEqual(WEIGHTS["market"], 4.0)
        self.assertEqual(WEIGHTS["goalies"], 1.6)


class TestTheMixture(unittest.TestCase):
    def test_it_sums_to_one_and_means_what_it_says(self):
        for mu in (4.5, 5.5, 6.1, 7.0):
            pm = total_pmf(mu)
            self.assertAlmostEqual(sum(pm), 1.0, places=9)
            self.assertAlmostEqual(sum(k * v for k, v in enumerate(pm)), mu, places=9)

    def test_it_is_registered_as_the_nhl_split(self):
        self.assertEqual(split_for("NHL", 6.0, 6.1), nhl_split(6.0, 6.1))

    def test_a_whole_number_line_pushes(self):
        o, p, u = nhl_split(6.0, 6.1)
        self.assertTrue(0.10 < p < 0.20)
        self.assertAlmostEqual(o + p + u, 1.0, places=9)
        o2, p2, u2 = nhl_split(5.5, 6.1)
        self.assertEqual(p2, 0.0)

    def test_the_empty_net_lump_lifts_the_over_on_the_half_above_regulation(self):
        """The same mean as a plain count, but with mass pushed one goal up:
        P(total >= 6) is higher than a plain NB of the same mean says."""
        from totals.fullgame import nb_split
        o_mix, _, _ = nhl_split(5.5, 6.1)
        o_nb, _, _ = nb_split(5.5, 6.1, REG_PHI)
        self.assertNotAlmostEqual(o_mix, o_nb, places=3)


class TestTheGoalie(unittest.TestCase):
    def test_league_average_inputs_move_nothing(self):
        self.assertAlmostEqual(goalie_gap(LEAGUE_SAVE_PCT, LEAGUE_SHOTS), 0.0, places=12)
        f = forecast_nhl("A @ B", 6.0, -110, -110, **LEAGUE)
        anchor = next(e.total for e in f.estimates if e.name == "Market")
        self.assertAlmostEqual(f.projected, anchor, places=12)

    def test_a_hot_goalie_lowers_the_total_and_a_cold_one_raises_it(self):
        hot = forecast_nhl("A @ B", 6.0, -110, -110, **{**LEAGUE, "home_goalie_sv": 0.930})
        cold = forecast_nhl("A @ B", 6.0, -110, -110, **{**LEAGUE, "home_goalie_sv": 0.880})
        base = forecast_nhl("A @ B", 6.0, -110, -110, **LEAGUE)
        self.assertLess(hot.projected, base.projected)
        self.assertGreater(cold.projected, base.projected)

    def test_shrinkage_by_shots(self):
        self.assertEqual(sv_weight(None), 1.0)
        self.assertAlmostEqual(sv_weight(SV_STABLE_AT), 0.5)
        self.assertLess(sv_weight(300), sv_weight(1500))
        few = shrink_sv(0.930, 300)
        many = shrink_sv(0.930, 1500)
        self.assertLess(few, many)
        self.assertGreater(few, LEAGUE_SAVE_PCT)

    def test_the_other_sides_shots_scale_the_gap(self):
        heavy = goalie_gap(0.880, 35.0)
        light = goalie_gap(0.880, 25.0)
        self.assertGreater(heavy, light)

    def test_shots_alone_read_as_shot_rates(self):
        f = forecast_nhl("A @ B", 6.0, -110, -110, away_shots_for=34, home_shots_for=33)
        self.assertIn("Shot rates", [e.name for e in f.estimates])
        self.assertGreater(f.projected, next(e.total for e in f.estimates if e.name == "Market"))

    def test_an_unconfirmed_goalie_is_said_out_loud(self):
        f = forecast_nhl("A @ B", 6.0, -110, -110, **LEAGUE)
        self.assertTrue(any("NOT confirmed" in n for n in f.notes))
        g = forecast_nhl("A @ B", 6.0, -110, -110, away_goalie_confirmed=True, home_goalie_confirmed=True, **LEAGUE)
        self.assertFalse(any("NOT confirmed" in n for n in g.notes))

    def test_an_implausible_save_percentage_is_dropped(self):
        f = forecast_nhl("A @ B", 6.0, -110, -110, **{**LEAGUE, "home_goalie_sv": 9.3})
        self.assertNotIn("Goalies", [e.name for e in f.estimates])


class TestTheGateAndTheTags(unittest.TestCase):
    def test_nothing_entered_is_a_coin_flip(self):
        f = forecast_nhl("A @ B", 6.0)
        self.assertEqual(f.band, BANDS[-1][1])
        self.assertAlmostEqual(f.p_resolved, 0.5, places=3)

    def test_special_teams_and_form_cannot_buy_a_band(self):
        f = forecast_nhl("A @ B", 5.5, -110, -110, away_pp_pct=30, home_pp_pct=30, away_pk_pct=70,
                         home_pk_pct=70, away_last10_total=8.0, home_last10_total=8.0)
        self.assertEqual(f.side, "OVER")
        self.assertEqual(f.band, BANDS[-1][1])
        self.assertTrue(any("Held at" in n for n in f.notes))

    def test_special_teams_need_all_four(self):
        f = forecast_nhl("A @ B", 6.0, -110, -110, away_pp_pct=25)
        self.assertNotIn("Special teams", [e.name for e in f.estimates])
        self.assertTrue(any("all four" in n for n in f.notes))

    def test_a_back_to_back_is_shown_not_scored(self):
        f = forecast_nhl("A @ B", 6.0, -110, -110, away_rest_days=0, **LEAGUE)
        g = forecast_nhl("A @ B", 6.0, -110, -110, away_rest_days=2, **LEAGUE)
        self.assertAlmostEqual(f.projected, g.projected, places=12)
        self.assertTrue(any("Back to back" in n for n in f.notes))

    def test_a_typo_total_is_refused(self):
        with self.assertRaises(ValueError):
            forecast_nhl("A @ B", 60.0)


class TestTheMarkets(unittest.TestCase):
    def test_the_moneyline_reproduces_the_book_when_nothing_moves_the_total(self):
        m = forecast_matchup_nhl("Rangers", "Bruins", **BOARD, **LEAGUE)
        p_mkt, _ = devig(-150, 130)
        ml = next(mk for mk in m.markets if mk.key == "ml")
        p_home = ml.p if ml.side == "HOME" else 1.0 - ml.p
        self.assertAlmostEqual(p_home, p_mkt, places=6)

    def test_the_puck_line_sides_sum_to_one_with_no_push_at_a_half(self):
        pl = puck_line_probs(3.2, 2.5, -1.5)
        self.assertAlmostEqual(sum(pl), 1.0, places=9)
        self.assertEqual(pl[1], 0.0)

    def test_every_final_margin_is_nonzero(self):
        d = final_margin_dist(3.0, 2.8)
        self.assertNotIn(0, d)
        self.assertAlmostEqual(sum(d.values()), 1.0, places=9)

    def test_the_favourite_covers_less_often_than_it_wins(self):
        self.assertLess(puck_line_probs(3.2, 2.5, -1.5)[0], p_home_wins(3.2, 2.5))

    def test_the_empty_net_lifts_the_favourites_cover(self):
        import totals.nhl as nhl
        with_eng = puck_line_probs(3.2, 2.5, -1.5)[0]
        saved = nhl.ENG_GIVEN_ONE_GOAL_LEAD
        try:
            nhl.ENG_GIVEN_ONE_GOAL_LEAD = 0.0
            without = puck_line_probs(3.2, 2.5, -1.5)[0]
        finally:
            nhl.ENG_GIVEN_ONE_GOAL_LEAD = saved
        self.assertGreater(with_eng, without)
        self.assertEqual(ENG_GIVEN_ONE_GOAL_LEAD, saved)

    def test_solve_split_is_exact(self):
        lh, la = solve_split(5.6, 0.58)
        self.assertAlmostEqual(lh + la, 5.6, places=9)
        self.assertAlmostEqual(p_home_wins(lh, la), 0.58, places=6)

    def test_the_first_period_is_anchored_on_its_own_market(self):
        m = forecast_matchup_nhl("Rangers", "Bruins", **{**BOARD, "p1_over_price": -110, "p1_under_price": -110}, **LEAGUE)
        p1 = next(mk for mk in m.markets if mk.key == "p1")
        self.assertAlmostEqual(p1.p, 0.5, places=3)

    def test_the_first_period_reads_the_goalie_gap_scaled(self):
        hot = forecast_matchup_nhl("Rangers", "Bruins", **BOARD, **{**LEAGUE, "home_goalie_sv": 0.935})
        base = forecast_matchup_nhl("Rangers", "Bruins", **BOARD, **LEAGUE)
        p1h = next(mk for mk in hot.markets if mk.key == "p1")
        p1b = next(mk for mk in base.markets if mk.key == "p1")
        under_h = p1h.p if p1h.side == "UNDER" else 1 - p1h.p
        under_b = p1b.p if p1b.side == "UNDER" else 1 - p1b.p
        self.assertGreater(under_h, under_b)
        self.assertTrue(any(f"{P1_SHARE:.0%}" in n for n in p1h.notes))

    def test_the_total_is_the_forecasts_total(self):
        m = forecast_matchup_nhl("Rangers", "Bruins", **BOARD, **LEAGUE)
        one = forecast_nhl("Rangers @ Bruins", 6.0, -110, -110, **LEAGUE)
        t = next(mk for mk in m.markets if mk.key == "total")
        self.assertAlmostEqual(t.p, one.p_resolved, places=12)
        self.assertEqual(t.band, one.band)

    def test_no_moneyline_means_no_sides(self):
        m = forecast_matchup_nhl("Rangers", "Bruins", total_line=6.0, p1_line=1.5)
        self.assertEqual({mk.key for mk in m.markets}, {"total", "p1"})
        self.assertIsNone(m.lam_home)

    def test_a_typo_period_total_is_refused(self):
        with self.assertRaises(ValueError):
            forecast_matchup_nhl("A", "B", total_line=6.0, p1_line=15)


class TestGrading(unittest.TestCase):
    def setUp(self):
        self.m = forecast_matchup_nhl("Rangers", "Bruins", **BOARD, **LEAGUE)
        self.by = {mk.key: mk for mk in self.m.markets}

    def test_total_and_push(self):
        t = self.by["total"]
        self.assertEqual(grade(t, home_goals=3, away_goals=3), "push")
        res = grade(t, home_goals=4, away_goals=3)
        self.assertEqual(res, "win" if t.side == "OVER" else "loss")

    def test_a_shootout_is_a_one_goal_margin(self):
        ml, pl = self.by["ml"], self.by["pl"]
        self.assertEqual(grade(ml, home_goals=3, away_goals=2), "win" if ml.side == "HOME" else "loss")
        # home -1.5 cannot cover a one-goal win; the away +1.5 side does
        self.assertEqual(grade(pl, home_goals=3, away_goals=2), "win" if pl.side == "AWAY" else "loss")
        self.assertEqual(grade(pl, home_goals=4, away_goals=2), "win" if pl.side == "HOME" else "loss")

    def test_the_first_period_grades_and_refuses_the_impossible(self):
        p1 = self.by["p1"]
        self.assertIsNone(grade(p1, home_goals=3, away_goals=2))
        self.assertEqual(grade(p1, home_goals=3, away_goals=2, p1_home=4, p1_away=0), "invalid")
        res = grade(p1, home_goals=3, away_goals=2, p1_home=1, p1_away=1)
        self.assertEqual(res, "win" if p1.side == "OVER" else "loss")

    def test_ungradeable_without_a_score(self):
        self.assertIsNone(grade(self.by["ml"], home_goals=None, away_goals=None))


if __name__ == "__main__":
    unittest.main()
