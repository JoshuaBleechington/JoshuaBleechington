"""Alias resolution: map surface forms onto a canonical skill term.

Real screeners index the literal string.  A human reading "Certified
Information Systems Security Professional" knows it is CISSP; a keyword index
does not.  This module lets the scorer credit the candidate for the concept
while still reporting *which* surface form the job description used, because
that is the string worth putting on the resume.
"""

from __future__ import annotations

import json
import os
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .text import canonical

_DATA = os.path.join(os.path.dirname(__file__), "data", "aliases.json")


class SkillLexicon:
    """Bidirectional alias index plus a set of known-skill phrases.

    ``resolve`` collapses any surface form to a canonical id.  ``surfaces``
    expands a canonical id back to every form worth searching for.
    """

    def __init__(self, mapping: Optional[Dict[str, Dict[str, List[str]]]] = None):
        self._canon_by_key: Dict[str, str] = {}
        self._surfaces: Dict[str, List[str]] = {}
        self._category: Dict[str, str] = {}
        if mapping is None:
            mapping = self._load_default()
        for category, entries in mapping.items():
            if category.startswith("_"):
                continue
            for term, alts in entries.items():
                self.add(term, alts, category)

    @staticmethod
    def _load_default() -> Dict[str, Dict[str, List[str]]]:
        with open(_DATA, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def add(self, term: str, alts: Iterable[str] = (), category: str = "custom") -> None:
        forms = [term, *alts]
        self._surfaces.setdefault(term, [])
        self._category[term] = category
        for form in forms:
            key = canonical(form)
            if not key:
                continue
            # A multi-word alias that collapses to a single token has lost its
            # meaning to stopword stripping ("security plus" -> "security") and
            # would hijack a very generic term.  Keep it as a surface form, but
            # never as a lookup key.
            if len(form.split()) > 1 and len(key.split()) == 1:
                if form not in self._surfaces[term]:
                    self._surfaces[term].append(form)
                continue
            # First writer wins so an explicit canonical term is never
            # shadowed by another entry's alias.
            self._canon_by_key.setdefault(key, term)
            if form not in self._surfaces[term]:
                self._surfaces[term].append(form)

    def resolve(self, phrase: str) -> Optional[str]:
        """Return the canonical term for a surface form, or None if unknown."""
        return self._canon_by_key.get(canonical(phrase))

    def surfaces(self, term: str) -> List[str]:
        return self._surfaces.get(term, [term])

    def category(self, term: str) -> str:
        return self._category.get(term, "custom")

    def all_terms(self) -> List[str]:
        """Every canonical term, in insertion order."""
        return list(self._surfaces)

    def keys(self) -> Set[str]:
        """Every canonical key (stemmed) known to the lexicon."""
        return set(self._canon_by_key)

    def is_known(self, phrase: str) -> bool:
        return canonical(phrase) in self._canon_by_key

    def variants_of(self, phrase: str) -> List[str]:
        """All surface forms equivalent to ``phrase`` (including itself)."""
        term = self.resolve(phrase)
        if term is None:
            return [phrase]
        return self.surfaces(term)

    def load_extra(self, path: str) -> None:
        """Merge a user-supplied JSON alias file over the defaults."""
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        for category, entries in data.items():
            if category.startswith("_"):
                continue
            if not isinstance(entries, dict):
                continue
            for term, alts in entries.items():
                self.add(term, alts or [], category)


_DEFAULT: Optional[SkillLexicon] = None


def default_lexicon() -> SkillLexicon:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = SkillLexicon()
    return _DEFAULT
