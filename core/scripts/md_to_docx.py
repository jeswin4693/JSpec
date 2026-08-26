"""Markdown -> .docx, using only the Python standard library.

A .docx is a zip of XML parts, so `zipfile` plus string templating is enough. This
exists instead of python-docx or pandoc because neither is installed and D-013 says the
system Python stays untouched - a document generator is not worth a dependency.

Supports the subset this project's markdown actually uses: ATX headings, paragraphs with
bold / italic / inline code, bullet and numbered lists, task-list checkboxes, pipe
tables, fenced code blocks, blockquotes and horizontal rules.

Usage:
    python core/scripts/md_to_docx.py OUT.docx TITLE IN1.md [IN2.md ...]
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'

# --- static parts ----------------------------------------------------------------

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
</Types>"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
</Relationships>"""

DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>
</Relationships>"""


def _style(
    sid: str,
    name: str,
    *,
    size: int,
    bold: bool = False,
    color: str = "1F2430",
    before: int = 0,
    after: int = 120,
    mono: bool = False,
    outline: int | None = None,
    keep: bool = False,
) -> str:
    """One paragraph style. `size` is half-points, Word's unit."""
    font = "Consolas" if mono else "Calibri"
    heading = "" if outline is None else f'<w:outlineLvl w:val="{outline}"/>'
    keepnext = "<w:keepNext/><w:keepLines/>" if keep else ""
    return (
        f'<w:style w:type="paragraph" w:styleId="{sid}">'
        f'<w:name w:val="{name}"/><w:basedOn w:val="Normal"/><w:qFormat/>'
        f"<w:pPr>{keepnext}"
        f'<w:spacing w:before="{before}" w:after="{after}" w:line="276" w:lineRule="auto"/>'
        f"{heading}</w:pPr>"
        f'<w:rPr><w:rFonts w:ascii="{font}" w:hAnsi="{font}"/>'
        f'{"<w:b/>" if bold else ""}<w:color w:val="{color}"/><w:sz w:val="{size}"/></w:rPr>'
        "</w:style>"
    )


STYLES = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles {W}>
<w:docDefaults><w:rPrDefault><w:rPr>
<w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="21"/><w:szCs w:val="21"/>
</w:rPr></w:rPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/>
<w:pPr><w:spacing w:after="140" w:line="288" w:lineRule="auto"/></w:pPr>
<w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:color w:val="1F2430"/><w:sz w:val="21"/></w:rPr></w:style>
{_style("Title", "Title", size=56, bold=True, color="14171F", after=60)}
{_style("Subtitle", "Subtitle", size=24, color="5C6472", after=360)}
{_style("Heading1", "heading 1", size=36, bold=True, color="14171F", before=400, after=160, outline=0, keep=True)}
{_style("Heading2", "heading 2", size=28, bold=True, color="2B4C8C", before=320, after=120, outline=1, keep=True)}
{_style("Heading3", "heading 3", size=23, bold=True, color="14171F", before=240, after=100, outline=2, keep=True)}
{_style("Code", "Code Block", size=18, mono=True, color="24292F", before=60, after=140)}
{_style("Quote", "Quote", size=21, color="5C6472", before=60, after=140)}
<w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/>
<w:basedOn w:val="Normal"/><w:qFormat/>
<w:pPr><w:spacing w:after="80" w:line="276" w:lineRule="auto"/><w:contextualSpacing/></w:pPr></w:style>
<w:style w:type="character" w:styleId="InlineCode"><w:name w:val="Inline Code"/><w:qFormat/>
<w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:color w:val="9B2C6F"/><w:sz w:val="19"/></w:rPr></w:style>
<w:style w:type="table" w:styleId="JTable"><w:name w:val="JSpec Table"/><w:qFormat/>
<w:tblPr><w:tblBorders>
<w:top w:val="single" w:sz="4" w:color="C9CFDA"/><w:left w:val="single" w:sz="4" w:color="C9CFDA"/>
<w:bottom w:val="single" w:sz="4" w:color="C9CFDA"/><w:right w:val="single" w:sz="4" w:color="C9CFDA"/>
<w:insideH w:val="single" w:sz="4" w:color="C9CFDA"/><w:insideV w:val="single" w:sz="4" w:color="C9CFDA"/>
</w:tblBorders><w:tblCellMar>
<w:top w:w="80" w:type="dxa"/><w:left w:w="120" w:type="dxa"/>
<w:bottom w:w="80" w:type="dxa"/><w:right w:w="120" w:type="dxa"/>
</w:tblCellMar></w:tblPr></w:style>
</w:styles>"""


def _abstract(aid: int, fmt: str, text: str, font: str | None) -> str:
    levels = []
    for lvl in range(3):
        indent = 360 + lvl * 360
        rpr = (
            f'<w:rPr><w:rFonts w:ascii="{font}" w:hAnsi="{font}" w:hint="default"/></w:rPr>'
            if font
            else ""
        )
        t = text if fmt == "bullet" else f"%{lvl + 1}."
        levels.append(
            f'<w:lvl w:ilvl="{lvl}"><w:start w:val="1"/><w:numFmt w:val="{fmt}"/>'
            f'<w:lvlText w:val="{t}"/><w:lvlJc w:val="left"/>'
            f'<w:pPr><w:ind w:left="{indent + 360}" w:hanging="360"/></w:pPr>{rpr}</w:lvl>'
        )
    return f'<w:abstractNum w:abstractNumId="{aid}">{"".join(levels)}</w:abstractNum>'


NUMBERING = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering {W}>
{_abstract(0, "bullet", "•", "Symbol")}
{_abstract(1, "decimal", "", None)}
<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>
<w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num>
</w:numbering>"""


def core_props(title: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"'
        ' xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f"<dc:title>{escape(title)}</dc:title><dc:creator>JSpec</dc:creator>"
        "</cp:coreProperties>"
    )


# --- inline formatting ------------------------------------------------------------

# Order matters: code first so ** inside backticks is left alone.
TOKEN = re.compile(r"(`[^`]+`|\*\*\*[^*]+\*\*\*|\*\*[^*]+\*\*|(?<!\*)\*(?!\*)[^*]+\*)")


def runs(text: str) -> str:
    """Markdown inline -> a sequence of <w:r> runs."""
    out = []
    for part in TOKEN.split(text):
        if not part:
            continue
        bold = italic = code = False
        if part.startswith("`") and part.endswith("`") and len(part) > 1:
            part, code = part[1:-1], True
        elif part.startswith("***") and part.endswith("***"):
            part, bold, italic = part[3:-3], True, True
        elif part.startswith("**") and part.endswith("**"):
            part, bold = part[2:-2], True
        elif part.startswith("*") and part.endswith("*") and len(part) > 1:
            part, italic = part[1:-1], True

        props = []
        if code:
            props.append('<w:rStyle w:val="InlineCode"/>')
        if bold:
            props.append("<w:b/>")
        if italic:
            props.append("<w:i/>")
        rpr = f"<w:rPr>{''.join(props)}</w:rPr>" if props else ""
        # Markdown link -> just its text; a Word hyperlink needs a relationship per link.
        part = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", part)
        out.append(f'<w:r>{rpr}<w:t xml:space="preserve">{escape(part)}</w:t></w:r>')
    return "".join(out)


def para(
    text: str, style: str | None = None, num: int | None = None, lvl: int = 0
) -> str:
    props = []
    if style:
        props.append(f'<w:pStyle w:val="{style}"/>')
    if num:
        props.append(
            f'<w:numPr><w:ilvl w:val="{lvl}"/><w:numId w:val="{num}"/></w:numPr>'
        )
    ppr = f"<w:pPr>{''.join(props)}</w:pPr>" if props else ""
    return f"<w:p>{ppr}{runs(text)}</w:p>"


def rule() -> str:
    return (
        "<w:p><w:pPr><w:spacing w:before='120' w:after='120'/><w:pBdr>"
        "<w:bottom w:val='single' w:sz='6' w:color='C9CFDA'/></w:pBdr></w:pPr></w:p>"
    ).replace("'", '"')


def table(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    head, *body = rows
    cols = max(len(r) for r in rows)

    def cell(txt: str, bold: bool) -> str:
        shade = '<w:shd w:val="clear" w:fill="EEF1F6"/>' if bold else ""
        body_txt = f"**{txt}**" if bold and txt and not txt.startswith("**") else txt
        return (
            f'<w:tc><w:tcPr><w:tcW w:w="0" w:type="auto"/>{shade}</w:tcPr>'
            f"{para(body_txt, 'ListParagraph')}</w:tc>"
        )

    def row(cells: list[str], bold: bool) -> str:
        padded = cells + [""] * (cols - len(cells))
        trpr = "<w:trPr><w:tblHeader/></w:trPr>" if bold else ""
        return f"<w:tr>{trpr}{''.join(cell(c, bold) for c in padded)}</w:tr>"

    return (
        '<w:tbl><w:tblPr><w:tblStyle w:val="JTable"/><w:tblW w:w="5000" w:type="pct"/>'
        '<w:tblLayout w:type="autofit"/></w:tblPr>'
        + row(head, True)
        + "".join(row(r, False) for r in body)
        + "</w:tbl>"
        + '<w:p><w:pPr><w:spacing w:after="80"/></w:pPr></w:p>'
    )


# --- block parsing ---------------------------------------------------------------

SPLIT_ROW = re.compile(r"^\s*\|?[\s:|-]+\|[\s:|-]*$")


def cells_of(line: str) -> list[str]:
    line = line.strip().strip("|")
    return [c.strip() for c in line.split("|")]


def convert(md: str) -> str:
    lines = md.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip()
        stripped = line.strip()

        # fenced code
        if stripped.startswith("```"):
            i += 1
            block = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block.append(lines[i])
                i += 1
            i += 1
            for b in block or [""]:
                out.append(
                    f'<w:p><w:pPr><w:pStyle w:val="Code"/></w:pPr>'
                    f'<w:r><w:t xml:space="preserve">{escape(b)}</w:t></w:r></w:p>'
                )
            continue

        # table: a header line followed by a separator line
        if "|" in stripped and i + 1 < len(lines) and SPLIT_ROW.match(lines[i + 1]):
            rows = [cells_of(stripped)]
            i += 2
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                rows.append(cells_of(lines[i]))
                i += 1
            out.append(table(rows))
            continue

        if not stripped:
            i += 1
            continue

        if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", stripped):
            out.append(rule())
            i += 1
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            depth = min(len(m.group(1)), 3)
            out.append(para(m.group(2), f"Heading{depth}"))
            i += 1
            continue

        if stripped.startswith("> "):
            out.append(para(stripped[2:], "Quote"))
            i += 1
            continue

        indent = len(raw) - len(raw.lstrip())
        lvl = min(indent // 2, 2)

        m = re.match(r"^[-*+]\s+(.*)$", stripped)
        if m:
            text = m.group(1)
            # task list -> a visible box, since Word has no markdown checkbox
            box = {"[x]": "☒ ", "[X]": "☒ ", "[ ]": "☐ ", "[~]": "▣ ", "[!]": "⚠ "}
            for k, v in box.items():
                if text.startswith(k):
                    text = v + text[len(k) :].lstrip()
                    break
            out.append(para(text, "ListParagraph", num=1, lvl=lvl))
            i += 1
            continue

        m = re.match(r"^\d+[.)]\s+(.*)$", stripped)
        if m:
            out.append(para(m.group(1), "ListParagraph", num=2, lvl=lvl))
            i += 1
            continue

        # plain paragraph: join soft-wrapped lines
        buf = [stripped]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if (
                not nxt
                or nxt.startswith(("#", "> ", "```", "|"))
                or re.match(r"^([-*+]\s|\d+[.)]\s)", nxt)
                or re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", nxt)
            ):
                break
            buf.append(nxt)
            i += 1
        out.append(para(" ".join(buf)))

    return "".join(out)


def build(out_path: Path, title: str, subtitle: str, sources: list[Path]) -> None:
    body = [para(title, "Title"), para(subtitle, "Subtitle")]
    for src in sources:
        body.append(convert(src.read_text(encoding="utf-8")))

    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<w:document {W}><w:body>"
        + "".join(body)
        + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"'
        ' w:header="708" w:footer="708" w:gutter="0"/></w:sectPr>'
        "</w:body></w:document>"
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", ROOT_RELS)
        z.writestr("docProps/core.xml", core_props(title))
        z.writestr("word/_rels/document.xml.rels", DOC_RELS)
        z.writestr("word/styles.xml", STYLES)
        z.writestr("word/numbering.xml", NUMBERING)
        z.writestr("word/document.xml", document)


def main() -> None:
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    out, title, *srcs = sys.argv[1:]
    sub = "JSpec · generated from the markdown sources in this repository"
    build(Path(out), title, sub, [Path(s) for s in srcs])
    print(f"wrote {out} ({Path(out).stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
