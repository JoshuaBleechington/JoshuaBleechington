"""Tests for the game-day model.

What is being locked in is refusal. Every previous version of this project
failed by finding an edge where there wasn't one, so most of these check that
a plausible-looking situation still comes back PASS.
"""

import unittest
from datetime import date

from totals.gameday import (
    DISPERSION,
    players_out,
    public_split,
    temperature,
    bullpens_recent,
    head_to_head,
    park_wind_scale,
    pitchers_last5,
    team_form,
    umpire_ou,
    umpire_rpg,
    wind,
    MIN_EDGE,
    STRONG_EDGE,
    Call,
    Evidence,
    decide,
    slate,
)

DAY = date(2026, 8, 24)
OTHER_DAY = date(2026, 8, 23)


def ev(name="Thing", worth=1.0, basis="documented", source="src",
       as_of=DAY, already_moved=0.0):
    return Evidence(name, worth, basis, source, as_of, already_moved)


class TestPricedInIsNotAnEdge(unittest.TestCase):
    """The Caitlin Clark lesson, which is the reason this module exists.

    Her being ruled out moved the Fever line from -11 to -6. Reading that news
    afterwards and betting it is arriving after the market, not beating it.
    """

    def test_news_the_line_has_fully_absorbed_is_worth_nothing(self):
        c = decide("MLB", "Cubs @ Reds", "total 9", "OVER", "UNDER",
                   [ev("Ace scratched", -1.2, already_moved=-1.3)], DAY)
        self.assertEqual(c.verdict, "PASS")
        self.assertAlmostEqual(c.net, 0.0)
        self.assertIn("already moved", " ".join(c.reasons))

    def test_only_the_unabsorbed_half_counts(self):
        c = decide("MLB", "Cubs @ Reds", "total 9", "OVER", "UNDER",
                   [ev("Wind in 18", -1.0, already_moved=-0.5)], DAY)
        self.assertAlmostEqual(c.net, -0.5)
        self.assertEqual(c.side, "UNDER")
        self.assertEqual(c.verdict, "LEAN")

    def test_a_line_that_moved_further_than_the_factor_is_not_a_fade(self):
        """The market disagreeing with my estimate is not a signal to bet against it.

        Letting `unpriced` flip sign here would have the model fading a real
        move on the strength of a coefficient nobody has backtested, which is
        the overconfidence this whole rewrite exists to refuse.
        """
        e = ev("Star out", -3.0, already_moved=-6.0)
        self.assertAlmostEqual(e.unpriced, 0.0)
        e2 = ev("Wind out", 0.6, already_moved=1.5)
        self.assertAlmostEqual(e2.unpriced, 0.0)


class TestGates(unittest.TestCase):
    def test_nothing_found_is_a_pass_and_says_so(self):
        c = decide("MLB", "Mets @ Phillies", "total 8.5", "OVER", "UNDER", [], DAY)
        self.assertEqual(c.verdict, "PASS")
        self.assertFalse(c.gates["fresh"])
        self.assertIn("best estimate", " ".join(c.reasons))

    def test_yesterdays_evidence_is_dropped(self):
        c = decide("MLB", "A @ B", "total 8.5", "OVER", "UNDER",
                   [ev("Stale bullpen note", 1.2, as_of=OTHER_DAY)], DAY)
        self.assertEqual(c.verdict, "PASS")
        self.assertEqual(c.evidence, [])
        self.assertIn("not game-day", " ".join(c.reasons))

    def test_provisional_alone_cannot_carry_a_bet(self):
        c = decide("MLB", "A @ B", "total 8.5", "OVER", "UNDER",
                   [ev("Bullpen down 3", 1.5, basis="provisional")], DAY)
        self.assertEqual(c.verdict, "PASS")
        self.assertFalse(c.gates["grounded"])
        self.assertIn("hypothesis", " ".join(c.reasons))

    def test_a_documented_contradiction_stands_the_bet_down(self):
        c = decide("MLB", "Cubs @ Reds", "total 9", "OVER", "UNDER",
                   [ev("Umpire", 0.42), ev("Wind in", -1.40)], DAY)
        self.assertEqual(c.verdict, "PASS")
        self.assertFalse(c.gates["uncontradicted"])
        self.assertIn("no validated way to net", " ".join(c.reasons))

    def test_a_trivial_dissent_does_not_veto_a_real_read(self):
        """The fault that killed the old confidence model, rediscovered here.

        There, a head-to-head signal holding 1.25% of the weight could still
        cost a full band, and four logged picks were downgraded that way. Here
        a 0.15-run temperature term was standing down a game carried by a
        half-run umpire. A dissent has to be worth something to count.
        """
        c = decide("MLB", "A @ B", "total 8", "OVER", "UNDER",
                   [ev("Umpire", -0.70), ev("Temperature", 0.15)], DAY)
        self.assertTrue(c.gates["uncontradicted"])
        self.assertEqual(c.side, "UNDER")
        self.assertEqual(c.verdict, "LEAN")

    def test_the_dissent_floor_is_half_the_lean_bar(self):
        from totals.gameday import CONTRADICTION_FLOOR
        for sport in ("MLB", "WNBA"):
            self.assertAlmostEqual(CONTRADICTION_FLOOR[sport], MIN_EDGE[sport] / 2)
        # just under the floor: ignored. just over: vetoes.
        floor = CONTRADICTION_FLOOR["MLB"]
        quiet = decide("MLB", "A @ B", "total 8", "OVER", "UNDER",
                       [ev("Umpire", -0.80), ev("Temp", floor - 0.01)], DAY)
        loud = decide("MLB", "A @ B", "total 8", "OVER", "UNDER",
                      [ev("Umpire", -0.80), ev("Temp", floor + 0.01)], DAY)
        self.assertTrue(quiet.gates["uncontradicted"])
        self.assertFalse(loud.gates["uncontradicted"])

    def test_a_contradiction_the_market_already_ate_does_not_block(self):
        """An item the line has absorbed is history, not an argument about tonight."""
        c = decide("MLB", "A @ B", "total 9", "OVER", "UNDER",
                   [ev("Wind in", -1.0, already_moved=-1.0),
                    ev("Umpire", 1.0)], DAY)
        self.assertTrue(c.gates["uncontradicted"])
        self.assertAlmostEqual(c.net, 1.0)
        self.assertEqual(c.verdict, "BET")

    def test_a_small_edge_is_under_the_bar(self):
        c = decide("MLB", "A @ B", "total 8.5", "OVER", "UNDER",
                   [ev("Umpire", MIN_EDGE["MLB"] - 0.01)], DAY)
        self.assertEqual(c.verdict, "PASS")
        self.assertFalse(c.gates["unpriced"])

    def test_all_four_gates_have_to_pass(self):
        c = decide("MLB", "A @ B", "total 8.5", "OVER", "UNDER",
                   [ev("Umpire", 0.5)], DAY)
        self.assertTrue(all(c.gates.values()))
        self.assertNotEqual(c.verdict, "PASS")


class TestVerdictLadder(unittest.TestCase):
    def test_lean_and_bet_split_at_the_strong_threshold(self):
        lean = decide("MLB", "A @ B", "total 8.5", "OVER", "UNDER",
                      [ev("Umpire", STRONG_EDGE["MLB"] - 0.01)], DAY)
        bet = decide("MLB", "A @ B", "total 8.5", "OVER", "UNDER",
                     [ev("Umpire", STRONG_EDGE["MLB"])], DAY)
        self.assertEqual(lean.verdict, "LEAN")
        self.assertEqual(bet.verdict, "BET")

    def test_a_pass_names_no_side_and_claims_no_edge(self):
        c = decide("MLB", "A @ B", "total 8.5", "OVER", "UNDER", [], DAY)
        self.assertEqual(c.side, "—")
        self.assertAlmostEqual(c.win_pct, 0.5)

    def test_the_probability_stays_unflattering(self):
        """A full run of unpriced MLB edge is a quarter of a standard deviation.

        If this ever starts printing numbers in the 60s from realistic inputs,
        something has gone wrong with the dispersion.
        """
        c = decide("MLB", "A @ B", "total 8.5", "OVER", "UNDER",
                   [ev("Umpire", 1.0)], DAY)
        self.assertLess(c.win_pct, 0.60)
        self.assertGreater(c.win_pct, 0.55)
        modest = decide("MLB", "A @ B", "total 8.5", "OVER", "UNDER",
                        [ev("Umpire", 0.5)], DAY)
        self.assertLess(modest.win_pct, 0.55)

    def test_the_side_follows_the_sign(self):
        over = decide("MLB", "A @ B", "total 8.5", "OVER", "UNDER",
                      [ev("Wind out", 1.0)], DAY)
        under = decide("MLB", "A @ B", "total 8.5", "OVER", "UNDER",
                       [ev("Wind in", -1.0)], DAY)
        self.assertEqual(over.side, "OVER")
        self.assertEqual(under.side, "UNDER")


class TestSlate(unittest.TestCase):
    def test_passes_are_counted_not_listed(self):
        """Twelve PASSes printed in full is how a card of nothing looks like a card."""
        calls = [
            decide("MLB", f"G{i} @ H{i}", "total 8.5", "OVER", "UNDER", [], DAY)
            for i in range(12)
        ]
        calls.append(decide("MLB", "Live @ One", "total 8.5", "OVER", "UNDER",
                            [ev("Umpire", 1.0)], DAY))
        text = slate(calls)
        self.assertIn("Live @ One", text)
        self.assertIn("PASS (12)", text)
        self.assertEqual(text.count("Nothing found today"), 0)

    def test_an_empty_board_says_so_rather_than_printing_nothing(self):
        calls = [decide("MLB", "A @ B", "total 8.5", "OVER", "UNDER", [], DAY)]
        self.assertIn("clears the gates", slate(calls))

    def test_strongest_first(self):
        weak = decide("MLB", "Weak @ X", "total 8.5", "OVER", "UNDER",
                      [ev("Umpire", 0.5)], DAY)
        strong = decide("MLB", "Strong @ Y", "total 8.5", "OVER", "UNDER",
                        [ev("Umpire", 1.2)], DAY)
        text = slate([weak, strong])
        self.assertLess(text.index("Strong @ Y"), text.index("Weak @ X"))


class TestEvidenceHygiene(unittest.TestCase):
    def test_a_bad_basis_is_rejected_at_construction(self):
        with self.assertRaises(ValueError):
            Evidence("X", 1.0, "vibes", "somewhere", DAY)

    def test_every_item_has_to_carry_its_source(self):
        """Not enforced by the type, but the brief prints it, so a blank shows."""
        c = decide("MLB", "A @ B", "total 8.5", "OVER", "UNDER",
                   [ev("Umpire", 1.0, source="RotoWire assignments")], DAY)
        self.assertIn("RotoWire assignments", c.brief())

    def test_only_the_two_totals_markets_are_supported(self):
        """Adding a sport means adding its dispersion and thresholds on purpose,
        not by a string slipping through."""
        for sport in ("NFL", "NBA", "NHL"):
            with self.assertRaises(ValueError):
                decide(sport, "A @ B", "total 44", "OVER", "UNDER", [], DAY)
        for sport in ("MLB", "WNBA"):
            decide(sport, "A @ B", "total 180", "OVER", "UNDER", [], DAY)


if __name__ == "__main__":
    unittest.main()


class TestEvidenceBuilders(unittest.TestCase):
    """The under-hunting inputs. Mostly checking they refuse to read what they
    cannot see, since a builder that returns zero when it means "unchecked" is
    how a blank form starts producing verdicts."""

    def test_a_lopsided_ticket_money_split_leans_under(self):
        e = public_split(78, 44, "Action Network", DAY)
        self.assertLess(e.worth, 0)
        self.assertEqual(e.basis, "documented")
        self.assertIn("34-point gap", e.source)

    def test_the_reverse_split_leans_over(self):
        e = public_split(40, 72, "Action Network", DAY)
        self.assertGreater(e.worth, 0)

    def test_a_narrow_split_is_not_a_signal_at_all(self):
        self.assertIsNone(public_split(55, 51, "Action Network", DAY))

    def test_the_split_is_capped_because_the_size_is_not_documented(self):
        small = public_split(75, 45, "src", DAY)
        huge = public_split(95, 15, "src", DAY)
        self.assertAlmostEqual(small.worth, huge.worth)
        self.assertIn("size is not", small.source)

    def test_wind_in_is_the_biggest_single_under_driver(self):
        self.assertAlmostEqual(wind(23, "in", "RotoWire", DAY).worth, -1.5)
        self.assertAlmostEqual(wind(6, "in", "RotoWire", DAY).worth, 0.0)

    def test_a_cross_wind_reads_zero_rather_than_nothing(self):
        """Zero means checked; None means unchecked, and the gates tell them apart."""
        e = wind(25, "cross", "RotoWire", DAY)
        self.assertIsNotNone(e)
        self.assertAlmostEqual(e.worth, 0.0)
        self.assertIsNone(wind(25, "", "RotoWire", DAY))

    def test_a_pitcher_friendly_umpire_leans_under(self):
        e = umpire_ou(115, 185, "OddsShark", DAY)
        self.assertLess(e.worth, 0)
        self.assertGreater(e.worth, -1.0)

    def test_an_impossible_umpire_figure_is_ignored(self):
        self.assertIsNone(umpire_rpg(40.0, 200, "RotoWire", as_of=DAY))

    def test_a_cold_night_leans_under_but_barely(self):
        e = temperature(48, "RotoWire", DAY)
        self.assertLess(e.worth, 0)
        self.assertGreater(e.worth, -0.35)

    def test_a_real_under_card_stacks_up(self):
        c = decide("MLB", "Mariners @ Guardians", "total 7.5", "OVER", "UNDER", [
            wind(18, "in", "RotoWire", DAY),
            umpire_ou(120, 180, "OddsShark", DAY),
            public_split(76, 46, "Action Network", DAY),
            temperature(55, "RotoWire", DAY),
        ], DAY)
        self.assertEqual(c.side, "UNDER")
        self.assertEqual(c.verdict, "BET")
        self.assertLess(c.net, -0.9)
        self.assertTrue(all(c.gates.values()))


class TestParkFactor(unittest.TestCase):
    """The park scales the wind and is never a term of its own.

    Its own effect is published, season-long and identical every night, so it
    is inside the posted total already. Giving it an adjustment is the double
    count that put the fourteen-input model behind the naked line.
    """

    def test_a_missing_park_leaves_the_wind_exactly_as_it_was(self):
        plain = wind(18, "out", "fixture")
        parked = wind(18, "out", "fixture", park_factor=None)
        self.assertAlmostEqual(plain.worth, parked.worth)
        self.assertAlmostEqual(plain.worth, 1.0, places=6)

    def test_a_hitters_park_lifts_the_wind_and_a_pitchers_park_cuts_it(self):
        hot = wind(18, "out", "fixture", park_factor=113)
        cold = wind(18, "out", "fixture", park_factor=90)
        self.assertAlmostEqual(hot.worth, 1.13, places=6)
        self.assertAlmostEqual(cold.worth, 0.90, places=6)

    def test_the_park_cannot_flip_the_sign_of_a_wind_blowing_in(self):
        into = wind(18, "in", "fixture", park_factor=120)
        self.assertLess(into.worth, 0)
        self.assertAlmostEqual(into.worth, -1.2, places=6)

    def test_the_scaling_is_held_inside_twenty_percent(self):
        self.assertAlmostEqual(park_wind_scale(129), 1.20)
        self.assertAlmostEqual(park_wind_scale(71), 0.80)

    def test_an_implausible_figure_is_read_as_a_typo_and_ignored(self):
        """Same guard as the umpire's 40 R/Gm.

        A park factor entered as 1.13 instead of 113, or as 1130, must leave
        the wind alone rather than erase it or double it.
        """
        self.assertAlmostEqual(park_wind_scale(1.13), 1.0)
        self.assertAlmostEqual(park_wind_scale(1130), 1.0)

    def test_a_park_cannot_push_the_wind_past_its_own_cap(self):
        gale = wind(40, "out", "fixture", park_factor=120)
        self.assertAlmostEqual(gale.worth, 1.5, places=6)

    def test_no_wind_reading_means_the_park_does_nothing_at_all(self):
        """There is no path by which a park factor alone produces evidence."""
        self.assertIsNone(wind(18, "", "fixture", park_factor=120))
        cross = wind(25, "cross", "fixture", park_factor=120)
        self.assertAlmostEqual(cross.worth, 0.0)


class TestWnbaAbsences(unittest.TestCase):
    """The WNBA is back as a totals market only -- the spread model went 4-5."""

    def test_a_thin_bench_is_worth_more_than_in_any_other_league(self):
        e = players_out("Toronto", 3, "beat writer", leading_scorer_out=True,
                        as_of=DAY)
        self.assertLess(e.worth, 0)
        self.assertAlmostEqual(e.worth, -(3.5 + 2 * 2.0))

    def test_the_leading_scorer_counts_once_not_twice(self):
        """He is one of the starters_out, not an extra body on top of them."""
        with_star = players_out("T", 1, "src", leading_scorer_out=True, as_of=DAY)
        without = players_out("T", 1, "src", as_of=DAY)
        self.assertAlmostEqual(with_star.worth, -3.5)
        self.assertAlmostEqual(without.worth, -2.0)

    def test_a_long_injury_list_is_capped(self):
        """A five-deep list must not read as a fifteen-point edge.

        The fifth player out is replaced by someone who would not otherwise
        take the floor, and the returns stop compounding well before that.
        """
        e = players_out("Toronto", 5, "src", leading_scorer_out=True, as_of=DAY)
        self.assertAlmostEqual(e.worth, -8.0)
        deeper = players_out("Toronto", 9, "src", leading_scorer_out=True, as_of=DAY)
        self.assertAlmostEqual(deeper.worth, -8.0)

    def test_the_cap_still_leaves_room_to_tell_thin_from_gutted(self):
        """The first cap was 6.0 and bound at three absences, which made three,
        five and nine score the same. Granularity below the cap is the point."""
        worths = [players_out("T", n, "src", leading_scorer_out=True, as_of=DAY).worth
                  for n in (1, 2, 3, 4, 5)]
        self.assertEqual(len(set(worths[:4])), 4)
        self.assertAlmostEqual(worths[3], worths[4])

    def test_nobody_out_is_no_reading_rather_than_a_zero(self):
        self.assertIsNone(players_out("Toronto", 0, "src", as_of=DAY))

    def test_wnba_thresholds_demand_the_same_evidence_in_its_own_units(self):
        """Same fraction of dispersion as MLB, so neither sport is the soft one."""
        self.assertAlmostEqual(MIN_EDGE["WNBA"] / DISPERSION["WNBA"],
                               MIN_EDGE["MLB"] / DISPERSION["MLB"], places=2)
        self.assertAlmostEqual(STRONG_EDGE["WNBA"] / DISPERSION["WNBA"],
                               STRONG_EDGE["MLB"] / DISPERSION["MLB"], places=2)

    def test_absences_alone_can_carry_a_wnba_under(self):
        c = decide("WNBA", "Aces @ Tempo", "total 180", "OVER", "UNDER",
                   [players_out("Toronto", 5, "beat writer",
                                leading_scorer_out=True, as_of=DAY)], DAY)
        self.assertEqual(c.side, "UNDER")
        self.assertEqual(c.verdict, "BET")

    def test_but_not_once_the_line_has_already_moved_on_them(self):
        """The whole point. Five out is real; five out that the number already
        knows about is not a bet."""
        e = players_out("Toronto", 5, "beat writer", leading_scorer_out=True,
                        as_of=DAY)
        e.already_moved = -7.5
        c = decide("WNBA", "Aces @ Tempo", "total 180", "OVER", "UNDER", [e], DAY)
        self.assertEqual(c.verdict, "PASS")
        self.assertIn("already moved", " ".join(c.reasons))


class TestUmpire(unittest.TestCase):
    """The biggest single term available, and the easiest to overrate.

    An umpire's raw over/under split is mostly sampling noise: they work the
    plate about every fourth game, so a season is ~30 games against a prior
    worth 335. The job of these tests is to keep that honest.
    """

    def test_the_top_of_a_leaderboard_is_worth_almost_nothing(self):
        """Sorting umpires by over-rate puts the smallest samples on top.

        CB Bucknor at 3-0 and 100% led the table the owner sent. After
        shrinking he is worth five hundredths of a run.
        """
        e = umpire_ou(3, 0, "leaderboard", DAY, "CB Bucknor")
        self.assertLess(abs(e.worth), 0.10)
        self.assertIn("100%", e.source)

    def test_a_smaller_split_on_a_career_beats_a_huge_one_on_a_season(self):
        season = umpire_ou(9, 1, "leaderboard", DAY)      # 90% over, 10 games
        career = umpire_ou(185, 115, "career", DAY)       # 62% over, 300 games
        self.assertGreater(career.worth, season.worth * 3)

    def test_it_is_symmetric(self):
        over = umpire_ou(185, 115, "career", DAY)
        under = umpire_ou(115, 185, "career", DAY)
        self.assertAlmostEqual(over.worth, -under.worth, places=6)

    def test_an_even_record_is_worth_nothing(self):
        self.assertAlmostEqual(umpire_ou(150, 150, "career", DAY).worth, 0.0, places=6)

    def test_no_games_is_no_reading(self):
        self.assertIsNone(umpire_ou(0, 0, "career", DAY))

    def test_the_term_is_capped(self):
        self.assertLessEqual(abs(umpire_ou(3000, 0, "absurd", DAY).worth), 1.0)

    def test_the_rgm_fallback_says_it_is_the_weaker_input(self):
        """R/Gm is confounded by which parks he drew; the over/under record is
        park-adjusted by the lines it was measured against."""
        e = umpire_rpg(9.2, 250, "RotoWire", as_of=DAY)
        self.assertIn("weaker", e.source)
        self.assertIn("confounded", e.source)
        self.assertEqual(e.name, "Umpire (R/Gm fallback)")

    def test_the_shrinkage_is_derived_not_picked(self):
        """k = sd^2 / tau^2. The first version used 120, which quietly assumed a
        true between-umpire spread of 0.40 runs -- the optimistic end."""
        from totals.gameday import (DISPERSION, UMPIRE_SHRINK_GAMES,
                                    UMPIRE_TAU_RUNS)
        self.assertAlmostEqual(UMPIRE_SHRINK_GAMES,
                               DISPERSION["MLB"] ** 2 / UMPIRE_TAU_RUNS ** 2,
                               delta=1.0)


class TestTrialTier(unittest.TestCase):
    """Three inputs the owner asked to try, two of which measured null.

    Head-to-head came back t = -0.40 and team form t = -0.07 against the
    residual on 116 logged games. They are built because they were asked for,
    sized small because a large guess is how the first two models died, and
    labelled every time they appear. Pitcher last-five is the exception: the
    log only ever held season ERA, so that window is genuinely untested.
    """

    def test_all_three_are_provisional_and_say_why(self):
        for e in (team_form(9.4, 8.2, 5, 8.0, "Covers", DAY),
                  head_to_head(10.2, 6, 8.0, "Covers", DAY),
                  pitchers_last5(5.8, 27, 3.1, 29, "Covers", as_of=DAY),
                  bullpens_recent(5.1, 60, 3.4, 55, "Covers", as_of=DAY)):
            self.assertEqual(e.basis, "provisional")
        self.assertIn("t = -0.07", team_form(9.4, 8.2, 5, 8.0, "Covers", DAY).source)
        self.assertIn("t = -0.40", head_to_head(10.2, 6, 8.0, "Covers", DAY).source)
        self.assertIn("Untested here",
                      pitchers_last5(5.8, 27, 3.1, 29, "Covers", as_of=DAY).source)

    def test_bullpen_innings_are_optional_and_the_stand_in_says_so(self):
        """Innings came off the form on request; the regression cannot come off.

        An unshrunk ERA gap is the false precision this model exists to refuse,
        so a missing figure falls back to about a month of bullpen work. What
        matters is that the number is never reported as though it were entered.
        """
        from totals.gameday import BULLPEN_ASSUMED_IP
        e = bullpens_recent(6.20, None, 3.10, None, "Covers", as_of=DAY)
        self.assertIn("assumed", e.source)
        self.assertIn(f"{BULLPEN_ASSUMED_IP:.0f} IP", e.source)
        stated = bullpens_recent(6.20, BULLPEN_ASSUMED_IP, 3.10, BULLPEN_ASSUMED_IP,
                                 "Covers", as_of=DAY)
        self.assertAlmostEqual(e.worth, stated.worth)
        self.assertNotIn("assumed", stated.source)

    def test_the_assumed_innings_under_weight_a_season_figure(self):
        """The direction the guess is allowed to be wrong in.

        A season bullpen ERA rests on ~450 innings and would earn 0.84 of its
        gap. Assuming a month earns 0.55, so a season figure entered here is
        under-counted rather than over-counted -- it errs toward not betting.
        """
        assumed = bullpens_recent(6.20, None, 4.30, None, "Covers", as_of=DAY)
        season = bullpens_recent(6.20, 450, 4.30, 450, "Covers", as_of=DAY)
        self.assertLess(assumed.worth, season.worth)
        self.assertGreater(assumed.worth, 0)

    def test_a_bullpen_with_no_era_at_all_still_contributes_nothing(self):
        self.assertIsNone(bullpens_recent(None, None, None, None, "Covers", as_of=DAY))
        one = bullpens_recent(6.20, None, None, None, "Covers", as_of=DAY)
        self.assertIn("away", one.source)
        self.assertNotIn("home", one.source)

    def test_two_meetings_is_not_a_head_to_head(self):
        """Letting a two-game h2h vote is the exact fault that cost four picks a
        band in the old model."""
        self.assertIsNone(head_to_head(12.0, 2, 8.0, "Covers", DAY))
        self.assertIsNotNone(head_to_head(12.0, 3, 8.0, "Covers", DAY))

    def test_five_starts_keeps_under_a_fifth_of_its_gap(self):
        """27 innings against a 120-inning half-weight point."""
        e = pitchers_last5(8.30, 27, 4.30, 27, "Covers", as_of=DAY)
        raw = (8.30 - 4.30) * (5 / 9)          # what it would be unregressed
        self.assertLess(abs(e.worth), raw * 0.25)

    def test_the_trend_terms_are_capped(self):
        wild = team_form(20.0, 20.0, 5, 6.0, "Covers", DAY)
        self.assertAlmostEqual(wild.worth, 0.60)
        wild_h2h = head_to_head(30.0, 10, 6.0, "Covers", DAY)
        self.assertAlmostEqual(wild_h2h.worth, 0.40)

    def test_strict_mode_will_not_bet_on_provisional_evidence_alone(self):
        ev = [team_form(9.4, 9.8, 5, 8.0, "Covers", DAY),
              head_to_head(10.4, 6, 8.0, "Covers", DAY),
              pitchers_last5(5.9, 26, 5.4, 28, "Covers", as_of=DAY)]
        c = decide("MLB", "A @ B", "total 8", "OVER", "UNDER", ev, DAY)
        self.assertEqual(c.verdict, "PASS")
        self.assertFalse(c.gates["grounded"])

    def test_trial_mode_lets_it_lean_but_never_bet(self):
        """A top-band call on coefficients nobody has measured is the false
        confidence this whole model exists to refuse."""
        ev = [team_form(14.0, 14.0, 5, 8.0, "Covers", DAY),
              head_to_head(16.0, 8, 8.0, "Covers", DAY),
              pitchers_last5(9.0, 30, 9.0, 30, "Covers", as_of=DAY)]
        c = decide("MLB", "A @ B", "total 8", "OVER", "UNDER", ev, DAY, trial=True)
        self.assertGreater(abs(c.net), STRONG_EDGE["MLB"])   # would be a BET
        self.assertEqual(c.verdict, "LEAN")                  # but is not
        self.assertTrue(c.capped_at_lean)
        self.assertIn("tops out at LEAN", c.brief())

    def test_trial_mode_says_to_log_both_reads(self):
        c = decide("MLB", "A @ B", "total 8", "OVER", "UNDER",
                   [team_form(11.0, 11.0, 5, 8.0, "Covers", DAY)], DAY, trial=True)
        self.assertIn("compare after", " ".join(c.reasons))

    def test_a_documented_item_still_outranks_the_trial_tier(self):
        """With real evidence present the call is grounded normally and can bet."""
        ev = [ev_wind := wind(20, "out", "RotoWire", DAY),
              team_form(9.0, 9.0, 5, 8.0, "Covers", DAY)]
        c = decide("MLB", "A @ B", "total 8", "OVER", "UNDER", ev, DAY)
        self.assertTrue(c.gates["grounded"])
        self.assertEqual(c.verdict, "BET")
        self.assertFalse(c.capped_at_lean)

    def test_the_bullpen_is_form_not_availability_and_says_so(self):
        e = bullpens_recent(5.60, 70, 3.20, 65, "Covers", as_of=DAY)
        self.assertIn("not availability", e.source)
        self.assertLess(e.worth, BULLPEN_CAP_CHECK := 0.60)
