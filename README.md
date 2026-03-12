# comment-resolution-engine

A practical Python tool for NTIA-style comment resolution matrices. It now behaves like a deterministic engineering pipeline: it ingests a spreadsheet, optionally reads a line-numbered PDF, analyzes multi-agency feedback at scale, and emits structured artifacts (matrix updates, report patch proposals, FAQ log, section briefs, and briefing bullets).

## What this tool does now
- Runs a five-stage pipeline: **Ingest → Normalize → Analyze → Generate → Validate**.
- Ingests Excel matrices with automatic header detection and canonicalizes to structured `CommentRecord` objects.
- Optionally parses line-numbered PDFs to attach context windows (line −5 to +5) to each comment.
- Normalizes comment type variants into **TECHNICAL / CLARIFICATION / EDITORIAL** and derives effective comment text.
- Analyzes comments with clustering (TF‑IDF similarity), section grouping, intent classification, and heat maps to locate hot spots.
- Generates report-ready **Disposition**, **NTIA Comments**, and **Resolution** text grounded in PDF context for technical items.
- Produces proposed report patch records, shared (multi-comment) resolutions, FAQ entries, section briefs, and briefing bullets.
- Validates each row with rules tied to disposition and comment type, surfacing `validation_status` and `validation_notes`.
- Keeps the original sheet shape when practical and formats the output with frozen headers, filters, and wrapped text columns.
- Builds Rev-2 section-level rewrites and an optional assembled draft narrative using accepted fixes, shared resolutions, and clustered themes (without recreating figures or tables).

## Current Workflow
**Stage 1 – Ingest**
- Load the matrix and detect header variants for canonical fields (Comment Number, Reviewer Initials, Agency, Report Version, Section, Page, Line, Comment Type, Agency Notes, Agency Suggested Text Change, WG Chain Comments, Comment Disposition/Resolution).
- Optionally parse a line-numbered PDF and index line windows.

**Stage 2 – Normalize**
- Normalize comment types to TECHNICAL / CLARIFICATION / EDITORIAL.
- Derive `effective_comment` and `effective_suggested_text`.

**Stage 3 – Analyze**
- Cluster similar comments (TF‑IDF cosine similarity) and assign `comment_cluster_id`.
- Group by section and compute a comment heat map (LOW/MODERATE/HIGH/STRUCTURALLY_UNSTABLE).
- Classify comment intent (REQUEST_CHANGE, REQUEST_CLARIFICATION, SUGGEST_EDIT, TECHNICAL_CHALLENGE, OUT_OF_SCOPE).

**Stage 4 – Generate**
- Determine disposition and generate report-ready resolutions (accepts are phrased as clarifications/updates; rejects include rationale).
- Technical resolutions incorporate PDF context when available.
- Produce patch records (INSERT/REPLACE/APPEND/CLARIFY), shared resolutions for clustered items, FAQ entries, section briefs, and briefing bullets.

**Stage 5 – Validate**
- Apply deterministic validation rules to ensure accepted items describe the change, rejects provide justification, editorial defaults accept, and technical items reference context/sections where possible.
- Surface `validation_status` and `validation_notes` in the matrix.

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
1. Updated Excel matrix with:
   - Core metadata (Comment Number, Reviewer Initials, Agency, Report Version, Section, Page, Line)
   - Agency inputs (Notes, Suggested Text, WG Chain Comments)
   - NTIA outputs (NTIA Comments, Disposition, Resolution, Report Context, Resolution Task)
   - Analysis + validation (Comment Cluster Id, Intent Classification, Section Group, Heat Level, Validation Status/Notes)
2. Proposed report patch file (JSON, default `<output>_patches.json`) and shared resolution file (`<output>_shared_resolutions.json`).
3. FAQ / issue log (`<output>_faq.md`).
4. Section summary memo (`<output>_section_summary.md`).
5. Working group briefing bullets (`<output>_briefing.md`).
6. Section-level Rev-2 rewrite records (`<output>_rev2_sections.json`) when `--draft-rev2` is enabled.
7. Optional assembled Rev-2 narrative (`<output>_rev2_draft.md`) when `--assemble-rev2` is enabled.

## Usage

```bash
python -m comment_resolution_engine.cli \
  --comments inputs/comment_resolution_matrix.xlsx \
  --report inputs/report.pdf \
  --output outputs/resolved_matrix.xlsx \
  --config config/column_mapping.yaml \
  --patch-output outputs/report_patches.json \
  --faq-output outputs/faq.md \
  --summary-output outputs/section_summary.md \
  --briefing-output outputs/briefing.md \
  --draft-rev2 \
  --draft-mode CLEAN_REWRITE \
  --draft-sections 3.2,4.1,5.2 \
  --draft-high-priority-only \
  --assemble-rev2
```

If `--report` is omitted, the pipeline still runs without PDF context and produces the analysis/generation artifacts.

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
    models.py
    excel_io.py
    pdf_utils.py
    pipeline.py
    ingest/
      excel_reader.py
      pdf_parser.py
    normalize/
      comment_normalizer.py
    analysis/
      comment_clustering.py
      section_grouping.py
      intent_classifier.py
    generation/
      resolution_generator.py
      report_patch_generator.py
      faq_generator.py
      section_summary_generator.py
    validation/
      resolution_validator.py
    knowledge/
      canonical_definitions.py
      issue_library.py
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
