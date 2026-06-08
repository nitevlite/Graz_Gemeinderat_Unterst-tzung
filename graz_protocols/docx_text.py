from __future__ import annotations

from pathlib import Path
import re
import zipfile
import xml.etree.ElementTree as ET


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": WORD_NS}


def read_docx_paragraphs(path: Path) -> list[str]:
    """Return non-empty DOCX paragraphs in document order.

    This intentionally uses only stdlib ZIP/XML handling so the first parser MVP
    has no install step. It extracts text, tabs, and line breaks from Word runs.
    """
    with zipfile.ZipFile(path) as archive:
        try:
            raw_xml = archive.read("word/document.xml")
        except KeyError as exc:
            raise ValueError(f"{path} has no word/document.xml") from exc

    root = ET.fromstring(raw_xml)
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", NS):
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
            paragraphs.append(text)
    return paragraphs


def normalize_paragraph_text(value: str) -> str:
    value = value.replace("\u00a0", " ")
    value = re.sub(r"[ \r\f\v]+", " ", value)
    value = re.sub(r"\n+", "\n", value)
    return value.strip()
