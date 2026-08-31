"""Write a minimal, parser-friendly .docx using only the standard library.

The reader in ``extract.py`` deliberately avoids a helper library so it can see
the layout constructs that break ATS parsers.  The writer does the same, for a
different reason: a resume tool that needs a third-party dependency to produce
its main output is one ``pip install`` away from being useless, and the subset
of OOXML a clean resume needs is small.

Everything here is chosen to survive parsing: one column, no tables, no text
boxes, no headers or footers, no images, and real numbered bullets so a parser
reads them as list items rather than prose.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from typing import List, Optional, Sequence
from xml.sax.saxutils import escape

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
_PKG_R = "http://schemas.openxmlformats.org/package/2006/relationships"

BULLET_NUM_ID = 1

# US Letter in twentieths of a point; 1440 = one inch.
PAGE_WIDTH = 12240
PAGE_HEIGHT = 15840
MARGIN = 720


@dataclass
class Run:
    text: str
    bold: bool = False
    italic: bool = False
    size: Optional[int] = None      # half-points
    color: Optional[str] = None


@dataclass
class Block:
    """One paragraph: either body text, a heading, or a bullet."""

    runs: List[Run] = field(default_factory=list)
    kind: str = "body"              # body | heading | bullet
    space_before: int = 0
    space_after: int = 40
    rule_below: bool = False


def text_block(text: str, **kw) -> Block:
    return Block(runs=[Run(text, **{k: v for k, v in kw.items()
                                    if k in ("bold", "italic", "size", "color")})],
                 **{k: v for k, v in kw.items()
                    if k in ("kind", "space_before", "space_after", "rule_below")})


def _xml_escape(text: str) -> str:
    # Strip control characters that are illegal in XML 1.0 regardless of escaping.
    cleaned = "".join(c for c in text if c >= " " or c in "\t")
    return escape(cleaned)


def _run_xml(run: Run) -> str:
    props = []
    if run.bold:
        props.append("<w:b/>")
    if run.italic:
        props.append("<w:i/>")
    if run.color:
        props.append(f'<w:color w:val="{run.color}"/>')
    if run.size:
        props.append(f'<w:sz w:val="{run.size}"/><w:szCs w:val="{run.size}"/>')
    rpr = f"<w:rPr>{''.join(props)}</w:rPr>" if props else ""
    # xml:space="preserve" keeps leading and trailing spaces meaningful.
    return f'<w:r>{rpr}<w:t xml:space="preserve">{_xml_escape(run.text)}</w:t></w:r>'


def _block_xml(block: Block) -> str:
    props = [f'<w:spacing w:before="{block.space_before}" w:after="{block.space_after}"/>']
    if block.kind == "bullet":
        props.insert(0, f'<w:numPr><w:ilvl w:val="0"/><w:numId w:val="{BULLET_NUM_ID}"/></w:numPr>')
        props.append('<w:ind w:left="360" w:hanging="220"/>')
    if block.rule_below:
        props.append('<w:pBdr><w:bottom w:val="single" w:sz="6" w:space="2" w:color="444444"/></w:pBdr>')
    if block.kind == "heading":
        props.append('<w:outlineLvl w:val="0"/>')
    ppr = f"<w:pPr>{''.join(props)}</w:pPr>"
    return f"<w:p>{ppr}{''.join(_run_xml(r) for r in block.runs)}</w:p>"


def _document_xml(blocks: Sequence[Block]) -> str:
    body = "".join(_block_xml(b) for b in blocks)
    sect = (
        f'<w:sectPr><w:pgSz w:w="{PAGE_WIDTH}" w:h="{PAGE_HEIGHT}"/>'
        f'<w:pgMar w:top="{MARGIN}" w:right="{MARGIN}" w:bottom="{MARGIN}" w:left="{MARGIN}"'
        ' w:header="0" w:footer="0" w:gutter="0"/>'
        '<w:cols w:num="1" w:space="0"/></w:sectPr>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{W_NS}"><w:body>{body}{sect}</w:body></w:document>'
    )


def _styles_xml(font: str, size: int) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:styles xmlns:w="{W_NS}"><w:docDefaults><w:rPrDefault><w:rPr>'
        f'<w:rFonts w:ascii="{font}" w:hAnsi="{font}" w:cs="{font}"/>'
        f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>'
        '</w:rPr></w:rPrDefault><w:pPrDefault><w:pPr>'
        '<w:spacing w:after="40" w:line="240" w:lineRule="auto"/>'
        '</w:pPr></w:pPrDefault></w:docDefaults>'
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
        '<w:name w:val="Normal"/></w:style></w:styles>'
    )


def _numbering_xml(font: str) -> str:
    """A single bullet list definition.

    The bullet glyph lives here as a numbering property, not as text in the
    document, which is what makes a parser read these paragraphs as list items.
    """
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:numbering xmlns:w="{W_NS}">'
        '<w:abstractNum w:abstractNumId="0"><w:multiLevelType w:val="hybridMultilevel"/>'
        '<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/>'
        '<w:lvlText w:val="•"/><w:lvlJc w:val="left"/>'
        '<w:pPr><w:ind w:left="360" w:hanging="220"/></w:pPr>'
        '<w:rPr><w:rFonts w:ascii="Symbol" w:hAnsi="Symbol" w:hint="default"/></w:rPr>'
        '</w:lvl></w:abstractNum>'
        f'<w:num w:numId="{BULLET_NUM_ID}"><w:abstractNumId w:val="0"/></w:num>'
        '</w:numbering>'
    )


_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<Types xmlns="{_CT}">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
    '<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>'
    '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
    '</Types>'
)

_ROOT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<Relationships xmlns="{_PKG_R}">'
    f'<Relationship Id="rId1" Type="{_R}/officeDocument" Target="word/document.xml"/>'
    '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
    '</Relationships>'
)

_DOC_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<Relationships xmlns="{_PKG_R}">'
    f'<Relationship Id="rId1" Type="{_R}/styles" Target="styles.xml"/>'
    f'<Relationship Id="rId2" Type="{_R}/numbering" Target="numbering.xml"/>'
    '</Relationships>'
)


def _core_xml(title: str, author: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties '
        'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f'<dc:title>{_xml_escape(title)}</dc:title>'
        f'<dc:creator>{_xml_escape(author)}</dc:creator>'
        '</cp:coreProperties>'
    )


def write_docx(
    path: str,
    blocks: Sequence[Block],
    *,
    title: str = "Resume",
    author: str = "",
    font: str = "Calibri",
    size: int = 20,
) -> str:
    """Write the blocks to ``path`` as a .docx and return the path."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES)
        zf.writestr("_rels/.rels", _ROOT_RELS)
        zf.writestr("docProps/core.xml", _core_xml(title, author))
        zf.writestr("word/_rels/document.xml.rels", _DOC_RELS)
        zf.writestr("word/document.xml", _document_xml(blocks))
        zf.writestr("word/styles.xml", _styles_xml(font, size))
        zf.writestr("word/numbering.xml", _numbering_xml(font))
    return path
