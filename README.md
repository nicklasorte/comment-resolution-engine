# comment-resolution-engine

A practical Python tool for NTIA-style comment resolution matrices. It reads a comment matrix, optionally looks at a line-numbered PDF report, and fills **NTIA Comments**, **Comment Disposition**, and **Resolution** while preserving the original workbook structure.

## What this tool does now
- Reads a comment resolution matrix from Excel.
- Normalizes real-world header variants for NTIA columns.
- Uses `Comment Type` plus Agency inputs to pick an initial **Accept/Reject** disposition.
- Drafts concise **NTIA Comments** and **Resolution** text (report-ready language) using agency notes and suggested wording.
- Optionally pulls lightweight PDF context for reference (best effort).
- Keeps the original sheet shape whenever practical and formats the output with frozen headers, filters, and wrapped text columns.

## Current Workflow
- Load matrix and detect the core headers (Comment Number, Reviewer Initials, Agency, Report Version, Section, Page, Line, Comment Type, Agency Notes, Agency Suggested Text Change).
- Normalize `Comment Type: Editorial/Grammar, Clarification, Technical` into `Technical`, `Clarification`, or `Editorial/Grammar`.
- Derive the effective comment inputs:
  - `effective_comment` = Agency Notes if present, else Agency Suggested Text Change, else empty.
  - `effective_suggested_text` = Agency Suggested Text Change if present, else empty.
- Optionally pull nearby context from a line-numbered PDF.
- Populate `NTIA Comments`, `Comment Disposition`, and `Resolution`.
- Preserve the original workbook columns when practical; append/overwrite the NTIA fields instead of rebuilding the sheet from scratch.

## Column Semantics
- **Agency Notes**: Primary statement of the reviewer’s concern.
- **Agency Suggested Text Change**: Optional candidate wording from the reviewer.
- **NTIA Comments**: Concise internal note explaining accept/reject and whether suggested text was used or revised.
- **Comment Disposition**: Exactly `Accept` or `Reject`.
- **Resolution**: Final report-ready text to insert or substitute in the report (not meta-commentary).

## Inputs
1. **Excel comment resolution matrix** (`.xlsx`) with the NTIA headers above or common variants.
2. **Optional PDF report** with line numbers for grounding (`--report`), best-effort parsing only.

## Outputs
- The original matrix with populated or added columns:
  - Comment Number, Reviewer Initials, Agency, Report Version, Section, Page, Line, Comment Type
  - Agency Notes, Agency Suggested Text Change
  - NTIA Comments, Comment Disposition, Resolution
  - Report Context, Resolution Task
- Columns are matched to existing headers (e.g., `Internal Comments`, `Accept/Reject`, `Proposed Resolution`, `Final Text`) to avoid duplicates.

## Usage

```bash
python -m comment_resolution_engine.cli \
  --comments inputs/comment_resolution_matrix.xlsx \
  --report inputs/report.pdf \
  --output outputs/resolved_matrix.xlsx \
  --config config/column_mapping.yaml
```

If `--report` is omitted, the pipeline still runs without PDF context.

## Configure column mappings
- Copy `config/column_mapping.example.yaml` to `config/column_mapping.yaml`.
- Update `columns` to point to your canonical headers if they differ.
- Add local header variants under `synonyms` (e.g., `Internal Comments`, `Accept/Reject`, `Proposed Resolution`).
- Pass your config with `--config` in the CLI.

## PDF handling
- PDF parsing is intentionally lightweight and best effort.
- If a PDF is provided and a line reference is present, nearby numbered lines are pulled into `Report Context`; otherwise a placeholder is added.

## Deterministic today vs. future LLM integration
- Deterministic now:
  - Column detection and normalization.
  - Comment type normalization.
  - Basic Accept/Reject heuristics driven by comment type and keywords.
  - Draft NTIA Comments and Resolution using agency inputs.
  - Workbook formatting and structure preservation.
- Still open for LLM enhancement:
  - Richer semantic evaluation of technical validity.
  - Higher-fidelity rewriting of Resolution text.
  - Deeper PDF-grounded reasoning.

## Folder structure

```text
comment-resolution-engine/
  README.md
  pyproject.toml
  requirements.txt
  src/comment_resolution_engine/
    cli.py
    config.py
    excel_io.py
    pdf_utils.py
    resolver_schema.py
    prompt_builder.py
    pipeline.py
  prompts/
    resolution_engine.md
    codex_run_prompt.md
  config/
    column_mapping.example.yaml
  templates/
    README.md
  examples/
    sample_comment_matrix.csv
    sample_resolved_output.csv
  tests/
    ...
```

## Non-binary repository policy
Binary Excel templates are not committed. Use the CSV examples as shape references and generate workbooks locally via the CLI.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .[dev]
```

## Testing

```bash
python -m pytest
```

Tests that require optional runtime packages (`pandas`, `openpyxl`) are auto-skipped if those packages are unavailable in the current environment.
