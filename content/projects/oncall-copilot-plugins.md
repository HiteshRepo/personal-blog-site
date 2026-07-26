---
title: "On-call Copilot — Automated Alert Investigation with Claude Code Plugins"
organization: "Improving"
role: "Senior Data Engineer"
startDate: "2026-04-01"
techStack: ["Claude Code", "Anthropic Claude API", "Elasticsearch", "Databricks", "Azure Data Explorer", "Azure Event Hubs", "Pulumi ESC", "Go", "Python", "Shell", "incident.io"]
featured: true
description: "Claude Code plugin system that automates cloud infrastructure on-call investigation — paste an alert URL, get a full root cause report in under 2 minutes"
weight: 5
---

## Project Overview

Built as part of on-call operations for a cloud data pipeline platform, this two-layer Claude Code plugin system automates alert investigation end-to-end. An on-call engineer pastes an incident.io alert URL into Claude Code and receives a complete investigation report — root cause, evidence chain, and recommended remediation — in under 2 minutes, without manually querying dashboards or log systems. Achieved **100% adoption** within the team.

The system covers 30+ distinct alert types across distributed data pipeline services including streaming ingestion, indexing jobs, REST APIs, EventHub, and Azure Data Explorer.

## Architecture

### Two-Layer Plugin Design

**`platform-tools`** — data-fetching primitives with no domain logic:

| Skill | Purpose |
|-------|---------|
| `alert-intake` | Fetches and normalises incident.io alert into a structured Investigation Request |
| `alert-list` | Lists active/recent alerts for shift handoff and triage |
| `es-query` | Executes ES\|QL queries via Kibana async search API |
| `dbx-query` | Runs SQL against Databricks SQL Warehouse via Statements API |
| `dbx-job-status` | Fetches Databricks job run history and full driver log stack traces |
| `adx-query` | Executes KQL queries against Azure Data Explorer |
| `pulumi-esc` | Reads secrets from Pulumi ESC environments |
| `vpn-connect` | Manages Azure VPN connectivity and tenant switching |

**`oncall-copilot`** — domain-specific investigation and reporting skills:

- Top-level routing skill classifies each alert as one of two service domains and delegates to the appropriate domain router
- Domain routers match alert name prefixes and call the correct per-alert skill
- Per-alert skills query multiple data sources via platform-tools, reason over the results, and produce a structured report

### Routing Hierarchy

```
investigate-dp-alert          ← single entry point
  ├── investigate-earn-alert  ← EARN domain router
  │     ├── e2e failures
  │     ├── ingestion / SDK / lifecycle / telemetry DLQ alerts
  │     ├── API error (5xx/4xx) and latency alerts
  │     ├── ADX cluster health, ingestion, materialized view alerts
  │     └── EventHub quota / throttling alerts
  └── investigate-atlas-alert ← ATLAS domain router
        ├── Discovery Service (4xx, 5xx, latency)
        ├── Routing Service (4xx, 5xx)
        ├── Databricks streaming failures, no-consumer, EventHub backlog
        ├── Databricks bad-data quarantine and resource (CPU/disk) alerts
        └── Raw Data Ingestion Service (4xx, 5xx, latency, EventHub failures)
```

### Data Flow

```
/platform-tools:alert-intake <alert-url>
  → fetches alert via incident.io MCP
  → emits structured Investigation Request (service, env, region, severity)

Investigation Request
  → consumed by router skills
  → routed to per-alert skill

Per-alert skill
  → queries ES|QL, Databricks SQL, KQL, Pulumi ESC via platform-tools
  → synthesises evidence across sources
  → produces root cause + evidence chain + remediation guidance
```

## Key Features

### Shift Operations Support

Beyond individual alert investigation, the plugin system supports full shift workflows:

- **`review-earn-dashboard`** / **`review-data-ingestion-dashboard`** / **`review-item-catalog-dashboard`** — structured shift health checks with RAG (Red/Amber/Green) status across 8–14 checks per dashboard
- **`review-dp-dashboards`** — umbrella review combining all dashboards into a single report
- **`create-oncall-handoff`** — pulls all alerts from the shift, generates a structured EARN/ATLAS summary, and creates a Confluence page with Teams-paste-ready output
- **`analyze-alert-noise`** — identifies flapping alerts and recurring patterns for tuning recommendations
- **`create-alert-report`** — creates a Confluence investigation report under the correct year/month/day hierarchy
- **`create-alert-teams-message`** — formats investigation output for clipboard paste into a Teams alert thread

### Plugin Packaging

Distributed as a Claude Code plugin installable from a GitHub marketplace source:

```bash
claude plugin marketplace add org/oncall-copilot-plugins
claude plugin install platform-tools@oncall-copilot-plugins
claude plugin install oncall-copilot@oncall-copilot-plugins
```

Or via `settings.json` for zero-touch deployment across team machines.

## Impact

- Reduced mean-time-to-investigation from ~10–15 minutes of manual dashboard querying to **under 2 minutes**
- Eliminated context switching across Kibana, Databricks, ADX, and incident.io during high-stress on-call situations
- Standardised investigation output — every report follows the same root cause → evidence → action structure regardless of which engineer is on call
- Shift health reviews previously done manually are now a single slash command

## Technologies

- **AI Orchestration**: Claude Code plugins, Anthropic Claude API, skill composition, LLM-as-orchestrator pattern
- **Data Sources**: Elasticsearch (ES|QL), Databricks (SQL Statements API), Azure Data Explorer (KQL), Pulumi ESC, incident.io MCP
- **Tooling**: Go (standalone CLI tools), Python, Shell
- **Packaging**: Claude Code plugin marketplace format, `settings.json` deployment
