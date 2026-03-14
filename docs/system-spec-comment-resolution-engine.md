# SYS-001 Comment Resolution Engine Spec (pointer)

This repository implements SYS-001 as defined in the spectrum-systems architecture repository. The authoritative specification, workflow, and schema live in spectrum-systems; this file anchors the path referenced in README until the shared spec is synchronized here.

Key contract highlights enforced by this implementation:
- At least one working paper PDF is required; multiple revisions are supported via repeated `--report` flags.
- The comments matrix must include a `Report Version` column when multiple revisions are present; blank values map to the sole uploaded revision when only one PDF is provided.
- A referenced revision without an uploaded PDF triggers a clear PROVENANCE_ERROR.
- Outputs retain revision lineage and provenance metadata alongside validation status and notes.
