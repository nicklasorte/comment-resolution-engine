import pandas as pd

from comment_resolution_engine.eval.adjudication_queue import build_adjudication_queue
from comment_resolution_engine.eval.scoring import CommentExpectation


def test_adjudication_queue_filters_rows():
    df = pd.DataFrame(
        {
            "Comment Number": ["1", "2"],
            "Comment Disposition": ["Accept", "Accept"],
            "Validation Status": ["WARN", "PASS"],
            "Report Context": ["", "context"],
            "Context Confidence": ["NO_CONTEXT_FOUND", "EXACT_LINE_MATCH"],
            "Comment Type: Editorial/Grammar, Clarification, Technical": ["Technical", "Clarification"],
            "Resolution": ["", "resolved text"],
            "NTIA Comments": ["ntia", "ntia"],
            "Section Group": ["2.1", "1.1"],
            "Intent Classification": ["TECHNICAL_CHALLENGE", "REQUEST_CLARIFICATION"],
        }
    )

    expectations = {
        "1": CommentExpectation(requires_context=True, require_resolution=True, require_ntia_comment=True, requires_human_review=True),
        "2": CommentExpectation(requires_context=False, require_resolution=True, require_ntia_comment=True, requires_human_review=False),
    }

    queue = build_adjudication_queue(df, expectations)
    assert len(queue) == 1
    entry = queue[0]
    assert entry["comment_id"] == "1"
    joined = " ".join(entry["reasons"])
    assert "validation_status" in joined
    assert "missing_required_context" in joined or "technical_no_context" in joined
    assert "missing_resolution_text" in joined
