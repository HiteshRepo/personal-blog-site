---
title: "Page-Aware AI Chat: Floating Widget and Per-Page Context"
date: 2026-03-27T14:48:36-07:00
summary: "A practical walkthrough of adding per-page context awareness to a floating AI chat widget built with Hugo and Netlify Functions, covering layout overrides, slug injection, priority chunk labeling, and the prompt engineering fix that made summarise-this-post actually work."
draft: false
ai_generated: true
tags: ["ai", "rag", "netlify", "hugo", "javascript", "serverless", "openai"]
categories: []
---

> **Note:** This post was AI-generated from rough notes using the blog generation workflow.

In [Part 1](/) of this series, I set up a basic RAG-powered chat widget: TF-IDF retrieval, a knowledge base builder, a Netlify Function as the backend, and a simple inline widget on the homepage. It worked well for questions about my profile and experience. Ask it "what have you worked on in data engineering?" and it'd pull the right chunks and give a solid answer.

But there was an obvious gap. On a blog post or project page, asking "summarise this post" got back: *"I don't have that information."* The widget had no idea which page it was sitting on. That's what Phase 2 fixes.

## The Goal

Every blog post and project page should have its own context-aware floating chat assistant. It should know what page it's on, surface relevant suggested questions, and when someone asks "what tech was used here?" it should answer about *this* page — not all five of my projects at once.

## Floating Widget Design

The first decision was layout. A permanent sidebar or inline widget takes up real estate and feels heavy for a personal site. Instead, I went with a fixed bottom-right circular button that toggles a panel on click — stays out of the way until someone actually wants it.

```html
<!-- partials/float-widget.html -->
<div id="chat-fab" onclick="toggleChatPanel()">🤖</div>
<div id="chat-panel" class="chat-panel hidden">
  <div id="chat-messages"></div>
  <div id="suggestion-chips"></div>
  <div class="chat-input-row">
    <input id="chat-input" type="text" placeholder="Ask me anything..." />
    <button onclick="sendMessage()">Send</button>
  </div>
</div>
```

The panel renders suggestion chips based on page type, which I'll get to shortly. Clean, no permanent sidebar, pages stay readable.

## Hugo Layout Overrides

Hugo's layout lookup means I can drop a file at `layouts/posts/single.html` and it'll override the theme's default for that content type without touching the theme itself.

```html
<!-- layouts/posts/single.html -->
{{ define "main" }}
  {{ template "main" .SuperTemplate }}
  {{ partial "float-widget.html" (dict "page" . "pageType" "post") }}
{{ end }}
```

Same pattern for `layouts/projects/single.html`. The partial gets the current page context and a `pageType` string so it can render the right suggestion chips.

### Suggested Questions Per Page Type

Post pages get:

- "Summarise this post"
- "What are the key takeaways?"
- "What tech is covered?"

Project pages get:

- "What tech stack was used?"
- "What were the key achievements?"
- "What was Hitesh's role?"
- "Any AI or data engineering work here?"

The chips disappear after first use — one click, chip gone, question sent. Keeps the UI tidy.

```javascript
function renderChips(chips) {
  const container = document.getElementById('suggestion-chips');
  chips.forEach(text => {
    const btn = document.createElement('button');
    btn.className = 'chip';
    btn.textContent = text;
    btn.onclick = () => {
      btn.remove();
      sendMessage(text);
    };
    container.appendChild(btn);
  });
}
```

## Injecting the Page Slug

The chat function needs to know which page it's on. The cleanest way to do this in Hugo is a small inline script in the layout partial:

```html
<script>
  window.CHAT_PAGE_SLUG = {{ with .Page.File }}"{{ .BaseFileName }}"{{ else }}null{{ end }};
</script>
```

`BaseFileName` gives you `my-post-slug` without the extension. This gets sent with every chat request so the retrieval function can prioritise matching chunks.

The retrieve function in `chat.js` already had `pageSlug` support wired in from Phase 1 — any chunk whose source filename matches the slug gets flagged `isPriority: true` and sorted to position 0 regardless of its TF-IDF score:

```javascript
function retrieve(query, pageSlug, topK = 5) {
  const scores = computeTFIDF(query);
  return scores
    .map(chunk => ({
      ...chunk,
      isPriority: pageSlug && chunk.source.includes(pageSlug)
    }))
    .sort((a, b) => b.isPriority - a.isPriority || b.score - a.score)
    .slice(0, topK);
}
```

## The Bug: Retrieval Was Right, the Model Was Still Wrong

Here's where it got interesting. Even with the priority chunk sitting at rank 1, when I asked "summarise this post" the model would start talking about all my projects. Every chunk in the context window looks the same to the model — there's no signal distinguishing "this one is the page you're on" from "these are background context chunks."

The fix was straightforward once I framed it clearly: label the priority chunk explicitly, then tell the model what that label means.

### Labeling the Priority Chunk

In `buildContext()`, priority chunks get a `[CURRENT PAGE]` header:

```javascript
function buildContext(chunks) {
  return chunks.map(chunk => {
    const label = chunk.isPriority ? '[CURRENT PAGE]\n' : '';
    return `${label}${chunk.text}`;
  }).join('\n\n---\n\n');
}
```

### Updating the System Prompt

The Phase 1 system prompt was scoped tightly for profile/experience questions: *"Answer using ONLY post titles, project names, URLs, and facts from the context."* Too restrictive — it choked on content questions asking for explanation or summary.

Phase 2 adds a two-mode framing:

```text
You are an AI assistant for Hitesh's personal site.

Context sections labeled [CURRENT PAGE] are the primary source. When a [CURRENT PAGE] section is present, questions like "summarise this", "what tech was used?", "what were the achievements?" refer to THAT page only — do not blend in other projects or posts.

Use two modes based on the question:
- BLOG/PROJECT CONTENT: If asking about a specific post or project, explain from the [CURRENT PAGE] body. You can paraphrase and summarise.
- PROFILE/EXPERIENCE: If asking about background, skills, or experience generally, use facts and links from the broader context.

If you don't have enough detail, surface related content rather than saying "I don't have that information".
```

That last line matters. "I don't have that information" is a dead end. Surfacing something related keeps the conversation alive and is usually more useful anyway.

## Dev Environment Gotcha

Running `netlify dev` proxies Hugo (port 1313) through port 8888. Netlify Functions only work through the 8888 proxy — if you're hitting `localhost:1313` directly, function calls fail silently. Obvious in hindsight, but worth spelling out.

I added an explicit `[dev]` block to `netlify.toml`:

```toml
[dev]
  command = "hugo server"
  port = 8888
  targetPort = 1313
  publish = "public"
```

While I was in there, I also caught that the project list template was using `.Permalink` instead of `.RelPermalink` for links — which generates absolute `localhost:1313/...` URLs in dev that break in production. Switched to `.RelPermalink` throughout.

## Why [CURRENT PAGE] Instead of Something More Elaborate

You could handle this with separate system message slots, a tool call architecture, or a dedicated per-page function endpoint. All of those are heavier. The `[CURRENT PAGE]` label works within the existing single-turn context window — no extra infrastructure, no changes to the function routing, no additional API surface.

It's a lightweight convention: the label carries semantic weight that the model interprets correctly when the system prompt explains it. For a personal site running on Netlify's free tier, that tradeoff is exactly right.

## What This Unlocks

After these changes, the experience is noticeably different. On a post about building a data pipeline:

- "Summarise this post" → concise summary of *that post*
- "What tech is covered?" → pulls from the post body, not a guess from other chunks
- "Tell me about your experience with Kafka" → switches to profile mode, surfaces the right background context

The suggested chips lower the activation energy for visitors who aren't sure what to ask. Page-specific questions are answered from page-specific content. Generic questions still work fine.

## Conclusion

The retrieval side of RAG gets a lot of attention — embedding strategies, chunk sizes, similarity metrics. But getting the right chunk into position 1 is only half the problem. The other half is prompt framing: giving the model enough signal to know *what to do* with the priority content once it has it.

The `[CURRENT PAGE]` label is a small change with a disproportionate effect. Combined with Hugo layout overrides for per-page widget injection and the two-mode system prompt, the chat assistant now behaves like it actually belongs on each page — which is exactly what it should feel like.

Part 3 will look at adding conversation memory across page navigations and potentially moving the knowledge base build step into a proper CI pipeline step.
