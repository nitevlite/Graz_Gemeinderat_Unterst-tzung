from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
import re
import zipfile
import xml.etree.ElementTree as ET


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": WORD_NS}


@dataclass(frozen=True)
class DocxParagraph:
    text: str
    style: str
    index: int

    @property
    def is_heading(self) -> bool:
        return self.style.casefold().startswith("heading")

    @property
    def is_toc(self) -> bool:
        return self.style.casefold().startswith("toc")


def read_docx_paragraphs(path: Path) -> list[str]:
    """Return non-empty DOCX paragraphs in document order.

    This intentionally uses only stdlib ZIP/XML handling so the first parser MVP
    has no install step. It extracts text, tabs, and line breaks from Word runs.
    """
    return [paragraph.text for paragraph in read_docx_paragraph_blocks(path)]


def read_docx_paragraph_blocks(path: Path) -> list[DocxParagraph]:
    """Return DOCX paragraphs with Word style metadata."""
    with zipfile.ZipFile(path) as archive:
        try:
            raw_xml = archive.read("word/document.xml")
        except KeyError as exc:
            raise ValueError(f"{path} has no word/document.xml") from exc

    root = ET.fromstring(raw_xml)
    paragraphs: list[DocxParagraph] = []
    for index, paragraph in enumerate(root.findall(".//w:p", NS)):
        parts: list[str] = []
        for node in paragraph.iter():
            if node.tag == f"{{{WORD_NS}}}t" and node.text:
                parts.append(node.text)
            elif node.tag == f"{{{WORD_NS}}}tab":
                parts.append("\t")
            elif node.tag == f"{{{WORD_NS}}}br":
                parts.append("\n")
        text = normalize_paragraph_text("".join(parts))
        if text:
            paragraphs.append(DocxParagraph(text=text, style=get_paragraph_style(paragraph), index=index))
    return paragraphs


def get_paragraph_style(paragraph: ET.Element) -> str:
    style = paragraph.find("./w:pPr/w:pStyle", NS)
    if style is None:
        return ""
    return style.attrib.get(f"{{{WORD_NS}}}val", "")


def normalize_paragraph_text(value: str) -> str:
    value = value.replace("\u00a0", " ")
    value = re.sub(r"[ \r\f\v]+", " ", value)
    value = re.sub(r"\n+", "\n", value)
    return value.strip()
