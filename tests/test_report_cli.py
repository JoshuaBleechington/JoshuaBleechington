import json

import pytest

from resume_ats import score_text
from resume_ats.cli import main
from resume_ats.report import render_html, render_json, render_markdown, render_terminal


@pytest.fixture
def report(good_resume, jd_text):
    return score_text(good_resume, jd_text)


def test_all_renderers_produce_output(report):
    assert "ATS MATCH SCORE" in render_terminal(report, color=False)
    assert render_markdown(report).startswith("# ATS Match Report")
    html = render_html(report)
    assert html.startswith("<!doctype html>") and "</html>" in html


def test_html_is_self_contained(report):
    html = render_html(report)
    # No external asset may be referenced: the report must open offline.
    for marker in ("http://", "https://", "<script"):
        assert marker not in html


def test_json_round_trips_and_carries_a_disclaimer(report):
    data = json.loads(render_json(report))
    assert 0 <= data["total"] <= 100
    assert len(data["components"]) == 7
    assert "disclaimer" in data


def test_terminal_output_has_no_escape_codes_when_color_off(report):
    assert "\033[" not in render_terminal(report, color=False)


def _write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_cli_score_writes_each_format(tmp_path, good_resume, jd_text, capsys):
    resume = _write(tmp_path, "r.txt", good_resume)
    jd = _write(tmp_path, "j.txt", jd_text)
    for fmt, ext in (("json", "json"), ("markdown", "md"), ("html", "html")):
        out = str(tmp_path / f"out.{ext}")
        assert main(["score", resume, jd, "--format", fmt, "-o", out]) == 0
        assert len(open(out, encoding="utf-8").read()) > 200
    json.loads(open(str(tmp_path / "out.json"), encoding="utf-8").read())


def test_cli_min_score_gates_with_exit_code(tmp_path, good_resume, jd_text):
    resume = _write(tmp_path, "r.txt", good_resume)
    jd = _write(tmp_path, "j.txt", jd_text)
    out = str(tmp_path / "o.json")
    assert main(["score", resume, jd, "--min-score", "0", "-o", out]) == 0
    assert main(["score", resume, jd, "--min-score", "99.9", "-o", out]) == 2


def test_cli_audit_returns_two_on_blockers(broken_docx, tmp_path):
    out = str(tmp_path / "a.json")
    assert main(["audit", broken_docx, "--format", "json", "-o", out]) == 2
    assert json.loads(open(out, encoding="utf-8").read())["findings"]


def test_cli_keywords_and_compare(tmp_path, good_resume, jd_text):
    resume = _write(tmp_path, "r.txt", good_resume)
    other = _write(tmp_path, "r2.txt", good_resume.replace("Splunk", "Excel"))
    jd = _write(tmp_path, "j.txt", jd_text)
    out = str(tmp_path / "k.json")
    assert main(["keywords", jd, "--format", "json", "-o", out]) == 0
    assert json.loads(open(out, encoding="utf-8").read())["terms"]

    out2 = str(tmp_path / "c.json")
    assert main(["compare", resume, other, "--jd", jd, "--format", "json", "-o", out2]) == 0
    rows = json.loads(open(out2, encoding="utf-8").read())
    assert len(rows) == 2
    # compare must be sorted best-first
    assert rows[0]["total"] >= rows[1]["total"]


def test_cli_reports_unreadable_file_cleanly(tmp_path, jd_text):
    bad = tmp_path / "old.doc"
    bad.write_bytes(b"\xd0\xcf\x11\xe0")
    jd = _write(tmp_path, "j.txt", jd_text)
    assert main(["score", str(bad), jd]) == 1
