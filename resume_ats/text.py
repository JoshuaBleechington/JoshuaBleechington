"""Text normalization, tokenization and light stemming.

Deliberately dependency-free.  Everything downstream (keyword mining, matching,
scoring) runs on the primitives defined here, so the rules about what counts as
a token live in exactly one place.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable, Iterator, List, Sequence, Tuple

# Characters that are legal *inside* a token.  Without these, "c++", "ci/cd",
# ".net", "node.js" and "f5" get shredded into noise and the match rate lies.
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#&./_-]*")

_DASHES = dict.fromkeys(map(ord, "‐‑‒–—―−"), "-")
_QUOTES = {
    ord("‘"): "'", ord("’"): "'", ord("‚"): "'",
    ord("“"): '"', ord("”"): '"', ord("„"): '"',
    ord(" "): " ", ord("​"): "", ord("﻿"): "",
}

# Bullet glyphs that resumes use.  Normalised to "-" so bullet detection is
# not a guessing game later.
BULLET_CHARS = "-•‣▪●◦⁃∙·‧–—*+>"
_BULLET_RE = re.compile(r"^[\s%s]{0,6}[%s]\s+" % (re.escape(BULLET_CHARS), re.escape(BULLET_CHARS)))

STOPWORDS = frozenset("""
a about above across after again against all almost along already also although always am among an and
another any anyone anything are around as at be because been before being below best better between both
but by can cannot could day did do does doing done down due during each either else enough etc even ever
every everyone excellent experience few for from further get give go good great had has have having he her
here hers herself him himself his how however i if in including into is it its itself just keep least less
let like ll made make many may me might more most much must my myself need needs neither never new next no
nor not nothing now of off often on once one only or other others otherwise ought our ours ourselves out
over own per perhaps please plus proven quite rather re really same seem several shall she should since so
some someone something strong such sure than that the their theirs them themselves then there these they
thing things this those though through throughout thus to together too toward towards under unless until
up upon us use used using various very via was way we well were what whatever when where whether which while
who whom whose why will with within without would year years yet you your yours yourself
ability able across additional adept applicant applicants apply candidate candidates company duties employee
employer employment ideal include includes join looking opportunity position responsibilities role seeking
successful team teams work working workplace
""".split())

# Words that are stopwords in prose but meaningful inside a skill phrase.
_KEEP_IN_PHRASE = frozenset({"in", "of", "and", "as", "on", "for", "to"})

_SUFFIXES: Sequence[Tuple[str, str]] = (
    ("ies", "y"), ("sses", "ss"), ("ches", "ch"), ("shes", "sh"), ("xes", "x"),
    ("ing", ""), ("ed", ""), ("s", ""),
)
# Note: there is deliberately no blanket ("es", "") rule. It would stem
# "responses" to "respons" while "response" stays whole, so "incident response"
# and "incident responses" would fail to match each other. The specific
# -sses/-ches/-shes/-xes rules above cover the cases where -es really is the
# plural marker; everything else is handled correctly by stripping just the -s.


def normalize(text: str) -> str:
    """Lowercase and flatten unicode punctuation without destroying structure."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(_QUOTES).translate(_DASHES)
    text = "".join(
        c for c in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(c)
    )
    return text.lower()


def stem(token: str) -> str:
    """Very light suffix stripper.

    Acronyms and short tokens are left alone -- turning "aws" into "aw" or
    "sans" into "san" would silently break certification matching.
    """
    if len(token) <= 4 or not token.isalpha():
        return token
    for suffix, repl in _SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) + len(repl) >= 3:
            return token[: -len(suffix)] + repl
    return token


def tokenize(text: str, *, keep_stopwords: bool = False) -> List[str]:
    """Normalize then split into matchable tokens."""
    toks = _TOKEN_RE.findall(normalize(text))
    cleaned = []
    for t in toks:
        t = t.strip("./-_&")
        if not t:
            continue
        if not keep_stopwords and t in STOPWORDS:
            continue
        cleaned.append(t)
    return cleaned


def stems(text: str) -> List[str]:
    return [stem(t) for t in tokenize(text)]


def ngrams(tokens: Sequence[str], lo: int = 1, hi: int = 3) -> Iterator[Tuple[str, ...]]:
    n_tokens = len(tokens)
    for size in range(lo, hi + 1):
        for i in range(n_tokens - size + 1):
            yield tuple(tokens[i : i + size])


_SEGMENT_RE = re.compile(r"[,;:()\[\]{}<>|\u2022]|\s+/\s+|\s-\s|(?<=[.!?])\s")


def segments(text: str) -> List[str]:
    """Split a line at punctuation that separates independent list items.

    "Computer Science, Information Security" is two things, not a source of the
    phrase "science information security".
    """
    return [seg.strip() for seg in _SEGMENT_RE.split(normalize(text)) if seg and seg.strip()]


def phrase_ngrams(text: str, lo: int = 1, hi: int = 3) -> Iterator[str]:
    """N-grams that may contain glue words internally but never at the edges.

    "identity and access management" survives; "and the team" does not.
    """
    for segment in segments(text):
        toks = [t for t in (x.strip("./-_&") for x in _TOKEN_RE.findall(segment)) if t]
        for gram in ngrams(toks, lo, hi):
            if gram[0] in STOPWORDS or gram[-1] in STOPWORDS:
                continue
            if any(t in STOPWORDS and t not in _KEEP_IN_PHRASE for t in gram):
                continue
            yield " ".join(gram)


def canonical(phrase: str) -> str:
    """Stem-normalised form of a phrase, used as a dictionary key."""
    return " ".join(stem(t) for t in tokenize(phrase))


def sentences(text: str) -> List[str]:
    """Split into sentence-ish units, treating line breaks as hard boundaries."""
    out: List[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        for part in re.split(r"(?<=[.!?;])\s+(?=[A-Z0-9])", line):
            part = part.strip()
            if len(part) > 2:
                out.append(part)
    return out


def lines(text: str) -> List[str]:
    return [ln.rstrip() for ln in text.splitlines()]


def is_bullet(line: str) -> bool:
    return bool(_BULLET_RE.match(line))


def strip_bullet(line: str) -> str:
    return _BULLET_RE.sub("", line).strip()


def dedupe(items: Iterable[str]) -> List[str]:
    seen, out = set(), []
    for it in items:
        key = it.lower()
        if key not in seen:
            seen.add(key)
            out.append(it)
    return out

# Glyphs that a symbol font (Wingdings, Symbol) leaves behind when a decorative
# bullet is exported to PDF or plain text.  A Wingdings checkmark becomes a
# literal "u" with an umlaut, so a whole resume of bullets arrives as prose and
# no parser sees a single bullet point.  These characters essentially never
# start a real English line, which is what makes the repair safe.
BROKEN_BULLETS = "\u00fc\u00a7\u00d8\u00fe\u00a4\u00a8"
_BROKEN_BULLET_RE = re.compile(r"^([ \t]*)[%s]([ \t]+|(?=[A-Z]))" % re.escape(BROKEN_BULLETS))
_LONE_BROKEN_RE = re.compile(r"^[ \t]*[%s][ \t]*$" % re.escape(BROKEN_BULLETS))


def is_letter_spaced(line: str) -> bool:
    """True for text typed with spaces between letters ("E X P E R I E N C E").

    Two shapes occur in practice: fully spaced headings, and the ragged
    fragments a design tool produces when it tracks out a word
    ("Tra ns fo rmati o na l").  Both are unreadable to a parser, so both count.
    """
    stripped = line.strip()
    if len(stripped) < 7:
        return False
    if re.fullmatch(r"(?:[A-Za-z]\s){3,}[A-Za-z]", stripped):
        return True
    parts = stripped.split()
    if len(parts) < 5:
        return False
    short = sum(1 for p in parts if len(p) <= 2 and p.isalpha())
    return short / len(parts) >= 0.6


def repair_layout(text: str) -> Tuple[str, List[str]]:
    """Undo the damage that stops a parser reading a visually fine resume.

    Returns the repaired text and a list of human-readable notes describing
    what was repaired, so the audit can report the underlying problem rather
    than silently papering over it.
    """
    notes: List[str] = []
    out: List[str] = []
    broken = 0
    for raw in text.splitlines():
        if _LONE_BROKEN_RE.match(raw):
            broken += 1
            continue  # an orphaned bullet glyph with no text of its own
        repaired, n = _BROKEN_BULLET_RE.subn(r"\1- ", raw)
        broken += n
        out.append(repaired)
    if broken:
        notes.append(
            f"{broken} bullet(s) used a symbol font that exports as a stray "
            "letter, so no parser would have recognised them as bullets"
        )
    return "\n".join(out), notes
