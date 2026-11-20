# Semantic Photo Search with Immich's CLIP API: Build Your Own Search UI

- type: technical
- tags: immich, clip, semantic-search, nginx, kubernetes, web-speech-api, javascript, self-hosted

- The problem: Immich has powerful CLIP-based semantic search built in, but it's buried inside the app — no way to quickly search from a home screen shortcut or share it with family
- Solution: a standalone web UI (`immich-search`) deployed in K3s that wraps Immich's `POST /api/search/smart` endpoint with a clean search interface, voice input, and lightbox
- Immich's search stack: `machine-learning` container generates CLIP embeddings for every uploaded photo; `postgres:16-vectorchord0.4.3` stores them; `vchord` does approximate nearest-neighbor search — all in-cluster, no external API calls
- The `POST /api/search/smart` endpoint is stable since v2: accepts a `query` string and returns ranked assets with thumbnails, EXIF, dimensions — full natural language search, no keyword matching
- CORS problem: browser at `search.hiteshpattanayak.com` can't make API calls to `immich.hiteshpattanayak.com` due to cross-origin restrictions — fix is an nginx reverse proxy in the same pod that injects the `x-api-key` header server-side
- `?key=` query param vs `x-api-key` header: Immich only accepts API keys via header for most endpoints; `?key=` is for share tokens only — this silently breaks thumbnail loading in `<img src>` tags where you can't set headers
- nginx envsubst trick: store the API key in a Kubernetes Secret, pass as `IMMICH_API_KEY` env var, mount nginx config as a template at `/etc/nginx/templates/default.conf.template` — the official nginx image runs envsubst at startup and writes the final config
- Voice search via Web Speech API: `window.webkitSpeechRecognition` works on iOS Safari 14.5+ and all Chrome versions; tap to start, transcript auto-fills the search box and submits — zero backend changes required
- Lightbox preview 401: `size=thumbnail` works with session cookies but `size=preview` requires explicit `x-api-key` header — fixed by fetching preview via JS `fetch()` with the header and converting to a blob URL
- Deployment: single ConfigMap holds both `nginx.conf` template and `index.html`; subPath volume mounts don't auto-update when ConfigMap changes — pod must be restarted after every ConfigMap change (ArgoCD selfHeal triggers rollout but the pod restarts before the new ConfigMap propagates to the node)
- Making it a PWA: `<meta name="apple-mobile-web-app-capable" content="yes">` + `theme-color` meta tag + "Add to Home Screen" in Safari gives full-screen app experience on iPhone/iPad with no browser chrome
- Cloudflare Tunnel exposes it publicly at `search.hiteshpattanayak.com` — works from anywhere without VPN or /etc/hosts; nginx handles auth so no credentials in browser
