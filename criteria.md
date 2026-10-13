# FitFindr — Acceptance Criteria

Written before any tool or loop was built. These are the standards the agent is tested against in Unit 4. Each criterion names a target and how to check it, followed by the reason for that target.

All runs use the example wardrobe (`get_example_wardrobe()`) unless stated otherwise. Model-output criteria (1 and 4) are run with the cache off (`AI201_CACHE=0`), so each try is a real model call.

---

### 1. Happy path completes

Given a query that matches at least one listing, the agent completes all three tool calls and returns a fit card — in at least **4 of 5** tries.

*Check:* after `run_agent()` returns, `session["error"]` is `None` and `session["fit_card"]` is a non-empty string.

**Why 4 of 5 and not 5 of 5:** The query is parsed with regex, not a model, so an unusual phrasing (for example, "around thirty bucks" instead of "$30") can be misread into a filter that matches nothing, even though a person would see a match. Each run also makes two model calls against a 15-requests-per-minute free tier. The adapter in `generate.py` retries, but a run can still fail on quota. One miss in five allows for those causes without accepting a loop that's actually broken.

---

### 2. Empty search stops early with a useful message

Given a query that matches no listings, the agent stops before calling `suggest_outfit` and returns a message naming what to change — **5 of 5** tries.

*Check:* using `'designer ballgown size XXS under $5'`, `session["outfit_suggestion"]` and `session["fit_card"]` are both `None`, and `session["error"]` names at least one specific filter to change: the price, the size, or the keywords. A message that only says "No results" fails.

**Why 5 of 5:** This branch is plain code. `run_agent` checks whether `search_listings` returned an empty list, and the message is built from the parsed filters, not by the model. Nothing in this path is random, so any miss is a bug and not variance.

---

### 3. The item search found is the item the next tools receive

Given a query that matches at least one listing, the `id` of the listing passed as `new_item` to `suggest_outfit` equals `session["search_results"][0]["id"]`, and the same `id` is passed as `new_item` to `create_fit_card` — **5 of 5** tries, across 5 different matching queries.

*Check:* compare the three `id` values. They can be read from the trace output (each step's inputs), or by printing `session["search_results"][0]["id"]` and `session["selected_item"]["id"]` at the end of the run. The user types the query once, and nothing asks for the item again.

**Why 5 of 5:** Choosing the item is deterministic. `run_agent` writes `search_results[0]` into `session["selected_item"]`, and both model tools read `new_item` from that session field. No model is involved in passing state between steps, so a mismatch would mean the loop is reading from the wrong place, which is exactly the bug this criterion is meant to catch.

---

### 4. The fit card is usable even though its wording changes

Given a query that matches at least one listing, run 5 times with the cache off. A fit card **passes** if it (a) contains the selected item's price written as a dollar amount (for a `price` of 24.0, the text `$24` appears), (b) names the item's `platform` (case-insensitive), and (c) is between 15 and 80 words. Target: at least **4 of 5** cards pass, **and** at least 3 of the 5 cards are different strings.

*Check:* compare each card against `session["selected_item"]["price"]` and `["platform"]`, count words by splitting on spaces, and compare the five cards to each other.

**Why 4 of 5:** `create_fit_card` runs at `TEMPERATURE = 0.9`, so the wording is supposed to change. That's why this criterion checks facts and length, not exact text. At that temperature the model will sometimes write a price as "twenty-four bucks" or leave out the platform, so one miss in five is tolerated. The "3 of 5 different" check exists because identical cards would mean the cache was left on or the temperature is 0 (both set in `config.py`), and the caption would effectively be a template.

---

### 5. Size filtering matches whole sizes, not substrings

Call `search_listings('vintage', size=X)` for each of these 5 sizes: `M`, `S`, `L`, `XL`, `W30`. For every listing returned, the requested size appears as a whole token after the listing's `size` field is lowercased and split on spaces, slashes, and parentheses. Target: **5 of 5** sizes return zero listings that break this rule.

*Check:* for example, size `L` must never return a listing whose size is `"XL (oversized)"`, and size `M` should return a listing sized `"S/M"`.

**Why 5 of 5:** The `size` field in `data/listings.json` is free text (`"S/M"`, `"XL (oversized)"`, `"W30 L30"`), not a standard value. A plain substring test like `"l" in "xl"` returns True, which would make size filtering quietly wrong for shoppers who wear L. Because this filter is deterministic code with no model involved, a single wrong listing means the rule is broken. A lower target would hide exactly the bug this criterion is meant to catch.