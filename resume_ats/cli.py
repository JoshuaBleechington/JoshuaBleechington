"""Command line interface."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional, Sequence

from . import __version__
from .aliases import default_lexicon
from .extract import Document, ExtractionError, extract, from_string
from .jd import parse as parse_jd
from .report import render_html, render_json, render_markdown, render_terminal
from .score import ScoreReport, score as run_score

EPILOG = """\
examples:
  resume-ats score resume.docx job.txt
  resume-ats score resume.pdf --jd-text "$(pbpaste)" --format markdown -o report.md
  resume-ats score resume.docx job.txt --format html -o report.html
  resume-ats audit resume.docx
  resume-ats compare v1.docx v2.docx v3.docx --jd job.txt
  resume-ats keywords job.txt --top 40
"""


def _read_source(path: Optional[str], text: Optional[str], label: str) -> str:
    if text is not None:
        return text
    if path in ("-", None):
        if sys.stdin.isatty():
            raise SystemExit(f"error: no {label} provided (pass a file path, --{label}-text, or pipe stdin)")
        return sys.stdin.read()
    doc = extract(path)
    for warning in doc.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    return doc.text


def _load_resume(path: Optional[str], text: Optional[str]) -> Document:
    if text is not None:
        return from_string(text, "<--resume-text>")
    if path in ("-", None):
        if sys.stdin.isatty():
            raise SystemExit("error: no resume provided")
        return from_string(sys.stdin.read(), "<stdin>")
    return extract(path)


def _emit(text: str, out: Optional[str]) -> None:
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"wrote {out}", file=sys.stderr)
    else:
        print(text)


def _render(report: ScoreReport, fmt: str, color: bool, verbose: bool) -> str:
    if fmt == "json":
        return render_json(report)
    if fmt == "markdown":
        return render_markdown(report)
    if fmt == "html":
        return render_html(report)
    return render_terminal(report, color=color, verbose=verbose)


def cmd_score(args: argparse.Namespace) -> int:
    lexicon = default_lexicon()
    if args.aliases:
        lexicon.load_extra(args.aliases)

    document = _load_resume(args.resume, args.resume_text)
    jd_text = _read_source(args.jd, args.jd_text, "jd")
    jd = parse_jd(jd_text, lexicon)
    if args.title:
        jd.title = args.title

    report = run_score(document, jd, lexicon)
    color = sys.stdout.isatty() and not args.no_color and not args.output
    _emit(_render(report, args.format, color, args.verbose), args.output)

    if args.min_score is not None and report.total < args.min_score:
        print(
            f"score {report.total:.1f} is below the --min-score threshold of {args.min_score}",
            file=sys.stderr,
        )
        return 2
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    """Format-only check: no job description needed."""
    from .parseability import audit as run_audit
    from .resume import parse as parse_resume

    document = _load_resume(args.resume, None)
    resume = parse_resume(document.text)
    result = run_audit(document, resume)

    if args.format == "json":
        payload = {
            "file": document.source,
            "kind": document.kind,
            "extractor": document.extractor,
            "words": document.word_count,
            "parse_score": result.score,
            "sections_found": resume.section_order,
            "roles_found": len(resume.roles),
            "years_experience": resume.years_experience,
            "contact": {
                "email": resume.contact.email,
                "phone": resume.contact.phone,
                "linkedin": resume.contact.linkedin,
                "name": resume.contact.name_guess,
            },
            "findings": [
                {"severity": f.severity, "code": f.code, "message": f.message, "fix": f.fix}
                for f in result.sorted_findings()
            ],
        }
        _emit(json.dumps(payload, indent=2), args.output)
        return 0 if result.count("blocker") == 0 else 2

    lines: List[str] = []
    lines.append(f"ATS PARSE AUDIT — {document.source}")
    lines.append("─" * 72)
    lines.append(f"Format: {document.kind}   Reader: {document.extractor}   Words: {document.word_count}")
    lines.append(f"Parse-safety score: {result.score:.0f}/100")
    lines.append(f"Sections detected: {', '.join(resume.section_order) or 'none'}")
    lines.append(f"Positions detected: {len(resume.roles)}   Experience evidenced: {resume.years_experience} years")
    contact = resume.contact
    lines.append(
        f"Contact parsed: name={contact.name_guess or '-'} email={contact.email or '-'} "
        f"phone={contact.phone or '-'}"
    )
    lines.append("")
    if not result.findings:
        lines.append("No parsing problems detected.")
    for finding in result.sorted_findings():
        lines.append(f"  [{finding.severity.upper():<7}] {finding.message}")
        if finding.fix:
            lines.append(f"            -> {finding.fix}")
    lines.append("")
    lines.append("This checks whether an ATS can read the file. It says nothing about")
    lines.append("how well the content matches any particular job.")
    _emit("\n".join(lines), args.output)
    return 0 if result.count("blocker") == 0 else 2


def cmd_keywords(args: argparse.Namespace) -> int:
    """Show what the tool mined from a posting, and how it weighted it."""
    lexicon = default_lexicon()
    if args.aliases:
        lexicon.load_extra(args.aliases)
    jd_text = _read_source(args.jd, args.jd_text, "jd")
    jd = parse_jd(jd_text, lexicon)

    if args.format == "json":
        payload = {
            "title": jd.title,
            "min_years": jd.min_years,
            "min_degree": jd.min_degree,
            "clearance": jd.clearance,
            "terms": [
                {"term": r.display, "weight": round(r.weight, 2), "count": r.count,
                 "required": r.required, "preferred": r.preferred,
                 "known_skill": r.known_skill, "category": r.category}
                for r in jd.top(args.top)
            ],
        }
        _emit(json.dumps(payload, indent=2), args.output)
        return 0

    lines = [f"POSTING: {jd.title or '(title not detected)'}", "─" * 72]
    if jd.min_years:
        lines.append(f"Minimum experience: {jd.min_years:.0f} years")
    if jd.min_degree:
        lines.append(f"Minimum education:  {jd.min_degree}")
    if jd.clearance:
        lines.append(f"Clearance:          {jd.clearance}")
    lines.append("")
    lines.append(f"{'weight':>7}  {'req':>3} {'pref':>4}  term")
    for req in jd.top(args.top):
        lines.append(
            f"{req.weight:7.2f}  {'y' if req.required else '-':>3} "
            f"{'y' if req.preferred else '-':>4}  {req.display}"
        )
    _emit("\n".join(lines), args.output)
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    """Score several resume versions against one posting, best first."""
    lexicon = default_lexicon()
    if args.aliases:
        lexicon.load_extra(args.aliases)
    jd_text = _read_source(args.jd, args.jd_text, "jd")
    jd = parse_jd(jd_text, lexicon)

    rows = []
    for path in args.resumes:
        try:
            document = extract(path)
        except ExtractionError as exc:
            print(f"skipping {path}: {exc}", file=sys.stderr)
            continue
        report = run_score(document, jd, lexicon)
        rows.append((report.total, os.path.basename(path), report))

    if not rows:
        print("no resumes could be read", file=sys.stderr)
        return 1
    rows.sort(key=lambda r: -r[0])

    if args.format == "json":
        _emit(json.dumps([
            {"file": name, "total": total, "band": rep.band,
             "components": {c.name: round(c.score, 1) for c in rep.components}}
            for total, name, rep in rows
        ], indent=2), args.output)
        return 0

    names = [n for _, n, _ in rows]
    pad = max(len(n) for n in names)
    comp_names = [c.name for c in rows[0][2].components]
    header = f"{'resume'.ljust(pad)}  total  " + "  ".join(c[:5].rjust(5) for c in comp_names)
    lines = [f"COMPARING {len(rows)} VERSIONS AGAINST: {jd.title or 'the posting'}", "─" * len(header), header]
    for total, name, rep in rows:
        scores = "  ".join(f"{c.score:5.0f}" for c in rep.components)
        lines.append(f"{name.ljust(pad)}  {total:5.1f}  {scores}")
    lines.append("")
    lines.append(f"Best: {rows[0][1]} ({rows[0][0]:.1f}, {rows[0][2].band})")
    _emit("\n".join(lines), args.output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="resume-ats",
        description="Score a resume against a job description the way an applicant "
                    "tracking system would.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"resume-ats {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("-o", "--output", help="write to a file instead of stdout")
        p.add_argument("--aliases", help="extra alias JSON file to merge into the lexicon")

    p_score = sub.add_parser("score", help="score a resume against a job description")
    p_score.add_argument("resume", nargs="?", help="resume file (.docx, .pdf, .txt, .md) or - for stdin")
    p_score.add_argument("jd", nargs="?", help="job description file, or - for stdin")
    p_score.add_argument("--resume-text", help="pass resume text directly")
    p_score.add_argument("--jd-text", help="pass job description text directly")
    p_score.add_argument("--title", help="override the detected job title")
    p_score.add_argument("-f", "--format", default="text",
                         choices=["text", "markdown", "json", "html"])
    p_score.add_argument("-v", "--verbose", action="store_true", help="show job-description context for gaps")
    p_score.add_argument("--no-color", action="store_true")
    p_score.add_argument("--min-score", type=float,
                         help="exit with status 2 if the score is below this value")
    add_common(p_score)
    p_score.set_defaults(func=cmd_score)

    p_audit = sub.add_parser("audit", help="check a resume's ATS-readability (no job description)")
    p_audit.add_argument("resume", nargs="?", help="resume file or - for stdin")
    p_audit.add_argument("-f", "--format", default="text", choices=["text", "json"])
    add_common(p_audit)
    p_audit.set_defaults(func=cmd_audit)

    p_kw = sub.add_parser("keywords", help="show the weighted terms mined from a posting")
    p_kw.add_argument("jd", nargs="?", help="job description file or - for stdin")
    p_kw.add_argument("--jd-text", help="pass job description text directly")
    p_kw.add_argument("--top", type=int, default=40)
    p_kw.add_argument("-f", "--format", default="text", choices=["text", "json"])
    add_common(p_kw)
    p_kw.set_defaults(func=cmd_keywords)

    p_cmp = sub.add_parser("compare", help="rank several resume versions against one posting")
    p_cmp.add_argument("resumes", nargs="+", help="resume files to compare")
    p_cmp.add_argument("--jd", required=False, help="job description file")
    p_cmp.add_argument("--jd-text", help="pass job description text directly")
    p_cmp.add_argument("-f", "--format", default="text", choices=["text", "json"])
    add_common(p_cmp)
    p_cmp.set_defaults(func=cmd_compare)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except ExtractionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except BrokenPipeError:
        return 0
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
