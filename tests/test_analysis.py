from comment_resolution_engine.analysis.comment_clustering import assign_clusters
from comment_resolution_engine.analysis.intent_classifier import classify_intent
from comment_resolution_engine.models import NormalizedComment


def _comment(cid: str, text: str, ctype: str = "TECHNICAL"):
    return NormalizedComment(
        id=cid,
        reviewer_initials="AB",
        agency="Agency",
        report_version="Draft",
        section="1.0",
        page=1,
        line=10,
        comment_type=ctype,
        agency_notes=text,
        agency_suggested_text="",
        wg_chain_comments="",
        comment_disposition="",
        resolution="",
        raw_row={},
        normalized_type=ctype,
        effective_comment=text,
        effective_suggested_text="",
        report_context="",
    )


def test_assign_clusters_groups_similar_comments():
    comments = [
        _comment("1", "Clarify protection zone definition"),
        _comment("2", "Protection zone definition is unclear"),
        _comment("3", "Add reference to appendix"),
    ]
    clusters = assign_clusters(comments, similarity_threshold=0.4)
    assert clusters.assignments[0] == clusters.assignments[1]
    assert clusters.assignments[2] != clusters.assignments[0]
    assert clusters.clusters[clusters.assignments[0]].cluster_size == 2
    assert clusters.clusters[clusters.assignments[0]].cluster_label


def test_intent_classifier_defaults_to_type():
    comment = _comment("4", "Please clarify the methodology scope", ctype="TECHNICAL")
    assert classify_intent(comment) in {"TECHNICAL_CHALLENGE", "REQUEST_CLARIFICATION"}
