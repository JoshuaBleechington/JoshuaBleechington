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
