---
title: "GitOps Homelab: Running Ollama and Open WebUI on K3s with ArgoCD"
date: 2026-07-21T14:00:00-07:00
summary: "The second part of the GPU homelab series: bootstrapping a full GitOps platform on k3s using ArgoCD's app-of-apps pattern, wiring up Ollama and Open WebUI, and the four gotchas that will trip you up."
draft: false
ai_generated: false
tags: ["homelab", "kubernetes", "k3s", "argocd", "gitops", "ollama", "open-webui", "self-hosting", "nvidia", "gpu"]
categories: []
---

The [previous post](https://hiteshpattanayak.com/posts/gpu-enabled-kubernetes-homelab-setting-up-a-gtx-1650-laptop-as-a-k3s-node/) covered getting the GPU stack running on a single laptop: driver → CUDA → container toolkit → k3s → device plugin. At the end of that post you have a single-node cluster that can schedule GPU workloads. That's the foundation. This post builds everything on top of it.

The goal: a complete self-hosted platform — Ollama, Open WebUI, Grafana, a dashboard, and uptime monitoring — managed entirely by ArgoCD from a GitHub repo. Push a YAML file, ArgoCD deploys it. `kubectl apply` by hand is only used once, during the initial bootstrap.

All manifests, scripts, and Makefile targets are in [HiteshRepo/k3s-homelab](https://github.com/HiteshRepo/k3s-homelab).

## Why GitOps Instead of Plain kubectl

`kubectl apply -f` works, but it doesn't scale well as a workflow. You accumulate manual steps, forget what you applied, and have no easy way to recover if the node dies.

GitOps flips the model. The repository is the source of truth. The cluster continuously reconciles itself against what's in the repo. This gives you:

- **Rollback via git revert** — any change is a commit, so undoing it is a one-liner.
- **Cluster rebuild from scratch in two commands** — `./gpu-node-setup.sh` and `./first-time-setup.sh`.
- **Drift detection** — ArgoCD notices if something in the cluster diverges from the repo and can auto-heal it.
- **Visibility** — the ArgoCD UI shows exactly what's deployed, whether it's in sync, and what the last diff was.

None of this requires a cloud provider or a managed Kubernetes service. It runs fine on a single laptop.

## The App-of-Apps Pattern

The bootstrap is a single command:

```bash
kubectl apply -f app-of-apps.yaml
```

That one file creates an ArgoCD `Application` resource that points at the `apps/` directory in the repo. ArgoCD then discovers every other `Application` manifest in that directory and deploys them — including the one that manages ArgoCD itself. This is the app-of-apps pattern.

The structure looks like this:

```text
app-of-apps.yaml          ← the one file you apply by hand
apps/
  argocd.yaml             ← ArgoCD manages itself
  metallb.yaml
  traefik.yaml
  cert-manager.yaml
  local-path-provisioner.yaml
  ollama.yaml
  open-webui.yaml
  grafana.yaml
  homarr.yaml
  uptime-kuma.yaml
```

Each file in `apps/` is an ArgoCD `Application` that points at a Helm chart or a directory of manifests. ArgoCD watches the repo and re-syncs whenever those files change.

## Sync Waves: Encoding the Dependency Chain

Not all apps can deploy in any order. MetalLB must exist before Traefik can get an external IP. Cert-manager must be ready before anything tries to issue a TLS certificate. ArgoCD's sync waves let you express this dependency declaratively.

Each `Application` manifest gets an annotation:

```yaml
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: "1"
```

ArgoCD deploys wave 0 first, waits for health, then wave 1, and so on. The full dependency chain in this setup:

```text
Wave 0 — MetalLB (assigns IPs to LoadBalancer services)
Wave 1 — Traefik (ingress, needs a real IP from MetalLB)
Wave 1 — Cert-manager (TLS, doesn't depend on Traefik but can run in parallel)
Wave 2 — Local-path-provisioner (PVC support for the rest)
Wave 3 — Everything else (Ollama, Open WebUI, Grafana, Homarr, Uptime Kuma)
```

Without sync waves you'd have to manually apply resources in the right order and babysit the deployment. With them, `kubectl apply -f app-of-apps.yaml` handles the entire sequence.

## The Traffic Path

When you open `https://chat.lab.hiteshp.in` in a browser, the request goes through three layers before it reaches Open WebUI:

```text
DNS (*.lab.hiteshp.in → local IP, via /etc/hosts on client machines)
      ↓
MetalLB (bare-metal LoadBalancer — assigns a real IP to the Traefik Service)
      ↓
Traefik (ingress controller — TLS termination, routes by hostname)
      ↓
Open WebUI Service → Pod
```

**MetalLB** solves a problem that's easy to miss: on a bare-metal cluster, `Service` of type `LoadBalancer` just hangs in `<pending>` forever because there's no cloud provider to allocate an IP. MetalLB fills that role, pulling IPs from a configured address pool on your local network.

**Traefik** handles routing and TLS. A `Traefik IngressRoute` resource maps hostnames to backend services and terminates HTTPS so your apps don't have to. Cert-manager issues and renews the certificates automatically.

This three-layer setup is more infrastructure than strictly necessary for a homelab, but it mirrors how production clusters work, which is half the point.

## Storage: local-path-provisioner

Ollama needs persistent storage for model weights. Models are large — llama3.2:3b is around 2 GB — and re-downloading them every time the pod restarts is not acceptable.

The lightweight answer for a single-node cluster is `local-path-provisioner`. It satisfies `PersistentVolumeClaim` requests by creating directories on the host filesystem and binding them to pods. You get the standard PVC lifecycle (the directory is cleaned up when the PVC is deleted) without the complexity of Ceph or NFS.

Using raw `hostPath` volumes is the common shortcut, but it has no lifecycle management and no capacity limits. local-path-provisioner is the right call here.

## Deploying Ollama with GPU Access

The Ollama deployment requests a GPU with a single annotation:

```yaml
resources:
  limits:
    nvidia.com/gpu: 1
```

The rest of the deployment wires up storage and exposes the service:

```yaml
env:
  - name: OLLAMA_HOST
    value: "0.0.0.0"
volumeMounts:
  - name: ollama-storage
    mountPath: /root/.ollama
volumes:
  - name: ollama-storage
    persistentVolumeClaim:
      claimName: ollama-pvc
```

After ArgoCD deploys it, pull a model:

```bash
kubectl -n ollama exec -it deploy/ollama -- ollama pull llama3.2:3b
```

Verify the GPU is actually being used (not just falling back to CPU):

```bash
kubectl -n ollama exec -it deploy/ollama -- nvidia-smi
```

You should see the Ollama process in the process list with non-zero GPU memory usage while a model is loaded.

## Wiring Open WebUI to Ollama

Open WebUI connects to Ollama via an environment variable:

```yaml
env:
  - name: OLLAMA_BASE_URL
    value: "http://ollama.ollama.svc.cluster.local:11434"
  - name: WEBUI_AUTH
    value: "true"
```

`OLLAMA_BASE_URL` uses the cluster-internal DNS name (`<service>.<namespace>.svc.cluster.local`) so traffic stays inside the cluster. `WEBUI_AUTH: true` enables the first-admin registration flow — the first user to sign up gets admin rights. After that, new users must be approved.

Once both pods are running, Open WebUI is available at `https://chat.lab.hiteshp.in` (or whatever hostname you configured in the IngressRoute).

## The Full Setup Sequence

```bash
# Clone the repo
git clone https://github.com/HiteshRepo/k3s-homelab.git
cd k3s-homelab

# Step 1: GPU stack (requires reboot between runs — see previous post)
./gpu-node-setup.sh

# Step 2: k3s + ArgoCD + full platform bootstrap
# Prompts for your GitHub username, then handles everything else
./first-time-setup.sh

# Step 3: Create secrets that ArgoCD cannot manage (must exist before sync)
make homarr-secret
make cloudflared-secret TUNNEL_TOKEN=<token>   # optional, for external access

# Step 4: Bootstrap ArgoCD with the app-of-apps
kubectl apply -f app-of-apps.yaml

# Step 5: Pull a model after Ollama is running
kubectl -n ollama exec -it deploy/ollama -- ollama pull llama3.2:3b
```

After step 5, add entries to `/etc/hosts` on any machine you want to access the services from, pointing the `*.lab.hiteshp.in` hostnames at the MetalLB IP assigned to Traefik.

The deployed apps and their URLs:

| App | URL |
|-----|-----|
| ArgoCD | <https://argocd.lab.hiteshp.in> |
| Open WebUI | <https://chat.lab.hiteshp.in> |
| Grafana | <https://grafana.lab.hiteshp.in> |
| Homarr | <https://homarr.lab.hiteshp.in> |
| Uptime Kuma | <https://status.lab.hiteshp.in> |
| Traefik dashboard | <https://traefik.lab.hiteshp.in> |

## The Gotchas

These are the four issues that are not documented clearly anywhere and will cost you hours.

### 1. ArgoCD v3.x Redis Crash on k3s (x86_64)

After installing ArgoCD v3.x, the Redis pod crashes immediately with:

```text
exec /usr/local/bin/docker-entrypoint.sh: exec format error
```

The root cause: containerd pulls the OCI manifest index for the Redis image but fails to resolve the correct platform at runtime on x86_64 k3s. This is an upstream issue in how ArgoCD v3.x packages its Redis dependency.

**Fix:** Pin ArgoCD to v2.13.3, which uses Redis 7.x and does not have this issue.

```bash
helm install argocd argo/argo-cd --version 2.13.3 ...
```

Check the upstream ArgoCD issue tracker before upgrading to v3.x — this should be fixed in a future release.

### 2. Namespace Stuck in Terminating

If you delete a namespace that contains ArgoCD `Application` resources, it will hang in `Terminating` indefinitely. The reason: ArgoCD applications have a finalizer (`resources-finalizer.argocd.argoproj.io`) that requires the ArgoCD controller to run the cleanup logic. But deleting the namespace kills the controller pod before the finalizer can execute.

**Fix:** Remove the finalizers manually before deleting the namespace.

```bash
# For each Application in the namespace:
kubectl patch application <name> -n argocd \
  -p '{"metadata":{"finalizers":[]}}' --type=merge

# Then delete the namespace
kubectl delete namespace <name>
```

### 3. Homarr db-encryption Secret

Homarr 8.x requires a Kubernetes secret with a DB encryption key to exist before the pod starts. If the secret is missing, the pod fails with `CreateContainerConfigError`. This is not prominently documented.

Create the secret before ArgoCD syncs the Homarr app:

```bash
make homarr-secret
# which runs:
# kubectl create secret generic homarr-db-secret \
#   --from-literal=db-encryption-key=$(openssl rand -hex 32) \
#   -n homarr
```

ArgoCD cannot manage this secret because it would need to store the value in git, which defeats the purpose of a secret. It's a prerequisite that must exist out-of-band.

### 4. Traefik IngressRoute Namespace

`IngressRoute` resources (Traefik's CRD for routing) must live in the `traefik-system` namespace, not in the namespace of the app they route to. If you put an IngressRoute in `ollama` or `open-webui`, Traefik ignores it.

The Helm values flag that enables routing to services in other namespaces:

```yaml
# traefik Helm values
providers:
  kubernetesCRD:
    allowCrossNamespace: true
```

With this set, an IngressRoute in `traefik-system` can forward traffic to a service in any other namespace. Without it, cross-namespace routing silently fails.

## What's Next

The cluster is running locally and all services are accessible on the LAN. The next piece is external access — reaching `chat.lab.hiteshp.in` from outside the home network without opening ports or exposing a home IP.

Two options worth exploring:

- **Cloudflare Tunnel** — the `cloudflared` deployment is already in the repo; you just need a Cloudflare account and a tunnel token. Traffic goes outbound from the cluster to Cloudflare's edge, no inbound firewall rules needed.
- **Tailscale** — creates a private overlay network; the laptop becomes a Tailscale node and is reachable from any device on the tailnet.

Both approaches are zero-NAT, meaning no router configuration is required. The Cloudflare Tunnel approach also gives you a real public domain with automatic TLS, which makes the homelab feel more like a real deployment.
