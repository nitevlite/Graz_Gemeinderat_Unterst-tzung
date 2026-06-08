# Data Policy

## Non-Negotiable Rule

Gemeinderatsprotokolle and raw downloaded documents must never be pushed to Git.

The `.gitignore` is configured to exclude common protocol locations and document formats, but this is not enough by itself. Always check `git status --short` before staging or committing.

## Allowed In Git

- source code
- tests
- documentation
- extraction schemas
- small sanitized fixtures
- metadata-only examples without full protocol text

## Not Allowed In Git

- DOCX/PDF/XLSX protocol files
- full extracted protocol text
- raw DIGRA exports
- local archive manifests containing sensitive absolute paths, unless explicitly sanitized
- generated databases with source content

## Local Working Data

Use ignored directories for real source material:

- `graz_protokolle_arbeitskopie/`
- `data/raw/`
- `data/source/`

Use ignored output locations for generated extraction results:

- `out/`
- `exports/`
- `*.sqlite`
- `*.jsonl`

## Sanitized Fixtures

When tests need examples, create short artificial snippets that preserve structure but do not copy full protocol content.
