---
title: "Building MCP Tool Servers for a Dividend Review Agent (divvy-forge Part 2)"
date: 2026-08-27
summary: "How I built two MCP tool servers — divvy-reader and market-data-fetcher — that give a TrueForge agent live access to a GitHub portfolio and real stock fundamentals. Includes a walkthrough of the raw MCP protocol, BeautifulSoup scraping, and the yfinance fallback."
draft: false
tags: ["mcp", "trueforge", "python", "ai-agents", "fastmcp", "yfinance", "web-scraping", "divvy-forge"]
categories: []
---

This is part 2 of the divvy-forge series. [Part 1](https://hiteshpattanayak.com/posts/trueforge-daytona-setup-what-the-docs-miss/) covered getting TrueForge and Daytona running locally.

Demo video: [Watch on YouTube](https://youtu.be/7Bhga7G6Zec)

---

## What We're Building

[divvy-forge](https://github.com/HiteshRepo/divvy-forge) is a TrueForge-hosted agent that automates dividend portfolio reviews. My portfolio lives as markdown files in a private GitHub repo (`HiteshRepo/stock-screeners`). The agent reads the current state, fetches fresh market data, and opens a GitHub PR with proposed changes. I merge the PR to approve — nothing is applied until then.

For the agent to do any of this, it needs tools. In TrueForge, tools are exposed as **MCP servers** — small processes that speak the [Model Context Protocol](https://modelcontextprotocol.io/) over stdio. This post covers the two I built first:

- **divvy-reader** — reads the live portfolio state from GitHub
- **market-data-fetcher** — fetches fresh fundamentals from Screener.in (with yfinance fallback)

---

## What MCP Actually Is

MCP is a JSON-RPC 2.0 protocol over stdio. The LLM runtime (TrueForge in our case) spawns your server as a subprocess and communicates through a three-phase handshake:

```text
CLIENT                          SERVER
  |                               |
  |──── initialize ──────────────>|   version + capability negotiation
  |<─── result ───────────────────|
  |                               |
  |──── notifications/initialized>|   "ready" confirmation (no response)
  |                               |
  |──── tools/list ──────────────>|   schema discovery
  |<─── result ───────────────────|   JSON schemas for each tool
  |                               |
  |──── tools/call ──────────────>|   tool invocation
  |<─── result ───────────────────|   tool response
```

The key thing: **the LLM never sees your Python source code**. It only sees the JSON schemas returned by `tools/list` — the tool names, parameter types, and docstrings you write. FastMCP generates these schemas automatically from your type annotations.

---

## divvy-reader

**What it does:** reads live dividend state from `HiteshRepo/stock-screeners` via the GitHub contents API. No local clone required.

### Three tools

```python
@mcp.tool()
def list_watchlist() -> list[str]:
    """Return an ordered list of ticker symbols from the divvy watchlist."""

@mcp.tool()
def read_ticker(ticker: str) -> dict:
    """Return parsed ticker state: yield_pct, payout_ratio,
    last_review_date, notes, raw_markdown."""

@mcp.tool()
def read_file(path: str) -> str:
    """Fetch raw file content from HiteshRepo/stock-screeners
    via the GitHub contents API."""
```

`list_watchlist` and `read_ticker` parse a markdown pipe table — `dividend/data/watchlist.md` — and return structured data. Any field that can't be parsed comes back as `null` rather than raising an error.

`raw_markdown` in the `read_ticker` response is critical: the coordinator agent diffs against it when generating proposed changes, so format drift is contained — we're always diffing against what's actually in the file.

### Running it

```bash
make inspect-divvy-reader   # opens MCP Inspector in browser
# or
make serve-divvy-reader     # raw stdio (for TrueForge wiring)
```

Here's `list_watchlist` returning the live watchlist — INFY and TCS pulled directly from `dividend/data/watchlist.md` on GitHub:

![divvy-reader MCP Inspector — list_watchlist returning INFY and TCS](/images/divvy-forge-mcp-demo/divvy-reader-mcp-inspector.png)

### What `tools/list` returns

This is exactly what the LLM sees — nothing more:

```json
{
  "tools": [
    {
      "name": "list_watchlist",
      "description": "Return an ordered list of ticker symbols from the divvy watchlist.",
      "inputSchema": { "properties": {}, "required": [], "type": "object" }
    },
    {
      "name": "read_ticker",
      "description": "Return parsed ticker state for ticker from the divvy watchlist...",
      "inputSchema": {
        "properties": { "ticker": { "title": "Ticker", "type": "string" } },
        "required": ["ticker"],
        "type": "object"
      }
    }
  ]
}
```

---

## market-data-fetcher

**What it does:** fetches current fundamental data for a ticker — dividend yield, payout ratio, EPS, FCF, and 5-year DPS history. Primary source is Screener.in; yfinance is the automatic fallback.

### One tool

```python
@mcp.tool()
def get_fundamentals(ticker: str) -> dict:
    """Fetch current fundamental data for ticker.
    Tries Screener.in first; falls back to yfinance on failure."""
```

The response always includes `source`, `fetched_at`, and `raw_response_excerpt` so the coordinator can trace every number back to where it came from.

Here's a live call for INFY — `source: "screener.in"`, dividend yield, payout ratio, 5-year DPS history, EPS, and FCF all in one response:

![market-data-fetcher MCP Inspector — get_fundamentals result for INFY](/images/divvy-forge-mcp-demo/market-data-fetcher-mcp-inspector.png)

### Why not a JSON API?

I originally tried `GET https://www.screener.in/api/company/INFY/` — got 404. Turns out Screener.in has no public JSON API for fundamentals. All the data is in the HTML page, and it's public — no authentication needed.

### The two-step scrape

```python
# Step 1: confirm the ticker exists and resolve the canonical URL
GET /api/company/search/?q=INFY
# → [{"id": 1489, "url": "/company/INFY/consolidated/"}]

# Step 2: fetch and parse the HTML page
GET /company/INFY/consolidated/
```

BeautifulSoup parses three sections of the page:

| Section | Field extracted |
|---|---|
| `#top-ratios` | `dividend_yield_pct` |
| `#profit-loss` table | `eps`, `payout_ratio`, `dividends_per_share_history` |
| `#cash-flow` table | `free_cash_flow` (operating CF − capex) |

`dividends_per_share_history` is computed as EPS × payout% / 100 for each annual period — Screener.in doesn't give DPS directly.

```python
# Parsing #top-ratios
section = soup.find(id="top-ratios")
for li in section.find_all("li"):
    name = li.find(class_="name").get_text(strip=True)
    value = li.find(class_="number").get_text(strip=True)
    # e.g. name="Dividend Yield", value="4.42 %"
```

### Exponential backoff

The scraper retries on HTTP 429 and 5xx with a 1s initial delay, doubling each attempt, up to 3 retries before falling back to yfinance:

```python
_INITIAL_BACKOFF_SECS: float = 1.0
_MAX_RETRIES: int = 3

for attempt in range(_MAX_RETRIES + 1):
    resp = client.get(url, headers=_HTML_HEADERS, follow_redirects=True)
    if resp.status_code == 200:
        return _parse_html(ticker, resp.text)
    if resp.status_code == 429 or resp.status_code >= 500:
        if attempt < _MAX_RETRIES:
            time.sleep(backoff)
            backoff *= 2
            continue
        break  # exhausted — fall back to yfinance
```

### yfinance fallback

yfinance 1.6.0 (uses `curl_cffi` internally) handles Yahoo Finance's rate limits much more reliably than older versions:

```python
stock = yf.Ticker("INFY.NS")   # .NS suffix added automatically for bare NSE tickers
info = stock.info               # dividendYield, payoutRatio, trailingEps
dividends = stock.dividends     # historical dividend series
cashflow = stock.cashflow       # Free Cash Flow row
```

One breaking change in yfinance 1.x: `dividendYield` is now returned as a percentage (`4.42`) rather than a decimal (`0.0442`). `payoutRatio` is still decimal. Easy to miss.

### Error contract

The tool never raises an exception to the LLM — on total failure it returns a structured dict:

```json
{
  "error_code": "DATA_FETCH_FAILED",
  "error_message": "Both data sources failed for 'INFY'...",
  "ticker": "INFY",
  "screener_error": "...",
  "yfinance_error": "..."
}
```

The coordinator reads `error_code` and decides what to do — skip the ticker, retry later, or include a note in the PR.

---

## Seeing the Raw Protocol

I wrote a small demo script (`scripts/protocol_demo.py`) that spawns a server subprocess and shows every JSON-RPC message in the terminal — useful for demos and understanding exactly what flows between the LLM runtime and your server:

```bash
python scripts/protocol_demo.py market-data
python scripts/protocol_demo.py divvy-reader
```

**Phase 1 — INITIALIZE:** the client announces the protocol version; the server responds with its name, version, and supported capabilities:

![Phase 1 — INITIALIZE request from client](/images/divvy-forge-mcp-demo/market-data-fetcher-cli-1.png)

![Phase 1 — server response with capabilities and notifications/initialized](/images/divvy-forge-mcp-demo/market-data-fetcher-cli-2.png)

**Phase 2 — TOOLS/LIST:** the LLM runtime discovers what tools exist and their input schemas. This is the only thing the LLM ever sees — no Python source:

![Phase 2 — TOOLS/LIST schema discovery](/images/divvy-forge-mcp-demo/market-data-fetcher-cli-3.png)

**Phase 3 — TOOLS/CALL:** the actual `get_fundamentals` invocation and the full response coming back through the protocol:

![Phase 3 — TOOLS/CALL get_fundamentals invocation and response](/images/divvy-forge-mcp-demo/market-data-fetcher-cli-4.png)

One gotcha I hit early: piping all three messages at once to the server causes:

```text
RuntimeError: Received request before initialization was complete
```

`tools/list` arrived before the server finished processing `initialize`. The fix is to wait for each response before sending the next message — the protocol is strictly sequential during the handshake.

---

## Running via MCP Inspector

The easiest way to test interactively:

```bash
make inspect-market-data   # opens browser UI
make inspect-divvy-reader
```

The Inspector handles the protocol handshake automatically. You can call tools, see the raw JSON request/response, and verify the schema — without writing any client code.

---

## What's Next

These two servers plug into the coordinator agent (in progress):

1. `list_watchlist()` → get tickers to review
2. `read_ticker(ticker)` → current divvy state
3. `get_fundamentals(ticker)` → fresh market data
4. Spawn two parallel subagents: fundamentals analysis + dividend-cut-risk
5. Merge findings → generate unified diff → open PR on `HiteshRepo/stock-screeners`

Part 3 will cover the coordinator prompt design and how TrueForge's subagent delegation works in practice.

---

*Code: [github.com/HiteshRepo/divvy-forge](https://github.com/HiteshRepo/divvy-forge)*
