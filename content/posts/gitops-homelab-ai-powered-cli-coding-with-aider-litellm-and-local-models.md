---
title: "GitOps Homelab: AI-Powered CLI Coding with Aider, LiteLLM, and Local Models"
date: 2026-07-25T12:00:00-07:00
summary: "How to wire the LiteLLM gateway into aider for terminal-based AI pair programming, using model aliases, a port-forward systemd service to work around SSL issues, and the current 3B model lineup running on a GTX 1650."
draft: false
ai_generated: true
tags: ["homelab", "aider", "litellm", "ollama", "coding", "cli", "dotfiles", "self-hosting", "openai", "anthropic", "kubernetes"]
categories: []
---

> **Note:** This post was AI-generated from rough notes using the blog generation workflow.

The [previous post](https://hiteshpattanayak.com/posts/gitops-homelab-adding-litellm-as-a-unified-ai-gateway-for-ollama-and-cloud-models/) ended with LiteLLM running on k3s, proxying Ollama, OpenAI, and Anthropic behind a single OpenAI-compatible endpoint. Open WebUI can now reach all models through one URL with one key.

But Open WebUI is a browser tool. This post takes the same gateway and wires it into the terminal — specifically into [aider](https://aider.chat), an AI pair programmer that edits files directly inside your project directory.

The end result is a single `aider` command in any project that gives you an AI coding assistant backed by whichever model you pick — local or cloud — with short aliases to switch on the fly.

All aider config lives in [HiteshRepo/dotfiles](https://github.com/HiteshRepo/dotfiles). The port-forward setup lives in [HiteshRepo/k3s-homelab](https://github.com/HiteshRepo/k3s-homelab).

## Why Aider, Not Just the `llm` CLI

The `llm` CLI is a Unix tool: you pipe something in, get text out, compose it with other commands, script it. It's the right tool for one-off queries, quick lookups, and shell scripting.

Aider is a coding session. It reads your repository, builds context from the files you're working in, plans changes, edits files, shows you diffs, and can commit the results. You can ask it to add a function, fix a bug, refactor a module, and it will make the actual edits — not just describe them.

The distinction matters because the right tool depends on what you're doing. `llm "what does this error mean"` is one tool. `aider` with your repo loaded and a task to implement is another. Covering both in the same setup doesn't mean they're interchangeable.

## Why Route Aider Through LiteLLM

Aider supports OpenAI, Anthropic, and a growing list of providers directly. You could configure it to hit OpenAI with your OpenAI key and Anthropic with your Anthropic key. But that's two sets of credentials in your config, two endpoints to manage, and every other tool (Continue, Cursor, scripts) needs the same duplication.

LiteLLM solves this cleanly. Aider only needs one thing: an OpenAI-compatible endpoint. LiteLLM provides exactly that, sitting in front of Ollama, OpenAI, and Anthropic. When you tell aider to use a model, LiteLLM routes the request to the right backend. Switching from a local llama model to Claude doesn't require changing aider's configuration — you just pick a different model name.

## Aider Config Belongs in Dotfiles

Aider is configured via `~/.aider.conf.yml`. This is machine configuration — editor preferences, model defaults, aliases — not homelab infrastructure. It belongs alongside the rest of your dev tool setup in dotfiles, not in the k3s-homelab GitOps repo.

The dotfiles repo already manages `uv`, `llm`, and shell setup via a `Makefile`. Aider gets its own targets:

```bash
make install-aider   # installs aider via uv
make symlink-aider   # symlinks ~/.aider.conf.yml to dotfiles/aider/.aider.conf.yml
```

Bootstrapped as part of `make dev-tools` so a new machine gets everything in one step.

## The Config: One Endpoint, Model Aliases

The `~/.aider.conf.yml` points aider at LiteLLM on localhost (more on how that's exposed shortly) and maps short names to the full model strings:

```yaml
openai-api-base: http://localhost:4000/v1
openai-api-key: ${OPENAI_API_KEY}   # set to the LiteLLM master key

model: openai/llama3.2:3b           # default model on startup

model-aliases:
  local-llama: openai/llama3.2:3b
  local-qwen: openai/qwen2.5:3b
  local-phi: openai/phi3.5
  local-gpt4o: openai/gpt-4o
  local-sonnet: openai/claude-sonnet-4-5
```

Two things worth noting here.

**The `openai/` prefix is not optional.** Aider uses the `litellm` Python library internally. If you use `litellm/` as the model prefix instead of `openai/`, the library interprets it as a (non-existent) provider and throws `BadRequestError: LLM Provider NOT provided`. The prefix must be `openai/` regardless of what the actual backend is.

**The `local-` prefix convention.** Aider has built-in support for OpenAI and Anthropic model names. If you name an alias `gpt-4o`, aider will try to handle it through its built-in OpenAI integration rather than routing it through `openai-api-base`. Prefixing aliases with `local-` makes the routing explicit and avoids collisions. All models in this setup — including cloud ones routed via LiteLLM — use the `local-` prefix.

Inside an aider session, switching models is one command:

```text
/model local-llama     # llama3.2:3b via Ollama
/model local-phi       # phi3.5 via Ollama
/model local-gpt4o     # gpt-4o via LiteLLM → OpenAI
/model local-sonnet    # claude-sonnet-4-5 via LiteLLM → Anthropic
```

One note: when you run `/model`, aider prints the full `model-aliases` dict. This is expected behavior, not an error. There is no way to suppress it.

## The Port-Forward Systemd Service

The aider config points at `http://localhost:4000/v1`. LiteLLM runs inside the cluster. Getting it to localhost involved a detour through several dead ends.

The obvious path is to expose LiteLLM via an IngressRoute over HTTPS (already in place for `litellm.lab.hiteshp.in`). The problem: Python's SSL library uses `certifi`'s bundled CA bundle and ignores the system trust store entirely. Traefik's `tls: {}` generates a new self-signed cert on each restart. That cert will never be in `certifi`'s bundle.

Things tried that did not work:

- `update-ca-certificates` on the host
- `REQUESTS_CA_BUNDLE=""` (disables verification but `certifi` ignores it)
- `REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt` (Python ignores this too — `certifi` always wins)
- Pointing at the cluster's Let's Encrypt cert (requires a real domain reachable from inside the cluster)

The fix is simpler: `kubectl port-forward` exposes LiteLLM over plain HTTP on localhost. No SSL, no cert chain, no problem.

The k3s-homelab repo includes a target that creates a systemd service for the port-forward so it survives reboots:

```bash
make pf-litellm-service   # creates and enables the systemd service
```

One more constraint to be aware of: K3s ClusterIPs are virtual IPs managed by kube-proxy. They are not directly accessible from the host node — they only exist inside the cluster network. The port-forward is the correct and only practical way to reach a cluster service from the host without running a full VPN or CNI workaround.

To set the LiteLLM master key as `OPENAI_API_KEY` in your shell profile (required so aider picks it up):

```bash
make litellm-master-key        # prints the master key from the cluster secret
make set-ai-key KEY=<key>      # from dotfiles — writes to shell profile
```

## Current Models: GTX 1650, 4GB VRAM

The hard constraint on this hardware is 4GB VRAM. A GTX 1650 is a budget laptop GPU, and it shapes every model decision.

3B models at Q4 quantization use roughly 2GB — they fit comfortably with headroom. 7B models are ~4GB at Q4, which is borderline. They may run with CPU offloading but will be noticeably slower. The current lineup stays at 3B until there's benchmark data to justify the trade-off.

| Model | Alias | Why |
|-------|-------|-----|
| `llama3.2:3b` | `local-llama` | General purpose baseline |
| `qwen2.5:3b` | `local-qwen` | Strong reasoning for its size |
| `phi3.5` | `local-phi` | Microsoft's compact model, good instruction following |

## What's Coming: Coding-Focused Models

The current models are general-purpose. For aider specifically — where the task is code generation, refactoring, and file editing — there are better options to evaluate:

| Model | Why worth trying |
|-------|-----------------|
| `qwen2.5-coder:3b` | Drop-in upgrade over `qwen2.5:3b`, fine-tuned specifically for code |
| `phi4-mini` | Newer generation phi, better benchmark scores than phi3.5 |
| `deepseek-r1:1.5b` | Reasoning model, very compact, surprisingly capable for its size |
| `qwen2.5-coder:7b` | Best coding model if it fits in 4GB with CPU offloading |
| `mistral:7b` | Solid general-purpose 7B for comparison baseline |

The plan is to run each model against the same set of coding tasks in aider and compare: completion quality, edit accuracy, tokens per second, and whether the model reliably follows aider's structured edit format (required for file patching to work correctly).

[Kimi (Moonshot AI)](https://platform.moonshot.ai) is also on the list as a cloud option — it has an OpenAI-compatible API, strong long-context and reasoning capabilities, and a free tier. Adding it to LiteLLM's model list means it's immediately available in aider as another `local-kimi` alias without touching the dotfiles config.

## The Full Setup Sequence

```bash
# In k3s-homelab
make pf-litellm-service    # expose LiteLLM on localhost:4000
make litellm-master-key    # print the master key

# In dotfiles
make set-ai-key KEY=<master-key>   # write OPENAI_API_KEY to shell profile
make install-aider                 # install aider via uv
make symlink-aider                 # link ~/.aider.conf.yml

# Start coding
cd any-project/
aider
```

## What's Next

The aider setup is stable for local models. The immediate next step is benchmarking `qwen2.5-coder:3b` and `phi4-mini` against the general-purpose models on actual coding tasks — not synthetic benchmarks, but real aider sessions with file edits. Results will determine whether the upgrade is worth the model swap.

After that: Cloudflare Tunnel to make the whole stack reachable outside the home network, and Kimi as the first additional cloud model in the LiteLLM gateway.
