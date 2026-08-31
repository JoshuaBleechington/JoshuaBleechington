"""Render a ScoreReport as terminal text, Markdown, JSON or a standalone HTML page."""

from __future__ import annotations

import json
import html as _html
import shutil
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from .score import ScoreReport

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
COLORS = {"green": "\033[32m", "yellow": "\033[33m", "red": "\033[31m", "cyan": "\033[36m"}

SEVERITY_LABEL = {"blocker": "BLOCKER", "major": "MAJOR", "minor": "minor"}


def _band_color(total: float) -> str:
    if total >= 70:
        return "green"
    if total >= 55:
        return "yellow"
    return "red"


def _paint(text: str, color: str, enabled: bool) -> str:
    if not enabled or color not in COLORS:
        return text
    return f"{COLORS[color]}{text}{RESET}"


def _bar(pct: float, width: int = 24) -> str:
    filled = int(round(max(0.0, min(100.0, pct)) / 100.0 * width))
    return "█" * filled + "·" * (width - filled)


def render_terminal(report: ScoreReport, color: bool = True, verbose: bool = False) -> str:
    width = min(shutil.get_terminal_size((88, 24)).columns, 96)
    out: List[str] = []
    rule = "─" * width

    def head(title: str) -> None:
        out.append("")
        out.append(_paint(title, "cyan", color) if not color else f"{BOLD}{title}{RESET}")
        out.append(rule)

    title = report.jd.title if report.jd and report.jd.title else "the posting"
    out.append(rule)
    score_txt = f"{report.total:.1f}/100"
    band = f"{report.band.upper()}"
    out.append(
        f"{BOLD if color else ''}ATS MATCH SCORE{RESET if color else ''}  "
        f"{_paint(score_txt, _band_color(report.total), color)}   "
        f"{_paint(band, _band_color(report.total), color)}"
    )
    out.append(f"{report.verdict}")
    out.append(f"Resume: {report.document.source if report.document else '-'}    Target: {title}")
    out.append(rule)

    head("SCORE BREAKDOWN")
    for comp in report.components:
        colour = "green" if comp.score >= 75 else ("yellow" if comp.score >= 50 else "red")
        out.append(
            f"  {comp.name:<13} {_paint(_bar(comp.score), colour, color)} "
            f"{comp.score:5.1f}  ({comp.points:4.1f}/{comp.weight:.0f} pts)"
        )
        out.append(f"  {'':<13} {DIM if color else ''}{comp.detail}{RESET if color else ''}")

    if report.gate_penalty:
        out.append("")
        out.append(_paint(
            f"  Score capped by {len(report.failed_gates)} unmet hard requirement(s) "
            f"(-{report.gate_penalty:.1f} points).", "red", color))

    if report.gates:
        head("HARD REQUIREMENTS (knockout filters)")
        for gate in report.gates:
            mark = "PASS" if gate.satisfied else "FAIL"
            colour = "green" if gate.satisfied else "red"
            out.append(f"  [{_paint(mark, colour, color)}] {gate.detail} — {gate.evidence}")

    if report.parse and report.parse.findings:
        head("ATS PARSING AUDIT")
        for finding in report.parse.sorted_findings():
            colour = {"blocker": "red", "major": "yellow", "minor": "cyan"}[finding.severity]
            out.append(f"  {_paint(SEVERITY_LABEL[finding.severity], colour, color)}  {finding.message}")
            if finding.fix:
                out.append(f"           {DIM if color else ''}-> {finding.fix}{RESET if color else ''}")

    missing = report.missing(18)
    if missing:
        head("TOP MISSING KEYWORDS (highest weight first)")
        for m in missing:
            req = m.requirement
            tags = []
            if req.required:
                tags.append("required")
            if req.preferred:
                tags.append("preferred")
            if req.known_skill:
                tags.append(req.category)
            tag = f"  [{', '.join(tags)}]" if tags else ""
            out.append(f"  · {req.display}{DIM if color else ''}{tag}{RESET if color else ''}")
            if verbose and req.contexts:
                out.append(f"      {DIM if color else ''}JD: {req.contexts[0][:80]}{RESET if color else ''}")

    weak = report.weak(10)
    if weak:
        head("WEAK MATCHES (present, but not counted the way you think)")
        for m in weak:
            why = "skills list only" if m.in_skills_only else f"near miss -> '{m.matched_form}'"
            out.append(f"  · {m.requirement.display}  ({why})")

    if report.suggestions:
        head("WHAT TO FIX, IN ORDER")
        for i, suggestion in enumerate(report.suggestions, 1):
            out.append(f"  {i}. {_wrap(suggestion, width - 5)}")

    out.append("")
    out.append(f"{DIM if color else ''}Estimate based on resume and posting text only. "
               f"No vendor publishes real thresholds — use this to compare drafts, "
               f"not as a guarantee.{RESET if color else ''}")
    out.append("")
    return "\n".join(out)


def _wrap(text: str, width: int, indent: str = "     ") -> str:
    words, lines, current = text.split(), [], ""
    for word in words:
        if len(current) + len(word) + 1 > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return ("\n" + indent).join(lines)


def render_markdown(report: ScoreReport) -> str:
    jd_title = report.jd.title if report.jd and report.jd.title else "the posting"
    out: List[str] = []
    out.append(f"# ATS Match Report — {report.total:.1f}/100 ({report.band})")
    out.append("")
    out.append(f"**Target:** {jd_title}  ")
    out.append(f"**Resume:** `{report.document.source if report.document else '-'}`  ")
    out.append(f"**Generated:** {datetime.now():%Y-%m-%d %H:%M}")
    out.append("")
    out.append(f"> {report.verdict}")
    out.append("")

    out.append("## Score breakdown")
    out.append("")
    out.append("| Component | Score | Weight | Points | Notes |")
    out.append("|---|---:|---:|---:|---|")
    for c in report.components:
        out.append(f"| {c.name} | {c.score:.0f} | {c.weight:.0f} | {c.points:.1f} | {c.detail} |")
    out.append(f"| **Total** | | **100** | **{report.total:.1f}** | {report.band} |")
    out.append("")

    if report.gates:
        out.append("## Hard requirements")
        out.append("")
        out.append("| Requirement | Status | Evidence |")
        out.append("|---|---|---|")
        for g in report.gates:
            out.append(f"| {g.detail} | {'PASS' if g.satisfied else '**FAIL**'} | {g.evidence} |")
        out.append("")

    if report.parse and report.parse.findings:
        out.append("## ATS parsing audit")
        out.append("")
        for f in report.parse.sorted_findings():
            out.append(f"- **{SEVERITY_LABEL[f.severity]}** — {f.message}")
            if f.fix:
                out.append(f"  - _Fix:_ {f.fix}")
        out.append("")

    missing = report.missing(25)
    if missing:
        out.append("## Top missing keywords")
        out.append("")
        for m in missing:
            tags = [t for t in (
                "required" if m.requirement.required else "",
                "preferred" if m.requirement.preferred else "",
            ) if t]
            suffix = f" _({', '.join(tags)})_" if tags else ""
            out.append(f"- `{m.requirement.display}`{suffix}")
        out.append("")

    weak = report.weak(12)
    if weak:
        out.append("## Weak matches")
        out.append("")
        for m in weak:
            why = "in skills list only" if m.in_skills_only else f"near miss (`{m.matched_form}`)"
            out.append(f"- `{m.requirement.display}` — {why}")
        out.append("")

    if report.suggestions:
        out.append("## What to fix, in order")
        out.append("")
        for i, s in enumerate(report.suggestions, 1):
            out.append(f"{i}. {s}")
        out.append("")

    out.append("---")
    out.append("")
    out.append(
        "_Estimated from resume and posting text only. No ATS vendor publishes "
        "its thresholds; use this to compare drafts of your own resume, not as a "
        "guarantee of any outcome._"
    )
    return "\n".join(out)


def to_dict(report: ScoreReport) -> Dict[str, Any]:
    return {
        "total": report.total,
        "band": report.band,
        "verdict": report.verdict,
        "resume": report.document.source if report.document else None,
        "job_title": report.jd.title if report.jd else None,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "coverage": round(report.coverage, 4),
        "bm25": round(report.bm25, 3),
        "gate_penalty": report.gate_penalty,
        "components": [
            {"name": c.name, "score": round(c.score, 1), "weight": c.weight,
             "points": round(c.points, 2), "detail": c.detail}
            for c in report.components
        ],
        "gates": [asdict(g) for g in report.gates],
        "parse_findings": [asdict(f) for f in report.parse.sorted_findings()] if report.parse else [],
        "parse_score": report.parse.score if report.parse else None,
        "missing_keywords": [
            {"term": m.requirement.display, "weight": round(m.requirement.weight, 2),
             "required": m.requirement.required, "preferred": m.requirement.preferred,
             "category": m.requirement.category,
             "job_context": m.requirement.contexts[0] if m.requirement.contexts else ""}
            for m in report.missing(40)
        ],
        "weak_matches": [
            {"term": m.requirement.display, "status": m.status,
             "matched_form": m.matched_form, "skills_list_only": m.in_skills_only}
            for m in report.weak(20)
        ],
        "matched_keywords": [
            {"term": m.requirement.display, "status": m.status,
             "matched_form": m.matched_form, "occurrences": m.occurrences}
            for m in report.matches if m.status in ("exact", "alias")
        ],
        "suggestions": report.suggestions,
        "resume_stats": {
            "words": report.document.word_count if report.document else 0,
            "years_experience": report.resume.years_experience if report.resume else 0,
            "roles": len(report.resume.roles) if report.resume else 0,
            "bullets": len(report.resume.bullets) if report.resume else 0,
            "sections": report.resume.section_order if report.resume else [],
        },
        "disclaimer": (
            "Estimated from resume and posting text only. No ATS vendor publishes "
            "its thresholds; use this to compare drafts, not as a guarantee."
        ),
    }


def render_json(report: ScoreReport, indent: int = 2) -> str:
    return json.dumps(to_dict(report), indent=indent)


def render_html(report: ScoreReport) -> str:
    """A standalone, self-contained HTML report (no external assets)."""
    d = to_dict(report)
    e = _html.escape

    def comp_rows() -> str:
        rows = []
        for c in report.components:
            cls = "good" if c.score >= 75 else ("mid" if c.score >= 50 else "bad")
            rows.append(
                f'<tr><td>{e(c.name)}</td>'
                f'<td class="num">{c.score:.0f}</td>'
                f'<td><div class="bar"><i class="{cls}" style="width:{max(0,min(100,c.score)):.0f}%"></i></div></td>'
                f'<td class="num">{c.points:.1f}/{c.weight:.0f}</td>'
                f'<td class="note">{e(c.detail)}</td></tr>'
            )
        return "".join(rows)

    findings = "".join(
        f'<li class="sev-{e(f.severity)}"><b>{e(SEVERITY_LABEL[f.severity])}</b> {e(f.message)}'
        + (f'<div class="fix">{e(f.fix)}</div>' if f.fix else "")
        + "</li>"
        for f in (report.parse.sorted_findings() if report.parse else [])
    )
    gates = "".join(
        f'<li class="{"pass" if g.satisfied else "fail"}">'
        f'<b>{"PASS" if g.satisfied else "FAIL"}</b> {e(g.detail)} — {e(g.evidence)}</li>'
        for g in report.gates
    )
    missing = "".join(f"<span class='chip'>{e(m['term'])}</span>" for m in d["missing_keywords"][:30])
    matched = "".join(f"<span class='chip ok'>{e(m['term'])}</span>" for m in d["matched_keywords"][:30])
    steps = "".join(f"<li>{e(s)}</li>" for s in report.suggestions)
    band_cls = "good" if report.total >= 70 else ("mid" if report.total >= 55 else "bad")

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ATS Match Report — {report.total:.0f}/100</title>
<style>
:root{{--bg:#fbfbfa;--fg:#1c1c1a;--mut:#6b6b66;--line:#e3e3df;--card:#fff;
--good:#2f7d55;--mid:#b5760a;--bad:#b3352c;}}
@media(prefers-color-scheme:dark){{:root{{--bg:#15161a;--fg:#e9e9e6;--mut:#9b9b95;
--line:#2c2e34;--card:#1d1f24;--good:#5fb98a;--mid:#e0a13c;--bad:#e0685e;}}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,sans-serif;padding:28px 18px}}
.wrap{{max-width:920px;margin:0 auto}}
h1{{font-size:20px;margin:0 0 4px}} h2{{font-size:15px;margin:30px 0 10px;letter-spacing:.02em;text-transform:uppercase;color:var(--mut)}}
.hero{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px 22px}}
.score{{font-size:46px;font-weight:650;line-height:1}}
.score.good{{color:var(--good)}}.score.mid{{color:var(--mid)}}.score.bad{{color:var(--bad)}}
.meta{{color:var(--mut);font-size:13px;margin-top:8px}}
table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}}
td,th{{padding:9px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:middle}}
tr:last-child td{{border-bottom:none}}
.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
.note{{color:var(--mut);font-size:12.5px}}
.bar{{background:var(--line);border-radius:5px;height:8px;width:110px;overflow:hidden}}
.bar i{{display:block;height:100%}}
.bar .good{{background:var(--good)}}.bar .mid{{background:var(--mid)}}.bar .bad{{background:var(--bad)}}
ul{{padding-left:0;list-style:none;margin:0}}
li{{background:var(--card);border:1px solid var(--line);border-radius:9px;padding:10px 13px;margin-bottom:7px}}
.sev-blocker{{border-left:4px solid var(--bad)}}.sev-major{{border-left:4px solid var(--mid)}}
.sev-minor{{border-left:4px solid var(--line)}}
.pass{{border-left:4px solid var(--good)}}.fail{{border-left:4px solid var(--bad)}}
.fix{{color:var(--mut);font-size:13px;margin-top:5px}}
.chip{{display:inline-block;background:var(--card);border:1px solid var(--line);border-radius:999px;
padding:3px 11px;margin:0 5px 6px 0;font-size:13px}}
.chip.ok{{border-color:var(--good);color:var(--good)}}
ol{{padding-left:20px}} ol li{{margin-bottom:7px}}
.foot{{color:var(--mut);font-size:12.5px;margin-top:26px;border-top:1px solid var(--line);padding-top:14px}}
@media(max-width:620px){{.bar{{width:60px}}.note{{display:none}}}}
</style></head><body><div class="wrap">
<div class="hero">
  <div class="score {band_cls}">{report.total:.0f}<span style="font-size:18px;color:var(--mut)">/100</span></div>
  <h1>{e(report.band)} match — {e(d['job_title'] or 'the posting')}</h1>
  <div class="meta">{e(report.verdict)}</div>
  <div class="meta">Resume: {e(str(d['resume']))} · Generated {e(d['generated'])}</div>
</div>
<h2>Score breakdown</h2>
<table><tr><th>Component</th><th class="num">Score</th><th></th><th class="num">Points</th><th class="note">Notes</th></tr>{comp_rows()}</table>
{f'<h2>Hard requirements</h2><ul>{gates}</ul>' if gates else ''}
{f'<h2>Parsing audit</h2><ul>{findings}</ul>' if findings else ''}
{f'<h2>Missing keywords</h2><div>{missing}</div>' if missing else ''}
{f'<h2>Matched keywords</h2><div>{matched}</div>' if matched else ''}
{f'<h2>What to fix, in order</h2><ol>{steps}</ol>' if steps else ''}
<div class="foot">Estimated from resume and posting text only. No ATS vendor publishes its
thresholds, and behaviour differs between products — use this to compare drafts of your own
resume against one posting, not as a prediction of any specific system's decision.</div>
</div></body></html>"""
