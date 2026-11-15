---
title: "Homelab Backups with Kopia and Backblaze B2"
date: 2026-11-15T17:00:00+05:30
summary: "Implementing a 3-2-1 backup strategy for a k3s homelab using Kopia for encryption and deduplication, Backblaze B2 for offsite storage, and a USB pendrive for local backup — including the gotchas around B2 free tier limits and the wrong way to sync repositories."
draft: false
ai_generated: true
tags: ["kopia", "backblaze", "b2", "backup", "homelab", "kubernetes", "k3s", "self-hosted"]
categories: []
---

> **Note:** This post was AI-generated from rough notes using the blog generation workflow.

Homelab data has a nasty property: it's real data (your photos, cluster state, app databases) on hardware you bought yourself, with no SLA and no support contract. If the drive fails, it's gone. This post covers the backup strategy I built on top of a k3s cluster using Kopia and Backblaze B2.

---

## The 3-2-1 Rule

Three copies. Two different media. One offsite.

```
Copy 1 → Lenovo NVMe (primary — Immich library, app data)
Copy 2 → USB Pendrive (local backup — Kopia repository)
Copy 3 → Backblaze B2 (offsite — Kopia repository)
```

The primary data lives on the NVMe. Kopia backs it up independently to two separate repositories. Neither repository depends on the other.

---

## Kopia

[Kopia](https://kopia.io) is an open-source backup tool that does three important things before data leaves your machine:

- **Deduplication** — splits files into content-addressed chunks; identical blocks across all backups are stored once
- **Compression** — zstd by default (meaningful for text/databases, near-zero for already-compressed photos)
- **Encryption** — AES256-GCM; the destination (B2 or pendrive) sees only opaque encrypted blobs

The result: incremental backups where only changed chunks upload. A nightly backup of a 10GB photo library uploads only new photos, not 10GB every night.

---

## Backblaze B2

[Backblaze B2](https://www.backblaze.com/cloud-storage) is S3-compatible object storage at $6/TB/month — roughly 10x cheaper than AWS S3. The free tier is 10GB storage + 1GB/day download.

Kopia connects to B2 via the S3-compatible API:

```bash
kopia repository create s3 \
  --bucket=my-homelab-backup \
  --endpoint=s3.eu-central-003.backblazeb2.com \
  --access-key=<key-id> \
  --secret-access-key=<app-key> \
  --password=<encryption-password>
```

The `--password` is your Kopia encryption key. B2 never sees unencrypted data. Even if your B2 account is compromised, the data is unreadable without this password.

---

## What Gets Backed Up

Nightly at 2AM IST, a Kubernetes CronJob backs up:

| Source | What it contains |
|--------|----------------|
| `/mnt/immich` | Photo/video library (Immich) |
| `/mnt/pvcs/immich-postgres` | Immich database (albums, faces, metadata) |
| `/mnt/pvcs/open-webui` | LLM chat history |
| `/mnt/pvcs/kopia-config` | Kopia configuration |
| `/mnt/k3s-db` | k3s SQLite database (cluster state) |
| `/mnt/external/docs` | Personal documents |

The k3s database (`/var/lib/rancher/k3s/server/db/state.db`) is particularly important — it contains all Kubernetes secrets, configmaps, and CRDs including secrets not stored in Git. Without it, restoring a cluster means recreating every secret manually.

Note: single-node k3s uses SQLite, not etcd. `k3s etcd-snapshot` won't work — back up the SQLite file directly.

---

## Two Independent Repositories

The key design decision: two completely independent Kopia repositories, both backed up directly from source.

```
Source data → Kopia → B2 repository
Source data → Kopia → Pendrive repository
```

**What not to do:** `kopia repository sync-to filesystem` downloads from B2 to the pendrive. This consumes the 1GB/day download bandwidth cap immediately. With 8GB+ in B2, you'll hit the cap within minutes.

**What to do:** maintain two config files, connect to each repository separately, run the same backup function against each.

The CronJob does this with a shell function:

```bash
backup_all() {
  kopia snapshot create /mnt/immich
  kopia snapshot create /mnt/pvcs/immich-postgres
  # ... other sources
}

# B2 backup
kopia repository connect s3 --bucket=... --password=$KOPIA_PASSWORD
backup_all

# Pendrive backup
kopia --config-file=/app/config/repository-local.config \
  repository connect filesystem --path=/mnt/pendrive --password=$KOPIA_PASSWORD
backup_all
```

---

## Retention Policy

```bash
kopia policy set /mnt/immich \
  --keep-daily=7 \
  --keep-weekly=4 \
  --keep-monthly=12 \
  --compression=zstd
```

| Window | Snapshots kept |
|--------|---------------|
| Last 7 days | One per day |
| Last 4 weeks | One per week |
| Last 12 months | One per month |
| Last 3 years | One per year (default) |

You can restore to any specific day within the last week, any week within the last month.

---

## B2 Free Tier Gotchas

**Storage cap:** 10GB. Photos don't compress. 20GB of DSLR RAW photos will exceed the free tier instantly. Plan your storage before bulk uploads.

**What happens when you hit the cap:** B2 blocks all writes. Maintenance operations (which write index blobs) also fail. To recover: empty the bucket via the B2 dashboard, then recreate the Kopia repository from scratch.

**Download cap:** 1GB/day. This catches people who try to sync the B2 repository to a local copy (see above). Keep B2 as write-only during normal operations.

**After emptying the bucket:** Kopia's config file still points to B2 but the repository metadata is gone. Reconnect with `kopia repository create s3 ...` to reinitialize (this overwrites the existing config to point to the now-empty bucket).

---

## Deploying Kopia on k3s

Kopia runs as a Kubernetes Deployment with a web UI accessible at `https://kopia.lab.hiteshp.in`:

```yaml
containers:
  - name: kopia
    image: kopia/kopia:latest
    args:
      - server
      - start
      - --insecure
      - --address=0.0.0.0:51515
      - --server-username=admin
      - --server-password=kopia-admin
      - --password=$(KOPIA_PASSWORD)
      - --no-grpc
```

The `--password` flag auto-connects the server to the repository on startup. Without it, the UI shows a setup wizard on every restart.

**AppArmor note:** the same AppArmor issue that affects postgres also affects Kopia if you're running signal-intensive operations. Add the unconfined annotation if you see permission errors in Kopia logs.

The CronJob is separate from the server deployment — it runs `kopia snapshot create` directly against both repositories on a schedule, independent of the server pod.

---

## Useful Makefile Targets

```bash
make kopia-snapshots        # list all B2 snapshots
make kopia-snapshots-local  # list all pendrive snapshots
make kopia-stats            # B2 storage usage
make kopia-backup-now       # trigger manual backup via CronJob
make kopia-backup-b2        # run B2 backup directly (foreground)
make kopia-backup-local     # run pendrive backup directly (foreground)
```

---

## What This Protects Against

| Failure | B2 | Pendrive | Primary |
|---------|-----|---------|---------|
| Accidental file deletion | ✅ | ✅ | ❌ |
| NVMe drive failure | ✅ | ✅ | ❌ |
| Pendrive lost/stolen | ✅ | ❌ | ✅ |
| House fire / flood | ✅ | ❌ | ❌ |
| Internet outage | ❌ | ✅ | ✅ |

The B2 offsite copy is the safety net for physical disasters. The pendrive is the fast local restore when you accidentally delete something. The primary NVMe is where you work from day to day.
