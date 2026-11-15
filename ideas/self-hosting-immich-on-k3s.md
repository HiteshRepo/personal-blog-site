# Self-Hosting Immich on K3s — The Hard Parts Nobody Talks About

- type: technical
- tags: immich, k3s, kubernetes, homelab, self-hosted, argocd, postgres, apparmor, traefik, metallb

- Goal: deploy Immich (self-hosted Google Photos alternative) on a single-node k3s cluster using ArgoCD GitOps
- Stack: k3s + ArgoCD + Helm chart (immich-app/immich-charts 0.12.0) + Traefik ingress + MetalLB LoadBalancer + local-path-provisioner storage
- Immich components: immich-server, immich-machine-learning, postgres (custom image with VectorChord extension), valkey (Redis replacement), 200GB library PVC
- Key gotcha #1 — AppArmor blocks inter-process signals: the cri-containerd AppArmor profile blocks SIGINT between postgres processes, causing the WAL startup process to exit with code 1 after a 60-second timeout. Also causes gosu to hang and pg_ctl stop to fail with Permission denied. Fix: add container.apparmor.security.beta.kubernetes.io/<container-name>: unconfined annotation to the pod template
- Key gotcha #2 — postgres initdb requires correct ownership: local-path provisioner creates PVC directories as root. With runAsUser=999 (postgres user), initdb fails because it cannot chmod the data directory. Fix: add an initContainer running as root that chowns the directory to 999:999 before postgres starts
- Key gotcha #3 — Immich Helm chart 0.10.0 removed bundled postgres subchart: the chart now requires either CloudNativePG or external postgres. For homelab, deployed standalone postgres using ghcr.io/immich-app/postgres:16-vectorchord0.4.3 image (includes VectorChord for vector similarity search used by ML features)
- Key gotcha #4 — chart fails if postgresql or redis keys exist in Helm values: even with enabled: false, the presence of these keys triggers a template check error. Remove them entirely and use the new valkey key instead
- Key gotcha #5 — MetalLB subnet mismatch: had MetalLB IP pool configured for 192.168.1.x but actual LAN was 192.168.29.x — Traefik LoadBalancer got an IP that wasn't routable on the network. Fix: update both the IPAddressPool and the metallb.universe.tf/loadBalancerIPs annotation on the Traefik service
- Key gotcha #6 — vchord extension must be created manually on first deployment: even though vchord.so is in shared_preload_libraries, running CREATE EXTENSION IF NOT EXISTS vchord CASCADE must be done manually before Immich connects, otherwise Immich fails to activate the extension
- GitOps pattern: two ArgoCD Applications — immich-prereqs (wave 3) for namespace + PVC creation, immich (wave 4) for the Helm chart — ensures PVC exists before Helm deploys
- Traefik IngressRoute must be in traefik-system namespace (not immich namespace) with cross-namespace routing enabled
- Immich accessible at https://immich.lab.hiteshp.in on local network with self-signed cert from Traefik
- For mobile access without /etc/hosts support: expose via NodePort (kubectl patch svc immich-server -n immich -p '{"spec":{"type":"NodePort","ports":[{"port":2283,"nodePort":30283}]}}') and connect Immich iOS/iPadOS app to http://<node-ip>:30283
- Machine learning features (face recognition, CLIP search) work locally on CPU — no GPU required though GPU speeds it up significantly
- All config stored in GitHub repo — cluster can be rebuilt from scratch with one ArgoCD bootstrap command
