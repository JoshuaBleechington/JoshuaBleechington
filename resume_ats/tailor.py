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


def _join_wrapped(text: str) -> List[str]:
    """Rejoin lines that are continuations of the one above.

    A line is a continuation when the previous line did not end at a separator
    and this one does not start a new list item.
    """
    out: List[str] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        starts_item = stripped.startswith(("-", "\u2022", "*"))
        if out and not starts_item and not out[-1].rstrip().endswith((",", "|", ":", ";")):
            out[-1] = out[-1].rstrip() + " " + stripped
        else:
            out.append(stripped)
    return out


def _competency_terms(resume: Resume) -> List[str]:
    """Existing competencies, split out of whatever separator the resume used."""
    raw = resume.section("skills")
    terms: List[str] = []
    # Join wrapped lines first. A competency that ran over the line break was
    # otherwise cut in half, turning "Deal Shaping and Pursuit Management" into
    # "Deal Shaping and" plus "Pursuit Management".
    for chunk in _join_wrapped(raw):
        chunk = chunk.strip().lstrip("-•*").strip()
        if not chunk:
            continue
        # A "Category: a, b, c" line contributes its items, not its label.
        if ":" in chunk and len(chunk.split(":")[0].split()) <= 4:
            chunk = chunk.split(":", 1)[1]
        for part in chunk.replace("|", ",").split(","):
            part = " ".join(part.split())
            if 1 < len(part) <= 60:
                terms.append(part)
    seen, out = set(), []
    for t in terms:
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


# Glue words an initialism usually skips: SIEM is Security Information and
# Event Management, not S-I-A-E-M.
_ACRONYM_SKIP = frozenset({"and", "or", "of", "the", "for", "to", "in", "on", "a", "an"})


def _is_acronym_of(short: str, long_form: str) -> bool:
    """True when ``short`` is the initialism of ``long_form``.

    Tested both with and without the glue words, since real acronyms are
    inconsistent about them -- SIEM drops the "and", while R&D keeps it.
    """
    probe = short.replace(".", "").replace("-", "").replace("&", "").lower()
    if len(probe) < 2 or " " in short.strip():
        return False
    words = [w for w in long_form.split() if w and w[0].isalnum()]
    with_glue = "".join(w[0] for w in words).lower()
    without_glue = "".join(w[0] for w in words if w.lower() not in _ACRONYM_SKIP).lower()
    return probe in (with_glue, without_glue)


def pair_forms(a: str, b: str) -> str:
    """Render two names for one skill so a literal index finds both.

    Spelling out an acronym on first use -- "SIEM (Security Information and
    Event Management)" -- is ordinary resume practice, and it is the single
    cheapest way to satisfy two postings that search for opposite halves of the
    same pair.
    """
    short, long_form = (a, b) if len(a) <= len(b) else (b, a)
    if _is_acronym_of(short, long_form):
        return f"{short.upper()} ({long_form})"
    return f"{a} ({b})"


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
        resume_form = ""
        if canonical_term:
            for surface in lexicon.surfaces(canonical_term):
                found, _ = index.contains(surface)
                if found:
                    resume_form = surface
                    break
        if resume_form:
            if len(addable) < MAX_ADDED_TERMS:
                addable.append((term, resume_form))
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

    added_display: List[str] = []
    paired = 0
    for posting_form, resume_form in addable:
        posting_display = _title_case_term(posting_form, acronyms)
        resume_display = _title_case_term(resume_form, acronyms)
        differs = posting_display.lower() != resume_display.lower()
        is_pair = (_is_acronym_of(resume_form, posting_form)
                   or _is_acronym_of(posting_form, resume_form))
        if differs and is_pair:
            added_display.append(pair_forms(posting_display, resume_display))
            paired += 1
        else:
            added_display.append(posting_display)
    competencies.extend(added_display)

    if added_display:
        result.changes.append(Change(
            "terminology",
            "Added the posting's wording for skills the resume already "
            f"evidences under another name: {', '.join(added_display)}."))
    if paired:
        result.changes.append(Change(
            "terminology",
            f"Paired {paired} acronym(s) with their spelled-out form, so a "
            "posting searching for either half finds it."))

    # Lead with what this posting weights most heavily; a truncated read of a
    # long competencies line then still covers the important terms.
    weights = {r.term.lower(): r.weight for r in jd.requirements}
    competencies.sort(key=lambda t: -max(
        [weights.get(w, 0.0) for w in (t.lower(), t.lower().split(" (")[0])] or [0.0]))

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
                # Content that follows the bullets inside this role's block:
                # an undated position, a PATENTS or LANGUAGES list. Kept in
                # source order so it still reads as what it was.
                for line in role.trailing:
                    if line.startswith("- "):
                        result.blocks.append(
                            Block([Run(_clean(line[2:]), size=20)], kind="bullet"))
                    else:
                        result.blocks.append(
                            Block([Run(_clean(line), bold=True, size=20)],
                                  space_before=120, space_after=20))
            continue

        body = resume.section(key)
        if not body.strip():
            continue
        heading(label)
        # Rejoin wrapped lines so a summary reads as one flowing paragraph
        # rather than seven ragged fragments, which is how the source file's
        # line breaks would otherwise render in Word.
        for line in _join_wrapped(body):
            line = line.strip()
            if not line:
                continue
            if line.startswith("-"):
                result.blocks.append(Block([Run(_clean(line.lstrip("-")), size=20)], kind="bullet"))
            else:
                result.blocks.append(Block([Run(_clean(line), size=20)], space_after=40))

    result.changes.append(Change(
        "layout",
        "Rebuilt as single-column body text with standard headings, native "
        "Word bullets and dates on the title line: no tables, text boxes, "
        "columns, headers, footers or images."))

    # ---- nothing from the original may be lost ---------------------------
    rescued = _rescue_dropped_content(repaired, result, resume)
    if rescued:
        result.changes.append(Change(
            "structure",
            f"Carried {len(rescued)} line(s) the rebuild did not otherwise place "
            "into an Additional Information section, so nothing from the "
            "original is lost. Move them where they belong."))

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

    if jd.min_years and resume.years_experience >= jd.min_years * 2.5:
        result.manual.append(ManualItem(
            "verify",
            f"You evidence about {resume.years_experience:.0f} years against a "
            f"{jd.min_years:.0f}-year minimum. No keyword filter penalises that, but a "
            "human reader may read it as overqualified. If the level is right for you, "
            "say why you want this scope in the cover note."))

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


# Openers chosen so the finished bullet starts with a strong action verb,
# which is what the writing component and a human reader both look for.
_SKELETON_VERBS = (
    ("strategy", "Defined"), ("design", "Designed"), ("architecture", "Architected"),
    ("model", "Designed"), ("analytics", "Built"), ("data", "Built"),
    ("platform", "Delivered"), ("enablement", "Delivered"), ("training", "Delivered"),
    ("management", "Led"), ("leadership", "Led"), ("team", "Led"),
    ("practice", "Built"), ("program", "Led"), ("transformation", "Led"),
    ("consulting", "Led"), ("development", "Drove"), ("growth", "Drove"),
    ("partners", "Built"), ("partnerships", "Built"), ("workshops", "Ran"),
    ("reviews", "Ran"), ("governance", "Owned"), ("operations", "Owned"),
)


def _bullet_skeleton(term: str) -> str:
    """A fill-in-the-blank bullet built around the posting's exact wording."""
    lowered = term.lower()
    verb = "Led"
    for token, candidate in _SKELETON_VERBS:
        if token in lowered:
            verb = candidate
            break
    return f"{verb} ______ {term} for ______, delivering ______."


def _is_whole_requirement(line: str) -> bool:
    """Filter out the second half of a wrapped posting line.

    A requirement split across two lines yields fragments like "or related
    field; equivalent experience will be considered." Handing that back as a
    writing prompt is noise, so only lines that read as a complete statement
    are used.
    """
    text = line.strip()
    if len(text) < 35 or len(text) > 200:
        return False
    if not text[:1].isupper():
        return False
    first = text.split()[0].lower().rstrip(",")
    if first in {"and", "or", "but", "with", "including", "that", "which", "to",
                 "for", "as", "the", "a", "an", "in", "on", "of", "plus"}:
        return False
    return True


def notes_markdown(result: TailorResult, jd: JobDescription, report=None) -> str:
    """A working list for the candidate: what to write, and where.

    Kept strictly separate from the resume.  Everything here is a prompt for
    the person to answer from their own history -- the tool can say which
    requirement has no counterpart in the resume, but only they know whether
    they have done the work and what the number was.
    """
    name = result.resume.contact.name_guess if result.resume else ""
    lines: List[str] = []
    lines.append(f"# Tailoring notes — {jd.title or 'this posting'}")
    lines.append("")
    if name:
        lines.append(f"For: {name}")
    if report is not None:
        lines.append(f"Current score against this posting: **{report.total:.1f}/100** ({report.band})")
    lines.append("")
    lines.append("> These are prompts, not content. Answer them from work you actually did, "
                 "then paste the result into the resume. Nothing here has been written into "
                 "the document.")
    lines.append("")

    if report is not None and report.failed_gates:
        lines.append("## Blocking: unmet hard requirements")
        lines.append("")
        lines.append("A stated minimum behaves as a knockout, not a scoring factor. "
                     "If you do meet these, say so explicitly and early.")
        lines.append("")
        for gate in report.failed_gates:
            lines.append(f"- **{gate.detail}** — {gate.evidence}")
        lines.append("")

    if result.manual:
        lines.append("## What the posting wants that your resume does not show")
        lines.append("")
        for item in result.manual:
            lines.append(f"- {item.detail}")
        lines.append("")

    # Requirement lines with no counterpart: the clearest writing prompts there are.
    if report is not None and report.context_pairs:
        unmatched = [(line, sc) for line, sc, _ in report.context_pairs
                     if sc < 0.10 and _is_whole_requirement(line)]
        if unmatched:
            lines.append("## Requirements with no matching line in your resume")
            lines.append("")
            lines.append("For each, ask: *have I done this?* If yes, write one bullet — "
                         "**action verb + what you did + the scale + the result**. If no, skip it; "
                         "do not write it.")
            lines.append("")
            for line, _ in unmatched[:12]:
                lines.append(f"- [ ] {line}")
                lines.append("      - Your bullet: ")
            lines.append("")

    if report is not None:
        gaps = [m for m in report.missing(24) if m.requirement.known_skill
                or len(m.requirement.term.split()) > 1][:10]
        if gaps:
            lines.append("## Ready-to-fill bullets for the biggest gaps")
            lines.append("")
            lines.append("Each skeleton already carries the posting's exact wording, so once you "
                         "fill the blanks it lands as a keyword match *and* as demonstrated work. "
                         "Fill them from what you actually did. **If you cannot complete one "
                         "truthfully, delete it** -- a keyword you cannot speak to in the "
                         "interview costs more than the one it gained you.")
            lines.append("")
            for match in gaps:
                req = match.requirement
                term = req.term
                context = (req.contexts[0] if req.contexts else "").strip()
                lines.append(f"- [ ] **{term}**"
                             + ("  _(stated as required)_" if req.required else ""))
                lines.append(f"      `{_bullet_skeleton(term)}`")
                if context:
                    lines.append(f"      <sub>posting: \u201c{context[:120]}\u201d</sub>")
            lines.append("")

        missing = report.missing(20)
        if missing:
            lines.append("## Missing keywords, ranked by how hard the posting leans on them")
            lines.append("")
            lines.append("| Term | Required | Where the posting says it |")
            lines.append("|---|---|---|")
            for match in missing:
                req = match.requirement
                context = (req.contexts[0] if req.contexts else "").replace("|", "/")[:90]
                lines.append(f"| `{req.term}` | {'yes' if req.required else '—'} | {context} |")
            lines.append("")

    lines.append("## The two changes worth most, on any posting")
    lines.append("")
    lines.append("1. **Put numbers in your current role.** It is the first thing a recruiter "
                 "reads and the last thing most resumes quantify. Scope, savings, percentage, "
                 "headcount, contract value — two or three is enough.")
    lines.append("2. **Match the posting's exact title** in the headline under your name. "
                 "`tailor` does this automatically; check it reads naturally before sending.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("_Generated alongside the tailored resume. This file is for you — do not "
                 "send it with an application._")
    return "\n".join(lines) + "\n"


def _rescue_dropped_content(source: str, result: TailorResult, resume: Resume) -> List[str]:
    """Append anything from the original the rebuild did not carry over.

    Rebuilding from parsed structure means content the parser never attached to
    a role or a recognised section simply disappears: a position written
    without dates, a PATENTS or MILITARY SERVICE block, an award list under an
    unusual heading. Silently dropping a line from someone's resume is the
    worst thing this tool could do, so the rebuild is verified against the
    source and anything missing is carried through rather than lost.
    """
    from .text import tokenize

    placed = " ".join(tokenize(to_text(result)))
    placed_words = set(placed.split())

    # The cover letter is dropped deliberately; do not rescue it.
    head = " ".join(source.split())[:2500].lower()
    skip_prefix = 0
    if any(marker in head for marker in COVER_LETTER_MARKERS):
        for i, line in enumerate(source.splitlines()):
            if _match_section_heading(line):
                skip_prefix = i
                break

    contact_bits = {b.lower() for b in (
        resume.contact.email, resume.contact.phone, resume.contact.linkedin,
        resume.contact.github, resume.contact.location, resume.contact.name_guess) if b}

    missing: List[str] = []
    for raw in source.splitlines()[skip_prefix:]:
        line = " ".join(raw.split())
        if len(line.split()) < 5:
            continue
        if line.lower() in contact_bits:
            continue
        words = [w for w in tokenize(line) if len(w) > 2]
        if not words:
            continue
        covered = sum(1 for w in words if w in placed_words) / len(words)
        # Below this, the line's substance is genuinely absent rather than
        # merely reformatted.
        if covered < 0.6:
            missing.append(line.lstrip("-\u2022* ").strip())

    if missing:
        result.blocks.append(Block(
            [Run("ADDITIONAL INFORMATION", bold=True, size=21, color="222222")],
            kind="heading", space_before=220, space_after=90, rule_below=True))
        for line in missing:
            result.blocks.append(Block([Run(_clean(line), size=20)], kind="bullet"))
        result.text = to_text(result)
    return missing


def _match_section_heading(line: str):
    from .resume import _match_heading
    return _match_heading(line)


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
