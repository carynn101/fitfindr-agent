#!/usr/bin/env python3
"""
Diagnostic for the improvement: search relevance.

    python check_relevance.py

Not one of the five criteria. The before run showed search_listings returning
listings that share only one word with the query. This prints, for three probes,
every listing search returns (through MCP, the path the agent uses), plus the
message the empty-search diagnosis gives. Run it before and after the change and
compare.
"""

from datetime import datetime

from agent import explain_empty_search, parse_query
from mcp_client import call_tool

PROBES = [
    ("graphic tee", None, 30.0),        # symptom 1: description mentions
    ("90s track jacket", None, None),   # symptom 3: the retry's search
]


def main() -> None:
    print("Search relevance check")
    print(f"Produced by: check_relevance.py::main · {datetime.now():%Y-%m-%d %H:%M}\n")

    for description, size, max_price in PROBES:
        results = call_tool("search_listings", {
            "description": description, "size": size, "max_price": max_price,
        })
        print(f"search_listings({description!r}, size={size!r}, max_price={max_price!r})"
              f" -> {len(results)} results")
        for r in results:
            print(f"    {r['id']}  ${r['price']:<6} {r['title']}  {r['style_tags']}")
        print()

    query = "graphic tee under $10"   # symptom 2: the diagnosis message
    print(f"explain_empty_search for {query!r}:")
    print(f"    {explain_empty_search(parse_query(query))}")


if __name__ == "__main__":
    main()