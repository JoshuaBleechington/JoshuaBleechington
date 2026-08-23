"""Tests for the late-factor model.

The thing being locked in here is mostly restraint: that the model refuses to
produce an edge it cannot justify, that it separates documented coefficients
from placeholders, and that a run of adjustment converts to a believable win
probability rather than a flattering one.
"""

import unittest

from totals.late import (
    BREAKEVEN_110,
    RESIDUAL_SD,
    Adjustment,
    band_for,
    closing_line_value,
    decide_late,
    umpire_adjustment,
    wind_adjustment,
)


def game(**over):
    g = {
        "away": {"name": "Texas"},
        "home": {"name": "Anaheim"},
        "weather": {},
        "line": 8.5,
    }
    g.update(over)
    return g


class TestNoEdgeIsAnAnswer(unittest.TestCase):
    def test_a_game_with_no_late_factor_gets_no_edge_and_says_why(self):
        r = decide_late(game())
        self.assertEqual(r.band, "NO EDGE")
        self.assertEqual(r.adjustments, [])
        self.assertAlmostEqual(r.total_runs, 0.0)
        self.assertIn("genuine no-bet", " ".join(r.notes))

    def test_season_statistics_are_not_an_input_at_all(self):
        """The old model's entire feature set is ignored, by design.

        Ridge on those fourteen inputs, leave-one-out, gave a negative
        out-of-sample R-squared at every regularisation strength. Feeding them
        in here would reproduce that.
        """
        loaded = game()
        loaded["away"].update(runs_per_game=5.8, starter_era=2.1, bullpen_era=5.6)
        loaded["home"].update(runs_per_game=3.7, starter_era=6.9, bullpen_era=3.1)
        loaded["park_factor"] = 113
        self.assertEqual(decide_late(loaded).band, "NO EDGE")

    def test_a_missing_line_is_an_error_not_a_default(self):
        g = game()
        del g["line"]
        with self.assertRaises(ValueError):
            decide_late(g)


class TestUmpire(unittest.TestCase):
    def test_a_big_sample_keeps_most_of_its_gap(self):
        a = umpire_adjustment({"umpire": {"name": "X", "runs_per_game": 9.2,
                                          "games": 360, "league_runs_per_game": 8.6}})
        self.assertEqual(a.basis, "documented")
        # 0.6 raw, shrunk by 360/(360+120) = 0.75
        self.assertAlmostEqual(a.runs, 0.45, places=6)

    def test_a_thin_sample_keeps_almost_none_of_it(self):
        a = umpire_adjustment({"umpire": {"runs_per_game": 9.2, "games": 20,
                                          "league_runs_per_game": 8.6}})
        self.assertAlmostEqual(a.runs, 0.6 * (20 / 140), places=6)
        self.assertLess(abs(a.runs), 0.1)

    def test_no_games_means_no_claim(self):
        a = umpire_adjustment({"umpire": {"runs_per_game": 12.0}})
        self.assertAlmostEqual(a.runs, 0.0)

    def test_absent_umpire_produces_nothing_rather_than_zero(self):
        self.assertIsNone(umpire_adjustment({}))


class TestWind(unittest.TestCase):
    def test_a_light_wind_does_nothing(self):
        a = wind_adjustment({"weather": {"wind_mph": 6, "wind_direction": "out"}})
        self.assertAlmostEqual(a.runs, 0.0)

    def test_out_and_in_are_mirror_images(self):
        out = wind_adjustment({"weather": {"wind_mph": 18, "wind_direction": "out"}})
        into = wind_adjustment({"weather": {"wind_mph": 18, "wind_direction": "in"}})
        self.assertAlmostEqual(out.runs, -into.runs)
        self.assertAlmostEqual(out.runs, 1.0, places=6)

    def test_a_cross_wind_is_explicitly_nothing(self):
        a = wind_adjustment({"weather": {"wind_mph": 25, "wind_direction": "cross"}})
        self.assertAlmostEqual(a.runs, 0.0)
        self.assertIn("across the field", a.detail)

    def test_the_effect_is_capped(self):
        a = wind_adjustment({"weather": {"wind_mph": 60, "wind_direction": "out"}})
        self.assertAlmostEqual(a.runs, 1.5)

    def test_a_closed_roof_settles_it(self):
        a = wind_adjustment({"weather": {"dome": True, "wind_mph": 30,
                                         "wind_direction": "out"}})
        self.assertAlmostEqual(a.runs, 0.0)

    def test_a_speed_with_no_direction_is_not_usable(self):
        self.assertIsNone(wind_adjustment({"weather": {"wind_mph": 20}}))


class TestProbabilities(unittest.TestCase):
    def test_a_run_of_edge_is_only_a_quarter_of_a_standard_deviation(self):
        """The restraint that makes the numbers believable.

        RESIDUAL_SD is measured, not chosen: 4.39 runs, from the 116 settled
        games in the track record. It is why an honest edge here reads 53%,
        not 62%.
        """
        r = decide_late(game(umpire={"runs_per_game": 9.6, "games": 100000,
                                     "league_runs_per_game": 8.6}))
        self.assertAlmostEqual(r.total_runs, 1.0, places=2)
        self.assertLess(r.win_pct, 0.60)
        self.assertGreater(r.win_pct, 0.55)

    def test_a_typical_real_edge_lands_just_past_breakeven(self):
        r = decide_late(game(weather={"wind_mph": 13, "wind_direction": "out",
                                      "temp_f": 70}))
        self.assertAlmostEqual(r.total_runs, 0.5, places=2)
        self.assertEqual(r.side, "OVER")
        self.assertGreater(r.win_pct, BREAKEVEN_110)
        self.assertLess(r.win_pct, 0.56)

    def test_the_first_band_that_names_a_bet_starts_above_breakeven(self):
        self.assertEqual(band_for(BREAKEVEN_110 - 0.001), "NO EDGE")
        self.assertEqual(band_for(BREAKEVEN_110), "SLIM")
        self.assertEqual(band_for(0.54), "PLAYABLE")
        self.assertEqual(band_for(0.57), "STRONG")

    def test_wind_blowing_in_takes_the_under(self):
        r = decide_late(game(weather={"wind_mph": 20, "wind_direction": "in"}))
        self.assertEqual(r.side, "UNDER")
        self.assertLess(r.total_runs, 0)


class TestHonestyAboutCoefficients(unittest.TestCase):
    def test_documented_and_provisional_are_reported_separately(self):
        r = decide_late(game(
            umpire={"runs_per_game": 9.0, "games": 240, "league_runs_per_game": 8.6},
            away={"name": "Texas", "relievers_unavailable": 2},
        ))
        self.assertGreater(r.documented_runs, 0)
        self.assertGreater(r.provisional_runs, 0)
        bases = {a.name: a.basis for a in r.adjustments}
        self.assertEqual(bases["Umpire"], "documented")
        self.assertEqual(bases["Bullpen availability"], "provisional")

    def test_an_edge_resting_mostly_on_placeholders_says_so(self):
        r = decide_late(game(
            away={"name": "Texas", "relievers_unavailable": 3},
            home={"name": "Anaheim", "relievers_unavailable": 2},
        ))
        self.assertIn("have not been backtested", " ".join(r.notes))

    def test_a_large_adjustment_asks_you_to_check_the_inputs(self):
        r = decide_late(game(
            umpire={"runs_per_game": 10.2, "games": 100000, "league_runs_per_game": 8.6},
        ))
        self.assertIn("Check the inputs", " ".join(r.notes))


class TestClosingLineValue(unittest.TestCase):
    def test_the_over_wants_the_number_to_go_up(self):
        self.assertTrue(closing_line_value(8.0, 8.5, "OVER")["beat_close"])
        self.assertFalse(closing_line_value(8.0, 7.5, "OVER")["beat_close"])

    def test_the_under_wants_the_number_to_go_down(self):
        self.assertTrue(closing_line_value(8.5, 8.0, "UNDER")["beat_close"])
        self.assertFalse(closing_line_value(8.5, 9.0, "UNDER")["beat_close"])

    def test_no_move_is_neither_won_nor_lost(self):
        r = closing_line_value(8.5, 8.5, "OVER")
        self.assertTrue(r["no_move"])
        self.assertFalse(r["beat_close"])


if __name__ == "__main__":
    unittest.main()
