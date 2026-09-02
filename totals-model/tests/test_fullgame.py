"""Tests for the full-game model.

The first block is the most important thing in this file. The model this
replaces carried a permanent over-lean because its calibration anchor was a
number I picked, and a game with no information in it came back OVER 50.8%.
These tests pin the property that makes that impossible: anything league
average moves the forecast by exactly zero, as arithmetic rather than as a
calibration that happened to come out right.
"""

import math
import unittest

from totals.fullgame import (
    BANDS,
    BULLPEN_INNINGS,
    DISPERSION_PHI,
    H2H_FULL_WEIGHT_AT,
    LEAGUE_BULLPEN_ERA,
    LEAGUE_COMBINED_RPG,
    LEAGUE_STARTER_ERA,
    RESIDUAL_SD,
    STARTER_INNINGS,
    WEIGHTS,
    arm_differential,
    calibration,
    devig,
    fair_total,
    forecast_mlb,
    forecast_wnba,
    h2h_weight,
    implied,
    nb_pmf,
    nb_split,
    park_scale,
    sensitivity,
    slate,
    split_for,
)


class TestNoHiddenLean(unittest.TestCase):
    """The bug that killed the previous model, pinned shut.

    It anchored its pitcher estimate to a league-average total I derived from
    two numbers I chose, and books post a different one, so every projection
    carried +0.16 runs toward the over before anything was read.
    """

    def test_an_empty_card_is_exactly_a_coin_flip(self):
        for line in (7.0, 7.5, 8.0, 8.5, 9.0, 9.5, 10.5, 12.0):
            f = forecast_mlb("a @ b", line)
            self.assertAlmostEqual(f.p_resolved, 0.5, places=9,
                                   msg=f"line {line} leaned {f.side} {f.p_resolved}")
            # and the two sides are even in raw terms too, with the push carved
            # out of both rather than taken from one
            self.assertAlmostEqual(f.p_over, f.p_under, places=9)

    def test_league_average_everything_moves_nothing(self):
        f = forecast_mlb(
            "a @ b", 8.5,
            away_starter_era=LEAGUE_STARTER_ERA, home_starter_era=LEAGUE_STARTER_ERA,
            away_bullpen_era=LEAGUE_BULLPEN_ERA, home_bullpen_era=LEAGUE_BULLPEN_ERA,
            park_factor=100, temp_f=70.0, wind_mph=5, wind_direction="out")
        self.assertAlmostEqual(f.p_resolved, 0.5, places=9)

    def test_a_league_average_arm_has_a_zero_differential(self):
        self.assertAlmostEqual(
            arm_differential(LEAGUE_STARTER_ERA, LEAGUE_STARTER_ERA, STARTER_INNINGS, None), 0.0)
        self.assertAlmostEqual(
            arm_differential(LEAGUE_BULLPEN_ERA, LEAGUE_BULLPEN_ERA, BULLPEN_INNINGS, None), 0.0)

    def test_the_differential_is_anchored_to_fair_and_not_to_the_line(self):
        """The second half of the same bug, found while fixing the first.

        A posted line is the point that splits the two sides evenly, and for a
        right-skewed count distribution the mean sits above it. Anchoring the
        differentials to the LINE while the market estimate sits at the FAIR
        MEAN made two league-average staffs come back UNDER 51.9%.
        """
        f = forecast_mlb("a @ b", 8.5, away_starter_era=LEAGUE_STARTER_ERA,
                         home_starter_era=LEAGUE_STARTER_ERA)
        market = next(e for e in f.estimates if e.name == "Market")
        starters = next(e for e in f.estimates if e.name == "Starters")
        self.assertAlmostEqual(starters.total, market.total, places=9)
        self.assertGreater(market.total, 8.5, "the fair mean must exceed the line")

    def test_the_error_a_wrong_league_constant_can_cause_is_small(self):
        """Differential form is what buys this.

        The league numbers cannot be verified from inside the sandbox, so what
        matters is that being wrong about them is cheap. A 0.20 ERA error moves
        a projection by well under a tenth of a run; the anchor bug it replaced
        was worth 0.16 runs permanently.
        """
        s = sensitivity(0.20)
        self.assertLess(s["runs_on_projection"], 0.10)
        self.assertGreater(s["runs_on_projection"], 0.0)
        # and it scales linearly, so a catastrophic 1.0 error is still bounded
        self.assertLess(sensitivity(1.0)["runs_on_projection"], 0.40)


class TestPushesArePricedOut(unittest.TestCase):
    """A push refunds, so it sits outside the pricing and outside the band.

    Both of these were wrong on the first pass. Matching a de-vigged price to
    the UNCONDITIONAL P(over) made an empty card on a total of 8 come back over
    50.0 / under 40.5 -- a lean the market never expressed. And cutting the band
    from the raw probability called a 52.2% bet a coin flip because 9.6% of the
    mass sat on the number.
    """

    def test_an_even_market_on_a_pushable_line_is_even_on_both_sides(self):
        for line in (8, 9, 10):
            f = forecast_mlb("a @ b", line, over_price=-110, under_price=-110)
            self.assertAlmostEqual(f.p_over, f.p_under, places=9)
            self.assertGreater(f.p_push, 0.05)
            self.assertAlmostEqual(f.p_resolved, 0.5, places=9)
            self.assertAlmostEqual(f.fair_price, 100.0, places=6)

    def test_the_same_prices_give_the_same_resolved_odds_push_or_not(self):
        """A total of 8 and 8.5 at the same price describe the same bet in
        resolved terms; only the push mass differs."""
        for op, up in ((-120, 100), (-140, 120), (-105, -115)):
            whole = forecast_mlb("a @ b", 8, over_price=op, under_price=up)
            half = forecast_mlb("a @ b", 8.5, over_price=op, under_price=up)
            self.assertAlmostEqual(whole.p_resolved, half.p_resolved, places=6)
            self.assertEqual(whole.band, half.band)
            self.assertAlmostEqual(whole.fair_price, half.fair_price, places=3)
            self.assertGreater(whole.p_push, 0.05)
            self.assertAlmostEqual(half.p_push, 0.0)

    def test_the_band_reads_the_resolved_probability(self):
        f = forecast_mlb("a @ b", 8, over_price=-140, under_price=120)
        self.assertLess(f.p_side, 0.53)          # raw looks like a coin flip
        self.assertGreater(f.p_resolved, 0.56)   # resolved is a real lean
        self.assertEqual(f.band, "LEAN")

    def test_even_money_prints_as_plus_one_hundred_not_minus(self):
        """Without a tolerance the sign flips on a floating-point hair and an
        identical coin flip prints -100 on one card and +100 on the next."""
        for line in (7.5, 8, 8.5, 9, 10.5):
            self.assertAlmostEqual(forecast_mlb("a @ b", line).fair_price, 100.0, places=6)


class TestTheDistribution(unittest.TestCase):
    def test_the_pmf_is_a_distribution(self):
        for mu in (5.0, 9.04, 14.0):
            total = sum(nb_pmf(k, mu, DISPERSION_PHI["MLB"]) for k in range(0, 120))
            self.assertAlmostEqual(total, 1.0, places=9)

    def test_it_reproduces_the_measured_mean_and_spread(self):
        """phi is derived from the measured 4.39, so this must come back exact."""
        mu, phi = LEAGUE_COMBINED_RPG, DISPERSION_PHI["MLB"]
        ks = range(0, 140)
        m = sum(k * nb_pmf(k, mu, phi) for k in ks)
        v = sum((k - m) ** 2 * nb_pmf(k, mu, phi) for k in ks)
        self.assertAlmostEqual(m, LEAGUE_COMBINED_RPG, places=6)
        self.assertAlmostEqual(math.sqrt(v), RESIDUAL_SD["MLB"], places=4)

    def test_run_totals_are_right_skewed_so_the_mean_beats_the_median(self):
        """A normal cannot express this, and it is why the anchor matters.

        Fifteen-run games happen; minus-two-run games do not. The mass above
        the mean is thinner and longer than the mass below it.
        """
        mu, phi = 9.04, DISPERSION_PHI["MLB"]
        over_the_mean, _, under_the_mean = nb_split(mu, mu, phi)
        self.assertLess(over_the_mean, under_the_mean)

    def test_a_whole_number_line_can_push_and_a_half_cannot(self):
        for line in (8.0, 9.0, 10.0):
            _, push, _ = split_for("MLB", line, 8.7)
            self.assertGreater(push, 0.05, f"line {line} should push meaningfully")
        for line in (8.5, 9.5):
            _, push, _ = split_for("MLB", line, 8.7)
            self.assertAlmostEqual(push, 0.0)

    def test_the_three_outcomes_always_sum_to_one(self):
        for line in (7.0, 7.5, 8.0, 9.5, 11.0):
            for mu in (6.0, 8.7, 12.0):
                o, p, u = split_for("MLB", line, mu)
                self.assertAlmostEqual(o + p + u, 1.0, places=8)

    def test_under_a_whole_number_equals_under_the_half_below_it(self):
        """Under 9 and under 8.5 are the same event: nine runs or fewer minus
        the push. A model that disagrees has an off-by-one in its summation."""
        o85, _, u85 = split_for("MLB", 8.5, 8.7)
        o9, p9, u9 = split_for("MLB", 9.0, 8.7)
        self.assertAlmostEqual(u85, u9, places=9)
        self.assertAlmostEqual(o85, o9 + p9, places=9)

    def test_the_push_is_taken_from_both_sides_not_invented(self):
        f = forecast_mlb("a @ b", 8.0, wind_mph=25, wind_direction="out")
        self.assertGreater(f.p_push, 0.05)
        self.assertAlmostEqual(f.p_over + f.p_push + f.p_under, 1.0, places=8)
        self.assertIn("pushes and the stake comes back", " ".join(f.notes))


class TestThePricesAreInformation(unittest.TestCase):
    def test_implied_and_devig(self):
        self.assertAlmostEqual(implied(-110), 110 / 210)
        self.assertAlmostEqual(implied(+100), 0.5)
        o, u = devig(-110, -110)
        self.assertAlmostEqual(o, 0.5)
        self.assertAlmostEqual(o + u, 1.0)

    def test_a_juiced_over_means_fair_sits_above_the_posted_number(self):
        even, _ = fair_total("MLB", 8.5, -110, -110)
        juiced, _ = fair_total("MLB", 8.5, -120, +100)
        shaded, _ = fair_total("MLB", 8.5, -105, -115)
        self.assertGreater(juiced, even)
        self.assertLess(shaded, even)

    def test_no_prices_assumes_an_even_market_rather_than_a_mean(self):
        """The line is a 50/50 point, not an average. Treating it as an average
        is what made an empty card come back UNDER 55%."""
        assumed, why = fair_total("MLB", 8.5, None, None)
        priced, _ = fair_total("MLB", 8.5, -110, -110)
        self.assertAlmostEqual(assumed, priced, places=6)
        self.assertGreater(assumed, 8.5)
        self.assertIn("right-skewed", why)

    def test_reading_the_prices_changes_the_call(self):
        plain = forecast_mlb("a @ b", 8.5)
        priced = forecast_mlb("a @ b", 8.5, over_price=-125, under_price=+105)
        self.assertAlmostEqual(plain.p_resolved, 0.5, places=9)
        self.assertEqual(priced.side, "OVER")
        self.assertGreater(priced.p_resolved, 0.52)


class TestItAlwaysAnswers(unittest.TestCase):
    def test_every_card_gets_a_side(self):
        for f in (forecast_mlb("a @ b", 8.5),
                  forecast_mlb("a @ b", 9.0, away_starter_era=6.0, home_starter_era=2.0),
                  forecast_wnba("a @ b", 162.5)):
            self.assertIn(f.side, ("OVER", "UNDER"))
            self.assertIn(f.band, [name for _, name in BANDS])

    def test_the_named_side_is_the_likelier_one(self):
        f = forecast_mlb("a @ b", 9.5, away_starter_era=2.30, home_starter_era=2.10)
        self.assertEqual(f.side, "UNDER")
        self.assertGreater(f.p_under, f.p_over)

    def test_missing_inputs_reweight_rather_than_stall(self):
        with_h2h = forecast_wnba("a @ b", 160.0, away_last10_total=170.0,
                                 home_last10_total=170.0, h2h_total=170.0, h2h_meetings=4)
        without = forecast_wnba("a @ b", 160.0, away_last10_total=170.0,
                                home_last10_total=170.0)
        self.assertGreater(with_h2h.projected, without.projected)
        self.assertIn("No head-to-head", " ".join(without.notes))

    def test_weights_are_shares_not_absolutes(self):
        """Doubling every weight must change no forecast. If it ever does, the
        blend has stopped being a weighted mean and started summing, which is
        the shape that needed caps and produced runaway numbers."""
        kw = dict(away_starter_era=5.9, home_starter_era=3.1, away_bullpen_era=5.0,
                  home_bullpen_era=3.2, away_last10_total=10.4, home_last10_total=8.2)
        before = forecast_mlb("a @ b", 8.5, **kw).projected
        original = dict(WEIGHTS["MLB"])
        try:
            WEIGHTS["MLB"] = {k: v * 3 for k, v in original.items()}
            after = forecast_mlb("a @ b", 8.5, **kw).projected
        finally:
            WEIGHTS["MLB"] = original
        self.assertAlmostEqual(before, after, places=9)

    def test_a_blend_cannot_leave_the_range_of_its_parts(self):
        f = forecast_mlb("a @ b", 7.0, away_last10_total=16.0, home_last10_total=15.0)
        totals = [e.total for e in f.estimates]
        self.assertGreaterEqual(f.projected, min(totals))
        self.assertLessEqual(f.projected, max(totals))

    def test_one_starter_alone_is_not_a_differential(self):
        f = forecast_mlb("a @ b", 8.5, away_starter_era=7.9)
        self.assertNotIn("Starters", [e.name for e in f.estimates])
        self.assertIn("needs both arms", " ".join(f.notes))


class TestPricingTheCall(unittest.TestCase):
    def test_fair_price_round_trips_through_the_probability(self):
        f = forecast_mlb("a @ b", 8.5, wind_mph=22, wind_direction="out")
        self.assertAlmostEqual(implied(f.fair_price), f.p_resolved, places=6)

    def test_a_coin_flip_is_priced_at_even_money(self):
        f = forecast_mlb("a @ b", 8.5)
        self.assertAlmostEqual(abs(f.fair_price), 100.0, places=4)

    def test_edge_is_negative_when_the_price_is_worse_than_fair(self):
        f = forecast_mlb("a @ b", 8.5, wind_mph=20, wind_direction="out")
        self.assertGreater(f.edge_vs(+150), 0)      # generous price
        self.assertLess(f.edge_vs(-300), 0)         # terrible price
        self.assertAlmostEqual(f.edge_vs(f.fair_price), 0.0, places=6)

    def test_a_push_refunds_rather_than_losing(self):
        """A whole-number line with real push mass must price better than the
        same probability with none, because the stake comes back."""
        f = forecast_mlb("a @ b", 8.0, wind_mph=20, wind_direction="out")
        self.assertGreater(f.p_push, 0.05)
        # edge at fair is zero by construction even with the push present
        self.assertAlmostEqual(f.edge_vs(f.fair_price), 0.0, places=6)


class TestHeadToHeadSampleSize(unittest.TestCase):
    def test_the_weight_scales_with_meetings_up_to_four(self):
        self.assertAlmostEqual(h2h_weight(1.0, 1), 0.25)
        self.assertAlmostEqual(h2h_weight(1.0, 4), 1.00)
        self.assertAlmostEqual(h2h_weight(1.0, 40), 1.00)
        self.assertAlmostEqual(h2h_weight(1.0, 0), 0.00)

    def test_one_meeting_still_beats_leaving_it_out(self):
        without = forecast_wnba("a @ b", 160.0, away_last10_total=165.0,
                                home_last10_total=165.0)
        with_one = forecast_wnba("a @ b", 160.0, away_last10_total=165.0,
                                 home_last10_total=165.0, h2h_total=185.0, h2h_meetings=1)
        self.assertGreater(with_one.projected, without.projected)

    def test_a_thin_head_to_head_says_it_was_discounted(self):
        f = forecast_mlb("a @ b", 8.5, h2h_total=11.0, h2h_meetings=1)
        h = next(e for e in f.estimates if e.name.startswith("Head"))
        self.assertIn("Discounted", h.detail)
        self.assertAlmostEqual(h.weight, WEIGHTS["MLB"]["h2h"] / H2H_FULL_WEIGHT_AT)


class TestWeatherAndPark(unittest.TestCase):
    def test_wind_out_and_in_mirror(self):
        out = forecast_mlb("a @ b", 8.5, wind_mph=20, wind_direction="out")
        into = forecast_mlb("a @ b", 8.5, wind_mph=20, wind_direction="in")
        self.assertAlmostEqual(out.deltas[0].runs, -into.deltas[0].runs)
        self.assertEqual(out.side, "OVER")
        self.assertEqual(into.side, "UNDER")

    def test_nothing_under_the_dead_zone_counts(self):
        f = forecast_mlb("a @ b", 8.5, wind_mph=6, wind_direction="out")
        self.assertAlmostEqual(f.deltas[0].runs, 0.0)

    def test_a_cross_wind_is_a_reading_worth_zero(self):
        f = forecast_mlb("a @ b", 8.5, wind_mph=30, wind_direction="cross")
        self.assertAlmostEqual(f.deltas[0].runs, 0.0)
        self.assertIn("neither way", f.deltas[0].detail)

    def test_a_shut_roof_removes_the_weather(self):
        f = forecast_mlb("a @ b", 8.5, wind_mph=30, wind_direction="out", temp_f=98,
                         dome=True)
        self.assertEqual([d.name for d in f.deltas], ["Roof shut"])
        self.assertAlmostEqual(f.p_resolved, 0.5, places=9)

    def test_the_park_never_touches_the_market_anchor(self):
        """Park factor is inside the posted number already. Counting it twice
        is the double count that put the fourteen-input model behind the line."""
        f = forecast_mlb("a @ b", 10.5, park_factor=118)
        self.assertAlmostEqual(f.p_resolved, 0.5, places=9)

    def test_the_park_does_reach_the_differentials(self):
        neutral = forecast_mlb("a @ b", 8.5, away_starter_era=6.0, home_starter_era=6.0,
                               park_factor=100)
        coors = forecast_mlb("a @ b", 8.5, away_starter_era=6.0, home_starter_era=6.0,
                             park_factor=118)
        self.assertGreater(coors.projected, neutral.projected)

    def test_an_implausible_park_is_a_typo(self):
        self.assertAlmostEqual(park_scale(1.13), 1.0)
        self.assertAlmostEqual(park_scale(1130), 1.0)
        self.assertAlmostEqual(park_scale(113), 1.13)

    def test_line_movement_is_shown_and_never_scored(self):
        """The gate model subtracted movement, correctly, because it scored
        news against the number. Here the current line IS the anchor, so the
        move is already inside it."""
        moved = forecast_mlb("a @ b", 9.5, opened=8.5)
        still = forecast_mlb("a @ b", 9.5)
        self.assertAlmostEqual(moved.projected, still.projected, places=9)
        self.assertIn("NOT", " ".join(moved.notes))


class TestGuards(unittest.TestCase):
    def test_an_impossible_line_is_refused(self):
        with self.assertRaises(ValueError):
            forecast_mlb("a @ b", 162.5)          # WNBA number in the MLB box
        with self.assertRaises(ValueError):
            forecast_wnba("a @ b", 8.5)           # MLB number in the WNBA box

    def test_an_impossible_era_is_ignored_rather_than_believed(self):
        f = forecast_mlb("a @ b", 8.5, away_starter_era=99.0, home_starter_era=4.16)
        self.assertNotIn("Starters", [e.name for e in f.estimates])


class TestCalibration(unittest.TestCase):
    """Does a 60% call win 60% of the time? The previous model could not say."""

    def test_a_perfectly_calibrated_run_is_recognised(self):
        import random
        random.seed(11)
        recs = []
        for _ in range(4000):
            p = random.uniform(0.50, 0.70)
            recs.append((p, random.random() < p))
        c = calibration(recs)
        self.assertLess(c.brier, 0.25)
        self.assertIn("Calibrated within noise", c.verdict)

    def test_an_overconfident_model_is_caught(self):
        import random
        random.seed(12)
        # says 65%, actually does 50% — the exact failure mode that matters
        recs = [(0.65, random.random() < 0.50) for _ in range(2000)]
        c = calibration(recs)
        self.assertIn("Miscalibrated", c.verdict)
        self.assertLess(c.hit_rate, c.mean_forecast)

    def test_a_worthless_model_is_named_as_worthless(self):
        import random
        random.seed(13)
        recs = [(0.52, random.random() < 0.50) for _ in range(3000)]
        c = calibration(recs)
        self.assertGreaterEqual(c.brier, 0.24)

    def test_a_short_run_refuses_to_judge(self):
        c = calibration([(0.6, True)] * 12)
        self.assertIn("not enough to judge", c.verdict)
        self.assertIn("Keep logging", c.verdict)

    def test_buckets_report_what_was_said_against_what_happened(self):
        recs = [(0.55, True)] * 30 + [(0.55, False)] * 30 + [(0.65, True)] * 40
        c = calibration(recs)
        labels = {b["label"] for b in c.buckets}
        self.assertIn("53-57%", labels)
        self.assertIn("62%+", labels)
        mid = next(b for b in c.buckets if b["label"] == "53-57%")
        self.assertAlmostEqual(mid["did"], 0.5)
        self.assertIn("said", c.report())

    def test_it_refuses_an_empty_record(self):
        with self.assertRaises(ValueError):
            calibration([])


class TestSlate(unittest.TestCase):
    def test_ordered_by_conviction_and_names_every_side(self):
        rows = [forecast_mlb("Quiet @ Game", 8.5),
                forecast_mlb("Loud @ Game", 8.5, wind_mph=28, wind_direction="in")]
        text = slate(rows)
        self.assertLess(text.index("Loud @ Game"), text.index("Quiet @ Game"))
        self.assertNotIn("PASS", text)

    def test_an_empty_card_says_so(self):
        self.assertIn("Nothing", slate([]))


if __name__ == "__main__":
    unittest.main()
