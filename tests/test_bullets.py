"""Bullets a resume plainly has must be read as bullets.

Every failure here has the same shape: a person's accomplishments are on the
page, an ATS-style reader misses the list markers, and the resume is judged as
though it had no accomplishments at all. The marker is presentation; the
content is what matters, so the parser has to find the content whatever the
marker turns out to be -- or whether one survived at all.
"""

import pytest

from resume_ats.extract import from_string
from resume_ats.jd import parse as parse_jd
from resume_ats.resume import parse as parse_resume
from resume_ats.score import score
from resume_ats.text import is_bullet, repair_layout

RESUME = """Jane Doe
Dallas, TX | (469) 555-0100 | jane@example.com

SUMMARY
Home health and hospice operations executive.

PROFESSIONAL EXPERIENCE
Regional Vice President of Operations | Compassus
March 2021 - Present
{b}Led 14 hospice agencies across three states, growing average daily census 28%.
{b}Owned a $180M multi-site P&L and improved contribution margin 6 points.
{b}Drove survey readiness under CMS Conditions of Participation with zero deficiencies.

EDUCATION
MBA, Southern Methodist University
"""

JD = """Area Vice President of Operations

Responsibilities
- Provide leadership to Executive Directors across multiple markets.
- Drive census growth, clinical quality and regulatory compliance.

Requirements
- 10+ years of healthcare operations leadership.
- Bachelor's degree required.
"""

# Word's default bullet (Symbol font) and its Wingdings siblings all land in
# the private use area; the dingbats are what the bullet gallery offers.
MARKERS = [
    "-", "*", "•", "▪", "◦", "–",
    "", "", "", "", "",
    "»", "→", "▶", "➤", "➢",
    "✓", "✔", "❖", "♦", "◾", "■", "★",
]


@pytest.mark.parametrize("marker", MARKERS)
def test_every_marker_a_word_processor_offers_reads_as_a_bullet(marker):
    line = marker + " Led multi-site hospice operations."
    repaired, _ = repair_layout(line)
    assert is_bullet(repaired.splitlines()[0])


@pytest.mark.parametrize("marker", ["-", "", "➢", "✓", ""])
def test_the_writing_score_does_not_depend_on_the_marker(marker):
    prefix = (marker + " ") if marker else ""
    report = score(from_string(RESUME.format(b=prefix)), parse_jd(JD))
    writing = next(c for c in report.components if c.name == "writing")
    assert "no bullet points detected" not in writing.detail
    assert writing.score == pytest.approx(100.0)


def test_a_private_use_bullet_is_repaired_and_reported():
    """Word's own bullet arrives as an unprintable box, not a list marker."""
    repaired, notes = repair_layout(" Led operations.\n Owned the P&L.")
    assert all(line.startswith("- ") for line in repaired.splitlines())
    assert any("private-use" in n for n in notes)


def test_a_bare_letter_o_is_a_bullet_only_when_used_as_one():
    """Word's second-level bullet exports as "o"; so does the English word."""
    many, notes = repair_layout("o Led operations.\no Owned the P&L.\no Coached directors.")
    assert all(line.startswith("- ") for line in many.splitlines())
    assert notes

    once, notes = repair_layout("o Only one line looks like this.\nAnother line entirely.")
    assert not once.startswith("- ")
    assert not notes


def test_unmarked_accomplishment_lines_are_still_read_as_bullets():
    """Pasting from Word drops list markers -- the content is still there."""
    resume = parse_resume(RESUME.format(b=""))
    assert [len(r.bullets) for r in resume.roles] == [3]
    assert resume.roles[0].unmarked_bullets is True
    assert resume.roles[0].trailing == []


def test_promotion_leaves_a_genuinely_unrecognised_section_alone():
    """The rescue net for stray sections must not be turned into bullets."""
    resume = parse_resume("""Jane Doe
jane@example.com | (469) 555-0100

PROFESSIONAL EXPERIENCE
Regional Vice President | Compassus
March 2021 - Present
- Led 14 hospice agencies across three states.

PATENTS
US 10,000,000 - A method for something.

EDUCATION
MBA
""")
    assert resume.roles[0].bullets == ["Led 14 hospice agencies across three states."]
    assert resume.roles[0].unmarked_bullets is False


def test_a_short_stray_line_is_not_promoted_to_a_bullet():
    resume = parse_resume("""Jane Doe
jane@example.com | (469) 555-0100

PROFESSIONAL EXPERIENCE
Regional Vice President | Compassus
March 2021 - Present
Dallas, TX
Healthcare

EDUCATION
MBA
""")
    assert resume.roles[0].bullets == []
