# AGENTS.md

## Project Rule: Do Not Commit Protocols

Never commit, stage, or push Gemeinderatsprotokolle, downloaded council documents, local archive copies, or derived raw document exports.

This includes:

- `graz_protokolle_arbeitskopie/`
- `protokolle/`
- `archive/`
- `data/raw/`
- `data/source/`
- `*.docx`, `*.doc`, `*.pdf`, `*.xlsx`, `*.xls`, `*.odt`

Only commit source code, documentation, parser definitions, tests, and sanitized example fixtures.

## Working Notes

- Keep this file and the other project Markdown files current when project direction, data policy, commands, or architecture changes.
- Before any commit, run `git status --short` and confirm no protocol files are staged.
- If sample data is needed, create small sanitized text fixtures that do not contain full protocol content.
- Treat source documents as local working material, not repository content.

## Current Local Data

The current workspace contains a local, ignored protocol working copy:

- `graz_protokolle_arbeitskopie/`

It contains DOCX files copied from `E:\01_StadtGrazProtokolle\Archiv\...` plus a local `manifest.json`. This directory is intentionally ignored by Git.

## Current MVP

The parser MVP is implemented in `graz_protocols/` and tested with sanitized fixtures in `tests/`.
It reads DOCX paragraph style metadata and currently emits `agenda_item`, `urgent_motion`, `written_question`, and `written_motion` records.
Formal result lines are stored in `result_text`; keep this field focused on exact decision/result wording, not general source snippets.

Use:

```powershell
python -m graz_protocols.cli parse graz_protokolle_arbeitskopie --output out\agenda_items.jsonl --summary out\summary.json
```

The output directory `out/` is ignored and must remain untracked.
