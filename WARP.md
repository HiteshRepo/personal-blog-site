# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

Personal blog/portfolio site built with **Hugo** (static site generator), themed with `gohugo-theme-ananke` (Git submodule), deployed on Netlify. Includes an AI-assisted content generation pipeline and a Netlify serverless AI chat assistant.

## Essential Commands

### Development Server

    # Start local development server with drafts enabled
    make serve

    # Preview production build locally
    make preview

    # Build site
    make build

    # Remove public/ directory
    make clean

### Content Creation

    # Create AI-related posts
    make new-ai TITLE='Your AI Post Title'

    # Create non-technical posts
    make new-nontech TITLE='Your Opinion Post Title'

### AI-Assisted Post Generation

    # Convert raw notes into a structured ideas file
    make convert FILE=ideas/my-notes.md [OUTPUT=ideas/blog-1-my-post.md]

    # Generate a full blog post from an ideas file (outputs to content/posts/)
    make generate FILE=ideas/my-topic.md

    # Generate diagrams from an ideas file
    make diagrams FILE=ideas/my-topic.md

    # Build the AI chat knowledge base (writes netlify/functions/knowledge-base.json)
    make build-kb

### Publishing Workflow

    # Publish a draft (changes draft: true to draft: false, commits, tags, and pushes)
    make publish FILE=content/posts/your-post.md

    # Check for draft posts and validate build
    make check

### Linting and Quality

    # Lint all markdown files
    make lint-md

    # Lint and auto-fix markdown issues
    make lint-md-fix

## Architecture and Structure

### Content Architecture

All content lives under `content/`:

- **Blog posts**: `content/posts/` — all post types (technical, AI, non-technical)
- **Projects**: `content/projects/` — project showcase pages

Posts use `draft: true` frontmatter until published. Post type is expressed via `tags`/`categories` in frontmatter, not directory.

### Hugo Configuration

- **Development config**: `hugo.toml` (baseURL = `/`)
- **Production config**: `hugo.production.toml` (Google Analytics, full baseURL)
- **Build settings**: `netlify.toml` defines Hugo version (0.134.3) and build commands

### Theme and Customization

- Uses `gohugo-theme-ananke` as a Git submodule in `themes/`
- Custom CSS via `static/styles/design-system.css` and `static/styles/style.css`
- LaTeX support enabled (`uselatex = true`)
- Syntax highlighting enabled (`highlightjs = true`)
- Custom layouts in `layouts/` (homepage, projects page)

### AI Content Generation Pipeline

The `scripts/` directory contains Python scripts for AI-assisted workflows:

- **`convert_to_ideas.py`**: Converts raw notes into a structured ideas file using Claude or OpenAI
- **`generate_post.py`**: Generates a full Hugo post from an ideas file; outputs to `content/posts/`
- **`generate_diagrams.py`**: Generates diagram images from an ideas file; outputs to `static/images/`
- **`build-knowledge-base.py`**: Chunks all published posts, projects, and resume into `netlify/functions/knowledge-base.json` for the AI chat assistant

Ideas files live in `ideas/` (excluded from markdown linting). Format:

    # Blog Title Here
    - type: ai          # ai | technical | nontech
    - tags: tag1, tag2
    - images: /images/<subdir>/img1.png
    - bullet capturing one key idea

The `AI_PROVIDER` env var selects the model backend (`claude` or `openai`, default: `claude`).

### Deployment Pipeline

1. **Local Development**: `make serve` for development with draft content
2. **Content Creation**: Write ideas file in `ideas/`, run `make generate` or use the GitHub Actions workflow
3. **Publishing**: `make publish FILE=...` — sets `draft: false`, commits, tags (`v<date>-<slug>`), and pushes
4. **Automatic Deployment**: Netlify deploys on new `v*` tags (triggered by `deploy.yml`)
5. **Quality Assurance**: GitHub Actions run markdown linting, spell checking, and link validation on push/PR

### GitHub Actions Workflows

- **`deploy.yml`**: Triggers Netlify deploy on `v*` tags via deploy hook
- **`generate-post.yml`**: Manually dispatch to run the full AI generation pipeline (convert → diagrams → generate → commit → tag → push)
- **`main.yaml`**: Automated PR review using GPTScript (requires `OPENAI_API_KEY` secret)
- **`markdown-lint.yml`**: Validates markdown formatting
- **`spell-check.yml`**: CSpell with custom dictionary in `.cspell.json`
- **`link-checker.yml`**: Validates all markdown links

## Content Guidelines

### Frontmatter

All posts require:

    title: "Post Title"
    date: YYYY-MM-DDTHH:MM:SS-07:00
    draft: true
    tags: []
    categories: []

Use `make publish` or manually set `draft: false` to publish.

### Markdown Configuration

- Line length limit: 500 characters (configured in `.markdownlint.json`)
- Allows HTML elements: `br`, `img`, `a`, `div`, `span`, `details`, `summary`
- Duplicate headers allowed within same section (`siblings_only: true`)
- Always run `make lint-md` after editing `.md` files

### Spell Check Integration

Comprehensive technical vocabulary in `.cspell.json`. Add new domain-specific terms there if spell-check fails.

## Development Workflow

1. **Write ideas**: Create an ideas file in `ideas/` (manually or via `make convert`)
2. **Generate post**: Run `make generate FILE=ideas/my-topic.md` or trigger `generate-post.yml`
3. **Preview**: Use `make serve` to preview draft content
4. **Quality check**: Run `make lint-md` and `make check`
5. **Publish**: `make publish FILE=content/posts/my-post.md`
6. **Deploy**: Push/tag triggers Netlify deploy automatically

## Key Files and Directories

- `Makefile`: All development commands and automation
- `archetypes/default.md`: Default content template
- `hugo.toml` / `hugo.production.toml`: Environment-specific configurations
- `netlify.toml`: Deployment configuration
- `netlify/functions/`: Serverless functions including AI chat assistant and knowledge base
- `scripts/`: Python scripts for AI content generation and knowledge base building
- `ideas/`: Raw notes and ideas files (not linted, not published directly)
- `static/styles/`: Custom CSS files
- `.markdownlint.json`: Markdown linting rules
- `.cspell.json`: Spell check configuration and vocabulary
- `.github/workflows/`: CI/CD automation scripts
- `CLAUDE.md`: Guidance file for Claude Code (mirrors this file)
