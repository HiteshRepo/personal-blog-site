# Track Every Device in Your Homelab with One JSON Endpoint

- type: tutorial
- tags: homelab, gitops, golang, k3s, ios, scriptable, xbar, argocd, self-hosted

- The end goal: one curl command (`curl http://192.168.29.146:31376/status`) returns the health of every device in your homelab — cluster node, laptops, and iPhones — updated every 60 seconds
- Everything starts with a YAML file: `config/devices.yaml` lists every device with an id, name, kind (k8s-node/mac/linux/ios), ownership, and for mac/linux a host+port for the agent; this file is the single source of truth
- Adding a device takes under 5 minutes: `make device-add` prompts for fields interactively, appends to the YAML, prints either the agent install one-liner (mac/linux) or the iOS Shortcut push URL; `git push` → ArgoCD restarts the pod with the new device list
- `homelab-agent` install is a single command: the binary is cross-compiled for linux/amd64 and darwin/arm64; on macOS it installs as a launchd service, on Linux as a systemd user service; exposes `GET /metrics` on port 9101 (9100 conflicts with Prometheus node_exporter)
- iOS devices push rather than get polled: an iOS Shortcut runs hourly (silent automation), POSTing battery level and WiFi name to `POST /push`; if no push is received within 2 hours the device flips to `stale` — acceptable for a personal widget
- K8s node metrics come from inside the cluster: status-api queries the metrics-server, ArgoCD, Ollama, and Kopia APIs using in-cluster service DNS and a minimal-permission ServiceAccount — no credentials stored anywhere
- Three widget surfaces built from the same endpoint:
  - iPhone: Scriptable widget (small/medium/large + drill-down detail screen)
  - Mac: xbar menu bar plugin showing `🖥 5/5 ✓` with per-device dropdown
  - Linux: `watch -n 10 curl http://localhost:31376/status` alias in ~/.bashrc
- Status values and what they mean: `healthy` (agent responded within 5s or push received within 2h), `error` (agent unreachable), `stale` (iOS device hasn't pushed), `warning` (cluster API partially unavailable)
- Offboarding is symmetric: `make device-offboard id=<id>` SSHs to mac/linux to stop and uninstall the agent, removes the YAML entry, git push removes the device from status-api after ArgoCD sync
- What this deliberately doesn't do: persistent metrics history (Prometheus/Grafana already handle this), alerting (Uptime Kuma handles this), remote access beyond home WiFi (Tailscale is future work) — keeping the scope tight means the whole thing is ~600 lines of Go across two binaries
- The xbar plugin is 30 lines of bash: `curl` the status endpoint, `python3` to count healthy devices, one line per device with color coding — no dependencies beyond Python 3 which ships with macOS
- Total infrastructure cost: one extra K8s Deployment (2 replicas of a 6MB distroless container), one LoadBalancer IP from the MetalLB pool, one ConfigMap — negligible on a single-node homelab
