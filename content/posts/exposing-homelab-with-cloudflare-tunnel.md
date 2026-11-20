---
title: "Exposing Your Homelab to the Internet with Cloudflare Tunnel (Without Opening Any Ports)"
date: 2026-11-20T13:00:00+05:30
summary: "How I finally made my homelab accessible outside my LAN using Cloudflare Tunnel running in K3s — no port forwarding, no public IP, and GitHub OAuth for access control. Also: why the tunnel had been silently broken for 121 days."
draft: false
ai_generated: true
tags: ["cloudflare", "homelab", "self-hosted", "security", "dns", "kubernetes", "zero-trust", "github-oauth"]
categories: []
---

> **Note:** This post was AI-generated from rough notes using the blog generation workflow.

The problem with running a homelab entirely on your LAN is that it's entirely on your LAN. Every service I run — Homarr, ArgoCD, Grafana, Open WebUI, Immich — is only reachable via `/etc/hosts` entries pointing at `192.168.29.200`. That works fine on my laptop. It's completely useless on my iPhone when I'm not on home WiFi.

I didn't want to open ports on my router or deal with dynamic DNS. I didn't want to set up a VPN. What I wanted was something I could click on my phone without thinking about it.

Cloudflare Tunnel was the answer.

---

## How Cloudflare Tunnel Works

`cloudflared` runs inside your network, establishes outbound connections to Cloudflare's edge, and Cloudflare routes public traffic through those connections back to your services. No inbound port forwarding. No firewall rules. No public IP required.

In my case, `cloudflared` runs as a Deployment in K3s. It has direct access to cluster-internal DNS, so it can reach any service using the `{service}.{namespace}.svc.cluster.local` format — bypassing Traefik entirely.

---

## Prerequisite: Move Your Domain to Cloudflare DNS

Cloudflare Tunnel requires your domain to live in Cloudflare's DNS. If you're using another DNS provider (I was on NS1), you need to migrate first.

When you add a domain to Cloudflare, it scans your existing DNS records and imports them before you ever change your nameservers. Verify the imported records match your current provider exactly, then update nameservers at your registrar. Propagation took about 20 minutes. Zero downtime.

---

## The Tunnel Token Is a Kubernetes Secret

Create the tunnel from the Cloudflare dashboard: Zero Trust → Networks → Tunnels → Create tunnel → Cloudflared. Grab the token.

```bash
kubectl create secret generic cloudflared-token \
  --from-literal=token=<TUNNEL_TOKEN> \
  -n cloudflared
```

The Deployment references it as an environment variable:

```yaml
env:
  - name: TUNNEL_TOKEN
    valueFrom:
      secretKeyRef:
        name: cloudflared-token
        key: token
```

If the secret doesn't exist when the pod starts, you get `CreateContainerConfigError`. The pod won't start and ArgoCD will show the Deployment as `Synced` but the pod as not ready. This is how the tunnel was silently broken for **121 days** — the secret had been deleted during a cleanup and nobody noticed.

A `Synced` ArgoCD status and a healthy application are not the same thing.

---

## Configuring Routes via the API

Clicking through the UI for 9 services is tedious. The API replaces the entire ingress config atomically:

```bash
curl -X PUT \
  "https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations" \
  -H "Authorization: Bearer {API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "ingress": [
        {"hostname": "homarr.hiteshpattanayak.com",  "service": "http://homarr.homelab.svc.cluster.local:7575"},
        {"hostname": "immich.hiteshpattanayak.com",  "service": "http://immich-server.immich.svc.cluster.local:2283"},
        {"hostname": "grafana.hiteshpattanayak.com", "service": "http://prometheus-stack-grafana.monitoring.svc.cluster.local:80"},
        {"hostname": "argocd.hiteshpattanayak.com",  "service": "http://argocd-server.argocd.svc.cluster.local:80"},
        {"service": "http_status:404"}
      ]
    }
  }'
```

The last catch-all `http_status:404` is required — `cloudflared` errors on startup without it.

The API call configures routing but **does not** create DNS records. Create a CNAME for each hostname pointing at `{TUNNEL_ID}.cfargotunnel.com` separately.

---

## GitHub OAuth via Cloudflare Access

One GitHub OAuth app covers all services. The callback URL is always:

```
https://{your-team}.cloudflareaccess.com/cdn-cgi/access/callback
```

Create it in GitHub → Settings → Developer settings → OAuth Apps → New OAuth App. Set the callback URL above. Copy the Client ID and Secret into Cloudflare Zero Trust → Integrations → Identity providers → Add → GitHub.

Then for each service, create an Access Application:

```
Application type: Self-hosted
Application domain: homarr.hiteshpattanayak.com
Policy: Allow — Email — is — your@email.com
```

With `auto_redirect_to_identity: true`, users hit the service, get redirected to GitHub login, verify, and go through. The whole flow takes about 2 seconds.

---

## Where Cloudflare Access Breaks Things

Cloudflare Access sets a session cookie on the browser. For SPAs making background `fetch()` POST requests, this causes "Failed to fetch" — Access intercepts the POST and returns an authentication redirect, which the browser's `fetch()` can't follow cross-origin.

This happened with AdGuard Home's admin UI and with ArgoCD's internal API calls. The fix: remove Access from applications that have their own authentication layer. AdGuard has username/password. ArgoCD has its own login. Only protect services with no built-in auth.

---

## Tunnel Is More Reliable Than MetalLB on WiFi

My homelab uses MetalLB L2 mode for the LoadBalancer VIP (`192.168.29.200`). After every speaker restart, the gratuitous ARP re-announcement doesn't always propagate correctly on WiFi, leaving clients with stale ARP cache entries. ICMP works, TCP doesn't. This breaks every few days.

Cloudflare Tunnel is completely unaffected by this — it's an outbound connection from inside the cluster. My phone now uses `homarr.hiteshpattanayak.com` instead of the LAN address for daily use. It works at home, at a coffee shop, on cellular.

The full setup is in [HiteshRepo/k3s-homelab](https://github.com/HiteshRepo/k3s-homelab) under `gitops/manifests/cloudflared/` and `gitops/apps/cloudflared.yaml`.
