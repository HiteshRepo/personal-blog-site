---
title: "GitOps Homelab: Adding LiteLLM as a Unified AI Gateway for Ollama and Cloud Models"
date: 2026-07-25T12:00:00-07:00
summary: "How to add LiteLLM as a proxy layer on top of Ollama and Open WebUI, unifying local and cloud AI models behind a single OpenAI-compatible endpoint, managed via GitOps with ArgoCD."
draft: false
ai_generated: true
tags: ["homelab", "kubernetes", "k3s", "argocd", "gitops", "litellm", "ollama", "open-webui", "openai", "anthropic", "self-hosting"]
categories: []
---

> **Note:** This post was AI-generated from rough notes using the blog generation workflow.

The [previous post](https://hiteshpattanayak.com/posts/gitops-homelab-running-ollama-and-open-webui-on-k3s-with-argocd/) ended with Ollama and Open WebUI running on k3s, managed by ArgoCD. Local models work — you can chat with `llama3.2:3b` through the browser. But the moment you want to also use GPT-4o or Claude for a task that needs more capability, you have to configure a second connection in Open WebUI's admin panel, manage separate API keys, and switch connections manually for different models.

This post adds LiteLLM as a proxy layer that solves that. By the end, Open WebUI shows local Ollama models and cloud models in the same dropdown, all routed through a single internal service. One URL, one key, everything available.

All manifests and Makefile targets are in [HiteshRepo/k3s-homelab](https://github.com/HiteshRepo/k3s-homelab).

## The Problem: Two Separate Connections

Open WebUI natively supports two connection types: Ollama (for local models) and OpenAI-compatible APIs (for cloud models). They are configured separately in the admin panel, and they appear as separate model groups in the UI.

If you want `llama3.2:3b` and `gpt-4o` in the same session without switching connections, you have to configure two separate connections in the admin panel, keep two sets of API credentials, and tell each tool (Open WebUI, Continue, Aider) about both endpoints.

Scaling this to more providers makes it worse. Three providers means three connections everywhere. The problem compounds.

## What LiteLLM Does

LiteLLM is a proxy that speaks OpenAI's API on the inbound side and translates requests to the appropriate backend (Ollama, OpenAI, Anthropic, Bedrock, etc.) on the outbound side. Every caller sees one endpoint and one API key. LiteLLM handles the routing.

The traffic flow for this setup:

```text
Open WebUI → LiteLLM (/v1/chat/completions)
                ├── model: llama3.2:3b     → Ollama (cluster-internal)
                ├── model: gpt-4o          → OpenAI API
                └── model: claude-3-5-sonnet → Anthropic API
```

The caller — whether it's Open WebUI, Aider, or a curl command — never needs to know which backend handles the request. Model routing is purely config-driven on the LiteLLM side.

## Model Config as a ConfigMap

LiteLLM is configured via a YAML file. Storing it in a Kubernetes ConfigMap keeps it in Git and lets ArgoCD manage it — no container rebuilds to add a model.

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: litellm-config
  namespace: litellm
data:
  config.yaml: |
    model_list:
      - model_name: llama3.2:3b
        litellm_params:
          model: ollama/llama3.2:3b
          api_base: http://ollama.ollama.svc.cluster.local:11434

      - model_name: gpt-4o
        litellm_params:
          model: openai/gpt-4o
          api_key: os.environ/OPENAI_API_KEY

      - model_name: claude-3-5-sonnet
        litellm_params:
          model: anthropic/claude-3-5-sonnet-20241022
          api_key: os.environ/ANTHROPIC_API_KEY

    general_settings:
      master_key: os.environ/LITELLM_MASTER_KEY
```

The `api_base` for Ollama is `http://ollama.ollama.svc.cluster.local:11434` — the standard Kubernetes cluster-internal DNS name derived from `<service>.<namespace>.svc.cluster.local:<port>`. Read your Ollama Service manifest: if the service is named `ollama` and it lives in the `ollama` namespace, the DNS name is exactly that. No guesswork.

## Secret Layering

Cloud provider API keys and the LiteLLM master key live in a Secret in the `litellm` namespace:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: litellm-keys
  namespace: litellm
type: Opaque
data:
  openai-api-key: <base64>
  anthropic-api-key: <base64>
  master-key: <base64>
```

Create this before ArgoCD syncs the LiteLLM app — if the Secret doesn't exist, the pod fails on startup:

```bash
make litellm-secret OPENAI_API_KEY=sk-... ANTHROPIC_API_KEY=sk-ant-...
```

Kubernetes Secrets are namespace-scoped. Open WebUI lives in the `ollama` namespace and needs the master key to authenticate against LiteLLM. Since you can't reference a Secret across namespaces, the master key must be duplicated into the `ollama` namespace:

```bash
kubectl get secret litellm-keys -n litellm -o jsonpath='{.data.master-key}' | \
  xargs -I{} kubectl create secret generic litellm-master-key \
  --from-literal=master-key={} -n ollama
```

This duplication is intentional. Kubernetes doesn't have a native cross-namespace secret reference mechanism (without an operator like External Secrets or Sealed Secrets). For a homelab, duplicating the single key is the right call over adding another dependency.

## Adding LiteLLM to the GitOps Repo

The LiteLLM ArgoCD Application goes in `apps/litellm.yaml`, pointing at a `manifests/litellm/` directory:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: litellm
  namespace: argocd
  annotations:
    argocd.argoproj.io/sync-wave: "3"
spec:
  project: default
  source:
    repoURL: https://github.com/HiteshRepo/k3s-homelab
    targetRevision: HEAD
    path: manifests/litellm
  destination:
    server: https://kubernetes.default.svc
    namespace: litellm
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

Sync wave 3 puts it after MetalLB, Traefik, and local-path-provisioner — the same wave as Ollama and Open WebUI. The order within a wave doesn't matter since LiteLLM doesn't depend on Open WebUI and vice versa.

The LiteLLM Deployment mounts the ConfigMap and references the Secret:

```yaml
spec:
  containers:
    - name: litellm
      image: ghcr.io/berriai/litellm:main-stable
      args: ["--config", "/app/config.yaml", "--port", "4000"]
      envFrom:
        - secretRef:
            name: litellm-keys
      volumeMounts:
        - name: config
          mountPath: /app/config.yaml
          subPath: config.yaml
  volumes:
    - name: config
      configMap:
        name: litellm-config
```

The `IngressRoute` goes in `traefik-system` (not `litellm`) — same pattern as the other apps in this setup:

```yaml
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: litellm
  namespace: traefik-system
spec:
  entryPoints:
    - websecure
  routes:
    - match: Host(`litellm.lab.hiteshp.in`)
      kind: Rule
      services:
        - name: litellm
          namespace: litellm
          port: 4000
  tls:
    certResolver: letsencrypt
```

After pushing these files, force a sync:

```bash
make sync APP=litellm
```

Verify LiteLLM is up and listing models:

```bash
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
  curl http://litellm.litellm.svc.cluster.local:4000/v1/models \
  -H "Authorization: Bearer $(kubectl get secret litellm-keys -n litellm \
      -o jsonpath='{.data.master-key}' | base64 -d)"
```

## Wiring Open WebUI to LiteLLM

Update the Open WebUI deployment to point at LiteLLM instead of (or in addition to) Ollama directly:

```yaml
env:
  - name: OPENAI_API_BASE_URL
    value: "http://litellm.litellm.svc.cluster.local:4000/v1"
  - name: OPENAI_API_KEY
    valueFrom:
      secretKeyRef:
        name: litellm-master-key
        key: master-key
```

Then sync:

```bash
make sync APP=ollama
```

**Important:** these env vars configure the connection at deployment time, but Open WebUI stores connection settings in its own database. If Open WebUI was previously configured with different settings, the database takes precedence over env vars. You must also add the connection manually:

Admin Panel → Settings → Connections → Add OpenAI connection:

- URL: `http://litellm.litellm.svc.cluster.local:4000/v1`
- Key: master key from above

```bash
kubectl get secret litellm-keys -n litellm -o jsonpath='{.data.master-key}' | base64 -d
```

After saving, Open WebUI fetches the model list from LiteLLM and all configured models appear in the model selector — local and cloud, side by side.

## The Gotchas

### OOMKills on `main-latest`

The `ghcr.io/berriai/litellm:main-latest` nightly build includes a Prisma schema migration that runs on startup and spikes memory well past 1 Gi. On a resource-constrained homelab node, this causes OOMKills before the container even starts serving requests.

The fix is to use `main-stable` and disable the schema migration:

```yaml
image: ghcr.io/berriai/litellm:main-stable
env:
  - name: DISABLE_SCHEMA_UPDATE
    value: "true"
  - name: STORE_MODEL_IN_DB
    value: "false"
```

`STORE_MODEL_IN_DB: false` means model config comes from the ConfigMap only, not the database — which is what you want for GitOps anyway. `DISABLE_SCHEMA_UPDATE: true` skips the migration entirely.

### GPU Held by Unknown Pods

When an Ollama pod gets stuck in `Unknown` state — usually after a node crash or forced delete — it keeps holding the `nvidia.com/gpu: 1` resource. New Ollama pods queue behind it with `Insufficient nvidia.com/gpu` and never start.

The pod is unreachable by normal `kubectl delete`, so you need to force it:

```bash
kubectl delete pod <pod-name> -n ollama --force --grace-period=0
```

After the pod disappears, the GPU resource is released and the new pod schedules. Check with:

```bash
kubectl describe node | grep -A5 "Allocated resources"
```

### Docker Hub ImagePullBackOff

Using `latest` tags with the default `Always` pull policy means Kubernetes tries to pull from Docker Hub every time the pod restarts. Docker Hub has intermittent CDN reliability issues — on a bad day, Ollama goes down every time a pod restarts because the pull fails.

The fix is `imagePullPolicy: IfNotPresent`:

```yaml
spec:
  containers:
    - name: ollama
      image: ollama/ollama:latest
      imagePullPolicy: IfNotPresent
```

With this, Kubernetes uses the already-cached image and skips the pull entirely. For a ~4 GB image on a homelab with no local registry, this is the right default.

## The Running Stack

After all of this, the services are:

| App | URL |
|-----|-----|
| LiteLLM | <https://litellm.lab.hiteshp.in> |
| Open WebUI | <https://chat.lab.hiteshp.in> |

Open WebUI shows all models — `llama3.2:3b` from Ollama, `gpt-4o` from OpenAI, `claude-3-5-sonnet` from Anthropic — in a single list. Requests route through LiteLLM transparently.

Any other tool that supports OpenAI-compatible APIs (Continue, Aider, Cursor) can now point at `http://litellm.litellm.svc.cluster.local:4000/v1` with the master key and get access to all models. No per-tool provider configuration needed.

## What's Next

The stack now handles both local inference and cloud model routing. The next layer is external access — reaching `chat.lab.hiteshp.in` from outside the home network without opening firewall ports. The Cloudflare Tunnel setup (`cloudflared`) is already in the repo for this; it just needs a tunnel token and a Cloudflare account.
