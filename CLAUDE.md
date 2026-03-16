# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Personal blog/portfolio site built with **Hugo** (static site generator), themed with `gohugo-theme-ananke` (Git submodule), deployed on Netlify.

## Common Commands

All automation is in the `Makefile`:

```bash
make serve          # Local dev server with drafts (hugo server -D)
make build          # Production build: hugo --gc --minify
make clean          # Remove public/ directory
make preview        # Preview production build locally
make check          # Check for drafts and validate build

# Content creation
make new-tech TITLE='My Post Title'      # Technical post
make new-ai TITLE='My Post Title'        # AI-specific post
make new-nontech TITLE='My Post Title'   # Opinion/non-technical post
make publish FILE=content/posts/my-post.md  # Mark draft as published

# Linting
make lint-md        # Lint markdown files
make lint-md-fix    # Auto-fix markdown issues
```

## Architecture

**Hugo configuration:**

- `hugo.toml` — dev config (baseURL = `/`)
- `hugo.production.toml` — production config (Google Analytics, full baseURL)
- `netlify.toml` — Netlify build settings (Hugo v0.134.3, publish dir `public/`)

**Content (`content/`):**

- `posts/` — all blog posts (technical, AI, non-technical)
- `projects/` — project showcase pages
- Posts use `draft: true` frontmatter until published

**Archetypes (`archetypes/`):** Templates for each content type with predefined frontmatter and section stubs. The `make new-*` commands use these.

**Custom layouts (`layouts/`):**

- `index.html` — homepage
- `projects/list.html` — projects page

**Static assets (`static/`):**

- `styles/design-system.css`, `styles/style.css` — custom CSS (style.css is ~33K lines)
- `images/` — post/project images
- `resume/` — resume files

## CI/CD & Quality Gates

GitHub Actions run on push/PR:

- `markdown-lint.yml` — markdownlint with rules in `.markdownlint.json`
- `spell-check.yml` — cspell with custom dictionary in `.cspell.json`
- `link-checker.yml` — validates all markdown links
- `main.yaml` — GPTScript automated PR review (requires `OPENAI_API_KEY` secret)

Linting rules: line length max 500 chars, HTML tags allowed (`br`, `img`, `a`, `div`, `span`, `details`, `summary`). The `.cspell.json` has 280+ whitelisted technical terms — add new domain-specific terms there if spell-check fails.

## Content Frontmatter

Posts require these frontmatter fields (from archetypes):

```yaml
title: "Post Title"
date: YYYY-MM-DDTHH:MM:SS-07:00
draft: true
tags: []
categories: []
```

Set `draft: false` (or use `make publish`) to publish.

## Markdown Rules

Always run `make lint-md` after editing `.md` files. Use `make lint-md-fix` to auto-fix most issues first, then fix the rest manually.

Key rules to follow:

- **Blank lines around headings**: Always add a blank line before and after every heading.
- **Blank lines around lists**: Always add a blank line before and after every list block.
- **Single H1**: Each file may have at most one `#` heading. Files with a frontmatter `title:` field already have an implicit H1 — do not add another `#` heading in the body.
- **No emphasis as heading**: Do not use a line of purely `**bold**` or `*italic*` text as a visual heading. Use actual `####` heading syntax instead. For standalone labels like dates or subtitles, use plain text (no asterisks).
- **No bare URLs**: Wrap URLs in angle brackets (`<url>`) or use `[text](url)` link syntax.
- **Trailing newline**: Files must end with a single newline character.
- **Line length**: Max 500 characters (code blocks and tables are exempt).
- **Allowed HTML tags**: `br`, `img`, `a`, `div`, `span`, `details`, `summary`.
