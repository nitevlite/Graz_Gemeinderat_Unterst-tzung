# Development

## Git Hygiene

Before staging:

```powershell
git status --short
```

Only stage source and documentation files. Never stage protocol files or generated raw extraction output.

GitHub remote:

```text
origin https://github.com/nitevlite/graz-council-protocol-explorer.git
```

Recommended staging pattern:

```powershell
git add .gitignore AGENTS.md README.md DATA_POLICY.md PROJECT_NOTES.md DEVELOPMENT.md
```

## Local Data

Keep source documents in ignored folders. The current local working folder is:

```text
graz_protokolle_arbeitskopie/
```

## Parser Output

Write generated data to ignored paths such as:

```text
out/
exports/
```

Do not commit generated databases or JSONL files unless they are tiny sanitized fixtures.

## Commands

Run tests:

```powershell
python -m pytest -q
```

Pytest is configured without its cache provider to avoid local cache churn.

Run the parser MVP:

```powershell
python -m graz_protocols.cli parse graz_protokolle_arbeitskopie --output out\agenda_items.jsonl --summary out\summary.json
```

The parser output is local working data and ignored by Git.
The current parser reads DOCX paragraph styles and emits multiple record types, including written questions and motions.
It emits normalized `result_text` for display, `votes` for structured decision details, and `raw_result_text` only as local traceability data in the ignored JSONL output.

Build the local HTML viewer:

```powershell
python -m graz_protocols.viewer --records out\agenda_items.jsonl --summary out\summary.json --output viewer.html
```

The generated viewer intentionally removes raw source snippets and original result formulations from its embedded records.

## Documentation Maintenance

Whenever the project changes, update the relevant Markdown file in the same work session:

- `AGENTS.md` for agent rules and workflow constraints
- `DATA_POLICY.md` for data handling rules
- `PROJECT_NOTES.md` for architecture direction and project state
- `README.md` for user-facing project purpose
- `DEVELOPMENT.md` for commands and local workflow
