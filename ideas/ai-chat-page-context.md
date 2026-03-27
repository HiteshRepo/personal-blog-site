# Page-Aware AI Chat: Floating Widget and Per-Page Context

- type: technical
- tags: ai, rag, netlify, hugo, javascript, serverless, openai

- Part 2 of the AI chat series (Part 1 covered the core RAG setup: TF-IDF retrieval, knowledge base builder, Netlify Function, basic inline widget)
- The problem with Phase 1: the chat widget on the homepage worked well for profile/experience questions but had no awareness of which post or project page the visitor was on — asking "summarise this post" returned "I don't have that information"
- Phase 2 goal: every blog post and project page gets its own context-aware floating chat assistant that knows what page it's on
- Floating widget design: fixed bottom-right circular button (🤖), clicking toggles a panel — keeps pages clean without a permanent sidebar taking up space
- Hugo layout overrides: created layouts/posts/single.html and layouts/projects/single.html that extend the theme's default single template and inject the float widget partial at the end
- Suggested questions per page type: post pages get "Summarise this post", "What are the key takeaways?", "What tech is covered?"; project pages get "What tech stack was used?", "What were the key achievements?", "What was Hitesh's role?", "Any AI or data engineering work here?" — chips disappear after first use
- Page slug injection: each page sets window.CHAT_PAGE_SLUG via Hugo template ({{ with .Page.File }}"{{ .BaseFileName }}"{{ else }}null{{ end }}) so the chat function knows the current page
- Priority retrieval: the retrieve() function in chat.js already had pageSlug support from Phase 1 — matching chunks get isPriority=true and are sorted to rank 1 regardless of TF-IDF score
- The key bug: even with the priority chunk at rank 1, the model was answering about ALL projects/posts instead of just the current page — because all 5 context chunks looked identical to the model
- Fix: label the priority chunk as [CURRENT PAGE] in buildContext(), then add a system prompt rule: "When a [CURRENT PAGE] section is present, questions like 'summarise this', 'what tech was used?', 'what were the achievements?' refer to THAT page only"
- System prompt evolution: Phase 1 prompt was designed only for profile/experience questions ("Answer using ONLY post titles, project names, URLs, and facts") — too restrictive for content questions; added two-mode framing: BLOG/PROJECT CONTENT mode (explain from post body) vs PROFILE/EXPERIENCE mode (use facts and links)
- Related content fallback: instead of hard "I don't have that information", model now surfaces related content when exact answer is absent
- Dev environment gotcha: netlify dev proxies Hugo (port 1313) through port 8888 — functions only work via 8888; added [dev] block to netlify.toml to make this explicit; also fixed .Permalink → .RelPermalink in project list template to avoid absolute localhost:1313 links
- The [CURRENT PAGE] label pattern is a lightweight alternative to separate system message slots or tool calls — it works within the existing single-turn context window without any extra infrastructure
- Lesson: when building RAG systems, retrieval correctness (getting the right chunk) is only half the problem — the other half is prompt framing (telling the model what to do with the priority content)
