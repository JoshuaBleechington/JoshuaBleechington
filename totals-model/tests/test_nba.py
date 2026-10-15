"""The basketball book, totals/nba.py: the constants as measured, the fade,
the stage deltas, the labels, the half, the sides, the grading."""
import unittest

from totals.nba import (
    DEADLINE_DELTA, HALF_SHARE, LAST_TWO_WEEKS_DELTA, LEAGUE_RATING, MARGIN_SD, RATINGS_FADE, RATINGS_FADE_UNTIL,
    RATINGS_MIN_GAMES, RATINGS_SHRINK_K, TOTAL_SD, forecast_matchup_nba, forecast_nba, grade, margin_from_spread,
    nba_fair_total, nba_split, ratings_projection, stage_of,
)

LG = dict(away_ort=112.7, home_ort=112.7, away_drt=112.7, home_drt=112.7, away_pace=101.5, home_pace=101.5, away_games=20, home_games=20)


class TestTheDistribution(unittest.TestCase):
    def test_a_normal_at_the_measured_spread(self):
        o, pu, u = nba_split(228.5, 228.5)
        self.assertAlmostEqual(o, 0.5, places=9)
        self.assertEqual(pu, 0.0)
        o2, pu2, u2 = nba_split(228.0, 228.0)
        self.assertGreater(pu2, 0.02)              # a whole number pushes
        self.assertAlmostEqual(o2, u2, places=9)
        o3, _, _ = nba_split(228.5, 228.5 + TOTAL_SD)
        self.assertAlmostEqual(o3, 0.8413, places=3)

    def test_the_anchor_is_the_line_at_even_prices_and_moves_with_them(self):
        mu, _ = nba_fair_total("NBA", 228.5, -110, -110)
        self.assertAlmostEqual(mu, 228.5, places=6)
        mu2, why = nba_fair_total("NBA", 228.5, -125, 105)
        self.assertGreater(mu2, 229.0)
        self.assertLess(mu2, 232.0)
        self.assertIn("de-vigs to", why)
        mu3, _ = nba_fair_total("NBA", 228.5, None, None)
        self.assertAlmostEqual(mu3, 228.5, places=6)

    def test_the_league_rating_is_the_points_over_the_pace(self):
        self.assertAlmostEqual(LEAGUE_RATING, 112.7, places=1)


class TestTheTotal(unittest.TestCase):
    def test_nothing_but_the_number_is_the_market(self):
        f = forecast_nba("A @ B", 228.5, -110, -110)
        self.assertAlmostEqual(f.projected, 228.5, places=6)
        self.assertEqual(f.band, "NO BET")
        self.assertEqual([e.name for e in f.estimates], ["Market"])

    def test_four_league_ratings_on_the_leagues_number_move_nothing(self):
        # the projection is the backtest's: an absolute against the close, so the zero sits where
        # the ratings' own total meets the line, the league's 228.8
        lg = 228.8 / 2.0 / 101.5 * 100.0
        f = forecast_nba("A @ B", 228.8, -110, -110, away_ort=lg, home_ort=lg, away_drt=lg, home_drt=lg, away_pace=101.5, home_pace=101.5,
                         away_games=20, home_games=20, league_rating=lg, league_pace=101.5)
        self.assertAlmostEqual(f.projected, 228.8, places=6)
        g = forecast_nba("A @ B", 228.5, -110, -110, **LG)       # on 228.5 the league ratings lean +0.3 and the fade is three hundredths
        self.assertAlmostEqual(g.projected, 228.5 - RATINGS_FADE * -1 * (2 * 101.5 / 100.0 * LEAGUE_RATING - 228.5) * 0.5, places=6)

    def test_the_ratings_are_faded_shrunk_and_tagged(self):
        rp = ratings_projection(118.0, 118.0, 112.7, 112.7, 101.5, 101.5)
        self.assertAlmostEqual(rp[0], 101.5 / 100.0 * (118.0 + 112.7 - 112.7) * 2, places=6)   # 239.5
        f = forecast_nba("A @ B", 228.5, -110, -110, away_ort=118.0, home_ort=118.0, away_drt=112.7, home_drt=112.7,
                         away_pace=101.5, home_pace=101.5, away_games=20, home_games=30)
        d = [x for x in f.deltas if x.name == "Ratings, faded"]
        self.assertEqual(len(d), 1)
        lean = rp[0] - 228.5
        self.assertAlmostEqual(d[0].runs, RATINGS_FADE * lean * 20 / (20 + RATINGS_SHRINK_K), places=6)
        self.assertLess(f.projected, 228.5)        # two high-rated offences pull the line DOWN
        self.assertFalse(d[0].mechanism)
        self.assertEqual(f.band, "NO BET")         # tagged: cannot buy a band alone

    def test_the_fade_needs_ten_games_and_stops_at_fifty(self):
        kw = dict(away_ort=118.0, home_ort=118.0, away_drt=112.7, home_drt=112.7, away_pace=101.5, home_pace=101.5)
        f = forecast_nba("A @ B", 228.5, -110, -110, away_games=RATINGS_MIN_GAMES - 1, home_games=40, **kw)
        self.assertFalse(f.deltas)
        self.assertTrue(any("SHOWN, NOT SCORED" in n and "needs" in n for n in f.notes))
        g = forecast_nba("A @ B", 228.5, -110, -110, away_games=RATINGS_FADE_UNTIL, home_games=60, **kw)
        self.assertFalse(g.deltas)
        self.assertTrue(any("past 50 games" in n for n in g.notes))
        h = forecast_nba("A @ B", 228.5, -110, -110, **kw)       # no games typed: shown
        self.assertFalse(h.deltas)

    def test_a_partial_set_of_ratings_is_dropped(self):
        f = forecast_nba("A @ B", 228.5, -110, -110, away_ort=118.0, home_drt=110.0, away_games=20, home_games=20)
        self.assertFalse(f.deltas)
        self.assertTrue(any("travel together" in n for n in f.notes))

    def test_the_stage_deltas(self):
        self.assertIsNone(stage_of("2026-12-01"))
        self.assertIsNone(stage_of("2027-02-04"))                 # the deadline day itself: before
        self.assertEqual(stage_of("2027-02-05")[0], DEADLINE_DELTA)
        self.assertEqual(stage_of("2027-03-29")[0], LAST_TWO_WEEKS_DELTA)
        self.assertEqual(stage_of("2027-04-11")[0], LAST_TWO_WEEKS_DELTA)
        self.assertIsNone(stage_of("2027-04-20"))                 # the playoffs: no delta
        self.assertIsNone(stage_of(None))
        self.assertIsNone(stage_of("garbage"))
        f = forecast_nba("A @ B", 228.5, -110, -110, game_date="2027-03-01")
        self.assertAlmostEqual(f.projected, 228.5 + DEADLINE_DELTA, places=6)
        self.assertFalse(f.deltas[0].mechanism)
        self.assertEqual(f.band, "NO BET")
        g = forecast_nba("A @ B", 228.5, -110, -110, game_date="2027-04-05")
        self.assertAlmostEqual(g.projected, 228.5 + LAST_TWO_WEEKS_DELTA, places=6)

    def test_the_labels(self):
        f = forecast_nba("Nuggets @ Jazz", 238.5, -110, -110, away="Nuggets", home="Jazz", away_rest_days=0, home_rest_days=2,
                         away_out_minutes=48.0, home_out_minutes=0.0)
        self.assertAlmostEqual(f.projected, 238.5, places=6)     # none of it moves the number
        self.assertTrue(any("Nuggets" in n and "WATCHED" in n for n in f.notes))
        self.assertTrue(any("Jazz" in n and "WATCHED" in n for n in f.notes))
        self.assertTrue(any("Back to back for the away side" in n for n in f.notes))
        self.assertTrue(any("Regulars out" in n and "away 48" in n for n in f.notes))

    def test_an_absurd_total_is_refused(self):
        with self.assertRaises(ValueError):
            forecast_nba("A @ B", 28.5, -110, -110)


class TestTheMatchup(unittest.TestCase):
    def test_the_half_anchors_on_its_market_and_takes_the_games_lean_at_the_share(self):
        m = forecast_matchup_nba("Knicks", "Celtics", total_line=228.5, over_price=-110, under_price=-110,
                                 h1_line=114.5, h1_over_price=-110, h1_under_price=-110, game_date="2027-04-05")
        h1 = next(x for x in m.markets if x.key == "h1")
        proj = 114.5 + LAST_TWO_WEEKS_DELTA * HALF_SHARE
        self.assertIn(f"Projected {proj:.1f} against 114.5", " ".join(h1.notes))
        self.assertEqual(h1.side, "OVER")
        self.assertTrue(h1.anchored)
        self.assertIn("1H OVER 114.5", h1.pick)

    def test_the_sides_are_the_books_number(self):
        m = forecast_matchup_nba("Knicks", "Celtics", total_line=228.5, over_price=-110, under_price=-110,
                                 spread=-6.5, spread_home_price=-110, spread_away_price=-110, home_ml=-250, away_ml=205)
        ml = next(x for x in m.markets if x.key == "ml")
        sp = next(x for x in m.markets if x.key == "spread")
        self.assertEqual(ml.side, "HOME")
        self.assertAlmostEqual(ml.p, 0.5 + 0.5 * __import__("math").erf(6.5 / MARGIN_SD / 2 ** 0.5), places=6)
        self.assertAlmostEqual(sp.p, 0.5, places=6)                 # at the spread's own number, a coin
        self.assertAlmostEqual(m.lam_home - m.lam_away, 6.5, places=6)
        self.assertAlmostEqual(m.lam_home + m.lam_away, 228.5, places=6)
        self.assertTrue(any("never the pick" in n for n in m.notes))

    def test_a_priced_spread_moves_fair_off_the_number(self):
        mg, why = margin_from_spread(-6.5, -125, 105)
        self.assertGreater(mg, 6.5)
        self.assertIn("de-vigs", why)
        mg2, _ = margin_from_spread(-6.5, None, None)
        self.assertEqual(mg2, 6.5)

    def test_a_moneyline_alone_gives_the_margin(self):
        m = forecast_matchup_nba("Knicks", "Celtics", total_line=228.5, home_ml=-250, away_ml=205)
        self.assertGreater(m.lam_home, m.lam_away)
        self.assertEqual([x.key for x in m.markets], ["total", "ml"])

    def test_no_sides_without_a_number(self):
        m = forecast_matchup_nba("Knicks", "Celtics", total_line=228.5)
        self.assertEqual([x.key for x in m.markets], ["total"])
        self.assertIsNone(m.lam_home)

    def test_the_big_home_favourite_is_watched(self):
        m = forecast_matchup_nba("Wizards", "Celtics", total_line=228.5, spread=-14.5, spread_home_price=-110, spread_away_price=-110)
        self.assertTrue(any("ten or more" in n for n in m.notes))

    def test_a_bad_half_line_is_refused(self):
        with self.assertRaises(ValueError):
            forecast_matchup_nba("A", "B", total_line=228.5, h1_line=228.5)

    def test_the_early_season_side_watch(self):
        # the ratings make the Bucks 16 better over 100 possessions; the spread says 3.5
        kw = dict(total_line=229.5, over_price=-110, under_price=-110, spread=-3.5, spread_home_price=-110, spread_away_price=-110,
                  away_ort=110.0, away_drt=118.0, home_ort=118.0, home_drt=110.0, away_pace=100.0, home_pace=100.0)
        early = forecast_matchup_nba("Hornets", "Bucks", away_games=15, home_games=16, **kw)
        note = [n for n in early.notes if n.startswith("Early-season side watch")]
        self.assertEqual(len(note), 1)
        self.assertIn("toward the Bucks", note[0])
        self.assertIn("WATCHED, NOT SCORED", note[0])
        sp = next(m for m in early.markets if m.key == "spread")
        self.assertAlmostEqual(sp.p, 0.5, places=2)   # a watch moves nothing
        later = forecast_matchup_nba("Hornets", "Bucks", away_games=35, home_games=36, **kw)
        self.assertFalse(any(n.startswith("Early-season side watch") for n in later.notes))
        nine = forecast_matchup_nba("Hornets", "Bucks", away_games=9, home_games=16, **kw)
        self.assertFalse(any(n.startswith("Early-season side watch") for n in nine.notes))
        close = forecast_matchup_nba("Hornets", "Bucks", away_games=15, home_games=16, **dict(kw, away_ort=114.0, home_ort=114.0, away_drt=114.0, home_drt=114.0))
        self.assertFalse(any(n.startswith("Early-season side watch") for n in close.notes))   # even ratings: 3.5 points of lean, under four


class TestGrading(unittest.TestCase):
    def setUp(self):
        m = forecast_matchup_nba("Knicks", "Celtics", total_line=228.5, over_price=-110, under_price=-110,
                                 spread=-6.5, spread_home_price=-110, spread_away_price=-110, home_ml=-250, away_ml=205,
                                 h1_line=114.5, h1_over_price=-110, h1_under_price=-110)
        self.by = {x.key: x for x in m.markets}

    def test_the_total_and_the_half(self):
        t = self.by["total"]
        res = grade(t, home_points=120, away_points=110)
        self.assertEqual(res, "win" if t.side == "OVER" else "loss")
        self.assertEqual(grade(self.by["h1"], home_points=120, away_points=110, h1_home=60, h1_away=60), "win" if self.by["h1"].side == "OVER" else "loss")   # 120 at the half clears 114.5
        self.assertEqual(grade(self.by["h1"], home_points=120, away_points=110, h1_home=60, h1_away=50), "loss" if self.by["h1"].side == "OVER" else "win")   # 110 does not
        self.assertEqual(grade(self.by["h1"], home_points=120, away_points=110, h1_home=130, h1_away=50), "invalid")
        self.assertIsNone(grade(self.by["h1"], home_points=120, away_points=110))

    def test_the_spread_and_the_moneyline(self):
        sp, ml = self.by["spread"], self.by["ml"]
        self.assertEqual(grade(ml, home_points=120, away_points=110), "win" if ml.side == "HOME" else "loss")
        self.assertEqual(grade(sp, home_points=120, away_points=110), "win" if sp.side == "HOME" else "loss")   # by ten covers 6.5
        self.assertEqual(grade(sp, home_points=116, away_points=110), "loss" if sp.side == "HOME" else "win")   # by six does not
        self.assertIsNone(grade(sp, home_points=None, away_points=None))


if __name__ == "__main__":
    unittest.main()
