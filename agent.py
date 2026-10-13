"""
The FitFindr planning loop.

This is the file that makes FitFindr an agent rather than a script. The loop
decides which step to run next based on what the last step returned, and every
tool reads its inputs from the session rather than from the previous call.

    python agent.py          runs a matching query and an impossible one

search_listings and create_fit_card are called through the MCP server
(mcp_server.py) via mcp_client.call_tool. suggest_outfit is called directly.

Branch rule:
    If search_listings returns an empty list, work out which filter caused it,
    put a message naming what to change in session["error"], and stop.
    Otherwise, take the first result and go to suggest_outfit, then
    create_fit_card.
"""

import re

import config
import trace
from tools import suggest_outfit, _platform
from generate import ModelUnavailable  # noqa: F401 — handled in unit 4
from mcp_client import call_tool


# ── session state ─────────────────────────────────────────────────────────────

def new_session(query: str, wardrobe: dict) -> dict:
    """
    A fresh session for one user interaction.

    The session is the single source of truth for a run. Every tool result goes
    in here, and the next tool reads it back out.
    """
    return {
        "query": query,              # what the user typed
        "parsed": {},                # description / size / max_price pulled out of it
        "search_results": [],        # everything search_listings returned
        "selected_item": None,       # the one chosen — goes into suggest_outfit
        "wardrobe": wardrobe,        # the user's wardrobe
        "outfit_suggestion": None,   # what suggest_outfit returned
        "fit_card": None,            # what create_fit_card returned
        "error": None,               # set when the run ended early
        "steps": [],                 # the order the loop ran its steps in
    }


# ── MCP-backed tool calls ─────────────────────────────────────────────────────

def _search(description: str, size: str | None, max_price: float | None) -> list[dict]:
    """search_listings, called through the MCP server. Every search goes through here."""
    return call_tool("search_listings", {
        "description": description,
        "size": size,
        "max_price": max_price,
    })


def _fit_card(outfit: str, new_item: dict) -> str:
    """create_fit_card, called through the MCP server."""
    return call_tool("create_fit_card", {"outfit": outfit, "new_item": new_item})


# ── query parsing (regex, no model call) ─────────────────────────────────────

_PRICE_PATTERNS = [
    r"(?:under|below|less than|max|up to)?\s*\$\s*(\d+(?:\.\d+)?)",
    r"\b(?:under|below|less than|up to)\s+(\d+(?:\.\d+)?)\b",
]
_SIZE_PATTERN = r"\bsize\s+([a-z]?\d+(?:\s+l\d+)?|[a-z]+(?:/[a-z]+)?)\b"
_FILLER = {
    "a", "an", "the", "i", "im", "i'm", "want", "need", "looking", "for",
    "in", "with", "some", "find", "me", "please", "under", "below", "size",
}


def parse_query(query: str) -> dict:
    """
    Pull a max_price, a size, and a description out of a plain-language query.

        'vintage graphic tee under $30, size M'
        -> {'description': 'vintage graphic tee', 'size': 'M', 'max_price': 30.0}
    """
    text = query.lower()
    max_price = None
    size = None

    for pattern in _PRICE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            max_price = float(match.group(1))
            text = text[: match.start()] + " " + text[match.end():]
            break

    match = re.search(_SIZE_PATTERN, text)
    if match:
        size = match.group(1).upper()
        text = text[: match.start()] + " " + text[match.end():]

    words = re.findall(r"[a-z0-9'/-]+", text)
    description = " ".join(w for w in words if w not in _FILLER)

    return {"description": description, "size": size, "max_price": max_price}


# ── the empty-search message ──────────────────────────────────────────────────

def explain_empty_search(parsed: dict) -> str:
    """
    Work out which filter removed every match by re-running the search with
    filters relaxed one at a time, and say what to change. Search makes no
    model call, so this costs nothing.
    """
    desc = parsed["description"]
    size = parsed["size"]
    price = parsed["max_price"]

    if not desc:
        return (
            "I couldn't tell what kind of item you're looking for. Add a few "
            "words describing it, like 'graphic tee' or 'denim jacket'."
        )

    size_part = f" in size {size}" if size else ""
    price_part = f" under ${price:g}" if price is not None else ""

    if price is not None:
        without_price = _search(desc, size, None)
        if without_price:
            cheapest = min(without_price, key=lambda l: l["price"])
            return (
                f"Nothing matching '{desc}'{size_part}{price_part}. The cheapest "
                f"match is ${cheapest['price']:g} ({cheapest['title']} on "
                f"{_platform(cheapest)}). Try raising your max price to "
                f"${cheapest['price']:g}."
            )

    if size:
        without_size = _search(desc, None, price)
        if without_size:
            sizes = sorted({l["size"] for l in without_size})
            return (
                f"Nothing matching '{desc}' in size {size}{price_part}. It's "
                f"available in: {', '.join(sizes)}. Try one of those sizes, or "
                f"leave the size out."
            )

    if size and price is not None and _search(desc, None, None):
        return (
            f"Nothing matching '{desc}' with both size {size} and a "
            f"${price:g} limit. Try removing the size and raising your price."
        )

    return (
        f"No listings match '{desc}' at all. Try broader words, like a "
        f"category ('dress', 'jacket', 'jeans') or a style ('vintage', "
        f"'y2k', 'streetwear')."
    )


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Run the loop once and return the finished session.

    Each pass runs one step and chooses the next one from what that step
    returned. The run ends when the next step is "done".

    Returns:
        The session dict. Check session["error"] first: if it isn't None, the
        run ended early and the later fields are still None.
    """
    session = new_session(query, wardrobe)
    next_step = "parse"
    iterations = 0

    while next_step != "done":
        iterations += 1
        trace.check_iterations(iterations)
        session["steps"].append(next_step)

        if next_step == "parse":
            session["parsed"] = parse_query(session["query"])
            next_step = "search"

        elif next_step == "search":
            p = session["parsed"]
            session["search_results"] = _search(
                p["description"], p["size"], p["max_price"]
            )
            # ── THE BRANCH ──
            if not session["search_results"]:
                next_step = "explain_empty"
            else:
                next_step = "select"

        elif next_step == "explain_empty":
            session["error"] = explain_empty_search(session["parsed"])
            next_step = "done"

        elif next_step == "select":
            session["selected_item"] = session["search_results"][0]
            next_step = "suggest_outfit"

        elif next_step == "suggest_outfit":
            session["outfit_suggestion"] = suggest_outfit(
                session["selected_item"], session["wardrobe"]
            )
            next_step = "create_fit_card"

        elif next_step == "create_fit_card":
            session["fit_card"] = _fit_card(
                session["outfit_suggestion"], session["selected_item"]
            )
            next_step = "done"

    return session


# ── running it directly ───────────────────────────────────────────────────────

def _show(session: dict) -> None:
    print(f"  parsed:   {session['parsed']}")
    print(f"  steps:    {' -> '.join(session['steps'])}")
    if session["error"]:
        print(f"  stopped:  {session['error']}")
        print(f"  fit_card is {session['fit_card']!r} — it should still be None here")
        return

    item = session["selected_item"] or {}
    print(f"  found:    {item.get('title')} — ${item.get('price')} on {item.get('platform')} [{item.get('id')}]")
    print(f"  outfit:   {session['outfit_suggestion']}")
    print(f"  fit card: {session['fit_card']}")


if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe

    print("=== A query the data can match ===")
    _show(run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    ))

    print("\n=== A query it can't ===")
    _show(run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    ))

    print(
        "\nThe second one should stop before the fit card. If both paths look "
        "the same,\nthe branch isn't doing anything yet."
    )