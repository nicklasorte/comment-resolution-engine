from __future__ import annotations

from typing import Dict, Iterable, List

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ..models import NormalizedComment


def _union_find(similarity_matrix: np.ndarray, threshold: float) -> Dict[int, int]:
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
            if similarity_matrix[i, j] >= threshold:
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


def assign_clusters(comments: Iterable[NormalizedComment], similarity_threshold: float = 0.55) -> List[str]:
    comments = list(comments)
    if not comments:
        return []

    corpus = [(c.effective_comment or c.effective_suggested_text or c.agency_notes or "").lower() for c in comments]
    if any(text.strip() for text in corpus):
        vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1)
        matrix = vectorizer.fit_transform(corpus)
        sim = cosine_similarity(matrix)
        clusters = _union_find(sim, threshold=similarity_threshold)
        return [f"C{clusters[idx]:03d}" for idx in range(len(comments))]

    return [f"C{idx+1:03d}" for idx in range(len(comments))]
