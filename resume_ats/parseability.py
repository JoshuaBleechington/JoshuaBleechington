"""Audit whether an ATS can read the resume at all.

This is the part candidates never get feedback on.  A resume can be a perfect
match on paper and still arrive at the recruiter as three lines of garbled
text, because the layout that made it look good defeated the parser.  Findings
here are graded by how the failure actually manifests:

* ``blocker``  -- content is likely lost or scrambled outright.
* ``major``    -- a field or section the parser expects will not be populated.
* ``minor``    -- cosmetic or risk-increasing, not usually fatal.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from .extract import Document
from .text import is_letter_spaced
from .resume import Resume, EMAIL_RE, PHONE_RE

SEVERITY_ORDER = {"blocker": 0, "major": 1, "minor": 2}
SEVERITY_PENALTY = {"blocker": 34.0, "major": 12.0, "minor": 4.0}

# Fonts that commonly fail to map glyphs back to characters on PDF export.
RISKY_FONTS = {
    "wingdings", "webdings", "symbol", "zapfdingbats", "marlett",
    "bookshelf symbol 7", "monotype sorts",
}

# Glyphs used as decorative bullets that some parsers emit as literal noise
# or drop along with the line they prefix.
EXOTIC_BULLETS = "▪◆◇■□▶►✔✓✦❖➢➤"


@dataclass
class Finding:
    severity: str
    code: str
    message: str
    fix: str = ""
    detail: str = ""

    def __str__(self) -> str:
        return f"[{self.severity}] {self.message}"


@dataclass
class ParseAudit:
    findings: List[Finding] = field(default_factory=list)
    score: float = 100.0

    def add(self, severity: str, code: str, message: str, fix: str = "", detail: str = "") -> None:
        self.findings.append(Finding(severity, code, message, fix, detail))

    def sorted_findings(self) -> List[Finding]:
        return sorted(self.findings, key=lambda f: (SEVERITY_ORDER[f.severity], f.code))

    def count(self, severity: str) -> int:
        return sum(1 for f in self.findings if f.severity == severity)


COVER_LETTER_MARKERS = (
    "dear hiring manager", "dear sir or madam", "to whom it may concern",
    "i am writing to express", "i am writing to apply", "cover letter",
    "thank you for considering my application",
)


def audit(doc: Document, resume: Resume, repairs: Sequence[str] = ()) -> ParseAudit:
    result = ParseAudit()
    text = doc.text or ""
    words = doc.word_count

    for note in repairs:
        result.add(
            "blocker", "encoding.symbolbullets",
            note[0].upper() + note[1:] + ".",
            "Replace them with your word processor's standard bullet list. "
            "The scores below assume the repair; without it, every "
            "accomplishment reads to a parser as unstructured prose.",
        )
    _check_cover_letter(result, text)
    _check_extraction(result, doc, resume, words)
    _check_layout(result, doc)
    _check_contact(result, doc, resume)
    _check_sections(result, resume)
    _check_dates(result, resume)
    _check_encoding(result, text)
    _check_length(result, doc, words)

    penalty = sum(SEVERITY_PENALTY[f.severity] for f in result.findings)
    result.score = max(0.0, 100.0 - penalty)
    return result


def _check_extraction(result: ParseAudit, doc: Document, resume: Resume, words: int) -> None:
    for warning in doc.warnings:
        result.add(
            "blocker", "extract.warning", warning,
            "Export a text-based PDF directly from Word or Google Docs "
            "(File > Save as PDF), never a scan, photo or 'print to image'.",
        )
    # This finding means "the content did not survive extraction", not "the
    # resume is short" -- length.short already covers that. Requiring the loss
    # of structure as well stops it firing on a genuinely brief resume that
    # parsed perfectly, where it was a false blocker that swamped the score.
    structure_lost = not resume.section_order or not resume.roles
    if words < 120 and doc.kind != "txt" and structure_lost:
        result.add(
            "blocker", "extract.empty",
            f"Only {words} words of text could be recovered from this file, "
            "and no usable structure came with them.",
            "If the resume looks full when you open it, the content is locked "
            "inside images or shapes. Rebuild it as ordinary body text.",
        )
    if doc.kind == "pdf" and doc.extractor == "none":
        result.add(
            "major", "extract.nopdf",
            "PDF text could not be verified because no PDF reader is installed.",
            "Run: pip install pdfminer.six",
        )


def _check_layout(result: ParseAudit, doc: Document) -> None:
    if doc.columns and doc.columns > 1:
        result.add(
            "blocker", "layout.columns",
            f"The document uses a {doc.columns}-column section layout.",
            "Switch to a single-column layout. Parsers read left-to-right "
            "across the whole page, which interleaves the two columns into "
            "unusable text.",
        )
    if doc.text_boxes:
        result.add(
            "blocker", "layout.textbox",
            f"{doc.text_boxes} text box(es) hold roughly {doc.text_box_chars} characters.",
            "Move text box content into the main document body. Most parsers "
            "skip text boxes entirely, so anything in them is invisible.",
        )
    if doc.tables:
        severity = "major" if doc.table_text_chars > 400 else "minor"
        result.add(
            severity, "layout.tables",
            f"{doc.tables} table(s) contain about {doc.table_text_chars} characters.",
            "Replace tables with plain paragraphs and simple bullet lists. "
            "Table cells are frequently read out of order or merged together.",
        )
    if doc.header_footer_chars > 40:
        result.add(
            "major", "layout.headerfooter",
            f"About {doc.header_footer_chars} characters sit in the page header or footer.",
            "Move anything important -- especially your name, email and phone "
            "-- into the body of the first page. Headers and footers are "
            "routinely discarded before parsing.",
        )
    if doc.images:
        result.add(
            "minor", "layout.images",
            f"The file embeds {doc.images} image(s).",
            "Make sure no skill, date or contact detail exists only inside an "
            "image, icon, logo or skill-rating graphic -- none of it is readable.",
        )
    risky = [f for f in doc.fonts if f.lower() in RISKY_FONTS]
    if risky:
        result.add(
            "minor", "layout.fonts",
            f"Symbol fonts in use: {', '.join(sorted(set(risky)))}.",
            "Use a standard text font. Symbol fonts often extract as random "
            "letters that pollute your keyword match.",
        )


def _check_contact(result: ParseAudit, doc: Document, resume: Resume) -> None:
    contact = resume.contact
    if not contact.email:
        result.add(
            "blocker", "contact.email",
            "No email address was found in the resume text.",
            "Put your email as plain selectable text near the top. If it is "
            "there but not detected, it is probably inside a header, a text "
            "box or an image.",
        )
    if not contact.phone:
        result.add(
            "major", "contact.phone",
            "No phone number was found in the resume text.",
            "Add a phone number in a standard format, e.g. (555) 010-2233. "
            "Avoid spacing it out with unusual separators.",
        )
    if not contact.name_guess:
        result.add(
            "minor", "contact.name",
            "A candidate name could not be identified in the first few lines.",
            "Put your full name alone on the first line, in body text rather "
            "than a graphic or a header.",
        )
    if contact.email and doc.header_footer_chars and not EMAIL_RE.search(
        "\n".join(resume.text.splitlines()[:15])
    ):
        result.add(
            "major", "contact.buried",
            "Contact details do not appear near the top of the document body.",
            "Move them to the first few lines of page one.",
        )


def _check_sections(result: ParseAudit, resume: Resume) -> None:
    present = set(resume.section_order)
    for name, severity, why in (
        ("experience", "blocker",
         "Without a recognised experience heading, the parser cannot build a "
         "work history, and many systems then treat the application as having "
         "no relevant experience."),
        ("education", "major",
         "Education is a standard indexed field and is often used for "
         "automatic filtering."),
        ("skills", "minor",
         "A skills section gives the keyword index a dense, unambiguous block "
         "to read."),
    ):
        if name not in present:
            result.add(
                severity, f"section.{name}",
                f"No recognised '{name}' section heading was found.",
                f"Add a plain heading such as '{name.title()}'. {why}",
            )
    if resume.unrecognized_headings:
        sample = ", ".join(resume.unrecognized_headings[:4])
        result.add(
            "minor", "section.custom",
            f"Non-standard heading(s) detected: {sample}.",
            "Creative headings ('Where I've Made an Impact') are not in any "
            "parser's vocabulary. Use conventional names and put the creative "
            "phrasing in the body if you want it.",
        )


def _check_dates(result: ParseAudit, resume: Resume) -> None:
    if not resume.roles:
        result.add(
            "blocker", "dates.noroles",
            "No dated positions could be reconstructed from the experience section.",
            "Give every role a heading with a date range on the same line, "
            "e.g. 'Security Analyst | Contoso | Mar 2022 - Present'.",
        )
        return
    undated = [r for r in resume.roles if not r.start]
    if undated:
        result.add(
            "major", "dates.missing",
            f"{len(undated)} position(s) have no parsable date range.",
            "Use a consistent 'Mon YYYY - Mon YYYY' or 'YYYY - YYYY' format on "
            "the same line as the job title.",
        )
    if not any(r.is_current for r in resume.roles):
        latest = max((r.end for r in resume.roles if r.end), default=None)
        if latest is None:
            return
        # Only worth flagging if the most recent role ended a while ago.
        from datetime import date as _date
        months = (_date.today().year - latest[0]) * 12 + (_date.today().month - latest[1])
        if months > 8:
            result.add(
                "minor", "dates.stale",
                f"The most recent dated role ended around {latest[1]:02d}/{latest[0]}.",
                "If you are currently employed, mark the role 'Present' so the "
                "parser records you as actively working.",
            )


def _check_encoding(result: ParseAudit, text: str) -> None:
    if not text:
        return
    if "�" in text:
        result.add(
            "major", "encoding.replacement",
            "The text contains replacement characters, a sign of a broken font "
            "or encoding.",
            "Retype the affected lines, or rebuild the document from a clean "
            "template.",
        )
    exotic = {c for c in text if c in EXOTIC_BULLETS}
    if exotic:
        result.add(
            "minor", "encoding.bullets",
            f"Decorative bullet glyphs in use: {' '.join(sorted(exotic))}.",
            "Use your word processor's standard bullet list. Decorative glyphs "
            "sometimes take the rest of the line with them.",
        )
    # Letter-spaced text ("E D U C A T I O N") tokenises into nonsense.
    spaced = [ln.strip() for ln in text.splitlines() if is_letter_spaced(ln)]
    if spaced:
        sample = "; ".join(s[:32] for s in spaced[:3])
        # A handful is a styled heading; a page full of it means the section
        # headings and skills list are gone entirely.
        severity = "blocker" if len(spaced) >= 4 else "major"
        result.add(
            severity, "encoding.spaced",
            f"{len(spaced)} line(s) are letter-spaced and unreadable to a parser: {sample}.",
            "Set letter-spacing in the font instead of typing spaces between "
            "letters. As typed, these words -- often the section headings and "
            "the whole skills list -- do not exist as far as an ATS is concerned.",
        )
    tabs = sum(1 for ln in text.splitlines() if ln.count("\t") >= 2)
    if tabs > 6:
        result.add(
            "minor", "encoding.tabs",
            f"{tabs} lines use multiple tab stops to simulate columns.",
            "Tab-aligned pseudo-columns can be read as one run-on line. Prefer "
            "separate lines.",
        )


def _check_cover_letter(result: ParseAudit, text: str) -> None:
    """A cover letter bound into the resume file displaces the resume itself."""
    head = " ".join(text.split())[:2500].lower()
    if any(marker in head for marker in COVER_LETTER_MARKERS):
        result.add(
            "major", "content.coverletter",
            "The file appears to open with a cover letter.",
            "Upload the cover letter as a separate document. Bound in here it "
            "becomes page one of the resume, pushing the work history down and "
            "diluting the keyword index with letter prose.",
        )


def _check_length(result: ParseAudit, doc: Document, words: int) -> None:
    if words > 1400:
        result.add(
            "minor", "length.long",
            f"The resume is {words} words, which is long for a screening read.",
            "Aim for roughly 450-900 words (1-2 pages) unless the posting asks "
            "for a full CV.",
        )
    elif 0 < words < 220:
        result.add(
            "major", "length.short",
            f"The resume is only {words} words.",
            "Thin content gives the keyword index almost nothing to match. "
            "Expand each role with concrete, quantified accomplishments.",
        )
    if doc.pages and doc.pages > 3:
        result.add(
            "minor", "length.pages",
            f"The PDF is {doc.pages} pages.",
            "Trim to two pages unless this is an academic or federal CV.",
        )
