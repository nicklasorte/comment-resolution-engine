# Provenance implementation guidance (SYS-001)

comment-resolution-engine emits per-record provenance aligned to spectrum-systems guidance. The provenance companion JSON (`*_provenance.json`) and Excel columns record:
- Stable identifiers (`record_id`, `record_type`, `provenance_record_id`).
- Source lineage (`source_document`, `source_revision`, `resolved_against_revision`, `derived_from`).
- Workflow context (`workflow_name`, `workflow_step`, `generation_mode`).
- Versioning (`schema_version`, `spec_version`, `provenance_guidance_version`, `error_taxonomy_version`, `generated_by_version`).
- Review metadata (`review_status`, `validation_status`, `validation_notes`, `confidence_score`).
- System identity (`generated_by_system`, `generated_by_repo`).
- Timestamps (`created_at`, `updated_at`).

Downstream systems should treat spectrum-systems as the source of truth for field semantics and updates. This repository keeps deterministic defaults and fills gaps when external rulepacks are absent.
