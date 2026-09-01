"""Composite scoring.

The weighting reflects how applications actually fail, not how they feel like
they fail.  Parse quality carries a large share because a resume that does not
parse cannot score at all downstream, and hard requirements act as a *gate*
rather than a weight because that is how knockout questions and boolean filters
behave: no amount of keyword coverage compensates for a missing mandatory
credential.

Every number produced here is an estimate from the resume and posting text
alone.  No employer publishes their real thresholds, and vendors differ, so
these scores are for comparing drafts of your own resume against one posting --
not a prediction of any specific system's verdict.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .aliases import SkillLexicon, default_lexicon
from .extract import Document
from .jd import JobDescription, HardRequirement, degree_rank
from .match import (
    MatchResult, ResumeIndex, TermMatch, bm25, contextual_coverage, match_requirements,
)
from .parseability import ParseAudit, audit as parse_audit
from .resume import EMAIL_RE, METRIC_RE, PHONE_RE, URL_RE, Resume, opener_strength
from .text import repair_layout, stems, tokenize

# Component weights, summing to 100.
WEIGHTS: Dict[str, float] = {
    "parseability": 22.0,   # can the system read it at all
    "keywords": 30.0,       # weighted requirement coverage
    "context": 14.0,        # are requirements evidenced, not just listed
    "title": 10.0,          # requisition title alignment
    "experience": 10.0,     # years / seniority fit
    "education": 6.0,       # degree and certifications
    "writing": 8.0,         # quantification, strong verbs, hygiene
}

# Cosine at or above this counts as "the resume says something about this".
# Tuned on short bullet-length text, where 0.10 already implies real overlap of
# distinctive terms rather than shared filler words.
RELATED_THRESHOLD = 0.10

BANDS: Sequence[Tuple[float, str, str]] = (
    (85, "Strong", "Competitive on keyword screening; focus on the cover note and referrals."),
    (70, "Good", "Likely to clear automated filters. Close the top gaps to be safe."),
    (55, "Borderline", "Could go either way. The gaps below are worth fixing before you apply."),
    (40, "Weak", "Likely to be filtered out. Address the blockers and top missing terms."),
    (0, "Poor", "Very unlikely to reach a human in this form."),
)


@dataclass
class Gate:
    """A hard requirement and whether the resume satisfies it."""

    kind: str
    detail: str
    satisfied: bool
    evidence: str = ""
    note: str = ""


@dataclass
class Component:
    name: str
    score: float          # 0-100 within the component
    weight: float
    detail: str = ""

    @property
    def points(self) -> float:
        return self.score / 100.0 * self.weight


@dataclass
class ScoreReport:
    total: float = 0.0
    band: str = ""
    verdict: str = ""
    components: List[Component] = field(default_factory=list)
    gates: List[Gate] = field(default_factory=list)
    matches: List[TermMatch] = field(default_factory=list)
    parse: Optional[ParseAudit] = None
    resume: Optional[Resume] = None
    jd: Optional[JobDescription] = None
    document: Optional[Document] = None
    bm25: float = 0.0
    coverage: float = 0.0
    context_pairs: List[Tuple[str, float, str]] = field(default_factory=list)
    gate_penalty: float = 0.0
    suggestions: List[str] = field(default_factory=list)

    @property
    def failed_gates(self) -> List[Gate]:
        return [g for g in self.gates if not g.satisfied]

    def component(self, name: str) -> Optional[Component]:
        return next((c for c in self.components if c.name == name), None)

    def missing(self, limit: int = 20) -> List[TermMatch]:
        out = [m for m in self.matches if m.status == "missing"]
        return sorted(out, key=lambda m: -m.requirement.weight)[:limit]

    def weak(self, limit: int = 10) -> List[TermMatch]:
        """Terms present only fuzzily or only inside a skills list."""
        out = [
            m for m in self.matches
            if m.status == "fuzzy" or (m.status != "missing" and m.in_skills_only)
        ]
        return sorted(out, key=lambda m: -m.requirement.weight)[:limit]


def _band(total: float) -> Tuple[str, str]:
    for threshold, name, verdict in BANDS:
        if total >= threshold:
            return name, verdict
    return BANDS[-1][1], BANDS[-1][2]


# --------------------------------------------------------------------------
# Individual components
# --------------------------------------------------------------------------

def _title_score(jd: JobDescription, resume: Resume) -> Tuple[float, str]:
    """Overlap between the requisition title and the candidate's role titles."""
    if not jd.title:
        return 70.0, "no requisition title detected; scored neutrally"
    target = set(stems(jd.title)) - {"ii", "iii", "iv", "sr", "jr", "senior", "junior", "staff", "lead"}
    if not target:
        return 70.0, "requisition title had no distinctive words"

    candidates: List[Tuple[float, str]] = []
    for role in resume.roles:
        got = set(stems(role.title))
        if not got:
            continue
        overlap = len(target & got) / len(target)
        recency_bonus = 1.0 if role is resume.roles[0] else 0.85
        candidates.append((overlap * recency_bonus, role.title))
    # A headline under the name ("Senior Director, Solution Consulting") is
    # standard practice and is precisely what a title match should see, but it
    # sits above the first section heading, so scanning only roles and the
    # summary missed it entirely.
    for raw in resume.section("_header").splitlines():
        line = raw.strip()
        if not line or len(line.split()) > 12:
            continue
        if EMAIL_RE.search(line) or PHONE_RE.search(line) or URL_RE.search(line):
            continue
        got = set(stems(line))
        if not got:
            continue
        # Just under a held title: a stated target is a claim, not a record.
        candidates.append((len(target & got) / len(target) * 0.95, f"headline {line!r}"))

    summary = resume.section("summary")
    if summary:
        got = set(stems(summary))
        candidates.append((len(target & got) / len(target) * 0.8, "summary"))

    if not candidates:
        return 25.0, "no job titles found to compare"
    best, where = max(candidates, key=lambda p: p[0])
    pct = min(100.0, best * 100.0)
    return pct, f"best title overlap {pct:.0f}% (from {where!r}) against {jd.title!r}"


def _experience_score(jd: JobDescription, resume: Resume) -> Tuple[float, str]:
    have = resume.years_experience
    need = jd.min_years
    if need is None:
        if have <= 0:
            return 60.0, "no minimum stated; no dated experience found in resume"
        return 85.0, f"no minimum stated; resume evidences about {have} years"
    if have <= 0:
        return 15.0, f"posting asks for {need:.0f}+ years; none could be parsed from dates"
    ratio = have / need
    if ratio >= 1.0:
        # Being wildly over the requirement is a mild negative in practice.
        score = 100.0 if ratio <= 2.5 else 88.0
    else:
        score = max(10.0, 100.0 * (ratio ** 1.5))
    return score, f"posting asks {need:.0f}+ years; resume evidences about {have} years"


def degree_evidence(resume: Resume) -> int:
    """Highest degree evidenced anywhere in the resume.

    Deliberately not limited to the education section.  A design-led layout can
    place the "Education" heading *after* the degrees it labels, or lose it to a
    text box, leaving a section that parses to something like "Page 2 of 2".
    Trusting that section alone reported a real candidate's MBA and BS as "no
    degree detected" and failed a degree gate that he actually meets -- a false
    knockout is far worse than crediting a degree mentioned elsewhere.
    """
    sectioned = degree_rank(resume.section("education") + "\n" + resume.section("certifications"))
    return max(sectioned, degree_rank(resume.text))


def _education_score(jd: JobDescription, resume: Resume) -> Tuple[float, str]:
    have = degree_evidence(resume)
    if jd.min_degree is None:
        # A posting that states no requirement cannot be under-met. Holding a
        # degree anyway is full marks; the old 85 ceiling docked a candidate
        # for a gap that did not exist and could not be closed.
        if have:
            return 100.0, "no degree requirement stated; resume shows a degree"
        return 70.0, "no degree requirement stated; none detected"
    need = degree_rank(jd.min_degree)
    if have >= need:
        return 100.0, f"posting asks for a {jd.min_degree} degree; resume shows an equal or higher degree"
    if have:
        return 55.0, f"posting asks for a {jd.min_degree} degree; a lower degree was detected"
    return 25.0, f"posting asks for a {jd.min_degree} degree; none detected in the resume"


def _writing_score(resume: Resume) -> Tuple[float, str]:
    """Accomplishment quality: quantification, strong openers, bullet length."""
    bullets = resume.experience_bullets
    if not bullets:
        return 35.0, "no bullet points detected"

    quantified = sum(1 for b in bullets if METRIC_RE.search(b))
    strong = 0
    weak = 0
    for b in bullets:
        strength = opener_strength(b)
        if strength == "strong":
            strong += 1
        elif strength == "weak":
            weak += 1
    long_bullets = sum(1 for b in bullets if len(b.split()) > 45)

    n = len(bullets)
    quant_ratio = quantified / n
    strong_ratio = strong / n

    score = 100.0
    score -= max(0.0, (0.5 - quant_ratio)) * 90.0     # target: half are quantified
    score -= max(0.0, (0.6 - strong_ratio)) * 55.0    # target: most open with a verb
    score -= (weak / n) * 45.0
    score -= (long_bullets / n) * 25.0
    score = max(0.0, min(100.0, score))
    detail = (
        f"{n} bullets; {quantified} quantified ({quant_ratio:.0%}), "
        f"{strong} strong openers ({strong_ratio:.0%}), {weak} weak openers"
    )
    return score, detail


def _context_score(pairs: Sequence[Tuple[str, float, str]]) -> Tuple[float, str]:
    """How well resume lines actually mirror the posting's requirement lines."""
    if not pairs:
        return 60.0, "no requirement lines available to compare"
    scores = sorted((s for _, s, _ in pairs), reverse=True)
    n = len(scores)
    # Cosine between two short lines is small in absolute terms even when they
    # clearly describe the same work, so the raw mean is not usable as a score.
    # Blend breadth (how many requirements got any related line) with depth
    # (how strong the better matches are), which is stable across posting
    # lengths in a way a scaled mean is not.
    covered = sum(1 for s in scores if s >= RELATED_THRESHOLD)
    breadth = covered / n
    top_half = scores[: max(1, n // 2)]
    depth = min(1.0, (sum(top_half) / len(top_half)) / 0.22)
    calibrated = 100.0 * (0.62 * breadth + 0.38 * depth)
    return calibrated, f"{covered}/{n} requirement lines have a clearly related resume line"


# --------------------------------------------------------------------------
# Hard-requirement gates
# --------------------------------------------------------------------------

def _evaluate_gates(jd: JobDescription, resume: Resume, index: ResumeIndex) -> List[Gate]:
    gates: List[Gate] = []
    seen: set = set()
    for hard in jd.hard_requirements:
        key = (hard.kind, hard.detail.lower())
        if key in seen:
            continue
        seen.add(key)

        if hard.kind == "years":
            need = hard.value or 0.0
            have = resume.years_experience
            gates.append(Gate(
                "years", f"{need:.0f}+ years of experience",
                satisfied=have >= need,
                evidence=f"resume evidences about {have} years",
                note=hard.context[:160],
            ))
        elif hard.kind == "degree":
            need = int(hard.value or 0)
            have = degree_evidence(resume)
            gates.append(Gate(
                "degree", hard.detail,
                satisfied=have >= need,
                evidence="degree detected" if have else "no degree detected",
                note=hard.context[:160],
            ))
        elif hard.kind == "clearance":
            present, _ = index.contains(hard.detail)
            if not present:
                present = bool(resume.section("clearance"))
            gates.append(Gate(
                "clearance", hard.detail,
                satisfied=present,
                evidence="mentioned in resume" if present else "not mentioned in resume",
                note=hard.context[:160],
            ))
    return gates


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def score(
    document: Document,
    jd: JobDescription,
    lexicon: Optional[SkillLexicon] = None,
) -> ScoreReport:
    from .resume import parse as parse_resume

    lexicon = lexicon or default_lexicon()
    # Repair mechanical damage first, then measure. Scoring the broken text
    # would report a content problem ("no bullet points") for what is really a
    # font problem, and send the candidate off to rewrite prose that is fine.
    repaired_text, repairs = repair_layout(document.text)
    resume = parse_resume(repaired_text)

    recent_text = resume.roles[0].text if resume.roles else ""
    index = ResumeIndex(
        repaired_text,
        skills_text=resume.section("skills"),
        recent_text=recent_text,
    )

    matches = match_requirements(jd.requirements, index, lexicon)
    mres = MatchResult(matches=matches)

    jd_lines = jd.requirement_lines + jd.responsibility_lines
    # Compare against bullets *and* prose lines (summary, skills). Restricting
    # this to bullets made a skills-list-only match score zero here as well as
    # taking the skills-only penalty in the keyword component -- one weakness,
    # counted twice.
    resume_lines = list(resume.bullets)
    resume_lines += [
        ln.strip() for ln in repaired_text.splitlines()
        if len(ln.split()) > 4 and ln.strip() not in resume_lines
    ]
    pairs = contextual_coverage(jd_lines, resume_lines)

    audit_result = parse_audit(document, resume, repairs)

    coverage = mres.coverage
    kw_score = min(100.0, coverage * 118.0)  # full marks short of literal 100% coverage

    title_s, title_d = _title_score(jd, resume)
    exp_s, exp_d = _experience_score(jd, resume)
    edu_s, edu_d = _education_score(jd, resume)
    wri_s, wri_d = _writing_score(resume)
    ctx_s, ctx_d = _context_score(pairs)

    components = [
        Component("parseability", audit_result.score, WEIGHTS["parseability"],
                  f"{audit_result.count('blocker')} blockers, "
                  f"{audit_result.count('major')} major, {audit_result.count('minor')} minor"),
        Component("keywords", kw_score, WEIGHTS["keywords"],
                  f"{coverage:.0%} weighted coverage of {len(jd.requirements)} mined terms"),
        Component("context", ctx_s, WEIGHTS["context"], ctx_d),
        Component("title", title_s, WEIGHTS["title"], title_d),
        Component("experience", exp_s, WEIGHTS["experience"], exp_d),
        Component("education", edu_s, WEIGHTS["education"], edu_d),
        Component("writing", wri_s, WEIGHTS["writing"], wri_d),
    ]

    total = sum(c.points for c in components)

    gates = _evaluate_gates(jd, resume, index)
    failed = [g for g in gates if not g.satisfied]
    # A failed gate caps the score rather than merely subtracting from it,
    # because that is how a knockout filter behaves.
    gate_penalty = 0.0
    if failed:
        cap = 62.0 if len(failed) == 1 else 48.0
        if total > cap:
            gate_penalty = total - cap
            total = cap

    band, verdict = _band(total)

    report = ScoreReport(
        total=round(total, 1),
        band=band,
        verdict=verdict,
        components=components,
        gates=gates,
        matches=matches,
        parse=audit_result,
        resume=resume,
        jd=jd,
        document=document,
        bm25=bm25(stems(jd.signal_text), index.stems),
        coverage=coverage,
        context_pairs=pairs,
        gate_penalty=round(gate_penalty, 1),
    )
    report.suggestions = build_suggestions(report)
    return report


def build_suggestions(report: ScoreReport) -> List[str]:
    """Ordered, concrete next actions -- highest expected score gain first."""
    out: List[str] = []
    parse = report.parse

    if parse:
        for finding in parse.sorted_findings():
            if finding.severity == "blocker":
                out.append(f"Fix first (blocks parsing): {finding.message} {finding.fix}".strip())

    for gate in report.failed_gates:
        out.append(
            f"Hard requirement not evidenced -- {gate.detail} ({gate.evidence}). "
            "If you do meet it, state it explicitly; if you do not, expect an "
            "automatic knockout regardless of everything else."
        )

    missing = report.missing(8)
    if missing:
        terms = ", ".join(f"'{m.requirement.display}'" for m in missing[:8])
        out.append(
            "Add the highest-weighted missing terms, each inside a real "
            f"accomplishment bullet rather than a keyword list: {terms}."
        )

    weak = report.weak(6)
    skills_only = [m for m in weak if m.in_skills_only]
    if skills_only:
        terms = ", ".join(f"'{m.requirement.display}'" for m in skills_only[:6])
        out.append(
            f"These appear only in your skills list: {terms}. Show at least one "
            "of them being used in a bullet -- newer AI screeners weight "
            "demonstrated use over a keyword blob."
        )
    fuzzy = [m for m in weak if m.status == "fuzzy"]
    if fuzzy:
        terms = ", ".join(
            f"'{m.requirement.display}'" for m in fuzzy[:6]
        )
        out.append(
            f"Near-miss wording: {terms}. Match the posting's exact phrasing at "
            "least once -- literal string indexes do not credit paraphrases."
        )

    writing = report.component("writing")
    if writing and writing.score < 70:
        out.append(
            "Strengthen the bullets: open with an action verb and quantify the "
            "result (scope, percentage, time saved, volume handled). "
            f"Currently {writing.detail}."
        )

    title = report.component("title")
    if title and title.score < 55 and report.jd and report.jd.title:
        out.append(
            f"Your titles do not align with '{report.jd.title}'. If your actual "
            "title differs, add the posting's title as a parenthetical or in "
            "your summary line, e.g. 'Security Analyst (SOC Analyst II)'."
        )

    if parse:
        majors = [f for f in parse.sorted_findings() if f.severity == "major"]
        for finding in majors[:4]:
            out.append(f"{finding.message} {finding.fix}".strip())

    return out
