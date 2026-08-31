"""Rebuild a resume as an ATS-aligned document, guided by a job description.

What this does and does not do is the whole design.

It **restructures and re-words material that is already in the resume**: it
repairs layout damage, rebuilds the document in a single-column form a parser
can read, orders the sections conventionally, sets a headline to the posting's
title, and adds a term to the competencies list when the posting uses a
different surface form for something the resume already evidences ("solution
consulting" where the resume says "presales").

It **never writes an achievement, metric, employer, credential or skill the
candidate did not supply**.  A tool that invents "increased revenue 40%"
because a posting asked for revenue growth is producing a false document, and
the person carrying it into an interview is the one who pays.  Gaps the
candidate must close themselves are reported separately and never appear in the
generated file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .aliases import SkillLexicon, default_lexicon
from .docx_writer import Block, Run, write_docx
from .extract import Document
from .jd import JobDescription
from .match import ResumeIndex, match_requirements
from .parseability import COVER_LETTER_MARKERS
from .resume import MONTHS, Resume, Role, repeated_lines
from .resume import parse as parse_resume
from .text import repair_layout

MONTH_NAMES = ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]

# Section order a parser expects, with the headings it recognises.
SECTION_ORDER: Sequence[Tuple[str, str]] = (
    ("summary", "SUMMARY"),
    ("skills", "CORE COMPETENCIES"),
    ("experience", "PROFESSIONAL EXPERIENCE"),
    ("projects", "PROJECTS"),
    ("education", "EDUCATION"),
    ("certifications", "CERTIFICATIONS"),
    ("clearance", "SECURITY CLEARANCE"),
    ("awards", "AWARDS"),
    ("publications", "PUBLICATIONS"),
    ("volunteer", "VOLUNTEER EXPERIENCE"),
)

MAX_ADDED_TERMS = 12


@dataclass
class Change:
    """One edit the tool made, and why."""

    category: str      # layout | structure | terminology
    detail: str


@dataclass
class ManualItem:
    """Something only the candidate can supply. Never written into the file."""

    kind: str          # missing-keyword | metrics | verify
    detail: str


@dataclass
class TailorResult:
    blocks: List[Block] = field(default_factory=list)
    text: str = ""
    changes: List[Change] = field(default_factory=list)
    manual: List[ManualItem] = field(default_factory=list)
    resume: Optional[Resume] = None
    headline: str = ""
    source_warnings: List[str] = field(default_factory=list)

    @property
    def source_is_usable(self) -> bool:
        """False when the input was too damaged to rebuild faithfully."""
        return not self.source_warnings

    def by_category(self, category: str) -> List[Change]:
        return [c for c in self.changes if c.category == category]


def _fmt_month(ym: Optional[Tuple[int, int]]) -> str:
    if not ym:
        return ""
    year, month = ym
    name = MONTH_NAMES[month - 1] if 1 <= month <= 12 else ""
    return f"{name} {year}".strip()


def _role_dates(role: Role) -> str:
    start = _fmt_month(role.start)
    if not start:
        return ""
    end = "Present" if role.is_current or role.end is None else _fmt_month(role.end)
    return f"{start} - {end}"


def _role_heading(role: Role) -> str:
    """Title and employer on one line, without the dates."""
    parts = [p for p in (role.title.strip(), role.organization.strip()) if p]
    if parts:
        return " | ".join(parts)
    # Fall back to the raw heading with any date range removed.
    from .resume import DATE_RANGE_RE
    cleaned = DATE_RANGE_RE.sub("", role.heading).strip(" |,-\t")
    return cleaned or "Position"


def _contact_line(resume: Resume) -> str:
    c = resume.contact
    bits = [c.location, c.phone, c.email, c.linkedin, c.github]
    return " | ".join(b for b in bits if b)


def _competency_terms(resume: Resume) -> List[str]:
    """Existing competencies, split out of whatever separator the resume used."""
    raw = resume.section("skills")
    terms: List[str] = []
    for line in raw.splitlines():
        line = line.strip().lstrip("-•*").strip()
        if not line:
            continue
        # A "Category: a, b, c" line contributes its items, not its label.
        if ":" in line and len(line.split(":")[0].split()) <= 4:
            line = line.split(":", 1)[1]
        for part in line.replace("|", ",").split(","):
            part = part.strip()
            if 1 < len(part) <= 60:
                terms.append(part)
    seen, out = set(), []
    for t in terms:
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


def _evidenced_gap_terms(
    jd: JobDescription, resume: Resume, index: ResumeIndex, lexicon: SkillLexicon
) -> Tuple[List[str], List[str]]:
    """Split the posting's terms into ones we may add, and ones we may not.

    A term is addable only when the resume already evidences the same canonical
    skill under a different name -- the posting says "solution consulting", the
    resume says "presales".  Adding the posting's wording then makes a literal
    index find something the candidate genuinely has.  A term with no evidence
    anywhere in the resume is never added; it goes to the candidate instead.
    """
    addable: List[str] = []
    absent: List[str] = []
    existing_terms = {t.lower() for t in _competency_terms(resume)}

    for match in sorted(jd.requirements, key=lambda r: -r.weight):
        term = match.term
        if term.lower() in existing_terms:
            continue
        present, _ = index.contains(term)
        if present:
            continue  # already worded exactly as the posting words it

        canonical_term = lexicon.resolve(term)
        evidenced = False
        if canonical_term:
            for surface in lexicon.surfaces(canonical_term):
                found, _ = index.contains(surface)
                if found:
                    evidenced = True
                    break
        if evidenced:
            if len(addable) < MAX_ADDED_TERMS:
                addable.append(term)
        elif match.required or match.known_skill:
            absent.append(term)
    return addable, absent


def _clean(text: str) -> str:
    """Collapse tabs and runs of spaces.

    Tab-aligned pseudo-columns survive extraction from the source file and read
    as one run-on line to a parser, so the rebuild must not carry them through.
    """
    return " ".join(text.split())


def _acronyms(lexicon: SkillLexicon) -> set:
    """Short single-word lexicon terms, which are acronyms in practice.

    Derived from the lexicon rather than hard-coded so a term added to
    ``aliases.json`` is capitalised correctly without touching this file --
    an earlier hard-coded list rendered CXO and OEM as "Cxo" and "Oem".
    """
    out = set()
    for key in lexicon.all_terms():
        if " " not in key and 2 <= len(key) <= 5 and key.isalpha() and key.islower():
            out.add(key)
    return out


_SMALL_WORDS = {"and", "or", "of", "the", "for", "to", "in", "as", "on", "a", "an"}


def _title_case_term(term: str, acronyms: Optional[set] = None) -> str:
    """Present a mined lower-case term the way a resume would write it."""
    acronyms = acronyms if acronyms is not None else set()
    words = term.split()
    out = []
    for i, w in enumerate(words):
        low = w.lower()
        # Check the singular too, so a posting's "OEMs" is not rendered "Oems".
        if w.isupper() or low in acronyms:
            out.append(w.upper())
        elif low.endswith("s") and low[:-1] in acronyms:
            out.append(low[:-1].upper() + "s")
        elif i and w.lower() in _SMALL_WORDS:
            out.append(w.lower())
        else:
            out.append(w[:1].upper() + w[1:])
    return " ".join(out)


def build(
    document: Document,
    jd: JobDescription,
    lexicon: Optional[SkillLexicon] = None,
    *,
    headline: Optional[str] = None,
) -> TailorResult:
    """Produce the tailored document, its change log and the manual work list."""
    lexicon = lexicon or default_lexicon()
    result = TailorResult()

    repaired, repairs = repair_layout(document.text)
    for note in repairs:
        result.changes.append(Change("layout", note[0].upper() + note[1:] + "."))

    resume = parse_resume(repaired)
    result.resume = resume
    index = ResumeIndex(repaired,
                        skills_text=resume.section("skills"),
                        recent_text=resume.roles[0].text if resume.roles else "")

    head = " ".join(repaired.split())[:2500].lower()
    if any(marker in head for marker in COVER_LETTER_MARKERS):
        result.changes.append(Change(
            "structure",
            "Dropped cover-letter prose from the top of the file; send it as a "
            "separate document."))

    banners = repeated_lines(repaired)
    if banners:
        result.changes.append(Change(
            "layout",
            f"Removed {len(banners)} repeated page banner(s), which a parser "
            "otherwise reads as a job title on every role."))

    # ---- header -------------------------------------------------------
    name = resume.contact.name_guess or ""
    if name:
        result.blocks.append(Block([Run(_clean(name), bold=True, size=30)], space_after=20))
    contact = _contact_line(resume)
    if contact:
        result.blocks.append(Block([Run(_clean(contact), size=19)], space_after=20))

    chosen_headline = headline or (jd.title.strip() if jd.title else "")
    result.headline = chosen_headline
    if chosen_headline:
        result.blocks.append(Block([Run(_clean(chosen_headline), bold=True, size=22)], space_after=160))
        result.changes.append(Change(
            "structure",
            f'Added the headline "{chosen_headline}" under the name, which is '
            "what title matching reads."))

    # ---- competencies -------------------------------------------------
    addable, absent = _evidenced_gap_terms(jd, resume, index, lexicon)
    acronyms = _acronyms(lexicon)
    competencies = _competency_terms(resume)
    added_display = [_title_case_term(t, acronyms) for t in addable]
    competencies.extend(added_display)
    if added_display:
        result.changes.append(Change(
            "terminology",
            "Added the posting's wording for skills the resume already "
            f"evidences under another name: {', '.join(added_display)}."))

    # ---- body ----------------------------------------------------------
    def heading(text: str) -> None:
        result.blocks.append(Block([Run(_clean(text), bold=True, size=21, color="222222")],
                                   kind="heading", space_before=220, space_after=90,
                                   rule_below=True))

    for key, label in SECTION_ORDER:
        if key == "skills":
            if competencies:
                heading(label)
                result.blocks.append(Block([Run(_clean(" | ".join(competencies)), size=20)],
                                           space_after=40))
            continue

        if key == "experience":
            if not resume.roles:
                continue
            heading(label)
            for role in resume.roles:
                result.blocks.append(Block([Run(_clean(_role_heading(role)), bold=True, size=20)],
                                           space_before=150, space_after=10))
                dates = _role_dates(role)
                if dates:
                    result.blocks.append(Block([Run(dates, italic=True, size=19, color="444444")],
                                               space_after=50))
                for bullet in role.bullets:
                    result.blocks.append(Block([Run(_clean(bullet), size=20)], kind="bullet"))
            continue

        body = resume.section(key)
        if not body.strip():
            continue
        heading(label)
        for line in body.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.lstrip().startswith("-"):
                result.blocks.append(Block([Run(_clean(line.lstrip("-")), size=20)], kind="bullet"))
            else:
                result.blocks.append(Block([Run(_clean(line), size=20)], space_after=40))

    result.changes.append(Change(
        "layout",
        "Rebuilt as single-column body text with standard headings, native "
        "Word bullets and dates on the title line: no tables, text boxes, "
        "columns, headers, footers or images."))

    # ---- what only the candidate can supply -----------------------------
    if absent:
        result.manual.append(ManualItem(
            "missing-keyword",
            "The posting asks for these and the resume shows no evidence of them. "
            "Add each only where you can point to real work: "
            + ", ".join(absent[:12]) + "."))

    for role in resume.roles[:1]:
        from .resume import METRIC_RE
        quantified = sum(1 for b in role.bullets if METRIC_RE.search(b))
        if role.bullets and quantified == 0:
            result.manual.append(ManualItem(
                "metrics",
                f'Your current role ("{_role_heading(role)}") has no numbers in '
                f"any of its {len(role.bullets)} bullets. Recruiters read it "
                "first. Add scope, savings, percentages or headcount to two or "
                "three of them."))

    skills_only = [m.requirement.term for m in match_requirements(jd.requirements, index, lexicon)
                   if m.status != "missing" and m.in_skills_only][:8]
    if skills_only:
        result.manual.append(ManualItem(
            "verify",
            "These appear only in your competencies list, never in a bullet: "
            + ", ".join(skills_only)
            + ". Show at least one being used in real work."))

    result.source_warnings = _source_warnings(repaired, resume)
    result.text = to_text(result)
    return result


def _source_warnings(text: str, resume: Resume) -> List[str]:
    """Detect a source too damaged to rebuild from.

    Tailoring can only rearrange what extraction recovered.  When the original
    is a graphic-led layout whose dates and headings never became text, the
    rebuild is faithful to a parse that already lost most of the resume -- and
    a confidently produced, *worse* document is the one outcome worse than
    saying nothing.  Better to stop and ask for a source that reads.
    """
    from .text import is_letter_spaced

    warnings: List[str] = []
    spaced = [ln for ln in text.splitlines() if is_letter_spaced(ln)]
    if len(spaced) >= 4:
        warnings.append(
            f"{len(spaced)} lines of the original are letter-spaced graphics rather "
            "than text, so their content never reached the parser and cannot be "
            "rebuilt from here.")
    if "experience" not in resume.section_order:
        warnings.append(
            "No experience section could be found in the original, so the work "
            "history could not be reconstructed.")
    if not resume.roles:
        warnings.append("No dated positions could be recovered from the original.")
    elif len(resume.roles) < 2 and len(text.split()) > 600:
        warnings.append(
            f"Only {len(resume.roles)} position(s) were recovered from a "
            f"{len(text.split())}-word document, so most of the work history is missing.")
    if not resume.contact.email:
        warnings.append("No email address could be read from the original.")
    return warnings


def to_text(result: TailorResult) -> str:
    """Plain-text form of the same document, for pasting into web forms."""
    lines: List[str] = []
    for block in result.blocks:
        content = "".join(r.text for r in block.runs)
        if block.kind == "bullet":
            lines.append("- " + content)
        elif block.kind == "heading":
            lines.append("")
            lines.append(content)
        else:
            lines.append(content)
    return "\n".join(lines).strip() + "\n"


def save(result: TailorResult, path: str) -> str:
    """Write the tailored resume to .docx, or to .txt/.md by extension."""
    lower = path.lower()
    if lower.endswith((".txt", ".md", ".markdown")):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(result.text)
        return path
    name = result.resume.contact.name_guess if result.resume else ""
    return write_docx(path, result.blocks,
                      title=f"{name} - Resume".strip(" -"), author=name or "")
