# GitOps Homelab: Adding LiteLLM as a Unified AI Gateway for Ollama and Cloud Models

- type: technical
- tags: homelab, kubernetes, k3s, argocd, gitops, litellm, ollama, open-webui, openai, anthropic, self-hosting

## Context

The previous post covered deploying Ollama and Open WebUI on K3s with ArgoCD. This post picks up from there and adds LiteLLM as a proxy layer that unifies local Ollama models and cloud provider APIs (OpenAI, Anthropic) behind a single OpenAI-compatible endpoint.

The end result: Open WebUI shows local and cloud models in the same model selector, all routed through one internal service — no separate API key config per provider in the UI.

## Key ideas

- **Why LiteLLM**: Open WebUI supports both Ollama and OpenAI endpoints separately, but LiteLLM gives you one URL and one key for everything; any tool that speaks OpenAI-compatible API (Continue, Aider, Cursor) can now hit a single endpoint and get access to all models
- **Traffic flow**: Open WebUI → LiteLLM (`/v1/chat/completions`) → routes to Ollama, OpenAI, or Anthropic based on model name — the caller never knows which backend is handling the request
- **Model config as a ConfigMap**: LiteLLM is configured via a YAML file listing models and their backends; storing it in a Kubernetes ConfigMap keeps it in Git and ArgoCD-managed, with no need to rebuild the container image to change models
- **Kubernetes DNS for inter-service calls**: the Ollama api_base is `http://ollama.ollama.svc.cluster.local:11434` — mechanically derived from `<service>.<namespace>.svc.cluster.local:<port>`; no guesswork, just read the Service manifest
- **Secret layering**: provider API keys live in a Secret in the `litellm` namespace; the auto-generated master key is duplicated into the `ollama` namespace so Open WebUI can reference it — Kubernetes secrets are namespace-scoped so cross-namespace sharing requires duplication or an operator
- **Open WebUI DB precedence**: env vars (`OPENAI_API_BASE_URL`, `OPENAI_API_KEY`) configure the connection at deployment time but Open WebUI's own database takes precedence; the connection must also be added manually in Admin Panel → Settings → Connections on first setup
- **`imagePullPolicy: IfNotPresent` on Ollama**: without this, Kubernetes defaults to `Always` for `latest` tags and re-pulls from Docker Hub on every pod restart; for a ~4GB image this is a major availability risk when Docker Hub has connectivity blips

## Real-world gotchas to cover

- **`main-latest` OOMKills**: the nightly dev build is heavy — Prisma schema migration alone spikes memory past 1Gi on startup; fix: switch to `main-stable` and set `DISABLE_SCHEMA_UPDATE=true`, `STORE_MODEL_IN_DB=false`, `DISABLE_ADMIN_UI=true`
- **GPU held by Unknown pods**: when an Ollama pod gets stuck in `Unknown` state it keeps holding `nvidia.com/gpu: 1`; new pods queue behind it with `Insufficient nvidia.com/gpu`; fix: `kubectl delete pod --force --grace-period=0`
- **Docker Hub ImagePullBackOff**: `latest` tag + `Always` pull policy + intermittent Docker Hub CDN issues = Ollama down every time the pod restarts; `imagePullPolicy: IfNotPresent` uses the already-cached image and skips the pull entirely

## Setup reference

```bash
# Create secrets before ArgoCD deploys LiteLLM (must exist first)
make litellm-secret OPENAI_API_KEY=sk-... ANTHROPIC_API_KEY=sk-ant-...

# Force sync after pushing changes
make sync APP=litellm
make sync APP=ollama  # if Open WebUI env vars changed

# Get the master key to add the connection in Open WebUI admin panel
kubectl get secret litellm-keys -n litellm -o jsonpath='{.data.master-key}' | base64 -d

# Verify LiteLLM is serving models
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
  curl http://litellm.litellm.svc.cluster.local:4000/v1/models
```

In Open WebUI → Admin Panel → Settings → Connections → add OpenAI entry:
- URL: `http://litellm.litellm.svc.cluster.local:4000/v1`
- Key: master key from above

| App | URL |
|-----|-----|
| LiteLLM | <https://litellm.lab.hiteshp.in> |
| Open WebUI | <https://chat.lab.hiteshp.in> |

## Structure

1. Where we left off (Ollama + Open WebUI running locally)
2. The problem: two separate connection configs for local vs cloud models
3. What LiteLLM is and how it fits in the stack
4. Adding LiteLLM to the GitOps repo (app, manifest, ingress route, Makefile secret target)
5. Wiring Open WebUI to LiteLLM
6. The gotchas section (OOM, GPU lock, Docker Hub, DB precedence)
7. What's next
