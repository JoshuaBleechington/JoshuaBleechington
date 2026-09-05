from resume_ats.extract import extract, from_string
from resume_ats.parseability import audit
from resume_ats.resume import parse as parse_resume


def _audit_text(text):
    doc = from_string(text)
    return audit(doc, parse_resume(text))


def test_broken_layout_produces_blockers(broken_docx):
    doc = extract(broken_docx)
    result = audit(doc, parse_resume(doc.text))
    codes = {f.code for f in result.findings}
    assert "layout.columns" in codes
    assert "layout.textbox" in codes
    assert result.count("blocker") >= 2
    assert result.score < 40


def test_clean_resume_has_no_blockers(good_resume):
    result = _audit_text(good_resume)
    assert result.count("blocker") == 0


def test_missing_contact_is_a_blocker():
    result = _audit_text("SUMMARY\nA candidate.\n\nEXPERIENCE\nAnalyst | X | 2020 - 2022\n- Did work.\n")
    assert "contact.email" in {f.code for f in result.findings}


def test_letter_spaced_headings_are_caught():
    result = _audit_text("Jane Doe\njane@x.com\n(555) 010-2233\nE X P E R I E N C E\nAnalyst | X | 2020 - 2022\n- Work.\n")
    assert "encoding.spaced" in {f.code for f in result.findings}


def test_every_finding_carries_a_fix(broken_docx):
    doc = extract(broken_docx)
    result = audit(doc, parse_resume(doc.text))
    assert result.findings
    for finding in result.findings:
        assert finding.fix, f"{finding.code} has no actionable fix text"
