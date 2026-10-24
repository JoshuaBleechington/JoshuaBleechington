"""Assemble web/callsheet2.html from its three parts.

    python3 tools_build_callsheet2.py

The page is head + Call Sheet #1's ENGINE BLOCK (copied verbatim out of
web/fullgame.html, between its two sentinel comments) + tail. The engine is
copied rather than linked because an artifact is one file, and it is copied
by this script rather than by hand because a hand copy is the thing that
drifts. The browser harness asserts the two copies are byte-identical.
"""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).parent / "web"
OPEN = "  /* ===== ENGINE BLOCK."
CLOSE = "  /* ===== END ENGINE BLOCK ===== */"


def engine_block() -> str:
    src = (ROOT / "fullgame.html").read_text().split("\n")
    start = next(i for i, l in enumerate(src) if l.startswith(OPEN))
    end = next(i for i, l in enumerate(src) if l.startswith(CLOSE))
    return "\n".join(src[start:end + 1]) + "\n"


def build() -> str:
    head = (ROOT / "callsheet2.head.html").read_text()
    tail = (ROOT / "callsheet2.tail.js").read_text()
    return head + engine_block() + tail


if __name__ == "__main__":
    out = ROOT / "callsheet2.html"
    out.write_text(build())
    print(f"wrote {out} ({out.stat().st_size:,} bytes)")
