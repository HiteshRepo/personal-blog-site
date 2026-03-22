---
title: "TCP/IP, DNS, and Data Transmission Protocols Explained"
date: 2026-03-22T17:22:27-07:00
summary: "A practical, code-illustrated guide to how TCP/IP, DNS, and modern data transmission protocols work under the hood — from handshakes and packet routing to WebSockets, gRPC, and QUIC."
draft: false
ai_generated: true
tags: ["tcp-ip", "networking", "dns", "udp", "websockets", "grpc", "http", "protocols"]
categories: []
---

> **Note:** This post was AI-generated from rough notes using the blog generation workflow.

Every time you open a browser and hit Enter, a surprisingly deep stack of protocols kicks into motion. Most developers interact with this stack indirectly — through fetch(), axios, or WebSocket — but understanding what's actually happening underneath makes you a better engineer. Let's walk through it.

---

## IP and TCP: The Foundation

**IP (Internet Protocol)** is the addressing system. Every device on the internet has an IP address, and IP is responsible for routing packets toward the right destination.

**TCP (Transmission Control Protocol)** sits on top of IP and handles *reliable, ordered delivery*. IP gets the packet roughly where it needs to go; TCP makes sure it actually arrives, in order, without corruption.

Together, they handle the majority of internet traffic — but they're not always the right tool. More on that shortly.

---

## DNS: Turning Names Into Addresses

Before any data moves, your browser needs to figure out *where* to send it. You type `github.com` — the network needs an IP address.

DNS (Domain Name System) resolves this through an 8-step lookup chain:

1. **Browser cache** — Did we already look this up recently?
2. **OS cache** — Check `/etc/hosts` and the system resolver cache
3. **Router** — Your local router may cache DNS responses
4. **ISP DNS** — Your internet provider's resolver
5. **Root DNS** — Knows where to find `.com`, `.org`, `.io` servers
6. **TLD DNS** — The `.com` nameserver knows where `github.com` lives
7. **Authoritative DNS** — GitHub's own nameserver returns the actual IP
8. **Result cached** — Every layer caches the result for future lookups

This sounds slow, but in practice it's nearly instant. Caching at every layer means most lookups never leave your machine.

---

## The Full Browser Request Flow

Once DNS resolves the IP, a browser request goes through five sequential phases:

1. **DNS lookup** (covered above)
2. **TCP handshake** — establish a reliable connection
3. **TLS handshake** — negotiate encryption (for HTTPS)
4. **HTTP request** — send your actual GET/POST
5. **HTTP response** — receive the data

Let's dig into TCP specifically.

---

## The TCP 3-Way Handshake

Before a single byte of your HTTP request is sent, TCP establishes a connection:

```
CLIENT                                SERVER
  |                                      |
  |  ——— SYN (seq=100) ————————————→    |   "I want to connect.
  |                                      |    My sequence starts at 100"
  |                                      |
  |  ←—— SYN-ACK (seq=200, ack=101) —— |   "OK! My sequence starts at 200.
  |                                      |    I got your 100, expecting 101 next"
  |                                      |
  |  ——— ACK (ack=201) ————————————→   |   "Got it! Expecting 201 from you"
  |                                      |
  |        CONNECTION ESTABLISHED ✅     |
```

**SEQ numbers** identify a packet's position in the byte stream. **ACK numbers** confirm receipt — always `last received byte + 1`, meaning "I got everything up to here, now send me this."

---

## Packet Segmentation

TCP doesn't send your data as one blob. It breaks it into packets, typically 1500 bytes each (the standard MTU — Maximum Transmission Unit):

```
Original Data:  "Hello, this is a very long message..."  (5000 bytes)

           ┌─────────────────────────────────┐
           │         TCP breaks it up        │
           └─────────────────────────────────┘

Packet 1:  [Header | seq=0    | "Hello, th"]   (1500 bytes)
Packet 2:  [Header | seq=1500 | "is is a v"]   (1500 bytes)
Packet 3:  [Header | seq=3000 | "ery long "]   (1500 bytes)
Packet 4:  [Header | seq=4500 | "message…" ]   (500 bytes)
```

Each packet carries a header with everything needed to reconstruct the stream:

```
┌──────────────────────────────────────────┐
│              TCP PACKET                  │
├──────────────────────────────────────────┤
│  Source Port      │  Destination Port    │  ← Who's talking to whom
├──────────────────────────────────────────┤
│         Sequence Number                  │  ← This packet's position
├──────────────────────────────────────────┤
│         Acknowledgment Number            │  ← What I've received so far
├──────────────────────────────────────────┤
│  Flags (SYN, ACK, FIN...)               │  ← What type of message
├──────────────────────────────────────────┤
│  Window Size                            │  ← How much data I can handle
├──────────────────────────────────────────┤
│  Checksum                               │  ← Error detection
├──────────────────────────────────────────┤
│                                          │
│              DATA PAYLOAD                │
│                                          │
└──────────────────────────────────────────┘
```

---

## Packets Take Different Routes

Individual packets aren't guaranteed to follow the same path through the network:

```
[Packet 1] ——→ Router A ——→ Router C ——→ Server
[Packet 2] ——→ Router B ——→ Router D ——→ Server
[Packet 3] ——→ Router A ——→ Router D ——→ Server
```

They can arrive out of order. TCP handles this with a receive buffer and sequence numbers:

```
PACKETS ARRIVING (out of order):

  Arrives: Packet 3  → Buffer: [_, _, ✅]   "Waiting for 1 and 2"
  Arrives: Packet 1  → Buffer: [✅, _, ✅]  "Waiting for 2"
  Arrives: Packet 2  → Buffer: [✅, ✅, ✅] "All here!"

REASSEMBLE in sequence order → Original data restored ✅
```

---

## Guaranteed Delivery: Two Mechanisms

### ACK Timeout

Every packet starts a timer. If no ACK arrives before the timer expires, the packet is resent:

```
CLIENT                              SERVER
  |                                    |
  |  ——— Packet 2 (seq=1500) ——→     |
  |       ⏱️ Timer starts...           |
  |                                    |   ❌ Packet lost in network
  |       ⏱️ Timer EXPIRES!            |
  |                                    |
  |  ——— Packet 2 RESENT ————→       |   📦 Arrives this time!
  |                                    |
  |  ←—— ACK (ack=3000) ————————     |   ✅ "Got it, send from 3000"
```

### Fast Retransmit (Triple Duplicate ACK)

Waiting for a timeout is slow. If the receiver gets three identical ACKs, it signals a missing packet immediately — no waiting:

```
CLIENT                              SERVER
  |                                    |
  |  ——→ Packet 1 ——→               |  ✅ Received
  |  ——→ Packet 2 ——→               |  ❌ Lost!
  |  ——→ Packet 3 ——→               |  ✅ Received (but out of order)
  |  ——→ Packet 4 ——→               |  ✅ Received (but out of order)
  |  ——→ Packet 5 ——→               |  ✅ Received (but out of order)
  |                                    |
  |  ←—— ACK 1 ————————————————     |  "Still waiting for packet 2!"
  |  ←—— ACK 1 ————————————————     |  "Still waiting for packet 2!"
  |  ←—— ACK 1 ————————————————     |  "STILL waiting for packet 2!"
  |                                    |
  |  3 duplicate ACKs = FAST RETRANSMIT
  |  ——→ Packet 2 RESENT ——→        |  ✅ Now buffer is complete!
  |                                    |
  |  ←—— ACK 6 ————————————————     |  "Got everything up to 5, send 6"
```

### Flow Control: Window Size

The receiver tells the sender how much data it can buffer at once — preventing the sender from overwhelming it:

```
Server → Client: "My window is 3 packets"
                  (I can handle 3 at a time)

[Packet 1] [Packet 2] [Packet 3] ——→  ✅ Window full, STOP

Client processes them...

Client → Server: "Window is now 3 again, send more"

[Packet 4] [Packet 5] [Packet 6] ——→  ✅ Continue
```

---

## Closing the Connection: 4-Way FIN Handshake

TCP closes gracefully, letting each side finish independently:

```
CLIENT                              SERVER
  |                                    |
  |  ——— FIN ——————————————→         |  "I'm done sending"
  |  ←—— ACK ——————————————          |  "OK, got it"
  |                                    |   (server may still be sending...)
  |  ←—— FIN ——————————————          |  "I'm done too"
  |  ——— ACK ——————————————→         |  "OK, goodbye!"
  |                                    |
  |         CONNECTION CLOSED 👋       |
```

---

## UDP: When Speed Beats Reliability

UDP skips all of that — no handshake, no ACKs, no retransmits, no ordering. Its entire header is 8 bytes vs TCP's 20–60:

```
┌──────────────────────────────────────┐
│             UDP PACKET               │
├──────────────────────────────────────┤
│  Source Port   │  Destination Port   │
├──────────────────────────────────────┤
│  Length        │  Checksum           │
├──────────────────────────────────────┤
│                                      │
│           DATA PAYLOAD               │
│                                      │
└──────────────────────────────────────┘
```

```
Feature              TCP                  UDP
─────────────────────────────────────────────────────
Connection           Handshake required   No handshake
Delivery guarantee   ✅ Yes               ❌ No
Order guarantee      ✅ Yes               ❌ No
Lost packet retry    ✅ Yes               ❌ No
Speed                🐢 Slower            ⚡ Faster
Header size          20-60 bytes          8 bytes
Use case             Accuracy matters     Speed matters
```

**Use TCP when** correctness is non-negotiable: web requests, file transfer, email, banking.

**Use UDP when** speed matters more than completeness: video calls, live streaming, gaming, DNS, VoIP.

### Building Selective Reliability on UDP

Games often do this — retry only what matters, drop the rest:

```
Application Layer:  Custom retry logic  ← You build this
      ↓
UDP Layer:          Fast, no overhead   ← Protocol handles this
      ↓
Network Layer:      Raw delivery        ← Network handles this
```

A player death event gets retried. A particle animation that already played? Silently dropped.

---

## QUIC: TCP's Evolved Replacement

QUIC (used by HTTP/3, built by Google) runs over UDP and solves three real TCP problems:

```
TCP Problem 1: Head-of-Line Blocking
──────────────────────────────────────
TCP: Packet 2 lost → EVERYTHING waits for packet 2
     [1 ✅] [2 ❌ waiting...] [3 🔒] [4 🔒] [5 🔒]

QUIC: Packet 2 lost → Only stream 2 waits, rest continue
     [Stream 1 ✅] [Stream 2 ❌ waiting] [Stream 3 ✅]


TCP Problem 2: Slow Handshake
──────────────────────────────────────
TCP + TLS:   3-way handshake + TLS handshake = 2-3 round trips
QUIC:        Combines both = 1 round trip (or even 0 for returning users!)


TCP Problem 3: Connection breaks on network switch
──────────────────────────────────────
TCP:   Switch WiFi → Mobile data = connection drops, restart
QUIC:  Switch WiFi → Mobile data = connection continues ✅
       (uses Connection ID instead of IP, so IP change doesn't matter)
```

---

## WebSockets, SSE, gRPC, and MQTT

### WebSockets — Persistent Two-Way Channel

Standard HTTP is request/response — the client always asks first. WebSockets flip that model:

```
Normal HTTP:
Client → "Give me updates"    → Server
Client ← "Here are updates"   ← Server
         (connection closes)
Client → "Give me updates"    → Server   (must ask again!)
Client ← "Here are updates"   ← Server

WebSocket:
Client ↔ Server   [CONNECTION STAYS OPEN]
         Server → Client  "New message!"
         Server → Client  "User X joined"
         Client → Server  "I typed something"
         Server → Client  "Another update"
                  ... forever until closed
```

Used by: Slack, WhatsApp Web, Google Docs, multiplayer games.

```javascript
const ws = new WebSocket('wss://example.com/socket');
ws.onmessage = (event) => console.log('Received:', event.data);
ws.send('Hello server!');
```

### SSE — One-Way Server Push

Server-Sent Events are simpler than WebSockets — the client subscribes once, the server streams forever:

```
Client → "Subscribe to updates"  → Server
         (connection stays open)

Server → Client  "Update 1"
Server → Client  "Update 2"
Server → Client  "Update 3"
         ... server pushes, client only listens
```

Used by: ChatGPT streaming responses, live dashboards.

```javascript
const es = new EventSource('/stream');
es.onmessage = (e) => console.log(e.data);
```

### gRPC — Fast Binary RPC

gRPC (HTTP/2, built by Google) uses Protobuf instead of JSON — roughly 3× smaller payloads:

```
REST API (JSON):
{
  "userId": 123,
  "name": "Rohit",
  "email": "rohit@gmail.com"
}
→ Human readable, but verbose (lots of bytes)

gRPC (Binary Protobuf):
→ 0x7B 0x22 ...  (binary encoded, ~3x smaller)
→ Not human readable, but blazing fast
```

Used internally at Netflix, Uber, and Google for microservice communication where latency and throughput matter.

### MQTT — IoT Pub/Sub

MQTT is designed for constrained devices — low power, low bandwidth, unreliable networks:

```
Temperature Sensor  →  [Publish] "temp/room1" = 24°C
                              ↓
Smart Thermostat    ←  [Subscribed to "temp/room1"] gets 24°C
Mobile App          ←  [Subscribed to "temp/room1"] gets 24°C
```

Used in smart homes, hospital monitoring, and industrial IoT.

---

## Protocol Decision Table

```
Need                          Use
──────────────────────────────────────────────────────
Reliable web requests         TCP / HTTP
Fast, loss-tolerant           UDP
Modern web (HTTP/3)           QUIC
Real-time two-way chat        WebSocket
Server pushing live updates   SSE (Server-Sent Events)
Microservice communication    gRPC
IoT / low-power devices       MQTT
Video/voice calls             UDP (or QUIC)
File transfer                 TCP
```

And if you're thinking in terms of the reliability/speed tradeoff:

```
RELIABILITY  ←─────────────────────────────→  SPEED

    TCP          QUIC        WebSocket        UDP
  [■■■■■■■]   [■■■■■■]      [■■■■■]        [■■■]
  Safest       Fast +        Persistent      Fastest
               Reliable      2-way           Raw
```

---

## Wrapping Up

The internet is a layered system, and each protocol exists because of a specific tradeoff. TCP gives you reliability at the cost of overhead. UDP gives you speed at the cost of guarantees. QUIC tries to get you both. WebSockets, SSE, gRPC, and MQTT are all specialized tools built on top of these fundamentals for specific problems.

Next time you reach for a technology — WebSocket vs SSE, REST vs gRPC, HTTP/2 vs HTTP/3 — you now have the mental model to make that call based on what's actually happening at the wire level.
