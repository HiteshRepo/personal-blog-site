# GitOps Homelab: Running Ollama and Open WebUI on K3s with ArgoCD

- type: technical
- tags: homelab, kubernetes, k3s, argocd, gitops, ollama, open-webui, self-hosting, nvidia, gpu

## Context

The previous post covered getting the GPU stack running on a single laptop (driver → CUDA → container toolkit → k3s → device plugin). This post picks up from there and covers the full GitOps homelab: deploying a complete self-hosted platform using ArgoCD to manage everything declaratively from a GitHub repo.

The end result: push a YAML file to GitHub and ArgoCD deploys it automatically. No `kubectl apply` by hand after the initial bootstrap.

## Key ideas

- **Why GitOps over plain kubectl**: the repo is the source of truth; rollback is `git revert`; you can rebuild the entire cluster from scratch by running two commands; drift is detected and auto-healed
- **App-of-apps pattern**: a single `kubectl apply -f app-of-apps.yaml` bootstraps everything; ArgoCD then manages itself and all child apps; explain why this works and why the sync waves exist (MetalLB must exist before Traefik can get an IP, etc.)
- **Sync waves**: show the dependency chain and how ArgoCD's sync wave annotations encode it declaratively rather than manually ordering commands
- **Traffic path**: DNS (`*.lab.hiteshp.in`) → MetalLB (bare-metal LoadBalancer) → Traefik (ingress + TLS termination) → service; explain why each layer exists and what problem it solves
- **Storage**: local-path-provisioner as a lightweight PVC solution for single-node; why hostPath is worse (no lifecycle management, no capacity limits)
- **Ollama on GPU in Kubernetes**: `nvidia.com/gpu: 1` resource request, PVC for model storage, the OLLAMA_HOST env var; verify GPU usage with nvidia-smi inside the pod
- **Open WebUI**: wiring it to Ollama via OLLAMA_BASE_URL, WEBUI_AUTH for the first-admin-registration flow
- **Secrets that can't be in Git**: Homarr's db-encryption key and cloudflared token; how to handle prerequisites that ArgoCD can't manage

## Real-world gotchas to cover

- **ArgoCD v3.x Redis ECR multi-arch issue on k3s (x86_64)**: `exec /usr/local/bin/docker-entrypoint.sh: exec format error`; containerd pulls the OCI manifest index but fails to resolve the correct platform at runtime; fix was to pin ArgoCD to v2.13.3 which uses Redis 7.x; note upgrade path back to v3.x when fixed upstream
- **Namespace deletion stuck on Terminating**: ArgoCD Application finalizers (`resources-finalizer.argocd.argoproj.io`) require the ArgoCD controller to process; deleting the namespace kills the controller before it can run the finalizers; fix: remove finalizers manually before deletion
- **Homarr db-encryption secret**: Homarr 8.x requires a pre-existing Kubernetes secret with a DB encryption key; not documented prominently; pod crashes with `CreateContainerConfigError` until it exists
- **Traefik IngressRoute namespace**: IngressRoutes must be in `traefik-system`, not the app's namespace; `allowCrossNamespace: true` in Helm values is what makes cross-namespace routing work

## Setup reference

Full repo with all manifests, scripts, and Makefile targets: <https://github.com/HiteshRepo/k3s-homelab>

Key setup commands to include in the post:

```bash
# Clone the repo
git clone https://github.com/HiteshRepo/k3s-homelab.git
cd k3s-homelab

# GPU setup (requires reboot between runs)
./gpu-node-setup.sh

# Full platform setup (prompts for GitHub username, installs k3s + ArgoCD, bootstraps everything)
./first-time-setup.sh

# Prerequisites that must be created before ArgoCD deploys the apps
make homarr-secret
make cloudflared-secret TUNNEL_TOKEN=<token>  # optional, for external access

# Pull a model into Ollama (after cluster is up)
kubectl -n ollama exec -it deploy/ollama -- ollama pull llama3.2:3b

# Verify GPU is being used
kubectl -n ollama exec -it deploy/ollama -- nvidia-smi
```

Apps deployed and their URLs (resolved via /etc/hosts on client machines):

| App | URL |
|-----|-----|
| ArgoCD | <https://argocd.lab.hiteshp.in> |
| Open WebUI | <https://chat.lab.hiteshp.in> |
| Grafana | <https://grafana.lab.hiteshp.in> |
| Homarr | <https://homarr.lab.hiteshp.in> |
| Uptime Kuma | <https://status.lab.hiteshp.in> |
| Traefik | <https://traefik.lab.hiteshp.in> |

## Structure

1. Where we left off (GPU laptop with k3s running): <https://hiteshpattanayak.com/posts/gpu-enabled-kubernetes-homelab-setting-up-a-gtx-1650-laptop-as-a-k3s-node/>
2. The repo structure and GitOps flow
3. Bootstrap: one `kubectl apply` to rule them all
4. The full stack walkthrough (sync waves, what each app does)
5. Deploying Ollama + Open WebUI
6. The gotchas section
7. What's next (external access via Cloudflare Tunnel or Tailscale)
