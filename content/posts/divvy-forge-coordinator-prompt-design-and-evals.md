---
title: "Coordinator Prompt Design and Eval-Driven Verification (divvy-forge Part 3)"
date: 2026-08-27
summary: "How I designed the coordinator and subagent prompts for divvy-forge as versioned markdown files, embedded subagent instructions inline, defined strict output contracts, and used promptfoo evals to catch three real prompt bugs before a single live agent run."
draft: true
tags: ["ai-agents", "prompt-engineering", "promptfoo", "trueforge", "python", "divvy-forge", "llm-evals"]
categories: []
---

This is part 3 of the divvy-forge series.
[Part 1](https://hiteshpattanayak.com/posts/trueforge-daytona-setup-what-the-docs-miss/) covered TrueForge + Daytona setup.
[Part 2](https://hiteshpattanayak.com/posts/building-mcp-tool-servers-for-a-dividend-review-agent-divvy-forge-part-2/) covered the MCP tool servers.

Demo video: [Watch on YouTube](https://youtu.be/PLACEHOLDER)

---

## Where We Are

At the end of part 2, divvy-forge had two working MCP servers:

- **divvy-reader** — reads the live portfolio state from GitHub
- **market-data-fetcher** — fetches fresh fundamentals (Screener.in + yfinance fallback)

The coordinator agent — the thing that reads a ticker, delegates analysis to two parallel subagents, and generates a markdown diff — is next. But before wiring it into TrueForge, I needed to design its prompts and verify they actually work. This post is about that step.

The coordinator isn't running end-to-end yet. The github-pr-opener MCP server (the thing that turns a diff into a GitHub PR) isn't built. But the prompts are done, tested, and pushed. Part 4 will cover the full run.

---

## Why Prompts as Files

The first decision: where does the prompt text live?

The obvious place is Python — a triple-quoted string in a module. That works until you need to diff a prompt change, review it in a PR, or hand it to someone who isn't comfortable reading Python. Prompts are content. They deserve their own files, their own git history, and the ability to be edited without touching code.

So the prompt text lives in `config/prompts/` as plain markdown files:

```
config/prompts/
    coordinator_system.md        ← outer coordinator shell
    fundamentals_subagent.md     ← subagent A instructions
    risk_subagent.md             ← subagent B instructions
    merge_findings.md            ← merge logic section
    generate_diff.md             ← diff generation rules
```

![config/prompts/ directory in the file tree](/images/divvy-forge-coordinator-evals/prompts-dir.png)

The Python module (`coordinator_prompts.py`) is just a loader:

```python
_PROMPTS_DIR = Path(__file__).parent.parent.parent / "config" / "prompts"

def _load(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")

FUNDAMENTALS_SUBAGENT_INSTRUCTIONS = _load("fundamentals_subagent.md")
RISK_SUBAGENT_INSTRUCTIONS         = _load("risk_subagent.md")
MERGE_FINDINGS_INSTRUCTIONS        = _load("merge_findings.md")
GENERATE_DIFF_INSTRUCTIONS         = _load("generate_diff.md")
```

Fifty lines of Python. No prompt text.

---

## The `<<SECTION>>` Assembly Pattern

The coordinator system prompt is a template — it references the four section files inline. The obvious choice for substitution is Python's f-strings or `.format()`. But the prompts contain JSON examples with curly braces everywhere:

```
On error returns: {error_code, error_message, ...}
```

Every one of those would need to be escaped as `{{error_code, error_message, ...}}`. That's noise inside markdown that makes the files harder to read and edit.

Instead, `coordinator_system.md` uses `<<SECTION_NAME>>` markers:

```markdown
Use these instructions for subagent A:
---
<<FUNDAMENTALS_SUBAGENT_INSTRUCTIONS>>
---
```

The loader assembles with `str.replace()` — no escaping needed, no ambiguity:

```python
COORDINATOR_SYSTEM_PROMPT = (
    _load("coordinator_system.md")
    .replace("<<FUNDAMENTALS_SUBAGENT_INSTRUCTIONS>>", FUNDAMENTALS_SUBAGENT_INSTRUCTIONS)
    .replace("<<RISK_SUBAGENT_INSTRUCTIONS>>",         RISK_SUBAGENT_INSTRUCTIONS)
    .replace("<<MERGE_FINDINGS_INSTRUCTIONS>>",        MERGE_FINDINGS_INSTRUCTIONS)
    .replace("<<GENERATE_DIFF_INSTRUCTIONS>>",         GENERATE_DIFF_INSTRUCTIONS)
)
```

---

## How the Coordinator Uses Subagents

TrueForge's dynamic subagents don't have separate manifest files. There's no `fundamentals_agent.yaml` to register. The coordinator LLM spawns subagents at runtime by passing instructions to TrueForge's subagent tool. Those instructions come directly from the coordinator's system prompt.

So `coordinator_system.md` embeds the full subagent instructions inline:

```markdown
**Subagent A — fundamentals-analysis**
Pass a JSON object with:
  - ticker
  - fundamentals  (the dict from market-data-fetcher)
  - stored_yield_pct

Use these instructions for subagent A:
---
<<FUNDAMENTALS_SUBAGENT_INSTRUCTIONS>>
---

**Subagent B — dividend-cut-risk**
Pass a JSON object with:
  - ticker
  - search_window_days: 90

Use these instructions for subagent B:
---
<<RISK_SUBAGENT_INSTRUCTIONS>>
---
```

When assembled, the final system prompt is a single document containing the coordinator's workflow *plus* the complete instructions for both subagents. The LLM reads all of it upfront and knows exactly what to tell each subagent when it spawns them.

The coordinator is also explicit about concurrency:

```markdown
### Step 3 — Spawn two subagents CONCURRENTLY
Spawn BOTH subagents at the same time (do not wait for one before
spawning the other).

### Step 4 — Wait for both subagents to complete
Do NOT process either subagent's output until BOTH have returned.
```

TrueForge tracks subagent threads via `thread.created` and `thread.done` SSE events. The coordinator runner in Python (`coordinator.py`) tracks these:

```python
for event in client.stream_turn(session_id, user_message):
    if isinstance(event, ThreadCreatedEvent):
        threads_created.append(event.thread_id)
    elif isinstance(event, ThreadDoneEvent):
        threads_done.append(event.thread_id)
    elif isinstance(event, TurnDoneEvent):
        final_output = event.output_content
```

Two `ThreadCreated` events → two `ThreadDone` events → then the coordinator's merged output arrives in `TurnDoneEvent`.

---

## Output Contracts

Each subagent must return a strict JSON schema. The fundamentals subagent:

```json
{
  "status": "ok",
  "yield_trend": "improving | stable | deteriorating | null",
  "payout_sustainability": "safe | watch | at_risk | null",
  "suggested_yield_update": 3.5,
  "reasoning": "...",
  "error_message": null,
  "failed_code": null
}
```

The risk subagent:

```json
{
  "risk_level": "low | medium | high | unknown",
  "signals": ["dividend cut announced"],
  "sources": [{"title": "...", "url": "..."}],
  "reasoning": "..."
}
```

The coordinator's final output must end with a fenced block tagged `coordinator-output`:

````markdown
```coordinator-output
{
  "ticker": "INFY",
  "status": "ok",
  "merge_reasoning": "...",
  "fundamentals": {...},
  "risk": {...},
  "diff": "--- a/...\n+++ b/...",
  "diff_generated": true,
  "changed_fields": ["Yield %"],
  "review_date": "2026-08-27"
}
```
````

The Python parser extracts it with a regex and raises `ValueError` if the block is missing or malformed — the seam between prompt and code is explicit and tested:

```python
_COORDINATOR_OUTPUT_RE = re.compile(
    r"```coordinator-output\s*(\{.*?\})\s*```",
    re.DOTALL,
)

def _parse_coordinator_output(text: str) -> dict:
    match = _COORDINATOR_OUTPUT_RE.search(text)
    if not match:
        raise ValueError("No ```coordinator-output``` block found")
    return json.loads(match.group(1))
```

---

## Verifying with Promptfoo

The prompts were designed, but were they correct? Rather than find out during a live agent run, I set up [promptfoo](https://promptfoo.dev) evals — one suite per subagent.

The eval structure:

```
evals/
    fundamentals_subagent/
        promptfoo.yaml    ← 5 test cases
        prompt.yaml       ← chat template
    risk_subagent/
        promptfoo.yaml    ← 5 test cases
        prompt.yaml       ← chat template
```

Each `prompt.yaml` is a two-message chat: the system prompt loads directly from the markdown file, and the user message carries the test input:

```yaml
- role: system
  content: "file://../../config/prompts/fundamentals_subagent.md"
- role: user
  content: "{{user_message}}"
```

### Test cases — fundamentals subagent

Five cases covering the decision boundaries:

| Case | Input | Expected |
|---|---|---|
| Improving yield | DPS trending up, 40 % payout, positive FCF | `yield_trend=improving`, `payout_sustainability=safe` |
| Deteriorating + at-risk | DPS falling, 94 % payout, negative FCF | `yield_trend=deteriorating`, `payout_sustainability=at_risk` |
| Stable + watch | Flat DPS, 78 % payout | `yield_trend=stable`, `payout_sustainability=watch` |
| Null payout_ratio | `payout_ratio=null`, `dividend_yield_pct=4.2` | `payout_sustainability=null`, `suggested_yield_update=4.2` |
| Null DPS history | `dividends_per_share_history=null`, `payout_ratio=65 %` | `yield_trend=null`, `payout_sustainability=safe` |

Assertions mix structural checks (JavaScript) with reasoning quality checks (LLM rubric):

```yaml
assert:
  - type: javascript
    description: yield_trend is improving
    value: JSON.parse(output).yield_trend === 'improving'
  - type: llm-rubric
    value: >
      The reasoning cites at least one specific numeric value from the
      input data and explains how yield_trend was derived.
```

### Test cases — risk subagent

The risk subagent normally calls a news search MCP tool — which doesn't exist in a promptfoo context. The fix: inject mock articles in the user message and tell the model to treat them as search results:

```yaml
- role: user
  content: |
    Ticker: {{ticker}}
    search_window_days: 90

    === EVALUATION MODE ===
    Treat the following as articles returned by your search tool.

    {{mock_articles}}
```

Five cases:

| Case | Mock articles | Expected |
|---|---|---|
| Explicit cut announcement | "INFY announces 30 % dividend reduction" | `risk_level=high` |
| Earnings miss only | "XYZ misses Q3 by 28 %, analysts flag sustainability" | `risk_level=medium` |
| Irrelevant articles | General market commentary, no dividend mention | `risk_level=low`, empty signals |
| No search results | "Search returned 0 results" | `risk_level=unknown` (not `low`) |
| FCF decline, no cut language | "TCS FCF fell 35 % YoY" | `risk_level=medium` |

---

## Three Bugs the Evals Caught

Running the evals before any live agent run caught three real prompt issues.

### Bug 1: `file://` syntax in prompt templates

The first run errored on all 5 cases:

```
Invalid type for 'messages[0].content': expected one of a string or
array of objects, but got an object instead.
```

The prompt template used `content: {file: path}` — a YAML object — instead of `content: "file://path"` — a string. Promptfoo was passing the raw dict to the OpenAI API.

Fix: one-line change in `prompt.yaml`.

### Bug 2: DPS array ordering was ambiguous

After fixing the syntax, Case 2 (deteriorating yield) failed — the model returned `yield_trend: "improving"` instead of `"deteriorating"`.

The test data was `[24, 22, 20, 18, 14]` — oldest first, latest last. The model assumed newest first, read `24` as the latest value, compared it against the average of `[22, 20, 18]`, and concluded improving.

The prompt said "compare the most recent value against the 3-period average" — but said nothing about array order. The model's assumption (newest-first) is reasonable. The ambiguity was in the prompt.

![promptfoo showing Case 2 failing with yield_trend=improving](/images/divvy-forge-coordinator-evals/eval-failure-dps-ordering.png)

Fix: added one sentence to `fundamentals_subagent.md`:

```
dividends_per_share_history (ordered oldest-first; the last element
is the most recent period)
```

### Bug 3: null propagation not followed

Case 4 (null `payout_ratio`) failed — the model returned `payout_sustainability: "safe"` instead of `null`.

The model's logic: `payout_ratio=null` → can't trigger `at_risk` or `watch` → "otherwise → safe". That's technically consistent with the prompt's decision tree. But the prompt also had a constraint: "if `payout_ratio` is null, set `payout_sustainability` to null." The constraint was there but buried at the bottom of the file, after the analysis steps.

The model followed the decision tree and ignored the constraint.

Fix: moved the constraint up and made it impossible to miss:

```markdown
**IMPORTANT — null propagation rule**: if `payout_ratio` is null, you
MUST set `payout_sustainability` to `null`. Do NOT infer sustainability
from FCF alone; `payout_ratio` is the primary indicator and its absence
makes the conclusion undetermined.
```

After all three fixes: 5/5 on both suites.

![promptfoo showing 5/5 pass on fundamentals subagent](/images/divvy-forge-coordinator-evals/eval-pass-fundamentals.png)

![promptfoo showing 5/5 pass on risk subagent](/images/divvy-forge-coordinator-evals/eval-pass-risk.png)

---

## Provider Independence

The evals are written against the output contract — not against model-specific phrasing. The assertion `JSON.parse(output).yield_trend === 'improving'` doesn't care what words the model used in its reasoning. The `llm-rubric` assertions check whether the reasoning is logically grounded in the input data, not whether it uses particular language.

To run the same evals against a different provider:

```bash
npx promptfoo eval -c evals/fundamentals_subagent/promptfoo.yaml \
  --providers anthropic:claude-sonnet-4-5-20251001
```

No YAML changes. If the assertions pass, the prompt works with that provider. If they fail, you know exactly which contract was violated and can fix the prompt rather than working around a specific model's quirks.

---

## Running the Evals

```bash
make eval               # both suites
make eval-fundamentals  # fundamentals only
make eval-risk          # risk only
make eval-view          # open results in browser
```

Requires `OPENAI_API_KEY` in `.env` and Node 22 (`nvm use 22`).

---

## What's Next

Part 4: `github-pr-opener` MCP tool — the missing piece that turns the coordinator's diff into an actual GitHub PR on `HiteshRepo/stock-screeners`. Once that's in, the full loop closes.

---

*Code: [github.com/HiteshRepo/divvy-forge](https://github.com/HiteshRepo/divvy-forge)*
