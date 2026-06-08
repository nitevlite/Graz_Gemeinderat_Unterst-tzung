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
