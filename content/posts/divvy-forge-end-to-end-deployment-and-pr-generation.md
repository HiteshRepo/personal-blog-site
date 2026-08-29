---
title: "End-to-End Deployment and Live PR Generation (divvy-forge Part 4)"
date: 2026-08-29T18:00:00-07:00
summary: "The final part of the divvy-forge series: wiring TrueForge deployment, discovering the real agent manifest API through trial and error, fixing coordinator prompt flow so subagents run silently, and watching the agent open a real GitHub PR with coordinator reasoning, a unified diff, and subagent findings."
draft: false
ai_generated: true
tags: ["ai-agents", "trueforge", "mcp", "python", "divvy-forge", "daytona", "prompt-engineering", "github"]
categories: []
---

> **Note:** This post was AI-generated from rough notes using the blog generation workflow.

This is part 4 of the divvy-forge series.
[Part 1](https://hiteshpattanayak.com/posts/trueforge-daytona-setup-what-the-docs-miss/) covered TrueForge + Daytona setup.
[Part 2](https://hiteshpattanayak.com/posts/building-mcp-tool-servers-for-a-dividend-review-agent-divvy-forge-part-2/) covered the MCP tool servers.
[Part 3](https://hiteshpattanayak.com/posts/divvy-forge-coordinator-prompt-design-and-evals/) covered coordinator prompt design and evals.

---

The previous three posts built all the pieces: TrueForge and Daytona running locally, three MCP tool servers, a coordinator with tested subagent prompts. This post covers getting everything wired together and watching the agent open a real GitHub PR against my dividend portfolio.

It took more iteration than I expected. The TrueForge API has a few surprises.

Demo video: [Watch on YouTube](https://youtu.be/H8XZ2pNBTug)

![divvy-forge architecture: batch_runner triggers a TrueForge session, the coordinator spawns two parallel subagents, merges their findings into a diff, and opens a GitHub PR](/images/divvy-forge-e2e/architecture.svg)

## What Deployment Means Here

divvy-forge has no Kubernetes, no Docker Compose, no cloud deployment. "Deploy" means:

1. Start three MCP servers as local HTTP processes
2. Register them with TrueForge (Settings → Connectors)
3. Register the coordinator agent with its manifest
4. Run `batch_runner.py`

I wrote a `deploy.py` script and a `Makefile` target to do steps 2 and 3 programmatically. The goal was `make deploy` as the single command before every run.

## Discovering the Real API Shape

The TrueForge API is undocumented beyond the README. I probed it with curl to figure out what each endpoint actually accepts.

**MCP server registration** was the first surprise. I assumed `POST /api/v1/settings/mcp-servers` with `{name, url}`. The real schema:

```json
{
  "manifest": {
    "type": "remote",
    "name": "divvy-reader",
    "url": "http://localhost:9001/sse",
    "description": "Reads divvy markdown files from HiteshRepo/stock-screeners"
  }
}
```

Two things wrong with my first attempt: the fields had to be nested under `manifest`, and `type: "remote"` was required. There is no stdio transport in TrueForge's connector model — servers must be reachable over HTTP.

That meant updating each MCP server to support SSE transport alongside the existing stdio mode. FastMCP (the MCP Python SDK) supports this via `mcp.run(transport="sse")`. I added a `--sse` flag to each server's entry point and Makefile targets to start them in HTTP mode:

```bash
make serve-divvy-reader-http    # port 9001
make serve-market-data-http     # port 9002
make serve-github-pr-http       # port 9003
```

The URL must include the `/sse` path — TrueForge uses the registered URL verbatim as the SSE endpoint, so `http://localhost:9001` returns 404 while `http://localhost:9001/sse` returns the SSE stream.

**Agent registration** had the same pattern. I assumed the model was a string:

```json
{"model": "openai/gpt-4o"}
```

It's an object:

```json
{"model": {"name": "openai/gpt-4o"}}
```

And MCP server references are objects too, not strings:

```json
{"mcp_servers": [{"name": "divvy-reader"}]}
```

Once I had the right shapes, `make deploy` went green:

![TrueForge Connectors UI showing divvy-reader, github-pr-opener, and market-data-fetcher all Connected](/images/divvy-forge-e2e/trueforge-connectors.png)

## The Subagent Question

I spent time early on trying to figure out whether TrueForge supported dynamic subagents. The config accepts `dynamic_sub_agents: {enabled: true}` without complaint, but I couldn't find the config key anywhere in TrueForge's backend source. My first test ended with the coordinator outputting "I've launched the subagents for both fundamentals analysis and dividend cut risk assessment, I'll wait for their findings" — zero tool calls, one sad turn, done.

The answer came from the database. TrueForge stores everything in SQLite. Looking at `turn_thread` rows, the agent run had only a `main` thread — no subagent threads were spawned.

Then I looked at an earlier run (before I knew the correct system prompt). That run showed something different: TrueForge's UI rendered `Sub-agent: fundamentals-analysis` and `Sub-agent: dividend-cut-risk` as distinct steps in the agent flow. Subagents were supported — the coordinator prompt just wasn't triggering them correctly.

## Getting the Coordinator to Shut Up

The coordinator prompt had the agent announcing its intentions at every step. "I've read the ticker state. Now I'll fetch fundamentals." "Launching subagents now." The problem: TrueForge ends a turn when the model produces text output. If the coordinator narrates while spawning subagents, the turn closes before it gets the results back.

The fix is simple but non-obvious: the coordinator must produce **only tool calls** during the subagent phase, no text. Any text in that model response becomes the turn's final output.

I added an explicit instruction to the coordinator prompt:

```text
**IMPORTANT: Output NO text in this step. Only tool calls.**
Do not write any message before, during, or after spawning the subagents.
Any text you output here will end your turn prematurely before you receive
the subagent results.
```

The same applies after subagents return. The coordinator must go directly from receiving results to merging and generating the diff — silently — and only produce text once it writes the `coordinator-output` JSON block.

## Multi-Turn Continuation

Even with the silent subagent spawning, the coordinator's work spans multiple turns. TrueForge's `ask_user_questions` feature was also firing mid-run, pausing to ask which analysis path to take. I disabled it in the agent manifest config:

```yaml
config:
  ask_user_questions:
    enabled: false
```

For the multi-turn problem, `run_coordinator_turn` needed a continuation loop. After each turn, it checks for the `coordinator-output` block. If not found, it submits a `"continue"` message on the same session and tries again, up to 10 times:

```python
for _ in range(_MAX_CONTINUATION_TURNS - 1):
    continuation_output, _ = _stream_one_turn(
        client, session_id, "continue", threads_created, threads_done
    )
    if _COORDINATOR_OUTPUT_RE.search(final_output):
        data = _parse_coordinator_output(final_output)
        return _build_result(data, final_output, threads_created, threads_done)
```

## Daytona Sandboxes Spinning Up

Each agent run creates a Daytona sandbox for code execution. The sandbox is where the fundamentals subagent runs its Python analysis — computing yield trend, payout sustainability, and the suggested yield update. TrueForge provisions the sandbox transparently; from the coordinator's perspective it just calls a `bash` tool.

The Daytona dashboard shows the sandboxes spinning up per run, auto-stopping after 5 minutes of inactivity:

![Daytona dashboard showing multiple TrueForge-provisioned sandboxes in Stopped state](/images/divvy-forge-e2e/daytona-sandboxes.png)

Each sandbox is a container with 1 vCPU, 1 GiB RAM, and 3 GiB storage — just enough to run a Python script:

![Daytona sandbox details: 1 vCPU, 1 GiB RAM, 3 GiB, auto-stop 5m, python label](/images/divvy-forge-e2e/daytona-sandbox-1.png)

## The Agent Flow

With everything wired, a `make single TICKER=INFY` run produces this in TrueForge's UI:

![TrueForge agent steps: read_ticker, get_fundamentals, Sub-agent fundamentals-analysis, Sub-agent dividend-cut-risk, get_current_datetime — with coordinator-output JSON below](/images/divvy-forge-e2e/trueforge-agent-flow.png)

Nine tool calls in total:

- `read_ticker` (divvy-reader) — loads current yield, payout ratio, notes, raw markdown
- `get_fundamentals` (market-data-fetcher) — fetches live data from yfinance
- `Sub-agent: fundamentals-analysis` — writes and executes Python in the Daytona sandbox, computes yield trend (improving: 25.0 vs 3-period avg 22.0) and payout sustainability (safe: 64.6% payout, positive FCF of 3.733B)
- `Sub-agent: dividend-cut-risk` — searches for recent dividend-cut signals (none found)
- `get_current_datetime` — stamps the review date
- Coordinator merges findings, generates the unified diff, outputs `coordinator-output` JSON

## The PR

The batch runner parses the `coordinator-output` block and hands it to `github-pr-opener`. The result:

![GitHub PR list showing Divvy Review: INFY (2026-08-29) open](/images/divvy-forge-e2e/pr-opened.png)

The PR body has the coordinator's reasoning, the diff, and collapsed sections for each subagent's findings:

![PR body showing Proposed Changes, Coordinator Reasoning, unified diff, and collapsed Fundamentals and Risk sections](/images/divvy-forge-e2e/pr-body.png)

The diff itself is minimal — only the yield and date changed:

![GitHub Files Changed: INFY yield updated from 3.50 to 4.50, date updated from 2025-08-25 to 2026-08-29](/images/divvy-forge-e2e/pr-files-changed.png)

The coordinator's reasoning is traceable: "Dividend per share rose to 25.0 from a 3-period prior average of 22.0, which is +13.6% and meets the improving threshold. Payout ratio is 64.6% and free cash flow is positive at 3733000000.0, supporting a safe classification."

## What I'd Do Differently

**MCP server discovery at deploy time.** Right now `deploy.py` hardcodes the server URLs (`localhost:9001-9003`). A cleaner approach would be to read URLs from a config file so the same script works against a remote TrueForge instance without edits.

**Rate limit handling.** The coordinator runs against a 30k TPM limit on the OpenAI free tier. The assembled prompt (coordinator system + subagent instructions + tool responses + subagent results) easily approaches that ceiling. I trimmed the subagent instruction files and switched to a higher-capacity model, but a proper fix would be retry-with-backoff in the streaming client.

**Agent mode toggle.** I added `AGENT_MODE=single` as a fallback for when TrueForge's subagent mechanism isn't available — the coordinator does the full analysis inline without spawning subagents. The subagent mode is the default; single is there for debugging or version compatibility.

## Source

All the code is at <https://github.com/HiteshRepo/divvy-forge>.

The three earlier posts in the series cover the pieces that make this run: the TrueForge + Daytona setup, the MCP tool servers, and the coordinator prompt design with promptfoo evals.
