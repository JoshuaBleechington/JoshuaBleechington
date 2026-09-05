"""Every position keeps its title and its employer, in any layout.

This has now broken three separate ways, each time deleting real content from
someone's resume: a role rendered as the literal word "Position", a role
borrowing the previous one's title, and an employer disowned from the output
without ever being used. So the layouts are pinned as a matrix -- a resume
puts the title, the employer and the dates in any of these orders, and none
of them may lose a name.
"""

import pytest

from resume_ats.aliases import default_lexicon
from resume_ats.extract import from_string
from resume_ats.jd import parse as parse_jd
from resume_ats.resume import parse as parse_resume
from resume_ats import tailor

HEAD = """Dana Whitfield
Dallas, TX | (469) 555-0182 | dana@example.com

SUMMARY
Healthcare operations leader.

PROFESSIONAL EXPERIENCE
"""
TAIL = "\nEDUCATION\nMaster of Health Administration, University of Texas\n"
B1 = "- Led 14 hospice agencies across three states.\n- Owned a $180M P&L.\n"
B2 = "- Ran regulatory compliance for twelve locations.\n"

T1, O1, D1 = "Regional Director of Operations", "Compassus", "March 2019 - Present"
T2, O2, D2 = "Director of Clinical Operations", "Bristol Hospice", "June 2014 - March 2019"

LAYOUTS = {
    "title, org | dates":  f"{T1}, {O1} | {D1}\n{B1}\n{T2}, {O2} | {D2}\n{B2}",
    "title | org | dates": f"{T1} | {O1} | {D1}\n{B1}\n{T2} | {O2} | {D2}\n{B2}",
    "org / title / dates": f"{O1}\n{T1}\n{D1}\n{B1}\n{O2}\n{T2}\n{D2}\n{B2}",
    "title / org / dates": f"{T1}\n{O1}\n{D1}\n{B1}\n{T2}\n{O2}\n{D2}\n{B2}",
    "dates / title / org": f"{D1}\n{T1}\n{O1}\n{B1}\n{D2}\n{T2}\n{O2}\n{B2}",
    "dates / org / title": f"{D1}\n{O1}\n{T1}\n{B1}\n{D2}\n{O2}\n{T2}\n{B2}",
    "org-loc / title / dates": f"{O1} - Dallas, TX\n{T1}\n{D1}\n{B1}\n{O2} - Salt Lake City, UT\n{T2}\n{D2}\n{B2}",
    "title TAB dates / org": f"{T1}\t{D1}\n{O1}\n{B1}\n{T2}\t{D2}\n{O2}\n{B2}",
    "org TAB dates / title": f"{O1}\t{D1}\n{T1}\n{B1}\n{O2}\t{D2}\n{T2}\n{B2}",
    "title, org (dates)":  f"{T1}, {O1} ({D1})\n{B1}\n{T2}, {O2} ({D2})\n{B2}",
    "org, loc | dates / title": f"{O1}, Dallas, TX | {D1}\n{T1}\n{B1}\n{O2}, Salt Lake City, UT | {D2}\n{T2}\n{B2}",
    "org / title / dates, caps": f"{O1.upper()}\n{T1}\n{D1}\n{B1}\n{O2.upper()}\n{T2}\n{D2}\n{B2}",
}

JD = """Area Vice President of Operations

Responsibilities
- Provide leadership to Executive Directors across multiple markets.
- Drive census growth and regulatory compliance.

Requirements
- 10+ years of healthcare operations leadership.
"""


def rebuild(body):
    text = HEAD + body + TAIL
    return text, tailor.build(from_string(text), parse_jd(JD), default_lexicon()).text


@pytest.mark.parametrize("name", sorted(LAYOUTS))
def test_two_roles_are_found_and_named(name):
    resume = parse_resume(HEAD + LAYOUTS[name] + TAIL)
    assert len(resume.roles) == 2, name
    for role in resume.roles:
        assert role.title, name
        assert role.title != "Position", name


@pytest.mark.parametrize("name", sorted(LAYOUTS))
def test_no_role_renders_as_the_word_position(name):
    _, out = rebuild(LAYOUTS[name])
    assert "\nPosition\n" not in out
    assert "\nPosition |" not in out


@pytest.mark.parametrize("name", sorted(LAYOUTS))
def test_both_titles_and_both_employers_reach_the_document(name):
    _, out = rebuild(LAYOUTS[name])
    lowered = out.lower()
    for token in (T1, T2, O1, O2):
        assert token.lower() in lowered, f"{name}: lost {token!r}"


@pytest.mark.parametrize("name", sorted(LAYOUTS))
def test_a_borrowed_line_is_not_printed_twice(name):
    _, out = rebuild(LAYOUTS[name])
    assert out.lower().count(O1.lower()) == 1, name
    assert out.lower().count(O2.lower()) == 1, name


@pytest.mark.parametrize("name", sorted(LAYOUTS))
def test_neither_role_steals_the_others_name(name):
    resume = parse_resume(HEAD + LAYOUTS[name] + TAIL)
    first, second = resume.roles
    assert first.title != second.title, name
    if first.organization and second.organization:
        assert first.organization != second.organization, name


def test_an_employer_that_contributed_nothing_is_left_in_place():
    """The bug: a borrowed line was disowned even when it went unused."""
    text = HEAD + LAYOUTS["title TAB dates / org"] + TAIL
    resume = parse_resume(text)
    assert resume.roles[0].organization == O1
    assert resume.roles[1].organization == O2


def test_the_employer_keeps_the_capitalisation_its_author_used():
    resume = parse_resume(HEAD + LAYOUTS["org / title / dates, caps"] + TAIL)
    assert resume.roles[0].organization == O1.upper()


def test_a_dates_suffix_does_not_leave_an_empty_bracket():
    resume = parse_resume(HEAD + LAYOUTS["title, org (dates)"] + TAIL)
    assert resume.roles[0].organization == O1
