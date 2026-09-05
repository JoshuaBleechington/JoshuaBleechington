from resume_ats import score_text
from resume_ats.extract import extract, from_string
from resume_ats.jd import parse as parse_jd
from resume_ats.score import WEIGHTS, score


def test_weights_sum_to_one_hundred():
    assert abs(sum(WEIGHTS.values()) - 100.0) < 1e-9


def test_relevant_resume_beats_irrelevant_one(good_resume, jd_text):
    irrelevant = """Pat Smith
pat@example.com | (555) 111-2222

SUMMARY
Pastry chef and kitchen manager.

EXPERIENCE
Head Pastry Chef | Sweet Co | Jan 2020 - Present
- Developed seasonal dessert menus and managed a team of six.

EDUCATION
Culinary Arts Diploma, 2019
"""
    relevant = score_text(good_resume, jd_text)
    unrelated = score_text(irrelevant, jd_text)
    assert relevant.total > unrelated.total + 20


def test_layout_damage_costs_points(broken_docx, clean_docx, jd_text):
    jd = parse_jd(jd_text)
    broken = score(extract(broken_docx), jd)
    clean = score(extract(clean_docx), jd)
    assert clean.total > broken.total
    assert clean.component("parseability").score > broken.component("parseability").score


def test_unmet_hard_requirement_caps_the_score():
    jd = parse_jd(
        "Senior Engineer\n\nRequirements\n"
        "- Must have an active Top Secret clearance.\n"
        "- Minimum of 3 years of experience with Python.\n"
    )
    resume = """Alex Roe
alex@example.com | (555) 010-9999

SUMMARY
Senior engineer.

SKILLS
Python, Django, PostgreSQL, AWS, Kubernetes, Terraform

EXPERIENCE
Senior Engineer | Acme | Jan 2015 - Present
- Built Python services handling 40,000 requests per second.
- Led the migration of 30 services to Kubernetes, cutting cost by 35%.

EDUCATION
B.S. Computer Science, 2014
"""
    report = score(from_string(resume), jd)
    failed = [g for g in report.gates if not g.satisfied]
    assert any(g.kind == "clearance" for g in failed)
    # A knockout filter is not a small deduction.
    assert report.total <= 62.0
    assert report.gate_penalty > 0


def test_met_hard_requirements_do_not_cap(good_resume, jd_text):
    report = score_text(good_resume, jd_text)
    assert not report.failed_gates
    assert report.gate_penalty == 0


def test_missing_keywords_are_ranked_by_weight(good_resume, jd_text):
    report = score_text(good_resume, jd_text)
    weights = [m.requirement.weight for m in report.missing(10)]
    assert weights == sorted(weights, reverse=True)


def test_skills_list_only_terms_score_lower_than_demonstrated_ones(jd_text):
    listed = """Sam Lee
sam@example.com | (555) 010-3333

SKILLS
Splunk, Python, MITRE ATT&CK, threat hunting

EXPERIENCE
Analyst | Acme | Jan 2018 - Present
- Handled assorted duties for the team as assigned each week.

EDUCATION
B.S. Computer Science, 2017
"""
    demonstrated = listed.replace(
        "- Handled assorted duties for the team as assigned each week.",
        "- Built threat hunting content in Splunk with Python, mapped to MITRE ATT&CK.",
    )
    assert score_text(demonstrated, jd_text).total > score_text(listed, jd_text).total


def test_quantified_bullets_score_better_than_vague_ones(jd_text):
    base = """Sam Lee
sam@example.com | (555) 010-3333

SKILLS
Splunk, Python

EXPERIENCE
Analyst | Acme | Jan 2018 - Present
{bullets}

EDUCATION
B.S. Computer Science, 2017
"""
    vague = base.format(bullets=(
        "- Responsible for monitoring alerts.\n"
        "- Helped with various security tasks."
    ))
    sharp = base.format(bullets=(
        "- Triaged 4,000 alerts per quarter, cutting false positives by 38%.\n"
        "- Automated 12 response playbooks, saving 20 hours per week."
    ))
    assert score_text(sharp, jd_text).component("writing").score > \
           score_text(vague, jd_text).component("writing").score


def test_score_stays_in_range_on_degenerate_input():
    for text in ("", "   ", "hello"):
        report = score_text(text, "Engineer\n\nRequirements\n- Python.\n")
        assert 0.0 <= report.total <= 100.0


def test_empty_job_description_does_not_crash(good_resume):
    report = score_text(good_resume, "")
    assert 0.0 <= report.total <= 100.0


def test_suggestions_lead_with_blockers(broken_docx, jd_text):
    report = score(extract(broken_docx), parse_jd(jd_text))
    assert report.suggestions
    assert report.suggestions[0].startswith("Fix first")
