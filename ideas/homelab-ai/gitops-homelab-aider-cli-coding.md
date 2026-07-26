# GitOps Homelab: AI-Powered CLI Coding with Aider, LiteLLM, and Local Models

- type: technical
- tags: homelab, aider, litellm, ollama, coding, cli, dotfiles, self-hosting, openai, anthropic, kubernetes

## Context

The previous post added LiteLLM as a unified AI gateway aggregating local Ollama models and cloud APIs behind a single OpenAI-compatible endpoint. This post picks up from there and wires that gateway into real developer tooling — specifically aider, an AI pair programmer that runs in the terminal and edits files directly.

The end result: a single `aider` command in any project directory gives you an AI coding assistant backed by your homelab, with short aliases to switch between local and cloud models on the fly.

## Key ideas

- **Why aider over just llm CLI**: `llm` is a Unix tool for one-off queries and scripting; aider is a full coding session — it reads your repo, plans changes, edits files, shows diffs, and commits; the right tool depends on the task
- **Why LiteLLM as the gateway**: aider only needs one OpenAI-compatible endpoint; LiteLLM sits in front of Ollama, OpenAI, and Anthropic so aider never needs to know which backend is handling the request — swap models without changing aider config
- **Dotfiles as the right home for aider config**: `~/.aider.conf.yml` is machine config not homelab infrastructure; belongs in dotfiles alongside uv, llm, and other dev tool setup — bootstrapped via `make dev-tools`
- **Model aliases for ergonomics**: aider model names are verbose (`openai/ollama/llama3.2:3b`); `model-aliases` in the config maps short names (`local-llama`, `local-phi`) so `/model local-llama` works inside a session
- **`local-` prefix convention**: avoids clashing with aider's built-in OpenAI/Anthropic model names; all homelab-routed models (including cloud ones via LiteLLM) get the `local-` prefix to make routing explicit

## Models in the stack

### Currently running (GTX 1650, 4GB VRAM)

| Model | Alias | Why |
|-------|-------|-----|
| `llama3.2:3b` | `local-llama` | General purpose baseline |
| `qwen2.5:3b` | `local-qwen` | Strong reasoning for its size |
| `phi3.5` | `local-phi` | Microsoft's compact model, good instruction following |

### Planned upgrades (to benchmark)

| Model | Why worth trying |
|-------|-----------------|
| `qwen2.5-coder:3b` | Drop-in upgrade over `qwen2.5:3b` — fine-tuned specifically for code generation, much better for aider use case |
| `phi4-mini` | Newer generation phi, better benchmark scores than phi3.5 |
| `deepseek-r1:1.5b` | Reasoning model, very compact, surprisingly capable for its size |
| `qwen2.5-coder:7b` | Best coding model if it fits in 4GB VRAM with CPU offloading |
| `mistral:7b` | Solid general-purpose 7B |
| Kimi (Moonshot AI) | OpenAI-compatible cloud API, strong long-context and reasoning, free tier — adds another cloud option via LiteLLM without hosting anything |

### Why 3B models for local hosting

4GB VRAM is the hard constraint on a GTX 1650. 3B models at Q4 quantization use ~2GB, fitting comfortably. 7B models (~4GB) are borderline — they may run with CPU offloading but will be noticeably slower. Benchmarking both sizes is on the roadmap.

## Real-world gotchas to cover

- **`llm` vs `aider` is not either/or**: `llm` for quick queries and scripting, aider for coding sessions; covered both in one post but they serve different purposes
- **aider uses `litellm` Python library internally**: model prefix must be `openai/` not `litellm/` — the library interprets `litellm/` as a (non-existent) provider and throws `BadRequestError: LLM Provider NOT provided`
- **Self-signed cert SSL chain**: Traefik's `tls: {}` generates a new self-signed cert on each restart; Python (via `certifi`) ignores the system trust store entirely; things tried and failed: `update-ca-certificates`, `REQUESTS_CA_BUNDLE=""`, `REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt`; fix: `kubectl port-forward` exposed over plain HTTP on localhost, managed as a systemd service so it survives reboots
- **ClusterIP not reachable from host**: K3s ClusterIPs are virtual IPs managed by kube-proxy; not directly accessible from the host node; port-forward is the correct way to reach cluster services from the host
- **model-aliases dumps verbosely on `/model` switch**: aider prints the full aliases dict when you switch models — expected behavior, not an error; no way to suppress it

## Setup reference

```bash
# Install aider
make install-aider  # from dotfiles

# Symlink config
make symlink-aider  # from dotfiles

# Keep LiteLLM accessible on localhost (systemd service, survives reboots)
make pf-litellm-service  # from k3s-homelab

# Set the LiteLLM master key for aider
make litellm-master-key  # from k3s-homelab — prints the key
make set-ai-key KEY=<master-key>  # from dotfiles — sets OPENAI_API_KEY in shell profile
```

Inside aider:
```
/model local-llama     # switch to llama3.2:3b via Ollama
/model local-phi       # switch to phi3.5 via Ollama
/model local-gpt4o     # switch to gpt-4o via LiteLLM → OpenAI
/model local-sonnet    # switch to claude-sonnet-4-5 via LiteLLM → Anthropic
```

## Structure

1. Where we left off (LiteLLM proxying Ollama + OpenAI + Anthropic)
2. Why aider — what it does differently from llm CLI
3. Adding aider to dotfiles (install, config, symlink, model aliases)
4. The port-forward systemd service — why it exists and why HTTPS didn't work
5. The current model lineup and VRAM constraints
6. What's planned: coding-focused models and benchmarking methodology
7. What's next (Kimi, model benchmarking results)
