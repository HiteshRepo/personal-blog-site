---
title: "GitOps Homelab: Building a Multi-Device Health Dashboard with Go, K3s, and an iPhone Widget"
date: 2026-11-16T12:00:00+05:30
summary: "How I built a unified device health dashboard for my homelab — a Go HTTP aggregator in K3s that pulls metrics from Mac/Linux agents, queries cluster APIs, and receives iOS push payloads, all surfaced in a Scriptable iPhone widget."
draft: false
ai_generated: true
tags: ["homelab", "golang", "k3s", "kubernetes", "argocd", "ios", "scriptable", "metallb", "traefik", "gitops", "gopsutil"]
categories: []
---

> **Note:** This post was AI-generated from rough notes using the blog generation workflow.

Checking homelab health used to mean three browser tabs and an SSH session. ArgoCD for cluster sync status. Grafana for CPU and memory graphs. A terminal to SSH into the MacBook and run `top`. That friction compounds fast — you stop checking, the laptop runs hot for two days before anyone notices, and a pod is quietly crashlooping in the background.

I wanted one endpoint: `GET /status`. Something I could hit from any device and get back a single JSON blob telling me whether every machine in the fleet was healthy. This post is the full story of building that.

All source code is in [HiteshRepo/k3s-homelab](https://github.com/HiteshRepo/k3s-homelab) and [HiteshRepo/awesome-tools](https://github.com/HiteshRepo/awesome-tools).

---

## Architecture: Three Collection Strategies

The fleet has four fundamentally different kinds of devices. Each needs a different data collection approach.

**Pull — mac and linux agents.** A Go binary called `homelab-agent` runs on each Mac and Linux machine, exposing a `GET /metrics` endpoint on port 9101. The `status-api` running in K3s polls each agent every 60 seconds. This is the simplest approach for machines you control and can install software on.

**In-cluster query — the Kubernetes node itself.** The `status-api` is already inside the cluster, so it queries the metrics-server, ArgoCD API, and Ollama API directly via cluster-internal DNS. No agent needed. The node is a first-class device in the registry.

**Push — iOS devices.** iPhones can't be polled. They're behind NAT, they sleep, and there's no equivalent of SSH. Instead, iOS devices POST to `POST /push` on a schedule via the iOS Shortcuts automation. The `status-api` stores the last push payload in memory and serves it on demand.

Three strategies, one unified `GET /status` response.

---

## homelab-agent: Metrics on Port 9101

`homelab-agent` is a small Go binary that wraps [gopsutil](https://github.com/shirou/gopsutil) for the cross-platform metrics and adds some platform-specific extras.

```
cmd/homelab-agent/
├── main.go
├── internal/
│   ├── metrics/
│   │   ├── collector.go        # gopsutil: cpu, mem, disk, uptime
│   │   ├── battery_darwin.go   // +build darwin
│   │   └── battery_linux.go    // +build linux
│   └── server/
│       └── server.go           # HTTP server on :9101
```

The core metrics are straightforward gopsutil calls:

```go
// internal/metrics/collector.go
func Collect() (*Metrics, error) {
    cpuPercents, err := cpu.Percent(time.Second, false)
    if err != nil {
        return nil, fmt.Errorf("cpu: %w", err)
    }
    vmStat, err := mem.VirtualMemory()
    if err != nil {
        return nil, fmt.Errorf("mem: %w", err)
    }
    diskStat, err := disk.Usage("/")
    if err != nil {
        return nil, fmt.Errorf("disk: %w", err)
    }
    uptime, err := host.Uptime()
    if err != nil {
        return nil, fmt.Errorf("uptime: %w", err)
    }
    return &Metrics{
        CPUPercent:  cpuPercents[0],
        MemPercent:  vmStat.UsedPercent,
        DiskPercent: diskStat.UsedPercent,
        UptimeHours: float64(uptime) / 3600,
    }, nil
}
```

Battery is handled differently per platform via build tags. On macOS, `battery_darwin.go` shells out to `pmset -g batt` and parses the output — gopsutil's battery support on macOS is unreliable in practice. On Linux, `battery_linux.go` reads from `/sys/class/power_supply/BAT0/capacity` directly:

```go
// internal/metrics/battery_linux.go
//go:build linux

func BatteryPercent() (float64, error) {
    data, err := os.ReadFile("/sys/class/power_supply/BAT0/capacity")
    if err != nil {
        return 0, err // desktop machine — no battery
    }
    val, err := strconv.ParseFloat(strings.TrimSpace(string(data)), 64)
    if err != nil {
        return 0, fmt.Errorf("parse battery: %w", err)
    }
    return val, nil
}
```

CPU temperature is Linux-only via `lm-sensors`. The macOS SMC approach requires cgo, which complicates cross-compilation. For macOS, the temperature field is omitted from the response rather than returning a stale or wrong value.

Port 9101 specifically — port 9100 is the standard port for Prometheus `node_exporter`. Running on 9100 would cause a collision on the Lenovo, which also runs node_exporter for Grafana.

**Running as a service.** On Linux, `homelab-agent` installs as a systemd user service under `~/.config/systemd/user/homelab-agent.service`. On macOS it installs as a launchd user agent under `~/Library/LaunchAgents/com.homelab.agent.plist`. Both start automatically on login and restart on failure.

---

## Device Registry: config/devices.yaml

Every device in the fleet is listed in `config/devices.yaml`. This file lives in the [k3s-homelab](https://github.com/HiteshRepo/k3s-homelab) repository and is mounted into the `status-api` pod as a ConfigMap volume.

```yaml
# gitops/manifests/status-api/config/devices.yaml
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

The `kind` field drives what collection strategy the `status-api` uses for each device. `k8s-node` triggers the in-cluster query path. `mac` and `linux` trigger the agent polling path. `ios` expects push data.

`cleanup_on_offboard: true` on the work MacBook is a signal to `make device-offboard` that it should SSH in and uninstall the agent before removing the entry from the YAML — important for machines you don't own.

Adding a new device is interactive:

```bash
make device-add
# prompts: id, name, kind, host, port, ownership
# appends the new entry to devices.yaml
# prints: "git push to deploy — ArgoCD will pick it up"
```

---

## status-api Internals

The `status-api` reads `devices.yaml` at startup and validates it before accepting any traffic. Required fields and duplicate ID detection are enforced at load time — if the YAML is malformed or has duplicate IDs, the process exits non-zero. This surfaces configuration errors during deployment rather than serving wrong data silently.

```go
// internal/registry/loader.go
func Load(path string) (*Registry, error) {
    data, err := os.ReadFile(path)
    if err != nil {
        return nil, fmt.Errorf("read registry: %w", err)
    }
    var reg Registry
    if err := yaml.Unmarshal(data, &reg); err != nil {
        return nil, fmt.Errorf("parse registry: %w", err)
    }
    seen := map[string]bool{}
    for _, d := range reg.Devices {
        if d.ID == "" {
            return nil, fmt.Errorf("device missing required field: id")
        }
        if d.Kind == "" {
            return nil, fmt.Errorf("device %q missing required field: kind", d.ID)
        }
        if seen[d.ID] {
            return nil, fmt.Errorf("duplicate device id: %q", d.ID)
        }
        seen[d.ID] = true
    }
    return &reg, nil
}
```

**Agent poller.** One goroutine per mac/linux device spawns at startup and polls on a 60-second ticker. Each goroutine writes its result into a `sync.Map` keyed by device ID. The HTTP handler reads from the map without blocking the pollers.

**iOS push store.** `POST /push` deserializes the payload and stores it in a `sync.Map` with a timestamp. `GET /status` reads the entry and computes status: if the last push was more than 2 hours ago, the device is marked `stale`. If no push has ever arrived, it's `unknown`.

**K8s collector.** A background goroutine queries the metrics-server API, ArgoCD's application list endpoint, and Ollama's `/api/tags` endpoint on a 30-second interval. It uses the in-cluster service account token automatically mounted at `/var/run/secrets/kubernetes.io/serviceaccount/token`.

---

## Kubernetes Delivery

The status-api lives under `gitops/manifests/status-api/` and is managed by an ArgoCD Application at sync wave 4.

```yaml
# gitops/manifests/status-api/rbac.yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: status-api
rules:
  - apiGroups: [""]
    resources: ["nodes", "pods"]
    verbs: ["get", "list"]
  - apiGroups: ["argoproj.io"]
    resources: ["applications"]
    verbs: ["get", "list"]
```

Minimal permissions: nodes, pods, and ArgoCD applications. Nothing else.

```yaml
# gitops/manifests/status-api/deployment.yaml
containers:
  - name: status-api
    image: ghcr.io/hiteshrepo/status-api:latest
    imagePullPolicy: IfNotPresent
    volumeMounts:
      - name: devices-config
        mountPath: /app/config
volumes:
  - name: devices-config
    configMap:
      name: devices-config
```

The ConfigMap is generated from `config/devices.yaml` and applied by ArgoCD as part of the same sync. The Traefik IngressRoute lives in `traefik-system` as required:

```yaml
# gitops/manifests/ingress-routes/status-api.yaml
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: status-api
  namespace: traefik-system
spec:
  entryPoints:
    - websecure
  routes:
    - match: Host(`status-api.lab.hiteshp.in`)
      kind: Rule
      services:
        - name: status-api
          namespace: status-api
          port: 8080
  tls: {}
```

---

## Testing

The registry package has 92.9% test coverage via table-driven tests covering every invalid YAML case: missing ID, missing kind, duplicate IDs, malformed YAML, empty file.

```go
// internal/registry/loader_test.go
func TestLoad(t *testing.T) {
    cases := []struct {
        name    string
        yaml    string
        wantErr string
    }{
        {
            name:    "duplicate id",
            yaml:    "devices:\n  - id: foo\n    kind: mac\n  - id: foo\n    kind: linux\n",
            wantErr: `duplicate device id: "foo"`,
        },
        {
            name:    "missing kind",
            yaml:    "devices:\n  - id: foo\n",
            wantErr: `device "foo" missing required field: kind`,
        },
    }
    for _, tc := range cases {
        t.Run(tc.name, func(t *testing.T) {
            f := writeTempFile(t, tc.yaml)
            _, err := Load(f)
            if tc.wantErr == "" {
                require.NoError(t, err)
            } else {
                require.ErrorContains(t, err, tc.wantErr)
            }
        })
    }
}
```

The push store tests use a 1ns stale threshold to test the `stale` path without sleeping:

```go
store := NewPushStore(1 * time.Nanosecond) // stale almost immediately
store.Store("iphone-11", payload)
time.Sleep(2 * time.Nanosecond)
status := store.Status("iphone-11")
assert.Equal(t, "stale", status)
```

The Scriptable widget JavaScript is bundled into the binary with `//go:embed`:

```go
// main.go
//go:embed widget.js
var widgetJS []byte

// handler
mux.HandleFunc("/widget.js", func(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Content-Type", "text/plain")
    w.Write(widgetJS)
})
```

---

## Gotchas

**ConfigMap change alone does not restart the pod.** ArgoCD will sync the ConfigMap update, but the running pod will keep serving the old version from memory. After pushing a `devices.yaml` change, force a rollout:

```bash
kubectl rollout restart deployment/status-api -n status-api
```

**MetalLB LoadBalancer IP not reachable from WiFi clients.** The `status-api.lab.hiteshp.in` domain resolves to the MetalLB IP (`192.168.29.201`), which works fine from the Lenovo itself but the iPhone reports "The Internet connection appears to be offline". MetalLB's L2 ARP announcements don't always propagate to wireless segments depending on how the router handles ARP on the wireless bridge. Use the NodePort instead — the Lenovo's real IP is always reachable from any device on the LAN:

```
http://192.168.29.146:31376/status   # works from iPhone, xbar, curl
```

**Distroless container: no shell for debugging.** The `status-api` image uses `gcr.io/distroless/static:nonroot` for a small attack surface and no shell. When you need to test connectivity from inside the cluster, run a temporary busybox pod instead:

```bash
kubectl run debug --image=busybox --rm -it --restart=Never -- sh
# now you're inside the cluster
wget -O- http://status-api.status-api.svc.cluster.local:8080/status
```

**Silent poll failures.** The agent poller goroutines used to fail silently — the `sync.Map` entry would just go stale without any log line. Discovered this when the MacBook Work entry showed `stale` for a week: the host IP had changed from `192.168.29.231` to `192.168.1.101` after a DHCP rebind. Added explicit `log.Printf` on every poll error. Now stale entries come with a reason in the logs.
