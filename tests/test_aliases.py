from resume_ats.aliases import SkillLexicon, default_lexicon


def test_expansions_resolve_to_acronyms():
    lex = default_lexicon()
    assert lex.resolve("Certified Information Systems Security Professional") == "cissp"
    assert lex.resolve("identity and access management") == "iam"
    assert lex.resolve("Azure Active Directory") == "entra id"


def test_generic_word_is_not_hijacked_by_an_alias():
    # "security plus" loses its stopword and would otherwise register the very
    # generic key "security" as the Security+ certification.
    lex = default_lexicon()
    assert lex.resolve("security") is None
    assert lex.resolve("comptia security+") == "security+"


def test_custom_aliases_can_be_added():
    lex = SkillLexicon({"custom": {"widgetry": ["widget engineering"]}})
    assert lex.resolve("Widget Engineering") == "widgetry"
    assert "widget engineering" in lex.surfaces("widgetry")
