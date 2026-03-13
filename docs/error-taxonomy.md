# Error taxonomy (SYS-001)

All surfaced errors are categorized so automation can react consistently:
- `EXTRACTION_ERROR`: Missing or unreadable dependencies and source files.
- `SCHEMA_ERROR`: Input column/header/schema mismatches.
- `GENERATION_ERROR`: Failures during text generation or patch building.
- `PROVENANCE_ERROR`: Missing or mismatched revision lineage and uploaded sources.
- `VALIDATION_ERROR`: Deterministic validation failures on comment content or dispositions.

The CLI prints the category with the message, and structured outputs propagate taxonomy versions from `comment_resolution_engine.contracts`.
