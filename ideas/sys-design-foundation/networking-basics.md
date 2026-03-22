## Top level view
- tcp/ip
    - tcp: it is like reliable delivery guy that ensures data arrives in order
    - ip: address of the device on the internet
- dns: keeps a map of domain and its corresponding IP address
    - DNS Lookup Works (Step by step):
        - You type: google.com
        - Browser checks its own cache → Not found
        - Asks your OS cache        → Not found
        - Asks your Router          → Not found
        - Asks ISP's DNS Server     → Not found
        - Asks Root DNS Server      → "Try .com servers"
        - Asks .com DNS Server      → "Try Google's DNS"
        - Asks Google's DNS Server  → "It's 142.250.80.46!" ✅
        - Result is cached at every step for next time
    - This whole process takes milliseconds.
- HTTP is the language your browser and the server use to talk, once TCP gives you a connection and DNS gives you the address.
    - HTTP methods and HTTP status define the protocol
    - HTTPS adds a TLS/SSL layer that encrypts the conversation so nobody can eavesdrop.

## Putting It All Together

1. DNS Lookup
   → google.com resolved to 142.250.80.46

2. TCP Handshake
   → Your browser and Google's server establish a connection

3. TLS Handshake (because it's HTTPS)
   → They agree on encryption keys, secure the channel

4. HTTP Request
   → Browser sends: GET / HTTP/1.1

5. HTTP Response
   → Google sends back the HTML page

6. Browser renders the page 🎉

## Deep dive

### The 3-Way Handshake (Connection Setup)

Before any data flows, client and server must agree to talk.

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

What are SEQ and ACK numbers?
- SEQ (Sequence Number) — "This is packet #X I'm sending"
- ACK (Acknowledge Number) — "I received up to X, send me X+1 next"

Your data doesn't travel as one big blob. It gets chopped into small packets — typically 1500 bytes each (called MTU - Maximum Transmission Unit).

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

### Anatomy of a TCP Packet

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

Each packet can take a completely different route to the destination.
They may arrive out of order. TCP handles this.

```
[Packet 1] ——→ Router A ——→ Router C ——→ Server
[Packet 2] ——→ Router B ——→ Router D ——→ Server
[Packet 3] ——→ Router A ——→ Router D ——→ Server
```

The receiving side maintains a buffer — a waiting room for packets.

```
PACKETS ARRIVING (out of order):

  Arrives: Packet 3  → Buffer: [_, _, ✅]   "Waiting for 1 and 2"
  Arrives: Packet 1  → Buffer: [✅, _, ✅]  "Waiting for 2"
  Arrives: Packet 2  → Buffer: [✅, ✅, ✅] "All here!"

REASSEMBLE in sequence order → Original data restored ✅
```


This is where TCP really shines. It guarantees delivery.

Two mechanisms:
- Mechanism 1 — ACK Timeout: Every packet sent starts a timer. If no ACK comes back before the timer expires → packet is assumed lost → resend.

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

- Mechanism 2 — Triple Duplicate ACK (Faster!): If packets 1, 3, 4, 5 arrive but packet 2 is missing — the receiver keeps sending ACK for 1, hinting that 2 is missing.


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

TCP uses a Window Size — the receiver tells the sender how much it can handle at once.

```
Server → Client: "My window is 3 packets"
                  (I can handle 3 at a time)

[Packet 1] [Packet 2] [Packet 3] ——→  ✅ Window full, STOP

Client processes them...

Client → Server: "Window is now 3 again, send more"

[Packet 4] [Packet 5] [Packet 6] ——→  ✅ Continue
```

Closing a TCP connection is more careful than opening one — either side can finish sending independently.

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

## Other Data Transmission Mechanisms

### UDP — The "Fire and Forget" Protocol

UDP (User Datagram Protocol) is TCP's simpler, faster cousin. It sends data without any of TCP's guarantees.

UDP Packet Structure (Much simpler than TCP):

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

No sequence numbers. No ACKs. No retransmit. Just raw data.

TCP vs UDP — Head to Head

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

When to use TCP:
- Web browsing (HTTP)
- File downloads
- Emails
- Banking transactions

> A single wrong byte in a bank transfer = disaster. Use TCP.

When to use UDP:
- Video calls (Zoom, Meet)
- Live streaming (YouTube Live, Twitch)
- Online gaming
- DNS lookups
- VoIP (phone over internet)

> In a video call, if one frame drops, you don't want TCP to pause everything and wait for it. A slightly glitchy frame is better than a frozen call. Use UDP.

Pure UDP is unreliable — but applications can build their own reliability on top of UDP when they need a balance of speed + some guarantees.

> 🎮 Games use UDP but implement their own "important packet" tracking — only critical events (player death, score) get retried. Non-critical ones (dust particle animation) are dropped guilt-free.

```
Application Layer:  Custom retry logic  ← You build this
      ↓
UDP Layer:          Fast, no overhead   ← Protocol handles this
      ↓
Network Layer:      Raw delivery        ← Network handles this
```

### QUIC — The Modern Upgrade

QUIC (Quick UDP Internet Connections) was built by Google and is the foundation of HTTP/3 — the latest version of the web protocol.

> 🚗 TCP is an old highway with tolls at every junction. QUIC is a new expressway — built on UDP but with smart lanes, faster entry, and no unnecessary stops.

Problems QUIC solves:
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

> Used by: YouTube, Google Search, Gmail, Cloudflare

### WebSockets — Persistent Two-Way Connection

HTTP is one-way — client asks, server responds, done. WebSockets keep the connection permanently open for real-time back-and-forth.

> ☎️ HTTP is like texting — you send a message, wait for a reply, conversation ends. WebSocket is like a phone call — line stays open, both sides talk freely anytime.

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

Used by: WhatsApp Web, Slack, live sports scores, stock tickers, multiplayer games, collaborative docs (Google Docs)

### Server-Sent Events (SSE) — One-Way Live Stream

Like WebSockets, but only server → client. The client opens a connection once and the server keeps pushing updates.

> 📺 Like subscribing to a TV channel. You tune in once, and the channel keeps broadcasting to you. You don't broadcast back.

```
Client → "Subscribe to updates"  → Server
         (connection stays open)

Server → Client  "Update 1"
Server → Client  "Update 2"
Server → Client  "Update 3"
         ... server pushes, client only listens
```

Used by: Live news feeds, ChatGPT's streaming responses, live dashboards, notifications

### gRPC — High Performance Service Communication

gRPC is a protocol built by Google for microservices talking to each other — not browsers. It uses HTTP/2 under the hood and sends data in binary instead of text (JSON).

> 📦 REST/JSON is like sending a letter written in plain English. gRPC is like sending a compressed zip file — smaller, faster, but needs a decoder to read.

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

Used by: Internal microservice communication at Netflix, Uber, Google

### MQTT — Lightweight IoT Protocol

Built for devices with very low power and bandwidth — like sensors, smartwatches, smart bulbs.

> 📡 Like a radio broadcast tower. Devices subscribe to a "channel" (topic). When something is published to that channel, all subscribers receive it instantly — even if they have a weak signal.

```
Temperature Sensor  →  [Publish] "temp/room1" = 24°C
                              ↓
Smart Thermostat    ←  [Subscribed to "temp/room1"] gets 24°C
Mobile App          ←  [Subscribed to "temp/room1"] gets 24°C
```

Used by: Smart home devices, hospital monitoring, industrial IoT

### The bigger picture

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

### The Transmission Spectrum

```
RELIABILITY  ←─────────────────────────────→  SPEED

    TCP          QUIC        WebSocket        UDP
  [■■■■■■■]   [■■■■■■]      [■■■■■]        [■■■]
  Safest       Fast +        Persistent      Fastest
               Reliable      2-way           Raw
```