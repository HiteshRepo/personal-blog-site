# Why MetalLB L2 Mode Breaks on WiFi (And How to Fix It Permanently)

- type: technical
- tags: metallb, kubernetes, networking, arp, homelab, k3s, wifi, python

- The symptom: `ping 192.168.29.200` works (ICMP replies) but `curl https://immich.lab.hiteshp.in` times out or refuses connection — TCP broken, ICMP fine, same IP
- Root cause: MetalLB L2 mode uses ARP to claim the VIP (`192.168.29.200`) — it responds to ARP requests with a MAC address. On WiFi, the AP only forwards unicast frames to known associated client MACs; MetalLB's VIP MAC (`7a:10:c9:29:28:da`) is different from the node's real WiFi NIC MAC (`40:74:e0:0c:c7:c2`) — the AP doesn't know how to forward to it
- Why ICMP works but TCP doesn't: after a MetalLB speaker restart, the gratuitous ARP re-announcement doesn't always reach WiFi clients correctly; ICMP (ping) uses a simpler kernel path that bypasses some iptables rules; TCP hits the full kube-proxy iptables DNAT rules which require the packet to actually arrive at the node
- The iptables path: kube-proxy creates `KUBE-SERVICES → KUBE-EXT-* → KUBE-SVC-* → KUBE-SEP-*` chains in the NAT table; a packet destined for `192.168.29.200:443` gets DNAT'd to the Traefik pod IP (`10.42.0.215:443`); this works from inside the node (loop through router) but packets from WiFi clients never arrive because the AP drops them
- MetalLB FRR `permission denied` errors: the speaker pod (v0.15.x) logs continuous `permission denied` from the FRR sidecar — cosmetic only, FRR is for BGP mode and not used in L2; ignore these
- Fix attempt 1 (restart speaker): deleting the MetalLB speaker pod forces a fresh gratuitous ARP broadcast on restart; this works temporarily but breaks again after the next restart
- Fix attempt 2 (iptables DNAT to ClusterIP): `iptables -t nat -A PREROUTING -i wlp0s20f3 -p tcp --dport 443 -j DNAT --to-destination 10.43.146.60:443` on the node's WiFi interface — works but doesn't survive reboots and doesn't fix the root cause
- Permanent fix — gratuitous ARP CronJob: a K8s CronJob runs every 5 minutes sending 3 unsolicited ARP packets using Python raw sockets (`AF_PACKET`); `arping` fails with "bind: Address not available" because the VIP isn't assigned to the interface; Python raw sockets bypass this by crafting the Ethernet+ARP frame directly without binding to the source IP
- Python raw ARP packet: `socket.socket(AF_PACKET, SOCK_RAW, htons(0x0806))` bound to the WiFi interface; get the real NIC MAC via `fcntl.ioctl(SIOCGIFHWADDR)`; build the frame manually with `struct.pack`; send 3 times — keeps all WiFi clients' ARP caches fresh for the VIP
- Long-term: for a production setup, MetalLB BGP mode or using `hostNetwork: true` on Traefik to bind directly to the node IP would be more reliable; L2 mode on WiFi is fundamentally fragile because WiFi APs enforce MAC-based addressing
