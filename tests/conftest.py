import os
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'

GOOD_RESUME = """\
Joshua Bleechington
Denver, CO | josh@example.com | (555) 010-2233
linkedin.com/in/example

PROFESSIONAL SUMMARY
Security analyst focused on detection engineering and vulnerability management.

TECHNICAL SKILLS
Splunk, Microsoft Sentinel, Python, KQL, NIST CSF, ISO 27001

PROFESSIONAL EXPERIENCE

Security Analyst | Contoso Financial | Mar 2022 - Present
- Led vulnerability management across 1,200 endpoints, cutting critical findings by 63%.
- Built threat hunting playbooks in Microsoft Sentinel using KQL, uncovering 14 incidents.

IT Support Specialist | Northwind Health | Jun 2019 - Feb 2022
- Administered Active Directory accounts for 800 users.
- Assisted with endpoint patching.

EDUCATION
B.S. Information Technology, Metro State University, 2019

CERTIFICATIONS
CISSP, CompTIA Security+
"""

JD = """\
Cybersecurity Analyst II

About Us
We are an equal opportunity employer offering 401k, dental insurance and PTO.

Responsibilities
- Monitor and triage alerts in Splunk Enterprise Security.
- Perform threat hunting using MITRE ATT&CK.

Minimum Qualifications
- Bachelor's degree in Computer Science or related field.
- Minimum of 4 years of experience in a security operations center.
- Must have hands-on experience with SIEM platforms.
- Experience with Python scripting.

Preferred Qualifications
- CISSP certification preferred.
- Kubernetes experience is nice to have.

Benefits
Stock options and a generous 401k.
"""


@pytest.fixture
def good_resume():
    return GOOD_RESUME


@pytest.fixture
def jd_text():
    return JD


@pytest.fixture
def broken_docx(tmp_path):
    """A .docx that breaks every rule an ATS cares about."""
    path = tmp_path / "broken.docx"
    doc = f"""<?xml version="1.0"?>
<w:document {W} xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">
<w:body>
<w:p><w:r><w:t>Jane Doe</w:t></w:r></w:p>
<w:tbl><w:tr>
  <w:tc><w:p><w:r><w:t>Splunk and CrowdStrike and Sentinel and Python and Azure</w:t></w:r></w:p></w:tc>
  <w:tc><w:p><w:r><w:t>Threat hunting and incident response and forensics work</w:t></w:r></w:p></w:tc>
</w:tr></w:tbl>
<w:p><w:r><w:txbxContent><w:p><w:r><w:t>CISSP certified professional</w:t></w:r></w:p></w:txbxContent></w:r></w:p>
<w:sectPr><w:cols w:num="2"/></w:sectPr>
</w:body></w:document>"""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml", doc)
        zf.writestr(
            "word/header1.xml",
            f'<?xml version="1.0"?><w:hdr {W}><w:p><w:r>'
            f"<w:t>jane@example.com | 555-010-2233</w:t></w:r></w:p></w:hdr>",
        )
        zf.writestr("word/media/image1.png", b"\x89PNG")
    return str(path)


@pytest.fixture
def clean_docx(tmp_path):
    """A .docx with the same content laid out the way a parser expects."""
    path = tmp_path / "clean.docx"
    paras = "".join(
        f"<w:p><w:r><w:t>{line}</w:t></w:r></w:p>"
        for line in GOOD_RESUME.replace("&", "&amp;").splitlines()
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml",
                    f'<?xml version="1.0"?><w:document {W}><w:body>{paras}</w:body></w:document>')
    return str(path)


@pytest.fixture
def text_pdf(tmp_path):
    """A minimal but valid text-based PDF (no external writer needed)."""
    content = (
        b"BT /F1 11 Tf 50 750 Td (Joshua Bleechington) Tj "
        b"0 -14 Td (josh@example.com | \\(555\\) 010-2233) Tj\n"
        b"0 -22 Td (SUMMARY) Tj 0 -14 Td (Security analyst focused on threat hunting.) Tj\n"
        b"0 -22 Td (EXPERIENCE) Tj "
        b"0 -14 Td (Security Analyst | Contoso | Mar 2022 - Present) Tj\n"
        b"0 -14 Td (- Led vulnerability management across 1,200 endpoints.) Tj\n"
        b"0 -22 Td (EDUCATION) Tj 0 -14 Td (B.S. Information Technology, 2019) Tj ET"
    )
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + obj + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    path = tmp_path / "resume.pdf"
    path.write_bytes(out)
    return str(path)
