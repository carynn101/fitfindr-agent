"""
The runs the test needs. run_eval.py runs every scenario here five times,
with caching off, and writes the run log into results/.

How each criterion in criteria.md is measured:

  1. Happy path completes     -> scenario A, 5 tries of the same query.
  2. Empty search stops early -> the impossible query, 5 tries.
  3. Same item flows through  -> "across 5 different matching queries":
                                 try 1 of A, B, C, D and E (one try per query).
                                 C, D and E exist for this criterion; A and B
                                 are shared with criteria 1 and 4.
  4. Fit card is usable       -> scenario B, 5 tries of the same query
                                 (a different item and platform from A).
  5. Size filter is whole-token -> NOT run here. It calls search_listings
                                 directly for 5 sizes, so it has its own
                                 script: python check_size_filter.py

Diagnostic runs ("criterion": None) aren't one of the five; they cover the
empty-wardrobe failure mode and the retry-without-size stretch feature.
"""

SCENARIOS = [
    {
        # A. Criterion 1 (and query 1 of 5 for criterion 3).
        "name": "A: matching query completes",
        "query": "vintage graphic tee under $30",
        "wardrobe": "example",
        "criterion": 1,
    },
    {
        # Criterion 2: the empty-search branch. Has a size, so the retry
        # also runs, and must still stop before suggest_outfit.
        "name": "impossible query stops early",
        "query": "designer ballgown size XXS under $5",
        "wardrobe": "example",
        "criterion": 2,
    },
    {
        # B. Criterion 4 (and query 2 of 5 for criterion 3).
        # A different item and platform from A ($45, Poshmark).
        "name": "B: fit card for the track jacket",
        "query": "90s track jacket in size M",
        "wardrobe": "example",
        "criterion": 4,
    },
    {
        # C. Criterion 3, query 3 of 5.
        "name": "C: state check, denim jacket",
        "query": "denim jacket under $50",
        "wardrobe": "example",
        "criterion": 3,
    },
    {
        # D. Criterion 3, query 4 of 5.
        "name": "D: state check, platform sneakers",
        "query": "platform sneakers size 8",
        "wardrobe": "example",
        "criterion": 3,
    },
    {
        # E. Criterion 3, query 5 of 5.
        "name": "E: state check, corduroy pants",
        "query": "corduroy pants under $40",
        "wardrobe": "example",
        "criterion": 3,
    },
    {
        # Diagnostic: unit 4 failure mode, empty wardrobe.
        "name": "empty wardrobe",
        "query": "denim jacket under $50",
        "wardrobe": "empty",
        "criterion": None,
    },
    {
        # Diagnostic: stretch feature, retry without the size filter.
        "name": "retry without size",
        "query": "90s track jacket size XS",
        "wardrobe": "example",
        "criterion": None,
    },
]

WARDROBES = ("example", "empty")


def validate() -> list[str]:
    """Complain about anything malformed, before a long run rather than during."""
    problems = []
    for i, scenario in enumerate(SCENARIOS, 1):
        if not scenario.get("query", "").strip():
            problems.append(f"scenario {i} has no query")
        if scenario.get("wardrobe") not in WARDROBES:
            problems.append(
                f"scenario {i} has wardrobe {scenario.get('wardrobe')!r} — "
                f"it should be one of {WARDROBES}"
            )
    return problems