from __future__ import annotations

from typing import Dict, Iterable, List


def aggregate_metrics(results: Iterable[dict]) -> Dict[str, float]:
    results = list(results)
    if not results:
        return {}
    keys = set()
    for result in results:
        keys.update(result.get("metrics", {}).keys())
    aggregated: Dict[str, float] = {}
    for key in sorted(keys):
        aggregated[key] = sum(r.get("metrics", {}).get(key, 0.0) for r in results) / len(results)
    return aggregated


def render_markdown(results: List[dict], aggregate: Dict[str, float]) -> str:
    lines: List[str] = ["# Golden Evaluation Report"]
    if aggregate:
        lines.append("## Aggregate metrics")
        for key, value in aggregate.items():
            lines.append(f"- {key}: {value:.3f}")

    for result in results:
        lines.append(f"## Case {result.get('case_id')}")
        metrics = result.get("metrics", {})
        for key, value in metrics.items():
            lines.append(f"- {key}: {value:.3f}")
        queue = result.get("queue") or []
        if queue:
            lines.append(f"- queued_for_review: {', '.join(queue)}")
    return "\n".join(lines)
