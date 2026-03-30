#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


FONT_MAIN_CANDIDATES = [
    ("/System/Library/Fonts/Supplemental/Songti.ttc", 6),
    ("/System/Library/Fonts/Supplemental/Songti.ttc", 3),
    ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 0),
    ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0),
    ("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc", 0),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),
    ("/usr/share/fonts/truetype/arphic/uming.ttc", 0),
    ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", 0),
]
FONT_MONO_CANDIDATES = [
    ("/System/Library/Fonts/Menlo.ttc", 0),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 0),
]


def choose_font(candidates: list[tuple[str, int]]) -> tuple[str, int]:
    for candidate, subfont_index in candidates:
        path = Path(candidate)
        if path.exists():
            return str(path), subfont_index
    raise FileNotFoundError(f"No usable font found in: {candidates}")


def register_fonts() -> None:
    main_font_path, main_subfont_index = choose_font(FONT_MAIN_CANDIDATES)
    pdfmetrics.registerFont(
        TTFont("TripSans", main_font_path, subfontIndex=main_subfont_index)
    )
    mono_path, mono_subfont_index = choose_font(FONT_MONO_CANDIDATES)
    pdfmetrics.registerFont(
        TTFont("TripMono", mono_path, subfontIndex=mono_subfont_index)
    )


def build_styles() -> dict[str, ParagraphStyle]:
    styles = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "TripTitle",
            parent=styles["Title"],
            fontName="TripSans",
            fontSize=20.5,
            leading=25,
            textColor=colors.black,
            spaceAfter=12,
            wordWrap="CJK",
        ),
        "subtitle": ParagraphStyle(
            "TripSubtitle",
            parent=styles["BodyText"],
            fontName="TripSans",
            fontSize=11.2,
            leading=16.5,
            textColor=colors.black,
            spaceAfter=6,
            wordWrap="CJK",
        ),
        "h2": ParagraphStyle(
            "TripH2",
            parent=styles["Heading2"],
            fontName="TripSans",
            fontSize=15.5,
            leading=21,
            textColor=colors.black,
            spaceBefore=12,
            spaceAfter=7,
            keepWithNext=True,
            wordWrap="CJK",
        ),
        "h3": ParagraphStyle(
            "TripH3",
            parent=styles["Heading3"],
            fontName="TripSans",
            fontSize=12.2,
            leading=17.4,
            textColor=colors.black,
            spaceBefore=8,
            spaceAfter=6,
            keepWithNext=True,
            wordWrap="CJK",
        ),
        "h4": ParagraphStyle(
            "TripH4",
            parent=styles["Heading4"],
            fontName="TripSans",
            fontSize=11.1,
            leading=15.5,
            textColor=colors.black,
            spaceBefore=6,
            spaceAfter=4,
            keepWithNext=True,
            wordWrap="CJK",
        ),
        "body": ParagraphStyle(
            "TripBody",
            parent=styles["BodyText"],
            fontName="TripSans",
            fontSize=10.6,
            leading=16.5,
            textColor=colors.black,
            spaceAfter=7,
            wordWrap="CJK",
        ),
        "list": ParagraphStyle(
            "TripList",
            parent=styles["BodyText"],
            fontName="TripSans",
            fontSize=10.6,
            leading=16.5,
            textColor=colors.black,
            leftIndent=11,
            firstLineIndent=0,
            spaceAfter=6,
            wordWrap="CJK",
        ),
        "table": ParagraphStyle(
            "TripTable",
            parent=styles["BodyText"],
            fontName="TripSans",
            fontSize=9.4,
            leading=13.4,
            textColor=colors.black,
            wordWrap="CJK",
        ),
        "caption": ParagraphStyle(
            "TripCaption",
            parent=styles["BodyText"],
            fontName="TripSans",
            fontSize=9.2,
            leading=13,
            textColor=colors.black,
            alignment=TA_CENTER,
            spaceBefore=2,
            spaceAfter=8,
            wordWrap="CJK",
        ),
        "footnote": ParagraphStyle(
            "TripFootnote",
            parent=styles["BodyText"],
            fontName="TripSans",
            fontSize=9.0,
            leading=12.5,
            textColor=colors.black,
            leftIndent=12,
            firstLineIndent=-12,
            spaceAfter=4,
            wordWrap="CJK",
        ),
    }


def escape_text(text: str) -> str:
    return html.escape(text, quote=False)


def footnote_anchor(label: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z_-]+", "-", label).strip("-")
    if not cleaned:
        cleaned = "ref"
    return f"footnote-{cleaned}"


def blue_link(href: str, label: str) -> str:
    return f'<link href="{href}" color="#2563eb">{label}</link>'


def convert_inline(text: str) -> str:
    text = text.replace("->", "→")
    text = escape_text(text)
    text = text.replace("**", "")
    text = text.replace("__", "")
    text = re.sub(r"</?(strong|b)>", "", text, flags=re.IGNORECASE)

    def repl_code(match: re.Match[str]) -> str:
        inner = match.group(1)
        return '<font name="TripSans" color="#000000">' + escape_text(inner) + "</font>"

    def repl_footnote(match: re.Match[str]) -> str:
        label = match.group(1)
        anchor = footnote_anchor(label)
        return (
            f'<super><font name="TripSans" size="7">'
            f'{blue_link(f"#{anchor}", f"[{label}]")}'
            f"</font></super>"
        )

    def repl_link(match: re.Match[str]) -> str:
        label = escape_text(match.group(1))
        href = html.escape(match.group(2), quote=True)
        return blue_link(href, label)

    text = re.sub(r"`([^`]+)`", repl_code, text)
    text = re.sub(r"\[\^([^\]]+)\]", repl_footnote, text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", repl_link, text)
    return text


def parse_table(lines: list[str], start: int) -> tuple[list[str], int]:
    rows = []
    index = start
    while index < len(lines) and lines[index].strip().startswith("|"):
        rows.append(lines[index].strip())
        index += 1
    return rows, index


def skip_blank_lines(lines: list[str], start: int) -> int:
    index = start
    while index < len(lines) and not lines[index].strip():
        index += 1
    return index


def parse_footnote_definition(lines: list[str], start: int) -> tuple[str, str, int] | None:
    match = re.match(r"\[\^([^\]]+)\]:\s*(.+)", lines[start].strip())
    if not match:
        return None

    label = match.group(1)
    parts = [match.group(2).strip()]
    index = start + 1
    while index < len(lines):
        raw = lines[index]
        if raw.startswith("  ") or raw.startswith("\t"):
            parts.append(raw.strip())
            index += 1
            continue
        break
    return label, " ".join(parts), index


def table_from_markdown(raw_rows: list[str], styles: dict[str, ParagraphStyle], doc_width: float) -> Table:
    body_rows = []
    for idx, raw in enumerate(raw_rows):
        cols = [column.strip() for column in raw.strip().strip("|").split("|")]
        if idx == 1 and all(set(column) <= {"-", ":"} for column in cols):
            continue
        body_rows.append(cols)

    max_cols = max(len(row) for row in body_rows)
    padded = [row + [""] * (max_cols - len(row)) for row in body_rows]
    col_width = doc_width / max_cols
    data = [
        [Paragraph(convert_inline(cell), styles["table"]) for cell in row]
        for row in padded
    ]

    table = Table(data, colWidths=[col_width] * max_cols, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f1f1")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("FONTNAME", (0, 0), (-1, -1), "TripSans"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d6d6d6")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def image_flowable(image_path: Path, doc_width: float) -> list[Image]:
    with PILImage.open(image_path) as image:
        width, height = image.size
    max_width = doc_width
    max_height = 175 * mm
    scale = min(max_width / width, max_height / height, 1.0)
    flowable = Image(str(image_path), width=width * scale, height=height * scale)
    flowable.hAlign = "CENTER"
    return [flowable]


def image_block_from_match(
    image_match: re.Match[str],
    base_dir: Path,
    styles: dict[str, ParagraphStyle],
    doc_width: float,
) -> list:
    alt_text = image_match.group(1).strip()
    image_path = Path(image_match.group(2).strip())
    if not image_path.is_absolute():
        image_path = (base_dir / image_path).resolve()
    block = list(image_flowable(image_path, doc_width))
    if alt_text:
        block.append(Paragraph(convert_inline(alt_text), styles["caption"]))
    return block


def footer_builder(footer_text: str):
    def footer(canvas, doc):
        page_num = canvas.getPageNumber()
        canvas.saveState()
        canvas.setFont("TripSans", 9.2)
        canvas.setFillColor(colors.black)
        canvas.drawString(doc.leftMargin, 12 * mm, footer_text)
        canvas.drawRightString(A4[0] - doc.rightMargin, 12 * mm, f"{page_num}")
        canvas.restoreState()

    return footer


def build_story(md_path: Path, styles: dict[str, ParagraphStyle], doc_width: float) -> list:
    lines = md_path.read_text(encoding="utf-8").splitlines()
    story = []
    base_dir = md_path.parent
    index = 0

    while index < len(lines):
        line = lines[index].rstrip()
        stripped = line.strip()

        if not stripped:
            story.append(Spacer(1, 3))
            index += 1
            continue

        if stripped.startswith("# "):
            story.append(Paragraph(convert_inline(stripped[2:].strip()), styles["title"]))
            index = skip_blank_lines(lines, index + 1)
            continue

        if stripped.startswith("## "):
            story.append(Spacer(1, 4))
            story.append(Paragraph(convert_inline(stripped[3:].strip()), styles["h2"]))
            index = skip_blank_lines(lines, index + 1)
            continue

        if stripped.startswith("### "):
            heading = Paragraph(convert_inline(stripped[4:].strip()), styles["h3"])
            next_index = skip_blank_lines(lines, index + 1)
            if next_index < len(lines):
                if lines[next_index].strip().startswith("#### "):
                    subheading = Paragraph(convert_inline(lines[next_index].strip()[5:].strip()), styles["h4"])
                    image_index = skip_blank_lines(lines, next_index + 1)
                    if image_index < len(lines):
                        image_match = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", lines[image_index].strip())
                        if image_match:
                            story.append(
                                KeepTogether(
                                    [
                                        heading,
                                        Spacer(1, 2),
                                        subheading,
                                        Spacer(1, 2),
                                        *image_block_from_match(image_match, base_dir, styles, doc_width),
                                    ]
                                )
                            )
                            index = image_index + 1
                            continue
                next_match = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", lines[next_index].strip())
                if next_match:
                    story.append(
                        KeepTogether(
                            [heading, Spacer(1, 2), *image_block_from_match(next_match, base_dir, styles, doc_width)]
                        )
                    )
                    index = next_index + 1
                    continue
            story.append(heading)
            index = next_index
            continue

        if stripped.startswith("#### "):
            heading = Paragraph(convert_inline(stripped[5:].strip()), styles["h4"])
            next_index = skip_blank_lines(lines, index + 1)
            if next_index < len(lines):
                next_match = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", lines[next_index].strip())
                if next_match:
                    story.append(
                        KeepTogether(
                            [heading, Spacer(1, 2), *image_block_from_match(next_match, base_dir, styles, doc_width)]
                        )
                    )
                    index = next_index + 1
                    continue
            story.append(heading)
            index = next_index
            continue

        image_match = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", stripped)
        if image_match:
            story.append(KeepTogether(image_block_from_match(image_match, base_dir, styles, doc_width)))
            index += 1
            continue

        if stripped.startswith("|"):
            raw_rows, next_index = parse_table(lines, index)
            story.append(table_from_markdown(raw_rows, styles, doc_width))
            story.append(Spacer(1, 6))
            index = next_index
            continue

        footnote = parse_footnote_definition(lines, index)
        if footnote:
            label, content, next_index = footnote
            anchor = footnote_anchor(label)
            story.append(
                Paragraph(
                    f'<a name="{anchor}"/><font name="TripSans">[{label}]</font> {convert_inline(content)}',
                    styles["footnote"],
                )
            )
            index = next_index
            continue

        checkbox = re.match(r"- \[ \] (.+)", stripped)
        if checkbox:
            story.append(Paragraph(convert_inline(f"□ {checkbox.group(1)}"), styles["list"]))
            index += 1
            continue

        bullet = re.match(r"- (.+)", stripped)
        if bullet:
            story.append(Paragraph(convert_inline(f"• {bullet.group(1)}"), styles["list"]))
            index += 1
            continue

        numbered = re.match(r"(\d+)\. (.+)", stripped)
        if numbered:
            story.append(
                Paragraph(
                    convert_inline(f"{numbered.group(1)}. {numbered.group(2)}"),
                    styles["list"],
                )
            )
            index += 1
            continue

        if stripped.startswith(("时间：", "出发：", "方式：", "更新日期：", "目的地：", "行程天数：")):
            style = styles["subtitle"]
        else:
            style = styles["body"]
        story.append(Paragraph(convert_inline(stripped), style))
        index += 1

    return story


def render_previews(pdf_path: Path, preview_dir: Path) -> None:
    import fitz

    preview_dir.mkdir(parents=True, exist_ok=True)
    document = fitz.open(pdf_path)
    try:
        for page in document:
            pix = page.get_pixmap(matrix=fitz.Matrix(1.6, 1.6), alpha=False)
            out = preview_dir / f"{pdf_path.stem}-page-{page.number + 1}.png"
            pix.save(out)
    finally:
        document.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a PDF from the travel-guide-xhs markdown format.")
    parser.add_argument("--input", required=True, help="Input markdown file.")
    parser.add_argument("--output", required=True, help="Output PDF path.")
    parser.add_argument("--title", help="PDF metadata title. Defaults to the markdown stem.")
    parser.add_argument("--author", default="Codex", help="PDF metadata author.")
    parser.add_argument("--footer", help="Footer text. Defaults to the title.")
    parser.add_argument(
        "--preview-dir",
        help="Optional directory for preview PNGs. If omitted, no previews are rendered.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    title = args.title or input_path.stem
    footer_text = args.footer or title

    register_fonts()
    styles = build_styles()

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title=title,
        author=args.author,
    )

    story = build_story(input_path, styles, doc.width)
    footer = footer_builder(footer_text)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)

    if args.preview_dir:
        render_previews(output_path, Path(args.preview_dir).expanduser().resolve())

    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
