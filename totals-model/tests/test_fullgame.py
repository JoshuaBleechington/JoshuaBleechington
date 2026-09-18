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
    ERA_OVERDISPERSION,
    ERA_STABLE_AT,
    STARTER_TALENT_SD,
    era_weight,
    shrink_era,
    H2H_FULL_WEIGHT_AT,
    LEAGUE_BULLPEN_ERA,
    LEAGUE_COMBINED_RPG,
    LEAGUE_STARTER_ERA,
    RESIDUAL_SD,
    STARTER_INNINGS,
    WEIGHTS,
    arm_differential,
    calibration,
    margin_guard,
    residual_spread,
    devig,
    fair_total,
    hold,
    market_confidence,
    complete_pair,
    TYPICAL_HOLD,
    HOLD_90TH,
    forecast_mlb,
    h2h_weight,
    implied,
    nb_pmf,
    nb_split,
    park_scale,
    sensitivity,
    slate,
    split_for,
    alt_ladder,
    alt_edge,
    cents_between,
    price_for,
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
        self.assertEqual(f.band, "BET")

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


class TestAWideMarketIsALessCertainOne(unittest.TestCase):
    """Found on 2026-09-04 from a real card.

    A total entered at 8.5 when the main number had moved to 9 picked up an
    ALTERNATE-line quote of -150/-110: a 12.4% hold where every other game that
    night sat at 2.4-4.8%. Proportional de-vig read 53.4% over and pushed the
    card from LEAN to STRONG on what was mostly markup rather than opinion.
    """

    def test_a_normal_hold_is_left_completely_alone(self):
        for op, up in ((-110, -110), (-115, -105), (-120, 100), (-105, -115),
                       (100, -110), (-250, 200)):
            self.assertLessEqual(hold(op, up), 0.05 + 1e-9)
            self.assertAlmostEqual(market_confidence(hold(op, up)), 1.0)
            raw, _ = devig(op, up, shrink=False)
            shrunk, _ = devig(op, up)
            self.assertAlmostEqual(raw, shrunk, places=12,
                                   msg=f"{op}/{up} must be untouched")

    def test_a_wide_market_is_pulled_back_toward_even(self):
        raw, _ = devig(-150, -110, shrink=False)
        shrunk, _ = devig(-150, -110)
        self.assertGreater(raw, shrunk)
        self.assertGreater(shrunk, 0.5)          # never flips the side
        self.assertAlmostEqual(hold(-150, -110), 0.1238, places=4)
        self.assertAlmostEqual(market_confidence(0.1238), 0.05 / 0.1238, places=6)

    def test_the_shrink_never_crosses_even_or_changes_direction(self):
        for op, up in ((-150, -110), (-300, -110), (-110, -300), (500, -110)):
            raw, _ = devig(op, up, shrink=False)
            shrunk, _ = devig(op, up)
            self.assertEqual(raw > 0.5, shrunk > 0.5)
            self.assertLessEqual(abs(shrunk - 0.5), abs(raw - 0.5) + 1e-12)

    def test_a_symmetric_quote_stays_exactly_even_at_any_hold(self):
        """Neutrality must survive the change. A shrink toward even cannot
        move something that is already even."""
        for op in (-110, -105, -150, -400):
            p_over, p_under = devig(op, op)
            self.assertAlmostEqual(p_over, 0.5, places=12)
            self.assertAlmostEqual(p_under, 0.5, places=12)

    def test_it_says_the_quote_looks_like_an_alternate_line(self):
        _, why = fair_total("MLB", 8.5, -150, -110)
        self.assertIn("ALTERNATE line", why)
        self.assertIn("12.4% hold", why)
        _, normal = fair_total("MLB", 8.5, -115, -105)
        self.assertNotIn("ALTERNATE", normal)

    def test_the_real_card_moves_by_about_a_point_and_a_half(self):
        kw = dict(away_starter_era=3.46, home_starter_era=3.32, away_rpg=4.24,
                  home_rpg=4.91, away_bullpen_era=4.00, home_bullpen_era=5.15,
                  away_last10_total=8.9, home_last10_total=9.8, h2h_total=12.0,
                  h2h_meetings=2, park_factor=106, wind_mph=11.8,
                  wind_direction="out", temp_f=96.5, ticket_pct_over=55,
                  money_pct_over=59)
        f = forecast_mlb("MIA @ KC", 8.5, over_price=-150, under_price=-110, **kw)
        self.assertEqual(f.side, "OVER")
        self.assertLess(f.p_resolved, 0.575)     # was 58.7% before the change
        self.assertGreater(f.p_resolved, 0.56)

    def test_shin_is_deliberately_not_used(self):
        """Shin corrects favourite-longshot bias and moves the favourite UP.

        It is a real effect and the wrong one here: under Shin a -150/-110 quote
        reads 53.8% against proportional's 53.4%, which would have made the
        alternate line MORE confident rather than less. This pins the direction
        so nobody re-adds it thinking it fixes this.
        """
        raw, _ = devig(-150, -110, shrink=False)
        shrunk, _ = devig(-150, -110)
        self.assertLess(shrunk, raw)             # we go DOWN, Shin goes up


class TestItAlwaysAnswers(unittest.TestCase):
    def test_every_card_gets_a_side(self):
        for f in (forecast_mlb("a @ b", 8.5),
                  forecast_mlb("a @ b", 9.0, away_starter_era=6.0, home_starter_era=2.0),
                  forecast_mlb("a @ b", 11.5, over_price=-130, under_price=110)):
            self.assertIn(f.side, ("OVER", "UNDER"))
            self.assertIn(f.band, [name for _, name in BANDS])

    def test_the_named_side_is_the_likelier_one(self):
        f = forecast_mlb("a @ b", 9.5, away_starter_era=2.30, home_starter_era=2.10)
        self.assertEqual(f.side, "UNDER")
        self.assertGreater(f.p_under, f.p_over)

    def test_missing_inputs_reweight_rather_than_stall(self):
        with_h2h = forecast_mlb("a @ b", 8.5, away_last10_total=10.0,
                                home_last10_total=10.0, h2h_total=11.0, h2h_meetings=4)
        without = forecast_mlb("a @ b", 8.5, away_last10_total=10.0,
                               home_last10_total=10.0)
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
        without = forecast_mlb("a @ b", 8.5, away_last10_total=9.0,
                               home_last10_total=9.0)
        with_one = forecast_mlb("a @ b", 8.5, away_last10_total=9.0,
                                home_last10_total=9.0, h2h_total=14.0, h2h_meetings=1)
        self.assertGreater(with_one.projected, without.projected)

    def test_a_thin_head_to_head_says_it_was_discounted(self):
        f = forecast_mlb("a @ b", 8.5, h2h_total=11.0, h2h_meetings=1)
        h = next(e for e in f.estimates if e.name.startswith("Head"))
        self.assertIn("Discounted", h.detail)
        self.assertAlmostEqual(h.weight, WEIGHTS["MLB"]["h2h"] / H2H_FULL_WEIGHT_AT)


class TestSoftInputsCannotBuyABand(unittest.TestCase):
    """A measured-null input may move the forecast. It may not be the bet.

    The Tigers/Guardians card is the reason this exists. Head to head at 6.4
    over nine meetings and a public-money flag dragged a card the market and
    both pitching staffs read as a coin flip into an UNDER LEAN, against the
    price. It went twelve runs. The outcome was a 1-in-5 tail and proves
    nothing; the reasoning was the problem.
    """

    #: The real card, as logged.
    TIGERS = dict(
        line=8.0, over_price=-120, under_price=100,
        away_starter_era=3.24, home_starter_era=3.77,
        away_rpg=4.05, home_rpg=4.12,
        away_bullpen_era=4.00, home_bullpen_era=3.73,
        away_last10_total=9.0, home_last10_total=8.9,
        h2h_total=6.4, h2h_meetings=9, park_factor=98,
        wind_mph=6, wind_direction="cross", temp_f=76,
        ticket_pct_over=67, money_pct_over=38,
    )

    def test_the_card_that_prompted_this_is_held_at_a_coin_flip(self):
        f = forecast_mlb("Tigers @ Guardians", **self.TIGERS)
        self.assertEqual(f.side, "UNDER")
        self.assertEqual(f.band_ungated, "BET")
        self.assertEqual(f.band, "NO BET")
        # The core read names the OTHER side, which is the whole point.
        self.assertLess(f.p_corroborated, 0.5)

    def test_the_headline_probability_is_untouched(self):
        """The gate governs the band, never the forecast.

        The probability is the best estimate of what happens; the band is the
        recommendation. Silently moving the first to justify the second would
        corrupt the calibration measure, which reads the probability.
        """
        f = forecast_mlb("Tigers @ Guardians", **self.TIGERS)
        self.assertAlmostEqual(f.p_resolved, 0.5397, places=3)
        self.assertAlmostEqual(f.projected, 8.164, places=2)

    def test_it_says_plainly_that_it_pulled_the_band(self):
        f = forecast_mlb("Tigers @ Guardians", **self.TIGERS)
        note = next(n for n in f.notes if "Held at" in n)
        self.assertIn("NO BET", note)
        self.assertIn("BET", note)
        self.assertIn("the other side", note)

    def test_a_card_with_no_soft_inputs_is_left_completely_alone(self):
        """Not an approximation of a no-op -- an actual one."""
        bare = dict(line=8.5, over_price=-115, under_price=-105,
                    away_starter_era=2.90, home_starter_era=5.40,
                    away_bullpen_era=3.10, home_bullpen_era=5.10)
        f = forecast_mlb("a @ b", **bare)
        self.assertEqual(f.band, f.band_ungated)
        self.assertAlmostEqual(f.projected_corroborated, f.projected, places=12)
        self.assertAlmostEqual(f.p_corroborated, f.p_resolved, places=12)
        self.assertFalse(any("Held at" in n for n in f.notes))

    def test_soft_inputs_agreeing_with_the_core_keep_the_band(self):
        """The gate is a veto, not a tax. Corroborated confidence survives."""
        kw = dict(line=8.5, over_price=-110, under_price=-110,
                  away_starter_era=6.20, home_starter_era=6.40,
                  away_bullpen_era=5.90, home_bullpen_era=5.80)
        core = forecast_mlb("a @ b", **kw)
        withsoft = forecast_mlb("a @ b", away_last10_total=11.0,
                                home_last10_total=11.4, **kw)
        self.assertEqual(core.side, "OVER")
        self.assertEqual(withsoft.side, "OVER")
        self.assertEqual(withsoft.band, withsoft.band_ungated)
        self.assertNotEqual(withsoft.band, "NO BET")

    def test_soft_inputs_can_still_cut_confidence(self):
        """Deleting them is never allowed to RAISE the band."""
        kw = dict(line=8.5, over_price=-110, under_price=-110,
                  away_starter_era=6.20, home_starter_era=6.40,
                  away_bullpen_era=5.90, home_bullpen_era=5.80)
        cut = forecast_mlb("a @ b", away_last10_total=7.0,
                           home_last10_total=7.2, **kw)
        self.assertLessEqual(BANDS_ORDER[cut.band], BANDS_ORDER[cut.band_ungated])

    def test_the_band_never_exceeds_either_read(self):
        """min(), stated as a property rather than trusted to one example."""
        for h2h in (4.0, 6.0, 8.0, 10.0, 14.0):
            for split in ((70, 30), (30, 70), (50, 50)):
                f = forecast_mlb(
                    "a @ b", line=8.5, over_price=-110, under_price=-110,
                    away_starter_era=3.10, home_starter_era=3.30,
                    away_bullpen_era=3.40, home_bullpen_era=3.20,
                    h2h_total=h2h, h2h_meetings=6,
                    ticket_pct_over=split[0], money_pct_over=split[1])
                floor = next(fl for fl, n in BANDS if n == f.band)
                if f.band != "NO BET":
                    self.assertGreaterEqual(f.p_resolved, floor)
                    self.assertGreaterEqual(f.p_corroborated, floor)

    def test_wind_and_temperature_are_mechanism_and_survive_the_gate(self):
        """Wind is the one input the market prices imperfectly. It is not soft."""
        f = forecast_mlb("a @ b", line=8.5, wind_mph=25, wind_direction="out",
                         away_starter_era=4.16, home_starter_era=4.16)
        wind = next(d for d in f.deltas if d.name == "Wind")
        self.assertTrue(wind.mechanism)
        self.assertGreater(f.projected_corroborated, f.line)

    def test_the_three_soft_inputs_are_the_only_ones_tagged(self):
        f = forecast_mlb(
            "a @ b", line=8.5, away_starter_era=3.9, home_starter_era=4.4,
            away_bullpen_era=3.8, home_bullpen_era=4.3,
            away_last10_total=9.0, home_last10_total=9.2,
            h2h_total=9.1, h2h_meetings=5, wind_mph=14, wind_direction="out",
            temp_f=84, ticket_pct_over=70, money_pct_over=40)
        soft = {e.name for e in f.estimates if not e.mechanism}
        soft |= {d.name for d in f.deltas if not d.mechanism}
        self.assertEqual(soft, {"Last 10", "Head to head (5)", "Money split"})

BANDS_ORDER = {name: i for i, (_floor, name) in enumerate(BANDS)}


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
            forecast_mlb("a @ b", 162.5)          # a basketball number
        with self.assertRaises(ValueError):
            forecast_mlb("a @ b", 1.5)            # no MLB total is ever this low

    def test_an_impossible_era_is_ignored_rather_than_believed(self):
        f = forecast_mlb("a @ b", 8.5, away_starter_era=99.0, home_starter_era=4.16)
        self.assertNotIn("Starters", [e.name for e in f.estimates])


class TestOnePriceIsNotNoPrice(unittest.TestCase):
    """A card with only the over filled in used to throw the price away.

    `fair_total` fell back to "assume -110/-110" and the heaviest input on the
    board went in blind. On a real Brewers/Pirates card that cost 1.8 points of
    probability. A -120 over is the book saying fair sits north of the posted
    number, and that survives without its partner.
    """

    def test_a_complete_quote_is_left_alone(self):
        """The whole change must be invisible when both prices are given."""
        self.assertIsNone(complete_pair(-120, 100))
        for op, up in ((-110, -110), (-120, 100), (-150, 125), (105, -125)):
            a = forecast_mlb("a @ b", 8.5, over_price=op, under_price=up)
            self.assertEqual(a.projected, forecast_mlb(
                "a @ b", 8.5, over_price=op, under_price=up).projected)
            self.assertNotIn("reconstructed", a.estimates[0].detail)

    def test_no_price_at_all_still_falls_back_the_old_way(self):
        self.assertIsNone(complete_pair(None, None))
        f = forecast_mlb("a @ b", 8.5)
        self.assertAlmostEqual(f.p_resolved, 0.5, places=9)
        self.assertIn("No prices given", f.estimates[0].detail)

    def test_a_lone_over_price_pushes_the_anchor_up(self):
        blind = fair_total("MLB", 8.5, None, None)[0]
        lone = fair_total("MLB", 8.5, -120, None)[0]
        self.assertGreater(lone, blind, "a -120 over says fair is north of the line")
        self.assertIn("reconstructed", fair_total("MLB", 8.5, -120, None)[1])

    def test_a_lone_under_price_pushes_the_anchor_down(self):
        blind = fair_total("MLB", 8.5, None, None)[0]
        lone = fair_total("MLB", 8.5, None, -120)[0]
        self.assertLess(lone, blind)

    def test_the_two_sides_are_mirror_images_in_probability(self):
        """A lone -140 over and a lone -140 under must lean equally hard.

        The symmetry lives in the PROBABILITY, not in the mean. Asserting that
        the anchor moves by the same number of runs each way fails by 0.012,
        and that failure is correct: the run distribution is right-skewed, so
        the map from probability to mean is not linear. The reconstruction
        itself is exactly symmetric and that is what gets pinned.
        """
        for price in (-120, -140, -175):
            o = complete_pair(price, None)
            u = complete_pair(None, price)
            self.assertAlmostEqual(devig(*o, shrink=False)[0] - 0.5,
                                   0.5 - devig(*u, shrink=False)[0], places=12)
        # and the anchor still moves the right way on each side
        blind = fair_total("MLB", 8.5, None, None)[0]
        self.assertGreater(fair_total("MLB", 8.5, -140, None)[0], blind)
        self.assertLess(fair_total("MLB", 8.5, None, -140)[0], blind)

    def test_a_reconstructed_quote_does_not_get_full_authority(self):
        """Its hold is assumed, not observed, so it is cut against the 90th
        percentile of what this book actually charges."""
        rebuilt = complete_pair(-120, None)
        raw, _ = devig(rebuilt[0], rebuilt[1], shrink=False)
        kept, _ = devig(rebuilt[0], rebuilt[1], confidence_hold=HOLD_90TH)
        self.assertLess(abs(kept - 0.5), abs(raw - 0.5))
        self.assertAlmostEqual(kept - 0.5, (raw - 0.5) * market_confidence(HOLD_90TH),
                               places=9)
        self.assertLess(market_confidence(HOLD_90TH), 1.0)

    def test_it_never_invents_a_price_past_certainty(self):
        """A longshot so long the usual hold cannot cover it falls back."""
        self.assertIsNone(complete_pair(+2000, None))
        f = forecast_mlb("a @ b", 8.5, over_price=+2000)
        self.assertIn("No prices given", f.estimates[0].detail)

    def test_the_reconstruction_beats_discarding_the_price(self):
        """The property the whole change rests on, on real-shaped quotes.

        Measured across 133 logged two-priced cards it lands 73-78% closer to
        the true answer and 122 of 133 improve; this pins the direction.
        """
        for op, up in ((-120, 100), (-140, 105), (-150, 120), (-105, -115), (100, -120)):
            truth = fair_total("MLB", 8.5, op, up)[0]
            blind = fair_total("MLB", 8.5, None, None)[0]
            rebuilt_o = fair_total("MLB", 8.5, op, None)[0]
            rebuilt_u = fair_total("MLB", 8.5, None, up)[0]
            for got in (rebuilt_o, rebuilt_u):
                self.assertLess(abs(got - truth), abs(blind - truth),
                                f"{op}/{up}: reconstruction was no better than discarding")

    def test_the_measured_hold_constants_are_what_the_book_charges(self):
        """These are measured on the logged card, so they must stay ordered and
        stay in the range a main line actually trades at."""
        self.assertLess(TYPICAL_HOLD, HOLD_90TH)
        self.assertLess(0.02, TYPICAL_HOLD)
        self.assertLess(HOLD_90TH, 0.10)


class TestTheGuardIsMeasuredNotRemembered(unittest.TestCase):
    """A constant that cites a live measurement is the one that goes stale.

    The page carried `OVERCONFIDENCE = 3.0` with the comment "measured, not
    chosen: the model has said 54.2% and done 51.1%". True when written, false
    by 110 graded calls (55.41% against 55.45%). Nobody re-checks a number that
    claims it was measured, so it is computed now.
    """

    def test_an_underconfident_model_does_not_earn_extra_margin(self):
        """Doing better than you said is not a licence to bet thinner."""
        recs = [(0.55, i % 100 < 70) for i in range(400)]     # says 55, does 70
        g = margin_guard(recs)
        self.assertEqual(g.bias, 0.0)
        self.assertGreater(g.points, 0.0, "noise alone still floors it")

    def test_a_measured_overconfidence_is_carried_in_full(self):
        recs = [(0.60, i % 100 < 45) for i in range(400)]     # says 60, does 45
        g = margin_guard(recs)
        self.assertAlmostEqual(g.bias, 0.15, places=6)
        self.assertGreater(g.points, 0.15)

    def test_the_guard_tightens_as_the_card_grows(self):
        """The property the hardcoded 3.0 could never have."""
        last = float("inf")
        for n in (50, 110, 400, 1000, 4000):
            g = margin_guard([(0.55, i % 100 < 55) for i in range(n)])
            self.assertLess(g.points, last)
            last = g.points

    def test_a_thin_card_blocks_everything_without_a_special_case(self):
        """At ten calls one standard error is enormous, which IS the answer."""
        g = margin_guard([(0.55, i % 2 == 0) for i in range(10)])
        self.assertGreater(g.points, 0.10,
                           "ten calls cannot establish a margin of any size")

    def test_no_graded_calls_is_not_a_clean_bill_of_health(self):
        g = margin_guard([])
        self.assertEqual(g.n, 0)
        self.assertEqual(g.points, float("inf"))
        self.assertIn("unmeasured", g.detail)

    def test_the_spread_check_reports_rather_than_refits(self):
        """It must never quietly move RESIDUAL_SD. Chasing a fortnight's
        residuals is how a dispersion parameter ends up fitting noise."""
        tight = residual_spread([0.2, -0.3, 0.1, -0.2, 0.25, -0.15] * 30)
        self.assertFalse(tight.consistent)
        self.assertIn("OUTSIDE", tight.detail)
        self.assertEqual(tight.assumed, RESIDUAL_SD["MLB"],
                         "the constant is reported, never rewritten")
        self.assertEqual(RESIDUAL_SD["MLB"], 4.39)

    def test_a_spread_matching_the_constant_is_reported_as_settled(self):
        import random
        rng = random.Random(7)
        got = residual_spread([rng.gauss(1.0, 4.39) for _ in range(600)])
        self.assertTrue(got.consistent)
        self.assertLessEqual(got.lo, 4.39)
        self.assertGreaterEqual(got.hi, 4.39)

    def test_the_interval_brackets_the_true_spread(self):
        """The chi-square approximation has to actually cover."""
        import random
        rng = random.Random(11)
        covered = 0
        for _ in range(200):
            got = residual_spread([rng.gauss(0.0, 4.0) for _ in range(120)], assumed=4.0)
            covered += got.consistent
        self.assertGreater(covered, 180, f"95% interval covered only {covered}/200")

    def test_too_few_games_refuses_to_measure_a_spread(self):
        got = residual_spread([1.0, -2.0])
        self.assertIn("not enough", got.detail)


class TestAStarterERAIsAMeasurement(unittest.TestCase):
    """A short season is a noisy season, and the model has to know it.

    Before this block a call-up's 5.24 in 22 innings carried exactly the
    authority of an ace's 5.24 in 190. The fix is empirical Bayes on the
    innings count. What these tests mostly pin is that it is SAFE: it is off
    unless asked for, it only ever pulls toward the league, and it can never
    invent a number more extreme than the one typed.
    """

    def test_a_blank_innings_field_changes_absolutely_nothing(self):
        """The whole feature has to be invisible to every card logged before it.

        This is the guarantee the change stands on. If it fails, a back
        catalogue of graded cards silently re-scores and the record is gone.
        """
        for line, aera, hera in ((8.5, 5.24, 5.53), (9.0, 2.10, 6.40),
                                 (7.5, 4.16, 4.16), (11.0, 3.01, 3.99)):
            plain = forecast_mlb("a @ b", line, over_price=-110, under_price=-110,
                                 away_starter_era=aera, home_starter_era=hera)
            blank = forecast_mlb("a @ b", line, over_price=-110, under_price=-110,
                                 away_starter_era=aera, home_starter_era=hera,
                                 away_starter_ip=None, home_starter_ip=None)
            self.assertEqual(plain.projected, blank.projected)
            self.assertEqual(plain.p_resolved, blank.p_resolved)
            self.assertEqual(plain.band, blank.band)
            self.assertEqual(plain.side, blank.side)

    def test_the_stabilisation_point_is_derived_not_chosen(self):
        """ERA_STABLE_AT must fall out of the other two constants.

        If someone edits it by hand to tune a backtest, this fails -- which is
        the point. It is 9 * overdispersion * league ERA / talent variance.
        """
        expected = (9.0 * ERA_OVERDISPERSION * LEAGUE_STARTER_ERA
                    / STARTER_TALENT_SD ** 2)
        self.assertAlmostEqual(ERA_STABLE_AT, expected, places=9)
        self.assertAlmostEqual(era_weight(ERA_STABLE_AT), 0.5, places=9,
                               msg="at the stabilisation point it is a 50/50 split")

    def test_more_innings_is_always_more_trust_and_never_full_trust(self):
        last = -1.0
        for ip in (1, 10, 22.1, 60, 90.7, 143.1, 190, 300):
            w = era_weight(ip)
            self.assertGreater(w, last, "weight must rise with innings")
            self.assertGreater(w, 0.0)
            self.assertLess(w, 1.0, "a season is a sample, never a reading")
            last = w

    def test_shrinking_only_ever_pulls_toward_the_league(self):
        """It can move a number in, never out, and never past the prior."""
        for era in (1.20, 2.80, 4.16, 5.24, 7.90):
            for ip in (5, 22.1, 90, 143.1, 220):
                out = shrink_era(era, ip)
                lo, hi = sorted((era, LEAGUE_STARTER_ERA))
                self.assertGreaterEqual(out, lo - 1e-12)
                self.assertLessEqual(out, hi + 1e-12)
                self.assertLessEqual(abs(out - LEAGUE_STARTER_ERA),
                                     abs(era - LEAGUE_STARTER_ERA) + 1e-12)

    def test_a_league_average_arm_is_untouched_by_any_sample_size(self):
        """Shrinking toward the mean cannot move something already at it."""
        for ip in (1, 22.1, 90.7, 200, None):
            self.assertAlmostEqual(shrink_era(LEAGUE_STARTER_ERA, ip),
                                   LEAGUE_STARTER_ERA, places=12)

    def test_the_same_era_moves_the_card_less_on_fewer_innings(self):
        """The ordering that makes the feature worth having at all."""
        def proj(ip):
            return forecast_mlb("a @ b", 8.5, over_price=-110, under_price=-110,
                                away_starter_era=6.50, home_starter_era=4.16,
                                away_starter_ip=ip, home_starter_ip=200.0).projected
        self.assertLess(proj(20), proj(80))
        self.assertLess(proj(80), proj(180))
        self.assertLess(proj(180), proj(None), "blank must be the most credulous")

    def test_an_implausible_innings_count_is_ignored_rather_than_believed(self):
        """Same posture as an implausible ERA: fall back, do not extrapolate."""
        for junk in (-5.0, 0.0, 9999.0):
            self.assertEqual(era_weight(junk), 1.0)

    def test_the_card_says_when_it_has_discounted_an_arm(self):
        f = forecast_mlb("a @ b", 8.5, over_price=-110, under_price=-110,
                         away_starter_era=5.24, home_starter_era=5.53,
                         away_starter_ip=22.1, home_starter_ip=143.1)
        detail = next(e for e in f.estimates if e.name == "Starters").detail
        self.assertIn("22.1 IP", detail)
        self.assertIn("sample size", detail)
        plain = forecast_mlb("a @ b", 8.5, over_price=-110, under_price=-110,
                             away_starter_era=5.24, home_starter_era=5.53)
        self.assertNotIn("sample size",
                         next(e for e in plain.estimates if e.name == "Starters").detail,
                         "a card with no innings typed must not claim a discount")


class TestAlternateLines(unittest.TestCase):
    """The one thing here that does not need the model to be right.

    A book prices its MAIN line efficiently -- that is the single fact this
    project has established. It prices the alternate ladder off a template. So
    the fair price at every other number is arithmetic on the market's own
    distribution, and comparing it to what the book offers is a relative
    judgement that needs no forecasting edge at all.
    """

    def test_the_main_rung_reproduces_the_main_line(self):
        rungs = alt_ladder("MLB", 8.5, -115, -105, span=2.0)
        main = next(r for r in rungs if abs(r.line - 8.5) < 1e-9)
        f = forecast_mlb("a @ b", 8.5, over_price=-115, under_price=-105)
        market = next(e for e in f.estimates if e.name == "Market")
        over, _push, under = split_for("MLB", 8.5, market.total)
        self.assertAlmostEqual(main.p_over, over / (over + under), places=9)

    def test_the_ladder_is_monotone(self):
        """A higher total can only ever be harder to go over."""
        rungs = alt_ladder("MLB", 8.5, -110, -110, span=3.0)
        for a, b in zip(rungs, rungs[1:]):
            self.assertGreater(a.p_over, b.p_over,
                               f"{a.line} -> {b.line} did not fall")

    def test_only_whole_numbers_push(self):
        for r in alt_ladder("MLB", 8.5, -110, -110, span=2.0):
            if abs(r.line - round(r.line)) < 1e-9:
                self.assertGreater(r.p_push, 0.05)
            else:
                self.assertAlmostEqual(r.p_push, 0.0, places=9)

    def test_the_two_sides_of_a_rung_are_complementary(self):
        for r in alt_ladder("MLB", 9.0, -120, 100, span=2.0):
            self.assertAlmostEqual(implied(r.fair_over) + implied(r.fair_under),
                                   1.0, places=6)

    def test_cents_and_expected_value_never_disagree_in_sign(self):
        """The bug this caught.

        The index rises with implied probability and a higher implied
        probability is a WORSE price, so the subtraction was backwards: a book
        offering +145 where fair was +195 reported as FIFTY CENTS OF VALUE while
        its expected value was -0.17 a unit.
        """
        rungs = alt_ladder("MLB", 8.5, -115, -105, span=3.0)
        for r in rungs:
            for side in ("OVER", "UNDER"):
                fair = r.fair_over if side == "OVER" else r.fair_under
                for offered in (fair - 60, fair - 20, fair + 20, fair + 60,
                                -110, 100, 150, -200):
                    e = alt_edge(r, side, offered)
                    if abs(e["cents"]) < 1e-6:
                        continue
                    self.assertEqual(
                        e["cents"] > 0, e["ev_per_unit"] > 0,
                        f"{side} {r.line} fair {fair:+.0f} offered {offered:+.0f}: "
                        f"{e['cents']:+.1f} cents but EV {e['ev_per_unit']:+.4f}")

    def test_the_fair_price_is_exactly_zero_edge(self):
        for r in alt_ladder("MLB", 8.5, -110, -110, span=2.0):
            for side in ("OVER", "UNDER"):
                fair = r.fair_over if side == "OVER" else r.fair_under
                e = alt_edge(r, side, fair)
                self.assertAlmostEqual(e["cents"], 0.0, places=6)
                self.assertAlmostEqual(e["ev_per_unit"], 0.0, places=6)

    def test_a_better_price_is_always_worth_more(self):
        r = next(x for x in alt_ladder("MLB", 8.5, -110, -110, span=2.0)
                 if abs(x.line - 10.5) < 1e-9)
        worse = alt_edge(r, "OVER", 150)
        better = alt_edge(r, "OVER", 250)
        self.assertGreater(better["cents"], worse["cents"])
        self.assertGreater(better["ev_per_unit"], worse["ev_per_unit"])

    def test_the_model_ladder_can_be_asked_for_separately(self):
        """Two ladders, and the difference between them matters.

        The MARKET ladder needs only the main line to be efficient. The MODEL
        ladder is only as good as the model, which on 106 logged games has added
        nothing over the base rate. They must not be confused.
        """
        market = alt_ladder("MLB", 8.5, -110, -110, span=1.0)
        model = alt_ladder("MLB", 8.5, -110, -110, span=1.0, mu=10.5)
        self.assertGreater(model[0].p_over, market[0].p_over)

    def test_a_pushable_rung_prices_on_the_resolved_outcome(self):
        r = next(x for x in alt_ladder("MLB", 8.5, -110, -110, span=1.0)
                 if abs(x.line - 9.0) < 1e-9)
        self.assertGreater(r.p_push, 0.05)
        # the two fair prices must still be a complete book once the push is out
        self.assertAlmostEqual(implied(r.fair_over) + implied(r.fair_under),
                               1.0, places=6)


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


class TestInningsMustBeFilledOnBothSidesOrNeither(unittest.TestCase):
    """A blank innings box is not neutral, and that is easy to miss.

    Blank means "trust this ERA in full", which is more authority than 210
    innings earns. So shrinking one arm while the other keeps full trust tilts
    the differential toward whichever box was left empty -- on a 3.00 against
    5.50 card it flips the side on which box got typed into.
    """

    KW = dict(over_price=-110, under_price=-110,
              away_starter_era=3.00, home_starter_era=5.50)
    WARN = "one starter and not the other"

    def _warned(self, f):
        return any(self.WARN in n for n in f.notes)

    def test_a_one_sided_fill_can_flip_the_side(self):
        away = forecast_mlb("a @ b", 8.5, away_starter_ip=165.1, **self.KW)
        home = forecast_mlb("a @ b", 8.5, home_starter_ip=165.1, **self.KW)
        self.assertNotEqual(away.side, home.side,
                            "if this stops flipping the warning can go")

    def test_a_one_sided_fill_is_called_out(self):
        for kw in ({"away_starter_ip": 165.1}, {"home_starter_ip": 190.0}):
            self.assertTrue(self._warned(forecast_mlb("a @ b", 8.5, **kw, **self.KW)))

    def test_both_or_neither_is_not_warned_about(self):
        self.assertFalse(self._warned(forecast_mlb("a @ b", 8.5, **self.KW)))
        self.assertFalse(self._warned(forecast_mlb(
            "a @ b", 8.5, away_starter_ip=165.1, home_starter_ip=190.0, **self.KW)))

    def test_an_ignored_innings_count_does_not_trip_the_warning(self):
        """An implausible figure falls back to full trust, so the card is
        effectively 'neither' and must not claim a one-sided fill."""
        self.assertFalse(self._warned(forecast_mlb(
            "a @ b", 8.5, away_starter_ip=9999.0, **self.KW)))

    def test_baseball_notation_does_not_need_converting(self):
        """165.1 means 165 and a third. Typing the decimal is harmless.

        Pinned as a bound on the error, and the bound is measured rather than
        guessed -- I asserted 0.001 first and it failed at 60.2 IP, because the
        weight curve is steepest at low innings where a third of an inning is a
        larger share of the sample. Swept across 5-230 IP the worst drift is
        0.00458 of weight, at 5.2 IP. What that is worth downstream is the
        number that matters: at most 0.004 of an ERA on the value that enters
        the blend, which is nothing.
        """
        worst = 0.0
        for whole in range(5, 231):
            for tenth, third in ((0.1, 1 / 3), (0.2, 2 / 3)):
                worst = max(worst, abs(era_weight(whole + tenth)
                                       - era_weight(whole + third)))
        self.assertLess(worst, 0.005, "the notation shortcut has stopped being free")
        # and the thing that actually reaches the projection
        for ip, third, era in ((22.2, 22 + 2 / 3, 5.24), (165.1, 165 + 1 / 3, 3.00)):
            self.assertLess(abs(shrink_era(era, ip) - shrink_era(era, third)), 0.005)
