"""Matching a resume against mined requirements.

Three independent signals, because real screeners use more than one:

* **Literal / alias match** -- what a boolean recruiter search does.
* **Fuzzy match** -- catches "Splunk ES" vs "Splunk Enterprise Security" and
  ordinary typos, reported separately because a near miss is not a hit as far
  as an exact-match index is concerned.
* **BM25 + TF-IDF cosine** -- Okapi BM25 is the ranking function behind the
  Lucene/Elasticsearch indexes that many ATS products search over, so ranking
  the resume the same way approximates where it lands in a recruiter's result
  list rather than just whether a word is present.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .aliases import SkillLexicon, default_lexicon
from .jd import Requirement
from .text import canonical, stem, stems, tokenize

FUZZY_THRESHOLD = 0.86


@dataclass
class TermMatch:
    """How one requirement fared against the resume."""

    requirement: Requirement
    status: str                       # exact | alias | fuzzy | missing
    matched_form: str = ""            # the string actually found in the resume
    evidence: str = ""                # the resume line it was found in
    in_recent_role: bool = False
    in_skills_only: bool = False
    occurrences: int = 0

    @property
    def credit(self) -> float:
        """Fraction of the requirement's weight this match earns.

        A fuzzy hit is deliberately worth less than an exact one: an index that
        matches literal strings will not credit it at all.
        """
        base = {"exact": 1.0, "alias": 0.92, "fuzzy": 0.6, "missing": 0.0}[self.status]
        if self.status == "missing":
            return 0.0
        if self.in_skills_only:
            # Present only in a skills list, never demonstrated in context.
            # Keyword filters accept this; AI screeners increasingly do not.
            base *= 0.82
        if self.in_recent_role:
            base *= 1.05
        return min(1.0, base)


@dataclass
class MatchResult:
    matches: List[TermMatch] = field(default_factory=list)
    bm25: float = 0.0
    cosine: float = 0.0

    def by_status(self, status: str) -> List[TermMatch]:
        return [m for m in self.matches if m.status == status]

    @property
    def missing(self) -> List[TermMatch]:
        return sorted(self.by_status("missing"), key=lambda m: -m.requirement.weight)

    @property
    def coverage(self) -> float:
        """Weighted fraction of requirement weight the resume satisfies."""
        total = sum(m.requirement.weight for m in self.matches)
        if total <= 0:
            return 0.0
        got = sum(m.requirement.weight * m.credit for m in self.matches)
        return got / total


class ResumeIndex:
    """Searchable view of a resume, built once and queried many times."""

    def __init__(self, text: str, *, skills_text: str = "", recent_text: str = ""):
        self.text = text
        self.norm_lines = [ln for ln in text.splitlines() if ln.strip()]
        self.tokens = tokenize(text)
        self.stems = [stem(t) for t in self.tokens]
        self.stem_counts = Counter(self.stems)
        self.joined = " " + " ".join(self.stems) + " "
        self.skills_joined = " " + " ".join(stems(skills_text)) + " " if skills_text else ""
        self.recent_joined = " " + " ".join(stems(recent_text)) + " " if recent_text else ""
        self._line_index: List[Tuple[str, str]] = [
            (" " + " ".join(stems(ln)) + " ", ln.strip()) for ln in self.norm_lines
        ]
        # Bucket vocabulary by first letter to keep fuzzy search linear enough.
        self._vocab: Set[str] = set(self.stems)
        self._by_initial: Dict[str, List[str]] = {}
        for word in self._vocab:
            self._by_initial.setdefault(word[:1], []).append(word)

    def contains(self, phrase: str) -> Tuple[bool, int]:
        key = canonical(phrase)
        if not key:
            return False, 0
        needle = " " + key + " "
        count = self.joined.count(needle)
        return count > 0, count

    def find_line(self, phrase: str) -> str:
        key = canonical(phrase)
        if not key:
            return ""
        needle = " " + key + " "
        for blob, raw in self._line_index:
            if needle in blob:
                return raw
        return ""

    def in_skills(self, phrase: str) -> bool:
        key = canonical(phrase)
        return bool(key) and (" " + key + " ") in self.skills_joined

    def in_recent(self, phrase: str) -> bool:
        key = canonical(phrase)
        return bool(key) and (" " + key + " ") in self.recent_joined

    def fuzzy(self, phrase: str, threshold: float = FUZZY_THRESHOLD) -> Optional[str]:
        """Nearest vocabulary match for a phrase, or None."""
        key = canonical(phrase)
        if not key:
            return None
        parts = key.split()
        if len(parts) > 1:
            return self._fuzzy_phrase(parts, threshold)
        return self._fuzzy_word(key, threshold)

    def _fuzzy_word(self, word: str, threshold: float) -> Optional[str]:
        if len(word) < 5:
            return None  # short tokens are too easy to confuse
        best, best_score = None, threshold
        for cand in self._by_initial.get(word[:1], ()):
            if abs(len(cand) - len(word)) > 3:
                continue
            score = SequenceMatcher(None, word, cand).ratio()
            if score > best_score:
                best, best_score = cand, score
        return best

    def _fuzzy_phrase(self, parts: Sequence[str], threshold: float) -> Optional[str]:
        """Match a multi-word phrase only if its words occur *close together*.

        Checking mere presence is not enough.  "Security Analyst" in a job
        title, "Information Technology" in a degree and "vulnerability
        management" in a bullet would otherwise combine to claim a match for
        "security information and event management" -- three unrelated lines
        conjured into a skill the resume never mentions.  Requiring the words
        inside one short window is what makes this a phrase match rather than a
        bag-of-words coincidence.
        """
        if len(parts) < 2:
            return None
        resolved: Dict[str, str] = {}
        for part in parts:
            if part in self._vocab:
                resolved[part] = part
            else:
                approx = self._fuzzy_word(part, threshold)
                if approx:
                    resolved[part] = approx
        # Allow one missing word only on longer phrases; a 2- or 3-word phrase
        # must be fully present, or the "match" is mostly coincidence.
        needed = max(2, math.ceil(len(parts) * 0.75))
        if len(resolved) < needed:
            return None

        targets = set(resolved.values())
        positions = [(i, t) for i, t in enumerate(self.stems) if t in targets]
        if len(positions) < needed:
            return None

        # Allow at most one intervening word across the whole span. A looser
        # window lets words from three different lines count as one phrase.
        window = len(parts) + 1
        left = 0
        seen: Counter = Counter()
        for right, (pos, tok) in enumerate(positions):
            seen[tok] += 1
            while positions[right][0] - positions[left][0] > window:
                seen[positions[left][1]] -= 1
                if seen[positions[left][1]] == 0:
                    del seen[positions[left][1]]
                left += 1
            if len(seen) >= needed:
                start = positions[left][0]
                end = min(len(self.tokens), positions[right][0] + 1)
                return " ".join(self.tokens[start:end])
        return None


def match_requirements(
    requirements: Sequence[Requirement],
    index: ResumeIndex,
    lexicon: Optional[SkillLexicon] = None,
) -> List[TermMatch]:
    lexicon = lexicon or default_lexicon()
    out: List[TermMatch] = []
    for req in requirements:
        forms = [req.term]
        if req.known_skill:
            forms = list(dict.fromkeys([req.term, *lexicon.variants_of(req.term)]))

        best: Optional[TermMatch] = None
        for i, form in enumerate(forms):
            present, count = index.contains(form)
            if present:
                status = "exact" if i == 0 else "alias"
                # The skills-list penalty is for a capability you listed but
                # never showed doing. Showing it under a different name is
                # still showing it, so check every equivalent surface form
                # before docking the match.
                demonstrated = any(_outside_skills(index, f) for f in forms)
                best = TermMatch(
                    requirement=req,
                    status=status,
                    matched_form=form,
                    evidence=index.find_line(form),
                    occurrences=count,
                    in_recent_role=index.in_recent(form),
                    in_skills_only=index.in_skills(form) and not demonstrated,
                )
                break
        if best is None:
            for form in forms:
                approx = index.fuzzy(form)
                if approx:
                    best = TermMatch(
                        requirement=req,
                        status="fuzzy",
                        matched_form=approx,
                        evidence=index.find_line(approx),
                        occurrences=1,
                    )
                    break
        if best is None:
            best = TermMatch(requirement=req, status="missing")
        out.append(best)
    return out


def _outside_skills(index: ResumeIndex, form: str) -> bool:
    """True if the term also appears somewhere other than the skills list."""
    key = canonical(form)
    if not key:
        return False
    needle = " " + key + " "
    total = index.joined.count(needle)
    in_skills = index.skills_joined.count(needle) if index.skills_joined else 0
    return total > in_skills


# --------------------------------------------------------------------------
# BM25 and cosine
# --------------------------------------------------------------------------

def bm25(
    query_tokens: Sequence[str],
    doc_tokens: Sequence[str],
    corpus_df: Optional[Dict[str, int]] = None,
    corpus_size: int = 1,
    k1: float = 1.5,
    b: float = 0.75,
    avg_len: Optional[float] = None,
) -> float:
    """Okapi BM25 of one document against a query.

    With a single document there is no real corpus, so IDF is approximated from
    the query itself.  The absolute number is meaningless; the value is in
    comparing two versions of the same resume against the same posting.
    """
    if not query_tokens or not doc_tokens:
        return 0.0
    doc_len = len(doc_tokens)
    avg_len = avg_len or doc_len or 1.0
    freqs = Counter(doc_tokens)
    corpus_df = corpus_df or {}
    score = 0.0
    for term in set(query_tokens):
        f = freqs.get(term, 0)
        if not f:
            continue
        df = corpus_df.get(term, 1)
        idf = math.log(1 + (corpus_size - df + 0.5) / (df + 0.5))
        denom = f + k1 * (1 - b + b * doc_len / avg_len)
        score += idf * (f * (k1 + 1)) / denom
    return score


def _tf_idf(docs: Sequence[Sequence[str]]) -> List[Dict[str, float]]:
    n = len(docs)
    df: Counter = Counter()
    for doc in docs:
        df.update(set(doc))
    vectors: List[Dict[str, float]] = []
    for doc in docs:
        counts = Counter(doc)
        total = sum(counts.values()) or 1
        vec = {}
        for term, count in counts.items():
            idf = math.log((n + 1) / (df[term] + 1)) + 1.0
            vec[term] = (count / total) * idf
        vectors.append(vec)
    return vectors


def cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    num = sum(a[t] * b[t] for t in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if not na or not nb:
        return 0.0
    return num / (na * nb)


def contextual_coverage(
    jd_lines: Sequence[str], resume_lines: Sequence[str]
) -> List[Tuple[str, float, str]]:
    """For each JD requirement line, the best-matching resume line and its score.

    This is the signal that separates "the word appears in a skills blob" from
    "the candidate describes doing the thing", which is what LLM-based screeners
    are actually asked to judge.
    """
    jd_docs = [stems(line) for line in jd_lines]
    res_docs = [stems(line) for line in resume_lines]
    if not jd_docs or not res_docs:
        return [(line, 0.0, "") for line in jd_lines]

    vectors = _tf_idf(list(jd_docs) + list(res_docs))
    jd_vecs = vectors[: len(jd_docs)]
    res_vecs = vectors[len(jd_docs) :]

    results: List[Tuple[str, float, str]] = []
    for i, line in enumerate(jd_lines):
        best_score, best_line = 0.0, ""
        for j, rvec in enumerate(res_vecs):
            score = cosine(jd_vecs[i], rvec)
            if score > best_score:
                best_score, best_line = score, resume_lines[j]
        results.append((line, best_score, best_line))
    return results
