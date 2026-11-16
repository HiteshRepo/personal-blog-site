# Building a Multi-Device Health Dashboard for My Homelab: Go, K3s, and an iPhone Widget

- type: technical
- tags: homelab, golang, k3s, kubernetes, argocd, ios, scriptable, metallb, traefik, gitops

- The problem: checking homelab health required opening ArgoCD, Grafana, and manually SSHing — no single view of "are all my devices okay right now"
- Solution: a single Go HTTP service (`status-api`) running in K3s that aggregates metrics from cluster internals, LAN-polled agents, and iOS push payloads into one `GET /status` JSON endpoint
- Three fundamentally different collection strategies required: pull (homelab-agent on Mac/Linux over LAN), in-cluster query (K8s metrics-server, ArgoCD API, Ollama API, Kopia API), and push (iOS devices can't be polled from outside — they POST via Shortcuts automation)
- `homelab-agent`: a lightweight Go binary using `gopsutil` exposing `GET /metrics` (CPU, MEM, disk, battery, uptime, CPU temp) as a systemd/launchd service; cross-compiled for linux/amd64 and darwin/arm64; installs via a single shell one-liner
- Battery detection is OS-specific: Darwin uses `pmset -g batt` output parsing, Linux reads `/sys/class/power_supply/BAT0/`; CPU temp (Linux only) uses `gopsutil/sensors`; build tags (`//go:build darwin`, `//go:build linux`) keep the binary clean with no runtime OS checks
- Port conflict gotcha: port 9100 conflicts with Prometheus node_exporter on Linux — homelab-agent runs on 9101
- Device registry as YAML (`config/devices.yaml`): single source of truth committed to the repo; ArgoCD mounts it as a ConfigMap volume into status-api; adding a device is `make device-add` + git push
- GitOps delivery: status-api deployed as an ArgoCD Application (wave 4); ConfigMap change alone doesn't trigger pod restart — must `kubectl rollout restart` or add a checksum annotation
- iOS push payload design: initially modelled `wifi_connected` as `bool` — broke immediately because iOS Shortcuts passes the WiFi network name (a string), not a boolean; changed to `wifi_name *string` with all payload fields as optional pointers
- iOS stale detection: if no push received within 2 hours, device flips to `stale`; in-memory `sync.Map` keyed by device id (no database needed — pod restarts are infrequent, stale for up to 1h on restart is acceptable)
- MetalLB assigns `192.168.29.201` to status-api's LoadBalancer service — reachable from Mac but not from iPhone (router segments wired/WiFi); iPhone must use the NodePort `192.168.29.146:31376` via the Lenovo's real IP
- K8s cluster metrics collector: queries `/api/v1/pods` with ServiceAccount token, ArgoCD `/api/v1/applications`, Ollama `/api/ps`, Kopia `/api/v1/snapshots` — all via in-cluster service DNS; partial failure sets affected fields to null and device status to `warning` rather than `error`
- RBAC: dedicated ServiceAccount with ClusterRole granting only `get`/`list` on nodes, pods, and ArgoCD Application CRDs — no secrets or configmap access
- Testing strategy: registry loader at 92.9% coverage (table-driven invalid YAML cases), push store at 100% (stale threshold set to 1ns to force immediate staleness in tests), HTTP handler tests verify error/stale state without needing a live cluster
- `go:embed` for serving widget.js and shortcut files from status-api itself — avoids firewall/hostname issues when distributing to iOS; embedding base64 manually in Go source gets corrupted, `//go:embed` reads the actual file at build time
- Distroless image (`gcr.io/distroless/static-debian12:nonroot`): no shell inside the container makes debugging harder — `kubectl exec` with busybox sidecar used to test connectivity; poll errors were silent until log lines were added to the agent poller
- Build pipeline: no CI yet — manually `git pull` on Lenovo, `docker build`, `docker save | sudo k3s ctr images import -`, `kubectl rollout restart`; next step is a GitHub Actions workflow
