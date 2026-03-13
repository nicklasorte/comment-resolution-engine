# Rules Engine

The pipeline now consumes external rule packs while preserving deterministic local fallbacks.

## Supported rule files
- `canonical_terms.yaml`: normalize revisions/terms and set canonical terms.
- `issue_patterns.yaml`: classify issue patterns and optionally drive disposition.
- `disposition_rules.yaml`: set disposition/notes/patch templates based on structured matches.
- `drafting_rules.yaml`: post-process generated resolution/NTIA text.
- `validation_rules.yaml`: run blocking or advisory validation (run-level or comment-level).
- `profiles/<profile>.yaml`: optional overlays; rules in a profile replace or extend base rules by `rule_id`.

## Validation and strictness
- Every rules file is validated at load time for structure, required fields, and enum values (disposition, workflow_status, validation_status, error_category).
- Strictness modes:
  - **permissive** (runtime default): unknown keys become warnings preserved in rule metadata.
  - **strict** (tests/CI): unknown keys or missing required fields raise SCHEMA/VALIDATION errors.
- Validation errors surface as `RulePackLoadError`/`RulePackValidationError` with the offending file, rule_id, and allowed values. Malformed YAML fails before execution.

## Matching and precedence
1. Profile overrides replace/augment base rules (highest precedence).
2. Section-specific hooks reserved for future use.
3. Issue pattern rules are evaluated before canonical term/local heuristics.
4. Canonical term rules run next; local canonical definitions backfill if no rule matches.
5. Local fallbacks handle any remaining logic.
Within a rule type, higher `priority` wins first; disabled rules are skipped. Canonical rules may apply multiple matches in order; disposition/issue/validation rules stop at the first highest-priority match.

## Rule contracts
- Common fields: `rule_id` (required), `rule_type` (required in strict mode), `priority` (int), `enabled` (bool), `match` (mapping), `action` (mapping), `rationale_template`, `patch_template`, `source`, `version`.
- Canonical term rules: `action` must provide `set_field`, `canonical_term`, `replace_with`, or `normalized_value`. Conflicts on the same target field at the same priority are recorded.
- Issue pattern rules: `action` may set `issue_type`, `classification`, `disposition`, or `notes_template`; empty actions warn.
- Disposition rules: `action.disposition` allowed values: `Accept`, `Reject`, `Partial`, `Partial Accept`, `Defer`. `workflow_status` allowed: `open`, `pending`, `resolved`, `needs_review`, `blocked`, `out_of_scope`.
- Drafting rules: string-valued `append_resolution`, `prepend_resolution`, `append_ntia_comment`, or `replace_text`. Multiple rules may apply; conflicting `replace_text` at the same priority is skipped with a conflict marker.
- Validation rules: support `scope` (`run`/`comment`), `status`/`validation_status`, `code`, `notes`, `blocking`/`block`, `error_category` (must match ErrorCategory enum). Blocking rules must supply `error_category` and an error message.

## Conflicts and provenance
- Within a rule type, highest priority wins; ties are resolved deterministically by `rule_id`.
- Conflicts (same priority, different single-value outputs) are marked with `conflict_with` and `skip_reason` in `applied_rules` provenance. Canonical rules still apply non-conflicting field updates.
- Rule provenance now records: `rule_id`, `rule_type`, `rule_source`, `rule_version`, `rules_profile`, `rules_version`, `match_basis`, `precedence_rank`, `applied/skip_reason`, `conflict_with`, `generation_mode`, and the applied action.

## Profile overrides
- Profiles accept lists keyed by section: `canonical_terms`, `issue_patterns`, `disposition_rules`, `drafting_rules`, `validation_rules`.
- Overrides replace base rules by `rule_id`; new `rule_id` entries are appended. Malformed override payloads or unknown sections fail validation in strict mode.

## Self-check / validation command
Validate a rules directory without running the full pipeline:

```bash
python -m comment_resolution_engine.cli --validate-rules --rules-path ../spectrum-systems/rules/comment-resolution --rules-strict
```

The command reports files loaded, rules by type, and any warnings. It returns a non-zero exit code on schema or validation failures.

## Fallback behavior
- If `--rules-path` is not provided, all behavior reverts to local canonical definitions, issue heuristics, disposition logic, drafting, and validation.
- Missing rule files are tolerated; the engine quietly uses local defaults for those categories.

## Provenance fields
Record-level outputs include `rule_id`, `rule_source`, `rule_version`, `rules_profile`, `rules_version`, `matched_rule_types`, and `generation_mode` when rules contribute. Run-level provenance includes `rules_path`, `rules_profile`, `rules_version`, and `rules_loaded_count`.

## Current limitations
- Matcher is intentionally simple (exact/contains/numeric/list checks); no DSL is supported.
- Section-specific rule hooks exist but are not yet populated.
- Rules are loaded from the filesystem only; no package installation is required.
