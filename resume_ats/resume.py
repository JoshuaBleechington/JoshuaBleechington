"""Parse a resume into the structure an applicant tracking system tries to build.

An ATS does not read a resume as prose.  It looks for a handful of named
sections, pulls contact fields out of the top, and tries to reconstruct a
chronological work history from date ranges.  Modelling the same steps lets us
report where *its* reconstruction would fail, which is the failure mode
candidates never get told about.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Sequence, Set, Tuple

from .text import is_bullet, lines, normalize, stem, strip_bullet, tokenize

# Section headings an ATS looks for, mapped to the canonical bucket.  The
# aliases matter: "Professional Experience" is recognised, "What I've Been Up
# To" is not, and that difference silently drops a work history.
SECTION_ALIASES: Dict[str, Tuple[str, ...]] = {
    "summary": ("summary", "professional summary", "profile", "professional profile",
                "objective", "career objective", "about", "about me", "overview",
                "executive summary", "career summary", "highlights",
                "qualifications summary", "summary of qualifications"),
    "experience": ("experience", "work experience", "professional experience",
                   "employment", "employment history", "work history",
                   "relevant experience", "career history", "professional background",
                   "industry experience"),
    "education": ("education", "academic background", "academics",
                  "education and training", "educational background"),
    "skills": ("skills", "technical skills", "core competencies", "competencies",
               "technical proficiencies", "areas of expertise", "expertise",
               "technologies", "tools and technologies", "technical expertise",
               "key skills", "skill set"),
    "certifications": ("certifications", "certification", "licenses",
                       "licenses and certifications", "certifications and licenses",
                       "professional certifications", "credentials"),
    "projects": ("projects", "key projects", "selected projects", "portfolio",
                 "personal projects", "technical projects"),
    "awards": ("awards", "honors", "achievements", "recognition", "awards and honors"),
    "publications": ("publications", "papers", "research", "speaking", "presentations"),
    "volunteer": ("volunteer", "volunteering", "community involvement", "activities"),
    "clearance": ("clearance", "security clearance", "clearances"),
    "references": ("references",),
}

# Reverse index, longest-first so "professional experience" wins over "experience".
_HEADING_LOOKUP: List[Tuple[str, str]] = sorted(
    ((alias, canon) for canon, aliases in SECTION_ALIASES.items() for alias in aliases),
    key=lambda pair: -len(pair[0]),
)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]?\d{3}[\s.-]?\d{4}\b"
)
URL_RE = re.compile(r"(?:https?://|www\.)[^\s,;<>()\[\]]+", re.I)
LINKEDIN_RE = re.compile(r"linkedin\.com/in/[A-Za-z0-9_-]+", re.I)
GITHUB_RE = re.compile(r"github\.com/[A-Za-z0-9_-]+", re.I)

MONTHS = ("jan", "feb", "mar", "apr", "may", "jun",
          "jul", "aug", "sep", "oct", "nov", "dec")
_MONTH_NUM = {m: i + 1 for i, m in enumerate(MONTHS)}

# Unnamed on purpose: this fragment is interpolated twice into DATE_RANGE_RE,
# and duplicate group names are a regex compile error.
_DATE_TOKEN = (
    r"(?:(?:%s)[a-z]*\.?\s*(?:\d{1,2},?\s*)?)?(?:19|20)\d{2}" % "|".join(MONTHS)
)
_PRESENT = r"(?:present|current|now|to\s*date|ongoing)"
DATE_RANGE_RE = re.compile(
    r"(?P<start>%s)\s*(?:-|to|through|–|—)\s*(?P<end>%s|%s)"
    % (_DATE_TOKEN, _PRESENT, _DATE_TOKEN),
    re.I,
)

# Weak verbs that signal duty-listing rather than accomplishment.
WEAK_OPENERS = frozenset({
    "responsible", "duties", "tasked", "helped", "assisted", "worked",
    "participated", "involved", "familiar", "exposure", "handled", "various",
})

# Matched by stem, so "design"/"designed"/"designing" all count.  Irregular
# verbs need both forms listed, since no stemmer relates "lead" to "led".
# Present tense matters: a current role is correctly written in it, and an
# earlier version of this list credited only past tense, quietly penalising
# every bullet in the job the candidate holds right now.
STRONG_VERBS = frozenset("""
achieved administered analyzed architected audited automated built centralized
championed conducted configured consolidated coordinated created cut decreased
delivered deployed designed detected developed directed drove eliminated
engineered enhanced established executed expanded facilitated forged generated
hardened headed hunted identified implemented improved increased initiated
instituted integrated introduced investigated launched led managed mentored
migrated mitigated modernized monitored negotiated optimized orchestrated
overhauled owned partnered performed pioneered prevented prioritized produced
programmed quantified rearchitected rebuilt reduced refactored remediated
reorganized reported researched resolved restructured revamped saved scaled
secured shipped simplified spearheaded standardized streamlined strengthened
supervised supported tested tracked trained transformed triaged tuned
uncovered unified upgraded validated
lead drive build run win grow oversee hold keep rebuild undertake set shape
close sign retain position engage present negotiate expand advise partner
signed closed retained positioned engaged consulted presented negotiated won
grew expanded advised chaired forecast governed guided influenced instrumented
justified landed originated qualified quantified rescued restored safeguarded
sold sourced sponsored steered structured surfaced turned unblocked
""".split())

STRONG_VERB_STEMS = frozenset(stem(v) for v in STRONG_VERBS)
WEAK_OPENER_STEMS = frozenset(stem(v) for v in WEAK_OPENERS)


def opener_strength(bullet: str) -> str:
    """Classify a bullet's first word as 'strong', 'weak' or 'neutral'."""
    first = (tokenize(bullet) or [""])[0]
    if not first:
        return "neutral"
    root = stem(first)
    if root in WEAK_OPENER_STEMS:
        return "weak"
    if root in STRONG_VERB_STEMS:
        return "strong"
    return "neutral"

METRIC_RE = re.compile(
    r"(?:\$\s?\d|\d+\s?(?:%|percent)|\b\d{1,3}(?:,\d{3})+\b|\b\d+\s?(?:x|hours?|hrs?|"
    r"days?|weeks?|months?|users?|endpoints?|servers?|alerts?|incidents?|systems?|"
    r"accounts?|devices?|tickets?|k\b|m\b|mm\b|bn\b))",
    re.I,
)


@dataclass
class Role:
    """One position reconstructed from the experience section."""

    heading: str
    title: str = ""
    organization: str = ""
    start: Optional[Tuple[int, int]] = None   # (year, month)
    end: Optional[Tuple[int, int]] = None
    is_current: bool = False
    bullets: List[str] = field(default_factory=list)
    text: str = ""

    @property
    def months(self) -> int:
        if not self.start:
            return 0
        end = self.end or _today_ym()
        return max(0, (end[0] - self.start[0]) * 12 + (end[1] - self.start[1]))


@dataclass
class Contact:
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    urls: List[str] = field(default_factory=list)
    name_guess: Optional[str] = None
    location: Optional[str] = None

    @property
    def missing(self) -> List[str]:
        out = []
        if not self.email:
            out.append("email")
        if not self.phone:
            out.append("phone")
        return out


@dataclass
class Resume:
    text: str
    sections: Dict[str, str] = field(default_factory=dict)
    section_order: List[str] = field(default_factory=list)
    unrecognized_headings: List[str] = field(default_factory=list)
    contact: Contact = field(default_factory=Contact)
    roles: List[Role] = field(default_factory=list)
    bullets: List[str] = field(default_factory=list)

    @property
    def experience_bullets(self) -> List[str]:
        """Bullets attached to a dated position.

        Education and certification lines are list items, not accomplishments;
        counting "Master of Business Administration" as an unquantified bullet
        with a weak opener penalised the candidate for having a degree.
        """
        out: List[str] = []
        for role in self.roles:
            out.extend(role.bullets)
        return out or self.bullets

    @property
    def total_experience_months(self) -> int:
        """Union of role date ranges, so overlapping jobs are not double counted."""
        spans = [(r.start, r.end or _today_ym()) for r in self.roles if r.start]
        if not spans:
            return 0
        spans = sorted((_ym_to_int(s), _ym_to_int(e)) for s, e in spans)
        merged: List[List[int]] = []
        for s, e in spans:
            if merged and s <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], e)
            else:
                merged.append([s, e])
        return sum(max(0, e - s) for s, e in merged)

    @property
    def years_experience(self) -> float:
        return round(self.total_experience_months / 12.0, 1)

    def section(self, name: str) -> str:
        return self.sections.get(name, "")


def _today_ym() -> Tuple[int, int]:
    today = date.today()
    return (today.year, today.month)


def _ym_to_int(ym: Tuple[int, int]) -> int:
    return ym[0] * 12 + ym[1]


def _looks_like_heading(raw: str) -> bool:
    """Heuristics for a section heading line, before we know which section."""
    line = raw.strip().rstrip(":").strip()
    if not line or len(line) > 60 or is_bullet(raw):
        return False
    words = line.split()
    if len(words) > 5:
        return False
    if line.endswith((".", ",", ";")):
        return False
    letters = [c for c in line if c.isalpha()]
    if not letters:
        return False
    upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
    title_case = all(w[0].isupper() for w in words if w and w[0].isalpha())
    return upper_ratio > 0.7 or (title_case and len(words) <= 4)


def _match_heading(raw: str) -> Optional[str]:
    """Return the canonical section for a heading line, if it is one."""
    line = normalize(raw).strip().strip(":|-–—•* \t")
    line = re.sub(r"\s+", " ", line)
    if not line or len(line) > 60:
        return None
    for alias, canon in _HEADING_LOOKUP:
        if line == alias or line.startswith(alias + " ") or line.startswith(alias + ":"):
            return canon
        # "EXPERIENCE ————" style decorated headings
        if re.fullmatch(re.escape(alias) + r"[\s_=~.·|/-]*", line):
            return canon
    return None


def parse_dates(text: str) -> Tuple[Optional[Tuple[int, int]], Optional[Tuple[int, int]], bool]:
    """Pull the first date range out of a line."""
    m = DATE_RANGE_RE.search(text)
    if not m:
        return None, None, False
    start = _parse_date_token(m.group("start"))
    end_raw = m.group("end") or ""
    if re.fullmatch(_PRESENT, end_raw.strip(), re.I):
        return start, None, True
    return start, _parse_date_token(end_raw), False


def _parse_date_token(tok: str) -> Optional[Tuple[int, int]]:
    if not tok:
        return None
    tok = tok.lower()
    ym = re.search(r"(19|20)\d{2}", tok)
    if not ym:
        return None
    year = int(ym.group(0))
    month = 1
    for name, num in _MONTH_NUM.items():
        if name in tok:
            month = num
            break
    return (year, month)


def split_sections(text: str) -> Tuple[Dict[str, str], List[str], List[str]]:
    """Segment the resume by heading, mirroring how an ATS buckets content."""
    body = lines(text)
    sections: Dict[str, List[str]] = {}
    order: List[str] = []
    unrecognized: List[str] = []
    current = "_header"
    sections[current] = []
    order.append(current)

    for raw in body:
        canon = _match_heading(raw)
        if canon:
            current = canon
            if current not in sections:
                sections[current] = []
                order.append(current)
            continue
        if _looks_like_heading(raw) and len(raw.strip()) > 2:
            stripped = raw.strip().rstrip(":")
            # Only flag as an unrecognised *section* heading if it sits alone
            # and is not obviously a job title line (those carry dates).
            if not DATE_RANGE_RE.search(raw) and stripped.isupper() and len(stripped.split()) <= 4:
                unrecognized.append(stripped)
        sections[current].append(raw)

    return ({k: "\n".join(v).strip() for k, v in sections.items()}, order, unrecognized)


def parse_contact(text: str, header_hint: str = "") -> Contact:
    head = header_hint or "\n".join(text.splitlines()[:12])
    scope = head if EMAIL_RE.search(head) else text

    contact = Contact()
    m = EMAIL_RE.search(scope)
    contact.email = m.group(0) if m else None
    m = PHONE_RE.search(scope)
    contact.phone = m.group(0).strip() if m else None
    m = LINKEDIN_RE.search(text)
    contact.linkedin = m.group(0) if m else None
    m = GITHUB_RE.search(text)
    contact.github = m.group(0) if m else None
    contact.urls = URL_RE.findall(head)

    banners = repeated_lines(text)
    for raw in text.splitlines()[:6]:
        line = raw.strip()
        if not line or EMAIL_RE.search(line) or URL_RE.search(line):
            continue
        if line in banners:
            continue
        words = line.replace(",", " ").split()
        if 1 < len(words) <= 4 and all(w[0].isupper() for w in words if w[:1].isalpha()):
            if not any(ch.isdigit() for ch in line):
                contact.name_guess = line
                break

    loc = re.search(
        r"\b([A-Z][a-zA-Z.\- ]{2,24}),\s*([A-Z]{2}|[A-Z][a-z]+)\b(?:\s+\d{5})?", head
    )
    if loc:
        contact.location = loc.group(0).strip()
    return contact


_ORG_LINE_RE = re.compile(r"^[A-Z0-9][A-Z0-9 &.,'()/\-\u2013\u2014]{3,}$")


def _looks_like_org(line: str) -> bool:
    """An employer line is typically set in caps, often with a location."""
    return bool(_ORG_LINE_RE.match(line.strip()))


def _borrow_heading(recent: Sequence[str]) -> Tuple[str, str, List[str]]:
    """Recover a title and employer from the lines above a bare date line.

    Many resumes stack the block as employer / title / dates on three lines, so
    the dated line carries no name at all.  Reading only that line loses every
    job title and employer, and leaves the employer text stuck on the end of the
    previous role's last bullet.
    """
    title, org, used = "", "", []
    for line in reversed(list(recent)):
        # Collapse tabs first: a resume that tab-aligns its heading would
        # otherwise fail the employer test and land as the job title.
        candidate = " ".join(line.split())
        if not candidate or len(candidate) > 120 or is_bullet(candidate):
            continue
        if _looks_like_org(candidate):
            if not org:
                org, _ = _split_title_org(candidate)
                org = org or candidate
                used.append(line)
        elif not title:
            title = candidate
            used.append(line)
        if title and org:
            break
    return title, org, used


def parse_roles(experience_text: str, banners: Optional[Set[str]] = None) -> List[Role]:
    """Reconstruct positions from the experience block."""
    banners = banners or set()
    roles: List[Role] = []
    current: Optional[Role] = None
    buffer: List[str] = []
    recent: List[str] = []

    def flush() -> None:
        if current is not None:
            current.text = "\n".join(buffer).strip()
            roles.append(current)

    def disown(lines: Sequence[str]) -> None:
        """Take borrowed heading lines back off the previous role."""
        for line in lines:
            stripped = line.strip()
            if stripped in buffer:
                buffer.remove(stripped)
            if current is not None and current.bullets:
                last = current.bullets[-1]
                if last.endswith(stripped) and last != stripped:
                    current.bullets[-1] = last[: -len(stripped)].strip()
                elif last == stripped:
                    current.bullets.pop()

    for raw in experience_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        has_dates = bool(DATE_RANGE_RE.search(line)) or bool(
            re.search(r"(19|20)\d{2}\s*(?:-|–|—|to)\s*(?:present|current|(19|20)\d{2})", line, re.I)
        )
        if has_dates and not is_bullet(raw):
            title, org = _split_title_org(line)
            if title in banners:
                title = ""
            if not title or not org:
                borrowed_title, borrowed_org, used = _borrow_heading(recent)
                if not title and borrowed_title and borrowed_title not in banners:
                    title = borrowed_title
                if not org and borrowed_org:
                    org = borrowed_org
                disown(used)
            flush()
            buffer = [line]
            start, end, is_current = parse_dates(line)
            current = Role(heading=line, start=start, end=end, is_current=is_current)
            current.title, current.organization = title, org
            recent = []
            continue
        if current is None:
            if not is_bullet(raw):
                recent.append(line)
                if len(recent) > 3:
                    recent.pop(0)
            continue
        buffer.append(line)
        if not is_bullet(raw):
            recent.append(line)
            if len(recent) > 3:
                recent.pop(0)
        if is_bullet(raw):
            current.bullets.append(strip_bullet(raw))
        elif current.bullets:
            # Wrapped continuation of the previous bullet.
            current.bullets[-1] = (current.bullets[-1] + " " + line).strip()

    flush()
    return roles


def _split_title_org(line: str) -> Tuple[str, str]:
    """Best-effort split of a 'Title | Company | Dates' style heading."""
    cleaned = DATE_RANGE_RE.sub("", line)
    cleaned = re.sub(r"(19|20)\d{2}\s*(?:-|–|—|to)\s*(?:present|current)", "", cleaned, flags=re.I)
    # When the author used an explicit delimiter, honour only that one. Also
    # splitting on commas turned "Senior Director, Sales and Solution Support |
    # Pivot Technology Solutions" into a title of "Senior Director" and an
    # employer of "Sales and Solution Support", losing the real employer.
    if re.search(r"[|•·]", cleaned):
        pieces = re.split(r"\s*[|•·]\s*", cleaned)
    else:
        pieces = re.split(r"\s{2,}|\s+[-–—]\s+|,\s+", cleaned)
    parts = [p.strip(" ,|·—–-\t") for p in pieces]
    parts = [p for p in parts if p and not re.fullmatch(r"[\d\s./-]*", p)]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def collect_bullets(text: str) -> List[str]:
    """Collect bullet lines, stitching wrapped continuation lines back together."""
    out: List[str] = []
    open_bullet = False
    for raw in text.splitlines():
        if is_bullet(raw):
            out.append(strip_bullet(raw))
            open_bullet = True
            continue
        stripped = raw.strip()
        # A continuation line is indented and does not start a new construct.
        if open_bullet and stripped and raw[:1] in " \t" and not _match_heading(raw):
            out[-1] = (out[-1] + " " + stripped).strip()
        else:
            open_bullet = False
    return [b for b in out if len(b) > 15]


def repeated_lines(text: str, min_repeats: int = 3) -> Set[str]:
    """Lines that recur across the document -- page banners, headers, footers.

    A designed resume often repeats a name/title banner on every page.  Left in,
    it is mistaken for a job title on every role, so a candidate whose history
    tops out at Senior Director reads as "Vice President" throughout.
    """
    counts: Dict[str, int] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if 3 < len(line) < 70:
            counts[line] = counts.get(line, 0) + 1
    return {line for line, n in counts.items() if n >= min_repeats}


def parse(text: str) -> Resume:
    sections, order, unrecognized = split_sections(text)
    resume = Resume(
        text=text,
        sections=sections,
        section_order=[s for s in order if s != "_header"],
        unrecognized_headings=unrecognized,
    )
    resume.contact = parse_contact(text, sections.get("_header", ""))
    # The candidate's own name is short and often capitalised, which makes it
    # look exactly like a section heading. Flagging it as a "non-standard
    # heading" is noise, not a finding.
    if resume.contact.name_guess:
        name = resume.contact.name_guess.strip()
        resume.unrecognized_headings = [
            h for h in resume.unrecognized_headings
            if " ".join(h.split()).lower() != " ".join(name.split()).lower()
        ]
    banners = repeated_lines(text)
    exp = sections.get("experience", "")
    resume.roles = parse_roles(exp, banners) if exp else parse_roles(text, banners)
    resume.bullets = collect_bullets(text)
    return resume
