"""The keyword denominator holds only terms a resume could honestly contain.

Measured against a real posting, over a third of the keyword weight was going
to slices of sentences: "decisions support exceptional", "ensures agency",
"providing", the hiring manager's title, the office's city. No resume can be
written to contain those, so every one of them lowered the ceiling an honest
candidate could reach. Each test pins one class of that noise -- and the terms
that must survive the cleaning, which matter more.
"""

import pytest

from resume_ats.extract import from_string
from resume_ats.jd import license_required, parse as parse_jd
from resume_ats.score import score

POSTING = """Area Vice President of Operations
Luminary Hospice - Dallas, TX
Reports To: SVP and General Manager of Business Operations
Location: Dallas, Texas (Travel territories: DFW, TX and KC, Missouri)
Must be a Registered Nurse living in the DFW Area

About the role:
Reporting to the SVP & General Manager, this leader ensures agency performance,
clinical quality, and patient care consistently reflect Luminary's standards.

Job Responsibilities:

Performance Management & Continuous Improvement
- Drive performance against clinical quality, regulatory compliance, census growth, and financial benchmarks.
- Ensure full compliance with CMS Conditions of Participation governing hospice care.
- Partner with business development to assess new markets and support agency start-ups.
- Lead with a patient-first mindset, ensuring every decision reflects the mission.

Job Qualifications:
- Registered Nurse license required for this role.
- 10+ years of progressive leadership experience in healthcare operations, with hospice or post-acute experience strongly preferred.
- Deep knowledge of regulatory requirements in hospice and home health.
- Ability to travel regularly to agencies.
"""


@pytest.fixture(scope="module")
def jd():
    return parse_jd(POSTING)


@pytest.fixture(scope="module")
def terms(jd):
    return {r.term for r in jd.requirements}


# -- noise that must not be a keyword ---------------------------------------

@pytest.mark.parametrize("fragment", [
    "ensures agency", "ensures agency performance", "decision reflects",
    "care consistently reflect", "drive performance", "travel regularly",
    "appropriately staffed", "providing", "ensuring", "reflect", "assess",
])
def test_a_slice_of_a_sentence_is_not_a_keyword(terms, fragment):
    assert fragment not in terms


@pytest.mark.parametrize("word", ["svp", "general manager", "svp general manager", "reports"])
def test_the_reporting_line_is_not_a_keyword(terms, word):
    assert word not in terms


@pytest.mark.parametrize("place", ["dallas", "dfw", "dfw area", "texas", "missouri"])
def test_the_office_location_is_not_a_keyword(terms, place):
    assert place not in terms


def test_a_residency_condition_is_not_a_keyword(terms):
    assert "registered nurse living" not in terms
    assert "living" not in terms


def test_a_title_case_sub_heading_is_not_rescued_as_a_term(terms):
    assert "performance management continuous" not in terms
    assert "management continuous improvement" not in terms
    assert "performance management continuous improvement" not in terms


# -- real terms that must survive --------------------------------------------

@pytest.mark.parametrize("term", [
    "census growth", "clinical quality", "regulatory compliance", "hospice",
    "agency performance", "business development", "continuous improvement",
])
def test_a_real_skill_survives_the_cleaning(terms, term):
    assert term in terms


def test_a_proper_term_inside_a_sentence_survives_despite_its_length(terms):
    """"CMS Conditions of Participation" is four words and in no lexicon."""
    assert "cms conditions of participation" in terms


def test_fewer_terms_means_a_higher_ceiling(jd):
    """The whole point: an honest resume can now reach the top."""
    assert len(jd.requirements) < 60


# -- hard requirements --------------------------------------------------------

def test_a_minimum_survives_a_preferred_clause_later_in_the_line(jd):
    """"10+ years ... hospice experience strongly preferred" still asks 10."""
    assert jd.min_years == 10.0


def test_a_required_licence_is_a_gate(jd):
    assert [h.detail for h in jd.hard_requirements if h.kind == "license"] == [
        "registered nurse", "registered nurse"]


@pytest.mark.parametrize("line,expected", [
    ("Registered Nurse license required for this role.", "registered nurse"),
    ("Must hold an active RN license in Texas.", "registered nurse"),
    ("Current CPA license required.", "certified public accountant"),
    ("Valid Class A CDL required.", "commercial driver's license"),
    ("RN preferred but not required.", None),
    ("Works closely with registered nurses on the floor.", None),
])
def test_licence_detection(line, expected):
    assert license_required(line) == expected


def test_a_heading_with_a_qualifier_is_still_classified(jd):
    kinds = {kind for _, kind, _ in jd.blocks}
    assert "required" in kinds and "responsibility" in kinds


# -- what the gate does to a score --------------------------------------------

NURSE = """Dana Whitfield
Dallas, TX | (469) 555-0182 | dana@example.com
Area Vice President of Operations

SUMMARY
Hospice operations executive leading multiple agencies across Texas.

PROFESSIONAL EXPERIENCE
Regional Director of Operations | Compassus
March 2010 - Present
- Led 14 hospice agencies, driving census growth and regulatory compliance.
- Drove performance against clinical quality, patient satisfaction and financial benchmarks.
- Partnered with business development to assess new markets and support agency start-ups.
- Owned survey readiness under CMS Conditions of Participation governing hospice care.
- Coached Executive Directors through corrective action plans and continuous improvement.
- Managed a $180M P&L across field operations in three states.

EDUCATION
Master of Health Administration, University of Texas

CERTIFICATIONS
Registered Nurse (RN), Texas
"""

NOT_A_NURSE = NURSE.replace("\nCERTIFICATIONS\nRegistered Nurse (RN), Texas\n", "\n")


def test_the_licence_gate_is_satisfied_by_the_resumes_own_shorthand(jd):
    report = score(from_string(NURSE), jd)
    assert not [g for g in report.failed_gates if g.kind == "license"]


def test_a_missing_required_licence_caps_the_score(jd):
    """The same resume minus one line: a knockout, not a deduction."""
    held = score(from_string(NURSE), jd).total
    missing = score(from_string(NOT_A_NURSE), jd)
    assert held > 62.0, "fixture must clear the cap for the cap to be observable"
    assert [g.kind for g in missing.failed_gates] == ["license"]
    assert missing.total <= 62.0 < held


def test_no_stated_minimum_cannot_be_under_met():
    posting = parse_jd("Director of Operations\n\nResponsibilities\n- Lead the region.\n")
    report = score(from_string(NURSE), posting)
    exp = next(c for c in report.components if c.name == "experience")
    assert exp.score == 100.0
