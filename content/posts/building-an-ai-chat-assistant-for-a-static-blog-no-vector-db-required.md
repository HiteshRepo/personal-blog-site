---
title: "Building an AI Chat Assistant for a Static Blog — No Vector DB Required"
date: 2026-03-27T12:54:33-07:00
summary: "A practical walkthrough of building a conversational AI assistant for a Hugo static site using TF-IDF retrieval over a flat JSON knowledge base — no vector database, no backend server, no embeddings infrastructure required."
draft: false
ai_generated: true
tags: ["ai", "rag", "netlify", "hugo", "openai", "serverless", "javascript", "python"]
categories: []
---

> **Note:** This post was AI-generated from rough notes using the blog generation workflow.

A few months ago I wanted to add a chat assistant to my personal site — something that could answer questions about my blog posts, projects, and resume without making visitors dig through pages manually. Every tutorial I found pointed at the same stack: embeddings, a vector database, a backend API, maybe a caching layer. For a site with maybe 60 pieces of content, that felt like serious overkill. Here's what I built instead, and why it works fine.

## The Stack

- **Hugo** for the static site
- **Netlify Functions** (serverless Node.js) for the chat endpoint
- **OpenAI gpt-4o-mini** as the primary model, **Anthropic Claude Haiku** as a fallback
- A flat **JSON knowledge base** built by a Python script at deploy time

No vector DB. No embeddings API calls at retrieval time. No persistent backend. The whole retrieval layer is TF-IDF over a JSON file that gets bundled into the serverless function at build time.

## Building the Knowledge Base

A Python script runs before `hugo` in the build pipeline. It reads every markdown file from `content/posts/`, `content/projects/`, and `resume.md`, parses YAML frontmatter, strips markdown syntax (while preserving link URLs as `text (url)`), chunks body text into ~400-word pieces, and writes `netlify/functions/knowledge-base.json`.

```python
def chunk_text(text, slug, title, chunk_type, url, max_words=400):
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_words):
        piece = " ".join(words[i:i + max_words])
        chunks.append({
            "slug": slug,
            "title": title,
            "type": chunk_type,  # "post", "project", "resume"
            "url": url,
            "body": piece
        })
    return chunks
```

Two special entries get added unconditionally: a hardcoded `ABOUT` chunk with contact info, personal facts, and a career summary, and a `TIMELINE` array that gets injected into every system prompt. The `ABOUT` chunk exists because some facts — your email address, where you live, what conferences you've spoken at — need to be reliably retrievable regardless of how the query is phrased.

The knowledge base is gitignored. It's generated at build time, not source-controlled.

```toml
# netlify.toml
[build]
  command = "python scripts/build_knowledge_base.py && hugo"
```

## TF-IDF Retrieval in Node.js

The retrieval function lives entirely in the serverless handler. No external library — just a few dozen lines of JavaScript.

```javascript
function score(query, chunks) {
  const tokens = tokenize(expandSynonyms(query));
  
  return chunks.map(chunk => {
    let s = 0;
    const body = tokenize(chunk.body);
    const title = tokenize(chunk.title);
    
    for (const term of tokens) {
      const bodyFreq = body.filter(t => t === term).length / body.length;
      const titleFreq = title.filter(t => t === term).length;
      s += bodyFreq + titleFreq * 3; // 3× title boost
    }
    
    return { ...chunk, score: s };
  });
}
```

After scoring, I deduplicate by slug — keeping only the highest-scoring chunk per document — then return the top 5. This prevents a single long post from flooding the context window with multiple chunks.

### Synonym Expansion

This is where I spent more time than I expected. Natural language queries don't use the same words as your content.

```javascript
const SYNONYMS = {
  k8s: "kubernetes",
  yoe: "experience",
  "years of experience": "experience",
  "reach out": "contact",
  "reach": "contact",
  "contact": "email",
  "current company": "organization",
  "company": "organization",
};
```

Without synonym expansion, "how do I reach you" scores near zero because "reach" doesn't appear in my contact info — "email" and "contact" do. Chain expansions (`reach → contact → email`) let a single query hop through multiple synonyms.

### Type-Filter Boost

When someone asks "what posts have you written about Go?", they want posts, not projects. I add a small score boost for chunk types that match words in the query:

```javascript
if (queryRaw.includes("post") && chunk.type === "post") score += 0.05;
if (queryRaw.includes("project") && chunk.type === "project") score += 0.05;
```

The important detail: type tokens (`post`, `posts`, `project`) get stripped *before* body scoring. Otherwise "post" matches the word "post" inside half your articles and the boost becomes noise.

## Bundling with esbuild

The knowledge base is loaded with `require()` so esbuild can bundle it directly into the function:

```javascript
const kb = require("./knowledge-base.json");
```

Don't use `fs.readFileSync(__dirname + "/knowledge-base.json")`. After esbuild bundles the function, `__dirname` points somewhere in a temp build directory where the JSON no longer exists. The `require()` approach embeds the data at bundle time — no runtime file I/O.

## The System Prompt

A few rules I had to make explicit after the model hallucinated things:

```
- Never invent post titles or project names. Only reference content from the context provided.
- Always copy URLs exactly as they appear in context. Do not construct or guess URLs.
- Format all links as markdown: [Title](url)
- If asked for contact information, list ALL methods present in context.
- If you don't have the information, say "I don't have that information" — do not speculate.
```

One non-obvious lesson: don't include example answers in your system prompt unless you want the model to treat them as templates. I had an example that said `salary: not publicly disclosed` to demonstrate formatting. The model started saying "not publicly disclosed" in response to completely unrelated questions. Removing the example fixed it immediately.

`mailto:` links also need explicit handling in your markdown renderer on the frontend. Most renderers don't auto-link them.

## Pluggable AI Provider

An `AI_PROVIDER` environment variable switches between OpenAI and Anthropic. Same message format, different SDK calls:

```javascript
async function callAI(messages) {
  if (process.env.AI_PROVIDER === "anthropic") {
    const response = await anthropic.messages.create({
      model: "claude-haiku-20240307",
      max_tokens: 1024,
      system: messages[0].content,
      messages: messages.slice(1),
    });
    return response.content[0].text;
  }
  
  // Default: OpenAI
  const response = await openai.chat.completions.create({
    model: "gpt-4o-mini",
    messages,
  });
  return response.choices[0].message.content;
}
```

## Multi-Turn Conversation

Conversation history is kept in browser memory — a simple array of `{role, content}` pairs. Every request sends the full history:

```javascript
const history = [];

async function chat(userMessage) {
  history.push({ role: "user", content: userMessage });
  const response = await fetch("/api/chat", {
    method: "POST",
    body: JSON.stringify({ messages: history }),
  });
  const { reply } = await response.json();
  history.push({ role: "assistant", content: reply });
  return reply;
}
```

No session storage, no database. Works fine for a chat widget that lives in a single page session.

## Debugging Retrieval

I keep a `test-retrieval.js` script that mirrors the retrieval logic and prints the top-8 scored chunks for any query:

```bash
node test-retrieval.js "how many years of experience do you have"
```

```
[1] ABOUT (score: 0.047) — about/contact
[2] resume-chunk-0 (score: 0.031) — resume
[3] senior-engineer-post (score: 0.008) — posts/...
```

This is the most important debugging tool in the project. When the assistant gives a wrong answer, you check retrieval first. Nine times out of ten, the right chunk isn't making it into the top 5 — and the fix is a synonym or a stop word adjustment, not a prompt change.

## What You're Trading Off

TF-IDF can't match "authentication" to "Auth0" unless you add that synonym manually. It won't understand that a question about "shipping features fast" is related to your post on CI/CD pipelines. Vector search handles those cases naturally.

But for a personal site with under 100 content chunks, those edge cases are rare and fixable with targeted synonym additions. What you get in return: zero infrastructure cost, zero embedding latency, a retrieval layer you can read and debug in an afternoon, and a build pipeline that produces a fully self-contained serverless function.

## Wrapping Up

If you're building a chat assistant for a small content site, reach for the simple tool first. A flat JSON file and 50 lines of TF-IDF scoring will handle most questions your visitors actually ask. Save the vector database for when you've outgrown it — and with a good local debugging script, you'll know exactly when that is.
