# hiteshpattanayak.info

Personal blog and portfolio site built with [Hugo](https://gohugo.io/), themed with
[gohugo-theme-ananke](https://github.com/theNewDynamic/gohugo-theme-ananke), deployed on Netlify.

## Stack

- **Hugo** — static site generator
- **Netlify** — hosting, CI/CD, serverless functions
- **Netlify Functions (Node.js)** — AI chat backend with TF-IDF retrieval
- **OpenAI / Anthropic** — chat completions (SSE streaming)
- **Upstash Redis** — rate limiting for the chat function
- **Google Analytics 4** — page view and chat event tracking

## Local Development

Requires [Netlify CLI](https://docs.netlify.com/cli/get-started/) for the AI chat to work locally.

```bash
# Install dependencies
npm install

# Start full dev environment (Hugo + Netlify Functions proxied through port 8888)
netlify dev

# Hugo only (no chat function)
make serve
```

All automation is in the `Makefile`:

```bash
make serve          # Hugo dev server with drafts (port 1313)
make build          # Production build
make clean          # Remove public/
make preview        # Preview production build locally
make check          # Check for drafts and validate build

# Content
make new-tech TITLE='My Post Title'      # Technical post
make new-ai TITLE='My Post Title'        # AI post
make new-nontech TITLE='My Post Title'   # Opinion/non-technical post
make publish FILE=content/posts/my-post.md

# Linting
make lint-md        # Lint markdown
make lint-md-fix    # Auto-fix markdown issues
```

## AI Chat Assistant

A RAG-powered chat widget on every page — answers questions about posts, projects, and experience.

### Architecture

- **Knowledge base** — built from all published posts, projects, and resume at deploy time
- **Retrieval** — TF-IDF scoring with synonym expansion, title boosting, and per-page priority context
- **Backend** — `netlify/functions/chat.mjs` (Netlify Functions v2, ESM)
- **Frontend** — `static/js/chat.js` (SSE streaming reader)
- **Rate limiting** — Upstash Redis REST API (20 requests/IP/hour)

### Building the knowledge base

```bash
python3 scripts/build-knowledge-base.py
```

Runs automatically as part of the Netlify build command. Output is
`netlify/functions/knowledge-base.json` (gitignored — generated at build time).

### Environment variables

Set these in Netlify Dashboard → Site configuration → Environment variables:

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Yes (default) | OpenAI API key |
| `ANTHROPIC_API_KEY` | If using Anthropic | Anthropic API key |
| `AI_PROVIDER` | No | `openai` (default) or `anthropic` |
| `UPSTASH_REDIS_REST_URL` | No | Upstash Redis URL for rate limiting |
| `UPSTASH_REDIS_REST_TOKEN` | No | Upstash Redis token |

For local dev, add to a `.env` file (picked up automatically by `netlify dev`).

## AI-Assisted Blog Generation

Posts can be generated from structured idea files using an AI script.

### Local generation

```bash
export ANTHROPIC_API_KEY=your_key
make generate FILE=ideas/path-to-ideas-file.md
```

Output lands in `content/posts/<slug>.md` with `draft: true`.

### GitHub Actions generation

Go to **Actions → Generate Blog Post → Run workflow**

- `file` — path like `ideas/llm-foundation/blog-1.md`
- `provider` — `claude` (default) or `openai`

Commits with `[skip ci]` and creates a version tag.

### Ideas file format

```text
# Blog Title Here
- type: ai          # ai | technical | nontech
- tags: tag1, tag2
- bullet point for content
- another bullet
```

## Content Structure

```text
content/
  posts/       — blog posts (technical, AI, opinion)
  projects/    — project showcase pages
ideas/         — source material for AI-generated posts
scripts/
  generate_post.py         — AI blog generation script
  build-knowledge-base.py  — knowledge base builder
netlify/functions/
  chat.mjs     — AI chat serverless function
static/js/
  chat.js      — chat widget frontend (SSE client)
layouts/
  partials/chat-widget.html        — inline widget (about page)
  partials/chat-widget-float.html  — floating widget (posts/projects)
  posts/single.html                — post layout override (injects float widget)
  projects/single.html             — project layout override (injects float widget)
```

## Deployment

Netlify deploys automatically on every push to `main`. The build command:

1. Runs `python3 scripts/build-knowledge-base.py` — generates knowledge base JSON
2. Runs `hugo --gc --minify --buildFuture` — builds the static site
3. Bundles `netlify/functions/chat.mjs` with esbuild — packages the chat function

## CI / Quality Gates

GitHub Actions run on every push and PR:

- `markdown-lint.yml` — markdownlint (config: `.markdownlint.json`)
- `spell-check.yml` — cspell (config: `.cspell.json`)
- `link-checker.yml` — validates all markdown links
- `main.yaml` — GPTScript automated PR review
