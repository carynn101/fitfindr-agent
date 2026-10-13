"""
FitFindr's MCP server.

Exposes two FitFindr tools over the Model Context Protocol, so any MCP client
(not just this project's agent) can call them:

    search_listings   required for unit 4: no model call, deterministic
    create_fit_card   stretch: a second tool, which does call the model

    python mcp_server.py        starts the server (it waits on stdin; that's expected)
    python mcp_client.py        asks the server what it offers

The implementations live in tools.py and are imported under aliases, so the
registered functions don't call themselves.
"""

from mcp.server.fastmcp import FastMCP

from tools import search_listings as _search_listings_impl
from tools import create_fit_card as _create_fit_card_impl

# log_level="WARNING" keeps the server from printing an INFO line per request.
mcp = FastMCP("fitfindr", log_level="WARNING")


@mcp.tool()
def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search 40 secondhand clothing listings (Depop, Poshmark, thredUp) by keywords,
    with an optional size and an optional maximum price in US dollars (inclusive).

    description: keywords for the item, e.g. "vintage graphic tee".
    size: a size such as "M", "8", or "W30 L30", matched as a whole token,
          so "M" matches "S/M" but "L" does not match "XL". Omit to skip.
    max_price: price ceiling in US dollars, e.g. 30.0. Omit to skip.

    Returns up to 10 listing objects, best keyword match first (ties go to the
    lower price). Each has: id, title, description, category, style_tags (list),
    size, condition, price (number), colors (list), brand (string or null),
    platform. Returns an empty list when nothing matches; it never errors on
    zero results.
    """
    return _search_listings_impl(description, size, max_price)


@mcp.tool()
def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Write a short social-media caption (2-4 sentences) for a thrifted item and
    the outfit it's styled in. The caption names the item, its price as a
    dollar amount (e.g. "$24"), and the platform it was found on, once each.
    Wording varies between calls.

    outfit: a description of how the item is being styled (plain text).
    new_item: one listing object as returned by search_listings; uses its
              title, price, and platform.

    If outfit is empty or only whitespace, no caption is generated and the tool
    returns a message saying a fit card needs an outfit suggestion. Raises an
    error if the language model can't be reached.
    """
    return _create_fit_card_impl(outfit, new_item)


if __name__ == "__main__":
    mcp.run()