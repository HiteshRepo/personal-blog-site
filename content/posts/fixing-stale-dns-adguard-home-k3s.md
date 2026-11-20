---
title: "Fixing Stale DNS Once and For All with AdGuard Home on K3s"
date: 2026-11-20T15:00:00+05:30
summary: "My JIO router was caching NXDOMAIN responses, Chrome was caching them again on top of that, and I spent way too long wondering why a DNS record I'd just created wasn't resolving. Here's how AdGuard Home on K3s fixed it permanently."
draft: false
ai_generated: true
tags: ["adguard", "dns", "homelab", "k3s", "kubernetes", "networking", "cloudflare", "chrome"]
categories: []
---

> **Note:** This post was AI-generated from rough notes using the blog generation workflow.

I added a new DNS record. Waited a minute. Opened Chrome. Got "This site can't be reached." Checked `nslookup` from Terminal — resolved fine. Chrome: still broken. Flushed the macOS DNS cache. Chrome: still broken. Ten minutes later, it just started working.

This happened enough times that I finally traced it properly.

---

## The Two-Layer DNS Cache Problem

**Layer 1 — the router.** My JIO router's DNS proxy caches responses aggressively. After creating a new record, devices on the LAN kept getting stale NXDOMAIN from the router cache even after the record was live upstream.

**Layer 2 — Chrome.** Chrome maintains its own internal DNS cache completely separate from the OS resolver. `sudo dscacheutil -flushcache` does exactly nothing for Chrome. They expire independently.

This explained the random behaviour: different tabs had different cache entries expiring at different times. When Chrome caches an NXDOMAIN, it holds it. The only reliable fixes:

```
chrome://net-internals/#dns      → Clear host cache
chrome://net-internals/#sockets  → Close idle sockets
```

Or just relaunch Chrome. But all of this is treating symptoms. The root cause was the router handing out stale responses.

---

## Deploying AdGuard Home on K3s

I gave AdGuard a dedicated MetalLB LoadBalancer IP — `192.168.29.202` — using the annotation so it gets a fixed address to put in the router:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: adguard-dns
  namespace: adguard
  annotations:
    metallb.universe.tf/loadBalancerIPs: 192.168.29.202
spec:
  type: LoadBalancer
  selector:
    app: adguard
  ports:
    - name: dns-udp
      port: 53
      targetPort: 53
      protocol: UDP
    - name: dns-tcp
      port: 53
      targetPort: 53
      protocol: TCP
```

A second ClusterIP service exposes the web UI on port 80, routed through a Traefik IngressRoute (in the `traefik-system` namespace — Traefik ignores routes in other namespaces by default).

---

## Bootstrap DNS: The DoH Catch

I configured AdGuard to use Cloudflare DNS-over-HTTPS:

```
https://cloudflare-dns.com/dns-query
```

There's a chicken-and-egg problem. AdGuard needs to resolve `cloudflare-dns.com` to reach the DoH endpoint, but it can't resolve anything until it has a working upstream. The fix is bootstrap DNS — plain DNS addresses used specifically to resolve the DoH hostname on startup:

```
Bootstrap DNS: 1.0.0.1, 1.1.1.1
```

Without bootstrap DNS configured, AdGuard silently fails to reach its upstream and falls back to whatever it can find. This isn't obvious from the UI.

---

## Two Things That Went Wrong

**Port 3000 redirect.** AdGuard's setup wizard runs on port 3000. After completing setup, it redirects the browser to `hostname:3000`. Behind Traefik this breaks — the browser hits port 3000 directly instead of going through Traefik on 443. Fix: change `http.address` in `AdGuardHome.yaml` from `0.0.0.0:3000` to `0.0.0.0:80` via `kubectl exec`, then restart the pod.

**Cloudflare Access blocking SPA API calls.** I had Cloudflare Access protecting several services. AdGuard's web UI makes `fetch()` POST requests internally (the DNS config endpoint, filter list updates, etc.). Access intercepts these and returns authentication redirects, causing "Failed to fetch" errors throughout the UI. Fix: remove Cloudflare Access from AdGuard entirely. It has its own login — there's no reason to put Access in front of it.

---

## Pointing the Router at AdGuard

JIO Router → Network → LAN → DHCP Setup → DNS Servers → "Use Below":

```
Primary DNS:   192.168.29.202
Secondary DNS: 1.1.1.1
```

The secondary DNS matters. If the K3s cluster goes down, devices fall back to Cloudflare directly instead of losing DNS entirely.

After renewing DHCP leases on client devices, all DNS queries on the `192.168.29.x` network flow through AdGuard → Cloudflare DoH.

---

## Does It Fix the Stale DNS Problem?

Yes, with an asterisk.

AdGuard querying Cloudflare DoH means I'm no longer at the mercy of the router's DNS cache. New records propagate within the authoritative TTL — usually 60 seconds. Chrome's internal cache is now the *only* caching layer, not the second of two. When I clear Chrome's cache, it immediately gets a fresh response from AdGuard.

The asterisk: Chrome's cache is still there and always will be. If Chrome caches an NXDOMAIN before the record existed, it'll serve that until its timer expires. The manual flush is still occasionally needed, just much less often.

The ad blocking is a side effect worth mentioning — every device on the LAN gets it automatically with no per-device configuration. I can inspect queries and add custom rewrites from one place.

---

## Quick Reference

| Thing | Value |
|-------|-------|
| AdGuard DNS IP | `192.168.29.202` |
| AdGuard web UI | `https://adguard.hiteshpattanayak.com` |
| Upstream DNS | `https://cloudflare-dns.com/dns-query` (DoH) |
| Bootstrap DNS | `1.0.0.1`, `1.1.1.1` |
| Flush Chrome DNS | `chrome://net-internals/#dns` → Clear host cache |
| macOS DNS flush | `sudo dscacheutil -flushcache` (doesn't affect Chrome) |

Manifests are in [HiteshRepo/k3s-homelab](https://github.com/HiteshRepo/k3s-homelab) under `gitops/manifests/adguard/`.
