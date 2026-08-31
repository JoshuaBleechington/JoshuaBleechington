"""Tests for rebuilding a resume as an ATS-aligned document.

The integrity tests matter more than the score tests. A resume generator that
invents an achievement produces a document its owner has to defend in an
interview, so "never fabricates" is the property worth pinning hardest.
"""

import re

import pytest

from resume_ats import tailor
from resume_ats.aliases import default_lexicon
from resume_ats.docx_writer import Block, Run, write_docx
from resume_ats.extract import extract, from_string
from resume_ats.jd import parse as parse_jd
from resume_ats.resume import parse as parse_resume
from resume_ats.score import score

STACKED_RESUME = """MOHAMMED Y
Plano, TX | (469) 555-0100 | moe@example.com

SUMMARY AND SKILLS
Presales leader in IT outsourcing.

AREAS OF EXPERTISE
Presales Engagement, Account Management, Service Management

PROFESSIONAL EXPERIENCE

PIVOT TECHNOLOGY SOLUTIONS - PLANO, TX
Senior Director (Sales and Solutions Support)
July 2018 - April 2020

- Signed deals in excess of $21M in annual contract value
- Increased annual contract signings by 40% year over year

COMPUCOM - DALLAS, TX
Senior Solutions Executive / Managing Account Director
July 2015 - July 2018

- Retained multi-million-dollar accounts through back to green action plans

EDUCATION
UT Austin - MBA
"""

JD = """Senior Director, Solution Consulting (Managed Services)

Responsibilities
- Lead solution consulting teams across managed services pursuits.
- Own deal shaping and pricing strategy for multi-tower outsourcing.

Minimum Qualifications
- Bachelor's degree required.
- Minimum of 10 years of experience in IT services.
- Must have experience with Kubernetes and Terraform.
- Strong service management and ITIL knowledge.
"""


@pytest.fixture
def result():
    return tailor.build(from_string(STACKED_RESUME), parse_jd(JD), default_lexicon())


# -- integrity ---------------------------------------------------------------

def test_no_numbers_are_invented(result):
    """Not one figure may appear that the candidate did not write."""
    nums = lambda t: set(re.findall(r"\$?\d[\d,.]*%?", t))
    assert not (nums(result.text) - nums(STACKED_RESUME))


def test_unevidenced_skills_never_enter_the_document(result):
    """The posting demands Kubernetes and Terraform; the resume shows neither."""
    body = result.text.lower()
    assert "kubernetes" not in body
    assert "terraform" not in body


def test_unevidenced_skills_are_reported_to_the_candidate_instead(result):
    manual = " ".join(m.detail.lower() for m in result.manual)
    assert "kubernetes" in manual or "terraform" in manual


def test_manual_items_are_not_written_into_the_file(result):
    """Advice to the candidate must never reach the employer."""
    body = result.text.lower()
    for phrase in ("only you can", "add scope", "recruiters read", "no evidence"):
        assert phrase not in body


def test_evidenced_synonym_is_added(result):
    """The resume says "presales"; the posting says "solution consulting"."""
    assert "solution consulting" in result.text.lower()
    assert any(c.category == "terminology" for c in result.changes)


def test_every_original_bullet_survives(result):
    for bullet in ("Signed deals in excess of $21M in annual contract value",
                   "Increased annual contract signings by 40% year over year",
                   "Retained multi-million-dollar accounts through back to green action plans"):
        assert bullet in result.text


def test_employers_and_dates_are_preserved(result):
    for token in ("PIVOT TECHNOLOGY SOLUTIONS", "COMPUCOM",
                  "July 2018 - April 2020", "July 2015 - July 2018"):
        assert token in result.text


# -- structure ---------------------------------------------------------------

def test_stacked_headings_recover_title_and_employer():
    resume = parse_resume(STACKED_RESUME)
    assert len(resume.roles) == 2
    assert resume.roles[0].title == "Senior Director (Sales and Solutions Support)"
    assert resume.roles[0].organization == "PIVOT TECHNOLOGY SOLUTIONS"
    assert resume.roles[1].organization == "COMPUCOM"


def test_employer_line_does_not_stick_to_the_previous_bullet():
    resume = parse_resume(STACKED_RESUME)
    assert all("COMPUCOM" not in b for b in resume.roles[0].bullets)


def test_headline_defaults_to_the_posting_title(result):
    assert result.headline == "Senior Director, Solution Consulting (Managed Services)"
    assert result.text.startswith("MOHAMMED Y")


def test_headline_can_be_overridden():
    out = tailor.build(from_string(STACKED_RESUME), parse_jd(JD), default_lexicon(),
                       headline="VP, Solutions")
    assert "VP, Solutions" in out.text


def test_standard_headings_are_emitted(result):
    for heading in ("SUMMARY", "CORE COMPETENCIES", "PROFESSIONAL EXPERIENCE", "EDUCATION"):
        assert heading in result.text


# -- the generated file ------------------------------------------------------

def test_generated_docx_is_parse_safe(tmp_path, result):
    path = str(tmp_path / "out.docx")
    tailor.save(result, path)
    doc = extract(path)
    assert doc.tables == 0
    assert doc.text_boxes == 0
    assert doc.columns == 1
    assert doc.images == 0
    assert doc.header_footer_chars == 0


def test_generated_docx_bullets_are_readable(tmp_path, result):
    path = str(tmp_path / "out.docx")
    tailor.save(result, path)
    resume = parse_resume(extract(path).text)
    assert len(resume.experience_bullets) >= 3


# A JD with no years minimum, so an unmet knockout gate does not cap both
# versions at the same number and hide the improvement.
UNGATED_JD = """Senior Director, Solution Consulting (Managed Services)

Responsibilities
- Lead solution consulting teams across managed services pursuits.
- Own deal shaping and pricing strategy for multi-tower outsourcing.
- Apply service management and ITIL practice to delivery.
"""


def test_tailoring_raises_the_score(tmp_path):
    jd = parse_jd(UNGATED_JD)
    before = score(from_string(STACKED_RESUME), jd)
    result = tailor.build(from_string(STACKED_RESUME), jd, default_lexicon())
    path = str(tmp_path / "out.docx")
    tailor.save(result, path)
    after = score(extract(path), jd)
    assert after.total > before.total
    assert after.parse.score >= before.parse.score


def test_an_unmet_gate_still_caps_the_tailored_resume(tmp_path):
    """Tailoring must not paper over a knockout the candidate genuinely fails."""
    jd = parse_jd(JD)  # requires 10+ years; the fixture evidences far fewer
    result = tailor.build(from_string(STACKED_RESUME), jd, default_lexicon())
    path = str(tmp_path / "out.docx")
    tailor.save(result, path)
    after = score(extract(path), jd)
    assert after.failed_gates
    assert after.total <= 62.0


def test_save_honours_a_text_extension(tmp_path, result):
    path = str(tmp_path / "out.txt")
    tailor.save(result, path)
    assert open(path, encoding="utf-8").read() == result.text


def test_symbol_bullets_are_repaired_into_the_output():
    source = STACKED_RESUME.replace("- Signed deals", "ü Signed deals")
    out = tailor.build(from_string(source), parse_jd(JD), default_lexicon())
    assert "Signed deals in excess of $21M" in out.text
    assert any("symbol font" in c.detail for c in out.changes)


def test_cover_letter_prose_is_dropped():
    source = ("Cover Letter\nDear Hiring Manager,\nI am writing to express my interest "
              "in your organization and my passion for excellence.\n\n" + STACKED_RESUME)
    out = tailor.build(from_string(source), parse_jd(JD), default_lexicon())
    assert "passion for excellence" not in out.text
    assert any("cover-letter" in c.detail.lower() for c in out.changes)


# -- the writer --------------------------------------------------------------

def test_writer_round_trips_bullets_and_text(tmp_path):
    path = str(tmp_path / "w.docx")
    write_docx(path, [
        Block([Run("Jane Doe", bold=True, size=30)]),
        Block([Run("Did the thing", size=20)], kind="bullet"),
    ], title="T", author="Jane Doe")
    text = extract(path).text
    assert "Jane Doe" in text
    assert "- Did the thing" in text


def test_writer_escapes_markup(tmp_path):
    path = str(tmp_path / "e.docx")
    write_docx(path, [Block([Run("R&D <Solutions> \"quoted\"")])])
    assert 'R&D <Solutions> "quoted"' in extract(path).text


# -- refusing a source that cannot be rebuilt --------------------------------

DAMAGED = """C O N T A C T
E D U C A T I O N
S K I L L S
C E R T I F I C A T I O N S
Tra ns fo rmati o na l  L e a d e r sh i p
2 0 2 0 - Cu rre nt  S e n i o r  D i re c to r
"""


def test_a_damaged_source_is_refused_not_silently_rebuilt():
    out = tailor.build(from_string(DAMAGED), parse_jd(JD), default_lexicon())
    assert not out.source_is_usable
    assert any("letter-spaced" in w for w in out.source_warnings)


def test_a_clean_source_is_usable(result):
    assert result.source_is_usable
    assert result.source_warnings == []


def test_cli_refuses_a_damaged_source(tmp_path):
    from resume_ats.cli import main
    resume = tmp_path / "bad.txt"
    resume.write_text(DAMAGED, encoding="utf-8")
    jd = tmp_path / "jd.txt"
    jd.write_text(JD, encoding="utf-8")
    out = tmp_path / "out.docx"
    assert main(["tailor", str(resume), str(jd), "-o", str(out)]) == 2
    assert not out.exists(), "no file should be written when the source is unusable"


def test_cli_force_overrides_the_refusal(tmp_path):
    from resume_ats.cli import main
    resume = tmp_path / "bad.txt"
    resume.write_text(DAMAGED, encoding="utf-8")
    jd = tmp_path / "jd.txt"
    jd.write_text(JD, encoding="utf-8")
    out = tmp_path / "out.docx"
    assert main(["tailor", str(resume), str(jd), "-o", str(out), "--force"]) == 0
    assert out.exists()
