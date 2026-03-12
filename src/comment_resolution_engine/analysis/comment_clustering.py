from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ..knowledge.canonical_definitions import match_canonical_term
from ..models import ClusterInfo, NormalizedComment


@dataclass(slots=True)
class ClusterOutput:
    assignments: List[str]
    clusters: Dict[str, ClusterInfo]


def _parse_section(section: str) -> Tuple[int, ...]:
    parts = [p for p in re.split(r"[^\d]+", str(section)) if p.isdigit()]
    return tuple(int(p) for p in parts)


def _sections_are_near(a: str | None, b: str | None, max_gap: int = 1) -> bool:
    if not a or not b:
        return True
    parsed_a = _parse_section(a)
    parsed_b = _parse_section(b)
    if not parsed_a or not parsed_b:
        return (a or "").strip().lower() == (b or "").strip().lower()
    if parsed_a[0] != parsed_b[0]:
        return abs(parsed_a[0] - parsed_b[0]) <= max_gap
    return abs(parsed_a[0] - parsed_b[0]) <= max_gap or parsed_a[:2] == parsed_b[:2]


def _union_find(similarity_matrix: np.ndarray, threshold: float, sections: list[str]) -> Dict[int, int]:
    parent = list(range(similarity_matrix.shape[0]))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[ry] = rx

    for i in range(similarity_matrix.shape[0]):
        for j in range(i + 1, similarity_matrix.shape[0]):
            if similarity_matrix[i, j] >= threshold and _sections_are_near(sections[i], sections[j]):
                union(i, j)

    clusters: Dict[int, int] = {}
    cluster_ids: Dict[int, int] = {}
    next_id = 1
    for idx in range(similarity_matrix.shape[0]):
        root = find(idx)
        if root not in cluster_ids:
            cluster_ids[root] = next_id
            next_id += 1
        clusters[idx] = cluster_ids[root]
    return clusters


def _representative(similarity_matrix: np.ndarray, indices: list[int]) -> int:
    if len(indices) == 1:
        return indices[0]
    submatrix = similarity_matrix[np.ix_(indices, indices)]
    sums = submatrix.sum(axis=1)
    return indices[int(np.argmax(sums))]


def _label_cluster(texts: list[str]) -> str:
    cleaned = [t for t in texts if t.strip()]
    if not cleaned:
        return "General clarification"
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(2, 3), min_df=1)
    try:
        matrix = vectorizer.fit_transform(cleaned)
    except ValueError:
        return cleaned[0][:80]
    scores = np.asarray(matrix.sum(axis=0)).ravel()
    features = vectorizer.get_feature_names_out()
    if not len(features):
        return cleaned[0][:80]
    top_indices = scores.argsort()[::-1][:3]
    phrases = [features[i] for i in top_indices if scores[i] > 0]
    if not phrases:
        return cleaned[0][:80]
    phrase_text = " / ".join(dict.fromkeys([p.strip() for p in phrases]))
    return phrase_text.capitalize()


def assign_clusters(comments: Iterable[NormalizedComment], similarity_threshold: float = 0.4) -> ClusterOutput:
    comments = list(comments)
    if not comments:
        return ClusterOutput(assignments=[], clusters={})

    sections = [c.section for c in comments]
    corpus = [(c.effective_comment or c.effective_suggested_text or c.agency_notes or "").lower() for c in comments]
    if any(text.strip() for text in corpus):
        vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1)
        matrix = vectorizer.fit_transform(corpus)
        sim = cosine_similarity(matrix)
        canonical_terms = [match_canonical_term(text) for text in corpus]
        for i in range(sim.shape[0]):
            for j in range(i + 1, sim.shape[0]):
                if canonical_terms[i] and canonical_terms[i] == canonical_terms[j] and _sections_are_near(sections[i], sections[j]):
                    sim[i, j] = sim[j, i] = max(sim[i, j], 0.99)
        unioned = _union_find(sim, threshold=similarity_threshold, sections=sections)
        assignments = [f"C{unioned[idx]:03d}" for idx in range(len(comments))]

        cluster_members: Dict[str, list[int]] = {}
        for idx, cid in enumerate(assignments):
            cluster_members.setdefault(cid, []).append(idx)

        cluster_metadata: Dict[str, ClusterInfo] = {}
        for cid, member_indices in cluster_members.items():
            rep_idx = _representative(sim, member_indices)
            rep_comment = comments[rep_idx]
            label = _label_cluster([corpus[i] for i in member_indices])
            cluster_metadata[cid] = ClusterInfo(
                cluster_id=cid,
                cluster_label=label,
                cluster_size=len(member_indices),
                representative_comment_id=rep_comment.id,
                sections=sorted({comments[i].section or "" for i in member_indices}),
            )
        return ClusterOutput(assignments=assignments, clusters=cluster_metadata)

    assignments = [f"C{idx+1:03d}" for idx in range(len(comments))]
    cluster_metadata = {
        cid: ClusterInfo(
            cluster_id=cid,
            cluster_label="General clarification",
            cluster_size=1,
            representative_comment_id=comments[idx].id,
            sections=[comments[idx].section or ""],
        )
        for idx, cid in enumerate(assignments)
    }
    return ClusterOutput(assignments=assignments, clusters=cluster_metadata)
