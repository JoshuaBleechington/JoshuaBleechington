"""Tests for the game-day model.

What is being locked in is refusal. Every previous version of this project
failed by finding an edge where there wasn't one, so most of these check that
a plausible-looking situation still comes back PASS.
"""

import unittest
from datetime import date

from totals.gameday import (
    public_split,
    temperature,
    umpire,
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
        self.assertIn("no honest way to net it out", " ".join(c.reasons))

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

    def test_only_mlb_is_supported(self):
        """WNBA was retired at the owner's call; nothing here covers it.

        Adding a sport back means adding its dispersion, its thresholds and its
        own checklist on purpose, not by a string slipping through.
        """
        for sport in ("WNBA", "NFL", "NBA"):
            with self.assertRaises(ValueError):
                decide(sport, "A @ B", "total 44", "OVER", "UNDER", [], DAY)


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
        e = umpire(7.9, 260, "RotoWire", as_of=DAY)
        self.assertLess(e.worth, 0)
        self.assertGreater(e.worth, -1.0)

    def test_an_impossible_umpire_figure_is_ignored(self):
        self.assertIsNone(umpire(40.0, 200, "RotoWire", as_of=DAY))

    def test_a_cold_night_leans_under_but_barely(self):
        e = temperature(48, "RotoWire", DAY)
        self.assertLess(e.worth, 0)
        self.assertGreater(e.worth, -0.35)

    def test_a_real_under_card_stacks_up(self):
        c = decide("MLB", "Mariners @ Guardians", "total 7.5", "OVER", "UNDER", [
            wind(18, "in", "RotoWire", DAY),
            umpire(8.0, 300, "RotoWire", as_of=DAY),
            public_split(76, 46, "Action Network", DAY),
            temperature(55, "RotoWire", DAY),
        ], DAY)
        self.assertEqual(c.side, "UNDER")
        self.assertEqual(c.verdict, "BET")
        self.assertLess(c.net, -0.9)
        self.assertTrue(all(c.gates.values()))
