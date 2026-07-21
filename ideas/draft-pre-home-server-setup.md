# GPU-Enabled Kubernetes Homelab: Setting Up a GTX 1650 Laptop as a k3s Node

- type: technical
- tags: homelab, kubernetes, k3s, nvidia, gpu, ollama, self-hosting, linux

- Context: turning an old GTX 1650 laptop into a GPU-enabled single-node k8s homelab to self-host Ollama and future AI workloads
- The setup is a layered stack — each component unlocks the next; explain the "why" behind each layer, not just the "what"
- Layer 1 — Ubuntu 26.04 LTS: fresh base OS, note ubuntu-drivers autoinstall is deprecated on 26.04
- Layer 2 — NVIDIA Driver 595: makes the OS aware the GPU exists; before this the GPU was an unknown PCI device; after this nvidia-smi works on host; heads-up: ubuntu-drivers install may install 580 instead of 595, both work fine for GTX 1650 + Ollama
- Layer 3 — CUDA Toolkit 12.4: driver lets the host see the GPU, CUDA lets applications use it for parallel compute (matrix multiplications powering LLM inference); enables Ollama to run on GPU instead of CPU, roughly 10–50x faster inference
- Layer 4 — NVIDIA Container Toolkit: containers are isolated by design and cannot see host hardware; this toolkit punches a controlled hole through that isolation; without it every pod is blind to the GTX 1650 regardless of host config
- Layer 5 — k3s: lightweight production-grade k8s on a single laptop; deploy, manage, scale services with standard manifests the same way prod systems are managed; intentionally disable traefik, servicelb, local-storage, metrics-server to keep it minimal and bring your own stack
- Layer 6 — NVIDIA Device Plugin (daemonset): even with container toolkit configured, k3s scheduler has no idea a GPU exists — it only tracks CPU and memory by default; the device plugin discovers the GPU and registers nvidia.com/gpu: 1 with the scheduler so pods can request it
- Challenge 1 — containerd not found: nvidia-ctk configure failed because containerd wasn't installed yet; k3s bundles its own containerd; fix was simple: install k3s first, then configure the NVIDIA runtime against k3s's containerd path
- Challenge 2 — GPU not visible to k3s scheduler (the tricky one): device plugin deployed but logged "Incompatible strategy detected" and "No devices found"; root cause: k3s regenerates its containerd config on every restart, wiping manual edits; fix: use the imports drop-in directory (config.toml.d/nvidia.toml) to set nvidia as the default runtime — a file k3s never overwrites
- End result: a legitimate GPU-enabled Kubernetes homelab; the laptop is now ready to run Ollama as a managed k8s workload with health checks, restarts, and resource limits
- Include the layered architecture diagram showing the full stack from GTX 1650 hardware to "Ready for Ollama"
- Include the key commands for each installation step so readers can follow along
- Include the device plugin log snippet showing the "Incompatible strategy" error so readers recognize it if they hit the same issue

## Raw Diagrams

```
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

```bash
# NVIDIA Driver — Step 1: see what Ubuntu recommends
ubuntu-drivers list

# Step 2: install recommended driver
sudo ubuntu-drivers install

# Or install explicitly by version
sudo apt install nvidia-driver-595-server

# Reboot and verify
sudo reboot
nvidia-smi
```

```bash
# CUDA Toolkit
sudo apt install nvidia-cuda-toolkit
nvcc --version
```

```bash
# NVIDIA Container Toolkit
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt update && sudo apt install -y nvidia-container-toolkit
```

```bash
# k3s — install with optional components disabled
curl -sfL https://get.k3s.io | sh -s - \
  --disable traefik \
  --disable servicelb \
  --disable local-storage \
  --disable metrics-server

sudo k3s kubectl get nodes
```

```bash
# NVIDIA Device Plugin
sudo k3s kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.17.0/deployments/static/nvidia-device-plugin.yml

sudo k3s kubectl get pods -n kube-system | grep nvidia

# Verify GPU is registered with scheduler
sudo k3s kubectl describe node | grep nvidia
# Expected:
# nvidia.com/gpu: 1
# nvidia.com/gpu: 1
```

```bash
# Fix for Challenge 2 — persistent NVIDIA runtime config for k3s
sudo nvidia-ctk runtime configure --runtime=containerd --config /var/lib/rancher/k3s/agent/etc/containerd/config.toml
sudo systemctl restart k3s

sudo k3s kubectl rollout restart daemonset nvidia-device-plugin-daemonset -n kube-system
sudo k3s kubectl get pods -n kube-system | grep nvidia
```

```bash
# Smoke test — run nvidia-smi inside a GPU-enabled pod
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
