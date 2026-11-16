---
title: "Getting a Custom Widget onto an iPhone in 2026 is Surprisingly Hard"
date: 2026-11-16T12:00:00+05:30
summary: "A war story: 4 separate blockers getting a Scriptable widget onto an iPhone to display homelab device health — unsigned shortcuts, macOS firewall, MetalLB WiFi segmentation, and base64 corruption in Go source."
draft: false
ai_generated: true
tags: ["ios", "scriptable", "shortcuts", "iphone", "homelab", "debugging", "go"]
categories: []
---

> **Note:** This post was AI-generated from rough notes using the blog generation workflow.

The status-api was running in K3s, `GET /status` returned clean JSON, and I had a Scriptable widget script ready to display it. All that remained was getting the widget code onto the iPhone and wiring up an iOS Shortcut to send push data. Should have been 20 minutes.

It was not 20 minutes.

This post documents the four blockers I hit in sequence, what I tried, and what actually fixed each one. All code lives in [HiteshRepo/awesome-tools](https://github.com/HiteshRepo/awesome-tools) and [HiteshRepo/k3s-homelab](https://github.com/HiteshRepo/k3s-homelab).

---

## Blocker 1: Unsigned Shortcuts

The push flow required an iOS Shortcut running on a schedule: collect battery level, collect WiFi name, POST to `/push`. I wrote a Python script using `plistlib` to generate a `.shortcut` file programmatically — the Shortcuts file format is just a plist with a specific schema.

The plan: generate the plist, AirDrop it to the iPhone, import it. What actually happened:

```
"Importing unsigned shortcut files is not supported."
```

Apple removed the "Allow Untrusted Shortcuts" toggle in iOS 15.4. It used to be in Settings → Shortcuts → Advanced. It's gone. Some posts mention a "Private Sharing" toggle — that's for sharing your own shortcuts publicly, not for importing arbitrary files. Unrelated.

I spent time reverse-engineering the plist format more carefully. Shortcuts uses `WFWorkflowActions` with UUID-based magic variable references, `WFTextTokenString` serialization for interpolated text, and `Aggrandizements` arrays for type coercion. The generated plist was structurally correct. iOS still rejected it. The signing requirement is enforced regardless of format correctness — Apple signs shortcuts through the Shortcuts Gallery, and there's no self-signing mechanism exposed to users.

**Fix:** create the shortcut manually in the Shortcuts app. Three actions:

1. Get Battery Level → store in variable `battery`
2. Get Network Details → Network Name → store in variable `wifi`  
3. Get Contents of URL → Method: POST, URL: `http://192.168.29.146:31376/push`, Body JSON: `{"id": "iphone-11", "battery_percent": [battery variable], "wifi_name": [wifi variable]}`

Three minutes. Done. The programmatic generation was a detour.

---

## Blocker 2: `wifi_connected bool`

The first version of the iOS push payload struct in Go had a boolean for WiFi status:

```go
type IOSPayload struct {
    ID             string  `json:"id"`
    BatteryPercent float64 `json:"battery_percent"`
    WiFiConnected  *bool   `json:"wifi_connected"`
}
```

Shortcuts' "Get Network Details → Network Name" returns the SSID string, not a boolean. If you're connected to "HomeNetwork-5G", that's what the action returns. If you're not connected, it returns an empty string or errors.

The first real push from the iPhone hit the `/push` endpoint and the status-api logged:

```
json: cannot unmarshal string into Go struct field IOSPayload.wifi_connected of type bool
```

**Fix:** change the struct to match what Shortcuts actually sends, and make all payload fields optional pointers so a partial payload doesn't fail to unmarshal:

```go
type IOSPayload struct {
    ID             string   `json:"id"`
    BatteryPercent *float64 `json:"battery_percent,omitempty"`
    WiFiName       *string  `json:"wifi_name,omitempty"`
}
```

The pointer fields mean a payload missing `battery_percent` (say, if you're running an older version of the shortcut) will unmarshal fine — the field is just nil.

---

## Blocker 3: macOS Firewall Blocking the HTTP Server

The Scriptable widget script needed to get onto the iPhone. Scriptable doesn't have a sync mechanism — you either type the code in directly (not viable for 150 lines), or you get the text from somewhere and paste it. The plan: serve `widget.js` over HTTP on the LAN so the iPhone could open it in Safari.

Tried on the MacBook first:

```bash
python3 -m http.server 8888
```

The MacBook's LAN IP is `192.168.29.231`. Opened `http://192.168.29.231:8888/widget.js` on the iPhone. Nothing. The macOS application firewall blocks incoming connections on new ports by default, even for processes bound to 0.0.0.0. The firewall prompt ("Do you want the application python3 to accept incoming network connections?") never appeared — the connection was silently dropped.

Tried from the Lenovo instead. The Lenovo runs Ubuntu and `ufw` was inactive:

```bash
python3 -m http.server 8888
```

Same result from the iPhone. The Lenovo's firewall was inactive but the connection still failed. Eventually confirmed the issue was more fundamental: the iPhone couldn't reach the Lenovo on port 8888 at all, possibly due to something in how the router handles connections to non-standard ports from wireless clients. Never fully diagnosed because the actual fix made it irrelevant.

**Fix:** serve `widget.js` directly from the status-api binary itself, at a `/widget.js` endpoint. No separate HTTP server. No firewall issues. The status-api is already reachable from the iPhone (once I solved Blocker 4). The file is embedded in the binary at compile time with `//go:embed`:

```go
// main.go
//go:embed widget.js
var widgetJS []byte

mux.HandleFunc("/widget.js", func(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Content-Type", "text/plain; charset=utf-8")
    w.Write(widgetJS)
})
```

iPhone opens `http://192.168.29.146:31376/widget.js` in Safari, selects all, copies into Scriptable. Done.

---

## Blocker 4: MetalLB IP Not Reachable from WiFi

With the widget serving problem solved on paper, the iPhone still couldn't reach the status-api. The Traefik IngressRoute exposed it at `https://status-api.lab.hiteshp.in`, but that requires a custom `/etc/hosts` entry the iPhone doesn't have. The MetalLB IP `192.168.29.201` works from the MacBook and Lenovo but the iPhone reports:

```
The Internet connection appears to be offline.
```

MetalLB uses Layer 2 mode — it broadcasts ARP responses to claim the LoadBalancer IP on the local network. This works reliably for wired connections but ARP propagation to wireless segments depends on how the router's internal switch bridges the wired and wireless networks. Some consumer routers forward ARP between all ports; others isolate the wireless bridge in ways that block unsolicited ARP announcements from propagating.

Tried the Traefik IngressRoute URL with the IP directly (bypassing hostname resolution) — same result. The issue was the IP itself, not DNS.

**Fix:** use the NodePort service and the Lenovo's real IP. The Lenovo is on the network as `192.168.29.146` (a DHCP reservation, so it's stable). The status-api Service exposes a NodePort on `31376`. Every device on the LAN can reach `192.168.29.146:31376` directly:

```yaml
# gitops/manifests/status-api/service.yaml
spec:
  type: NodePort
  ports:
    - port: 8080
      nodePort: 31376
```

```
http://192.168.29.146:31376/status    ✅ iPhone
http://192.168.29.146:31376/widget.js ✅ iPhone
http://192.168.29.146:31376/push      ✅ iOS Shortcuts
```

NodePort bypasses MetalLB and Traefik entirely. It's less elegant but it works from every device on the LAN without any configuration.

---

## The Base64 Corruption Trap

Before I switched to `//go:embed`, there was a phase where I tried inlining `widget.js` as a base64 constant in `main.go`. Encode the file, paste the string into source, decode at runtime and serve it.

The status-api compiled and served a response from `/widget.js`. Copied the content into Scriptable. The widget failed to parse. Decoded the constant and compared it character by character to the original file. Found this:

```
// original
async function fetchStatus(url) {

// what was served
anync function fetchStatus(url) {
```

A space appeared inside `async` during the copy-paste of the base64 string into the editor. The string was 2,400 characters long and I pasted it in one shot — the editor wrapped it and introduced whitespace. The base64 decoder doesn't validate structure, so it decoded silently and produced corrupted JavaScript.

`//go:embed widget.js` reads the actual file from disk at compile time. Zero opportunity for copy-paste corruption, zero runtime encoding/decoding, file stays as a file and is easy to edit.

---

## What Finally Worked

The working setup end-to-end:

1. `widget.js` is embedded in the status-api binary with `//go:embed widget.js` and served at `GET /widget.js` as `text/plain`
2. The status-api is exposed on NodePort `31376` via the Lenovo's real LAN IP `192.168.29.146`
3. On the iPhone: open `http://192.168.29.146:31376/widget.js` in Safari, select all, copy, open Scriptable, create a new script, paste
4. The widget fetches from `http://192.168.29.146:31376/status` — same host, same NodePort
5. Add to home screen: long-press → Scriptable → select the script → Done

The iOS Shortcut for push data runs hourly via Shortcuts automation (Automation → New Automation → Time of Day → Hourly → turn off "Ask Before Running"). Three actions: Get Battery Level, Get Network Details (Network Name), Get Contents of URL with POST to `/push`.

---

## Lessons

A few patterns that apply beyond this specific project:

**For local-network tools, skip HTTPS and the reverse proxy.** Traefik + cert-manager + MetalLB is the right stack for services you access from your laptop, but it adds layers that actively hurt for iPhone use. Use the host's real LAN IP and a NodePort. It's not elegant, but it's reliably reachable from every device.

**`//go:embed` is the correct way to bundle static files in Go.** Not base64 constants, not `ioutil.ReadFile` with a relative path, not a separate file server. The file is part of the binary, the binary is what gets deployed, and the binary serves the file. Simple.

**iOS Shortcuts manual creation beats programmatic import for personal automation.** The Apple signing requirement exists, it's not going away, and three manual actions take less time than debugging a plist generator. Save the automation engineering effort for the server side.

**Add structured error logging to background goroutines before you ship.** A goroutine that fails silently is worse than one that crashes — at least a crash is visible. Every background worker in the status-api now logs the device ID and error on every failed poll. Stale entries in the status response always come with an explanation in the logs.
