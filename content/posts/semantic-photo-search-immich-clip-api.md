---
title: "Semantic Photo Search with Immich's CLIP API: Build Your Own Search UI"
date: 2026-11-20T12:00:00+05:30
summary: "Immich has powerful CLIP-based semantic search built in, but it's locked inside the app. I built a standalone web UI that wraps the smart search endpoint with voice input, a lightbox, and nginx header injection — deployed in K3s and exposed publicly via Cloudflare Tunnel."
draft: false
ai_generated: true
tags: ["immich", "clip", "semantic-search", "nginx", "kubernetes", "web-speech-api", "javascript", "self-hosted"]
categories: []
---

> **Note:** This post was AI-generated from rough notes using the blog generation workflow.

Immich does something genuinely impressive out of the box: every photo you upload gets processed by a CLIP machine learning model that generates a semantic embedding. That means you can search for "golden hour on the beach" and it finds sunset photos even if none of them have that caption. No keyword matching. Pure vector similarity. The whole pipeline — ML container, postgres with vectorchord, ANN search — runs entirely in-cluster with no external API calls.

The problem is that this search is buried inside the Immich app. There's no way to put a search shortcut on your iPhone home screen, no way to share a quick search interface with family without also giving them full Immich access. I wanted a lightweight, standalone page that just does search — works from anywhere, works with voice, and feels like a native app on mobile.

This is the story of building that, including the parts that didn't work the first time.

---

## How Immich's Search Actually Works

Before writing any code I poked around the Immich source to understand what I was working with. The smart search endpoint is `POST /api/search/smart` and it's been stable since v2. The request body is simple:

```json
{
  "query": "kids playing in autumn leaves",
  "size": 24
}
```

The response is a ranked list of assets with thumbnails, EXIF data, and dimensions. Under the hood, Immich's machine-learning container runs a CLIP model (ViT-B/32 by default) and generates embeddings for every uploaded photo. Those embeddings live in postgres — specifically in `postgres:16-vectorchord0.4.3`, which is Immich's custom postgres build that bundles the [pgvecto.rs](https://github.com/tensorchord/pgvecto.rs) fork called vchord. When you search, your query string gets embedded with the same CLIP model and vchord does approximate nearest-neighbor lookup against the stored photo embeddings.

None of this requires a GPU at query time. The embeddings are precomputed at upload time (that's the ML container's job), so search itself is just a postgres vector query. Fast and cheap.

The API key goes in the `x-api-key` header. Keep that in mind — it matters later.

---

## The CORS Problem

My first attempt was a plain HTML file with a `fetch()` call directly to `https://immich.lab.hiteshp.in/api/search/smart`. Works fine locally, breaks immediately from any other origin.

```
Access to fetch at 'https://immich.lab.hiteshp.in' from origin 'https://search.hiteshpattanayak.com'
has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present.
```

I could configure Immich to add CORS headers, but that opens up cross-origin requests to the whole Immich API from any origin that knows my search UI's domain — not great. The cleaner approach is a reverse proxy that lives at the same origin as the search UI and proxies API calls to Immich server-side.

This also solves the API key problem. The `x-api-key` header needs to be on every request, but I don't want to hardcode it in the frontend or expose it to the browser. If the nginx proxy injects it server-side, the key never touches the client.

---

## nginx + envsubst: Injecting the API Key from a Secret

The official `nginx` Docker image has a neat trick: if you drop a file at `/etc/nginx/templates/default.conf.template`, nginx runs `envsubst` on it at container startup and writes the result to `/etc/nginx/conf.d/default.conf`. This means you can use shell-style variable substitution in your nginx config and pass values through environment variables.

My nginx config template:

```nginx
server {
    listen 80;

    location / {
        root /usr/share/nginx/html;
        index index.html;
    }

    location /api/ {
        proxy_pass http://immich-server.immich.svc.cluster.local:2283;
        proxy_set_header x-api-key "${IMMICH_API_KEY}";
        proxy_set_header Host immich-server.immich.svc.cluster.local;
    }
}
```

The `${IMMICH_API_KEY}` gets substituted at startup. The Kubernetes Secret holds the actual key:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: immich-search-key
  namespace: immich-search
type: Opaque
stringData:
  api-key: "your-immich-api-key-here"
```

Then in the Deployment, I reference it as an environment variable:

```yaml
env:
  - name: IMMICH_API_KEY
    valueFrom:
      secretKeyRef:
        name: immich-search-key
        key: api-key
```

The whole thing — nginx config template and `index.html` — lives in a single ConfigMap. Both are mounted into the container using `subPath`.

One gotcha I hit: **subPath volume mounts don't auto-update when the ConfigMap changes**. After every ConfigMap change you have to restart the pod:

```bash
kubectl rollout restart deployment/immich-search -n immich-search
```

I forgot this twice before it stuck.

---

## The `?key=` Trap

While debugging thumbnail loading I noticed that images loaded fine in the main search results but were returning 401 when clicked. My first instinct was to append `?key=YOUR_KEY` to the URL — I'd seen this pattern in other APIs. Doesn't work in Immich. The `?key=` query parameter is for share tokens only (the kind you generate when you share an album publicly). For regular API key auth, Immich only accepts the `x-api-key` header. This fails silently: you get a 401 with no hint that you're using the wrong auth method.

The fix is to fetch the preview image via JavaScript `fetch()` and convert it to a blob URL:

```javascript
async function loadPreview(assetId) {
  const resp = await fetch(`/api/assets/${assetId}/thumbnail?size=preview`);
  const blob = await resp.blob();
  return URL.createObjectURL(blob);
}
```

Since all requests go through nginx at `/api/`, the `x-api-key` header is injected server-side. The frontend doesn't need to touch auth at all.

---

## Voice Search with Web Speech API

Adding voice search took about 20 lines of JavaScript and zero backend changes. The Web Speech API works on iOS Safari 14.5+ and all modern Chrome versions.

```javascript
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const recognition = new SpeechRecognition();
recognition.lang = 'en-US';
recognition.interimResults = false;

recognition.onresult = (event) => {
  const transcript = event.results[0][0].transcript;
  document.getElementById('search-input').value = transcript;
  doSearch(transcript);
};

micButton.onclick = () => recognition.start();
```

One iOS gotcha: Speech Recognition requires a direct user gesture. You can't call `recognition.start()` from a `setTimeout` or any async context that's not directly triggered by a tap — Safari silently does nothing.

---

## Making It a PWA

A few meta tags and "Add to Home Screen" in Safari gives full-screen app experience with no browser chrome:

```html
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Photo Search">
<meta name="theme-color" content="#1a1a2e">
```

The full deployment is in [HiteshRepo/k3s-homelab](https://github.com/HiteshRepo/k3s-homelab) under `gitops/manifests/immich-search/`. ArgoCD picks it up automatically on push. Cloudflare Tunnel exposes it at `search.hiteshpattanayak.com` — no VPN, no `/etc/hosts` required on any device.
