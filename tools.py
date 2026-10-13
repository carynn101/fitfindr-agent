"""
The three FitFindr tools.

Each one is a standalone function that can be called and tested on its own,
before any of them are wired into the planning loop.

    search_listings(description, size, max_price)  -> list[dict]
    suggest_outfit(new_item, wardrobe)             -> str
    create_fit_card(outfit, new_item)              -> str

Specs for all three (inputs, return values, empty cases) are in the README
under Tool Inventory.
"""

import re

import config
from generate import generate
from utils.data_loader import load_listings


# ── shared helpers ────────────────────────────────────────────────────────────

# Words that carry no meaning for matching a listing.
_STOPWORDS = {
    "a", "an", "the", "and", "or", "for", "with", "in", "on", "of", "to",
    "i", "im", "i'm", "me", "my", "want", "wanted", "need", "looking", "look",
    "find", "some", "something", "any", "that", "this", "is", "it", "under",
    "below", "less", "than", "max", "around", "about", "size", "please",
}

_PLATFORM_NAMES = {"depop": "Depop", "poshmark": "Poshmark", "thredup": "thredUp"}


def _words(text: str | None) -> set[str]:
    """Lowercase word tokens of a string."""
    return set(re.findall(r"[a-z0-9']+", (text or "").lower()))


def _size_tokens(size: str | None) -> set[str]:
    """Split a size string on spaces, slashes, and parentheses: 'S/M' -> {'s', 'm'}."""
    return {t for t in re.split(r"[\s/()]+", (size or "").lower()) if t}


def _size_matches(listing_size: str | None, wanted: str) -> bool:
    """
    Whole-token size match. 'M' matches 'S/M' but 'L' does not match 'XL'.
    A multi-token request ('W30 L30') needs every token present.
    """
    wanted_tokens = _size_tokens(wanted)
    return bool(wanted_tokens) and wanted_tokens <= _size_tokens(listing_size)


def _format_price(price: float) -> str:
    """24.0 -> '$24', 24.5 -> '$24.50'."""
    return f"${int(price)}" if float(price).is_integer() else f"${price:.2f}"


def _platform(item: dict) -> str:
    raw = item.get("platform") or "unknown platform"
    return _PLATFORM_NAMES.get(raw.lower(), raw)


def _describe_item(item: dict) -> str:
    """The listing as plain text for a prompt. Skips brand when it's missing."""
    lines = [
        f"Title: {item.get('title')}",
        f"Category: {item.get('category')}",
        f"Colors: {', '.join(item.get('colors') or [])}",
        f"Style tags: {', '.join(item.get('style_tags') or [])}",
        f"Size: {item.get('size')}",
        f"Condition: {item.get('condition')}",
        f"Price: {_format_price(item.get('price', 0))}",
        f"Platform: {_platform(item)}",
    ]
    if item.get("brand"):
        lines.insert(1, f"Brand: {item['brand']}")
    return "\n".join(lines)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Return listings matching the description, size, and price ceiling, best
    match first. Returns [] when nothing matches -- never None, never raises.

    Scoring: each keyword scores 2 if it appears in title / style_tags /
    category, 1 if it appears only in description / colors / brand.
    Ties go to the lower price.
    """
    keywords = _words(description) - _STOPWORDS
    if not keywords:
        return []

    scored = []
    for listing in load_listings():
        if max_price is not None and listing.get("price", 0) > max_price:
            continue
        if size and not _size_matches(listing.get("size"), size):
            continue

        primary = (
            _words(listing.get("title"))
            | _words(" ".join(listing.get("style_tags") or []))
            | _words(listing.get("category"))
        )
        secondary = (
            _words(listing.get("description"))
            | _words(" ".join(listing.get("colors") or []))
            | _words(listing.get("brand"))
        )

        score = 0
        for word in keywords:
            if word in primary:
                score += 2
            elif word in secondary:
                score += 1

        if score > 0:
            scored.append((score, listing))

    scored.sort(key=lambda pair: (-pair[0], pair[1].get("price", 0)))
    return [listing for _, listing in scored[: config.SEARCH_RESULT_LIMIT]]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

_OUTFIT_SYSTEM = (
    "You are a personal stylist who specializes in secondhand fashion. "
    "Be concrete and practical. Write plain text with no markdown headers. "
    "Keep the whole answer under 120 words."
)


def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Suggest one or two outfits built around new_item. With wardrobe items,
    each outfit names at least one owned piece. With an empty wardrobe,
    returns general styling advice. Always returns a non-empty string.
    """
    items = (wardrobe or {}).get("items") or []
    item_text = _describe_item(new_item)

    if not items:
        prompt = (
            f"Someone is considering buying this thrifted item:\n\n{item_text}\n\n"
            "They haven't shared their wardrobe. Suggest one or two outfits "
            "built around this item, describing the general kinds of pieces "
            "that pair well with it (for example 'straight-leg dark denim' or "
            "'chunky white sneakers')."
        )
    else:
        wardrobe_lines = "\n".join(
            f"- {w.get('name')} ({w.get('category')}; "
            f"colors: {', '.join(w.get('colors') or [])}; "
            f"style: {', '.join(w.get('style_tags') or [])}"
            f"{'; ' + w['notes'] if w.get('notes') else ''})"
            for w in items
        )
        prompt = (
            f"Someone is considering buying this thrifted item:\n\n{item_text}\n\n"
            f"Here is what they already own:\n{wardrobe_lines}\n\n"
            "Suggest one or two complete outfits built around the new item. "
            "Each outfit must use at least one piece from their wardrobe, "
            "named exactly as it appears in the list above."
        )

    result = generate(prompt, system=_OUTFIT_SYSTEM)
    if not result.strip():
        return (
            f"Style the {new_item.get('title', 'item')} with simple basics in "
            "neutral colors and let it be the focus of the outfit."
        )
    return result


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

_CARD_SYSTEM = (
    "You write short, authentic social media captions for thrifted outfits. "
    "Sound like a real person posting their find, not a product listing."
)


def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Write a 2-4 sentence postable caption mentioning the item, its price, and
    its platform once each. If outfit is empty, makes no model call and
    returns a message instead.
    """
    title = new_item.get("title", "this item")
    if not outfit or not outfit.strip():
        return f"Can't write a fit card without an outfit suggestion for {title}."

    price = _format_price(new_item.get("price", 0))
    platform = _platform(new_item)

    prompt = (
        f"Write a caption for a post about this thrift find.\n\n"
        f"Item: {title}\n"
        f"Price: {price}\n"
        f"Found on: {platform}\n"
        f"How it's being styled:\n{outfit}\n\n"
        "Rules:\n"
        "- 2 to 4 sentences, under 60 words total.\n"
        f"- Mention the price written exactly as {price}, once.\n"
        f"- Mention {platform} by name, once.\n"
        "- Be specific about the vibe of the outfit.\n"
        "- Up to two emojis and up to two hashtags are fine."
    )

    result = generate(prompt, system=_CARD_SYSTEM)
    if not result.strip():
        return f"Scored this {title} for {price} on {platform} and I'm obsessed."
    return result