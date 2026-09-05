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


def test_an_explicit_delimiter_wins_over_a_comma():
    """A comma inside a job title must not be mistaken for the employer break."""
    from resume_ats.resume import _split_title_org
    title, org = _split_title_org(
        "Senior Director, Sales and Solution Support | Pivot Technology Solutions | "
        "Plano, TX | July 2018 - April 2020")
    assert title == "Senior Director, Sales and Solution Support"
    assert org == "Pivot Technology Solutions"


def test_every_employer_survives_tailoring():
    resume = """Moe Y
moe@example.com | (555) 010-2233

PROFESSIONAL EXPERIENCE

Senior Solutions Director | Milestone Technologies Inc. | Fremont, CA | April 2020 - Present
- Lead enterprise transformation initiatives.

Senior Director, Sales and Solution Support | Pivot Technology Solutions | Plano, TX | July 2018 - April 2020
- Signed deals in excess of $21M in annual contract value.

EDUCATION
UT Austin - MBA
"""
    out = tailor.build(from_string(resume), parse_jd(JD), default_lexicon())
    for employer in ("Milestone Technologies Inc.", "Pivot Technology Solutions"):
        assert employer in out.text, f"{employer} was lost in the rebuild"


def test_plural_acronyms_are_capitalised():
    """A posting's "OEMs" must not be rendered "Oems"."""
    from resume_ats.tailor import _acronyms, _title_case_term
    acr = _acronyms(default_lexicon())
    assert _title_case_term("oems", acr) == "OEMs"
    assert _title_case_term("oem", acr) == "OEM"
    assert _title_case_term("solution consulting", acr) == "Solution Consulting"


# -- acronym pairing ---------------------------------------------------------

def test_acronym_and_expansion_are_paired():
    from resume_ats.tailor import pair_forms, _is_acronym_of
    assert _is_acronym_of("tcv", "total contract value")
    assert not _is_acronym_of("presales", "solution consulting")
    assert pair_forms("TCV", "Total Contract Value") == "TCV (Total Contract Value)"
    assert pair_forms("Total Contract Value", "TCV") == "TCV (Total Contract Value)"


def test_pairing_puts_both_forms_where_an_index_finds_them():
    resume = """Moe Y
moe@example.com | (555) 010-2233

AREAS OF EXPERTISE
SIEM, incident response

PROFESSIONAL EXPERIENCE
Director | Acme | Jan 2015 - Present
- Ran the SIEM platform for the estate.

EDUCATION
BS Engineering
"""
    jd = parse_jd("Director\n\nRequirements\n"
                  "- Must have security information and event management experience.\n")
    out = tailor.build(from_string(resume), jd, default_lexicon())
    body = out.text.lower()
    assert "siem" in body and "security information and event management" in body


# -- the working list --------------------------------------------------------

def test_notes_are_generated_and_never_enter_the_resume(result):
    from resume_ats.score import score
    notes = tailor.notes_markdown(result, parse_jd(JD), score(from_string(STACKED_RESUME), parse_jd(JD)))
    assert "# Tailoring notes" in notes
    assert "do not send it with an application" in notes
    for phrase in ("Tailoring notes", "Your bullet", "prompts, not content"):
        assert phrase not in result.text


def test_notes_filter_out_wrapped_line_fragments():
    from resume_ats.tailor import _is_whole_requirement
    assert _is_whole_requirement("Lead complex global procurement transformation programs.")
    assert not _is_whole_requirement("or related field; equivalent experience considered.")
    assert not _is_whole_requirement("and operational objectives that support growth.")
    assert not _is_whole_requirement("Short.")


def test_competencies_lead_with_the_postings_heaviest_terms():
    resume = """Moe Y
moe@example.com | (555) 010-2233

AREAS OF EXPERTISE
Volunteering, Presales Engagement, Gardening

PROFESSIONAL EXPERIENCE
Director | Acme | Jan 2015 - Present
- Led presales engagement for managed services pursuits.

EDUCATION
BS Engineering
"""
    jd = parse_jd("Director, Presales\n\nRequirements\n"
                  "- Must have presales experience. Presales leadership is required.\n")
    out = tailor.build(from_string(resume), jd, default_lexicon())
    line = next(l for l in out.text.splitlines() if "Presales Engagement" in l)
    assert line.index("Presales Engagement") < line.index("Gardening")


# -- batch -------------------------------------------------------------------

def test_batch_writes_a_document_and_notes_per_posting(tmp_path):
    from resume_ats.cli import main
    resume = tmp_path / "r.txt"
    resume.write_text(STACKED_RESUME, encoding="utf-8")
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    (jobs / "alpha.txt").write_text(JD, encoding="utf-8")
    (jobs / "beta.txt").write_text(UNGATED_JD, encoding="utf-8")
    outdir = tmp_path / "apps"

    assert main(["tailor", str(resume), "--jobs", str(jobs), "--outdir", str(outdir)]) == 0
    for stem in ("alpha", "beta"):
        assert (outdir / f"{stem}.docx").exists()
        assert (outdir / f"{stem}-notes.md").exists()


def test_batch_output_never_contains_invented_numbers(tmp_path):
    from resume_ats.cli import main
    resume = tmp_path / "r.txt"
    resume.write_text(STACKED_RESUME, encoding="utf-8")
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    (jobs / "alpha.txt").write_text(JD, encoding="utf-8")
    outdir = tmp_path / "apps"
    main(["tailor", str(resume), "--jobs", str(jobs), "--outdir", str(outdir)])

    nums = lambda t: set(re.findall(r"\$?\d[\d,.]*%?", t))
    produced = extract(str(outdir / "alpha.docx")).text
    assert not (nums(produced) - nums(STACKED_RESUME))


# -- OOXML validity ----------------------------------------------------------

def test_paragraph_properties_are_emitted_in_schema_order(tmp_path):
    """CT_PPr is a sequence: numPr, pBdr, spacing, ind, outlineLvl.

    Word tolerates a wrong order, so this only shows up under a schema check --
    which is exactly why it needs a test.
    """
    import re as _re
    import zipfile
    from resume_ats.docx_writer import Block, Run, write_docx

    path = str(tmp_path / "order.docx")
    write_docx(path, [
        Block([Run("Heading")], kind="heading", rule_below=True, space_before=200),
        Block([Run("A bullet")], kind="bullet"),
    ])
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")

    order = ["numPr", "pBdr", "spacing", "ind", "outlineLvl"]
    for para in _re.findall(r"<w:pPr>.*?</w:pPr>", xml):
        seen = [name for name in order if f"<w:{name}" in para]
        positions = [para.index(f"<w:{name}") for name in seen]
        assert positions == sorted(positions), f"pPr children out of schema order: {seen}"


def test_bullet_paragraphs_carry_numbering_and_indent(tmp_path):
    import zipfile
    from resume_ats.docx_writer import Block, Run, write_docx

    path = str(tmp_path / "b.docx")
    write_docx(path, [Block([Run("Did the thing")], kind="bullet")])
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
        assert "numbering.xml" in zf.read("word/_rels/document.xml.rels").decode("utf-8")
    assert "<w:numPr>" in xml and 'w:numId w:val="1"' in xml


# -- wrapped competency lines ------------------------------------------------

def test_a_competency_wrapped_across_lines_is_not_cut_in_half():
    resume = """Moe Y
moe@example.com | (555) 010-2233

CORE COMPETENCIES
Presales Engagement | Deal Shaping and
Pursuit Management | Managed Services

PROFESSIONAL EXPERIENCE
Director | Acme | Jan 2015 - Present
- Led presales pursuits.

EDUCATION
BS Engineering
"""
    out = tailor.build(from_string(resume), parse_jd(JD), default_lexicon())
    assert "Deal Shaping and Pursuit Management" in out.text
    assert "Deal Shaping and |" not in out.text


def test_a_wrapped_summary_becomes_one_paragraph():
    """Source line breaks must not freeze into ragged fragments in Word."""
    resume = """Moe Y
moe@example.com | (555) 010-2233

SUMMARY
Presales leader with 28 years in IT services, managed services
and IT outsourcing. Builds teams that shape and close complex
multi-tower deals.

PROFESSIONAL EXPERIENCE
Director | Acme | Jan 2015 - Present
- Led presales pursuits.

EDUCATION
BS Engineering
"""
    out = tailor.build(from_string(resume), parse_jd(JD), default_lexicon())
    summary_blocks = [b for b in out.blocks
                      if b.kind == "body" and "Presales leader" in "".join(r.text for r in b.runs)]
    assert len(summary_blocks) == 1
    assert "managed services and IT outsourcing" in "".join(r.text for r in summary_blocks[0].runs)


# -- nothing from the original may be lost -----------------------------------

RAGGED = """Alex Roe
alex@example.com | (555) 010-2233

SUMMARY
Solutions leader in managed services.

PROFESSIONAL EXPERIENCE

Senior Director | Acme | Jan 2018 - Present
- Led presales pursuits worth $20M in total contract value.

Consultant | Betaco
- Advised clients on managed services strategy and delivery.

PATENTS
US 9,123,456 - Method for adaptive routing in distributed networks

LANGUAGES
Fluent in Spanish and conversational in Portuguese

EDUCATION
BS Engineering, State University
"""


def test_a_position_without_dates_is_not_dropped():
    out = tailor.build(from_string(RAGGED), parse_jd(JD), default_lexicon())
    assert "Betaco" in out.text
    assert "Advised clients on managed services strategy" in out.text


def test_a_section_under_an_unrecognised_heading_survives():
    out = tailor.build(from_string(RAGGED), parse_jd(JD), default_lexicon())
    assert "9,123,456" in out.text
    assert "adaptive routing" in out.text
    assert "Spanish" in out.text


def test_the_rescue_net_does_not_fire_when_content_is_placed_properly():
    """The safety net is a last resort, not the normal path."""
    out = tailor.build(from_string(RAGGED), parse_jd(JD), default_lexicon())
    assert "ADDITIONAL INFORMATION" not in out.text
    assert "9,123,456" in out.text and "Spanish" in out.text


def test_an_unrecognised_block_keeps_its_own_heading_and_content():
    out = tailor.build(from_string(RAGGED), parse_jd(JD), default_lexicon())
    text = out.text
    assert text.index("PATENTS") < text.index("9,123,456")
    assert text.index("LANGUAGES") < text.index("Spanish")


def test_an_undated_position_keeps_its_own_bullet():
    out = tailor.build(from_string(RAGGED), parse_jd(JD), default_lexicon())
    text = out.text
    assert text.index("Consultant | Betaco") < text.index("Advised clients on managed services")
    assert "delivery. US 9,123,456" not in text


def test_every_dated_position_survives_tailoring():
    out = tailor.build(from_string(STACKED_RESUME), parse_jd(JD), default_lexicon())
    source_roles = parse_resume(STACKED_RESUME).roles
    assert len(source_roles) == 2
    for role in source_roles:
        assert role.organization in out.text
        for bullet in role.bullets:
            assert bullet in out.text


def test_the_cover_letter_is_still_dropped_not_rescued():
    """The rescue pass must not resurrect prose we deliberately removed."""
    source = ("Cover Letter\nDear Hiring Manager,\nI am writing to express my sincere "
              "interest in this position and my lifelong passion for excellence.\n\n" + RAGGED)
    out = tailor.build(from_string(source), parse_jd(JD), default_lexicon())
    assert "passion for excellence" not in out.text
    assert "9,123,456" in out.text


# -- the "Position" bug: a date line above the job title ---------------------

DATES_ABOVE = """Joshua B
Phoenix, AZ | 602-555-0100 | jb@example.com

SUMMARY
CISSP certified cloud security analyst.

CORE COMPETENCIES
Governance, Risk, and Compliance (GRC): NIST 800-53, HIPAA, Risk Register
Vulnerability Management: Tenable.io, Nessus, CVE Triage

PROFESSIONAL EXPERIENCE
February 2020 - Present
Cloud Security Analyst, Acme Corp
- Built KQL detections in Microsoft Sentinel, cutting alert fatigue 40%.

June 2017 - January 2020
Security Analyst, Betaco
- Ran authenticated vulnerability scans across 900 endpoints.

EDUCATION
BS Information Technology
"""


def test_a_date_line_above_the_title_still_names_the_role():
    """A right-aligned date often extracts onto the line above the title."""
    resume = parse_resume(DATES_ABOVE)
    assert len(resume.roles) == 2
    assert resume.roles[0].title == "Cloud Security Analyst"
    assert resume.roles[0].organization == "Acme Corp"
    assert resume.roles[1].title == "Security Analyst"
    assert resume.roles[1].organization == "Betaco"


def test_no_role_is_ever_rendered_as_the_word_position():
    out = tailor.build(from_string(DATES_ABOVE), parse_jd(JD), default_lexicon())
    assert "\nPosition\n" not in out.text
    assert "Cloud Security Analyst" in out.text
    assert "Security Analyst | Betaco" in out.text


def test_a_later_role_does_not_steal_the_previous_titles():
    """With dates above the name, role two was taking role one's title."""
    resume = parse_resume(DATES_ABOVE)
    assert resume.roles[0].title != resume.roles[1].title
    assert resume.roles[0].organization != resume.roles[1].organization


DATES_BELOW = DATES_ABOVE.replace(
    "February 2020 - Present\nCloud Security Analyst, Acme Corp",
    "Cloud Security Analyst, Acme Corp\nFebruary 2020 - Present",
).replace(
    "June 2017 - January 2020\nSecurity Analyst, Betaco",
    "Security Analyst, Betaco\nJune 2017 - January 2020",
)


def test_a_borrowed_heading_is_not_also_kept_as_the_previous_roles_content():
    """The line naming role two was surviving as a stray line under role one."""
    out = tailor.build(from_string(DATES_BELOW), parse_jd(JD), default_lexicon())
    headings = [line for line in out.text.splitlines() if "Betaco" in line]
    assert headings == ["Security Analyst | Betaco"]


def test_both_date_layouts_rebuild_to_the_same_headings():
    above = tailor.build(from_string(DATES_ABOVE), parse_jd(JD), default_lexicon())
    below = tailor.build(from_string(DATES_BELOW), parse_jd(JD), default_lexicon())
    pick = lambda t: [l for l in t.splitlines() if "|" in l and ("Acme" in l or "Betaco" in l)]
    assert pick(above.text) == pick(below.text)


def test_the_employer_keeps_its_name_without_the_location():
    resume = parse_resume("""J B
jb@example.com | (555) 010-2233

PROFESSIONAL EXPERIENCE
Acme Corp - Phoenix, AZ
Cloud Security Analyst
February 2020 - Present
- Built detections.

EDUCATION
BS IT
""")
    assert resume.roles[0].organization == "Acme Corp"
    assert resume.roles[0].title == "Cloud Security Analyst"


# -- competency categories ---------------------------------------------------

def test_a_multi_word_category_label_is_not_split_into_skills():
    """"Governance, Risk, and Compliance (GRC):" is a label, not three skills."""
    out = tailor.build(from_string(DATES_ABOVE), parse_jd(JD), default_lexicon())
    assert "Governance, Risk, and Compliance (GRC): NIST 800-53" in out.text
    assert "| Governance |" not in out.text


def test_skill_categories_stay_on_their_own_lines():
    out = tailor.build(from_string(DATES_ABOVE), parse_jd(JD), default_lexicon())
    lines = [l for l in out.text.splitlines() if ":" in l and "|" in l]
    assert any(l.startswith("Vulnerability Management:") for l in lines)
    assert not any("Risk Register Vulnerability Management" in l for l in out.text.splitlines())
