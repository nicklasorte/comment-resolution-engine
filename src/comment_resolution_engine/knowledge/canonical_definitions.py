from __future__ import annotations

CANONICAL_DEFINITIONS = {
    "population_impact_metric": "An analytical estimate used to provide context for study results by approximating population associated with areas where deployment may be limited. It does not itself impose regulatory constraints.",
    "methodology_scope": "Methodology outputs are intended to inform technical understanding and are not determinative of licensing eligibility or regulatory status.",
}


def lookup_definition(key: str) -> str:
    return CANONICAL_DEFINITIONS.get(key, "")
