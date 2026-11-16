---
title: "Track Every Device in Your Homelab with One JSON Endpoint"
date: 2026-11-16T12:00:00+05:30
summary: "A practical guide to building a self-updating device health registry for your homelab: a YAML file in Git, a Go aggregator in K3s, and three widget surfaces — iPhone, macOS menu bar, and Linux terminal."
draft: false
ai_generated: true
tags: ["homelab", "gitops", "golang", "k3s", "ios", "scriptable", "xbar", "argocd", "self-hosted", "kubernetes"]
categories: []
---

> **Note:** This post was AI-generated from rough notes using the blog generation workflow.

By the end of this guide you'll have a single JSON endpoint that knows the health of every device in your homelab — cluster nodes, laptops, iPhones — and three lightweight surfaces to view it from: a Scriptable widget on your iPhone home screen, an xbar plugin in the Mac menu bar, and a one-liner alias in your Linux terminal.

```bash
curl http://192.168.29.146:31376/status
```

```json
{
  "devices": [
    {"id": "legion", "name": "Legion 5i (K8s node)", "status": "healthy", "cpu_percent": 12.4, "mem_percent": 61.2},
    {"id": "legion-host", "name": "Legion 5i (Host OS)", "status": "healthy", "cpu_percent": 8.1, "mem_percent": 44.0, "uptime_hours": 72.3},
    {"id": "macbook-work", "name": "MacBook Work", "status": "healthy", "cpu_percent": 34.2, "mem_percent": 78.9, "battery_percent": 87},
    {"id": "iphone-11", "name": "iPhone 11", "status": "healthy", "battery_percent": 62, "wifi_name": "HomeNetwork-5G"},
    {"id": "legion-gpu", "name": "Legion GPU", "status": "healthy", "gpu_util_percent": 0}
  ],
  "updated_at": "2026-11-16T10:22:01+05:30"
}
```

All source code is in [HiteshRepo/k3s-homelab](https://github.com/HiteshRepo/k3s-homelab) and [HiteshRepo/awesome-tools](https://github.com/HiteshRepo/awesome-tools).

---

## Step 1: Define the Device Registry

The fleet is defined in a single YAML file at `gitops/manifests/status-api/config/devices.yaml` in the [k3s-homelab](https://github.com/HiteshRepo/k3s-homelab) repository. This file is the source of truth — everything else is derived from it.

```yaml
devices:
  - id: legion
    name: Legion 5i (K8s node)
    kind: k8s-node
    ownership: personal

  - id: legion-host
    name: Legion 5i (Host OS)
    kind: linux
    host: 192.168.29.146
    port: 9101
    ownership: personal

  - id: macbook-work
    name: MacBook Work
    kind: mac
    host: 192.168.29.231
    port: 9101
    ownership: company
    cleanup_on_offboard: true

  - id: iphone-11
    name: iPhone 11
    kind: ios
    ownership: personal
```

The `kind` field controls how the status-api collects data:

| kind | collection method |
|------|------------------|
| `k8s-node` | queries metrics-server, ArgoCD API, Ollama API via in-cluster DNS |
| `linux` | polls `GET http://<host>:<port>/metrics` every 60s |
| `mac` | same as linux |
| `ios` | waits for `POST /push` from iOS Shortcuts |

`cleanup_on_offboard: true` on the work MacBook means `make device-offboard` will SSH in and uninstall `homelab-agent` before removing the entry from the YAML.

The YAML is mounted as a Kubernetes ConfigMap into the status-api pod. Push a change to Git — ArgoCD syncs the ConfigMap automatically.

---

## Step 2: Install homelab-agent on Mac and Linux

`homelab-agent` is the Go binary that runs on each non-Kubernetes machine and exposes a `/metrics` endpoint. Build it on the target machine:

```bash
# on the target machine
git clone https://github.com/HiteshRepo/awesome-tools.git
cd awesome-tools
go build -o homelab-agent ./cmd/homelab-agent/
```

Or cross-compile from your dev machine if you prefer:

```bash
# for Linux
GOOS=linux GOARCH=amd64 go build -o homelab-agent-linux ./cmd/homelab-agent/
scp homelab-agent-linux user@192.168.29.146:~/homelab-agent
```

**Install as a systemd user service on Linux:**

```ini
# ~/.config/systemd/user/homelab-agent.service
[Unit]
Description=homelab-agent metrics server
After=network.target

[Service]
ExecStart=/home/hitesh/homelab-agent
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

```bash
systemctl --user enable homelab-agent
systemctl --user start homelab-agent
```

**Install as a launchd user agent on macOS:**

```xml
<!-- ~/Library/LaunchAgents/com.homelab.agent.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.homelab.agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/hitesh/homelab-agent</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

```bash
launchctl load ~/Library/LaunchAgents/com.homelab.agent.plist
```

Verify the agent is running:

```bash
curl http://localhost:9101/metrics
```

You should get back JSON with CPU, memory, disk, uptime, and battery (if available on the platform).

---

## Step 3: Set Up the iOS Push Shortcut

iPhones can't be polled from the LAN — they're behind NAT and they sleep. Instead, an iOS Shortcut runs on a schedule and POSTs health data to the status-api.

Create a new Shortcut in the iOS Shortcuts app with three actions:

**Action 1 — Get Battery Level:** adds the current battery percentage as a variable.

**Action 2 — Get Network Details → Network Name:** returns the SSID of the connected WiFi network as a string.

**Action 3 — Get Contents of URL:**
- URL: `http://192.168.29.146:31376/push`
- Method: POST
- Headers: `Content-Type: application/json`
- Request Body: JSON
  ```json
  {
    "id": "iphone-11",
    "battery_percent": [Battery Level variable],
    "wifi_name": [Network Name variable]
  }
  ```

Automate it hourly: Shortcuts app → Automation → New Automation → Time of Day → Every Hour → turn off "Ask Before Running" → add the shortcut.

The status-api marks an iOS device as `stale` if no push has arrived in the last 2 hours. With hourly automation and the "Don't Ask" toggle, you'll always have a fresh reading.

---

## Step 4: Deploy to Kubernetes

The status-api manifests live under `gitops/manifests/status-api/`. The minimum set:

```
gitops/manifests/status-api/
├── namespace.yaml
├── rbac.yaml          # ServiceAccount + ClusterRole + ClusterRoleBinding
├── configmap.yaml     # generated from config/devices.yaml
├── deployment.yaml
└── service.yaml       # NodePort 31376 + ClusterIP 8080
```

The ArgoCD Application at wave 4:

```yaml
# gitops/apps/status-api.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: status-api
  namespace: argocd
  annotations:
    argocd.argoproj.io/sync-wave: "4"
spec:
  project: default
  source:
    repoURL: https://github.com/HiteshRepo/k3s-homelab
    targetRevision: main
    path: gitops/manifests/status-api
  destination:
    server: https://kubernetes.default.svc
    namespace: status-api
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

The Traefik IngressRoute must go in the `traefik-system` namespace (not `status-api`) — this is non-negotiable for Traefik to pick it up:

```yaml
# gitops/manifests/ingress-routes/status-api.yaml
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: status-api
  namespace: traefik-system
spec:
  entryPoints: [websecure]
  routes:
    - match: Host(`status-api.lab.hiteshp.in`)
      kind: Rule
      services:
        - name: status-api
          namespace: status-api
          port: 8080
  tls: {}
```

Push to `main` and ArgoCD deploys everything automatically.

---

## Step 5: Understand the Status Response

The `GET /status` response uses four status values:

| status | meaning |
|--------|---------|
| `healthy` | metrics received within the last 2 minutes (mac/linux) or 2 hours (ios), all thresholds normal |
| `warning` | metrics are fresh but a threshold is exceeded — CPU >90%, memory >90%, disk >90% |
| `stale` | last seen more than 2 minutes ago (mac/linux) or 2 hours ago (ios) — the device may be offline or unreachable |
| `error` | the last poll attempt returned an HTTP error or the response failed to parse |
| `unknown` | no data has ever been received for this device (ios push has never arrived) |

The K8s node status is derived differently: `healthy` means the node is `Ready` in Kubernetes and all ArgoCD applications are `Synced`. Any application in `OutOfSync` or `Degraded` state flips the node to `warning`.

---

## Step 6: Three Widget Surfaces

### iPhone — Scriptable Widget

Open `http://192.168.29.146:31376/widget.js` in Safari on the iPhone. Select All → Copy. Open Scriptable, tap the `+` to create a new script, paste. Name it "Homelab Status".

Add it to the home screen: long-press an empty area → `+` → Scriptable → choose the medium or large widget size → select "Homelab Status" → Done.

The widget fetches from `http://192.168.29.146:31376/status` and renders each device as a colored row: green for healthy, yellow for warning, red for error/stale.

### macOS Menu Bar — xbar Plugin

[xbar](https://xbarapp.com) renders shell script output in the macOS menu bar. Install it once:

```bash
brew install --cask xbar
```

The homelab plugin:

```bash
# ~/Library/Application Support/xbar/plugins/homelab.5m.sh
#!/usr/bin/env bash
# <xbar.title>Homelab Status</xbar.title>
# <xbar.refreshTime>5m</xbar.refreshTime>

STATUS=$(curl -sf --max-time 3 http://192.168.29.146:31376/status 2>/dev/null)

if [ -z "$STATUS" ]; then
    echo "⬜ homelab"
    exit 0
fi

TOTAL=$(echo "$STATUS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d['devices']))")
HEALTHY=$(echo "$STATUS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(sum(1 for x in d['devices'] if x['status']=='healthy'))")

if [ "$HEALTHY" -eq "$TOTAL" ]; then
    echo "🟢 $HEALTHY/$TOTAL"
else
    echo "🟡 $HEALTHY/$TOTAL"
fi

echo "---"
echo "$STATUS" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for dev in d['devices']:
    icon = '🟢' if dev['status'] == 'healthy' else ('🟡' if dev['status'] == 'warning' else '🔴')
    print(f\"{icon} {dev['name']} ({dev['status']})\")
"
```

Copy to the xbar plugins directory, make it executable, refresh xbar. The menu bar shows the healthy/total count and clicking it expands the full fleet list.

### Linux Terminal — Shell Alias

```bash
# ~/.bashrc or ~/.zshrc
alias homelab='curl -sf http://localhost:31376/status | python3 -m json.tool'
alias homelab-watch='watch -n 30 "curl -sf http://localhost:31376/status | python3 -m json.tool"'
```

`homelab` prints the full JSON formatted. `homelab-watch` refreshes every 30 seconds — useful when you're doing maintenance and want to watch status change in real time.

---

## Step 7: Adding and Removing Devices

**Adding a device:**

```bash
make device-add
```

The Makefile target prompts interactively for all required fields and appends the new entry to `devices.yaml`. After running it, review the diff and push:

```bash
git diff gitops/manifests/status-api/config/devices.yaml
git add gitops/manifests/status-api/config/devices.yaml
git commit -m "feat: add <device-name> to device registry"
git push
```

ArgoCD syncs the ConfigMap automatically. The status-api picks up the new device on the next restart — trigger one manually after the sync:

```bash
kubectl rollout restart deployment/status-api -n status-api
```

**Removing a device:**

```bash
make device-offboard id=macbook-work
```

If `cleanup_on_offboard: true` is set, the target SSHes into the device and runs the uninstall script for `homelab-agent` before modifying the YAML. For iOS devices it just removes the entry. The same git push → ArgoCD sync flow applies.

---

## What This Doesn't Do (By Design)

**No persistent metrics history.** The status-api holds only the most recent reading per device in memory. Historical trends and graphs are Grafana's job — the kube-prometheus-stack is already running and collecting node metrics. Duplicating that into the status-api would add complexity without benefit.

**No alerting.** If a device goes stale, the status response reflects it, but there's no notification. Uptime Kuma handles alerting for the services that matter. Adding push notifications to the status-api would require an APNS integration and significantly more code.

**No remote access.** The status-api is accessible only from the home LAN. There's no authentication and no intent to expose it publicly. If you need remote visibility, `kubectl port-forward` or a Cloudflare Tunnel to a specific endpoint is the right approach.

Keeping the scope tight means the entire implementation is around 600 lines of Go across two binaries — `homelab-agent` and `status-api` — both in [HiteshRepo/awesome-tools](https://github.com/HiteshRepo/awesome-tools). The YAML declarations live in [HiteshRepo/k3s-homelab](https://github.com/HiteshRepo/k3s-homelab). Small enough to fully understand, useful enough to run every day.
