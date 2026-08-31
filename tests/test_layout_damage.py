"""Regressions for damage found on real, design-led resumes.

Every case here comes from an actual resume that scored badly for mechanical
reasons rather than for anything about the candidate.
"""

from resume_ats import score_text
from resume_ats.extract import from_string
from resume_ats.jd import parse as parse_jd
from resume_ats.parseability import audit
from resume_ats.resume import parse as parse_resume, repeated_lines
from resume_ats.score import degree_evidence, score
from resume_ats.text import is_letter_spaced, repair_layout


# -- symbol-font bullets ---------------------------------------------------

def test_wingdings_bullets_are_repaired_and_reported():
    raw = "ü Led the migration of 30 services\nü Cut cost by 35%"
    repaired, notes = repair_layout(raw)
    assert repaired.splitlines()[0].startswith("- ")
    assert notes and "symbol font" in notes[0]


def test_orphaned_bullet_glyphs_are_dropped():
    repaired, _ = repair_layout("ü\nITIL v3 Trained")
    assert repaired.splitlines()[0] == "ITIL v3 Trained"


def test_symbol_bullets_do_not_read_as_missing_bullet_points():
    resume = """Jane Doe
jane@example.com | (555) 010-2233

SUMMARY
Solutions leader.

EXPERIENCE
Senior Director | Acme | Jan 2015 - Present
ü Signed deals in excess of $21M in annual contract value
ü Increased annual contract signings by 40% year over year

EDUCATION
MBA, University of Texas
"""
    report = score_text(resume, "Director\n\nRequirements\n- 5 years of experience.\n")
    assert report.resume.bullets, "repaired bullets should be visible to the parser"
    assert report.component("writing").score > 35.0


def test_repair_is_reported_as_a_blocker_not_silently_applied():
    text = "Jane Doe\njane@example.com | (555) 010-2233\n\nEXPERIENCE\nDirector | Acme | Jan 2015 - Present\nü Did the work here and there\n\nEDUCATION\nBS Engineering\n"
    repaired, notes = repair_layout(text)
    result = audit(from_string(text), parse_resume(repaired), notes)
    assert "encoding.symbolbullets" in {f.code for f in result.findings}
    assert any(f.severity == "blocker" for f in result.findings)


# -- letter spacing --------------------------------------------------------

def test_both_shapes_of_letter_spacing_are_detected():
    assert is_letter_spaced("E D U C A T I O N")
    assert is_letter_spaced("Tra ns fo rmati o na l  L e a d e r sh i p")
    assert not is_letter_spaced("Senior Solutions Director")
    assert not is_letter_spaced("Program & Account Management")


def test_pervasive_letter_spacing_is_a_blocker():
    text = ("Jane Doe\njane@x.com\n(555) 010-2233\n"
            + "\n".join(["C O N T A C T", "E D U C A T I O N", "S K I L L S", "C E R T S"])
            + "\nEXPERIENCE\nDirector | Acme | Jan 2015 - Present\n- Did work.\n")
    result = audit(from_string(text), parse_resume(text))
    spaced = [f for f in result.findings if f.code == "encoding.spaced"]
    assert spaced and spaced[0].severity == "blocker"


# -- degree evidence -------------------------------------------------------

def test_degree_counts_even_when_the_education_section_parsed_badly():
    # The "EDUCATION" heading lands *after* its own content, so the section
    # captures only page furniture -- but the degrees are plainly in the text.
    resume = parse_resume("""Jane Doe
jane@example.com | (555) 010-2233

EXPERIENCE
Director | Acme | Jan 2015 - Present
- Did the work.

UT Austin - MBA
UT Arlington - Bachelor of Science in Industrial Engineering

EDUCATION

Page 2 of 2
""")
    assert resume.section("education").strip() == "Page 2 of 2"
    assert degree_evidence(resume) >= 3, "an MBA in the body must still count"


def test_degree_gate_is_not_falsely_failed_by_a_bad_education_section():
    resume = """Jane Doe
jane@example.com | (555) 010-2233

EXPERIENCE
Director | Acme | Jan 2010 - Present
- Ran the programme.

UT Austin - MBA

EDUCATION

Page 2 of 2
"""
    jd = "Director\n\nRequirements\n- Bachelor's degree required.\n- Minimum of 5 years of experience.\n"
    report = score_text(resume, jd)
    degree_gates = [g for g in report.gates if g.kind == "degree"]
    assert degree_gates and all(g.satisfied for g in degree_gates)


# -- repeated page furniture -----------------------------------------------

def test_repeated_banner_is_identified():
    text = "\n".join(["VICE PRESIDENT, STRATEGIC SOLUTIONS", "a", "b"] * 3)
    assert "VICE PRESIDENT, STRATEGIC SOLUTIONS" in repeated_lines(text)


def test_page_banner_does_not_become_the_job_title():
    banner = "VICE PRESIDENT, STRATEGIC SOLUTIONS"
    text = f"""Mohammed Y
m@example.com | (555) 010-2233

EXPERIENCE
{banner}
Senior Director | Pivot | Jul 2018 - Apr 2020
- Signed deals worth $21M.
{banner}
Account Director | CompuCom | Jul 2015 - Jul 2018
- Retained major accounts.
{banner}
"""
    resume = parse_resume(text)
    assert all(r.title != banner for r in resume.roles), \
        "a repeated page banner must not be read as a held job title"


def test_banner_is_not_mistaken_for_the_candidate_name():
    banner = "VICE PRESIDENT STRATEGIC SOLUTIONS"
    text = f"{banner}\nPlano TX\nm@example.com\n\n{banner}\nx\n\n{banner}\ny\n"
    assert parse_resume(text).contact.name_guess != banner


# -- cover letter ----------------------------------------------------------

def test_embedded_cover_letter_is_flagged():
    text = ("Cover Letter\nDear Hiring Manager,\nI am writing to express my interest "
            "in joining your organization.\n\nEXPERIENCE\nDirector | Acme | Jan 2015 - Present\n- Work.\n")
    result = audit(from_string(text), parse_resume(text))
    assert "content.coverletter" in {f.code for f in result.findings}


def test_ordinary_resume_is_not_flagged_as_a_cover_letter():
    text = ("Jane Doe\njane@x.com | (555) 010-2233\n\nSUMMARY\nSolutions leader.\n\n"
            "EXPERIENCE\nDirector | Acme | Jan 2015 - Present\n- Work.\n")
    result = audit(from_string(text), parse_resume(text))
    assert "content.coverletter" not in {f.code for f in result.findings}


# -- domain vocabulary -----------------------------------------------------

def test_it_services_vocabulary_resolves():
    from resume_ats.aliases import default_lexicon
    lex = default_lexicon()
    for surface, canon in [
        ("total contract value", "tcv"),
        ("annual contract value", "acv"),
        ("pre-sales", "presales"),
        ("solution consulting", "presales"),
        ("SIAM", "service integration"),
        ("Master of Business Administration", "mba"),
        ("request for proposal", "rfp"),
        ("application modernization", "cloud migration"),
    ]:
        assert lex.resolve(surface) == canon, f"{surface} should resolve to {canon}"


def test_presales_resume_scores_above_an_unrelated_one():
    jd = parse_jd("""Senior Director, Solution Consulting

Requirements
- Must have experience leading presales and solution consulting teams.
- Track record closing outsourcing deals above $10M total contract value.
- Strong service management and ITIL knowledge.
""")
    presales = """Moe Y
moe@example.com | (555) 010-2233

SUMMARY
Presales and solution consulting leader.

EXPERIENCE
Senior Director, Solution Consulting | Acme | Jan 2015 - Present
- Led presales teams closing outsourcing deals above $40M total contract value.
- Ran service management and ITIL practice for the account.

EDUCATION
MBA
"""
    other = """Pat S
pat@example.com | (555) 111-2222

SUMMARY
Pastry chef.

EXPERIENCE
Head Chef | Sweet Co | Jan 2015 - Present
- Developed seasonal dessert menus.

EDUCATION
Culinary diploma
"""
    assert score(from_string(presales), jd).total > score(from_string(other), jd).total + 20
