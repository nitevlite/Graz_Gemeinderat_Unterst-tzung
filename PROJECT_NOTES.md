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

Current result handling:

- formal result lines are extracted into `raw_result_text` for local traceability
- `result_text` is normalized for display, not copied from the protocol wording
- structured vote details are emitted in `votes`
- status classification prefers formal result lines over arbitrary words in speeches
- legacy wording such as `mehrstimmig angenommen` is normalized to majority acceptance
- parenthetical party details such as `(Gegen KFG, NEOS, FPÖ)` are normalized into `Dagegen: ...`
- the local viewer shows only standardized `Ergebnisse`, not raw source snippets or original result formulations

Latest local run on 2026-06-08:

- input: `graz_protokolle_arbeitskopie/`
- files parsed: 18
- records written: 1135
- records with structured votes/results: 1053
- record types:
  - `agenda_item`: 459
  - `urgent_motion`: 108
  - `written_question`: 235
  - `written_motion`: 333
- status distribution:
  - `accepted_majority`: 181
  - `accepted_unanimous`: 317
  - `assigned`: 571
  - `rejected_majority`: 43
  - `unknown`: 20
- output: `out/agenda_items.jsonl`

Generated output is intentionally ignored.

## Next Build Step

Improve extraction quality beyond section detection:

- better vote result parsing with party names
- stronger place extraction and geocoding-ready location records
- SQLite output for search and timeline queries

## GitHub Issues

Created on 2026-06-08 in the private GitHub repo:

- https://github.com/nitevlite/graz-council-protocol-explorer/issues/1
- https://github.com/nitevlite/graz-council-protocol-explorer/issues/2
- https://github.com/nitevlite/graz-council-protocol-explorer/issues/3
- https://github.com/nitevlite/graz-council-protocol-explorer/issues/4
- https://github.com/nitevlite/graz-council-protocol-explorer/issues/5
- https://github.com/nitevlite/graz-council-protocol-explorer/issues/6
- https://github.com/nitevlite/graz-council-protocol-explorer/issues/7
- https://github.com/nitevlite/graz-council-protocol-explorer/issues/8
- https://github.com/nitevlite/graz-council-protocol-explorer/issues/9
- https://github.com/nitevlite/graz-council-protocol-explorer/issues/10
- https://github.com/nitevlite/graz-council-protocol-explorer/issues/11
- https://github.com/nitevlite/graz-council-protocol-explorer/issues/12
