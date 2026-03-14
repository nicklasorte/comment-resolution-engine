# Golden Regression Harness

Deterministic evaluation fixtures for the comment resolution engine. These cases mirror the SYS-001 / provenance / error-taxonomy guardrails described in the repository README and are intended to catch regressions before they reach reviewers.

## Layout
- `fixtures/<case_id>/comments.csv` – input matrix for the case (must include `Revision`).
- `fixtures/<case_id>/report_rev*.txt` – working-paper excerpts used as PDF stand-ins for deterministic line/context extraction.
- `expected/<case_id>_expected.json` – case manifest and assertions (see below).

## Expected file schema
```json
{
  "case_id": "sample_case_01",
  "inputs": {
    "comments_path": "golden/fixtures/sample_case_01/comments.csv",
    "reports": ["golden/fixtures/sample_case_01/report_rev1.txt"],
    "config_path": null,
    "rules_path": null,
    "rules_profile": null,
    "rules_version": null
  },
  "expectations": {
    "comments": {
      "1": {
        "disposition": "Accept",
        "intent": "TECHNICAL_CHALLENGE",
        "section_group": "2.1",
        "requires_context": true,
        "requires_human_review": false,
        "require_resolution": true,
        "require_ntia_comment": true,
        "validation_status_min": "PASS",
        "provenance_fields": ["record_id", "source_document", "workflow_name", "workflow_step", "generation_mode"]
      }
    },
    "section_heatmap": {"2.1": "LOW"}
  }
}
```

## How to run locally
```bash
python -m comment_resolution_engine.eval.golden_runner --output-dir outputs/golden
```

This command:
1. Discovers all `*_expected.json` manifests.
2. Runs the pipeline for each case.
3. Scores deterministically using `comment_resolution_engine.eval.scoring`.
4. Emits JSON + Markdown summaries and a reviewer adjudication queue export containing only rows needing human review.

Outputs default to the provided `--output-dir` and respect provenance guidance by carrying forward the generated provenance feed.
