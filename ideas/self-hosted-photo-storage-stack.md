# The Complete Self-Hosted Photo Storage Stack: Immich + Kopia + Backblaze B2

- type: technical
- tags: immich, kopia, backblaze, self-hosted, homelab, k3s, kubernetes, photo-management, backup, privacy

- Goal: replace Google Photos + iCloud with a fully self-hosted photo storage system that is private, free (or nearly free), and properly backed up
- The problem with cloud photo storage: Google/Apple train on your photos, storage costs grow over time ($3-10/month), you don't control your data, vendor lock-in
- Hardware: single Lenovo Legion laptop (Intel i5, 476GB NVMe, Nvidia GPU) running Ubuntu + k3s + 931GB external HDD
- The three-layer stack: Immich (primary library + AI features) + Kopia (backup engine) + Backblaze B2 (offsite storage)

## Layer 1 — Immich: Primary Library
- Self-hosted Google Photos alternative with face recognition, CLIP semantic search, timeline, albums, sharing
- Runs as k3s workload with 200GB NVMe PVC for library storage
- Mobile apps for iOS/iPadOS auto-backup
- Postgres with VectorChord extension for vector similarity search (powers "find photos with dogs on beach" style queries)
- Machine learning container handles face detection and CLIP embeddings locally — no cloud API calls
- Sources imported: iPhone (794), Google Photos (1,583), iPad (102), shared albums (67) — 2,395 unique assets
- Deduplication by file hash — same photo from multiple sources stored once

## Layer 2 — Kopia: Backup Engine
- Runs alongside Immich in k3s, backs up Immich library + postgres + k3s cluster state nightly
- Encrypts everything locally before it leaves the machine (AES256-GCM)
- Deduplicates across backups — only changed blocks uploaded (crucial for incremental photo library backups)
- Two independent repositories: Backblaze B2 (offsite) + USB pendrive (local)
- Retention: 7 daily / 4 weekly / 12 monthly snapshots

## Layer 3 — Backblaze B2: Offsite Storage
- S3-compatible object storage at $6/TB/month — 10x cheaper than AWS S3
- 10GB free tier covers cluster state + app data + photo metadata (not raw photos if large library)
- Kopia encrypts before upload — B2 only stores opaque encrypted chunks, cannot read your photos
- Free tier limit: plan storage before large uploads. 20GB of DSLR RAW photos exceeded the free tier

## Migration path from Google Photos
- Google Takeout export (zip), extract, upload via immich CLI (npm install -g @immich/cli, version must match server)
- CLI version mismatch gives exit code 0 but silently fails — always verify by checking asset count in UI after upload
- After verification: "Free Up Space" in Immich iOS app clears iPhone originals of confirmed-uploaded photos only
- Delete from Google Photos to free storage quota

## Storage architecture
- NVMe: OS + k3s + Immich library (photos from phones/Google) — 366GB free
- External HDD (931GB ext4): DSLR RAW photos (20GB) + personal docs — photos stay here as Immich external library, not duplicated to NVMe
- Pendrive (29GB): Kopia local backup repository — all Immich data + DSLR photos backed up here nightly
- B2: Kopia offsite backup — Immich library, postgres, cluster state (not DSLR photos until B2 upgraded to paid)

## What this replaces
- Google Photos ($3-10/month) → free (Immich on own hardware)
- iCloud Photos ($1-3/month) → free
- Google Drive storage for docs → external HDD
- No recurring cloud storage costs except optional B2 (~$1/month when upgraded to paid)

## Lessons learned
- AppArmor on k3s blocks signals between processes — postgres and Kopia both affected. Fix: unconfined annotation
- Mobile apps need local DNS or NodePort — /etc/hosts doesn't work on iOS/iPadOS
- Kopia pendrive sync (sync-to filesystem) downloads from B2 consuming bandwidth cap — wrong approach. Use two independent repositories instead
- B2 free tier 1GB/day download cap is easy to hit during troubleshooting. Plan storage before uploading
- Immich CLI version must exactly match server version — check both before bulk uploads
- Don't delete from source until verified in destination — spend a week using Immich first
