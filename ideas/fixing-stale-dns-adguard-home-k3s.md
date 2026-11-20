# Fixing Stale DNS Once and For All with AdGuard Home on K3s

- type: technical
- tags: adguard, dns, homelab, k3s, kubernetes, networking, cloudflare, chrome

- The problem: Chrome has its own DNS cache separate from the system DNS cache; after creating new DNS records (e.g. `status.hiteshpattanayak.com`), Chrome caches the NXDOMAIN response for minutes to hours — `chrome://net-internals/#dns` clear host cache helps temporarily but `#sockets` flush is also needed; relaunching Chrome clears everything but that's not a workflow
- Why the system DNS flush doesn't help Chrome: `sudo dscacheutil -flushcache && sudo killall -HUP mDNSResponder` clears the macOS DNS cache; Chrome ignores this and uses its own internal cache; the caches expire independently — which is why the site "randomly" works in some tabs but not others (different sticky notes expiring at different times)
- Root cause of the stale NXDOMAIN: the JIO router's DNS proxy was caching old responses; when devices queried it after a new record was created, they got NXDOMAIN from the cache, stored it locally, and Chrome compounded the problem with its own layer of caching
- AdGuard Home as the fix: runs in K3s, assigned a dedicated MetalLB LoadBalancer IP (`192.168.29.202`); queries Cloudflare DoH (`https://cloudflare-dns.com/dns-query`) directly — no caching of negative responses, always fresh
- Two services for AdGuard: DNS service (`LoadBalancer` on `192.168.29.202:53`) and Web UI service (`ClusterIP` on port 80); the LoadBalancer needs a specific IP via `metallb.universe.tf/loadBalancerIPs: 192.168.29.202` annotation
- Router DNS config: JIO router → Network → LAN → DHCP Setup → DNS Servers → "Use Below" → Primary: `192.168.29.202`, Secondary: `1.1.1.1`; DHCP lease renewal on each device pushes the new DNS automatically
- AdGuard web UI port conflict with Cloudflare Access: Access intercepts the browser session but blocks SPA `fetch()` POST requests (`control/dns_config`, `control/test_upstream_dns`) — "Failed to fetch" errors; fixed by removing Cloudflare Access from AdGuard (it has its own login) and relying on its built-in auth
- nginx config uses port 80 not 3000: AdGuard setup wizard runs on 3000 and after setup redirects to `hostname:3000` — this breaks when going through a reverse proxy that only handles port 443; fix is to change `http.address` in `AdGuardHome.yaml` from `0.0.0.0:3000` to `0.0.0.0:80` via `kubectl exec` + pod restart
- Two-network home: JIO (`192.168.29.x`) has AdGuard, Airtel (`192.168.1.x`) is a separate subnet that can't reach `192.168.29.202`; Airtel devices don't benefit from AdGuard — TODO is to set Airtel DNS to `1.1.1.1` directly once the router password is recovered
- Bonus: ad blocking across all LAN devices — AdGuard's default filter lists block ads and trackers at DNS level for every device on JIO WiFi with no per-device browser extension needed
- Bootstrap DNS required for DoH: Cloudflare DoH resolves via `https://cloudflare-dns.com/dns-query`; to resolve that hostname, AdGuard needs bootstrap DNS servers (`1.0.0.1`, `1.1.1.1`) configured — otherwise it can't reach the DoH server on startup
