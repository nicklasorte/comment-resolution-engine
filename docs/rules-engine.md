# Rules Engine

The pipeline now consumes external rule packs while preserving deterministic local fallbacks.

## Supported rule files
- `canonical_terms.yaml`: normalize revisions/terms and set canonical terms.
- `issue_patterns.yaml`: classify issue patterns and optionally drive disposition.
- `disposition_rules.yaml`: set disposition/notes/patch templates based on structured matches.
- `drafting_rules.yaml`: post-process generated resolution/NTIA text.
- `validation_rules.yaml`: run blocking or advisory validation (run-level or comment-level).
- `profiles/<profile>.yaml`: optional overlays; rules in a profile replace or extend base rules by `rule_id`.

## Matching and precedence
1. Profile overrides replace/augment base rules (highest precedence).
2. Section-specific hooks reserved for future use.
3. Issue pattern rules are evaluated before canonical term/local heuristics.
4. Canonical term rules run next; local canonical definitions backfill if no rule matches.
5. Local fallbacks handle any remaining logic.
Within a rule type, higher `priority` wins first; disabled rules are skipped. Canonical rules may apply multiple matches in order; disposition/issue/validation rules stop at the first highest-priority match.

## Fallback behavior
- If `--rules-path` is not provided, all behavior reverts to local canonical definitions, issue heuristics, disposition logic, drafting, and validation.
- Missing rule files are tolerated; the engine quietly uses local defaults for those categories.

## Provenance fields
Record-level outputs include `rule_id`, `rule_source`, `rule_version`, `rules_profile`, `rules_version`, `matched_rule_types`, and `generation_mode` when rules contribute. Run-level provenance includes `rules_path`, `rules_profile`, `rules_version`, and `rules_loaded_count`.

## Current limitations
- Matcher is intentionally simple (exact/contains/numeric/list checks); no DSL is supported.
- Section-specific rule hooks exist but are not yet populated.
- Rules are loaded from the filesystem only; no package installation is required.
