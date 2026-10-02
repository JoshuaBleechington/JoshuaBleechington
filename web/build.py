"""Assemble the single-file browser page from its three sources.

    python web/build.py            -> web/ats-screening-bench.html
    python web/build.py --preview  -> also web/preview.html, wrapped in a
                                      document skeleton for local browser tests

The page is published as an Artifact, which supplies its own <html>/<body>
wrapper, so the built file deliberately starts at <title>. The engine is a
hand port of the resume_ats package; keep the two in step (tests/parity).
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PDFJS = '<script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>'


def build() -> str:
    head = (HERE / "head.html").read_text(encoding="utf-8")
    engine = (HERE / "engine.js").read_text(encoding="utf-8")
    ui = (HERE / "ui.js").read_text(encoding="utf-8")
    return head + PDFJS + "\n<script>\n" + engine + "\n" + ui + "</script>"


def main() -> None:
    page = build()
    (HERE / "ats-screening-bench.html").write_text(page, encoding="utf-8")
    print(f"wrote web/ats-screening-bench.html ({len(page):,} bytes)")
    if "--preview" in sys.argv:
        wrapped = ('<!doctype html><html><head><meta charset="utf-8">'
                   '<meta name="viewport" content="width=device-width, initial-scale=1">'
                   '<style>body{margin:0}[hidden]{display:none!important}</style></head><body>\n'
                   + page + "\n</body></html>")
        (HERE / "preview.html").write_text(wrapped, encoding="utf-8")
        print("wrote web/preview.html")


if __name__ == "__main__":
    main()
