# Contracts Overview

comment-resolution-engine consumes and produces canonical artifacts defined in the spectrum-systems repository (the constitutional source of truth). This engine **does not** redefine or fork those contracts; it acts as a contract-aware consumer/producer within the czar repo org.

Key points:
- Consumes canonical `reviewer_comment_set` artifacts emitted by upstream systems such as working-paper-review-engine (or other reviewers that comply with the contract).
- Produces canonical `comment_resolution_matrix` artifacts plus accompanying `provenance_record` outputs.
- Validates artifacts at system boundaries and fails fast with clear errors when contract mismatches are detected.
- Provenance must be preserved for traceability and auditability; each resolution row carries a provenance record id and the run-level provenance feed is exported.

Local contract metadata
- Machine-readable declaration: `config/contracts/contract_declaration.yaml`
- Standards reference: `config/contracts/spectrum_contracts.yaml` (records upstream source repo and canonical contract references)
- Example artifacts: `examples/contracts/`

Interoperability
- Upstream: working-paper-review-engine (and future reviewers) should emit `reviewer_comment_set` artifacts; adapters exist only for legacy spreadsheets.
- Downstream: reporting and analysis systems should ingest the canonical `comment_resolution_matrix` and `provenance_record` exports, which capture revision links, upstream comment ids, dispositions, responses, and traceability metadata.

Validation boundaries
- Input contract validation: canonical reviewer comment sets are validated on load; legacy matrices are adapted into the canonical shape and validated before processing.
- Output contract validation: the exported matrix and provenance artifacts are validated before writing to disk to avoid silent drift.

Legacy compatibility
- Excel/CSV matrices remain supported as a legacy input/output format, but the canonical JSON artifacts are the preferred interface for interoperability.
