from resume_ats.text import (
    canonical, is_bullet, phrase_ngrams, segments, stem, strip_bullet, tokenize,
)


def test_tokenizer_preserves_technical_tokens():
    toks = tokenize("Experienced with CI/CD, Node.js, C++, .NET and MITRE ATT&CK")
    for expected in ("ci/cd", "node.js", "c++", "att&ck"):
        assert expected in toks, f"{expected} was destroyed by tokenization"


def test_stemmer_leaves_acronyms_alone():
    # Stemming "aws" to "aw" or "sans" to "san" would break skill matching.
    for acronym in ("aws", "sans", "gcp", "siem"):
        assert stem(acronym) == acronym


def test_stemmer_normalizes_inflections():
    assert stem("managing") == stem("managed") == "manag"
    assert stem("policies") == "policy"


def test_bullets_include_ascii_hyphen():
    assert is_bullet("- Led the migration")
    assert is_bullet("  • Led the migration")
    assert not is_bullet("Mar 2022 - Present")
    assert strip_bullet("- Led the migration") == "Led the migration"


def test_segments_split_on_list_punctuation():
    got = segments("Computer Science, Information Security, or related field")
    assert "information security" in got
    assert not any("science information" in s for s in got)


def test_phrase_ngrams_do_not_span_conjunctions_of_separate_skills():
    grams = set(phrase_ngrams("Familiarity with NIST CSF and ISO 27001"))
    assert "nist csf" in grams and "iso 27001" in grams


def test_canonical_is_order_and_case_stable():
    assert canonical("Incident Response") == canonical("incident   responses")
