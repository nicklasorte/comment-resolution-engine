import json
from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")

from comment_resolution_engine.pipeline import run_pipeline


def test_realistic_integration_pipeline(tmp_path: Path):
    comments_path = tmp_path / "comments.xlsx"
    df = pd.DataFrame(
        {
            "Comment Number": [1, 2, 3, 4],
            "Agency Notes": [
                "Clarify whether the population impact metric is regulatory or just analytical context.",
                "Population impact metric reads like a rule; please clarify intent.",
                "Standardize terminology for protection zones wording.",
                "Methodology scope should state it is analytical not regulatory.",
            ],
            "Comment Type: Editorial/Grammar, Clarification, Technical": ["Technical", "Technical", "Editorial", "Clarification"],
            "Agency Suggested Text Change": [
                "Explain that the population impact metric provides analytical context only.",
                "Note that the metric is not a licensing requirement.",
                "Use consistent term: protection assessment zone.",
                "State that methodology results are informational, not binding.",
            ],
            "Section": ["4.3", "4.4", "5.2", "2.1"],
            "Line": ["12", "13", "45", "8"],
            "Revision": ["rev1", "rev1", "rev1", "rev1"],
        }
    )
    df.to_excel(comments_path, index=False)

    pdf_path = tmp_path / "report.txt"
    pdf_path.write_text(
        "\n".join(
            [
                "10 Introductory text",
                "11 Additional context",
                "12 Population impact metric describes analytical estimate for context only",
                "13 It is not a regulatory requirement",
                "14 Supplemental detail",
                "45 Protection assessment zone terminology placeholder",
            ]
        )
    )

    output_path = tmp_path / "out.xlsx"
    out_df = run_pipeline(
        comments_path=comments_path,
        report_path=pdf_path,
        output_path=output_path,
        config_path=None,
    )

    required_columns = {
        "Comment Cluster Id",
        "Cluster Label",
        "Cluster Size",
        "Patch Text",
        "Patch Source",
        "Patch Confidence",
        "Resolution Basis",
        "Context Confidence",
        "Shared Resolution Id",
        "Validation Code",
        "Validation Status",
        "Resolution",
    }
    assert required_columns.issubset(set(out_df.columns))

    clusters = out_df["Comment Cluster Id"].tolist()
    assert clusters[0] == clusters[1] != clusters[2]

    shared_ids = [str(val) for val in out_df["Shared Resolution Id"].tolist()]
    assert shared_ids[0] not in {"", "nan"}

    assert out_df.iloc[0]["Context Confidence"] == "EXACT_LINE_MATCH"
    assert out_df.iloc[0]["Patch Text"] != ""

    patch_records = json.loads((tmp_path / "out_patches.json").read_text())
    assert patch_records
    assert "confidence" in patch_records[0]
    assert patch_records[0]["new_text"]

    faq_text = (tmp_path / "out_faq.md").read_text()
    assert "FAQ-" in faq_text
    assert "Answer:" in faq_text

    summary_text = (tmp_path / "out_section_summary.md").read_text()
    assert "Section 4.3" in summary_text or "Section 4.4" in summary_text

    briefing_text = (tmp_path / "out_briefing.md").read_text()
    assert "Top issues" in briefing_text
