# Migrating from Google Photos to Self-Hosted Immich

- type: technical
- tags: immich, google-photos, self-hosted, privacy, photo-management, google-takeout

- Goal: migrate all photos/videos from Google Photos and iPhone to self-hosted Immich, then delete from Google to free up storage
- Why: privacy (Google trains on your photos), cost (Google One subscription), control (your data on your hardware)
- Sources migrated: iPhone (794 photos), Google Photos (1,583 photos via Takeout), iPad (102 photos), shared album (67 photos) — 2,395 unique assets total
- Step 1 — iPhone backup: install Immich iOS app, connect to self-hosted server, enable background backup. Use direct NodePort URL (http://<server-ip>:30283) since iPhone can't use /etc/hosts for local DNS
- Step 2 — Google Takeout export: go to takeout.google.com, select only Google Photos, choose zip format with 2GB chunks. 4.4GB export splits into 3 zip files. Usually ready within 1-2 hours
- Step 3 — Install Immich CLI: npm install -g @immich/cli — IMPORTANT: version must match server version (immich --version should match server version shown in UI). Mismatched CLI gives misleading exit code 0 but silently fails all uploads with deviceAssetId validation errors
- Step 4 — Upload via CLI: immich login <server-url> <api-key> then immich upload --recursive <path-to-extracted-takeout>
- Deduplication: Immich deduplicates by file hash — 941 Google Photos were already on iPhone so were skipped automatically. No manual cleanup needed
- Google Takeout structure: Takeout/Google Photos/ with folders per year (Photos from 2020, etc.) and named albums. Immich preserves original dates from EXIF metadata
- After verification: use Immich app "Free Up Space" feature on iPhone — only deletes photos confirmed uploaded, keeps the 13 that failed to back up. For Google Photos: browse files and delete all, then empty trash
- Verification approach: check asset count in Profile → Account Stats, spot-check timeline by year, verify albums imported correctly, check face recognition picked up known people
- Face recognition results: Immich detected 9 people automatically from 2,395 photos — Hitesh, family members, friends — with no manual tagging
- Lessons: don't rush deletion — use Immich as primary app for a week before deleting sources. The 13 failed iPhone uploads (usually HEIC conversion issues) should be identified before deleting from device
- Storage freed: 4.4GB from Google (back under 15GB free tier), iPhone storage freed via "Free Up Space" without touching failed uploads
- Immich advantages over Google Photos: local AI processing (no cloud), no storage limits beyond your hardware, search by people/places/objects, albums, timeline view — feature parity with Google Photos for personal use
