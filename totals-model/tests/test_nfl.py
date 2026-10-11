"""Tests for the NFL spread model.

The first block is the most important. This model's claim is not that it beats
the NFL spread market -- nothing does on seventeen games a week -- but that it
prices the margin distribution correctly enough to say what half a point is
worth. If the distribution is wrong, there is nothing here at all.
"""

import math
import unittest

from totals.nfl import (
    BANDS,
    HOME_FIELD,
    KEY_FIT_SD,
    KEY_NUMBERS,
    MARGIN_SD,
    RATING_STABLE_AT,
    WEIGHTS,
    fair_price,
    fair_spread,
    forecast_nfl,
    half_point_value,
    hold,
    implied,
    key_multiplier,
    margin_pmf,
    margin_split,
    market_confidence,
    rating_weight,
    sensitivity,
    slate,
)
from totals.nfl import _price_index


class TestTheMarginDistribution(unittest.TestCase):
    """Everything rests on this being the real shape of NFL margins."""

    #: Published frequencies for the margins that are actually documented.
    PUBLISHED = {1: 0.029, 3: 0.095, 4: 0.040, 6: 0.045,
                 7: 0.065, 10: 0.045, 14: 0.035, 17: 0.025}

    def test_it_reproduces_the_published_margin_frequencies(self):
        pmf = margin_pmf(HOME_FIELD, KEY_FIT_SD)
        for m, want in self.PUBLISHED.items():
            got = pmf[m] + pmf[-m]
            self.assertAlmostEqual(
                got, want, delta=0.0005,
                msg=f"margin {m}: modelled {got:.4f} against a published {want:.4f}")

    def test_it_is_a_distribution(self):
        for mu in (-7.0, 0.0, 1.6, 10.0):
            self.assertAlmostEqual(sum(margin_pmf(mu).values()), 1.0, places=9)

    def test_three_is_the_most_common_margin_by_a_distance(self):
        pmf = margin_pmf(HOME_FIELD, KEY_FIT_SD)
        both = {m: pmf[m] + pmf[-m] for m in range(1, 40)}
        self.assertEqual(max(both, key=both.get), 3)
        self.assertGreater(both[3], both[7] * 1.3)

    def test_four_and_six_are_not_key_numbers(self):
        """The fit contradicts the folklore, so it gets pinned.

        Both come in BELOW 1.0 -- they are rarer than a smooth curve predicts,
        because three and seven take the mass.
        """
        self.assertLess(KEY_NUMBERS[4], 1.0)
        self.assertLess(KEY_NUMBERS[6], 1.0)
        self.assertGreater(KEY_NUMBERS[3], 1.5)

    def test_there_are_no_regulation_ties(self):
        self.assertNotIn(0, margin_pmf(1.6))

    def test_it_degrades_to_a_normal_when_the_multipliers_are_switched_off(self):
        """A model that gets the key numbers wrong should become a normal, not
        become nonsense."""
        import totals.nfl as nfl
        saved = dict(nfl.KEY_NUMBERS)
        try:
            nfl.KEY_NUMBERS.clear()
            pmf = margin_pmf(0.0, 14.0)
            # symmetric about zero, and the ratio of neighbours matches a normal
            self.assertAlmostEqual(pmf[5], pmf[-5], places=12)
            want = math.exp(-0.5 * ((5 / 14.0) ** 2 - (3 / 14.0) ** 2))
            self.assertAlmostEqual(pmf[5] / pmf[3], want, places=9)
        finally:
            nfl.KEY_NUMBERS.update(saved)


class TestPushesAreRealAndExact(unittest.TestCase):
    def test_only_a_whole_number_can_push(self):
        for s in (-3.5, -6.5, -7.5, 2.5):
            self.assertAlmostEqual(margin_split(s, 2.0)[1], 0.0, places=12)
        for s in (-3.0, -7.0, -10.0):
            self.assertGreater(margin_split(s, 2.0)[1], 0.01)

    def test_the_push_on_three_is_the_biggest_on_the_board(self):
        pushes = {s: margin_split(s, -s)[1] for s in (-1, -2, -3, -4, -6, -7, -10, -14)}
        self.assertEqual(max(pushes, key=pushes.get), -3)
        self.assertGreater(pushes[-3], 0.045)

    def test_the_three_outcomes_are_a_distribution(self):
        for s in (-3.0, -3.5, -7.0, 6.0):
            self.assertAlmostEqual(sum(margin_split(s, 1.5)), 1.0, places=9)


class TestWhatAHalfPointIsWorth(unittest.TestCase):
    """The part of this model that does not need an opinion to be useful."""

    def test_cents_do_not_explode_across_the_century(self):
        """The bug this caught: American odds jump from +100 to -100 for the
        same bet, so subtracting them directly reported a ten-cent move as two
        hundred cents."""
        self.assertAlmostEqual(_price_index(0.5), 0.0, places=9)
        self.assertAlmostEqual(_price_index(110 / 210.0), 10.0, places=6)
        self.assertAlmostEqual(_price_index(100 / 210.0), -10.0, places=6)
        # monotone through the boundary, and a 20-cent ladder stays 20 cents
        self.assertAlmostEqual(
            abs(_price_index(110 / 210.0) - _price_index(100 / 210.0)), 20.0, places=6)
        v = half_point_value(-3.0, 3.0)["cents"]
        self.assertLess(v, 30.0, "a half point is never worth thirty cents")
        self.assertGreater(v, 0.0)

    def test_buying_a_half_point_always_helps(self):
        for s in (-1.0, -2.5, -3.0, -3.5, -7.0, -10.0, -14.0):
            self.assertGreater(half_point_value(s, -s)["probability_gain"], 0.0)

    def test_the_three_is_the_most_valuable_half_point(self):
        vals = {s: half_point_value(s, -s)["cents"]
                for s in (-1, -1.5, -2, -2.5, -3, -3.5, -4, -6, -7, -10, -14)}
        best = max(vals, key=vals.get)
        self.assertIn(best, (-3.0, -3.5), f"best half point was {best}")

    def test_no_half_point_is_worth_the_twenty_cents_books_charge(self):
        """The model's headline finding, pinned.

        The best half point on the board is worth about twelve cents. Paying a
        flat twenty for any of them is a losing trade, every time.
        """
        worst_case = max(half_point_value(s, -s)["cents"]
                         for s in (-1, -1.5, -2, -2.5, -3, -3.5, -4, -6,
                                   -6.5, -7, -7.5, -9.5, -10, -13.5, -14))
        self.assertLess(worst_case, 20.0)

    def test_a_half_point_off_a_key_number_is_worth_much_less(self):
        on_three = half_point_value(-3.0, 3.0)["cents"]
        off_nine = half_point_value(-9.5, 9.5)["cents"]
        self.assertGreater(on_three, off_nine * 1.5)


class TestNoHiddenLean(unittest.TestCase):
    """The bug that killed the first MLB model, pinned shut here too."""

    def test_an_empty_card_is_exactly_a_coin_flip(self):
        for s in (-1.0, -2.5, -3.0, -7.0, 3.5, 6.0):
            f = forecast_nfl("a @ b", s)
            self.assertAlmostEqual(f.p_resolved, 0.5, places=6,
                                   msg=f"spread {s} leaned {f.side} {f.p_resolved}")
            self.assertEqual(f.band, "NO BET")

    def test_two_league_average_teams_move_the_line_by_nothing(self):
        f = forecast_nfl("a @ b", -3.0, home_net_ppg=0.0, away_net_ppg=0.0,
                         games_played=12)
        self.assertAlmostEqual(f.p_resolved, 0.5, places=6)

    def test_the_rating_is_anchored_to_the_market_not_the_posted_number(self):
        f = forecast_nfl("a @ b", -3.0, home_net_ppg=0.0, away_net_ppg=0.0,
                         games_played=12)
        market = next(e for e in f.estimates if e.name == "Market")
        rating = next(e for e in f.estimates if e.name == "Power rating")
        self.assertAlmostEqual(rating.margin, market.margin, places=9)

    def test_a_better_home_team_moves_the_forecast_toward_home(self):
        base = forecast_nfl("a @ b", -3.0, home_net_ppg=0.0, away_net_ppg=0.0,
                            games_played=12)
        good = forecast_nfl("a @ b", -3.0, home_net_ppg=8.0, away_net_ppg=0.0,
                            games_played=12)
        self.assertGreater(good.projected, base.projected)
        self.assertEqual(good.side, "HOME")


class TestSampleSizeDiscipline(unittest.TestCase):
    def test_a_rating_earns_its_weight_over_games_played(self):
        self.assertAlmostEqual(rating_weight(1.2, RATING_STABLE_AT), 1.2)
        self.assertAlmostEqual(rating_weight(1.2, RATING_STABLE_AT * 3), 1.2)
        self.assertAlmostEqual(rating_weight(1.2, RATING_STABLE_AT / 2), 0.6)
        self.assertAlmostEqual(rating_weight(1.2, 0), 0.0)
        self.assertAlmostEqual(rating_weight(1.2, None), 0.0)

    def test_week_one_ratings_barely_move_anything(self):
        """A net-points rating on one game is one game of noise."""
        wk1 = forecast_nfl("a @ b", -3.0, home_net_ppg=21.0, away_net_ppg=-21.0,
                           games_played=1)
        wk12 = forecast_nfl("a @ b", -3.0, home_net_ppg=21.0, away_net_ppg=-21.0,
                            games_played=12)
        self.assertLess(abs(wk1.projected - 3.0), abs(wk12.projected - 3.0))

    def test_no_games_played_drops_the_rating_entirely(self):
        f = forecast_nfl("a @ b", -3.0, home_net_ppg=10.0, away_net_ppg=-10.0)
        self.assertEqual([e.name for e in f.estimates], ["Market"])
        self.assertAlmostEqual(f.p_resolved, 0.5, places=6)


class TestThePricesAreInformation(unittest.TestCase):
    def test_a_line_and_an_expected_margin_are_not_the_same_thing(self):
        """The key numbers break the intuition, and that is the point.

        An even market on -3 does NOT mean the true margin is 3. Home covering
        -3 needs a margin of 4, which the fit says is RARER than a smooth curve
        predicts (0.74), while the mirror numbers 3 and 7 on the away side are
        boosted. So the even-money margin sits below the number.
        """
        at_three, _ = fair_spread(-3.0, -110, -110)
        self.assertLess(at_three, 3.0)
        self.assertGreater(at_three, 2.0)

    def test_minus_two_and_a_half_is_worth_far_more_than_minus_three(self):
        """The best-known asymmetry in NFL betting, reproduced from the
        distribution rather than asserted.

        At -2.5 the 3-point margin COVERS for you; at -3 the same margin is a
        push. Half a point buys the single most common outcome in the sport.
        """
        at_three, _ = fair_spread(-3.0, -110, -110)
        at_two_half, _ = fair_spread(-2.5, -110, -110)
        self.assertGreater(at_three - at_two_half, 0.7,
                           "half a point across 3 should be worth most of a point of margin")

    def test_a_juiced_home_price_reads_fair_above_the_number(self):
        mu, _ = fair_spread(-3.0, -130, 110)
        self.assertGreater(mu, 3.0)

    def test_a_wide_market_is_a_less_certain_one(self):
        """Same discipline as the MLB model: markup is not opinion.

        A -160/+120 quote holds 7.0% against a main line's 4.8%. Read
        proportionally it looks like a stronger home lean than it is; part of
        it is the book's margin, so the read is pulled back toward even.
        """
        even, _ = fair_spread(-3.0, -110, -110)
        wide_shrunk, _ = fair_spread(-3.0, -160, 120)
        self.assertAlmostEqual(hold(-160, 120), 0.0699, places=3)
        self.assertAlmostEqual(market_confidence(hold(-160, 120)), 0.715, places=2)
        self.assertAlmostEqual(market_confidence(0.048), 1.0, msg="a normal hold is untouched")
        # it still leans home, just far less than the raw prices suggest
        self.assertGreater(wide_shrunk, even)

    def test_a_normal_hold_is_left_alone(self):
        self.assertAlmostEqual(market_confidence(0.048), 1.0)
        self.assertAlmostEqual(market_confidence(0.10), 0.5)
        self.assertAlmostEqual(hold(-110, -110), 0.0476, places=3)

    def test_implied_and_fair_price_are_inverses(self):
        for p in (0.4, 0.5, 0.52, 0.6, 0.75):
            self.assertAlmostEqual(implied(fair_price(p)), p, places=9)


class TestTheQuarterbackIsNotDoubleCounted(unittest.TestCase):
    def test_a_missing_quarterback_moves_no_number(self):
        """The line moves three to seven points on the announcement, so the
        news is already inside the number being read."""
        base = forecast_nfl("a @ b", -3.0, home_net_ppg=2.0, away_net_ppg=0.0,
                            games_played=12)
        out = forecast_nfl("a @ b", -3.0, home_net_ppg=2.0, away_net_ppg=0.0,
                           games_played=12, home_qb_out=True)
        self.assertAlmostEqual(base.projected, out.projected, places=12)
        self.assertAlmostEqual(base.p_resolved, out.p_resolved, places=12)

    def test_but_it_says_so_loudly(self):
        f = forecast_nfl("a @ b", -3.0, home_qb_out=True)
        note = next(n for n in f.notes if "quarterback" in n)
        self.assertIn("NOT scored", note)
        self.assertIn("already inside", note)


class TestGuards(unittest.TestCase):
    def test_an_absurd_spread_is_refused(self):
        for s in (-45.0, 60.0):
            with self.assertRaises(ValueError):
                forecast_nfl("a @ b", s)

    def test_a_wrong_margin_sd_costs_very_little(self):
        s = sensitivity(1.0)
        self.assertLess(s["probability_points"], 1.0)
        self.assertLess(sensitivity(2.0)["probability_points"], 2.0)

    def test_the_bands_match_the_mlb_model_so_one_record_reads_across_both(self):
        from totals.fullgame import BANDS as MLB_BANDS
        self.assertEqual(BANDS, MLB_BANDS)


class TestOutput(unittest.TestCase):
    def test_a_card_on_a_key_number_says_so(self):
        f = forecast_nfl("a @ b", -3.0, home_price=-110, away_price=-110)
        self.assertTrue(any("key number" in n for n in f.notes))
        self.assertTrue(any("pushes" in n for n in f.notes))

    def test_a_card_off_a_key_number_does_not(self):
        f = forecast_nfl("a @ b", -8.5, home_price=-110, away_price=-110)
        self.assertFalse(any("key number" in n for n in f.notes))

    def test_the_dict_and_the_brief_both_render(self):
        f = forecast_nfl("Jets @ Bills", -6.5, home_price=-115, away_price=-105,
                         home_net_ppg=4.2, away_net_ppg=-3.1, games_played=10)
        d = f.to_dict()
        self.assertEqual(d["sport"], "NFL")
        self.assertIn("half_point", d)
        self.assertIn("cents", f.brief())
        self.assertIn("Jets @ Bills", slate([f]))

    def test_edge_against_a_price_is_signed_correctly(self):
        f = forecast_nfl("a @ b", -3.0, home_price=-150, away_price=130,
                         home_net_ppg=6.0, away_net_ppg=-2.0, games_played=12)
        fair = fair_price(f.p_resolved)
        # A favourite is priced negative, so a SMALLER magnitude is the better
        # price. -130 beats -150; laying more than fair is a losing bet.
        self.assertGreater(f.edge_vs(fair + 20), 0.0, "a cheaper price must be +EV")
        self.assertLess(f.edge_vs(fair - 20), 0.0, "laying over fair must be -EV")


if __name__ == "__main__":
    unittest.main()
