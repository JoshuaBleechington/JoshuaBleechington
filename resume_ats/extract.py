"""Turn a resume file into text *plus* a structural fingerprint.

The structural part matters as much as the text.  A resume laid out in a table
or a text box often reads perfectly to a human and arrives at the ATS as
scrambled fragments or nothing at all.  ``.docx`` is a zip of XML, so we read
it directly with the standard library rather than through a helper library --
that is the only way to see the constructs (tables, text boxes, headers,
columns, floating images) that actually cause parse failures.
"""

from __future__ import annotations

import io
import os
import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
WPS = "{http://schemas.microsoft.com/office/word/2010/wordprocessingShape}"


@dataclass
class Document:
    """Extracted text and the layout facts we care about."""

    text: str
    source: str
    kind: str = "txt"
    # Structural signals; ``None`` means "we could not tell for this format".
    tables: Optional[int] = None
    table_text_chars: int = 0
    text_boxes: Optional[int] = None
    text_box_chars: int = 0
    header_footer_chars: int = 0
    images: Optional[int] = None
    columns: Optional[int] = None
    pages: Optional[int] = None
    fonts: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    extractor: str = "plain"

    @property
    def word_count(self) -> int:
        return len(self.text.split())


class ExtractionError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# DOCX
# --------------------------------------------------------------------------

def _para_text(node: ET.Element) -> str:
    """Concatenate the runs of a paragraph, honouring tabs and breaks."""
    out: List[str] = []
    for child in node.iter():
        tag = child.tag
        if tag == W + "t":
            out.append(child.text or "")
        elif tag == W + "tab":
            out.append("\t")
        elif tag in (W + "br", W + "cr"):
            out.append("\n")
    return "".join(out)


def _is_list_paragraph(para: ET.Element) -> bool:
    """True if Word marks this paragraph as a numbered or bulleted list item.

    A correctly built Word bullet stores the glyph as a numbering property, not
    as text, so nothing in the run content looks like a bullet.  Real parsers
    read the numbering; so must we, or the properly formatted resume we tell
    people to write scores as having no bullet points at all.
    """
    props = para.find(W + "pPr")
    return props is not None and props.find(W + "numPr") is not None


def _iter_block_text(root: ET.Element) -> List[str]:
    """Walk body-level blocks in document order, flattening tables to rows."""
    blocks: List[str] = []

    def walk(node: ET.Element) -> None:
        for child in node:
            if child.tag == W + "p":
                text = _para_text(child)
                if text.strip() and _is_list_paragraph(child):
                    # Normalise to a literal marker so the rest of the pipeline
                    # sees a bullet regardless of how it was authored.
                    text = "- " + text.lstrip()
                blocks.append(text)
            elif child.tag == W + "tbl":
                for row in child.findall(W + "tr"):
                    cells = []
                    for cell in row.findall(W + "tc"):
                        parts = [_para_text(p) for p in cell.findall(W + "p")]
                        cells.append(" ".join(x.strip() for x in parts if x.strip()))
                    line = "  ".join(c for c in cells if c)
                    if line.strip():
                        blocks.append(line)
            elif child.tag in (W + "sdt", W + "sdtContent", W + "body"):
                walk(child)

    walk(root)
    return blocks


def extract_docx(path: str) -> Document:
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:  # .doc renamed to .docx is common
        raise ExtractionError(
            f"{os.path.basename(path)} is not a valid .docx (legacy .doc files "
            "must be re-saved as .docx)"
        ) from exc

    with zf:
        names = set(zf.namelist())
        if "word/document.xml" not in names:
            raise ExtractionError("missing word/document.xml -- not a Word document")
        raw = zf.read("word/document.xml")
        root = ET.fromstring(raw)
        body = root.find(W + "body")
        blocks = _iter_block_text(body if body is not None else root)
        text = "\n".join(blocks)

        tables = len(list(root.iter(W + "tbl")))
        table_chars = 0
        for tbl in root.iter(W + "tbl"):
            table_chars += sum(len(_para_text(p)) for p in tbl.iter(W + "p"))

        boxes = len(list(root.iter(WPS + "txbx"))) + len(list(root.iter(W + "txbxContent")))
        box_chars = 0
        for box in root.iter(W + "txbxContent"):
            box_chars += sum(len(_para_text(p)) for p in box.iter(W + "p"))

        # Multi-column sections are a top cause of interleaved-text parse errors.
        columns = 1
        for cols in root.iter(W + "cols"):
            try:
                columns = max(columns, int(cols.get(W + "num", "1")))
            except (TypeError, ValueError):
                pass

        images = sum(1 for n in names if n.startswith("word/media/"))

        hf_chars = 0
        for name in names:
            if re.match(r"word/(header|footer)\d*\.xml$", name):
                try:
                    hf_root = ET.fromstring(zf.read(name))
                except ET.ParseError:
                    continue
                hf_chars += sum(len(_para_text(p)) for p in hf_root.iter(W + "p"))

        fonts: List[str] = []
        if "word/fontTable.xml" in names:
            try:
                ft = ET.fromstring(zf.read("word/fontTable.xml"))
                fonts = [f.get(W + "name", "") for f in ft.iter(W + "font")]
                fonts = [f for f in fonts if f]
            except ET.ParseError:
                pass

    doc = Document(
        text=text,
        source=path,
        kind="docx",
        tables=tables,
        table_text_chars=table_chars,
        text_boxes=boxes,
        text_box_chars=box_chars,
        header_footer_chars=hf_chars,
        images=images,
        columns=columns,
        fonts=fonts,
        extractor="stdlib-ooxml",
    )
    return doc


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------

def extract_pdf(path: str) -> Document:
    """Extract PDF text with pdfminer.six when present, else degrade honestly."""
    warnings: List[str] = []
    text = ""
    pages = None
    extractor = "none"
    try:
        from pdfminer.high_level import extract_text as _pm_text  # type: ignore
        from pdfminer.pdfpage import PDFPage  # type: ignore

        text = _pm_text(path) or ""
        extractor = "pdfminer.six"
        with open(path, "rb") as fh:
            pages = sum(1 for _ in PDFPage.get_pages(fh))
    except ImportError:
        warnings.append(
            "pdfminer.six is not installed, so PDF text could not be read. "
            "Install it with: pip install pdfminer.six"
        )
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as exc:
        # Deliberately broader than Exception. pdfminer pulls in `cryptography`,
        # whose Rust bindings raise pyo3 PanicException -- a BaseException -- if
        # the native module is broken or mismatched. A missing or broken
        # optional dependency must degrade to a warning, never take down a run
        # that also has perfectly readable .docx files in it.
        warnings.append(
            f"PDF text extraction failed ({type(exc).__name__}: {exc}). "
            "Try: pip install --upgrade pdfminer.six cryptography -- or export "
            "the resume as .docx and scan that instead."
        )

    with open(path, "rb") as fh:
        raw = fh.read()
    images = len(re.findall(rb"/Subtype\s*/Image", raw))
    if pages is None:
        pages = max(1, len(re.findall(rb"/Type\s*/Page[^s]", raw)))

    if extractor != "none" and len(text.strip()) < 200 and len(raw) > 20000:
        warnings.append(
            "Almost no selectable text was recovered. This resume is probably a "
            "scan or an image export -- most ATS parsers will read it as blank."
        )

    return Document(
        text=text,
        source=path,
        kind="pdf",
        images=images,
        pages=pages,
        warnings=warnings,
        extractor=extractor,
    )


# --------------------------------------------------------------------------
# Plain text / markdown
# --------------------------------------------------------------------------

def extract_text_file(path: str) -> Document:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    kind = "md" if path.lower().endswith((".md", ".markdown")) else "txt"
    return Document(text=text, source=path, kind=kind, extractor="plain")


_DISPATCH: Dict[str, object] = {
    ".docx": extract_docx,
    ".pdf": extract_pdf,
    ".txt": extract_text_file,
    ".md": extract_text_file,
    ".markdown": extract_text_file,
    ".rtf": None,
    ".doc": None,
    ".pages": None,
}


def extract(path: str) -> Document:
    """Extract a Document from a path, choosing the reader by extension."""
    if not os.path.exists(path):
        raise ExtractionError(f"file not found: {path}")
    ext = os.path.splitext(path)[1].lower()
    if ext in _DISPATCH and _DISPATCH[ext] is None:
        raise ExtractionError(
            f"{ext} is not a format applicant tracking systems reliably parse. "
            "Re-save as .docx or a text-based .pdf and try again."
        )
    fn = _DISPATCH.get(ext)
    if fn is None:
        # Unknown extension: try to read it as text before giving up.
        try:
            return extract_text_file(path)
        except UnicodeDecodeError as exc:
            raise ExtractionError(f"unsupported file type: {ext or path}") from exc
    return fn(path)  # type: ignore[operator]


def from_string(text: str, name: str = "<stdin>") -> Document:
    return Document(text=text, source=name, kind="txt", extractor="plain")
