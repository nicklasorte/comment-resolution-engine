# comment-resolution-engine

## MVP Execution Pipeline — `resolve_comments.py`

`resolve_comments.py` is a self-contained script that adjudicates a comment
resolution matrix against a revised working paper PDF and writes an updated
matrix.

### Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Optional: validate dependencies only
python resolve_comments.py --preflight

# Run the MVP path with the committed sample inputs
python resolve_comments.py \
    --matrix examples/sample_matrix.xlsx \
    --paper  examples/sample_working_paper.pdf \
    --output /tmp/test_adjudicated.xlsx

# End-to-end canonical path (JSON artifact in, canonical artifacts + Excel out)
python -m comment_resolution_engine.cli \
    --reviewer-comment-set examples/contracts/reviewer_comment_set_example.json \
    --report examples/sample_working_paper.pdf \
    --output /tmp/test_adjudicated.xlsx
```

### CLI reference

```
python resolve_comments.py \
    --matrix  <input_matrix.xlsx|.csv>   # Required: comment resolution matrix
    --paper   <working_paper.pdf>        # Required: revised working paper PDF
    --output  <adjudicated_matrix.xlsx>  # Optional: output path
                                         #   default: adjudicated_comment_matrix.xlsx
    --emit-debug-json                    # Optional: write <output>_debug.json with reason codes and responses
```

### Smoke test

Validate the MVP pipeline using the committed sample inputs:

```bash
python -m pytest tests/test_mvp_smoke.py
```

### Input format

**`--matrix`** — Excel (`.xlsx`) or CSV spreadsheet that **must** contain the
canonical headers in any order (output is always written in deterministic contract order):

| Column | Description |
|--------|-------------|
| Comment Number | Unique row identifier |
| Reviewer Initials | Reviewer abbreviation |
| Agency | Submitting agency name |
| Report Version | Working paper revision anchor |
| Section | Working paper section reference |
| Page | Page number |
| Line | Line number or range |
| Comment Type: Editorial/Grammar, Clarification, Technical | Comment classification |
| Agency Notes | Full text of the agency comment |
| Agency Suggested Text Change | Optional proposed replacement text |
| NTIA Comments | *(populated by the script)* Revision reference and notes |
| Comment Disposition | *(populated by the script)* Adjudication outcome |
| Resolution | *(populated by the script)* Response text |

Allowed optional headers (preserved when present, appended after the canonical set): `Status`, `WG Chain Comments`,
`Revision`, `Line Number`.

Completed-row rules: if `Status` or `Comment Disposition` contains `complete`,
`completed`, `closed`, `resolved`, or `done`, the row must already include both
`Comment Disposition` and `Resolution` text. Otherwise the run fails fast with a
clear validation error.

Machine-readable contract: `config/contracts/matrix_contract.yaml` declares the
required headers, optional/metadata headers, generated columns, column order,
and completion rules used by the engine and tests.

**`--paper`** — PDF of the revised working paper. Text is extracted to supply
context for generating responses.

Sample files are provided in `examples/`:
- `examples/sample_matrix.xlsx` — five-row matrix with representative comments
- `examples/sample_working_paper.pdf` — working paper text matching the sample comments
These two files are intentionally tracked (whitelisted in `.gitignore`) as MVP sample inputs; other generated spreadsheets remain ignored by default.

### Output format

A single Excel workbook written to `--output` (default:
`adjudicated_comment_matrix.xlsx`).

The output **preserves**:
- all original rows
- the canonical header names
- deterministic column ordering:
  - base order: Comment Number, Reviewer Initials, Agency, Report Version, Section, Page, Line,
    Comment Type: Editorial/Grammar, Clarification, Technical, Agency Notes, Agency Suggested Text Change,
    NTIA Comments, Comment Disposition, Resolution
  - optional (when present): Status, WG Chain Comments, Revision, Line Number
  - metadata (only when `--include-metadata-columns` is used): Revision, Resolved Against Revision,
    WG Chain Comments, Report Context, Resolution Task, Generation Mode, Rule Id, Rule Source, Rule Version,
    Rules Profile, Rules Version, Matched Rule Types, Review Status, Confidence Score, Provenance Record Id,
    Comment Cluster Id, Intent Classification, Section Group, Heat Level, Validation Status, Validation Notes,
    Validation Code, Patch Text, Patch Source, Patch Confidence, Resolution Basis, Context Confidence,
    Cluster Label, Cluster Size, Shared Resolution Id, Canonical Term Used

The three resolution columns are populated as follows:

| Column | Generated content |
|--------|------------------|
| **Comment Disposition** | `Accepted` / `Partially Accepted` / `Rejected` / `Completed` |
| **Resolution** | Plain-language response to the agency comment |
| **NTIA Comments** | Revision reference (`Section X, p. Y, l. Z`) and explanatory notes |

**Disposition logic:**

- `Completed` — row was already marked as resolved in the input; existing
  resolution text is preserved.
- `Accepted` — editorial/grammar comments, or comments with suggested text.
- `Partially Accepted` — technical comments without suggested text.
- `Rejected` — comments containing out-of-scope or already-addressed signals.

---

A practical Python tool for NTIA-style comment resolution matrices. It now behaves like a deterministic engineering pipeline: it ingests a spreadsheet, requires at least one working paper PDF (and supports optional later revisions), analyzes multi-agency feedback at scale, and emits structured artifacts (matrix updates, report patch proposals, FAQ log, section briefs, and briefing bullets).

Implements: SYS-001  
Source Architecture Repo: spectrum-systems  
Governing Spec: docs/system-spec-comment-resolution-engine.md  
Governing Provenance Guidance: docs/provenance-implementation-guidance.md  
Governing Error Taxonomy: docs/error-taxonomy.md
Contract role:
- Repo role: engine_repo (czar org)
- Contract mode: consume_and_produce
- Consumes canonical `reviewer_comment_set` artifacts (plus standards manifest) from spectrum-systems / working-paper-review-engine
- Produces canonical `comment_resolution_matrix` and `provenance_record` artifacts aligned to spectrum-systems contracts (legacy Excel output remains for compatibility)

Constitution alignment:
- `config/constitution.yaml` pins SYS-001 to the spectrum-systems constitution and enumerates schema, prompt, rules, provenance, and error taxonomy references.
- Validate without running the pipeline using `python -m comment_resolution_engine.cli --check-constitution --constitution config/constitution.yaml --constitution-report outputs/constitution_report.json`.
- Runtime flags `--constitution`, `--constitution-report`, `--compatibility-mode`, `--fail-on-drift`, and `--rules-profile` control compatibility enforcement and reporting.

## What this tool does now
- Runs a five-stage pipeline: **Ingest → Normalize → Analyze → Generate → Validate**.
- Ingests Excel matrices with automatic header detection and canonicalizes to structured `CommentRecord` objects.
- Parses line-numbered PDFs (at least one required, multiple supported) to attach context windows (line −5 to +5) to each comment.
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

## Canonical MVP spreadsheet contract
The governed contract is declared in `config/contracts/matrix_contract.yaml` and enforced at ingest, normalization, and
workbook export. Required headers (always present on ingest and output): Comment Number, Reviewer Initials, Agency,
Report Version, Section, Page, Line, Comment Type: Editorial/Grammar, Clarification, Technical, Agency Notes,
Agency Suggested Text Change, NTIA Comments, Comment Disposition, Resolution. Optional headers (preserved in output
when present): Status, WG Chain Comments, Revision, Line Number. Generated columns: NTIA Comments, Comment
Disposition, Resolution (plus the metadata set when `--include-metadata-columns` is used). Duplicate canonical headers,
missing required headers, completed rows lacking disposition/resolution, or metadata collisions with the output set
fail fast with `SCHEMA_ERROR`/`VALIDATION_ERROR`.

## Column Semantics
- **Agency Notes**: Primary statement of the reviewer’s concern.
- **Agency Suggested Text Change**: Optional candidate wording from the reviewer.
- **NTIA Comments**: Concise internal note explaining accept/reject and whether suggested text was used or revised.
- **Comment Disposition**: Exactly `Accept` or `Reject`.
- **Resolution**: Final report-ready text to insert or substitute in the report (not meta-commentary).

## Inputs
1. **Excel/CSV comment resolution matrix** using the canonical headers above. `Report Version` is the revision anchor and must map to an uploaded working paper revision (filename stem or inferred `revN`).
2. **Working paper PDF revisions** (at least one) with line numbers for grounding (`--report`). Provide multiple `--report` flags in revision order to load later versions (rev1, rev2, rev3, ...).

If only one PDF is provided, blank `Report Version` cells map to the uploaded revision label. When multiple revisions are uploaded, every comment must declare a `Report Version`, and any reference without a matching uploaded PDF fails fast with a clear error.

## Outputs
1. Updated Excel matrix that retains the canonical headers/order and populates **NTIA Comments**, **Comment Disposition**, and **Resolution**. Optional machine metadata columns (clusters, patches, provenance, validation, rules) are excluded by default and can be added with `--include-metadata-columns` when needed.
2. Proposed report patch file (JSON, default `<output>_patches.json`) and shared resolution file (`<output>_shared_resolutions.json`).
3. FAQ / issue log (`<output>_faq.md`).
4. Section summary memo (`<output>_section_summary.md`).
5. Working group briefing bullets (`<output>_briefing.md`).
6. Section-level Rev-2 rewrite records (`<output>_rev2_sections.json`) when `--draft-rev2` is enabled.
7. Optional assembled Rev-2 narrative (`<output>_rev2_draft.md`) when `--assemble-rev2` is enabled.
8. Rev-2 revision appendix with rationale and traceability (`<output>_rev2_appendix.md`) produced when `--assemble-rev2` is enabled.
9. Companion provenance feed (`<output>_provenance.json`) aligning outputs to SYS-001 provenance guidance and error taxonomy versions.
10. Canonical artifacts: `<output>_comment_resolution_matrix.json` and `<output>_provenance_record.json`, which implement the spectrum-systems contracts for interoperability.

## Czar architecture context
- This repository is an operational engine repo in the czar org and defers to `spectrum-systems` as the constitutional source of truth.
- Upstream systems such as `working-paper-review-engine` emit canonical `reviewer_comment_set` artifacts; this engine validates and consumes them (or adapts legacy matrices) before transformation.
- The engine produces canonical `comment_resolution_matrix` artifacts plus provenance records for structured review, revision tracking, and downstream reporting.
- Contract conformance is what enables interoperability; adapters for legacy spreadsheets remain available but canonical JSON artifacts are preferred going forward.

## Usage

```bash
python -m comment_resolution_engine.cli \
  --comments inputs/comment_resolution_matrix.xlsx \
  --report inputs/report_rev1.pdf \
  --report inputs/report_rev2.pdf \
  --output outputs/resolved_matrix.xlsx \
  --include-metadata-columns \
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

The CLI also writes canonical contract artifacts alongside the workbook:
`<output>_comment_resolution_matrix.json` and `<output>_provenance_record.json` implement the spectrum-systems contracts for downstream interoperability.

To consume a shared rules pack (e.g., spectrum-systems starter rules), point the CLI at the rules directory. Rules are applied deterministically ahead of local fallbacks.

```bash
python -m comment_resolution_engine.cli \
  --comments examples/sample_comment_matrix.csv \
  --report inputs/report_rev1.pdf \
  --report inputs/report_rev2.pdf \
  --output outputs/resolved_matrix.xlsx \
  --rules-path ../spectrum-systems/rules/comment-resolution \
  --rules-profile default \
  --rules-version 0.1.0 \
  --rules-strict
```

When `--rules-path` is omitted, the engine uses local canonical definitions, issue heuristics, disposition logic, and validation as a fallback.

At least one `--report` argument is required. If a comment references a report version (e.g., `rev3` or a filename stem) without a matching PDF upload, the pipeline stops with a clear error.

## Rule packs and validation
- External rule packs are validated at load time for structure, required fields, and enum values (disposition, workflow status, validation status, error_category).
- Strictness levels:
  - **permissive** (default at runtime): unknown keys become warnings captured in provenance metadata.
  - **strict** (recommended for tests/CI): unknown keys and missing required fields raise SCHEMA/VALIDATION errors.
- Run a self-check without executing the full pipeline:

```bash
python -m comment_resolution_engine.cli --validate-rules --rules-path ../spectrum-systems/rules/comment-resolution --rules-strict
```

- Profile overrides must supply lists of rule overrides keyed by section (`canonical_terms`, `issue_patterns`, `disposition_rules`, `drafting_rules`, `validation_rules`). Malformed overrides fail fast in strict mode.

## Configure column mappings
- Copy `config/column_mapping.example.yaml` to `config/column_mapping.yaml`.
- Update `columns` to point to your canonical headers if they differ.
- Add local header variants under `synonyms` (e.g., `Internal Comments`, `Accept/Reject`, `Proposed Resolution`).
- Pass your config with `--config` in the CLI.

## PDF handling
- PDF parsing is intentionally lightweight and best effort.
- Multiple working paper revisions are indexed separately (rev1, rev2, rev3...). The first `--report` is treated as `rev1` unless the filename already contains `revN`.
- If a PDF is provided and a line reference is present, nearby numbered lines are pulled into `Report Context`; otherwise a placeholder is added. Referencing a `revN` without uploading the matching PDF stops the pipeline with a PROVENANCE_ERROR.

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

## Error taxonomy and provenance
- Every validation or ingest failure is surfaced with a structured category: `EXTRACTION_ERROR`, `SCHEMA_ERROR`, `GENERATION_ERROR`, `PROVENANCE_ERROR`, or `VALIDATION_ERROR`.
- Provenance metadata is emitted per row and per patch, including record identifiers, revision lineage, workflow identifiers, schema/spec versions, and confidence/review status.
