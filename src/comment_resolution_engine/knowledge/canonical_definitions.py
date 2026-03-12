from __future__ import annotations

CANONICAL_TERMS = {
    "population_impact_metric": {
        "keywords": ["population impact", "impact metric", "population metric"],
        "definition": "An analytical estimate used to provide context for study results by approximating population associated with areas where deployment may be limited. It does not itself impose regulatory constraints.",
        "rationale": "Do not characterize this metric as determinative of licensing or auction eligibility; it frames analytical context only.",
    },
    "methodology_scope": {
        "keywords": ["methodology scope", "method scope", "analytical rather than regulatory", "analytical approach"],
        "definition": "Methodology outputs are intended to inform technical understanding and are not determinative of licensing eligibility or regulatory status.",
        "rationale": "Clarify that analyses inform decision-makers but are not prescriptive policy requirements.",
    },
    "protection_zone_methodology": {
        "keywords": ["protection zone", "zone methodology", "search tolerance"],
        "definition": "The protection zone methodology describes the analytical boundaries and tolerances used to approximate where additional analysis is prudent; it is not a hard exclusionary rule.",
        "rationale": "Readers should understand the analytical assumptions and limitations without interpreting them as regulatory exclusions.",
    },
}


def lookup_definition(key: str) -> str:
    return CANONICAL_TERMS.get(key, {}).get("definition", "")


def lookup_rationale(key: str) -> str:
    return CANONICAL_TERMS.get(key, {}).get("rationale", "")


def match_canonical_term(text: str) -> str:
    lowered = (text or "").lower()
    for key, payload in CANONICAL_TERMS.items():
        for keyword in payload.get("keywords", []):
            if keyword.lower() in lowered:
                return key
    return ""
