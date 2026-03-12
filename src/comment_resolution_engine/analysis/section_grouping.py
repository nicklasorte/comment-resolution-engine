from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List

from ..models import NormalizedComment


def group_by_section(comments: Iterable[NormalizedComment]) -> Dict[str, List[str]]:
    groups: Dict[str, List[str]] = defaultdict(list)
    for c in comments:
        key = (c.section or "Unspecified").strip() or "Unspecified"
        groups[key].append(c.id)
    return dict(groups)


def heat_map(groups: Dict[str, List[str]]) -> Dict[str, tuple[int, str]]:
    heat_levels: Dict[str, tuple[int, str]] = {}
    for section, comment_ids in groups.items():
        count = len(comment_ids)
        if count >= 30:
            level = "STRUCTURALLY_UNSTABLE"
        elif count >= 15:
            level = "HIGH"
        elif count >= 7:
            level = "MODERATE"
        else:
            level = "LOW"
        heat_levels[section] = (count, level)
    return heat_levels
