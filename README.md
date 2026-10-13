# FitFindr 🧥

**An AI agent that shops secondhand for you.** Tell it what you want — *"a vintage graphic tee under $30, size M"* — and it searches resale listings, works out what the piece would go with in your existing wardrobe, and writes a caption you'd actually post.

FitFindr is a tool-using agent, not a fixed pipeline: a planning loop chooses its next step based on what the previous tool returned, and carries results between steps in an explicit session state.

**Stack:** Python 3.13 · Google Gemini API · step-based planning loop with branching · regex query parsing · JSON listing data

---

## What This Does

You describe what you're shopping for in plain language, for example *"vintage graphic tee under $30, size M"*, and FitFindr pulls out the item, size, and price ceiling, then searches 40 secondhand listings from Depop, Poshmark, and thredUp. For the best match, it suggests one or two complete outfits using pieces you already own, or general styling advice if you haven't shared a wardrobe, and writes a short, post-ready caption that includes the price and platform. If nothing matches, it stops before calling the model and tells you which filter to change, for example: *"Nothing matching 'graphic tee' under $10. The cheapest match is $15 (Mesh Long-Sleeve Top — Black on Depop). Try raising your max price to $15."*

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
- **When it has nothing:** If `wardrobe["items"]` is empty, it still returns a non-empty string, in this case general styling advice for the item. If the model returns empty text, it returns a fallback styling sentence. It never raises an exception or returns `""`.

### `create_fit_card`

- **What it does:** Calls the model to write a short caption about the find that someone could actually post. Output varies from run to run (`config.TEMPERATURE = 0.9`).
- **Inputs:** `outfit` (str): the suggestion string returned by `suggest_outfit` · `new_item` (dict): the listing dict for the item
- **Returns:** `str`, a 2–4 sentence caption written as a social post rather than a product description. It mentions the item, its price (formatted like `$24`), and its platform once each.
- **When it has nothing:** If `outfit` is empty or only whitespace, it makes **no model call** and returns `"Can't write a fit card without an outfit suggestion for <item title>."` It never raises an exception or returns `""`.

---

## Planning Loop

**Branch rule:** If `search_listings` returns an empty list, go to `explain_empty`: put a message in `session["error"]` naming which filter to change, and **stop**. In that case `suggest_outfit` and `create_fit_card` are never called, and `session["fit_card"]` stays `None`. Otherwise, go to `select`: put the first (highest-scoring) result in `session["selected_item"]`, then run `suggest_outfit`, then `create_fit_card`.

**Where it lives:** `agent.py::run_agent`

The loop is a `while` loop over named steps. Each pass runs one step, and that step chooses the next one based on what it returned. Every pass calls `trace.check_iterations()` so the loop can't run away (`config.MAX_ITERATIONS = 10`).

```
match:     parse → search → select → suggest_outfit → create_fit_card → done
no match:  parse → search → explain_empty → done
```

**How the query is parsed:** With regex in `agent.py::parse_query`, not a model call, so parsing is deterministic and uses none of the 15-requests-per-minute quota. A dollar amount (`$30`, `under 30`) becomes `max_price` (float). `size <X>` becomes `size` (this also handles `size W30 L30` and `size 8`). The remaining words, minus filler, become `description`. The result is stored in `session["parsed"]`.

**What moves through the session:** `query` → `parsed` → `search_results` → `selected_item` → `outfit_suggestion` → `fit_card`. Each tool reads its inputs from the session, not from the previous call's return value. `session["steps"]` records the path the loop took. On the empty-search path the run ends after `search_results`, with `error` set and every later field still `None`.

**Empty-search message** (`agent.py::explain_empty_search`): instead of saying "No results," the loop re-runs `search_listings` with filters relaxed one at a time to find which one removed every match. Without the price limit: it reports the cheapest match and suggests that price. Without the size: it lists the sizes that are available. Without both: it suggests loosening both. If nothing matches even with no filters, it suggests broader keywords. These extra searches cost nothing, because search makes no model call.

---

## Sample Run

**One full query**

```
$ python app.py ask 'vintage graphic tee under $30, size M'

  Found:    Y2K Baby Tee — Butterfly Print — $18.0 on depop

  Outfit:   Buy it. At eighteen dollars, this Y2K baby tee is a versatile addition that balances your oversized and baggy bottoms.

Outfit one: Pair the butterfly tee with your baggy straight-leg jeans, dark wash. Add the black combat boots and the black crossbody bag for a balanced contrast of tight and loose Y2K streetwear.

Outfit two: Style the tee tucked into your wide-leg khaki trousers. Layer the vintage black denim jacket on top and finish the look with your chunky white sneakers for an easy, everyday 90s-meets-Y2K casual outfit.

  Fit card: Scored this butterfly tee on Depop for just $18! Love balancing the tight fit with baggy dark wash jeans and chunky boots for that ultimate Y2K street style. 🦋✨ #thrifted #y2kstyle

0 model calls this session, 2 served from cache
```

**The empty-search branch** (stops before any model call):

```
$ python app.py ask 'designer ballgown size XXS under $5'

  No listings match 'designer ballgown' at all. Try broader words, like a category ('dress', 'jacket', 'jeans') or a style ('vintage', 'y2k', 'streetwear').

0 model calls this session
```

**Both paths, run through `python agent.py`**

```
=== A query the data can match ===
  parsed:   {'description': 'vintage graphic tee', 'size': None, 'max_price': 30.0}
  steps:    parse -> search -> select -> suggest_outfit -> create_fit_card
  found:    Y2K Baby Tee — Butterfly Print — $18.0 on depop [lst_002]
  outfit:   Buy it. At eighteen dollars, this Y2K baby tee is a versatile addition that balances your oversized and baggy bottoms.

Outfit one: Pair the butterfly tee with your baggy straight-leg jeans, dark wash. Add the black combat boots and the black crossbody bag for a balanced contrast of tight and loose Y2K streetwear.

Outfit two: Style the tee tucked into your wide-leg khaki trousers. Layer the vintage black denim jacket on top and finish the look with your chunky white sneakers for an easy, everyday 90s-meets-Y2K casual outfit.
  fit card: Scored this butterfly tee on Depop for just $18! Love balancing the tight fit with baggy dark wash jeans and chunky boots for that ultimate Y2K street style. 🦋✨ #thrifted #y2kstyle

=== A query it can't ===
  parsed:   {'description': 'designer ballgown', 'size': 'XXS', 'max_price': 5.0}
  steps:    parse -> search -> explain_empty
  stopped:  No listings match 'designer ballgown' at all. Try broader words, like a category ('dress', 'jacket', 'jeans') or a style ('vintage', 'y2k', 'streetwear').
  fit_card is None — it should still be None here
```

**The three tools, tested one at a time**

`search_listings` (and its empty case):

```
$ python -c "from tools import search_listings; r = search_listings('graphic tee', max_price=30); print(len(r), 'results'); [print(f\"  {l['id']}  {l['title']}  \${l['price']}  size {l['size']}\") for l in r]"
6 results
  lst_002  Y2K Baby Tee — Butterfly Print  $18.0  size S/M
  lst_033  Vintage Band Tee — Faded Grey  $19.0  size L
  lst_006  Graphic Tee — 2003 Tour Bootleg Style  $24.0  size L
  lst_017  Mesh Long-Sleeve Top — Black  $15.0  size S/M
  lst_015  Vintage Graphic Hoodie — Faded Black  $26.0  size L
  lst_011  Low-Rise Cargo Pants — Khaki  $27.0  size W29

$ python -c "from tools import search_listings; print(search_listings('designer ballgown', size='XXS', max_price=5))"
[]
```

`suggest_outfit` (with the example wardrobe, then an empty one):

```
$ python -c "from tools import suggest_outfit; from utils.data_loader import get_example_wardrobe, load_listings; print(suggest_outfit(load_listings()[5], get_example_wardrobe()))"
Outfit 1: Pair the graphic tee with your baggy straight-leg jeans, dark wash. Tuck the tee in slightly, add the brown leather belt, and finish with the chunky white sneakers and the black crossbody bag for an effortless 90s streetwear look.

Outfit 2: Layer the graphic tee over your white ribbed tank top, paired with the wide-leg khaki trousers. Wear it with the black combat boots and toss the vintage black denim jacket over your shoulders to lean into that grungy, textured style.

At $24, this tee is a solid deal for a versatile streetwear staple that bridges your denim and trouser collections.

$ python -c "from tools import suggest_outfit; from utils.data_loader import get_empty_wardrobe, load_listings; print(suggest_outfit(load_listings()[5], get_empty_wardrobe()))"
For an effortless streetwear look, pair this graphic tee with baggy mid-rise light wash jeans and chunky black combat boots. Throw an oversized vintage leather bomber jacket over your shoulders for extra warmth and texture.

If you prefer a grunge-inspired outfit, tuck the tee into a plaid flannel midi skirt and layer with sheer black tights. Finish this combination with worn-in canvas high-top sneakers and a silver chain necklace to tie the metal-inspired graphics together.
```

`create_fit_card` (three runs with the cache off, showing different wording each time, then the empty case):

```
$ AI201_CACHE=0 python -c "from tools import create_fit_card; from utils.data_loader import load_listings; print(create_fit_card('Pair it with baggy dark-wash jeans and chunky white sneakers', load_listings()[5]))"
Scored this bootleg tour tee on Depop for just $24 and I'm obsessed. Giving major early 2000s garage band energy paired with my go-to baggy jeans and chunky white sneakers. Effortless everyday uniform. 🎸👟

#thrifted #y2kstyle

(run 2)
Scored this bootleg tour tee on Depop for $24 and it's already my new favorite piece. Paired it with baggy dark-wash denim and chunky sneakers for that ultimate 90s skater vibe. 🛹🖤

#thrifted #y2kstyle

(run 3)
Found this unreal bootleg tour tee on Depop and I'm obsessed. Snagged it for just $24 and threw it on with baggy dark-wash denim and chunky white sneakers for the ultimate skater grunge look. 🛹✨

#thriftfinds #y2kstyle

$ python -c "from tools import create_fit_card; from utils.data_loader import load_listings; print(create_fit_card('', load_listings()[5]))"
Can't write a fit card without an outfit suggestion for Graphic Tee — 2003 Tour Bootleg Style.
```

---

## How I Used AI

**Moment 1: Keeping the README gradeable**

- *What I asked for:* A portfolio-style README draft for the project.
- *What came back:* A clean README, but with its own section layout that would have replaced CodePath's starter template.
- *What I changed:* Before committing, I compared it against the starter README and caught that the template has required structure: four labeled fields per tool (What it does / Inputs / Returns / When it has nothing) and four under Planning Loop. Replacing it would have cost points. I kept the template's exact headings and fields, and only kept the additions that didn't conflict with it (the summary, Data Model, and Running It sections).

**Moment 2: Debugging search relevance**

- *What I asked for:* I gave Claude my `search_listings` spec (whole-token size matching, 2-point/1-point keyword scoring) and had it generate the implementation.
- *What came back:* A function that passed my empty-case test, but my first real query, `search_listings('graphic tee', max_price=30)`, returned two items that aren't graphic tees: `Low-Rise Cargo Pants — Khaki` and `Mesh Long-Sleeve Top`.
- *What I changed:* I printed both listings' `style_tags` and `description` to find the cause. Neither has "graphic" or "tee" in its title or tags. Their descriptions mention a tee as something to wear *with* them ("layering with a long tee" scores 1 point, "layering under a graphic tee" scores 2). Real graphic tees score 4, so the agent still selects the right item. I then checked whether the bug reached anywhere else, and it does: `python app.py ask 'graphic tee under $10'` suggests the mesh top as the "cheapest match," because the empty-search diagnosis reuses the same scoring. I decided not to change the scoring yet, because my criteria were already committed. I recorded it as one root cause with two symptoms, to measure and fix in Unit 4.

---

# Part 2 — Testing

## Stretch Features (declared before building)

1. **Second tool on MCP.** `search_listings` is the required MCP tool. `create_fit_card` will also be exposed through `mcp_server.py`, so the agent calls both through `mcp_client.call_tool`. The Loop Trace will show both MCP calls.
2. **Retry with looser constraints.** When a search with a size filter comes back empty, the agent retries **once** without the size filter. If the retry finds results, the run continues and tells the user which constraint was dropped, for example: *"Nothing in size XS, so I dropped the size filter and found this in M."* If the retry is also empty, or the query had no size filter, the agent stops exactly as before. Criterion 2's test query (`designer ballgown`) has no matches even without a size, so it still stops before `suggest_outfit`.

---

## Run Log — Before

Produced by `run_eval.py::main` (criteria 1–4, agent loop in `agent.py::run_agent`) and `check_size_filter.py::main` (criterion 5). Cache off, 5 tries each. Full output: `results/run_2026-10-12_2353_before.md` and `results/criterion5_before.txt`.

| Criterion | Target | Try 1 | Try 2 | Try 3 | Try 4 | Try 5 | Verdict |
|---|---|---|---|---|---|---|---|
| 1. Matching query completes all three tools and returns a fit card | 4 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |
| 2. Empty search stops before `suggest_outfit` with a message naming what to change | 5 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |
| 3. Item from search is the item `suggest_outfit` and `create_fit_card` receive (5 different queries) | 5 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |
| 4. Fit card has the price, the platform, and 15–80 words; at least 3 of 5 cards distinct | 4 of 5 + 3 distinct | PASS | PASS | PASS | PASS | PASS | MET (5/5, 5 distinct) |
| 5. Size filter matches whole tokens only (sizes M, S, L, XL, W30) | 5 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |

For criterion 3, each try is a different query, as the criterion specifies: Try 1 = `vintage graphic tee under $30`, Try 2 = `90s track jacket in size M`, Try 3 = `denim jacket under $50`, Try 4 = `platform sneakers size 8`, Try 5 = `corduroy pants under $40` (try 1 of each scenario).

**Real output from one try per criterion:**

Criterion 1, try 1 (`run_eval.py::main` → `agent.py::run_agent`):
```
[3] select
      in:  10 results
      out: Y2K Baby Tee — Butterfly Print ($18.0, depop)
      →    top result, id lst_002
[4] suggest_outfit
      in:  new_item id lst_002 (Y2K Baby Tee — Butterfly Print), wardrobe: 10 items
      out: Outfit One: Pair the Y2K Baby Tee with your baggy straight-leg jeans, dark wash. Add the black combat boots an…
[5] create_fit_card (via MCP)
      in:  outfit (441 chars), new_item id lst_002 (Y2K Baby Tee — Butterfly Print)
      out: Scored this little butterfly tee on Depop for just $18! 🦋 It's giving major Y2K energy paired with baggy denim…
  try 1: completed — fit card 205 chars
```

Criterion 2, try 1 (`agent.py::run_agent`, ending in `agent.py::explain_empty_search`):
```
[2] search_listings (via MCP)
      in:  description='designer ballgown', size='XXS', max_price=5.0
      out: [] (empty)
      →    branch: empty with a size filter, retrying once without size
[3] search_listings (via MCP), retry
      in:  description='designer ballgown', size=None, max_price=5.0
      out: [] (empty)
      →    dropped constraint: size (XXS); still empty, going to explain_empty
[4] explain_empty
      out: No listings match 'designer ballgown' at all. Try broader words, like a category ('dress', 'jacket', 'jeans') …
      →    re-ran search via MCP with filters relaxed; stopping before suggest_outfit
  try 1: stopped early — No listings match 'designer ballgown' at all. Try broader wo
```

Criterion 3, try 4 (`agent.py::run_agent`): the same id at all three steps:
```
[3] select
      out: Platform Sneakers — White Chunky Sole ($48.0, poshmark)
      →    top result, id lst_019
[4] suggest_outfit
      in:  new_item id lst_019 (Platform Sneakers — White Chunky Sole), wardrobe: 10 items
[5] create_fit_card (via MCP)
      in:  outfit (622 chars), new_item id lst_019 (Platform Sneakers — White Chunky Sole)
```

Criterion 4, try 1 (`tools.py::create_fit_card`, called through `mcp_server.py::create_fit_card`): 39 words, contains `$45` and `Poshmark`:
```
Scored this 90s navy track jacket on Poshmark for $45 and it bridges streetwear and vintage pieces effortlessly. Love wearing it zipped over baggy jeans or khaki trousers with chunky sneakers for that easy retro vibe. 🧥✨ #thrifted #streetwear
```

Criterion 5, try 3 (`check_size_filter.py::main` → `search_listings` via MCP): `L` does not match `XL`:
```
Try 3: size='L' -> 5 listings -> PASS
    lst_033  size 'L'                  Vintage Band Tee — Faded Grey
    lst_006  size 'L'                  Graphic Tee — 2003 Tour Bootleg Style
    lst_015  size 'L'                  Vintage Graphic Hoodie — Faded Black
    lst_018  size 'M/L'                Vintage Linen Blazer — Cream
    lst_010  size 'L'                  Vintage Windbreaker — Color Block Purple/Teal
```

---

## Verdicts and Diagnoses

| # | Criterion | Target | Verdict | How I decided |
|---|---|---|---|---|
| 1 | Matching query completes and returns a fit card | 4 of 5 | **MET (5/5)** | All 5 tries reached `create_fit_card`, `session["error"]` was `None`, and the fit card was non-empty (183–226 chars). |
| 2 | Empty search stops before `suggest_outfit`, names what to change | 5 of 5 | **MET (5/5)** | No try has a `suggest_outfit` step in its trace. Every message names the keywords as the thing to change ("Try broader words…"). |
| 3 | Search's item is the item both later tools receive | 5 of 5 | **MET (5/5)** | For each of the 5 queries, the id at `select` matches the `new_item id` passed to `suggest_outfit` and `create_fit_card` (`lst_002`, `lst_004`, `lst_007`, `lst_019`, `lst_005`). |
| 4 | Fit card has the price, the platform, 15–80 words; 3+ of 5 distinct | 4 of 5 + 3 distinct | **MET (5/5)** | Every card contains `$45` and `Poshmark`, and runs 34–41 words. All 5 are different strings. |
| 5 | Size filter matches whole tokens only | 5 of 5 | **MET (5/5)** | No listing returned for any of the 5 sizes broke the rule. `M` matched `S/M` and `M/L`, and `L` never matched `XL`. |

### Diagnoses

**No criterion missed.** Some of that is the agent working, and some is targets I set too low:

- **Criterion 1 was too easy at 4 of 5.** I allowed one miss for regex misparses and quota failures. The regex parsed every query correctly, and the service pushed back 4 times during the run, but `generate.py`'s retry absorbed every one. **Tighter target: 5 of 5.**
- **Criterion 4 measured the wrong thing as well as too little.** It checks that the price and platform *appear*, not that the caption makes sense. For platform sneakers, `suggest_outfit` advised "Skip these… you already own chunky white sneakers" in 5 of 5 tries, and then `create_fit_card` wrote a celebratory post anyway ("Almost bought these…", "Saved myself $48…"). Those cards would all pass criterion 4. **Tighter target:** *"the fit card's stance matches `suggest_outfit`'s buy/skip recommendation in 5 of 5 tries."* The mechanism: `create_fit_card`'s prompt tells the model to write a post about "this thrift find" and never passes along the recommendation, so the caption assumes a purchase.

**A failure my criteria didn't cover: search relevance (`tools.py::search_listings`).** It appeared three times:

1. `search_listings('graphic tee', max_price=30)` returns the cargo pants and the mesh top. Neither one is a tee. Their descriptions only *mention* wearing one ("layering with a long tee", "under a graphic tee").
2. The empty-search diagnosis (`agent.py::explain_empty_search`) reuses that search, so `graphic tee under $10` suggests the mesh top at $15 as "the cheapest match."
3. The stretch retry for `90s track jacket` returns 10 items, including a Bucket Hat and Platform Mary Janes.

Printing the scores shows the mechanism:

```
=== graphic tee
 4  Y2K Baby Tee — Butterfly Print           [('graphic', 2), ('tee', 2)]
 2  Mesh Long-Sleeve Top — Black             [('graphic', 1), ('tee', 1)]
 1  Low-Rise Cargo Pants — Khaki             [('tee', 1)]
=== 90s track jacket
 6  90s Track Jacket — Navy/White Stripe     [('jacket', 2), ('90s', 2), ('track', 2)]
 2  Bucket Hat — Reversible, Brown Plaid     [('90s', 2)]
 2  Platform Mary Janes — Black Patent       [('90s', 2)]
```

The tool works as specified. The spec's own rule ("listings scoring 0 are dropped") is the problem: any listing with one matching word survives, however far it falls below the best match. One root cause, three symptoms. It never broke a criterion, because the agent only uses the top result, which was always correct. It breaks everywhere the agent uses the rest of the list.

**MCP side effect:** `run_eval.py` reported "36 model calls this session," but each try made two model calls. The `create_fit_card` calls run inside the MCP server process, so the agent's counter never sees them.

---

## Loop Trace

_In progress._

---

## The Improvement

_In progress._

---

## What's Still Broken

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