import pytest

from resume_ats.extract import ExtractionError, extract, from_string
from resume_ats.resume import parse as parse_resume


def test_docx_structure_is_detected(broken_docx):
    doc = extract(broken_docx)
    assert doc.tables == 1
    assert doc.text_boxes >= 1
    assert doc.columns == 2
    assert doc.images == 1
    assert doc.header_footer_chars > 0
    # Table content must still reach the text, in row order.
    assert "Splunk" in doc.text and "CrowdStrike" in doc.text


def test_legacy_doc_is_rejected_with_a_useful_message(tmp_path):
    path = tmp_path / "old.doc"
    path.write_bytes(b"\xd0\xcf\x11\xe0legacy word binary")
    with pytest.raises(ExtractionError) as exc:
        extract(str(path))
    assert ".docx" in str(exc.value)


def test_sections_are_bucketed(good_resume):
    resume = parse_resume(good_resume)
    for section in ("summary", "skills", "experience", "education", "certifications"):
        assert section in resume.section_order


def test_contact_details_are_extracted(good_resume):
    contact = parse_resume(good_resume).contact
    assert contact.email == "josh@example.com"
    assert contact.phone is not None
    assert contact.name_guess == "Joshua Bleechington"


def test_roles_and_dates_are_reconstructed(good_resume):
    resume = parse_resume(good_resume)
    assert len(resume.roles) == 2
    first = resume.roles[0]
    assert first.title == "Security Analyst"
    assert first.organization == "Contoso Financial"
    assert first.is_current
    assert len(first.bullets) == 2


def test_overlapping_roles_are_not_double_counted():
    text = """EXPERIENCE
Analyst | A Corp | Jan 2020 - Jan 2024
- Did work here.
Consultant | B Corp | Jan 2020 - Jan 2024
- Did work there.
"""
    resume = parse_resume(text)
    assert len(resume.roles) == 2
    # Four years held twice is still four years of experience.
    assert 3.5 <= resume.years_experience <= 4.5


def test_wrapped_bullet_lines_are_joined():
    text = """EXPERIENCE
Analyst | A Corp | Jan 2020 - Present
- Reduced mean time to respond by 40 percent across the
  entire detection pipeline.
"""
    resume = parse_resume(text)
    assert len(resume.roles[0].bullets) == 1
    assert "detection pipeline" in resume.roles[0].bullets[0]


def _pdfminer_available():
    try:
        import pdfminer.high_level  # noqa: F401
        return True
    except BaseException:
        return False


@pytest.mark.skipif(not _pdfminer_available(), reason="pdfminer.six not usable here")
def test_text_pdf_is_read_and_parsed(text_pdf):
    doc = extract(text_pdf)
    assert doc.kind == "pdf" and doc.pages == 1
    resume = parse_resume(doc.text)
    assert resume.contact.email == "josh@example.com"
    assert "experience" in resume.section_order
    assert resume.roles and resume.roles[0].is_current


def test_pdf_without_a_reader_degrades_to_a_warning(text_pdf, monkeypatch):
    """A broken or missing optional dependency must not abort the run."""
    import builtins

    real_import = builtins.__import__

    def explode(name, *args, **kwargs):
        if name.startswith("pdfminer"):
            # pdfminer pulls in cryptography, whose Rust bindings raise a
            # BaseException (not Exception) when the native module is broken.
            raise BaseException("simulated native crash")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", explode)
    doc = extract(text_pdf)
    assert doc.extractor == "none"
    assert doc.warnings and "PDF text extraction failed" in doc.warnings[0]
