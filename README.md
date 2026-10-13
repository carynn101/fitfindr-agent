# FitFindr 🧥

**An AI agent that shops secondhand for you.** Tell it what you want — *"a vintage graphic tee under $30, size M"* — and it searches resale listings, works out what the piece would go with in your existing wardrobe, and writes a caption you'd actually post.

FitFindr is a tool-using agent, not a fixed pipeline: a planning loop chooses its next step based on what the previous tool returned, and carries results between steps in an explicit session state.

**Stack:** Python 3.13 · Google Gemini API · custom tool-calling planning loop · JSON listing data

---

## What This Does

_In progress._

---

## Tool Inventory

All three tools live in `tools.py` and can be run and tested independently.

### `search_listings`

- **What it does:** Searches the 40 listings in `data/listings.json` and returns the ones matching the user's keywords, size, and price ceiling, best match first. It's the only tool that doesn't call the model.
- **Inputs:** `description` (str): keywords such as `"vintage graphic tee"` · `size` (str | None): size to filter by, or `None` to skip · `max_price` (float | None): inclusive price ceiling, or `None` to skip
- **Returns:** `list[dict]` of up to 10 listing dicts (`config.SEARCH_RESULT_LIMIT`), sorted by match score with the highest first and ties going to the lower price. Each dict is a full listing: `id`, `title`, `description`, `category`, `style_tags` (list), `size`, `condition`, `price` (float), `colors` (list), `brand` (str or None), `platform`.
- **When it has nothing:** Returns an empty list `[]`. It never returns `None` and never raises an exception.

**Size-matching rule:** The listing's `size` is lowercased and split into tokens on spaces, slashes, and parentheses. A listing matches only if the user's size equals one whole token. So `M` matches `"M"` and `"S/M"`, but not `"XL (oversized)"`, and `S` does not match `"US 9"`. Plain substring matching was rejected because `"l" in "xl"` is True.

**Scoring rule:** The description is lowercased, split into words, and stripped of filler words ("a", "the", "for", "looking"…). Each remaining word scores **2 points** if it appears in the listing's `title`, `style_tags`, or `category`, and **1 point** if it appears only in `description`, `colors`, or `brand`. Listings that score 0 are dropped.

### `suggest_outfit`

- **What it does:** Calls the model to suggest one or two outfits built around the new item, using pieces the user already owns.
- **Inputs:** `new_item` (dict): one listing dict, the item selected from the search results · `wardrobe` (dict): has an `"items"` key holding a list of wardrobe-item dicts (`name`, `category`, `colors`, `style_tags`, `notes`)
- **Returns:** `str`, a non-empty block of outfit suggestions. When the wardrobe has items, each outfit names at least one wardrobe piece by its `name`.
- **When it has nothing:** If `wardrobe["items"]` is empty, it still returns a non-empty string, in this case general styling advice for the item (what kinds of pieces pair with it). It never raises an exception or returns `""`.

### `create_fit_card`

- **What it does:** Calls the model to write a short caption about the find that someone could actually post. Output varies from run to run (`config.TEMPERATURE = 0.9`).
- **Inputs:** `outfit` (str): the suggestion string returned by `suggest_outfit` · `new_item` (dict): the listing dict for the item
- **Returns:** `str`, a 2–4 sentence caption written as a social post rather than a product description. It mentions the item, its price, and its platform once each.
- **When it has nothing:** If `outfit` is empty or only whitespace, it makes **no model call** and returns the message `"Can't write a fit card without an outfit suggestion for <item title>."` It never raises an exception or returns `""`.

---

## Planning Loop

**Branch rule:** If `search_listings` returns an empty list, put a message in `session["error"]` that names the filters that were used and which one to loosen, then **stop**. In that case `suggest_outfit` and `create_fit_card` are never called, and `session["fit_card"]` stays `None`. Otherwise, put the first (highest-scoring) result in `session["selected_item"]` and go to `suggest_outfit`, then to `create_fit_card`.

**Where it lives:** `agent.py::run_agent`

**How the query is parsed:** With regex, not a model call, so parsing is deterministic and uses none of the 15-requests-per-minute quota. A dollar amount (`$30`) becomes `max_price` (float). `size <X>` becomes `size`. The remaining words become `description`. The result is stored in `session["parsed"]`.

**What moves through the session:** `query` → `parsed` → `search_results` → `selected_item` → `outfit_suggestion` → `fit_card`. Each tool reads its inputs from the session, not from the previous call's return value. On the empty-search path the run ends at `search_results`, with `error` set and every later field still `None`.

**Empty-search message:** The message does more than say "No results." The loop re-runs `search_listings` with the size filter removed, and then with the price filter removed, to find out which filter eliminated every match. It then tells the user directly, for example: *"No graphic tees under $5. The cheapest match is $18 on Depop. Try raising your max price."* These extra searches cost nothing, because search makes no model call.

## Sample Run

_In progress._

---

## How I Used AI

_In progress._

---

## Data Model

FitFindr searches 40 secondhand listings across Depop, Poshmark, and thredUp.

| Field | Type | Example | Notes |
|---|---|---|---|
| `title` | str | Vintage Levi's 501 Jeans — Medium Wash | |
| `category` | str | bottoms | tops / bottoms / outerwear / … |
| `style_tags` | list[str] | `["vintage", "denim", "streetwear"]` | primary keyword-match target |
| `size` | str | `W30 L30`, `S/M`, `XL (oversized)` | free text, not standardized |
| `price` | float | 38.0 | |
| `colors` | list[str] | `["blue", "indigo"]` | |
| `brand` | str \| null | Levi's | often null |
| `condition` | str | good | |
| `platform` | str | depop | |

A wardrobe item has `name`, `category`, `colors`, `style_tags`, and `notes`. An empty wardrobe is supported: the outfit tool falls back to general styling advice.

---

## Running It

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add your GEMINI_API_KEY
python test.py              # environment check
python app.py ask 'vintage graphic tee under $30'
```

📖 Full command reference: [RUNNING.md](RUNNING.md)