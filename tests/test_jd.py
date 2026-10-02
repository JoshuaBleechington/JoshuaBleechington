from resume_ats.jd import parse as parse_jd


def test_blocks_are_classified(jd_text):
    kinds = {kind for _, kind, _ in parse_jd(jd_text).blocks}
    assert {"noise", "responsibility", "required", "preferred"} <= kinds


def test_hard_requirements_are_extracted(jd_text):
    jd = parse_jd(jd_text)
    assert jd.min_years == 4.0
    assert jd.min_degree == "bachelor"
    assert jd.title == "Cybersecurity Analyst II"


def test_benefits_boilerplate_is_not_mined_as_a_skill(jd_text):
    terms = {r.term for r in parse_jd(jd_text).requirements}
    for junk in ("401k", "dental insurance", "stock options", "pto", "equal opportunity"):
        assert junk not in terms


def test_requirement_language_never_becomes_a_keyword(jd_text):
    terms = {r.term for r in parse_jd(jd_text).requirements}
    assert not any(
        w in t.split() for t in terms for w in ("required", "minimum", "expertise", "familiarity")
    )


def test_required_terms_outweigh_preferred_ones(jd_text):
    reqs = {r.canonical_term: r for r in parse_jd(jd_text).requirements}
    siem = reqs.get("siem")
    kube = reqs.get("kubernetes")
    assert siem is not None and kube is not None
    assert siem.required and not siem.preferred
    assert kube.preferred
    assert siem.weight > kube.weight


def test_subphrases_of_a_stronger_term_are_suppressed(jd_text):
    terms = {r.term for r in parse_jd(jd_text).requirements}
    assert "security operations center" in terms
    # The fragments it subsumes should not be reported as separate gaps.
    assert "operations center" not in terms


def test_conjunction_fragments_are_not_mined():
    jd = parse_jd("Requirements\n- Familiarity with NIST CSF and ISO 27001.\n")
    terms = {r.term for r in jd.requirements}
    assert "nist csf" in terms and "iso 27001" in terms
    assert "csf and iso" not in terms
