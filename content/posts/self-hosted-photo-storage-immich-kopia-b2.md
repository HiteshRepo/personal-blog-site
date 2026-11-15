---
title: "The Complete Self-Hosted Photo Storage Stack: Immich + Kopia + Backblaze B2"
date: 2026-11-15T17:30:00+05:30
summary: "Replace Google Photos and iCloud with a fully self-hosted photo library on your own hardware — private, properly backed up, and feature-complete. This covers the full stack: Immich for the library, Kopia for backups, and Backblaze B2 for offsite storage."
draft: false
ai_generated: true
tags: ["immich", "kopia", "backblaze", "self-hosted", "homelab", "k3s", "kubernetes", "photo-management", "backup", "privacy"]
categories: []
---

> **Note:** This post was AI-generated from rough notes using the blog generation workflow.

Every month, cloud photo storage gets slightly more expensive or slightly more restrictive. Google Photos stopped offering unlimited free storage. iCloud is $1-3/month for enough space. Both services use your photos in ways you didn't explicitly agree to.

This post covers the full stack I built to replace both: Immich for the photo library, Kopia for backups, and Backblaze B2 for offsite storage — running on a single Lenovo laptop in my home.

---

## Hardware

One machine handles everything:

- **Lenovo Legion Y540** (Intel i5-9300H, 16GB RAM, Nvidia GTX 1650)
- **476GB NVMe** — OS, k3s, Immich library
- **931GB external HDD** — DSLR photos, documents
- **29GB USB pendrive** — Kopia local backup repository
- **Ubuntu 22.04 + k3s** — the platform

The GPU handles Immich's ML features (face detection, CLIP embeddings) locally. CPU works too, just slower.

---

## Layer 1 — Immich: The Library

[Immich](https://immich.app) is the self-hosted Google Photos alternative that actually competes feature-for-feature:

- Timeline view with infinite scroll
- Face recognition and grouping (ML, local)
- CLIP semantic search — "find photos of birthday cake" actually works
- Albums, sharing, favorites, archive
- iOS/Android apps with background backup
- Partner sharing

It runs as a k3s workload with five components: server, machine-learning, postgres (with VectorChord for vector search), valkey, and a 200GB PVC for the library.

### What I imported

| Source | Photos | Notes |
|--------|--------|-------|
| iPhone | 794 | Via Immich iOS app auto-backup |
| Google Photos | 1,583 | Via Google Takeout + Immich CLI |
| iPad | 102 | Via Immich iPadOS app |
| Shared albums | 67 | Uploaded via CLI |
| **Total unique** | **~2,400** | Duplicates auto-deduplicated |

The face recognition identified 9 people automatically from 2,400 photos. No manual tagging. Places were also auto-detected.

### Mobile access

iOS/iPadOS can't use `/etc/hosts` for local DNS, so `immich.lab.hiteshp.in` won't resolve on mobile. The workaround: expose via NodePort and connect the app directly to `http://<node-ip>:30283`. Works on the same WiFi without any router configuration.

---

## Layer 2 — Kopia: The Backup Engine

[Kopia](https://kopia.io) handles the backup side. Before any data leaves the machine, it:

- **Deduplicates** — only changed blocks after the first backup
- **Compresses** — zstd (meaningful for databases and text, near-zero for photos)
- **Encrypts** — AES256-GCM with a password you control

The encrypted chunks go to two independent repositories every night at 2AM:

```
Lenovo NVMe → Kopia → Backblaze B2 (offsite)
Lenovo NVMe → Kopia → USB Pendrive (local)
```

What gets backed up nightly:

- Immich photo library (NVMe PVC)
- Immich postgres (albums, faces, metadata)
- k3s SQLite database (cluster state + secrets)
- Open WebUI chat history
- Personal documents

---

## Layer 3 — Backblaze B2: Offsite Storage

[Backblaze B2](https://www.backblaze.com/cloud-storage) is S3-compatible object storage at $6/TB/month — 10x cheaper than AWS S3. The 10GB free tier covers everything except raw photo files.

Kopia connects via the S3 API. B2 only ever receives encrypted blobs — it cannot see your photos even if the account is compromised.

---

## Storage Architecture

```
NVMe (476GB)
├── OS + k3s + apps          ~73GB
├── Immich library           ~8GB (growing)
└── Free                    ~366GB

External HDD (931GB)
├── DSLR photos              ~20GB (d750, engagement, z6)
├── Docs                     ~100MB
└── Free                    ~910GB

Pendrive (29GB)
└── Kopia local repository   ~21GB (all sources)

Backblaze B2 (10GB free)
└── Kopia offsite repository ~8.8GB (excl. DSLR photos)
```

The DSLR photos (20GB RAW files) don't fit in the B2 free tier. They live on the external HDD as an Immich external library — files stay on the HDD, not duplicated to NVMe — and are backed up to the pendrive only until the B2 plan is upgraded.

---

## Migration Path

The migration from Google Photos to Immich took one afternoon:

1. **Google Takeout** — export from takeout.google.com (2-3 hours for 4.4GB)
2. **Install Immich CLI** — `npm install -g @immich/cli@<server-version>` (version must match exactly)
3. **Upload** — `immich upload --recursive "/path/to/Takeout/Google Photos"`
4. **Verify** — check asset count, timeline, albums
5. **Delete** — Google Photos and iPhone originals after 1 week of Immich as primary

The CLI deduplication handles overlap automatically — photos already in Immich from the iPhone backup are skipped by file hash.

---

## What This Replaces

| Was using | Replaced by | Monthly cost |
|-----------|------------|--------------|
| Google One (100GB) | Immich on own hardware | $0 |
| iCloud+ (50GB) | Immich on own hardware | $0 |
| Google Drive storage | External HDD | $0 |
| — | Backblaze B2 (optional) | ~$0.05 for free tier |

The hardware cost (NVMe + external HDD + pendrive) is a one-time expense. The ongoing cost is electricity.

---

## Limitations Worth Knowing

**No automatic offsite for large photo collections.** DSLR RAW files (20GB) exceed the B2 free tier. The options are: upgrade to paid B2 (~$1/month for my volume), or accept local-only backup for those files until ready to pay.

**Single-node k3s has no redundancy.** If the NVMe dies, you restore from the Kopia backup. Recovery time depends on how much data needs to be pulled from B2 or the pendrive.

**Mobile apps need local WiFi.** The NodePort approach works on home WiFi. Tailscale would extend this to work from anywhere, but that's a separate setup.

---

## The Stack in One Diagram

```
iPhone/iPad ──────────────────────────────────► Immich (k3s)
                                                      │
Google Photos ──► Takeout ──► immich CLI ─────────────┘
                                                      │
DSLR photos ──────────────────► External HDD ─► Immich External Library
                                      │
                                      └──────────────────────────────┐
                                                                     ▼
Immich PVC ──────────────────────────────► Kopia ──► Backblaze B2
Postgres PVC ────────────────────────────► Kopia ──► Pendrive
k3s SQLite ──────────────────────────────► Kopia
Docs ────────────────────────────────────► Kopia
```

Three layers. One laptop. No monthly cloud subscription.
