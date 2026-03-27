# Building an AI Chat Assistant for a Static Blog — No Vector DB Required

- type: technical
- tags: ai, rag, netlify, hugo, openai, serverless, javascript, python

- The goal: add a conversational AI assistant to a Hugo static site that can answer questions about blog posts, projects, and resume — without a backend server or vector database
- Stack: Hugo (static site generator) + Netlify Functions (serverless Node.js) + OpenAI gpt-4o-mini (with Anthropic Claude as a fallback) + a pre-built JSON knowledge base
- Core insight: for a small personal site (~50-100 chunks of content), TF-IDF retrieval over a flat JSON file is more than sufficient — no embeddings, no vector DB, no extra infrastructure
- Knowledge base builder (Python script): reads all markdown files from content/posts/, content/projects/, and resume.md at build time; parses YAML frontmatter; strips markdown syntax but preserves link URLs as "text (url)"; chunks body text into ~400-word pieces; outputs netlify/functions/knowledge-base.json
- Hardcoded ABOUT chunk: personal facts, contact info, books, conference talks, career summary — anything that needs to be reliably answerable regardless of query
- Career TIMELINE array: structured career history with period, role, tech stack, and summary per entry — injected into every prompt for context
- TF-IDF retrieval in Node.js: tokenize query, filter stop words, apply synonym expansion (k8s→kubernetes, yoe→experience, reach→contact→email, company→organization), score every chunk by term frequency with 3× title boost, deduplicate by slug keeping highest-scoring chunk per document, return top 5 chunks
- Type-filter boost pattern: queries mentioning "posts" or "projects" get a small boost for matching chunk types — but type tokens are stripped before body scoring to avoid "post" matching the word "post" in every article body
- Synonym expansion is critical for natural language queries: "how many years of experience" needs to map to "experience", "current company" needs to map to "organization", "reach out" needs to map to "contact" then "email"
- esbuild bundling: the knowledge base JSON is loaded via require() so esbuild bundles it into the function at deploy time — fs.readFileSync with __dirname fails after bundling because the path changes
- System prompt strict rules: never invent post titles, always copy exact URL from context, always format links as markdown [Title](url), list all contact methods when asked, fall back to "I don't have that information" only if genuinely absent
- Pluggable AI provider: AI_PROVIDER env var switches between openai (gpt-4o-mini, default) and anthropic (claude-haiku) — same message format, different SDK calls
- Build integration: netlify.toml build command runs the Python KB builder first, then hugo — knowledge base is always fresh on every deploy
- The knowledge-base.json is gitignored because it is generated at build time, not source-controlled
- Conversation history passed through on every request for multi-turn chat — kept in browser memory (array of role/content pairs)
- What this approach trades off vs. vector search: no semantic similarity (can't match "authentication" to "auth0" unless synonyms are added), but zero infrastructure cost, zero latency for embedding lookups, and trivially debuggable with a local test script
- Local debugging: test-retrieval.js mirrors the retrieval logic and prints top-8 scored chunks with scores for any query — critical for diagnosing why a question returns wrong results
- Lessons learned: stop words need tuning (generic words like "out", "reach" can dominate scores), example text in system prompts can be treated as templates by the model (removed a stale "not publicly disclosed" example that was causing wrong answers), mailto: links need explicit handling in the markdown renderer
