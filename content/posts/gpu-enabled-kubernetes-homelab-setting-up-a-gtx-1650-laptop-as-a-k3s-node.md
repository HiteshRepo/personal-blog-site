---
title: "GPU-Enabled Kubernetes Homelab: Setting Up a GTX 1650 Laptop as a k3s Node"
date: 2026-07-21T12:00:00-07:00
summary: "A step-by-step walkthrough of turning an old GTX 1650 laptop into a GPU-enabled single-node k3s cluster, explaining the why behind each layer of the stack and the two non-obvious gotchas that will trip you up."
draft: false
ai_generated: false
tags: ["homelab", "kubernetes", "k3s", "nvidia", "gpu", "ollama", "self-hosting", "linux"]
categories: []
---

I had an old laptop with a GTX 1650 sitting around and wanted to self-host Ollama for local LLM inference. Running it bare-metal works, but I wanted something more — health checks, automatic restarts, resource limits, and a platform I could keep adding services to. That meant Kubernetes.

The problem: getting a GPU into a k8s cluster is not a single `apt install`. It's a layered stack where each component depends on the one below it, and if you skip a layer or install them in the wrong order, nothing works and the errors are cryptic. This post walks through the entire stack on Ubuntu 26.04, explains what each piece actually does, and covers the two non-obvious issues I hit along the way.

## The Stack

Before touching a single command, it helps to understand what you're building and why each layer exists:

```text
GTX 1650 Hardware
      ↓
NVIDIA Driver          ← host OS sees the GPU
      ↓
CUDA Toolkit           ← AI workloads can use the GPU
      ↓
Container Toolkit      ← containers can reach the GPU
      ↓
k3s                    ← cluster to deploy and manage services
      ↓
Device Plugin          ← scheduler knows GPU exists and can assign it to pods
      ↓
✅ Ready for Ollama
```

Each arrow is a dependency. The driver without CUDA is a GPU the OS can see but can't compute with. CUDA without the container toolkit is a GPU that containers are blind to. The container toolkit without the device plugin is a GPU that k3s's scheduler can't schedule onto. You need all six layers.

## Layer 1: Ubuntu 26.04 LTS

Nothing special here — fresh install, standard setup. One thing to note: `ubuntu-drivers autoinstall` is deprecated on 26.04 and no longer available. The new command is `ubuntu-drivers install`.

## Layer 2: NVIDIA Driver

The driver makes Ubuntu aware the GPU exists. Before it, the GTX 1650 shows up as an unknown PCI device. After it, `nvidia-smi` works and the OS can read GPU temperature, check VRAM, and hand it compute tasks.

```bash
# See what Ubuntu recommends for your hardware
ubuntu-drivers list

# Install the recommended driver
sudo ubuntu-drivers install

# Or install explicitly by version
sudo apt install nvidia-driver-595-server

# Reboot and verify
sudo reboot
nvidia-smi
```

One heads-up specific to 26.04: `ubuntu-drivers install` may install driver 580 even if your hardware shows 595 as recommended. This is a known quirk — 580 works fine for the GTX 1650 with Ollama, so don't let the discrepancy block you.

## Layer 3: CUDA Toolkit

The driver lets the host see the GPU. CUDA lets applications actually use it for parallel computation — specifically the matrix multiplications that power LLM inference. Without CUDA, Ollama falls back to CPU, which is roughly 10–50x slower.

```bash
sudo apt install nvidia-cuda-toolkit
nvcc --version
```

## Layer 4: NVIDIA Container Toolkit

Containers are isolated by design. They can't see host hardware — that's the point. The NVIDIA Container Toolkit punches a controlled hole through that isolation by hooking into the container runtime. Without it, every pod is completely blind to the GTX 1650 regardless of what the host has configured.

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt update && sudo apt install -y nvidia-container-toolkit
```

Don't configure the runtime yet — do that after k3s is installed.

## Layer 5: k3s

k3s gives you a lightweight, production-grade Kubernetes cluster on a single machine. You can deploy, manage, scale, and update services using standard k8s manifests — the same way production systems are managed. For a homelab, that means Ollama, Open WebUI, Nginx, and anything else you want to run gets health checks, automatic restarts, and resource limits for free.

I installed it with several optional components disabled to keep things minimal:

```bash
curl -sfL https://get.k3s.io | sh -s - \
  --disable traefik \
  --disable servicelb \
  --disable local-storage \
  --disable metrics-server

sudo k3s kubectl get nodes
```

Disabling these means you bring your own ingress, load balancer, and storage — which gives you more control over the stack later.

## Layer 6: NVIDIA Device Plugin

Here's where it gets interesting. Even with the container toolkit installed and working, k3s's scheduler has no idea a GPU exists. By default it only tracks CPU and memory. The device plugin is a daemonset that discovers the GPU and registers `nvidia.com/gpu: 1` as a schedulable resource. Once it's running, pods can request a GPU and k3s knows which nodes can satisfy that request.

```bash
sudo k3s kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.17.0/deployments/static/nvidia-device-plugin.yml

sudo k3s kubectl get pods -n kube-system | grep nvidia

# Verify the GPU is registered with the scheduler
sudo k3s kubectl describe node | grep nvidia
# Expected output:
# nvidia.com/gpu: 1
# nvidia.com/gpu: 1
```

## The Two Gotchas

### Challenge 1: containerd not found

After installing the container toolkit, running `nvidia-ctk runtime configure` failed because containerd wasn't installed. The error made it seem like a toolkit problem — it wasn't. k3s bundles its own containerd binary, separate from the system one. The fix is just ordering: install k3s first, then configure the NVIDIA runtime against k3s's containerd path.

```bash
sudo nvidia-ctk runtime configure --runtime=containerd \
  --config /var/lib/rancher/k3s/agent/etc/containerd/config.toml
sudo systemctl restart k3s
```

### Challenge 2: GPU not visible to the k3s scheduler

This one is trickier. I deployed the device plugin and it ran, but the logs showed:

```text
E0718 10:42:07.181895       1 factory.go:112] Incompatible strategy detected auto
E0718 10:42:07.181909       1 factory.go:113] If this is a GPU node, did you configure the NVIDIA Container Toolkit?
I0718 10:42:07.181938       1 main.go:381] No devices found. Waiting indefinitely.
```

Everything looked correct — the container toolkit was installed, the runtime was configured. The root cause turned out to be subtle: **k3s regenerates its containerd config on every restart**, wiping any manual edits made directly to `config.toml`.

The fix is to use the imports drop-in directory instead. k3s respects files in `config.toml.d/` and never overwrites them:

```bash
sudo nvidia-ctk runtime configure --runtime=containerd \
  --config /var/lib/rancher/k3s/agent/etc/containerd/config.toml

sudo systemctl restart k3s

# Restart the device plugin to pick up the change
sudo k3s kubectl rollout restart daemonset nvidia-device-plugin-daemonset -n kube-system
sudo k3s kubectl get pods -n kube-system | grep nvidia
```

After this, the device plugin came up clean and `nvidia.com/gpu: 1` appeared in the node's capacity.

## Smoke Test

The final verification is running a GPU-enabled pod and checking that it can actually see the GPU:

```bash
sudo k3s kubectl apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: gpu-test
spec:
  restartPolicy: Never
  containers:
  - name: gpu-test
    image: nvidia/cuda:12.4.0-base-ubuntu22.04
    command: ["nvidia-smi"]
    resources:
      limits:
        nvidia.com/gpu: 1
EOF

sudo k3s kubectl get pod gpu-test
sudo k3s kubectl logs gpu-test
```

If the logs show the familiar `nvidia-smi` output with GPU name, driver version, and CUDA version — you're done. The laptop is now a GPU-enabled Kubernetes homelab.

## Where This Goes Next

With the stack in place, deploying Ollama is straightforward — a Deployment that requests `nvidia.com/gpu: 1`, a Service to expose it, and a PersistentVolumeClaim for model storage. Open WebUI can sit in front of it as a separate Deployment. Both are standard k8s manifests, and k3s handles the rest.

The setup does exactly what I wanted: Ollama runs on the GPU with hardware-accelerated inference, k3s keeps it running with health checks and automatic restarts, and the platform is ready for whatever comes next.
