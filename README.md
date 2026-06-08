# Graz Council Protocol Explorer

Working project for turning Gemeinderatsprotokolle der Stadt Graz into a searchable, structured, and source-linked decision register.

## Goal

Build a system that can answer questions like:

- What was approved?
- Where did it happen?
- Which agenda item, business number, person, party, amount, and date are involved?
- What is the original source text?
- How did a topic evolve across meetings?

## Data Policy

Protocol files are local working material and must not be committed or pushed.

The repository may contain:

- parser code
- extraction rules
- tests
- documentation
- sanitized fixtures

The repository must not contain:

- full DOCX/PDF protocols
- downloaded council documents
- raw DIGRA exports
- local archive copies
- unsanitized extracted full text

## Current Input Sources

- Local archive files under `E:\01_StadtGrazProtokolle\Archiv\...`
- DIGRA Public: `https://digra.graz.at/timetable`
- Graz council archive pages: `https://www.graz.at/cms/beitrag/10142612/7768104`
- Existing helper project: `E:\01_StadtGrazProtokolle\Digra_Export_Tool`

## First MVP

Extract structured records from local DOCX files:

- meeting date
- section
- agenda item number
- business number
- title
- status phrase
- money amounts
- place references
- short source snippet

Output should be a local ignored database or JSONL file, not committed.

## MVP CLI

Run the local parser against ignored DOCX working copies:

```powershell
python -m graz_protocols.cli parse graz_protokolle_arbeitskopie --output out\agenda_items.jsonl --summary out\summary.json
```

The parser writes JSONL records with meeting date, agenda item number, business numbers, title, status, amounts, location hints, and a short source snippet.

Generated output under `out/` is ignored and must not be committed.

Build a local double-click HTML viewer:

```powershell
python -m graz_protocols.viewer --records out\agenda_items.jsonl --summary out\summary.json --output viewer.html
```

Then open `viewer.html` in a browser. The file is generated local output and ignored by Git.
