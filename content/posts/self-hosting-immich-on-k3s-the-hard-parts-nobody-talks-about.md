---
title: "Self-Hosting Immich on K3s — The Hard Parts Nobody Talks About"
date: 2026-11-15T16:00:00+05:30
summary: "A practical guide to deploying Immich on a single-node k3s cluster with ArgoCD GitOps — covering six real production gotchas including AppArmor signal blocking, postgres initdb permissions, and MetalLB subnet mismatches."
draft: false
ai_generated: true
tags: ["immich", "k3s", "kubernetes", "homelab", "self-hosted", "argocd", "postgres", "apparmor", "traefik", "metallb"]
categories: []
---

> **Note:** This post was AI-generated from rough notes using the blog generation workflow.

Immich is the best self-hosted Google Photos alternative available today — face recognition, CLIP semantic search, timeline, albums, mobile apps. Getting it deployed on k3s sounds straightforward. It is not. This post covers the six gotchas that will burn hours if you don't know about them.

---

## The Stack

- **k3s** — single-node Kubernetes
- **ArgoCD** — GitOps, declarative everything
- **Immich Helm chart** — `immich-app/immich-charts` v0.12.0
- **Traefik** — ingress with self-signed TLS
- **MetalLB** — LoadBalancer IP assignment
- **local-path-provisioner** — PVC storage on NVMe

Immich itself runs five components: `immich-server`, `immich-machine-learning`, `postgres` (custom image with VectorChord), `valkey` (Redis replacement since chart 0.10.0), and a 200GB library PVC.

---

## Gotcha 1 — AppArmor Blocks Inter-Process Signals

**Symptom:** postgres startup process exits with code 1 exactly 60 seconds after WAL redo completes. `gosu` hangs indefinitely. `pg_ctl stop` returns `Permission denied`.

**Root cause:** The `cri-containerd.apparmor.d` profile blocks `SIGINT` between processes. The postgres WAL startup process signals the postmaster after recovery — AppArmor denies it. The 60-second hang is a timeout waiting for a signal that never arrives.

You can confirm this in `dmesg`:

```
apparmor="DENIED" operation="signal" profile="cri-containerd.apparmor.d"
pid=234147 comm="postgres" requested_mask="send" denied_mask="send" signal=int
```

**Fix:** Add the AppArmor unconfined annotation to your pod template:

```yaml
metadata:
  annotations:
    container.apparmor.security.beta.kubernetes.io/postgres: unconfined
    container.apparmor.security.beta.kubernetes.io/fix-permissions: unconfined
```

This same issue affects any container that uses inter-process signaling or `gosu` for privilege dropping.

---

## Gotcha 2 — postgres initdb Needs Correct Directory Ownership

**Symptom:** postgres pod starts, prints `Using SSD storage`, then hangs. `initdb` never runs. Data directory stays empty.

**Root cause:** `local-path-provisioner` creates PVC directories as `root`. The Immich postgres image runs `gosu postgres` to drop privileges before `initdb`. With `runAsUser: 999`, the postgres user cannot `chmod` the root-owned data directory, so `initdb` fails silently.

**Fix:** Add an `initContainer` that runs as root and fixes ownership before the main container starts:

```yaml
initContainers:
  - name: fix-permissions
    image: busybox
    securityContext:
      runAsUser: 0
    command:
      - sh
      - -c
      - chown -R 999:999 /var/lib/postgresql/data && chmod 700 /var/lib/postgresql/data
    volumeMounts:
      - name: postgres-data
        mountPath: /var/lib/postgresql/data
```

Then set `runAsUser: 999` on the main postgres container so the entrypoint skips the gosu call entirely.

---

## Gotcha 3 — Chart 0.10.0 Removed the Bundled Postgres Subchart

**Symptom:** ArgoCD shows manifest generation error: `The postgres subchart has been removed.`

**Root cause:** Immich Helm chart 0.10.0 dropped the bundled PostgreSQL subchart entirely. The chart's `checks.yaml` explicitly throws an error if `postgresql:` **or** `redis:` keys exist in your values — even with `enabled: false`.

**Fix:** Remove both keys entirely from your values. Deploy a standalone postgres using the Immich-specific image:

```yaml
image: ghcr.io/immich-app/postgres:16-vectorchord0.4.3
```

This image includes the VectorChord extension required for Immich's ML-powered search. The chart now uses `valkey` instead of Redis — configure it under the `valkey:` key.

---

## Gotcha 4 — vchord Extension Must Be Created Manually

**Symptom:** Immich microservices worker crashes with `vchord must be loaded via shared_preload_libraries` even though `SHOW shared_preload_libraries` shows `vchord.so`.

**Root cause:** Timing issue. The Immich server connects and runs `CREATE EXTENSION IF NOT EXISTS vchord CASCADE` before VectorChord finishes its own initialization after a fresh database. The extension is loaded but its internal state isn't ready for a session-level CREATE.

**Fix:** Run this once after the first deployment, before Immich connects:

```bash
kubectl exec -n immich <postgres-pod> -- \
  psql -U immich -d immich -c 'CREATE EXTENSION IF NOT EXISTS vchord CASCADE'
```

After that, Immich connects cleanly on every subsequent restart.

---

## Gotcha 5 — MetalLB Subnet Mismatch

**Symptom:** Traefik gets a LoadBalancer IP (`192.168.1.200`) but it's not reachable from any device on the LAN.

**Root cause:** MetalLB IP pool was configured for `192.168.1.200-220` but the actual LAN subnet was `192.168.29.x`. MetalLB advertised the IP via L2 but the router didn't know about it.

**Fix:** Update two places:

```yaml
# gitops/manifests/metallb-config/ippool.yaml
addresses:
  - 192.168.29.200-192.168.29.220
```

```yaml
# gitops/apps/traefik.yaml
annotations:
  metallb.universe.tf/loadBalancerIPs: 192.168.29.200
```

Then patch the live service: `kubectl annotate svc traefik -n traefik-system metallb.universe.tf/loadBalancerIPs=192.168.29.200 --overwrite`

---

## Gotcha 6 — Traefik IngressRoute Namespace

**Symptom:** Navigating to `https://immich.lab.hiteshp.in` returns 404 from Traefik even though the IngressRoute exists.

**Root cause:** IngressRoutes must be created in the `traefik-system` namespace, not the app's namespace. Traefik only watches its own namespace for IngressRoute resources. This is because cross-namespace routing is enabled via `allowCrossNamespace: true` in Traefik's Helm values.

```yaml
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: immich
  namespace: traefik-system  # not immich
spec:
  routes:
    - match: Host(`immich.lab.hiteshp.in`)
      services:
        - name: immich-server
          namespace: immich  # service in its own namespace is fine
          port: 2283
```

---

## Mobile Access Without DNS

iOS and iPadOS don't support `/etc/hosts` overrides, so `immich.lab.hiteshp.in` won't resolve on mobile. The workaround: expose Immich via NodePort and point the mobile app directly at the node IP.

```bash
kubectl patch svc immich-server -n immich \
  -p '{"spec":{"type":"NodePort","ports":[{"port":2283,"nodePort":30283}]}}'
```

Then connect the Immich iOS/iPadOS app to `http://192.168.29.146:30283`. Works on the same WiFi network without any DNS configuration.

---

## GitOps Pattern

Two ArgoCD Applications with sync waves ensure correct ordering:

```yaml
# immich-prereqs — wave 3
# Creates: namespace, library PVC (200GB), postgres PVC (10GB)

# immich — wave 4
# Deploys: Helm chart with server, ML, valkey, postgres
```

The PVC must exist before the Helm chart deploys — that's why the prereqs application runs one wave earlier. With `automated: {prune: true, selfHeal: true}`, any drift from the Git repo is automatically corrected.

---

## Summary

| Gotcha | Symptom | Fix |
|--------|---------|-----|
| AppArmor signal blocking | 60s timeout, gosu hangs | `apparmor: unconfined` annotation |
| initdb permission denied | Data dir stays empty | initContainer chown to 999:999 |
| Removed postgres subchart | Manifest generation error | Deploy standalone postgres image |
| vchord CREATE EXTENSION fails | Immich crashes on startup | Run CREATE EXTENSION manually once |
| MetalLB subnet mismatch | LoadBalancer IP unreachable | Update IP pool to match LAN subnet |
| IngressRoute namespace | 404 from Traefik | Create IngressRoute in traefik-system |

All config lives in a [public GitHub repo](https://github.com/HiteshRepo/k3s-homelab) — clone, run `first-time-setup.sh`, and ArgoCD bootstraps the full stack.
