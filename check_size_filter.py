#!/usr/bin/env python3
"""
Criterion 5: size filtering matches whole sizes, not substrings.

    python check_size_filter.py

Calls search_listings('vintage', size=X) through the MCP server (the same path
the agent uses) for each of the 5 sizes the criterion names. Each size is one
try. For every listing returned, prints its size field and checks the rule:
the requested size must appear as a whole token after the listing's size is
lowercased and split on spaces, slashes, and parentheses.

The raw size of every listing is printed so the PASS/FAIL can be checked by eye.
"""

import re
import sys
from datetime import datetime

from mcp_client import call_tool

SIZES = ["M", "S", "L", "XL", "W30"]


def tokens(size: str | None) -> set[str]:
    return {t for t in re.split(r"[ /()]+", (size or "").lower()) if t}


def main() -> int:
    print("Criterion 5 — size filter, whole-token matching")
    print(f"Produced by: check_size_filter.py::main · {datetime.now():%Y-%m-%d %H:%M}")
    print("Query: search_listings('vintage', size=X) via MCP\n")

    passes = 0
    for i, size in enumerate(SIZES, 1):
        results = call_tool("search_listings", {"description": "vintage", "size": size})
        wanted = tokens(size)
        bad = [r for r in results if not wanted <= tokens(r.get("size"))]
        verdict = "PASS" if not bad else "FAIL"
        passes += verdict == "PASS"

        print(f"Try {i}: size={size!r} -> {len(results)} listings -> {verdict}")
        for r in results:
            flag = "  <-- breaks rule" if r in bad else ""
            print(f"    {r['id']}  size {r.get('size')!r:<20} {r['title']}{flag}")
        print()

    print(f"Result: {passes} of {len(SIZES)} sizes returned no rule-breaking listings.")
    return 0


if __name__ == "__main__":
    sys.exit(main())