"""Turn a job posting into a weighted requirement profile.

Not every phrase in a posting carries equal weight.  A term inside a "Minimum
Qualifications" block that is prefixed with "must have" is a gate; the same term
under "Nice to have" is a tiebreaker; the same term in the benefits blurb is
noise.  Mining without that distinction is why naive keyword tools tell people
to stuff "401k" and "equal opportunity employer" into their resume.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .aliases import SkillLexicon, default_lexicon
from .text import STOPWORDS, canonical, is_bullet, normalize, phrase_ngrams, strip_bullet

# Blocks that describe the company or the benefits package, not the candidate.
# Everything under one of these headings is excluded from keyword mining.
NOISE_SECTIONS = (
    "benefits", "perks", "what we offer", "our offer", "compensation",
    "salary", "pay range", "pay transparency", "equal opportunity",
    "eeo", "diversity", "e-verify", "accommodation", "accommodations",
    "about us", "about the company", "who we are", "our company",
    "our mission", "our values", "why join", "life at", "disclaimer",
    "legal", "privacy", "how to apply", "application process",
)

REQUIRED_SECTIONS = (
    "requirements", "required", "minimum qualifications", "basic qualifications",
    "qualifications", "what you need", "what you'll need", "you have",
    "must have", "required skills", "required qualifications",
    "minimum requirements", "essential", "essential functions", "skills",
    "experience required", "who you are", "we're looking for",
)

PREFERRED_SECTIONS = (
    "preferred", "preferred qualifications", "nice to have", "nice-to-have",
    "bonus", "bonus points", "desired", "desirable", "plus", "pluses",
    "additional qualifications", "a plus", "even better", "extra credit",
    "preferred skills", "good to have",
)

RESPONSIBILITY_SECTIONS = (
    "responsibilities", "what you'll do", "what you will do", "the role",
    "duties", "job duties", "day to day", "day-to-day", "your impact",
    "key responsibilities", "about the role", "role overview", "position summary",
)

MUST_MARKERS = re.compile(
    r"\b(must have|must be|must possess|is required|are required|required\b|requires\b|"
    r"minimum of|at least|mandatory|non-negotiable|essential)\b", re.I
)
NICE_MARKERS = re.compile(
    r"\b(preferred|preferably|nice to have|a plus|bonus|desirable|ideally|"
    r"would be great|not required|optional)\b", re.I
)

YEARS_RE = re.compile(
    r"(\d{1,2})\s*(?:\+|plus)?\s*(?:-|to|–)?\s*(\d{1,2})?\s*\+?\s*(?:years?|yrs?)\b", re.I
)

DEGREE_RE = re.compile(
    r"\b(ph\.?d|doctorate|master'?s?|m\.?s\.?c?\b|m\.?b\.?a|bachelor'?s?|b\.?s\.?c?\b|"
    r"b\.?a\b|associate'?s?|high school diploma|ged)\b", re.I
)

CLEARANCE_RE = re.compile(
    r"\b(top secret/sci|ts/sci|top secret|secret clearance|security clearance|"
    r"public trust|poly(?:graph)?|dod\s*8570|8140)\b", re.I
)

# Terms that look important statistically but are pure posting boilerplate.
BOILERPLATE = frozenset("""
401k 401 k pto health dental vision insurance equity stock options bonus salary
compensation benefits perks holiday vacation remote hybrid onsite office
opportunity employer veteran disability gender race religion orientation
identity applicants qualified consideration background check drug screen
resume cover letter interview hiring recruiter application applicants apply
click submit posting requisition full time part time contract w2 c2c
""".split())


@dataclass
class Requirement:
    """One mined term with the evidence that set its weight."""

    term: str                       # surface form as written in the posting
    canonical_term: str             # alias-resolved id (falls back to term)
    weight: float = 1.0
    count: int = 0
    required: bool = False
    preferred: bool = False
    known_skill: bool = False
    category: str = "keyword"
    contexts: List[str] = field(default_factory=list)

    @property
    def display(self) -> str:
        return self.term


@dataclass
class HardRequirement:
    """A gating condition -- the kind a Workday knockout question enforces."""

    kind: str          # years | degree | clearance | certification
    detail: str
    value: Optional[float] = None
    context: str = ""


@dataclass
class JobDescription:
    text: str
    title: str = ""
    requirements: List[Requirement] = field(default_factory=list)
    hard_requirements: List[HardRequirement] = field(default_factory=list)
    responsibility_lines: List[str] = field(default_factory=list)
    requirement_lines: List[str] = field(default_factory=list)
    min_years: Optional[float] = None
    min_degree: Optional[str] = None
    clearance: Optional[str] = None
    blocks: List[Tuple[str, str, str]] = field(default_factory=list)  # (heading, kind, text)

    def top(self, n: int = 30) -> List[Requirement]:
        return sorted(self.requirements, key=lambda r: -r.weight)[:n]

    @property
    def signal_text(self) -> str:
        """JD text with boilerplate blocks removed."""
        return "\n".join(t for _, kind, t in self.blocks if kind != "noise")


DEGREE_RANK = {
    "ged": 1, "high school diploma": 1, "associate": 2, "associates": 2,
    "bachelor": 3, "bachelors": 3, "bs": 3, "ba": 3, "bsc": 3,
    "master": 4, "masters": 4, "ms": 4, "msc": 4, "mba": 4,
    "phd": 5, "doctorate": 5,
}


def degree_rank(text: str) -> int:
    t = normalize(text).replace(".", "").replace("'", "")
    best = 0
    for name, rank in DEGREE_RANK.items():
        if re.search(r"\b" + re.escape(name) + r"\b", t):
            best = max(best, rank)
    return best


def _classify_heading(line: str) -> Optional[str]:
    """Map a JD heading to noise / required / preferred / responsibility."""
    h = normalize(line).strip().strip(":*#-–—• \t")
    h = re.sub(r"\s+", " ", h)
    if not h or len(h) > 70:
        return None
    for name in NOISE_SECTIONS:
        if h.startswith(name):
            return "noise"
    for name in PREFERRED_SECTIONS:
        if h.startswith(name):
            return "preferred"
    for name in REQUIRED_SECTIONS:
        if h.startswith(name):
            return "required"
    for name in RESPONSIBILITY_SECTIONS:
        if h.startswith(name):
            return "responsibility"
    return None


def _looks_like_heading(line: str) -> bool:
    """A heading is short, standalone and not a bullet.

    Casing is deliberately *not* required: real postings write
    "Minimum Qualifications" in title case far more often than in caps, and an
    earlier version that demanded uppercase silently classified every posting
    as one undifferentiated block.
    """
    s = line.strip()
    if not s or len(s) > 70 or is_bullet(line):
        return False
    if len(s.split()) > 8:
        return False
    return not s.endswith((".", ",", ";"))


def split_blocks(text: str) -> List[Tuple[str, str, str]]:
    """Segment the posting into (heading, kind, body) blocks."""
    blocks: List[Tuple[str, str, List[str]]] = []
    heading, kind, buf = "", "body", []
    for raw in text.splitlines():
        candidate = _classify_heading(raw) if _looks_like_heading(raw) else None
        if candidate:
            if buf:
                blocks.append((heading, kind, buf))
            heading, kind, buf = raw.strip(), candidate, []
            continue
        buf.append(raw)
    if buf:
        blocks.append((heading, kind, buf))
    return [(h, k, "\n".join(b).strip()) for h, k, b in blocks]


def extract_title(text: str) -> str:
    """Guess the requisition title from the first meaningful line."""
    for raw in text.splitlines()[:12]:
        line = raw.strip().strip("#*_ ")
        if not line or len(line) > 90:
            continue
        low = normalize(line)
        if low.startswith(("job title", "title", "position", "role")):
            part = re.split(r"[:\-–]", line, maxsplit=1)
            if len(part) == 2 and part[1].strip():
                return part[1].strip()
            continue
        if any(low.startswith(n) for n in ("about", "we are", "our ", "company")):
            continue
        if len(line.split()) <= 12 and not line.endswith("."):
            return line
    return ""


def _find_hard_requirements(text: str, blocks: Sequence[Tuple[str, str, str]]) -> List[HardRequirement]:
    hard: List[HardRequirement] = []
    for heading, kind, body in blocks:
        if kind in ("noise", "preferred"):
            continue
        for raw in body.splitlines():
            line = raw.strip()
            if not line:
                continue
            is_preferred_line = bool(NICE_MARKERS.search(line))
            if is_preferred_line:
                continue

            m = YEARS_RE.search(line)
            if m and re.search(r"experience|background|working", line, re.I):
                lo = float(m.group(1))
                hard.append(HardRequirement("years", f"{m.group(0).strip()}", lo, line.strip()))

            if DEGREE_RE.search(line) and re.search(r"degree|diploma|bachelor|master|phd|ged", line, re.I):
                hard.append(HardRequirement("degree", DEGREE_RE.search(line).group(0), float(degree_rank(line)), line.strip()))

            c = CLEARANCE_RE.search(line)
            if c:
                hard.append(HardRequirement("clearance", c.group(0), None, line.strip()))
    return hard


def _mine_terms(
    blocks: Sequence[Tuple[str, str, str]], lexicon: SkillLexicon
) -> Dict[str, Requirement]:
    """Score candidate phrases by where and how they appear in the posting."""
    found: Dict[str, Requirement] = {}
    doc_freq: Counter = Counter()

    for heading, kind, body in blocks:
        if kind == "noise":
            continue
        base = {"required": 1.7, "preferred": 0.55, "responsibility": 1.15}.get(kind, 1.0)
        for raw in body.splitlines():
            line = strip_bullet(raw).strip() if is_bullet(raw) else raw.strip()
            if not line or len(line) < 3:
                continue
            line_weight = base
            if MUST_MARKERS.search(line):
                line_weight *= 1.45
            if NICE_MARKERS.search(line):
                line_weight *= 0.45

            seen_in_line = set()
            # Up to five raw tokens: a four-word skill containing a glue word
            # ("security information and event management") needs five, and the
            # candidate filter below rejects any long phrase the lexicon does
            # not vouch for, so the extra length costs no precision.
            for phrase in phrase_ngrams(line, 1, 5):
                key = canonical(phrase)
                if not key or key in seen_in_line:
                    continue
                if not _is_candidate(phrase, key, lexicon):
                    continue
                seen_in_line.add(key)
                doc_freq[key] += 1

                resolved = lexicon.resolve(phrase)
                known = resolved is not None
                cid = resolved or key
                req = found.get(cid)
                if req is None:
                    req = Requirement(
                        term=phrase,
                        canonical_term=cid,
                        weight=0.0,
                        known_skill=known,
                        category=lexicon.category(resolved) if resolved else "keyword",
                    )
                    found[cid] = req
                elif known and len(phrase) > len(req.term) and not req.known_skill:
                    req.term = phrase
                # Prefer the longer, more specific surface form for display.
                if len(phrase.split()) > len(req.term.split()) and known == req.known_skill:
                    req.term = phrase

                req.count += 1
                req.weight += line_weight * (1.0 + 0.35 * (len(phrase.split()) - 1))
                if known:
                    req.known_skill = True
                if kind == "required" or MUST_MARKERS.search(line):
                    req.required = True
                if kind == "preferred" or NICE_MARKERS.search(line):
                    req.preferred = True
                if len(req.contexts) < 3:
                    req.contexts.append(line.strip()[:200])

    _suppress_subsumed(found)

    # Dampen raw frequency and reward the curated lexicon, which is far higher
    # precision than any statistic we can compute from one document.
    for req in found.values():
        req.weight = req.weight * (1.0 + math.log1p(req.count) * 0.25)
        if req.known_skill:
            req.weight *= 1.6
        elif len(req.term.split()) >= 3:
            # An unvouched 3-word phrase is more often a sentence fragment
            # ("tracking remediation slas") than a skill, so it should not
            # outrank real skills in the gap list.
            req.weight *= 0.55
        if req.required and not req.preferred:
            req.weight *= 1.15
        if req.preferred and not req.required:
            req.weight *= 0.7
    return found


# Generic container nouns.  A phrase ending in one is a wrapper around the real
# skill ("SIEM platforms" -> "SIEM"), and reporting both as separate gaps is
# noise, so phrases are trimmed to the skill itself.
CONTAINER_NOUNS = frozenset("""
platform platforms tool tools tooling solution solutions technology technologies
product products service services vendor vendors system systems suite suites
environment environments capability capabilities activity activities
initiative initiatives effort efforts team teams stack stacks offering offerings
""".split())

# Words that describe *how much* of a skill is wanted, not the skill itself.
# Letting these into an n-gram produces junk like "siem platforms required"
# and "minimum of 4", which are useless as resume keywords.
REQUIREMENT_LANGUAGE = frozenset("""
required require requires requirement requirements minimum min must mandatory
preferred prefer preferably desired desirable essential plus bonus optional
experience experienced knowledge understanding familiarity familiar expertise
proficiency proficient demonstrated proven hands-on hands on strong solid
excellent deep broad extensive significant relevant related equivalent
ability able capable skills skill background exposure track record years year
degree qualification qualifications comfortable passion passionate willingness
bachelor bachelors master masters phd doctorate associate associates diploma ged
""".split())

def _suppress_subsumed(found: Dict[str, Requirement]) -> None:
    """Drop fragments that only ever appeared inside a stronger known skill.

    Mining n-grams of length 1-4 yields "security operations", "operations
    center" and "operations" alongside "security operations center".  Reporting
    all four as separate gaps triples the apparent work and buries the real one.
    A fragment is removed only when it never occurs more often than the parent,
    which preserves terms that genuinely stand alone elsewhere in the posting.
    """
    anchors = sorted(
        (r for r in found.values() if len(r.term.split()) > 1),
        key=lambda r: (-r.known_skill, -len(r.term)),
    )
    for anchor in anchors:
        parent = " " + anchor.term + " "
        for cid, req in list(found.items()):
            if req is anchor or req.known_skill or cid not in found:
                continue
            if len(req.term) >= len(anchor.term):
                continue
            if (" " + req.term + " ") in parent and req.count <= anchor.count:
                found.pop(cid, None)


_ALLOWED_SHORT = frozenset({
    "ai", "ml", "qa", "ci", "cd", "go", "r", "c", "aws", "gcp", "sql", "api",
    "ir", "ad", "iam", "pam", "dlp", "edr", "xdr", "mdr", "siem", "soc", "grc",
    "pki", "sso", "mfa", "waf", "vpn", "dns", "tcp", "ssl", "tls", "sox", "pci",
})


def _is_candidate(phrase: str, key: str, lexicon: Optional[SkillLexicon] = None) -> bool:
    """Filter obvious non-skills before they reach the scorer."""
    if not key or len(key) < 2:
        return False
    # A phrase containing a glue word is only meaningful if it is a real
    # multi-word skill ("identity and access management").  Otherwise it is a
    # fragment spanning a conjunction ("csf and iso").
    if any(w in STOPWORDS for w in phrase.split()):
        if lexicon is None or lexicon.resolve(phrase) is None:
            return False
    words = phrase.split()
    if any(w in BOILERPLATE for w in words):
        return False
    if any(w in REQUIREMENT_LANGUAGE for w in words):
        return False
    if len(words) == 1:
        w = words[0]
        if w in STOPWORDS:
            return False
        if w.isdigit():
            return False
        if len(w) <= 2 and w not in _ALLOWED_SHORT:
            return False
        # Bare verbs and vague nouns add noise as single tokens; they still
        # count inside longer phrases.
        if w in {"experience", "knowledge", "understanding", "ability", "skills",
                 "strong", "excellent", "years", "work", "working", "team",
                 "environment", "including", "related", "field", "level",
                 "support", "using", "use", "new", "well", "etc"}:
            return False
    if all(w.isdigit() or len(w) <= 2 for w in words):
        return False
    # Stray single letters come from possessives ("bachelor's" -> "bachelor s").
    if any(len(w) == 1 and not w.isdigit() for w in words):
        return False
    # Long n-grams are almost always sentence fragments unless the lexicon
    # vouches for them as a real multi-word skill.
    if len(words) >= 4 and (lexicon is None or lexicon.resolve(phrase) is None):
        return False
    if len(words) > 1 and words[-1] in CONTAINER_NOUNS:
        return False
    if len(words) == 1 and words[0] in CONTAINER_NOUNS:
        return False
    return True


def parse(text: str, lexicon: Optional[SkillLexicon] = None) -> JobDescription:
    lexicon = lexicon or default_lexicon()
    blocks = split_blocks(text)
    jd = JobDescription(text=text, blocks=blocks, title=extract_title(text))

    jd.requirements = list(_mine_terms(blocks, lexicon).values())
    jd.hard_requirements = _find_hard_requirements(text, blocks)

    years = [h.value for h in jd.hard_requirements if h.kind == "years" and h.value]
    jd.min_years = min(years) if years else None
    degrees = [h.value for h in jd.hard_requirements if h.kind == "degree" and h.value]
    jd.min_degree = None
    if degrees:
        rank = int(min(degrees))
        jd.min_degree = next((k for k, v in DEGREE_RANK.items() if v == rank), None)
    clearances = [h.detail for h in jd.hard_requirements if h.kind == "clearance"]
    jd.clearance = clearances[0] if clearances else None

    for heading, kind, body in blocks:
        target = None
        if kind == "responsibility":
            target = jd.responsibility_lines
        elif kind in ("required", "preferred"):
            target = jd.requirement_lines
        if target is None:
            continue
        for raw in body.splitlines():
            line = strip_bullet(raw).strip() if is_bullet(raw) else raw.strip()
            if len(line) > 25:
                target.append(line)

    return jd
