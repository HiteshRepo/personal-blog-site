# TCP/IP, DNS, and Data Transmission Protocols Explained

- type: technical
- tags: tcp-ip, networking, dns, udp, websockets, grpc, http, protocols
- TCP is a reliable delivery protocol that ensures data arrives in order; IP is the addressing system identifying devices on the internet.
- DNS resolves human-readable domain names to IP addresses through an 8-step lookup chain: browser cache → OS cache → router → ISP DNS → root DNS → TLD DNS → authoritative DNS → result cached at every step.
- The full flow of a browser request involves five sequential phases: DNS lookup, TCP handshake, TLS handshake, HTTP request, and HTTP response.
- TCP establishes connections via a 3-way handshake: SYN (seq=100) → SYN-ACK (seq=200, ack=101) → ACK (ack=201).
- SEQ numbers identify a packet's position in the stream; ACK numbers confirm receipt and request the next expected byte (ACK = last received + 1).
- Large data is segmented into packets typically 1500 bytes each (MTU), each carrying a header with source/destination port, sequence number, ACK number, flags, window size, and checksum.
- Individual packets can take different routes through the network and arrive out of order; TCP reassembles them using sequence numbers and a receive buffer.
- TCP guarantees delivery via two mechanisms: ACK timeout (timer per packet, resend on expiry) and triple duplicate ACK fast retransmit (3× same ACK signals a missing packet without waiting for timeout).
- TCP flow control uses a Window Size field — the receiver advertises how many packets it can buffer at once, preventing the sender from overwhelming it.
- TCP closes connections with a 4-step FIN handshake (FIN → ACK → FIN → ACK), allowing each side to finish sending independently before closing.
- UDP omits connection setup, sequence numbers, ACKs, and retransmits entirely; its header is only 8 bytes vs TCP's 20–60 bytes, making it significantly faster.
- TCP is preferred when correctness is critical (web, file transfer, email, banking); UDP is preferred when speed matters more than completeness (video calls, live streaming, gaming, DNS, VoIP).
- Applications can build selective reliability on top of UDP — for example, games retry only critical events (player death, score) and silently drop non-critical ones (particle animations).
- QUIC (HTTP/3, built by Google) runs over UDP and solves three TCP problems: head-of-line blocking (only the affected stream waits, not all), slow handshake (1 round trip vs 2–3 for TCP+TLS), and connection migration (uses Connection ID so switching WiFi to mobile data doesn't drop the connection).
- WebSockets upgrade an HTTP connection into a persistent, full-duplex channel — both client and server can send messages at any time without re-requesting; used by Slack, WhatsApp Web, Google Docs, and multiplayer games.
- Server-Sent Events (SSE) provide a one-way persistent stream from server to client over standard HTTP — the client subscribes once and receives a continuous push; used by ChatGPT streaming responses and live dashboards.
- gRPC (built by Google, runs on HTTP/2) serialises data as binary Protobuf instead of JSON, producing ~3× smaller payloads that are faster to encode/decode but not human-readable; used for internal microservice communication at Netflix, Uber, and Google.
- MQTT is a publish/subscribe protocol designed for low-power, low-bandwidth IoT devices; sensors publish to named topics and all subscribers receive updates instantly, used in smart home, hospital monitoring, and industrial IoT.
- Protocol selection decision table: reliable web requests → TCP/HTTP; loss-tolerant speed → UDP; modern web → QUIC; real-time bidirectional chat → WebSocket; server-to-client live updates → SSE; microservice RPC → gRPC; IoT/low-power → MQTT.
- The reliability-to-speed spectrum ranks protocols: TCP (safest) → QUIC (fast + reliable) → WebSocket (persistent two-way) → UDP (fastest, raw).

## Raw Diagrams

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

```
[Packet 1] ——→ Router A ——→ Router C ——→ Server
[Packet 2] ——→ Router B ——→ Router D ——→ Server
[Packet 3] ——→ Router A ——→ Router D ——→ Server
```

```
PACKETS ARRIVING (out of order):

  Arrives: Packet 3  → Buffer: [_, _, ✅]   "Waiting for 1 and 2"
  Arrives: Packet 1  → Buffer: [✅, _, ✅]  "Waiting for 2"
  Arrives: Packet 2  → Buffer: [✅, ✅, ✅] "All here!"

REASSEMBLE in sequence order → Original data restored ✅
```

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

```
Server → Client: "My window is 3 packets"
                  (I can handle 3 at a time)

[Packet 1] [Packet 2] [Packet 3] ——→  ✅ Window full, STOP

Client processes them...

Client → Server: "Window is now 3 again, send more"

[Packet 4] [Packet 5] [Packet 6] ——→  ✅ Continue
```

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

```
Application Layer:  Custom retry logic  ← You build this
      ↓
UDP Layer:          Fast, no overhead   ← Protocol handles this
      ↓
Network Layer:      Raw delivery        ← Network handles this
```

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

```
Client → "Subscribe to updates"  → Server
         (connection stays open)

Server → Client  "Update 1"
Server → Client  "Update 2"
Server → Client  "Update 3"
         ... server pushes, client only listens
```

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

```
Temperature Sensor  →  [Publish] "temp/room1" = 24°C
                              ↓
Smart Thermostat    ←  [Subscribed to "temp/room1"] gets 24°C
Mobile App          ←  [Subscribed to "temp/room1"] gets 24°C
```

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

```
RELIABILITY  ←─────────────────────────────→  SPEED

    TCP          QUIC        WebSocket        UDP
  [■■■■■■■]   [■■■■■■]      [■■■■■]        [■■■]
  Safest       Fast +        Persistent      Fastest
               Reliable      2-way           Raw
```
