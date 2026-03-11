# comment-resolution-engine

A lightweight Python tool for turning an agency comment matrix plus a line-numbered report PDF into a structured **comment-resolution table** with report-ready proposed text scaffolding.

## What this tool does
- Reads a comment matrix from Excel.
- Normalizes common column name variants (e.g., `Comment No.`, `Cmt #`, `Line`, `Rev`).
- Preserves key fields and generates a reusable output workbook.
- Adds a per-row `Resolution Task` prompt payload to support future LLM-assisted drafting.
- Produces a professionally formatted output Excel file (frozen headers, filters, wrapped narrative columns, useful widths).
- Optionally extracts limited text context from a PDF (best effort, non-blocking).

## Required inputs
1. **Excel comment matrix** (`.xlsx`)
2. **PDF report with line numbers** (`.pdf`) — optional for current version, but accepted by CLI

## Expected output
An Excel workbook containing at least:
- `Comment Number`
- `Proposed Report Text`

Also included by default:
- `Comment`
- `Line Number`
- `Revision`
- `Status`
- `Comment Type`
- `Source Line Reference`
- `Insert Location`
- `Resolution Task`

## Folder structure

```text
comment-resolution-engine/
  README.md
  .gitignore
  pyproject.toml
  requirements.txt
  .env.example
  src/comment_resolution_engine/
    __init__.py
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
    sample_output.csv
  tests/
    test_column_mapping.py
    test_prompt_builder.py
    test_excel_io.py
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Usage

```bash
python -m comment_resolution_engine.cli \
  --comments inputs/comment_matrix.xlsx \
  --report inputs/report.pdf \
  --output outputs/resolution_table.xlsx \
  --config config/column_mapping.example.yaml
```

If `--report` is omitted, pipeline still runs.

## Use with Codex / ChatGPT
1. Run CLI first to generate a structured draft workbook.
2. Use `prompts/resolution_engine.md` as the reusable instruction set.
3. Paste `prompts/codex_run_prompt.md` into Codex/ChatGPT and provide actual input files.
4. Have the model fill or refine `Proposed Report Text` while respecting direct report-ready style.

## Customize column mappings
- Copy `config/column_mapping.example.yaml` to `config/column_mapping.yaml`.
- Adjust canonical mappings under `columns`.
- Add local naming variants under `synonyms`.
- Pass custom file with `--config`.


## Non-binary repository policy
To keep this repository diff-friendly, binary Excel templates/examples are not committed.
- Use `examples/*.csv` for sample data shape.
- The CLI output workbook is generated at runtime (`--output ...xlsx`).
- If needed, create local Excel inputs from the CSV examples before running.

## Current limitations
- No end-to-end LLM call is included yet; this version prepares high-quality structured inputs and prompts.
- PDF extraction is best effort only and intentionally non-blocking.
- Comment classification is rule-based and simple by design.
- `Proposed Report Text` is seeded from revision notes for non-complete rows; final wording is intended for human or LLM refinement.

## Extension points
- Add an `llm_client.py` and call it from `pipeline.py` after `Resolution Task` creation.
- Persist prompt templates externally (already in `prompts/`) for consistent runs.
- Add stricter schema validation (e.g., pydantic) if/when needed.


## Testing

```bash
python -m pytest
```

Tests that require optional runtime packages (`pandas`, `openpyxl`) are auto-skipped if those packages are unavailable in the current environment.
