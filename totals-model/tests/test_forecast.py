"""Tests for the forecaster.

The earlier models were tested for restraint — most cases checked that a
plausible-looking edge still came back PASS. This one has no PASS, so what
needs locking in is different: that it always answers, that a missing input
re-weights rather than breaks, that the answer stays anchored to the market,
and that the probabilities never get flattering.
"""

import math
import unittest

from totals.forecast import (
    BANDS,
    H2H_FULL_WEIGHT_AT,
    h2h_weight,
    DISPERSION,
    F5_SHARE,
    F5_TOTAL,
    LEAGUE_ERA,
    PITCHER_CALIBRATION,
    WEIGHTS,
    Forecast,
    forecast_mlb_f5,
    forecast_wnba,
    normal_cdf,
    park_scale,
    slate,
    starter_f5_runs,
)


class TestItAlwaysAnswers(unittest.TestCase):
    """The whole point of the rewrite. There is no PASS to fall back on."""

    def test_a_bare_line_still_names_a_side(self):
        f = forecast_mlb_f5("A @ B", 4.5)
        self.assertIn(f.side, ("OVER", "UNDER"))
        self.assertEqual(f.band, "COIN FLIP")
        self.assertAlmostEqual(f.p_over, 0.5)
        self.assertIn("best estimate", " ".join(f.notes))

    def test_the_named_side_is_always_the_likelier_one(self):
        under = forecast_mlb_f5("A @ B", 6.0, away_starter_era=2.10,
                                home_starter_era=2.40)
        self.assertEqual(under.side, "UNDER")
        self.assertGreater(under.p_side, 0.5)
        self.assertLess(under.p_over, 0.5)

    def test_p_side_and_p_over_agree_on_the_over(self):
        f = forecast_mlb_f5("A @ B", 3.5, away_starter_era=6.90,
                            home_starter_era=6.40)
        self.assertEqual(f.side, "OVER")
        self.assertAlmostEqual(f.p_side, f.p_over)

    def test_every_band_is_reachable_and_ordered(self):
        floors = [floor for floor, _ in BANDS]
        self.assertEqual(floors, sorted(floors, reverse=True))
        seen = set()
        for line in (2.5, 3.5, 4.0, 4.5, 5.5, 7.5):
            seen.add(forecast_mlb_f5("A @ B", line, away_starter_era=5.40,
                                     home_starter_era=5.10).band)
        self.assertEqual(seen, {"MAX", "STRONG", "LEAN", "COIN FLIP"})


class TestMissingInputsReweight(unittest.TestCase):
    """"Restructure its weight" — the thing that was asked for by name."""

    def test_dropping_head_to_head_renormalises_the_rest(self):
        with_h2h = forecast_wnba("A @ B", 160.0, away_last10_total=170.0,
                                 home_last10_total=170.0, h2h_total=170.0,
                                 h2h_meetings=4)
        without = forecast_wnba("A @ B", 160.0, away_last10_total=170.0,
                                home_last10_total=170.0)
        # Every surviving estimate agrees on 170, so both blends sit between
        # 160 and 170 — but the market owns a larger share once h2h leaves.
        self.assertGreater(with_h2h.projected, without.projected)
        w = WEIGHTS["WNBA"]
        self.assertAlmostEqual(
            without.projected,
            (160.0 * w["market"] + 170.0 * w["form"]) / (w["market"] + w["form"]))

    def test_a_missing_input_never_costs_an_answer(self):
        f = forecast_wnba("A @ B", 165.0)
        self.assertIn(f.side, ("OVER", "UNDER"))
        self.assertIn("No head-to-head", " ".join(f.notes))

    def test_weights_are_shares_not_absolutes(self):
        """Doubling every weight must not change a single forecast.

        If it ever does, the blend has stopped being a weighted mean and has
        started summing adjustments — which is the shape that needed caps and
        produced the runaway numbers in the models this one replaces.
        """
        f = forecast_wnba("A @ B", 160.0, away_last10_total=175.0,
                          home_last10_total=171.0, h2h_total=180.0, h2h_meetings=5)
        original = dict(WEIGHTS["WNBA"])
        try:
            WEIGHTS["WNBA"] = {k: v * 2 for k, v in original.items()}
            doubled = forecast_wnba("A @ B", 160.0, away_last10_total=175.0,
                                    home_last10_total=171.0, h2h_total=180.0,
                                    h2h_meetings=5)
        finally:
            WEIGHTS["WNBA"] = original
        self.assertAlmostEqual(f.projected, doubled.projected)

    def test_one_starter_alone_is_not_scored(self):
        """Half a matchup is not an estimate of a total."""
        f = forecast_mlb_f5("A @ B", 4.5, away_starter_era=7.90)
        self.assertEqual([e.name for e in f.estimates], ["Market"])
        self.assertIn("Only one starter", " ".join(f.notes))


class TestHeadToHeadSampleSize(unittest.TestCase):
    """One meeting is information. It is not four meetings' worth of it.

    The old gate model refused to read a head-to-head under three meetings.
    Refusing is the wrong instinct for a forecaster that has to answer every
    card — the right move is to take the number and discount it.
    """

    def test_the_weight_scales_with_meetings_up_to_four(self):
        self.assertAlmostEqual(h2h_weight(1.0, 1), 0.25)
        self.assertAlmostEqual(h2h_weight(1.0, 2), 0.50)
        self.assertAlmostEqual(h2h_weight(1.0, 3), 0.75)
        self.assertAlmostEqual(h2h_weight(1.0, 4), 1.00)
        self.assertAlmostEqual(h2h_weight(1.0, 40), 1.00)
        self.assertAlmostEqual(h2h_weight(1.0, 0), 0.00)

    def test_one_meeting_moves_the_forecast_less_than_four_do(self):
        def p(n):
            return forecast_wnba("A @ B", 160.0, away_last10_total=165.0,
                                 home_last10_total=165.0, h2h_total=185.0,
                                 h2h_meetings=n).projected
        self.assertLess(p(1), p(2))
        self.assertLess(p(2), p(4))
        self.assertAlmostEqual(p(4), p(9))     # full weight, and no more

    def test_a_single_meeting_still_counts_for_something(self):
        """Entering it must beat leaving it out, or the advice is wrong."""
        without = forecast_wnba("A @ B", 160.0, away_last10_total=165.0,
                                home_last10_total=165.0)
        with_one = forecast_wnba("A @ B", 160.0, away_last10_total=165.0,
                                 home_last10_total=165.0, h2h_total=185.0,
                                 h2h_meetings=1)
        self.assertGreater(with_one.projected, without.projected)

    def test_a_thin_head_to_head_says_it_was_discounted(self):
        f = forecast_mlb_f5("A @ B", 4.5, h2h_total=13.0, h2h_meetings=1)
        h = next(e for e in f.estimates if e.name.startswith("Head"))
        self.assertIn("Discounted", h.detail)
        self.assertAlmostEqual(h.weight, WEIGHTS["MLB_F5"]["h2h"] / H2H_FULL_WEIGHT_AT)

    def test_a_full_head_to_head_does_not_claim_a_discount(self):
        f = forecast_mlb_f5("A @ B", 4.5, h2h_total=13.0, h2h_meetings=6)
        h = next(e for e in f.estimates if e.name.startswith("Head"))
        self.assertNotIn("Discounted", h.detail)
        self.assertAlmostEqual(h.weight, WEIGHTS["MLB_F5"]["h2h"])

    def test_one_meeting_cannot_outweigh_the_last_ten(self):
        f = forecast_wnba("A @ B", 160.0, away_last10_total=165.0,
                          home_last10_total=165.0, h2h_total=200.0, h2h_meetings=1)
        h = next(e for e in f.estimates if e.name.startswith("Head"))
        form = next(e for e in f.estimates if e.name == "Last 10")
        self.assertLess(h.weight, form.weight / 4)


class TestAnchoredToTheMarket(unittest.TestCase):
    """The one measured fact this project owns, and the reason for the shape."""

    def test_a_blend_can_never_leave_the_range_of_its_parts(self):
        """The structural replacement for coefficient caps.

        Earlier models summed adjustments, so a screaming input could run the
        projection anywhere and every term needed a ceiling bolted on. A
        weighted mean is bounded by its own inputs, so it needs none.
        """
        f = forecast_wnba("A @ B", 150.0, away_last10_total=200.0,
                          home_last10_total=205.0, h2h_total=210.0, h2h_meetings=6)
        totals = [e.total for e in f.estimates]
        self.assertGreaterEqual(f.projected, min(totals))
        self.assertLessEqual(f.projected, max(totals))

    def test_an_absurd_input_moves_the_answer_but_cannot_own_it(self):
        wild = forecast_wnba("A @ B", 160.0, away_last10_total=400.0,
                             home_last10_total=400.0)
        self.assertEqual(wild.side, "OVER")
        # form holds 1.6 of 4.6 — a third of the weight, and no more
        self.assertLess(wild.projected, 260.0)

    def test_the_market_holds_the_largest_single_weight_in_both_sports(self):
        for sport, weights in WEIGHTS.items():
            others = {k: v for k, v in weights.items() if k != "market"}
            self.assertGreater(weights["market"], max(others.values()),
                               f"{sport}: market must outweigh any single rival")

    def test_the_park_never_touches_the_market_anchor(self):
        """Park factor is already inside the posted number.

        Applying it to the line as well is the double count that put the
        fourteen-input model behind the naked line at 3.61 runs to 3.58.
        """
        coors = forecast_mlb_f5("A @ B", 5.5, park_factor=118)
        market = next(e for e in coors.estimates if e.name == "Market")
        self.assertAlmostEqual(market.total, 5.5)
        self.assertAlmostEqual(coors.projected, 5.5)

    def test_the_park_does_reach_the_statistical_estimates(self):
        neutral = forecast_mlb_f5("A @ B", 4.5, away_starter_era=4.30,
                                  home_starter_era=4.30, park_factor=100)
        hitters = forecast_mlb_f5("A @ B", 4.5, away_starter_era=4.30,
                                  home_starter_era=4.30, park_factor=118)
        self.assertGreater(hitters.projected, neutral.projected)

    def test_an_implausible_park_is_read_as_a_typo(self):
        self.assertAlmostEqual(park_scale(1.13), 1.0)
        self.assertAlmostEqual(park_scale(1130), 1.0)
        self.assertAlmostEqual(park_scale(None), 1.0)
        self.assertAlmostEqual(park_scale(113), 1.13)


class TestFirstFiveInnings(unittest.TestCase):
    def test_two_average_starters_project_the_league_average(self):
        """The calibration that keeps every projection unbiased.

        Raw ERA arithmetic gives 5.16 runs for a league-average pair against
        the 4.66 that F5 games actually average, because a starter's ERA is
        spread over innings that include the third time through the order.
        """
        self.assertAlmostEqual(2 * starter_f5_runs(LEAGUE_ERA), F5_TOTAL, places=6)
        self.assertLess(PITCHER_CALIBRATION, 1.0)

    def test_a_better_starter_lowers_the_projection(self):
        ace = starter_f5_runs(2.10)
        arsonist = starter_f5_runs(6.90)
        self.assertLess(ace, arsonist)

    def test_the_opposing_lineup_scales_the_assignment(self):
        """ERA alone cannot tell a 5.10 offence from a 3.60 one."""
        from totals.forecast import LEAGUE_RPG
        tough = starter_f5_runs(4.30, opponent_rpg=5.40)
        easy = starter_f5_runs(4.30, opponent_rpg=3.40)
        neutral = starter_f5_runs(4.30, opponent_rpg=LEAGUE_RPG)
        self.assertGreater(tough, neutral)
        self.assertLess(easy, neutral)
        self.assertAlmostEqual(neutral, starter_f5_runs(4.30))

    def test_form_and_h2h_are_converted_from_full_game(self):
        """They are entered full-game because that is what sites publish."""
        f = forecast_mlb_f5("A @ B", 4.5, away_last5_total=9.0, home_last5_total=9.0)
        form = next(e for e in f.estimates if e.name == "Recent form")
        self.assertAlmostEqual(form.total, 9.0 * F5_SHARE)
        self.assertLess(form.total, 9.0)

    def test_f5_is_less_noisy_than_the_full_game(self):
        """The reason F5 is a better-posed problem, not just a smaller one."""
        self.assertLess(DISPERSION["MLB_F5"], 4.39)
        self.assertAlmostEqual(DISPERSION["MLB_F5"], 4.39 * math.sqrt(F5_SHARE))

    def test_wind_is_scaled_to_five_innings(self):
        f = forecast_mlb_f5("A @ B", 4.5, wind_mph=28, wind_direction="out")
        wind = next(d for d in f.deltas if d.name == "Wind")
        # 20 mph over the dead zone, at the full-game 0.10 cut to F5's share
        self.assertAlmostEqual(wind.runs, 20 * 0.10 * F5_SHARE)
        self.assertLess(wind.runs, 20 * 0.10)

    def test_wind_in_and_out_are_mirror_images(self):
        out = forecast_mlb_f5("A @ B", 4.5, wind_mph=20, wind_direction="out")
        into = forecast_mlb_f5("A @ B", 4.5, wind_mph=20, wind_direction="in")
        self.assertAlmostEqual(out.deltas[0].runs, -into.deltas[0].runs)
        self.assertEqual(out.side, "OVER")
        self.assertEqual(into.side, "UNDER")

    def test_a_cross_wind_is_a_reading_worth_zero(self):
        f = forecast_mlb_f5("A @ B", 4.5, wind_mph=30, wind_direction="cross")
        self.assertAlmostEqual(f.deltas[0].runs, 0.0)
        self.assertIn("neither way", f.deltas[0].detail)

    def test_a_shut_roof_removes_the_weather_entirely(self):
        f = forecast_mlb_f5("A @ B", 4.5, wind_mph=30, wind_direction="out",
                            temp_f=98, dome=True)
        self.assertEqual([d.name for d in f.deltas], ["Roof shut"])
        self.assertAlmostEqual(f.projected, 4.5)

    def test_an_impossible_line_is_refused_rather_than_forecast(self):
        with self.assertRaises(ValueError):
            forecast_mlb_f5("A @ B", 45)          # full-game number in the F5 box
        with self.assertRaises(ValueError):
            forecast_wnba("A @ B", 8.5)           # F5 number in the WNBA box


class TestProbabilitiesStayHonest(unittest.TestCase):
    def test_a_full_run_of_f5_edge_is_not_a_lock(self):
        """One run is under a third of a standard deviation, even at F5."""
        f = forecast_mlb_f5("A @ B", 4.5, away_last5_total=20.0,
                            home_last5_total=20.0)
        self.assertGreater(f.edge_runs, 0.9)
        self.assertLess(f.p_side, 0.70)

    def test_the_probability_follows_the_dispersion_exactly(self):
        f = forecast_wnba("A @ B", 160.0, away_last10_total=180.0,
                          home_last10_total=180.0)
        self.assertAlmostEqual(
            f.p_over, normal_cdf((f.projected - f.line) / DISPERSION["WNBA"]))

    def test_a_dead_heat_resolves_to_the_over_by_rule(self):
        """Both implementations must break the tie the same way.

        A half-point disagreement between the Python and the browser flipped a
        card once. The rule is stated rather than left to floating point.
        """
        f = forecast_wnba("A @ B", 160.0, away_last10_total=160.0,
                          home_last10_total=160.0)
        self.assertAlmostEqual(f.p_over, 0.5)
        self.assertEqual(f.side, "OVER")

    def test_the_top_band_asks_you_to_check_the_inputs(self):
        f = forecast_wnba("A @ B", 150.0, away_last10_total=200.0,
                          home_last10_total=200.0)
        self.assertEqual(f.band, "MAX")
        self.assertIn("mistyped", " ".join(f.notes))


class TestWnbaAbsences(unittest.TestCase):
    def test_a_leading_scorer_costs_more_than_a_rotation_player(self):
        plain = forecast_wnba("A @ B", 160.0, away_starters_out=1)
        star = forecast_wnba("A @ B", 160.0, away_starters_out=1,
                             away_leading_scorer_out=True)
        self.assertLess(star.projected, plain.projected)
        self.assertAlmostEqual(plain.deltas[0].runs, -2.0)
        self.assertAlmostEqual(star.deltas[0].runs, -3.5)

    def test_absences_stack_across_both_teams(self):
        f = forecast_wnba("A @ B", 165.0, away_starters_out=2, home_starters_out=1)
        self.assertEqual(len(f.deltas), 2)
        self.assertAlmostEqual(sum(d.runs for d in f.deltas), -6.0)
        self.assertEqual(f.side, "UNDER")

    def test_a_healthy_card_carries_no_absence_delta(self):
        self.assertEqual(forecast_wnba("A @ B", 160.0).deltas, [])


class TestSlate(unittest.TestCase):
    def test_the_card_is_ordered_by_conviction(self):
        rows = [
            forecast_wnba("Thin @ Game", 160.0, away_last10_total=161.0,
                          home_last10_total=161.0),
            forecast_wnba("Loud @ Game", 150.0, away_last10_total=190.0,
                          home_last10_total=190.0),
        ]
        text = slate(rows)
        self.assertLess(text.index("Loud @ Game"), text.index("Thin @ Game"))

    def test_an_empty_card_says_so(self):
        self.assertIn("Nothing", slate([]))

    def test_every_row_names_a_side(self):
        rows = [forecast_mlb_f5(f"G{i} @ H", 4.5, away_last5_total=8.0 + i,
                                home_last5_total=9.0) for i in range(4)]
        for f in rows:
            self.assertIn(f.side, ("OVER", "UNDER"))
        self.assertNotIn("PASS", slate(rows))


class TestSerialisation(unittest.TestCase):
    def test_a_forecast_round_trips_the_numbers_the_page_needs(self):
        f = forecast_mlb_f5("PHI @ SEA", 4.5, away_starter_era=5.12,
                            home_starter_era=4.18, park_factor=93,
                            wind_mph=10.3, wind_direction="out")
        d = f.to_dict()
        self.assertEqual(d["side"], f.side)
        self.assertEqual(d["band"], f.band)
        self.assertAlmostEqual(d["p_over"], round(f.p_over, 4))
        self.assertEqual(len(d["estimates"]), len(f.estimates))
        self.assertEqual(len(d["deltas"]), len(f.deltas))

    def test_the_brief_prints_weight_shares_that_sum_to_a_hundred(self):
        f = forecast_wnba("A @ B", 160.0, away_last10_total=170.0,
                          home_last10_total=168.0, h2h_total=175.0, h2h_meetings=4)
        total = sum(e.weight for e in f.estimates)
        shares = [e.weight / total for e in f.estimates]
        self.assertAlmostEqual(sum(shares), 1.0)
        self.assertIn("% of weight", f.brief())


if __name__ == "__main__":
    unittest.main()
