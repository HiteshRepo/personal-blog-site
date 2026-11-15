---
title: "Migrating from Google Photos to Self-Hosted Immich"
date: 2026-11-15T16:30:00+05:30
summary: "How to export your entire Google Photos library, import it into self-hosted Immich with automatic deduplication, and safely delete from Google — including the CLI version gotcha that silently fails all uploads."
draft: false
ai_generated: true
tags: ["immich", "google-photos", "self-hosted", "privacy", "photo-management", "google-takeout"]
categories: []
---

> **Note:** This post was AI-generated from rough notes using the blog generation workflow.

Google Photos is convenient. It's also 15GB of free storage shared with Gmail, increasingly expensive when you exceed it, and a service where your photos train Google's AI models. If you've set up a self-hosted Immich instance and want to get your photos off Google, this is the migration path.

---

## What You're Moving

Before starting, check Google Photos storage at `photos.google.com → Settings → Storage`. This tells you how big the Takeout export will be. In my case: 4.4GB across photos going back to 2020.

The migration has four steps:

1. Export from Google (Takeout)
2. Import into Immich via CLI
3. Verify everything landed correctly
4. Delete from Google

---

## Step 1 — Google Takeout Export

Go to [takeout.google.com](https://takeout.google.com):

1. Click **Deselect all** — you only want Photos, not Drive/Gmail/etc.
2. Scroll down and check **Google Photos** only
3. Click **Next step**
4. Choose: Export once, `.zip` format, **2GB chunk size**
5. Click **Create export**

Google emails you download links when it's ready — usually 1-2 hours for a few GB, potentially days for large libraries. Download all the zip files.

The export structure looks like this:

```
Takeout/
└── Google Photos/
    ├── Photos from 2020/
    ├── Photos from 2021/
    ├── Photos from 2022/
    ├── Kumara Purnima 2023/
    ├── Memories together/
    └── ...
```

Each folder contains the original files plus `.json` sidecar files with metadata. Immich reads the EXIF data directly from the image files for dates — the JSON sidecars are ignored.

---

## Step 2 — Install Immich CLI

```bash
npm install -g @immich/cli
```

**Critical:** The CLI version must match your Immich server version exactly.

```bash
immich --version  # must match server version in UI
```

If versions don't match, the CLI will return exit code 0 and appear to succeed, but every single upload will silently fail with a `deviceAssetId` validation error. You won't know until you check the asset count in the UI and find nothing changed.

To find the right version:

```bash
# Check server version in Immich UI: Profile → About
npm install -g @immich/cli@2.6.3  # replace with your server version
```

---

## Step 3 — Upload via CLI

Log in with an API key (generate one in Immich: Profile → Account Settings → API Keys → New Key → Select All permissions):

```bash
immich login http://<server-ip>:<port> <your-api-key>
```

Then upload the extracted Takeout directory:

```bash
immich upload --recursive "/path/to/Takeout/Google Photos"
```

The CLI shows a progress bar and final summary:

```
Found 1612 new files and 941 duplicates
Successfully uploaded 1583 new assets (2.1 GB)
Skipped 29 duplicate assets (43 MB)
```

Duplicates are detected by file hash — if the same photo was already in Immich from an iPhone backup, it's automatically skipped. No manual deduplication needed.

---

## Step 4 — Verify

Don't delete from Google until you've verified. Check:

**Asset count:** Profile → Account Stats in Immich. The number should match what you expected.

**Timeline:** Scroll through 2020, 2021, 2022. Do events look right? Are dates correct?

**Albums:** Google Photos albums are imported as folders in the Takeout structure — they appear in Immich's timeline by date, not as separate albums. If you care about preserving album structure, you'll need to recreate them manually.

**Face recognition:** Immich runs ML locally and auto-groups photos by person. After import you should see known faces under Explore → People.

**Spot-check specific photos:** Think of 3-4 memorable events (holiday, birthday, trip) and confirm those photos are there.

---

## Freeing Up iPhone Storage

If you also backed up your iPhone to Immich, use the **Free Up Space** feature in the Immich iOS app rather than manually deleting from the Photos app. It only deletes photos that are confirmed uploaded — photos that failed to back up stay on the device automatically.

The 13 photos that failed in my case (usually HEIC conversion edge cases) stayed safely on the device.

---

## Deleting from Google

Once you're confident everything is in Immich:

1. Go to `photos.google.com`
2. Select all photos (Shift+Click from first to last)
3. Delete → move to Trash
4. Empty Trash

This frees up the Google storage quota. In my case: 4.4GB freed, dropping from 11.7GB to 7.3GB used out of 15GB free tier.

---

## Results

| Source | Photos uploaded | Duplicates skipped |
|--------|----------------|-------------------|
| iPhone | 794 | — |
| Google Photos | 1,583 | 941 (already from iPhone) |
| Shared album | 67 | 4 |
| **Total unique** | **~2,400** | — |

The face recognition detected 9 people automatically from 2,400 photos with no manual tagging. Places were also detected — Bhubaneswar, Dubai, Cuttack, among others.

---

## Why Bother

- **Privacy:** Immich runs entirely on your hardware. No cloud ML processing, no data training.
- **Cost:** No Google One subscription. Storage costs are your hardware.
- **No limits:** 200GB PVC today, expand anytime.
- **Features:** Face recognition, CLIP semantic search ("find photos of birthday cakes"), timeline, sharing — feature parity with Google Photos for personal use.

The migration takes an afternoon. The peace of mind from owning your own photo library is permanent.
