"""Rewriting must change the wording and never the claim.

The whole value of a resume builder is that its output is defensible in the
interview it wins. Every test here is a way that could stop being true: a
number that moves, a skill that appears from nowhere, a verb that upgrades
"assisted" into "led". None of those are style questions.
"""

import pytest

from resume_ats.aliases import default_lexicon
from resume_ats.extract import from_string
from resume_ats.jd import parse as parse_jd
from resume_ats.score import score
from resume_ats import tailor

WEAK = """Dana Whitfield
Dallas, TX | (469) 555-0182 | dana@example.com

SUMMARY
Healthcare operations leader.

PROFESSIONAL EXPERIENCE
Regional Director of Operations | Compassus
March 2019 - Present
- Responsible for managing 14 hospice agencies across three states.
- Duties included overseeing a $180M profit and loss statement.
- Assisted with quality improvement initiatives across the region.
- Worked with finance on budgeting, forecasting and margin improvement.

EDUCATION
Master of Health Administration, University of Texas
"""

JD = """Area Vice President of Operations

Responsibilities
- Provide leadership and mentorship to Executive Directors.
- Drive census growth, clinical quality and regulatory compliance.
- Partner with business development on market expansion.

Requirements
- 10+ years of healthcare operations leadership.
- Bachelor's degree required.
"""


# -- the claim survives the rewrite -----------------------------------------

@pytest.mark.parametrize("before,after", [
    ("Responsible for managing a team of 12 architects.", "Managed a team of 12 architects."),
    ("Duties included overseeing a $180M P&L.", "Oversaw a $180M P&L."),
    ("Tasked with driving census growth across the region.",
     "Drove census growth across the region."),
    ("Accountable for building and leading the presales team.",
     "Built and led the presales team."),
    ("Handled escalations for twelve enterprise accounts.",
     "Managed escalations for twelve enterprise accounts."),
])
def test_a_duty_phrase_becomes_the_action_it_describes(before, after):
    assert tailor.strengthen_bullet(before)[0] == after


@pytest.mark.parametrize("bullet", [
    "Led 14 hospice agencies, growing average daily census 28%.",
    "Signed deals exceeding $21M in annual contract value.",
    "Oversaw a $180M multi-site P&L.",
    "Built and led the presales organisation.",
])
def test_a_bullet_that_already_opens_strongly_is_left_alone(bullet):
    assert tailor.strengthen_bullet(bullet) == (bullet, "")


def test_a_rewrite_never_upgrades_the_strength_of_the_claim():
    """"Assisted with X" is a claim to have assisted, not to have led."""
    out, _ = tailor.strengthen_bullet("Assisted with the migration of 40 servers to Azure.")
    assert out.startswith("Supported")
    assert "Led" not in out and "Drove" not in out


@pytest.mark.parametrize("bullet", [
    "Responsible for managing 14 hospice agencies across three states.",
    "Was able to successfully utilize new reporting to cut costs by 12%.",
    "Duties included overseeing a $180M profit and loss statement.",
])
def test_no_number_changes_in_a_rewrite(bullet):
    import re
    numbers = lambda t: sorted(re.findall(r"[\d.,]+%?", t))
    assert numbers(tailor.strengthen_bullet(bullet)[0]) == numbers(bullet)


def test_a_rewrite_that_would_leave_a_fragment_is_abandoned():
    """Nothing is better than a bullet with no verb in it."""
    for bullet in ["Responsible for compliance.", "Involved in various meetings."]:
        out, why = tailor.strengthen_bullet(bullet)
        assert out == bullet and why == ""


def test_rewriting_lifts_the_writing_score():
    lex = default_lexicon()
    jd = parse_jd(JD)
    before = score(from_string(WEAK), jd)
    result = tailor.build(from_string(WEAK), jd, lex)
    after = score(from_string(result.text), jd)
    picked = lambda r: next(c for c in r.components if c.name == "writing").score
    assert picked(after) > picked(before)
    assert result.rewritten_bullets


# -- keywords: evidence, or the candidate's own say-so ----------------------

def test_a_term_the_resume_evidences_in_other_words_may_be_added():
    """"Executive leadership" against "leading a team of Executive Directors"."""
    from resume_ats.match import ResumeIndex
    from resume_ats.resume import parse as parse_resume
    text = ("PROFESSIONAL EXPERIENCE\nDirector | Acme\nJan 2019 - Present\n"
            "- Built and led a team of Executive Directors across four markets.\n")
    resume = parse_resume(text)
    index = ResumeIndex(text)
    assert tailor._words_all_present("executive leadership", index)


def test_a_term_the_resume_does_not_evidence_is_never_added():
    from resume_ats.match import ResumeIndex
    text = ("PROFESSIONAL EXPERIENCE\nDirector | Acme\nJan 2019 - Present\n"
            "- Built and led a team of Executive Directors.\n")
    index = ResumeIndex(text)
    assert not tailor._words_all_present("kubernetes administration", index)
    assert not tailor._words_all_present("continuous improvement", index)


def test_an_unevidenced_term_stays_out_of_the_document_by_default():
    result = tailor.build(from_string(WEAK), parse_jd(JD), default_lexicon())
    assert "mentorship" not in result.text.lower()
    assert "business development" not in result.text.lower()


def test_a_confirmed_skill_is_added_as_a_skill_only():
    """The candidate says they have it; that is not evidence they did a thing."""
    result = tailor.build(from_string(WEAK), parse_jd(JD), default_lexicon(),
                          confirmed_skills=["mentorship", "business development"])
    assert "Mentorship" in result.text
    assert result.confirmed_added
    # It reaches the competencies line, never an achievement bullet.
    bullets = [b for b in result.blocks if b.kind == "bullet"]
    joined = " ".join(r.text for b in bullets for r in b.runs).lower()
    assert "mentorship" not in joined
    assert "business development" not in joined


def test_confirming_a_skill_is_recorded_as_a_change():
    result = tailor.build(from_string(WEAK), parse_jd(JD), default_lexicon(),
                          confirmed_skills=["mentorship"])
    assert any("confirmed" in c.detail.lower() for c in result.changes)


def test_no_invented_number_enters_the_document():
    import re
    result = tailor.build(from_string(WEAK), parse_jd(JD), default_lexicon(),
                          confirmed_skills=["mentorship", "audits"])
    source = set(re.findall(r"\d[\d.,]*%?", WEAK))
    for number in re.findall(r"\d[\d.,]*%?", result.text):
        assert number in source or number in {"10", "2019", "3"}
