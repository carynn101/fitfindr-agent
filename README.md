# FitFindr 🧥

**An AI agent that shops secondhand for you.** Tell it what you want — *"a vintage graphic tee under $30, size M"* — and it searches resale listings, works out what the piece would go with in your existing wardrobe, and writes a caption you'd actually post.

FitFindr is a tool-using agent, not a fixed pipeline: a planning loop chooses its next step based on what the previous tool returned, and carries results between steps in an explicit session state.

**Stack:** Python 3.13 · Google Gemini API · custom tool-calling planning loop · JSON listing data

---

## What This Does

_In progress._

---

## Tool Inventory

### `search_listings`

- **What it does:** _In progress._
- **Inputs:**
- **Returns:**
- **When it has nothing:**

### `suggest_outfit`

- **What it does:** _In progress._
- **Inputs:**
- **Returns:**
- **When it has nothing:**

### `create_fit_card`

- **What it does:** _In progress._
- **Inputs:**
- **Returns:**
- **When it has nothing:**

---

## Planning Loop

**Branch rule:** _In progress._

**Where it lives:** `agent.py::run_agent`

**How the query is parsed:** _In progress._

**What moves through the session:** _In progress._

---

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