"""Tests for the game-day model.

What is being locked in is refusal. Every previous version of this project
failed by finding an edge where there wasn't one, so most of these check that
a plausible-looking situation still comes back PASS.
"""

import unittest
from datetime import date

from totals.gameday import (
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
        c = decide("WNBA", "Fever @ Sky", "home +6", "HOME", "AWAY",
                   [ev("Clark out", -4.8, already_moved=-5.0)], DAY)
        self.assertEqual(c.verdict, "PASS")
        self.assertAlmostEqual(c.net, 0.0)
        self.assertIn("already moved", " ".join(c.reasons))

    def test_only_the_unabsorbed_half_counts(self):
        c = decide("WNBA", "Lynx @ Storm", "home +3.5", "HOME", "AWAY",
                   [ev("Collier out", -3.4, already_moved=-1.0)], DAY)
        self.assertAlmostEqual(c.net, -2.4)
        self.assertEqual(c.side, "AWAY")
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

    def test_an_unknown_sport_is_an_error_not_a_default(self):
        with self.assertRaises(ValueError):
            decide("NFL", "A @ B", "total 44", "OVER", "UNDER", [], DAY)


if __name__ == "__main__":
    unittest.main()
