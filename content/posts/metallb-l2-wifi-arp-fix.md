---
title: "Why MetalLB L2 Mode Breaks on WiFi (And How to Fix It Permanently)"
date: 2026-11-20T14:00:00+05:30
summary: "MetalLB's L2 mode works fine on wired networks but silently breaks TCP on WiFi after a speaker restart. Here's why ICMP still works, what the AP is actually doing to your gratuitous ARPs, and a permanent fix using a Python raw-socket CronJob."
draft: false
ai_generated: true
tags: ["metallb", "kubernetes", "networking", "arp", "homelab", "k3s", "wifi", "python"]
categories: []
---

> **Note:** This post was AI-generated from rough notes using the blog generation workflow.

The symptom is maddening because it looks like a networking problem but doesn't behave like one. `ping 192.168.29.200` returns replies without complaint. But `curl https://immich.lab.hiteshp.in` times out. Same IP. Same machine. One protocol works, the other doesn't.

---

## What MetalLB L2 Mode Actually Does

In L2 mode, MetalLB claims ownership of a virtual IP (VIP) on your LAN by responding to ARP requests for that IP. When a client asks "who has 192.168.29.200?", the MetalLB speaker pod answers — but critically, it answers with a MAC address that is **not** the real NIC's MAC.

On my node, the real WiFi NIC MAC is `40:74:e0:0c:c7:c2`. MetalLB uses `7a:10:c9:29:28:da`. Those are different MACs.

Ethernet switches learn MAC-to-port mappings dynamically and work fine with this. WiFi APs don't. An AP only forwards unicast frames to associated client MACs — MACs that have gone through the 802.11 association handshake. MetalLB's VIP MAC has never associated with the AP. Frames addressed to it get dropped.

---

## Why ICMP Works But TCP Doesn't

After a MetalLB speaker restart, the speaker sends a gratuitous ARP. Clients learn the VIP→MAC mapping. But frames still can't reach the node because the AP drops frames addressed to the virtual MAC.

ICMP ping gets through because the kernel responds to it early in the network stack before iptables/kube-proxy gets involved. The response travels node→client, which works fine.

TCP traffic goes through the full kube-proxy iptables chain:

```
KUBE-SERVICES → KUBE-EXT-<hash> → KUBE-SVC-<hash> → KUBE-SEP-<hash>
```

A packet for `192.168.29.200:443` gets DNAT'd to Traefik's pod IP. But the packet from your WiFi laptop never arrives — the AP drops it at layer 2 before TCP even gets a chance.

---

## The Cosmetic Red Herring: FRR Errors

The MetalLB speaker logs are full of:

```
time="2026-11-15T10:23:41Z" level=error msg="permission denied" component=frr
```

Completely harmless. FRR is the BGP daemon bundled in MetalLB's speaker image. I'm running L2 mode. These errors exist even when everything is working. Ignore them.

---

## Fix Attempt 1: Restart the Speaker

```bash
kubectl delete pod -n metallb-system -l component=speaker
```

The pod self-heals in ~20 seconds and sends a fresh gratuitous ARP. This works temporarily. It breaks again after the next speaker restart (node reboot, pod eviction, upgrade).

---

## The Permanent Fix: Gratuitous ARP CronJob

The real problem: MetalLB only sends gratuitous ARPs on startup. WiFi clients lose the ARP cache entry after a few minutes. Nobody is refreshing it.

The fix: send gratuitous ARPs every 5 minutes.

`arping` doesn't work here:

```bash
arping -c 3 -A -I wlp0s20f3 192.168.29.200
# bind: Address not available
```

`arping` requires the IP to be assigned to the interface. MetalLB manages the VIP, not the OS. The solution is Python raw sockets (`AF_PACKET + SOCK_RAW`) which let you craft raw Ethernet frames without the IP being locally assigned:

```python
import socket, struct, fcntl

IFACE = "wlp0s20f3"
VIP   = "192.168.29.200"

def get_mac(iface):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    info = fcntl.ioctl(s.fileno(), 0x8927, struct.pack("256s", iface[:15].encode()))
    return info[18:24]

def send_gratuitous_arp(iface, vip):
    mac      = get_mac(iface)
    broadcast = b"\xff\xff\xff\xff\xff\xff"
    sender_ip = socket.inet_aton(vip)

    # Ethernet header + ARP payload
    eth = broadcast + mac + b"\x08\x06"
    arp = (b"\x00\x01"   # htype: Ethernet
         + b"\x08\x00"   # ptype: IPv4
         + b"\x06\x04"   # hlen/plen
         + b"\x00\x02"   # op: reply (gratuitous)
         + mac + sender_ip
         + broadcast + sender_ip)

    with socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x0806)) as s:
        s.bind((iface, 0))
        for _ in range(3):
            s.send(eth + arp)
            print(f"Sent gratuitous ARP for {vip} on {iface}")

send_gratuitous_arp(IFACE, VIP)
```

The key detail: `get_mac()` reads the real NIC's hardware MAC via `SIOCGIFHWADDR`. The gratuitous ARP announces "VIP `192.168.29.200` is at MAC `40:74:e0:0c:c7:c2`" — using the real WiFi NIC MAC. The AP knows that MAC is an associated client and forwards frames to it correctly.

---

## The CronJob Manifest

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: gratuitous-arp
  namespace: metallb-system
spec:
  schedule: "*/5 * * * *"
  concurrencyPolicy: Forbid
  jobTemplate:
    spec:
      template:
        spec:
          hostNetwork: true
          restartPolicy: OnFailure
          containers:
            - name: garp
              image: python:3.12-alpine
              command: ["python3", "-c", "<script inline>"]
              securityContext:
                privileged: true
```

`hostNetwork: true` gives access to physical interfaces. `privileged: true` is required for `AF_PACKET` socket creation. `concurrencyPolicy: Forbid` prevents overlapping runs.

The full manifest is in [HiteshRepo/k3s-homelab](https://github.com/HiteshRepo/k3s-homelab) under `gitops/manifests/metallb-config/gratuitous-arp.yaml`.

---

## The Core Insight

MetalLB L2 mode is designed for wired networks where switches handle unknown MACs via flooding. WiFi APs only forward to associated clients — MetalLB's virtual MAC is not an associated client, so frames get dropped silently.

The fix is to announce the VIP using the real NIC MAC instead of a virtual one. This requires raw sockets because `arping` only works with locally-assigned IPs. Once you announce with the real MAC, the AP forwards correctly and TCP works.

If you're running MetalLB on a WiFi-connected node and experiencing intermittent TCP breakage after restarts, this is your problem.
