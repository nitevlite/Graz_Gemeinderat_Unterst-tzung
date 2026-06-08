# Project Notes

## Direction

The project should become a structured decision register for Graz council protocols:

- full-text search with source references
- agenda item extraction
- decision/status classification
- money amount extraction
- place extraction and later map display
- topic timelines across meetings

## Useful Existing Tooling

`E:\01_StadtGrazProtokolle\Digra_Export_Tool` already contains useful logic for DIGRA:

- finding meetings
- reading DIGRA tabs
- exporting agenda-related documents
- creating DOCX protocol material

That project can inform this one, but raw exports from it must stay out of Git.

## Current Workspace State

As of 2026-06-08, `graz_protokolle_arbeitskopie/` contains 18 local DOCX protocol copies for initial analysis. The folder is ignored and must remain untracked.

## MVP Parser

An MVP parser now reads ignored local DOCX files and writes ignored structured output.

Current modules:

- `graz_protocols/docx_text.py`: stdlib DOCX text extraction
- `graz_protocols/parser.py`: agenda item, status, amount, business-number, and location-hint extraction
- `graz_protocols/cli.py`: batch parser CLI
- `graz_protocols/viewer.py`: generated local double-click HTML viewer
- `tests/test_parser.py`: sanitized parser tests

Latest local run on 2026-06-08:

- input: `graz_protokolle_arbeitskopie/`
- files parsed: 18
- records written: 459
- output: `out/agenda_items.jsonl`

Generated output is intentionally ignored.

## Next Build Step

Improve extraction beyond `Stk.` agenda items:

- written questions and written motions without `Stk.` headings
- better vote result parsing with party names
- stronger place extraction and geocoding-ready location records
- SQLite output for search and timeline queries
