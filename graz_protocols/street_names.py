from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile
import re
import xml.etree.ElementTree as ET


NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def load_street_names(path: Path) -> set[str]:
    values = read_first_column(path)
    names = {normalize_street_name(value) for value in values[1:] if value.strip()}
    return {name for name in names if name}


def read_first_column(path: Path) -> list[str]:
    with ZipFile(path) as archive:
        shared_strings = read_shared_strings(archive)
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        values: list[str] = []
        for row in sheet.findall(".//m:row", NS):
            cell = row.find("m:c[@r='A%s']" % row.get("r"), NS)
            if cell is None:
                values.append("")
                continue
            values.append(read_cell_value(cell, shared_strings))
        return values


def read_shared_strings(archive: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for item in root.findall("m:si", NS):
        texts = [node.text or "" for node in item.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")]
        values.append("".join(texts))
    return values


def read_cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    value = cell.find("m:v", NS)
    if value is None or value.text is None:
        return ""
    if cell.get("t") == "s":
        return shared_strings[int(value.text)]
    return value.text


def normalize_street_name(value: str) -> str:
    value = value.replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value).strip().casefold()
    value = value.replace("strasse", "straße")
    return value
