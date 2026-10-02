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
from typing import Dict, List, Optional, Sequence, Set, Tuple

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

# Professional licences a posting can require outright. In healthcare they are
# the commonest knockout question there is -- "RN license required" -- and a
# resume without one is screened out before a single keyword is weighed, so a
# score that ignored them rated an IT sales executive at 75 against a hospice
# role he could not legally hold. Each name maps to the forms a resume writes.
LICENSES = {
    "registered nurse": ["rn", "r.n.", "rn license", "rn licensure", "registered nurse license",
                         "bsn, rn", "msn, rn", "registered nurse (rn)"],
    "licensed practical nurse": ["lpn", "lvn", "licensed vocational nurse"],
    "nurse practitioner": ["np", "aprn", "advanced practice registered nurse", "fnp", "fnp-c"],
    "physician assistant": ["pa-c", "physician associate"],
    "physical therapist": ["dpt", "pt license", "licensed physical therapist"],
    "occupational therapist": ["otr", "otr/l", "licensed occupational therapist"],
    "respiratory therapist": ["rrt", "crt"],
    "registered dietitian": ["rd", "rdn"],
    "licensed clinical social worker": ["lcsw", "lmsw", "licensed social worker"],
    "certified nursing assistant": ["cna"],
    "pharmacist": ["pharmd", "rph", "licensed pharmacist"],
    "physician": ["md", "do", "medical license", "licensed physician", "board certified"],
    "certified public accountant": ["cpa", "cpa license"],
    "professional engineer": ["pe license", "p.e.", "licensed professional engineer"],
    "commercial driver's license": ["cdl", "class a cdl", "class b cdl", "cdl-a"],
    "bar admission": ["admitted to the bar", "licensed attorney", "state bar", "juris doctor", "j.d."],
    "real estate license": ["licensed realtor", "real estate salesperson license"],
    "series 7": ["finra series 7", "series 7 license"],
    "series 63": ["finra series 63"],
    "insurance license": ["licensed insurance agent", "property and casualty license", "life and health license"],
}

# How a posting says a licence is required: the licence, near a word that makes
# it a condition. "RN preferred" is a keyword; "must hold an active RN license"
# is a gate.
_LICENSE_NAME_RE = re.compile(
    r"\b(registered nurse|licensed practical nurse|licensed vocational nurse|nurse practitioner|"
    r"physician assistant|physical therapist|occupational therapist|respiratory therapist|"
    r"registered dietitian|licensed clinical social worker|certified nursing assistant|"
    r"pharmacist|physician|certified public accountant|professional engineer|"
    r"commercial driver'?s? licen[sc]e|bar admission|admitted to the bar|licensed attorney|"
    r"real estate licen[sc]e|series 7|series 63|insurance licen[sc]e|"
    r"rn|lpn|lvn|aprn|cna|cpa|cdl|rrt|lcsw|pharmd|dpt)\b", re.I)
_LICENSE_CONDITION_RE = re.compile(
    r"\b(licen[sc]e[ds]?|licensure|must (?:be|hold|have|possess)|required|active|current|"
    r"valid|unrestricted|in good standing|registered)\b", re.I)

_LICENSE_ALIAS_TO_NAME = {}
for _name, _alts in LICENSES.items():
    _LICENSE_ALIAS_TO_NAME[_name] = _name
    for _a in _alts:
        _LICENSE_ALIAS_TO_NAME[_a] = _name


def license_required(line: str) -> Optional[str]:
    """The licence a line makes a condition of the job, or None."""
    m = _LICENSE_NAME_RE.search(line)
    if not m or not _LICENSE_CONDITION_RE.search(line):
        return None
    if NICE_MARKERS.search(line) and not re.search(r"(?<!not )\brequired\b|\bmust\b", line, re.I):
        return None
    found = m.group(1).lower().replace("licence", "license")
    found = re.sub(r"'?s? licen[sc]e$", "'s license", found) if "driver" in found else found
    for name, alts in LICENSES.items():
        if found == name or found in alts:
            return name
    for name in LICENSES:
        if found in name:
            return name
    return found


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
    proper: bool = False            # written as a proper term (Title Case / acronym)
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
    company_tokens: Set[str] = field(default_factory=set)

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


# Words that appear in section headings, never in an employer's name.
_SECTION_VOCAB = frozenset(
    w for name in (NOISE_SECTIONS + REQUIRED_SECTIONS + PREFERRED_SECTIONS
                   + RESPONSIBILITY_SECTIONS)
    for w in name.split()
) | {"overview", "summary", "description", "position", "job", "posting"}

_COMPANY_PATTERNS = (
    re.compile(r"^\s*([A-Z][\w&.\-]*(?:\s+[A-Z][\w&.\-]*){0,3})\s*[-\u2013\u2014|]\s*\S", re.M),
    re.compile(r"\b(?:About|Join|At)\s+([A-Z][\w&.\-]*(?:\s+[A-Z][\w&.\-]*){0,2})\b"),
    re.compile(r"\b([A-Z][\w&.\-]*(?:\s+[A-Z][\w&.\-]*){0,2})\s+is\s+(?:a|an|the|part of)\b"),
)


def company_tokens(text: str, lexicon: Optional[SkillLexicon] = None) -> Set[str]:
    """Words that name the hiring employer rather than a requirement.

    A posting repeats its own company name, and the miner was counting it as a
    required keyword -- "accenture" and "five9" were among the heaviest missing
    terms against those postings. Nobody can put the hiring company's name on
    their resume, so every occurrence padded the denominator and understated
    coverage on exactly the postings that scored worst.

    A token is never excluded if the lexicon knows it as a skill, so an
    employer called Oracle or Splunk does not blind the miner to the product.
    """
    # The employer is named at the very top; scanning further down starts
    # catching section headings ("Key Responsibilities") instead.
    head = "\n".join(text.splitlines()[:3])
    found: Set[str] = set()
    for i, pattern in enumerate(_COMPANY_PATTERNS):
        scope = head if i == 0 else "\n".join(text.splitlines()[:12])
        for match in pattern.finditer(scope):
            for word in match.group(1).split():
                token = normalize(word).strip(".,&-")
                if len(token) < 3 or token in STOPWORDS or token in VAGUE_SINGLES:
                    continue
                if token in _SECTION_VOCAB:
                    continue
                # Never blind the miner to a product because the employer
                # shares its name.
                if lexicon is not None and lexicon.resolve(token):
                    continue
                found.add(token)
    return found


_CITY_STATE_RE = re.compile(r"\b([A-Z][A-Za-z.]+(?:\s+[A-Z][A-Za-z.]+){0,2}),\s*([A-Z]{2}|[A-Z][a-z]+)\b")
_RESIDENCY_LINE_RE = re.compile(
    r"\b(living|reside|residing|based|located|relocat\w*|commut\w*|territor(?:y|ies))\b|\barea\b", re.I)
_REPORTING_CLAUSE_RE = re.compile(
    r"\breport(?:s|ing)?\s+(?:directly\s+)?(?:in\s+)?to\s+(?:the\s+)?[^,.;:()]+", re.I)


def location_tokens(text: str) -> Set[str]:
    """Words that name where the job is, not what it needs.

    "Dallas" and "DFW" were being reported as missing keywords. A place name
    is read from "City, ST" in the header or a Location line, and from any
    capitalised word on a line about where the person must live.
    """
    found: Set[str] = set()
    lines = text.splitlines()
    scopes = lines[:5] + [ln for ln in lines if _METADATA_LINE_RE.match(ln)
                          or _RESIDENCY_LINE_RE.search(ln)]
    for raw in scopes:
        for m in _CITY_STATE_RE.finditer(raw):
            for word in m.group(1).split():
                found.add(normalize(word).strip(".,"))
        if _RESIDENCY_LINE_RE.search(raw) or _METADATA_LINE_RE.match(raw):
            for word in re.findall(r"\b[A-Z][A-Za-z]{1,}\b", raw):
                low = normalize(word)
                if low in STOPWORDS or low in VAGUE_SINGLES or len(low) < 3:
                    continue
                if raw.strip().startswith(word):      # a sentence's first word
                    continue
                if word.isupper() or word.istitle():
                    found.add(low)
    return {t for t in found if t not in _SECTION_VOCAB}


def _classify_heading(line: str) -> Optional[str]:
    """Map a JD heading to noise / required / preferred / responsibility."""
    h = normalize(line).strip().strip(":*#-–—• \t")
    h = re.sub(r"\s+", " ", h)
    if not h or len(h) > 70:
        return None
    kind = _match_heading_lists(h)
    if kind is None:
        # "Job Responsibilities", "Key Qualifications", "Core Requirements".
        stripped = re.sub(r"^(?:job|key|core|primary|main|position|role|your|the|our|general)\s+", "", h)
        if stripped != h:
            kind = _match_heading_lists(stripped)
    return kind


def _match_heading_lists(h: str) -> Optional[str]:
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
            if _METADATA_LINE_RE.match(line):
                continue
            nice = NICE_MARKERS.search(line)
            m = YEARS_RE.search(line)
            # "10+ years of leadership experience, hospice experience strongly
            # preferred": the preference qualifies the clause after it, not
            # the minimum before it. Skipping the whole line lost the
            # ten-year requirement and capped every candidate's experience
            # score at 85%.
            if nice and (m is None or nice.start() < m.start()):
                continue
            if m and re.search(r"experience|background|working", line, re.I):
                lo = float(m.group(1))
                hard.append(HardRequirement("years", f"{m.group(0).strip()}", lo, line.strip()))

            if nice:
                continue
            if DEGREE_RE.search(line) and re.search(r"degree|diploma|bachelor|master|phd|ged", line, re.I):
                hard.append(HardRequirement("degree", DEGREE_RE.search(line).group(0), float(degree_rank(line)), line.strip()))

            c = CLEARANCE_RE.search(line)
            if c:
                hard.append(HardRequirement("clearance", c.group(0), None, line.strip()))

            lic = license_required(line)
            if lic and (kind == "required" or MUST_MARKERS.search(line)
                        or re.search(r"\brequired\b", line, re.I)):
                hard.append(HardRequirement("license", lic, None, line.strip()))
    return hard


def _mine_terms(
    blocks: Sequence[Tuple[str, str, str]],
    lexicon: SkillLexicon,
    exclude: Optional[Set[str]] = None,
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
            if _METADATA_LINE_RE.match(line):
                continue
            # "Reporting to the SVP & General Manager, this leader..." names
            # a manager, not a skill. The clause goes; the sentence stays.
            line = _REPORTING_CLAUSE_RE.sub(" ", line)
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
                proper = len(phrase.split()) > 1 and _is_proper(phrase, line)
                if not _is_candidate(phrase, key, lexicon, proper=proper):
                    continue
                if exclude and any(w in exclude for w in phrase.split()):
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
                        proper=proper,
                        category=lexicon.category(resolved) if resolved else "keyword",
                    )
                    found[cid] = req
                elif known and len(phrase) > len(req.term) and not req.known_skill:
                    req.term = phrase
                if proper:
                    req.proper = True
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

    # A three-word phrase the posting used once, that neither the lexicon nor
    # the author's capitalisation vouches for, is a sentence fragment
    # ("trusted thought partner", "execute operational strategy").
    for cid in [c for c, r in found.items()
                if len(r.term.split()) >= 3 and r.count < 2
                and not r.known_skill and not r.proper]:
        del found[cid]

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


# Verb forms that begin or end a mid-sentence fragment. A phrase hinged on one
# of these ("leading global procurement", "success building") is a slice of a
# sentence, not a skill. Nouns that merely end in -ing -- engineering,
# consulting, marketing, planning, training -- are deliberately absent.
GERUND_HINGES = frozenset("""
leading building driving managing developing creating ensuring supporting
delivering providing working using including scaling commercializing defining
establishing identifying partnering collaborating monitoring representing
fostering sponsoring guiding advising enabling executing owning translating
maintaining leveraging aligning shaping growing serving
""".split())

# Modifier suffixes. "AI-enabled", "market-leading" and "executive-level"
# qualify a skill; alone they are adjectives, and reporting one as a missing
# keyword tells a candidate to add a word rather than a capability.
MODIFIER_SUFFIXES = ("-enabled", "-led", "-driven", "-based", "-level", "-leading",
                     "-focused", "-oriented", "-facing", "-ready", "-centric",
                     "-native", "-first", "-wide", "-critical", "-grade")

# Generic business nouns a posting uses to frame a requirement rather than to
# name one. Every one of these was reported as a missing keyword against a real
# posting, where "add the word firm to your resume" is worse than useless: it
# pads the denominator and understates how well the resume actually covers the
# job.
VAGUE_SINGLES = frozenset("""
experience knowledge understanding ability skills strong excellent years work
working team environment including related field level support using use new
well etc firm practice industry industries provider providers network networks
communication communications define scaling global market markets business
organization organizations company companies client clients customer customers
stakeholder stakeholders leader leaders analyst analysts executive executives
professional professionals priorities priority objectives outcomes initiatives
reviews review resources growth success excellence innovation insights trends
vision culture impact opportunities opportunity engagements solutions offerings
methodologies frameworks practices approaches capabilities
serves serve define defines drive drives lead leads own owns build builds
deliver delivers ensure ensures supports manage manages develop develops
create creates execute executes execution monitor monitors represent
represents identify identifies collaborate partner partners translate foster
sponsor guide advise enable maintain leverage align shape grow pipeline
important defining generation operating thought asset assets spanning adoption
questions roadmaps launches workflow launch coverage areas area role roles
job jobs multiple reflect trusted changes change decision decisions mission
missions staff needed choice choices home value values strongly key member
members regular regularly direct directly consistently exceptional timely
overall across within throughout continuous ongoing trust consistency state
region travel proactively acumen license licence licensure licensed
""".split())

# A posting's metadata lines name the reporting line, the office and the
# schedule, not a capability. Mining them put "svp", "general manager",
# "dallas" and "reports" among the heaviest missing keywords, and no resume
# can be written to contain its future manager's title.
_METADATA_LINE_RE = re.compile(
    r"^\s*(?:job\s+)?(?:title|position|location|locations|reports?\s+to|reporting\s+to|"
    r"department|division|travel|schedule|shift|hours|job\s+type|employment\s+type|"
    r"salary|pay|compensation|posted|requisition|req\s*id|job\s*id|work\s+arrangement)"
    r"\s*(?:/\s*\w+\s*)?[:\-\u2013]", re.I)

# Where the person has to live is a condition of the job, not a skill the
# resume can evidence. "DFW area" was being reported as a required keyword.
_RESIDENCY_WORDS = frozenset("""
area living residing reside relocate relocation relocating commute commutable
commuting locally onsite on-site in-office in-person
""".split())

# Gerunds that have become the name of a discipline. Everything else ending
# in -ing is a verb caught mid-sentence ("providing", "ensuring", "aligning")
# and names nothing a resume could be asked to contain.
_NOMINAL_GERUNDS = frozenset("""
planning training reporting forecasting budgeting consulting auditing mentoring
coaching staffing scheduling recruiting onboarding testing engineering marketing
accounting purchasing sourcing licensing nursing modeling modelling pricing
billing coding programming networking manufacturing underwriting contracting
outsourcing benchmarking screening credentialing learning monitoring
positioning advertising merchandising publishing counseling counselling
fundraising prospecting selling closing messaging branding
""".split())

# Verbs a posting uses to introduce a duty. A phrase that opens on one of
# these ("ensures agency", "drive performance", "guide agencies") is a slice
# of a sentence; a phrase that ends on one ("care consistently reflect") is
# the slice before the object. Neither is a keyword.
_JD_VERBS = frozenset("""
ensure provide drive guide deliver improve reduce strengthen support execute
advise scale conduct implement monitor develop assess help succeed lead build
partner work foster champion equip reinforce introduce standardize standardise
serve align reflect maintain manage oversee coordinate collaborate communicate
create define design establish evaluate identify influence leverage optimize
optimise own perform plan prepare prioritize prioritise promote recommend
represent resolve review shape translate utilize utilise track train understand
analyze analyse achieve assist demonstrate enable engage facilitate generate
participate contribute cultivate empower inspire motivate mentor coach
negotiate present report respond handle operate organize organise
""".split())

def _verb_forms(bare: frozenset) -> frozenset:
    out = set()
    for v in bare:
        out.add(v)
        out.add(v + "es" if v.endswith(("s", "sh", "ch", "x", "z")) else v + "s")
        if v.endswith("e") and not v.endswith("ee"):
            out.add(v[:-1] + "ing")
        else:
            out.add(v + "ing")
    return frozenset(out)

_VERB_FORMS = _verb_forms(_JD_VERBS)

# Nouns that are also verbs. "corrective action plans" ends on one and is a
# real term, so the end-of-phrase verb rule skips these.
_NOUN_VERB_HOMOGRAPHS = frozenset("""
plans reports reviews supports controls designs releases updates audits
schedules forecasts budgets changes needs contacts documents estimates
measures offers orders places projects records requests results returns
uses values works benefits impacts interfaces links partners pilots positions
presents programs purchases services structures targets transfers trends
drives leads focus
""".split())

# A phrase that trails off into a modifier is cut before its noun.
_TRAILING_MODIFIERS = frozenset("""
exceptional timely consistent appropriate operational strategic effective
efficient successful high strong multiple various regular key new additional
ongoing overall direct indirect proactive proactively broad deep full
""".split())


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


def _is_proper(phrase: str, raw_line: str) -> bool:
    """True if the posting wrote the phrase as a proper term.

    "CMS Conditions of Participation" and "Microsoft Sentinel" are written in
    Title Case or carry an acronym; "decisions support exceptional" is not.
    The capitalisation the author chose is the cheapest reliable signal that
    an n-gram is a name rather than a slice of a sentence.
    """
    m = re.search(r"\b" + r"\W+".join(re.escape(w) for w in phrase.split()) + r"\b",
                  raw_line, re.I)
    if not m:
        return False
    # A short line written entirely in Title Case is one of the posting's own
    # sub-headings ("Performance Management & Continuous Improvement"). The
    # author capitalised a heading, so capitals there vouch for nothing.
    line_words = re.findall(r"[A-Za-z][A-Za-z&.+#/-]*", raw_line)
    if len(line_words) <= 8 and all(w[:1].isupper() for w in line_words if len(w) >= 4):
        return False
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z&.+#/-]*", m.group(0))]
    if not words:
        return False
    # The first word of a line or sentence is capitalised anyway; it is only
    # evidence when something after it is capitalised too.
    at_start = m.start() == 0 or raw_line[:m.start()].rstrip().endswith((".", ":", "-", "\u2022"))
    judged = words[1:] if at_start and len(words) > 1 else words
    judged = [w for w in judged if w.lower() not in STOPWORDS]
    if not judged:
        return False
    if any(len(w) >= 2 and w.isupper() for w in judged):
        return True
    return all(w[:1].isupper() for w in judged)


def _is_candidate(phrase: str, key: str, lexicon: Optional[SkillLexicon] = None,
                  proper: bool = False) -> bool:
    """Filter obvious non-skills before they reach the scorer.

    ``proper`` says the posting wrote the phrase as a proper term, which earns
    a long phrase the benefit of the doubt the lexicon would otherwise give.
    """
    if not key or len(key) < 2:
        return False
    # A phrase containing a glue word is only meaningful if it is a real
    # multi-word skill ("identity and access management").  Otherwise it is a
    # fragment spanning a conjunction ("csf and iso").
    words = phrase.split()
    if any(w in STOPWORDS for w in words):
        coordinated = any(w in ("and", "or") for w in words)
        if (lexicon is None or lexicon.resolve(phrase) is None) and (coordinated or not proper):
            return False
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
        if w in VAGUE_SINGLES:
            return False
        if w.endswith(MODIFIER_SUFFIXES):
            return False
    if all(w.isdigit() or len(w) <= 2 for w in words):
        return False
    # "15+" is a quantity, not a keyword.
    if words and all(w.rstrip("+-").isdigit() for w in words):
        return False
    # A phrase hinged on a bare verb form is a slice of a sentence.
    if len(words) > 1 and (words[0] in GERUND_HINGES or words[-1] in GERUND_HINGES):
        if lexicon is None or lexicon.resolve(phrase) is None:
            return False
    # A phrase made entirely of generic words names nothing: "business growth"
    # and "practice priorities" are framing, not capabilities.
    if len(words) > 1 and all(w in VAGUE_SINGLES for w in words):
        if lexicon is None or lexicon.resolve(phrase) is None:
            return False
    # Stray single letters come from possessives ("bachelor's" -> "bachelor s").
    if any(len(w) == 1 and not w.isdigit() for w in words):
        return False
    vouched = lexicon is not None and lexicon.resolve(phrase) is not None
    # Long n-grams are almost always sentence fragments unless the lexicon
    # vouches for them, or the posting itself wrote them as a proper term.
    if len(words) >= 4 and not vouched and not proper:
        return False
    if len(words) > 1 and words[-1] in CONTAINER_NOUNS:
        return False
    if len(words) == 1 and words[0] in CONTAINER_NOUNS:
        return False
    if vouched:
        return True

    # Everything below removes slices of sentences that no resume could be
    # asked to contain. Each class was measured against a real posting, where
    # together they made up over a third of the keyword weight -- a ceiling
    # that no honest resume could reach.
    if any(w in _RESIDENCY_WORDS for w in words):
        return False                                  # "dfw area"
    first, last = words[0], words[-1]
    if len(words) == 1:
        if first.endswith("ing") and first not in _NOMINAL_GERUNDS:
            return False                              # "providing"
        if first in _VERB_FORMS and first not in _NOMINAL_GERUNDS:
            return False                              # "reflect", "assess"
        if first.endswith("ed") and len(first) > 4 and not proper:
            return False                              # "resourced", "needed"
        if first.endswith("ly") and len(first) > 4:
            return False                              # "proactively"
        return True
    if first in _VERB_FORMS or (first.endswith("ing") and first not in _NOMINAL_GERUNDS):
        return False                                  # "ensures agency"
    if first in _TRAILING_MODIFIERS or (first.endswith("ly") and len(first) > 4):
        return False                                  # "exceptional patient", "appropriately staffed"
    if (last in _VERB_FORMS and last not in _NOUN_VERB_HOMOGRAPHS
            and last not in _NOMINAL_GERUNDS and not last.endswith("ing")):
        return False                                  # "care consistently reflect", "decision reflects"
    if last.endswith("ly") or last in _TRAILING_MODIFIERS:
        return False                                  # "travel regularly", "provide operational"
    if last.endswith("ing") and last not in _NOMINAL_GERUNDS:
        return False                                  # "registered nurse living"
    return True


def parse(text: str, lexicon: Optional[SkillLexicon] = None) -> JobDescription:
    lexicon = lexicon or default_lexicon()
    blocks = split_blocks(text)
    jd = JobDescription(text=text, blocks=blocks, title=extract_title(text))

    # A company name can contain a common noun ("WNS Global Services"). If the
    # word also recurs through the requirements it is doing double duty as a
    # real term, and excluding it would lose a genuine keyword.
    candidates = company_tokens(text, lexicon)
    body = normalize("\n".join(t for _, kind, t in blocks if kind in ("required", "responsibility")))
    places = {t for t in location_tokens(text)
              if lexicon.resolve(t) is None
              and len(re.findall(r"\b" + re.escape(t) + r"\b", body)) < 3}
    jd.company_tokens = {
        token for token in candidates
        if len(re.findall(r"\b" + re.escape(token) + r"\b", body)) < 3
    }
    jd.requirements = list(_mine_terms(blocks, lexicon, jd.company_tokens | places).values())
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
