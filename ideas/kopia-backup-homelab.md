# Homelab Backups with Kopia and Backblaze B2

- type: technical
- tags: kopia, backblaze, b2, backup, homelab, kubernetes, k3s, 3-2-1-backup, self-hosted

- Goal: implement 3-2-1 backup strategy for homelab data — 3 copies, 2 media types, 1 offsite
- Stack: Kopia (open source backup tool) + Backblaze B2 (offsite S3-compatible storage) + USB pendrive (local backup) + k3s CronJob for scheduling
- What is Kopia: fast, encrypted, deduplicated backup tool. Splits files into chunks, deduplicates identical blocks across backups, compresses with zstd, encrypts with AES256-GCM before upload. Only changed blocks uploaded on subsequent backups
- What is Backblaze B2: S3-compatible cloud object storage at $6/TB/month (10GB free tier). Much cheaper than AWS S3 ($23/TB). Works with any S3-compatible tool including Kopia
- Two independent repositories: B2 for offsite (primary), pendrive for local (secondary). Each repository is completely independent — no syncing between them, both are upload-only from source
- What gets backed up nightly at 2AM IST: Immich library PVC (photos/videos), Immich postgres PVC (metadata/albums/faces), Open WebUI PVC (chat history), Kopia config PVC, k3s SQLite database (cluster state including secrets)
- k3s uses SQLite not etcd for single-node clusters — backup /var/lib/rancher/k3s/server/db/state.db to restore full cluster state including secrets not stored in Git
- Retention policy: 7 daily, 4 weekly, 12 monthly, 3 annual snapshots — can restore any specific day within last week, any week within last month, any month within last year
- CronJob pattern: single Kubernetes CronJob runs backup_all() function twice — once connected to B2 repo, once connected to pendrive repo (using separate --config-file). Clean separation with no bandwidth wasted on syncing
- Photo compression reality: JPEG, HEIC, MP4 are already compressed. Kopia's zstd compression gets 0-2% reduction on these. The real value is deduplication (unchanged photos not re-uploaded) and encryption
- B2 free tier pitfall: 10GB storage + 1GB/day download bandwidth. Hit the cap uploading 20GB of DSLR photos. Lesson: plan storage before uploading large photo libraries. After hitting cap, Backblaze blocks all writes — need to empty bucket and restart
- Gotcha — pendrive sync vs second repository: initially tried kopia repository sync-to filesystem which downloads from B2 to pendrive (uses download bandwidth cap). Correct approach: two independent repositories both backed up directly from source — no download needed
- Kopia deployed as k3s Deployment with hostPath volumes for external HDD and pendrive, plus PVC mounts for Immich/k3s data. Memory limit 4Gi needed for large repositories
- AppArmor blocks Kopia the same way it blocks postgres — same fix applies: unconfined annotation on the pod
- Making Makefile targets: kopia-snapshots, kopia-stats, kopia-backup-now, kopia-backup-b2, kopia-backup-local for quick CLI access without remembering kubectl exec commands
- Immich external library pattern: for large photo collections (DSLR RAW files, 20GB) that exceed B2 free tier — keep files on external HDD, add as Immich external library (files stay on HDD, not duplicated to NVMe), back up HDD path to pendrive only. When ready to upgrade B2, add to B2 CronJob with one line change
