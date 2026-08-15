import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from totals import (  # noqa: E402
    market,
    mlb,
    run_game,
    run_verdict,
    run_verdict_slate,
    wnba,
)
from totals.confidence import BANDS  # noqa: E402
from totals.distributions import (  # noqa: E402
    convolve,
    discrete_total_probs,
    negative_binomial_pmf,
    normal_total_probs,
)

BANDS_ORDER = {b: i for i, b in enumerate(BANDS)}


class TestMarket(unittest.TestCase):
    def test_odds_conversions_round_trip(self):
        for odds in (-250, -110, -101, 100, 145, 900):
            dec = market.american_to_decimal(odds)
            self.assertAlmostEqual(market.decimal_to_american(dec), odds, places=6)

    def test_implied_probability(self):
        self.assertAlmostEqual(market.american_to_prob(-110), 0.5238, places=4)
        self.assertAlmostEqual(market.american_to_prob(+100), 0.5, places=6)

    def test_devig_sums_to_one(self):
        for method in ("multiplicative", "power"):
            r = market.devig(-110, -110, method)
            self.assertAlmostEqual(r.p_over + r.p_under, 1.0, places=6)
            self.assertAlmostEqual(r.p_over, 0.5, places=4)
            self.assertAlmostEqual(r.hold, 0.0476, places=3)

    def test_devig_asymmetric(self):
        r = market.devig(-140, +120)
        self.assertGreater(r.p_over, r.p_under)
        self.assertAlmostEqual(r.p_over + r.p_under, 1.0, places=6)

    def test_ev_is_zero_at_fair_price(self):
        # 55% at +81.8 (fair) should be break-even.
        fair = market.prob_to_american(0.55)
        self.assertAlmostEqual(market.ev_per_unit(0.55, fair), 0.0, places=2)

    def test_ev_negative_at_juiced_price(self):
        self.assertLess(market.ev_per_unit(0.5, -110), 0)

    def test_kelly_zero_without_edge(self):
        self.assertEqual(market.kelly_fraction(0.50, -110), 0.0)

    def test_kelly_scales_with_multiplier(self):
        full = market.kelly_fraction(0.60, -110, multiplier=1.0)
        quarter = market.kelly_fraction(0.60, -110, multiplier=0.25)
        self.assertGreater(full, 0)
        self.assertAlmostEqual(quarter, full / 4.0, places=9)

    def test_push_dilutes_ev_but_not_below_loss(self):
        no_push = market.ev_per_unit(0.55, -110, push_prob=0.0)
        with_push = market.ev_per_unit(0.55, -110, push_prob=0.10)
        self.assertGreater(with_push, no_push)  # the push eats a loss, not a win


class TestDistributions(unittest.TestCase):
    def test_nb_pmf_sums_to_one(self):
        pmf = negative_binomial_pmf(4.4, 4.0)
        self.assertAlmostEqual(sum(pmf), 1.0, places=9)

    def test_nb_mean_and_variance(self):
        mean, r = 4.4, 4.0
        pmf = negative_binomial_pmf(mean, r, kmax=60)
        got_mean = sum(k * p for k, p in enumerate(pmf))
        got_var = sum((k - got_mean) ** 2 * p for k, p in enumerate(pmf))
        self.assertAlmostEqual(got_mean, mean, places=3)
        self.assertAlmostEqual(got_var, mean + mean**2 / r, places=2)
        # sd of MLB team runs per game is right around 3.
        self.assertAlmostEqual(math.sqrt(got_var), 3.04, places=1)

    def test_convolution_preserves_mass_and_mean(self):
        a = negative_binomial_pmf(4.5, 4.0, kmax=60)
        b = negative_binomial_pmf(3.5, 4.0, kmax=60)
        total = convolve(a, b)
        self.assertAlmostEqual(sum(total), 1.0, places=9)
        self.assertAlmostEqual(sum(k * p for k, p in enumerate(total)), 8.0, places=2)

    def test_half_line_cannot_push(self):
        pmf = convolve(negative_binomial_pmf(4.5, 4.0), negative_binomial_pmf(4.0, 4.0))
        probs = discrete_total_probs(pmf, 8.5)
        self.assertEqual(probs.p_push, 0.0)
        self.assertAlmostEqual(probs.p_over + probs.p_under, 1.0, places=9)

    def test_whole_line_pushes(self):
        pmf = convolve(negative_binomial_pmf(4.5, 4.0), negative_binomial_pmf(4.0, 4.0))
        probs = discrete_total_probs(pmf, 9.0)
        self.assertGreater(probs.p_push, 0.03)
        self.assertAlmostEqual(probs.p_over + probs.p_under + probs.p_push, 1.0, places=9)

    def test_normal_line_at_mean_is_a_coin_flip(self):
        probs = normal_total_probs(163.0, 11.5, 163.5)
        self.assertAlmostEqual(probs.p_over, 0.483, places=2)
        self.assertAlmostEqual(probs.p_over + probs.p_under, 1.0, places=9)

    def test_normal_whole_line_pushes(self):
        probs = normal_total_probs(163.0, 11.5, 163.0)
        self.assertGreater(probs.p_push, 0.03)
        self.assertAlmostEqual(probs.p_over + probs.p_under + probs.p_push, 1.0, places=9)


class TestMlb(unittest.TestCase):
    def neutral_game(self, **overrides):
        team = {
            "runs_per_game": mlb.LEAGUE_RUNS_PER_GAME,
            "starter_ra9": mlb.LEAGUE_RUNS_PER_GAME,
            "starter_ip": 6.0,
            "bullpen_ra9": mlb.LEAGUE_RUNS_PER_GAME,
        }
        game = {"away": dict(team, name="A"), "home": dict(team, name="H")}
        game.update(overrides)
        return game

    def test_league_average_game_returns_league_average_total(self):
        p = mlb.project(self.neutral_game())
        self.assertAlmostEqual(p.total, 2 * mlb.LEAGUE_RUNS_PER_GAME, places=6)

    def test_park_factor_scales_the_total(self):
        base = mlb.project(self.neutral_game()).total
        hot = mlb.project(self.neutral_game(park_factor=1.20)).total
        self.assertAlmostEqual(hot, base * 1.20, places=6)

    def test_better_starter_lowers_opponent_runs(self):
        game = self.neutral_game()
        game["home"]["starter_ra9"] = 2.50
        p = mlb.project(game)
        self.assertLess(p.away_score, mlb.LEAGUE_RUNS_PER_GAME)
        self.assertAlmostEqual(p.home_score, mlb.LEAGUE_RUNS_PER_GAME, places=6)

    def test_era_and_ra9_inputs_agree(self):
        by_ra9 = mlb.project(self.neutral_game()).total
        game = self.neutral_game()
        for side in ("away", "home"):
            for role in ("starter", "bullpen"):
                era = mlb.LEAGUE_RUNS_PER_GAME / mlb.ERA_TO_RA9
                game[side].pop(f"{role}_ra9")
                game[side][f"{role}_era"] = era
        self.assertAlmostEqual(mlb.project(game).total, by_ra9, places=6)

    def test_short_starter_gives_bullpen_more_weight(self):
        game = self.neutral_game()
        game["home"]["starter_ra9"] = 2.00
        game["home"]["bullpen_ra9"] = 6.00
        deep = mlb.project(game).away_score
        game["home"]["starter_ip"] = 4.0
        short = mlb.project(game).away_score
        self.assertGreater(short, deep)

    def test_own_park_factor_is_divided_out(self):
        # A team that scores 5.5 in a 1.30 park is not a 5.5 offence.
        game = self.neutral_game()
        game["away"]["runs_per_game"] = 5.50
        game["away"]["own_park_factor"] = 1.30
        p = mlb.project(game)
        self.assertAlmostEqual(p.away_score, 5.50 / 1.15, places=6)

    def test_weather(self):
        self.assertEqual(mlb.weather_factor(None), 1.0)
        self.assertEqual(mlb.weather_factor({"dome": True, "temp_f": 95}), 1.0)
        self.assertGreater(mlb.weather_factor({"temp_f": 95}), 1.0)
        self.assertLess(mlb.weather_factor({"temp_f": 45}), 1.0)
        self.assertLess(mlb.weather_factor({"wind_mph_out": -12}), 1.0)

    def test_weather_is_clamped(self):
        cap = 1.0 + mlb.WEATHER_CLAMP
        self.assertLessEqual(mlb.weather_factor({"temp_f": 120, "wind_mph_out": 40}), cap)
        self.assertGreaterEqual(mlb.weather_factor({"temp_f": 20, "wind_mph_out": -40}),
                                1.0 - mlb.WEATHER_CLAMP)

    def test_ordinary_summer_weather_does_not_hit_the_clamp(self):
        """The clamp is a guardrail for extremes. When it fires on a routine
        August game it stops being an adjustment and becomes a constant, which
        is how a +10% cap turned into a flat +0.9 runs on every outdoor game."""
        cap = 1.0 + mlb.WEATHER_CLAMP
        for temp, wind in ((88, 8), (89, 8), (83, 11), (90, 10), (88, 11), (91, 11)):
            f = mlb.weather_factor({"temp_f": temp, "wind_mph_out": wind})
            self.assertLess(f, cap - 1e-9,
                            "%dF / %dmph wind should not cap out" % (temp, wind))

    def test_temperature_is_symmetric_across_the_calendar(self):
        """Anchored to a seasonal norm, not 70F: cold games suppress, hot games
        inflate. Against a 70F reference nearly every game in summer is a
        one-way boost, on top of a league constant that already averages over
        those same hot games."""
        april = mlb.weather_factor({"temp_f": 55})
        september = mlb.weather_factor({"temp_f": 93})
        self.assertLess(april, 1.0)
        self.assertGreater(september, 1.0)
        self.assertAlmostEqual(mlb.weather_factor({"temp_f": mlb.TEMP_REFERENCE_F}), 1.0, places=9)

    def test_regression_leaves_a_league_average_starter_alone(self):
        lg_era = mlb.LEAGUE_RUNS_PER_GAME / mlb.ERA_TO_RA9
        self.assertAlmostEqual(mlb.regress_era(lg_era, 130, lg_era), lg_era, places=9)
        self.assertAlmostEqual(mlb.regress_era(lg_era, 10, lg_era), lg_era, places=9)

    def test_regression_pulls_extremes_toward_league(self):
        lg_era = mlb.LEAGUE_RUNS_PER_GAME / mlb.ERA_TO_RA9
        hot = mlb.regress_era(1.53, 40, lg_era)
        cold = mlb.regress_era(7.84, 45, lg_era)
        self.assertTrue(1.53 < hot < lg_era, hot)
        self.assertTrue(lg_era < cold < 7.84, cold)

    def test_more_innings_means_less_regression(self):
        lg_era = mlb.LEAGUE_RUNS_PER_GAME / mlb.ERA_TO_RA9
        small = mlb.regress_era(2.50, 30, lg_era)
        large = mlb.regress_era(2.50, 200, lg_era)
        self.assertLess(large, small)  # the bigger sample keeps more of its own ERA
        self.assertLess(2.50, large)

    def test_missing_season_ip_still_regresses(self):
        lg_era = mlb.LEAGUE_RUNS_PER_GAME / mlb.ERA_TO_RA9
        assumed = mlb.regress_era(2.00, None, lg_era)
        explicit = mlb.regress_era(2.00, mlb.DEFAULT_STARTER_SEASON_IP, lg_era)
        self.assertAlmostEqual(assumed, explicit, places=9)
        self.assertGreater(assumed, 2.00)

    def test_zero_innings_is_no_evidence_at_all(self):
        """Missing innings and zero innings are different claims.

        Missing means "an ERA, without saying how many innings back it"; zero
        means there is nothing behind it, so the answer is the league average.
        """
        lg_era = mlb.LEAGUE_RUNS_PER_GAME / mlb.ERA_TO_RA9
        self.assertAlmostEqual(mlb.regress_era(0.00, 0, lg_era), lg_era, places=9)
        self.assertAlmostEqual(mlb.regress_era(1.20, 0, lg_era), lg_era, places=9)
        # ...and it must not quietly reuse the rotation-regular default.
        self.assertNotAlmostEqual(mlb.regress_era(0.00, 0, lg_era),
                                  mlb.regress_era(0.00, None, lg_era), places=3)

    def test_a_blank_starter_does_not_become_the_best_pitcher_alive(self):
        """A form hands back 0 when the user hasn't got the number.

        Read literally, 0.00 ERA over 0.0 IP once regressed to 1.83 and produced
        the largest UNDER stake in the log; the game went 14 runs.
        """
        game = self.neutral_game()
        game["home"].pop("starter_ra9")
        game["home"]["starter_era"] = 0.0
        game["home"]["starter_season_ip"] = 0.0
        blank = mlb.project(game)
        neutral = mlb.project(self.neutral_game())
        self.assertAlmostEqual(blank.total, neutral.total, places=6)

    def test_regression_shrinks_disagreement_with_the_market(self):
        """A small-sample blowup starter should not move the total three runs."""
        game = self.neutral_game()
        game["away"].pop("starter_ra9")
        game["away"]["starter_era"] = 7.84
        game["away"]["starter_season_ip"] = 45
        raw = mlb.project(dict(game, regress_starters=False)).total
        reg = mlb.project(game).total
        neutral = 2 * mlb.LEAGUE_RUNS_PER_GAME
        self.assertGreater(raw, reg)
        self.assertLess(abs(reg - neutral), abs(raw - neutral))

    def test_regression_can_be_switched_off(self):
        """The away starter is the one getting hit, so the home team scores."""
        game = self.neutral_game()
        game["away"].pop("starter_ra9")
        game["away"]["starter_era"] = 7.84
        game["away"]["starter_season_ip"] = 45
        off = mlb.project(dict(game, regress_starters=False))
        on = mlb.project(game)
        # Away offence faces an untouched league-average home staff either way.
        self.assertAlmostEqual(off.away_score, mlb.LEAGUE_RUNS_PER_GAME, places=6)
        self.assertAlmostEqual(on.away_score, mlb.LEAGUE_RUNS_PER_GAME, places=6)
        # The home side is where the bad starter shows up, and regression tames it.
        self.assertGreater(off.home_score, mlb.LEAGUE_RUNS_PER_GAME)
        self.assertGreater(off.home_score, on.home_score)
        self.assertGreater(on.home_score, mlb.LEAGUE_RUNS_PER_GAME)

    def test_park_factor_accepts_either_scale(self):
        self.assertAlmostEqual(mlb.normalize_park_factor(102), 1.02, places=9)
        self.assertAlmostEqual(mlb.normalize_park_factor(1.02), 1.02, places=9)
        self.assertAlmostEqual(mlb.normalize_park_factor(100), 1.00, places=9)
        self.assertAlmostEqual(mlb.normalize_park_factor(0.92), 0.92, places=9)

    def test_savant_scale_gives_the_same_projection_as_decimals(self):
        """102 and 1.02 must mean the same thing, everywhere they appear."""
        decimal = self.neutral_game(park_factor=1.02)
        decimal["away"]["own_park_factor"] = 0.98
        decimal["home"]["own_park_factor"] = 1.02
        hundred = self.neutral_game(park_factor=102)
        hundred["away"]["own_park_factor"] = 98
        hundred["home"]["own_park_factor"] = 102
        self.assertAlmostEqual(mlb.project(decimal).total, mlb.project(hundred).total, places=9)

    def test_hundred_scale_no_longer_collapses_the_projection(self):
        """The bug this guards: 100-scale factors drove every total to ~0.3 runs
        and made the model shout UNDER on games it had never really seen."""
        g = self.neutral_game(park_factor=102)
        g["away"]["own_park_factor"] = 98
        g["home"]["own_park_factor"] = 102
        total = mlb.project(g).total
        self.assertGreater(total, 7.0)
        self.assertLess(total, 12.0)

    def test_projected_totals_land_in_a_believable_range(self):
        p = mlb.project(self.neutral_game(park_factor=1.0))
        probs = p.total_probs(8.5)
        self.assertAlmostEqual(probs.p_over + probs.p_under, 1.0, places=9)
        self.assertTrue(0.40 < probs.p_over < 0.60)


class TestWnba(unittest.TestCase):
    def neutral_game(self, **overrides):
        team = {
            "pace": wnba.LEAGUE_PACE,
            "off_rating": wnba.LEAGUE_RATING,
            "def_rating": wnba.LEAGUE_RATING,
            "rest_days": 2,
        }
        game = {"away": dict(team, name="A"), "home": dict(team, name="H")}
        game.update(overrides)
        return game

    def test_league_average_game(self):
        p = wnba.project(self.neutral_game(home_court_points=0.0))
        expected = 2 * wnba.LEAGUE_PACE * wnba.LEAGUE_RATING / 100.0
        # Only overtime should separate the two.
        self.assertAlmostEqual(p.total - expected, wnba.overtime_points(0.0), places=6)

    def test_home_court_moves_margin_not_total(self):
        flat = wnba.project(self.neutral_game(home_court_points=0.0))
        hca = wnba.project(self.neutral_game(home_court_points=3.0))
        self.assertAlmostEqual(hca.margin, 3.0, places=6)
        self.assertAlmostEqual(flat.margin, 0.0, places=6)
        # Totals differ only through the overtime term, which shrinks as the
        # projected margin grows.
        self.assertLess(abs(hca.total - flat.total), 0.5)

    def test_pace_drives_the_total(self):
        slow = wnba.project(self.neutral_game()).total
        game = self.neutral_game()
        game["away"]["pace"] = 90.0
        game["home"]["pace"] = 90.0
        self.assertGreater(wnba.project(game).total, slow + 15)

    def test_defence_suppresses_the_opponent(self):
        game = self.neutral_game(home_court_points=0.0)
        game["home"]["def_rating"] = 90.0
        p = wnba.project(game)
        self.assertLess(p.away_score, p.home_score)

    def test_back_to_back_costs_points(self):
        rested = wnba.project(self.neutral_game()).total
        game = self.neutral_game()
        game["away"]["rest_days"] = 0
        tired = wnba.project(game).total
        self.assertLess(tired, rested)

    def test_overtime_is_biggest_in_pick_em_games(self):
        self.assertGreater(wnba.overtime_points(0.0), wnba.overtime_points(12.0))
        self.assertLess(wnba.overtime_points(25.0), 0.2)
        # A coin-flip game should add about a point, not ten.
        self.assertTrue(0.5 < wnba.overtime_points(0.0) < 1.5)


class TestEndToEnd(unittest.TestCase):
    def test_mlb_game_report(self):
        game = {
            "away": {"name": "A", "runs_per_game": 4.8, "starter_era": 3.2, "starter_ip": 6.0,
                     "bullpen_era": 3.6},
            "home": {"name": "H", "runs_per_game": 4.2, "starter_era": 4.5, "starter_ip": 5.0,
                     "bullpen_era": 4.4},
            "park_factor": 1.05,
            "market": {"line": 8.5, "over_odds": -110, "under_odds": -110},
        }
        r = run_game("mlb", game)
        self.assertEqual(r["sport"], "MLB")
        self.assertEqual(r["matchup"], "A @ H")
        self.assertIn(r["best_side"], ("OVER", "UNDER"))
        self.assertAlmostEqual(r["p_over"] + r["p_under"] + r["p_push"], 1.0, places=3)
        self.assertGreaterEqual(r["kelly_stake_pct"], 0.0)
        # Edges are measured against the market's implied MEAN, not the posted
        # line, so that both sides of the comparison are the same quantity.
        self.assertAlmostEqual(
            r["raw_edge"], round(r["model_total"] - r["market_implied_total"], 2), places=2)
        self.assertAlmostEqual(
            r["blended_edge"], round(r["projected_total"] - r["market_implied_total"], 2), places=2)
        self.assertGreater(r["market_implied_total"], 8.5)  # median < mean, right-skewed

    def test_wnba_game_report(self):
        game = {
            "away": {"name": "A", "pace": 82, "off_rating": 105, "def_rating": 100},
            "home": {"name": "H", "pace": 80, "off_rating": 102, "def_rating": 98},
            "market": {"line": 164.5, "over_odds": -110, "under_odds": -110},
        }
        r = run_game("wnba", game)
        self.assertEqual(r["sport"], "WNBA")
        self.assertGreater(r["model_total"], 120)
        self.assertLess(r["model_total"], 200)
        self.assertAlmostEqual(r["p_over"] + r["p_under"] + r["p_push"], 1.0, places=3)

    def test_model_backs_the_side_it_projects(self):
        game = {
            "away": {"name": "A", "pace": 90, "off_rating": 112, "def_rating": 108},
            "home": {"name": "H", "pace": 90, "off_rating": 110, "def_rating": 107},
            "market": {"line": 150.5, "over_odds": -110, "under_odds": -110},
        }
        r = run_game("wnba", game)
        self.assertGreater(r["model_total"], 150.5)
        self.assertEqual(r["best_side"], "OVER")
        self.assertGreater(r["ev_per_unit"], 0)

    def test_edge_vs_market_agrees_with_ev_on_a_push_line(self):
        """A whole-number line used to print a negative edge beside a positive
        EV, because the model's probability counted pushes and the de-vigged
        market price did not."""
        game = {
            "away": {"name": "A", "runs_per_game": 4.37, "starter_era": 7.25,
                     "starter_season_ip": 104, "starter_ip": 4.1, "bullpen_era": 3.45,
                     "own_park_factor": 97},
            "home": {"name": "H", "runs_per_game": 4.52, "starter_era": 4.80,
                     "starter_season_ip": 13, "starter_ip": 4.1, "bullpen_era": 4.17,
                     "own_park_factor": 104},
            "park_factor": 104, "weather": {"dome": True},
            "market": {"line": 9.0, "over_odds": -110, "under_odds": -110},
        }
        r = run_game("mlb", game)
        self.assertGreater(r["p_push"], 0.05)  # a real push chunk
        # A positive EV must imply a positive edge: you cannot beat the price
        # while agreeing with the market. The converse is fine -- a small
        # disagreement that fails to cover the hold is +edge and -EV.
        if r["ev_per_unit"] > 0:
            self.assertGreater(r["prob_edge_vs_market"], 0)
        self.assertGreater(r["best_side_prob_decided"], r["best_side_prob"])

    def test_push_line_edge_is_positive_when_the_model_really_disagrees(self):
        """The same invariant on a game where the model has a genuine read,
        rather than the skew artefact that used to manufacture one."""
        game = {
            "away": {"name": "A", "runs_per_game": 5.9, "starter_era": 5.9,
                     "starter_season_ip": 150, "starter_ip": 4.0, "bullpen_era": 5.9},
            "home": {"name": "H", "runs_per_game": 5.9, "starter_era": 5.9,
                     "starter_season_ip": 150, "starter_ip": 4.0, "bullpen_era": 5.9},
            "market": {"line": 9.0, "over_odds": -110, "under_odds": -110},
        }
        r = run_game("mlb", game, model_weight=1.0)
        self.assertGreater(r["p_push"], 0.04)
        self.assertEqual(r["best_side"], "OVER")
        self.assertGreater(r["ev_per_unit"], 0)
        self.assertGreater(r["prob_edge_vs_market"], 0)
        self.assertGreater(r["best_side_prob_decided"], 110 / 210)

    def test_deferring_to_the_market_means_no_bet(self):
        """At weight 0 the model adopts the market's own probabilities, so EV is
        exactly minus the hold and nothing is worth backing.

        Previously it still claimed roughly +5% on the under of every game: the
        posted line was treated as a mean when it is a median, and centring a
        right-skewed distribution on it left over half the mass underneath."""
        base = {
            "away": {"name": "A", "runs_per_game": 4.49, "starter_era": 4.18,
                     "starter_season_ip": 130, "starter_ip": 5.2, "bullpen_era": 4.18},
            "home": {"name": "H", "runs_per_game": 4.49, "starter_era": 4.18,
                     "starter_season_ip": 130, "starter_ip": 5.2, "bullpen_era": 4.18},
        }
        for line in (7.5, 8.0, 8.5, 9.0, 9.5, 10.0, 11.5):
            game = dict(base, market={"line": line, "over_odds": -110, "under_odds": -110})
            r = run_game("mlb", game, model_weight=0.0)
            self.assertEqual(r["kelly_stake_pct"], 0.0, "line %s should pass" % line)
            self.assertLess(r["ev_per_unit"], 0, "line %s should be -EV" % line)
            self.assertAlmostEqual(r["prob_edge_vs_market"], 0.0, places=3)

    def test_market_implied_total_sits_above_a_baseball_line(self):
        """Right-skewed scoring: the line is the median, the mean is higher."""
        game = {
            "away": {"name": "A", "runs_per_game": 4.49, "starter_era": 4.18,
                     "starter_season_ip": 130, "starter_ip": 5.2, "bullpen_era": 4.18},
            "home": {"name": "H", "runs_per_game": 4.49, "starter_era": 4.18,
                     "starter_season_ip": 130, "starter_ip": 5.2, "bullpen_era": 4.18},
            "market": {"line": 9.0, "over_odds": -110, "under_odds": -110},
        }
        r = run_game("mlb", game)
        self.assertGreater(r["market_implied_total"], 9.0)
        self.assertLess(r["market_implied_total"], 10.5)

    def test_wnba_line_is_its_own_implied_mean(self):
        """Basketball totals are modelled as symmetric, so median == mean and
        the correction is a no-op there."""
        game = {
            "away": {"name": "A", "pace": wnba.LEAGUE_PACE,
                     "off_rating": wnba.LEAGUE_RATING, "def_rating": wnba.LEAGUE_RATING},
            "home": {"name": "H", "pace": wnba.LEAGUE_PACE,
                     "off_rating": wnba.LEAGUE_RATING, "def_rating": wnba.LEAGUE_RATING},
            "market": {"line": 168.5, "over_odds": -110, "under_odds": -110},
        }
        r = run_game("wnba", game)
        self.assertAlmostEqual(r["market_implied_total"], 168.5, places=1)

    def test_half_line_edge_is_unaffected(self):
        """With no push, decided-outcome and raw probabilities are the same."""
        game = {
            "away": {"name": "A", "runs_per_game": 4.8, "starter_era": 3.2,
                     "starter_ip": 6.0, "bullpen_era": 3.6},
            "home": {"name": "H", "runs_per_game": 4.2, "starter_era": 4.5,
                     "starter_ip": 5.0, "bullpen_era": 4.4},
            "market": {"line": 8.5, "over_odds": -110, "under_odds": -110},
        }
        r = run_game("mlb", game)
        self.assertEqual(r["p_push"], 0.0)
        self.assertAlmostEqual(r["best_side_prob_decided"], r["best_side_prob"], places=4)

    def test_no_market_still_projects(self):
        game = {
            "away": {"name": "A", "pace": 80, "off_rating": 101, "def_rating": 101},
            "home": {"name": "H", "pace": 80, "off_rating": 101, "def_rating": 101},
        }
        r = run_game("wnba", game)
        self.assertNotIn("line", r)
        self.assertIn("projected_total", r)

    def test_unknown_sport_rejected(self):
        with self.assertRaises(ValueError):
            run_game("nfl", {"away": {}, "home": {}})

    def test_example_slates_run(self):
        import json

        here = os.path.dirname(os.path.abspath(__file__))
        for sport, name in (("mlb", "mlb_slate.json"), ("wnba", "wnba_slate.json")):
            path = os.path.join(here, "..", "examples", name)
            with open(path, encoding="utf-8") as handle:
                games = json.load(handle)["games"]
            for game in games:
                r = run_game(sport, game)
                self.assertIn("ev_per_unit", r)

    def test_cli_runs(self):
        import contextlib
        import io

        from totals.cli import main

        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(here, "..", "examples", "mlb_slate.json")
        for fmt in ("table", "json"):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = main(["mlb", path, "--format", fmt])
            self.assertEqual(code, 0)
            self.assertIn("Rockies", buf.getvalue())


class TestShrinkageAndStaking(unittest.TestCase):
    """The model is small; the closing line is not. These guard the safety rails."""

    def wnba_game(self, line):
        return {
            "away": {"name": "A", "pace": 88, "off_rating": 110, "def_rating": 108},
            "home": {"name": "H", "pace": 88, "off_rating": 109, "def_rating": 107},
            "market": {"line": line, "over_odds": -110, "under_odds": -110},
        }

    def test_blend_lands_halfway_by_default(self):
        r = run_game("wnba", self.wnba_game(150.5))
        self.assertAlmostEqual(
            r["projected_total"], (r["model_total"] + 150.5) / 2.0, places=1
        )

    def test_model_weight_one_disables_shrinkage(self):
        r = run_game("wnba", self.wnba_game(150.5), model_weight=1.0)
        self.assertAlmostEqual(r["projected_total"], r["model_total"], places=6)
        self.assertAlmostEqual(r["raw_edge"], r["blended_edge"], places=6)

    def test_model_weight_zero_defers_entirely_to_the_market(self):
        r = run_game("wnba", self.wnba_game(150.5), model_weight=0.0)
        self.assertAlmostEqual(r["projected_total"], 150.5, places=6)
        self.assertAlmostEqual(r["blended_edge"], 0.0, places=6)
        # No disagreement with the market means no bet worth making.
        self.assertLess(r["ev_per_unit"], 0.0)

    def test_shrinkage_shrinks_the_edge(self):
        strong = run_game("wnba", self.wnba_game(150.5), model_weight=1.0)
        shrunk = run_game("wnba", self.wnba_game(150.5))
        self.assertEqual(strong["best_side"], shrunk["best_side"])
        self.assertLess(shrunk["ev_per_unit"], strong["ev_per_unit"])

    def test_blending_preserves_the_margin_lean(self):
        game = self.wnba_game(150.5)
        game["home"]["off_rating"] = 118
        r = run_game("wnba", game)
        self.assertGreater(r["model_margin"], 0)

    def test_stake_is_capped(self):
        r = run_game("wnba", self.wnba_game(120.5), max_stake_pct=2.0)
        self.assertGreater(r["kelly_uncapped_pct"], 2.0)  # a 30-point edge is absurd
        self.assertEqual(r["kelly_stake_pct"], 2.0)

    def test_no_stake_without_edge(self):
        r = run_game("wnba", self.wnba_game(150.5), model_weight=0.0)
        self.assertEqual(r["kelly_stake_pct"], 0.0)
        self.assertFalse(r["recommended"])

    def test_a_sliver_of_an_edge_is_not_a_recommendation(self):
        """Kelly is continuous; a recommendation should not be.

        Find the line where the model is barely on the right side of the juice,
        then confirm it reports positive EV and still refuses to call it a play.
        """
        for line in [x / 100.0 for x in range(19000, 22000)]:
            r = run_game("wnba", self.wnba_game(line))
            if 0 < r["kelly_uncapped_pct"] < r["min_stake_pct"]:
                break
        else:  # pragma: no cover
            self.fail("no line produced a sub-floor stake")
        self.assertGreater(r["ev_per_unit"], 0.0)
        self.assertFalse(r["recommended"])
        self.assertEqual(r["kelly_stake_pct"], 0.0)
        # The real size stays visible even when it is not being advised.
        self.assertGreater(r["kelly_uncapped_pct"], 0.0)

    def test_a_real_edge_still_clears_the_floor(self):
        r = run_game("wnba", self.wnba_game(140.5))
        self.assertTrue(r["recommended"])
        self.assertGreaterEqual(r["kelly_stake_pct"], r["min_stake_pct"])

    def test_betting_overs_only_declines_an_under(self):
        game = self.wnba_game(300.5)  # way above any projection -> model likes UNDER
        both = run_game("wnba", game)
        self.assertEqual(both["best_side"], "UNDER")
        self.assertTrue(both["recommended"])

        over_only = run_game("wnba", game, sides="over")
        self.assertFalse(over_only["recommended"])
        self.assertEqual(over_only["kelly_stake_pct"], 0.0)
        self.assertIn("under", over_only["not_recommended_because"])

    def test_the_filter_never_touches_the_projection_or_the_odds(self):
        """Filtering is a betting rule, not a modelling one.

        Suppressing a side would corrupt the number the other side is derived
        from, so everything the model actually believes must come through
        unchanged -- only the recommendation is withheld.
        """
        game = self.wnba_game(300.5)
        both = run_game("wnba", game)
        over_only = run_game("wnba", game, sides="over")
        for key in ("model_total", "projected_total", "p_over", "p_under", "p_push",
                    "best_side", "best_side_prob", "ev_per_unit", "fair_odds",
                    "market_implied_total", "kelly_uncapped_pct"):
            self.assertEqual(both[key], over_only[key], key)

    def test_betting_overs_only_still_takes_an_over(self):
        game = self.wnba_game(140.5)  # far below any projection -> model likes OVER
        r = run_game("wnba", game, sides="over")
        self.assertEqual(r["best_side"], "OVER")
        self.assertTrue(r["recommended"])
        self.assertIsNone(r["not_recommended_because"])

    def test_every_refusal_says_which_rail_stopped_it(self):
        reasons = {
            run_game("wnba", self.wnba_game(300.5), sides="over")["not_recommended_because"],
            run_game("wnba", self.wnba_game(150.5), model_weight=0.0)["not_recommended_because"],
            run_game("wnba", self.wnba_game(150.5), min_stake_pct=5.0)["not_recommended_because"],
        }
        self.assertEqual(len(reasons), 3)
        self.assertTrue(all(r for r in reasons))

    def test_the_floor_can_be_lowered(self):
        game = self.wnba_game(150.5)
        loose = run_game("wnba", game, min_stake_pct=0.0)
        strict = run_game("wnba", game, min_stake_pct=5.0)
        self.assertGreaterEqual(loose["kelly_stake_pct"], strict["kelly_stake_pct"])
        self.assertFalse(strict["recommended"])

    def test_mlb_blend_rebuilds_the_run_distribution(self):
        game = {
            "away": {"name": "A", "runs_per_game": 6.0, "starter_ra9": 6.0, "starter_ip": 5.0,
                     "bullpen_ra9": 6.0},
            "home": {"name": "H", "runs_per_game": 6.0, "starter_ra9": 6.0, "starter_ip": 5.0,
                     "bullpen_ra9": 6.0},
            "market": {"line": 8.5, "over_odds": -110, "under_odds": -110},
        }
        full = run_game("mlb", game, model_weight=1.0)
        half = run_game("mlb", game)
        # Same side, but the shrunk projection is less confident about it.
        self.assertEqual(full["best_side"], "OVER")
        self.assertEqual(half["best_side"], "OVER")
        self.assertLess(half["p_over"], full["p_over"])
        self.assertAlmostEqual(half["p_over"] + half["p_under"] + half["p_push"], 1.0, places=6)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestConfidenceModel(unittest.TestCase):
    """The verdict model: a side and a band, no price anywhere."""

    def mlb_game(self, **over):
        g = {
            "away": {"name": "A", "runs_per_game": 4.52, "starter_era": 4.20,
                     "starter_season_ip": 140, "starter_ip": 5.5, "bullpen_era": 4.20},
            "home": {"name": "H", "runs_per_game": 4.52, "starter_era": 4.20,
                     "starter_season_ip": 140, "starter_ip": 5.5, "bullpen_era": 4.20},
            "line": 9.0,
            "h2h": {"avg_total": 9.0, "games": 8},
            "form": {"away_avg_total": 9.0, "home_avg_total": 9.0, "games": 10},
        }
        g.update(over)
        return g

    def wnba_game(self, **over):
        g = {
            "away": {"name": "A", "pace": 80, "off_rating": 107, "def_rating": 107},
            "home": {"name": "H", "pace": 80, "off_rating": 107, "def_rating": 107},
            "line": 171.0,
            "h2h": {"avg_total": 171.0, "games": 4},
            "form": {"away_avg_total": 171.0, "home_avg_total": 171.0, "games": 8},
        }
        g.update(over)
        return g

    def test_it_reports_no_price_anywhere(self):
        r = run_verdict("mlb", self.mlb_game())
        for banned in ("ev_per_unit", "kelly_stake_pct", "best_side_odds", "fair_odds",
                       "book_hold", "market_p_over_novig", "recommended"):
            self.assertNotIn(banned, r)
        self.assertIn("band", r)
        self.assertIn("win_pct", r)

    def test_a_line_needs_no_odds_to_become_a_mean(self):
        """The market mean sits above a baseball line, because runs are skewed."""
        r = run_verdict("mlb", self.mlb_game(line=9.0))
        self.assertGreater(r["market_mean"], 9.0)
        self.assertLess(r["market_mean"], 10.5)

    def test_symmetric_scoring_puts_the_mean_on_the_line(self):
        r = run_verdict("wnba", self.wnba_game(line=171.0))
        self.assertAlmostEqual(r["market_mean"], 171.0, places=1)

    def test_bands_only_ever_step_down(self):
        """Every fault in this project's history arrived dressed as confidence."""
        from totals.confidence import BANDS, band_for, _step_down
        for b in BANDS:
            self.assertEqual(BANDS.index(_step_down(b)), max(0, BANDS.index(b) - 1))
        self.assertEqual(_step_down("HIGH", 5), "NO PLAY")
        self.assertEqual(band_for(0.99), "HIGH")
        self.assertEqual(band_for(0.50), "NO PLAY")

    def test_a_trend_pointing_the_other_way_costs_a_band(self):
        strong = {"h2h": {"avg_total": 20.0, "games": 8}}   # screams over
        agree = run_verdict("mlb", self.mlb_game(line=6.5, **strong))
        dissent = run_verdict("mlb", self.mlb_game(
            line=6.5, h2h={"avg_total": 3.0, "games": 8}))
        self.assertEqual(agree["side"], "OVER")
        self.assertIn("head to head points the other way (under)",
                      " ".join(dissent["downgrades"]))
        self.assertLess(BANDS_ORDER[dissent["band"]], BANDS_ORDER[agree["band"]])

    def test_no_trend_data_at_all_is_itself_a_downgrade(self):
        bare = run_verdict("mlb", self.mlb_game(line=6.5, h2h=None, form=None))
        self.assertIn("no head-to-head or recent form", " ".join(bare["downgrades"]))

    def test_a_blank_starter_costs_confidence_rather_than_earning_it(self):
        g = self.mlb_game(line=6.5)
        g["home"]["starter_era"] = 0.0
        g["home"]["starter_season_ip"] = 0.0
        r = run_verdict("mlb", g)
        self.assertTrue(any("league average arm" in f for f in r["flags"]))
        self.assertIn("inputs behind it are thin", " ".join(r["downgrades"]))

    def test_an_impossible_number_names_itself(self):
        """A typo does not announce itself -- it gets absorbed.

        401 average innings per start was silently read as "goes all nine",
        which removed the bullpen from the calculation and moved the projection
        half a run, with nothing on the page to say so.
        """
        g = self.mlb_game()
        g["away"]["starter_ip"] = 401
        r = run_verdict("mlb", g)
        self.assertTrue(any("average IP per start is 401" in f for f in r["flags"]), r["flags"])
        self.assertIn("inputs behind it are thin", " ".join(r["downgrades"]))

    def test_every_ranged_field_is_actually_checked(self):
        from totals.confidence import FIELD_RANGES
        for sport, ranges in FIELD_RANGES.items():
            build = self.mlb_game if sport == "MLB" else self.wnba_game
            for key, (lo, hi, label) in ranges.items():
                g = build()
                g["away"][key] = hi * 10 + 1
                flags = run_verdict(sport.lower(), g)["flags"]
                self.assertTrue(any(label in f and "outside the possible range" in f
                                    for f in flags),
                                f"{sport}.{key} above range went unflagged: {flags}")

    def test_a_plausible_number_is_left_alone(self):
        for sport in ("mlb", "wnba"):
            g = self.mlb_game() if sport == "mlb" else self.wnba_game()
            self.assertEqual(
                [f for f in run_verdict(sport, g)["flags"] if "outside the possible" in f], [])

    def test_a_nonsense_trend_is_flagged_too(self):
        r = run_verdict("mlb", self.mlb_game(h2h={"avg_total": 900, "games": 4}))
        self.assertTrue(any("head-to-head average total is 900" in f for f in r["flags"]),
                        r["flags"])

    def test_every_downgrade_carries_a_note_saying_what_to_look_at(self):
        """The headline names a category; the note has to name the number."""
        g = self.mlb_game(line=6.5, h2h={"avg_total": 3.0, "games": 8})
        g["home"]["starter_season_ip"] = 8
        r = run_verdict("mlb", g)
        self.assertTrue(r["downgrades"])
        self.assertEqual(len(r["downgrades"]), len(r["downgrade_notes"]))
        for note in r["downgrade_notes"]:
            self.assertTrue(note.strip(), "a downgrade came through with an empty note")
            self.assertTrue(note[0].isupper(), note)
            self.assertTrue(note.rstrip().endswith("."), note)
        joined = " ".join(r["downgrade_notes"])
        self.assertIn("3.0", joined)   # the dissenting head-to-head value
        self.assertIn("8 innings", joined)   # the thin-sample flag, verbatim

    def test_a_clean_verdict_has_no_notes(self):
        r = run_verdict("mlb", self.mlb_game())
        self.assertEqual(r["downgrades"], [])
        self.assertEqual(r["downgrade_notes"], [])

    def test_the_no_corroboration_note_says_what_to_add(self):
        r = run_verdict("mlb", self.mlb_game(line=6.5, h2h=None, form=None))
        note = " ".join(r["downgrade_notes"])
        self.assertIn("matchup model", note)
        self.assertIn("trend", note)

    def test_an_absurd_disagreement_is_a_symptom_not_an_edge(self):
        r = run_verdict("mlb", self.mlb_game(line=3.5))
        self.assertTrue(any("from the market" in f for f in r["flags"]))
        self.assertIn("inputs behind it are thin", " ".join(r["downgrades"]))

    def test_the_teams_own_park_is_ignored(self):
        plain = run_verdict("mlb", self.mlb_game())
        g = self.mlb_game()
        g["away"]["own_park_factor"] = 130
        g["home"]["own_park_factor"] = 70
        self.assertAlmostEqual(run_verdict("mlb", g)["projected_total"],
                               plain["projected_total"], places=6)

    def test_the_venue_park_still_moves_the_total(self):
        base = run_verdict("mlb", self.mlb_game())["model_total"]
        hot = run_verdict("mlb", self.mlb_game(park_factor=1.20))["model_total"]
        # Both sides are reported rounded to cents, so compare within that.
        self.assertAlmostEqual(hot, base * 1.20, delta=0.02)

    def test_trend_weights_never_outrun_the_model(self):
        r = run_verdict("mlb", self.mlb_game(trust=1.0))
        by = {s["name"]: s for s in r["signals"]}
        self.assertGreaterEqual(by["Matchup model"]["weight"], 0.5)
        self.assertAlmostEqual(sum(s["weight"] for s in r["signals"]), 1.0, places=6)

    def test_a_thin_head_to_head_earns_less_than_a_full_one(self):
        one = run_verdict("mlb", self.mlb_game(h2h={"avg_total": 11.0, "games": 1}))
        many = run_verdict("mlb", self.mlb_game(h2h={"avg_total": 11.0, "games": 8}))
        w = lambda r: [s for s in r["signals"] if s["name"] == "Head to head"][0]["weight"]
        self.assertLess(w(one), w(many))
        self.assertGreater(w(one), 0.0)

    def test_trust_zero_leaves_the_projection_on_the_market(self):
        r = run_verdict("mlb", self.mlb_game(line=6.5, trust=0.0))
        self.assertAlmostEqual(r["projected_total"], r["market_mean"], places=6)
        self.assertEqual(r["band"], "NO PLAY")

    def test_a_slate_sorts_strongest_first(self):
        games = [self.mlb_game(line=9.0), self.mlb_game(line=6.5),
                 self.mlb_game(line=13.5)]
        out = run_verdict_slate("mlb", games)
        ranks = [BANDS_ORDER[r["band"]] for r in out]
        self.assertEqual(ranks, sorted(ranks, reverse=True))

    def test_a_missing_line_is_an_error_not_a_guess(self):
        g = self.mlb_game()
        del g["line"]
        with self.assertRaises(ValueError):
            run_verdict("mlb", g)

    def test_wnba_works_the_same_way(self):
        r = run_verdict("wnba", self.wnba_game(line=160.0))
        self.assertEqual(r["side"], "OVER")
        self.assertIn(r["band"], BANDS)
        self.assertEqual(len(r["signals"]), 3)
