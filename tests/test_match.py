from resume_ats.match import ResumeIndex, bm25, contextual_coverage


def test_scattered_words_do_not_fake_a_phrase_match():
    # "Security Analyst", "Information Technology" and "vulnerability
    # management" must not combine into a match for
    # "security information and event management".
    text = """Security Analyst
    B.S. Information Technology
    Led vulnerability management for the estate.
    """
    index = ResumeIndex(text)
    assert index.fuzzy("security information and event management") is None


def test_adjacent_words_do_match_as_a_phrase():
    index = ResumeIndex("Ran the vulnerability management lifecycle end to end.")
    assert index.fuzzy("vulnerability management") is not None


def test_exact_containment_ignores_case_and_inflection():
    index = ResumeIndex("Handled Incident Responses across the estate.")
    present, count = index.contains("incident response")
    assert present and count == 1


def test_skills_only_terms_are_flagged():
    index = ResumeIndex(
        "SKILLS\nSplunk, Python\nEXPERIENCE\n- Built detections in Splunk.",
        skills_text="Splunk, Python",
    )
    assert index.in_skills("python")
    # Splunk also appears in a bullet, so it is not skills-only.
    from resume_ats.match import _outside_skills
    assert _outside_skills(index, "splunk")
    assert not _outside_skills(index, "python")


def test_bm25_rewards_the_more_relevant_document():
    query = ["splunk", "threat", "hunting"]
    close = ["splunk", "threat", "hunting", "detection"]
    far = ["accounting", "payroll", "invoice"]
    assert bm25(query, close) > bm25(query, far)


def test_contextual_coverage_picks_the_related_line():
    pairs = contextual_coverage(
        ["Perform threat hunting using MITRE ATT&CK"],
        ["Managed payroll reconciliation", "Built threat hunting playbooks with MITRE ATT&CK"],
    )
    _, score, best = pairs[0]
    assert "threat hunting playbooks" in best
    assert score > 0
