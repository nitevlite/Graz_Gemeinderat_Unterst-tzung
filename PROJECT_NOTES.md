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

## Next Build Step

Create a parser MVP that reads ignored local DOCX files and writes ignored structured output.

Suggested first modules:

- DOCX text extraction
- section splitter
- agenda item parser
- status phrase classifier
- amount extractor
- local CLI for batch processing
