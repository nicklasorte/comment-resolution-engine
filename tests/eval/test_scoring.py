from pathlib import Path

import pandas as pd

from comment_resolution_engine.eval.scoring import GoldenExpectations, CommentExpectation, score_case


def test_scoring_computes_expected_metrics():
    df = pd.DataFrame(
        {
            "Comment Number": ["1", "2"],
            "Comment Disposition": ["Accept", "Reject"],
            "Intent Classification": ["REQUEST_CHANGE", "SUGGEST_EDIT"],
            "Section Group": ["2.1", "1.1"],
            "Resolution": ["text", ""],
            "NTIA Comments": ["note1", "note2"],
            "Report Context": ["context here", ""],
            "Validation Status": ["PASS", "WARN"],
            "Provenance Record Id": ["prov-1", "prov-2"],
            "Heat Level": ["LOW", "LOW"],
        }
    )
    provenance_records = [
        {
            "record_id": "prov-1",
            "source_document": "doc1",
            "resolved_against_revision": "rev1",
            "workflow_name": "workflow",
            "workflow_step": "step",
            "generation_mode": "local",
        },
        {
            "record_id": "prov-2",
            "source_document": "doc1",
            "resolved_against_revision": "rev1",
            "workflow_name": "workflow",
            "workflow_step": "step",
            "generation_mode": "local",
        },
    ]
    expectations = GoldenExpectations(
        comments={
            "1": CommentExpectation(
                disposition="Accept",
                intent="REQUEST_CHANGE",
                section_group="2.1",
                requires_context=True,
                validation_status_min="PASS",
                provenance_fields=["record_id", "source_document", "workflow_name", "generation_mode"],
            ),
            "2": CommentExpectation(
                disposition="Reject",
                intent="SUGGEST_EDIT",
                section_group="1.1",
                requires_context=False,
                requires_human_review=True,
                validation_status_min="WARN",
                provenance_fields=["record_id", "source_document", "workflow_name"],
            ),
        },
        section_heatmap={"2.1": "LOW", "1.1": "LOW"},
    )

    result = score_case("case", df, provenance_records, ["2"], expectations)
    metrics = result["metrics"]

    assert metrics["disposition_accuracy"] == 1.0
    assert metrics["intent_accuracy"] == 1.0
    assert metrics["required_resolution_presence_rate"] == 0.5
    assert metrics["required_ntia_comment_presence_rate"] == 1.0
    assert metrics["context_attachment_rate"] == 1.0
    assert metrics["provenance_completeness_rate"] == 1.0
    assert metrics["validation_pass_rate"] == 1.0
    assert metrics["human_review_precision"] == 1.0
    assert metrics["human_review_recall"] == 1.0
    assert metrics["section_heatmap_stability"] == 1.0
