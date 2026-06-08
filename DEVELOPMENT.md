# Development

## Git Hygiene

Before staging:

```powershell
git status --short
```

Only stage source and documentation files. Never stage protocol files or generated raw extraction output.

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

## Documentation Maintenance

Whenever the project changes, update the relevant Markdown file in the same work session:

- `AGENTS.md` for agent rules and workflow constraints
- `DATA_POLICY.md` for data handling rules
- `PROJECT_NOTES.md` for architecture direction and project state
- `README.md` for user-facing project purpose
- `DEVELOPMENT.md` for commands and local workflow
