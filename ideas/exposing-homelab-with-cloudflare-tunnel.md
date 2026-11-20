# Exposing Your Homelab to the Internet with Cloudflare Tunnel (Without Opening Any Ports)

- type: technical
- tags: cloudflare, homelab, self-hosted, security, dns, kubernetes, zero-trust, github-oauth

- The problem: homelab services are only accessible on the LAN via `/etc/hosts` entries — useless on iPhone/iPad outside home WiFi, can't share with family, no real DNS
- Solution: Cloudflare Tunnel (`cloudflared`) already running in K3s as a Deployment; the tunnel connects outbound to Cloudflare's edge — no port forwarding, no firewall rules, no public IP needed
- DNS migration prerequisite: Cloudflare Tunnel requires the domain to be in Cloudflare's DNS (zone must be managed by Cloudflare); if domain uses NS1 or another provider, Cloudflare imports all existing DNS records before you switch nameservers — zero downtime if you verify the import first
- Tunnel token is a Kubernetes Secret: `cloudflared-token` in the `cloudflared` namespace; the deployment reads it via `TUNNEL_TOKEN` env var; if the secret is missing the pod gets `CreateContainerConfigError` — this was the reason the tunnel had been down for 121 days
- Adding routes via API instead of UI: `PUT /accounts/{id}/cfd_tunnel/{tunnel_id}/configurations` replaces the entire ingress config atomically — added 9 services in a single API call; DNS CNAMEs must be created separately via `POST /zones/{zone_id}/dns_records`
- Cloudflare Access for auth: GitHub OAuth as identity provider — user visits `homarr.hiteshpattanayak.com`, Cloudflare intercepts before the request reaches K3s, redirects to GitHub login, verifies email matches allowlist, then proxies through; `auto_redirect_to_identity: true` skips the provider selection screen
- Access breaks SPA API calls: Cloudflare Access sets a session cookie but SPA frameworks making `fetch()` POST requests to their own backend fail with "Failed to fetch" — Access doesn't forward cookies for non-GET requests correctly; fix is to remove Access from admin tools (AdGuard, ArgoCD) that have their own auth
- One GitHub OAuth app covers all services: callback URL is `https://{team}.cloudflareaccess.com/cdn-cgi/access/callback` — same for every protected subdomain; create one OAuth app in GitHub, reuse the Client ID/Secret across all Cloudflare Access applications
- Service URL format: `http://{service}.{namespace}.svc.cluster.local:{port}` — cloudflared runs inside K3s and resolves cluster-internal DNS; bypasses Traefik entirely for tunnelled services
- MetalLB L2 mode + WiFi unreliability: even with Cloudflare Tunnel for external access, LAN access via MetalLB VIP (`192.168.29.200`) breaks periodically on WiFi due to stale ARP; Cloudflare Tunnel is more reliable for daily use than the LAN route
