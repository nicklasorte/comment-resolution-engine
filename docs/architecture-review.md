# Technical Architecture Review: comment-resolution-engine

> Reviewer: Claude (claude-sonnet-4-6)
> Branch: claude/review-comment-resolution-40pO8
> Focus: Rule engine design, schema robustness, pipeline correctness, provenance, error taxonomy, code organization, test gaps, and scaling.

---

## 1. Rule Engine Design

### 1.1 `_precedence_rank` is dead metadata

`engine.py:24–34` defines a rank map that is stored in `RuleMatchResult.precedence_rank` but has zero effect on dispatch. The actual sort key across all five `apply_*` methods is `(-priority, rule_id)` (line 37). `issue_pattern` and `disposition` share rank 3; `validation` and `canonical_term` share rank 4. The map is documentation that contradicts itself and could mislead rule authors into thinking rank controls evaluation order.

### 1.2 Conflict detection only fires at the exact same priority level

`_select_first_with_conflicts` (lines 65–104) breaks out of the sorted rule list the moment `priority < best_priority`. If two semantically conflicting rules exist at priorities 100 and 90, the lower-priority rule is silently discarded with no `conflict_with` annotation and no warning. The conflict detection only fires at ties. Rule packs with near-miss priorities — a common author mistake — will silently suppress rules with no audit trail.

### 1.3 Template injection surface in drafting rules

`engine.py:320–326`:
```python
resolution_text = action["replace_text"].format(**context).strip()
```
`context` is built from comment matrix fields including `effective_comment`, `agency_notes`, and `agency_suggested_text` — all externally supplied. A comment containing `{rule_id}` or `{provenance_record_id}` will silently expand those values into the resolution text. If a rule template references a key absent from the context, this raises an uncaught `KeyError` that aborts the pipeline with no `CREError` wrapping. The same exposure applies to `append_resolution`, `prepend_resolution`, and `append_ntia_comment`.

### 1.4 `apply_canonical_rules` is called twice on different object types

`pipeline.py:191` calls it on raw `CommentRecord` objects before normalization. `pipeline.py:213` calls it again on `AnalyzedComment` objects after normalization. Between these two calls, `_hydrate_analyzed_comments` does `AnalyzedComment(**asdict(n))` — a shallow copy. Mutations made by the first application (via `setattr(comment, field, value)` at `engine.py:177`) are carried into the second application's starting state. The second pass matches against already-mutated fields, making its behavior dependent on the first pass. The engine is non-idempotent by construction, and this duplication is untested.

### 1.5 `apply_canonical_rules` mutates comments as a side effect

`engine.py:177` does `setattr(comment, field, value)` unconditionally during a method whose signature implies it returns matches. The mutation is invisible in the type signature and undocumented. Callers that read `comment.canonical_term_used` before and after this call will see different values with no indication of when the change occurred. With hundreds of canonical rules, this creates an ordering-dependent mutation chain.

### 1.6 `RuleEngine.warnings` accumulates with no reset

`engine.py:18` creates `self.warnings: List[str] = []` at construction. The list is never cleared. If a `RuleEngine` instance is reused across multiple pipeline invocations, warnings from early runs contaminate later ones. The pipeline currently creates one engine per run (line 168), so this is latent — but it is a trap for any refactor that pools the engine.

---

## 2. Rule-Pack Schema Robustness

### 2.1 No uniqueness constraint on `rule_id`

`schema_validation.py` validates individual entries but never checks for duplicate `rule_id` values within the same file. `_apply_profile_overrides` (loader.py:104–109) replaces the *first* matching entry by `rule_id`. If a base file has `rule_id: DISP_X` twice, the override replaces the first occurrence and the second is silently preserved. The engine sees two rules with identical IDs. At 300+ rules this is a near-certainty in a multi-author environment.

### 2.2 Profile override lookup is O(n × m)

`_apply_profile_overrides` (loader.py:94–112) performs a linear scan of `base_rules` for each entry in `overrides`. For a pack with 200 disposition rules and a profile with 50 overrides, this is 10,000 comparisons per call, repeated for each of the 5 rule file types. A dict indexed by `rule_id` would reduce this to O(n + m) with one pass.

### 2.3 Version verification is cosmetic

`load_rule_pack` accepts `requested_version` but never validates it against the content of the loaded files. Individual rules have a `version` field, but it is never compared to the request. A caller requesting `"2.0.0"` silently loads a `"1.0.0"` pack. The version appears in provenance as if it was verified.

### 2.4 Unknown `match` keys are silently ignored

The schema validator checks unknown keys in `action` (lines 177–194) and warns or errors. It does not do the same for `match` keys. The matcher (matcher.py:34–83) simply skips unrecognized keys — a rule with `fuzzy_contains: "methodology"` in its match spec will match everything (all conditions vacuously pass) instead of warning. This is particularly dangerous in permissive mode.

### 2.5 `set_field` can mutate arbitrary comment attributes

`engine.py:177` does `setattr(comment, field, value)` without an allowlist. A rule pack with `action: {set_field: {id: "INJECTED", revision: "rev99"}}` silently corrupts the comment's identity and revision before downstream processing.

### 2.6 `RULE_SPECIFIC_FIELDS` is intentionally all empty — but invisibly so

`schema_validation.py:70–76` maps all rule types to empty sets. No comment, assertion, or test indicates this is intentional. When rules need type-specific top-level fields, this map must be updated — but nothing in the code signals that contract.

---

## 3. Pipeline Correctness

### 3.1 Single missing revision aborts the entire run with no recovery

`pipeline.py:197` raises immediately if any one comment lacks a `revision` in a multi-PDF context. For 500 comments, one bad row kills the entire run. A pre-flight validation loop that collects all missing-revision errors before raising would give the user actionable information for a single-pass fix.

### 3.2 `default_revision` is filesystem-ordering-dependent

`pipeline.py:180`:
```python
default_revision = next(iter(pdf_contexts))
```
`pdf_contexts` insertion order depends on how `load_pdf_contexts` processes its inputs — which in turn depends on caller argument order or filesystem glob ordering. For provenance, the "default revision" for comments that lack a `revision` field is non-deterministic across environments.

### 3.3 `apply_run_validations` is called with an incomplete context

`pipeline.py:177–178` calls `apply_run_validations` with only `{"pdf_count": ...}` before PDFs are loaded. The full `run_context` (including `pdf_revisions`, `rules_profile`, `rules_version`) is constructed on lines 182–187, *after* validation. Any validation rule that matches on `pdf_revisions` or `rules_profile` silently never triggers — a dead zone in run-level validation.

### 3.4 `decision_lookup` is silently rebuilt three times without length assertions

`pipeline.py:248, 262, 281` each reassign `decision_lookup = {comment.id: decision for comment, decision in zip(analyzed, decisions)}`. If `analyzed` and `decisions` diverge in length, `zip` silently truncates the shorter iterable, producing an incorrect lookup. No assertion guards `len(analyzed) == len(decisions)`.

### 3.5 No atomic output writes

The pipeline writes seven or more files. There is no staging-and-rename pattern. A crash partway through leaves partial output — a valid Excel file but no provenance JSON, for example — with no way to detect incompleteness.

### 3.6 Canonical rules double-application creates context drift

Because canonical rules mutate the comment object via `setattr`, the context built for the second pass at `pipeline.py:213` reflects field values already changed by the first pass. If the first pass normalizes `revision` from `"Rev 02"` to `"rev2"`, the second pass matches against `"rev2"` and may trigger different or additional canonical rules. The behavior is not compositional and cannot be reasoned about from the rule definitions alone.

---

## 4. Provenance Model

### 4.1 `created_at == updated_at` always

`provenance.py:74–75`:
```python
now = utcnow_iso()
return ProvenanceRecord(..., created_at=now, updated_at=now)
```
`updated_at` is never changed after record construction. For auditability, it should reflect the last time a record was reviewed, approved, or modified. Currently it adds no information beyond `created_at`.

### 4.2 No operator or run identity

`ProvenanceRecord` has no `operator_id`, `pipeline_run_id`, `session_id`, or `invocation_args`. Two pipeline runs producing identical outputs are indistinguishable in provenance. For a system processing regulatory agency comments, the authorizing identity is a compliance requirement.

### 4.3 `record_id` collides across runs

`pipeline.py:101`:
```python
record_id = comment.provenance_record_id or f"prov-{comment.id}"
```
`comment.id` is the comment number from the spreadsheet (e.g., `"1"`, `"42"`). Two runs against the same spreadsheet produce identical `prov-1`, `prov-42`, etc. Any downstream store that uses `record_id` as a key silently overwrites prior records. A run-scoped UUID or timestamp component is required.

### 4.4 `derived_from.raw_row` is unbounded and unfiltered

`pipeline.py:103`: `derived_from = {"raw_row": comment.raw_row}`. This is the full dict of all columns from the input Excel row — potentially including PII, large text blobs, or internal annotations. The provenance JSON is written to disk and intended for audit transmission. There is no scrubbing or field allowlist.

### 4.5 `confidence_score` is an untyped string

`ProvenanceRecord.confidence_score: str` can be `""`, `"HIGH"`, `"MEDIUM"`, `"LOW"`, or a float-as-string. Downstream systems cannot reliably parse or compare it. It should be a typed enum or float in `[0.0, 1.0]`.

### 4.6 `prompt_version` conflated with spec version

`build_provenance_record` defaults `prompt_version` to `SPEC_VERSION` when `None` is passed. Since this pipeline has no LLM prompt templates, the field is semantically meaningless and misleading. Audit consumers may incorrectly interpret it as an LLM prompt hash.

### 4.7 Missing reproducibility fields

No `input_checksum` (hash of the comment matrix file), no `rules_pack_checksum` (hash of the loaded rule YAML files), no `pipeline_invocation_args`. These three fields are required to reproduce a run and to verify that a provenance record was generated from unmodified inputs.

---

## 5. Error Taxonomy Integration

### 5.1 `GENERATION_ERROR` is defined but never raised

`ErrorCategory.GENERATION_ERROR` exists in `errors.py` and the taxonomy doc. No code path raises it. `resolution_generator.py` returns empty strings on all failure paths (e.g., line 138: `return "", "synthesized_from_comment", "LOW", canonical_term`). A failed patch generation is indistinguishable from a successful one that produced no text.

### 5.2 Blocking validation raises inside a partial-match loop

`engine.py:278–279` raises `CREError` after the matching `result` has been appended to `matches`. When the exception propagates, the partial `matches` list is abandoned. Conflict and provenance annotations for that comment are lost. Fields mutated by earlier `apply_canonical_rules` calls are not rolled back.

### 5.3 Validation codes are pipe-delimited strings

`decision.validation_code = "|".join(dict.fromkeys(codes))` (resolution_validator.py:55). This prevents structured querying, requires custom splitting in every consumer, and cannot carry per-code metadata (severity, source rule, etc.). This will create downstream parsing debt as the number of validation codes grows.

### 5.4 `CREError` carries no structured payload

`CREError` stores only `category` and folds the message into the string representation. There is no `details` dict, no `file`/`rule_id` on the base class, and no JSON serialization path. A pipeline runner consuming errors programmatically must parse the string.

---

## 6. Code Organization

### 6.1 `pipeline.py` is a 460-line procedural monolith

`run_pipeline` performs: column mapping, rule pack loading, PDF ingestion, comment normalization, clustering, heat mapping, intent classification, decision building, validation, drafting, provenance record building, shared resolution building, patching, FAQ generation, briefing generation, Rev2 drafting, and writing 7+ output files — all in one function. There are no stage boundaries, no rollback points, and no way to unit test a single stage in isolation.

### 6.2 Two `provenance.py` files with overlapping concerns

`src/comment_resolution_engine/provenance.py` builds `ProvenanceRecord`. `src/comment_resolution_engine/rules/provenance.py` defines `GENERATION_MODE_*` constants and `summarize_rule_matches`. The generation mode constants are imported from the rules submodule but used throughout the top-level pipeline and generation modules. This cross-module dependency is not justified by the package boundary.

### 6.3 `_apply_rule_metadata` duplicated between pipeline and resolution generator

`pipeline.py:72–92` and `resolution_generator.py:154–170` perform nearly identical `hasattr + setattr` operations to copy rule match summary fields onto comment and decision objects. These are not shared. Any new field added to `RuleMatchResult` must be added in both places.

### 6.4 Hardcoded knowledge bases conflict with the rule-pack architecture

`knowledge/canonical_definitions.py` and `knowledge/issue_library.py` are Python dicts masquerading as modules. They are the local fallback when no rule pack is loaded. But in `_choose_resolution_basis` (resolution_generator.py:71), the local `match_canonical_term` is called even when rule matches exist (`if not canonical_term`). A rule pack can set `canonical_term: "methodology_scope_profile"` while the hardcoded `methodology_scope` entry remains active if the profile term has no `lookup_definition` entry. The two systems are not architecturally integrated.

### 6.5 `contracts.py` version constants are unreachable strings

`SPEC_VERSION = "1.0.0"`, `SCHEMA_VERSION = "1.0.0"`, etc. are static string literals with no mechanism to validate them against the `spectrum-systems` architecture repo. As the architecture repo evolves, these constants will silently drift, producing provenance records that claim compliance with a version that has since changed.

---

## 7. Test Coverage Gaps

| Gap | Risk |
|---|---|
| No test for `replace_text` template with missing context key | `KeyError` propagates as unformatted exception |
| No test for duplicate `rule_id` in a single rule file | Silent second-entry behavior, incorrect matching |
| No test for multi-PDF pipeline with mixed-revision comments | `default_revision` non-determinism undetected |
| No test for `updated_at != created_at` | Provenance timestamp field always identical |
| No test for `set_field` with reserved fields (`id`, `revision`) | Silent comment identity corruption |
| No test for unknown `match` keys | Always-matching rule passes validation silently |
| No test for `apply_canonical_rules` double-application order-dependence | Mutation ordering bugs under rule interaction |
| No benchmark for O(n²) clustering at scale | First performance cliff is invisible in CI |
| No test for `_apply_rule_metadata` vs `_apply_summary` divergence | Silent field-copy inconsistency on new fields |
| `test_conflicting_disposition_rules_resolve_deterministically` does not verify alphabetic `rule_id` tiebreaking | Non-determinism under sort is undetected |
| No negative test for `format(**context)` injection | Template expansion errors uncaught and untested |

---

## 8. What Breaks First as Rule Packs Grow

Ordered by expected failure:

**First — Profile override performance.** `_apply_profile_overrides` is O(n × m). A pack with 300 rules and a profile with 100 overrides produces 30,000 linear scans per rule file × 5 files = 150,000 comparisons just to load. At 500 rules this is the first noticeable load-time regression. Fix: index `base_rules` by `rule_id` before applying overrides.

**Second — Per-comment per-rule matching overhead.** `matches_rule` is called separately for each rule, each comment, and each of the five `apply_*` methods. The sort `self._sorted(rules)` is called fresh inside each method invocation (lines 138, 165, 245, 295, 333), including inside per-comment loops. At 500 comments × 200 rules per type × 5 types = 500,000 `matches_rule` evaluations plus 2,500 redundant sorts of lists that don't change between comments. Pre-sorting once at pack load time eliminates all redundant sort cost.

**Third — `RuleMatchResult.context` stores a full context dict copy per match.** `models.py:86`. If context has 50 fields and 10 rules match per comment, a 500-comment run stores 5,000 context copies. The `applied_rules` list is extended multiple times per comment and is serialized into both the Excel and provenance JSON. This is unbounded memory growth proportional to rule pack size × comment volume.

**Fourth — TF-IDF clustering matrix.** `comment_clustering.py:108` builds a full (n × n) cosine similarity matrix in memory. At 500 comments this is manageable. At 2,000 comments it is a 32 MB float64 matrix plus an O(n²) union-find inner loop at lines 52–55. This will become the dominant runtime cost before the rule engine does.

**Fifth — `_label_cluster` re-instantiates `TfidfVectorizer` per cluster.** Line 81. With 200 clusters of average size 3, this is 200 separate vectorizer fits on tiny corpora. This should be a single global fit on the full corpus with per-cluster score aggregation.

**Sixth — Duplicate `rule_id` silent corruption.** As the rule pack grows and multiple authors contribute, duplicate IDs become statistically likely. There is no load-time uniqueness check. The result is silent incorrect matching with no error or warning.

**Seventh — `format(**context)` KeyError cascade.** As rule packs gain more template actions and the comment matrix gains more columns, the chance that a template references a key absent in some comments' context grows. The first missing field in a `replace_text` action will abort the entire pipeline mid-loop with an unformatted `KeyError`.

---

## 9. Summary: Highest-Priority Fixes

1. **Add `rule_id` uniqueness validation** in `validate_rules_payload` — one loop, O(n), prevents silent corruption.
2. **Pre-sort rule lists once at pack load time**, not inside per-comment loops.
3. **Replace `format(**context)` with a safe template renderer** that catches `KeyError` and raises `CREError(GENERATION_ERROR, ...)`.
4. **Add an allowlist to `set_field`** — never allow mutation of identity fields (`id`, `revision`, `record_type`, `provenance_record_id`).
5. **Add `match` key validation** against the known operator set, the same way action keys are validated today.
6. **Add `pipeline_run_id` and operator identity** to `ProvenanceRecord` before the first production use.
7. **Replace pipe-delimited `validation_code`** with a structured list field.
8. **Remove the second `apply_canonical_rules` call** or make it idempotent by checking whether the field is already set before mutating.
9. **Break `run_pipeline` into named stages** with explicit input/output contracts so individual stages can be tested in isolation.
10. **Add `input_checksum` and `rules_pack_checksum`** to `ProvenanceRecord` for reproducibility verification.
