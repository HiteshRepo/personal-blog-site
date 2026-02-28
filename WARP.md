    # WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

This is a personal blog site built with Hugo static site generator, deployed automatically to Netlify. The site uses the `gohugo-theme-ananke` theme and supports multiple content types through custom archetypes.

## Essential Commands

### Development Server

    # Start local development server with drafts enabled
    make serve

    # Preview production build locally
    make preview

### Content Creation

    # Create technical posts (most common)
    make new-tech TITLE='Your Technical Post Title'

    # Create AI-related posts (special technical category)
    make new-ai TITLE='Your AI Post Title'

    # Create non-technical posts
    make new-nontech TITLE='Your Opinion Post Title'

    # Generic post creation (specify section manually)
    make new-post TITLE='Post Title' SECTION=technical

### Publishing Workflow

    # Publish a draft (changes draft: true to draft: false)
    make publish FILE=content/technical/your-post.md

    # Build site locally
    make build

    # Check for draft posts and validate build
    make check

### Linting and Quality

    # Lint all markdown files
    make lint-md

    # Lint and auto-fix markdown issues
    make lint-md-fix

    # See all available commands
    make help

## Architecture and Structure

### Content Architecture

The site uses Hugo's content organization with custom archetypes for different post types:

- **Technical posts**: Located in `content/technical/` with structured templates for code examples, prerequisites, and troubleshooting sections
- **AI posts**: Specialized subset in `content/technical/ai/` with sections for mathematical formulas, practical applications, and future directions
- **Non-technical posts**: Located in `content/nontechnical/` for opinion pieces and general content

### Hugo Configuration

- **Development config**: `hugo.toml` (local development with relative baseURL)
- **Production config**: `hugo.production.toml` (includes Google Analytics and production baseURL)
- **Build settings**: `netlify.toml` defines Hugo version (0.134.3) and build commands

### Theme and Customization

- Uses `gohugo-theme-ananke` as a Git submodule
- Custom CSS via `styles/design-system.css`
- LaTeX support enabled (`uselatex = true`)
- Syntax highlighting enabled (`highlightjs = true`)

### Deployment Pipeline

1. **Local Development**: Use `make serve` for development with draft content
2. **Content Creation**: Use Makefile commands to generate posts from archetypes
3. **Publishing**: Use `make publish` to mark drafts as ready
4. **Automatic Deployment**: Netlify builds and deploys on push to main branch
5. **Quality Assurance**: GitHub Actions run markdown linting, spell checking, and link validation

### GitHub Actions Workflows

- **PR Review**: Automated code review using GPTScript integration
- **Markdown Linting**: Validates markdown formatting
- **Spell Checking**: Uses CSpell with extensive technical vocabulary
- **Link Checking**: Validates external and internal links

## Content Guidelines

### Archetype Usage

Each content type has a specific archetype with predefined structure:

- **Technical**: Includes prerequisites, code examples, troubleshooting sections
- **AI**: Includes background, technical details, applications, challenges, future directions
- **Non-technical**: Focuses on main points, personal reflections, and conclusions

### Markdown Configuration

- Line length limit: 500 characters (configured in `.markdownlint.json`)
- Allows HTML elements: `br`, `img`, `a`, `div`, `span`, `details`, `summary`
- Duplicate headers allowed within same section (`siblings_only: true`)

### Spell Check Integration

Comprehensive technical vocabulary in `.cspell.json` includes:

- Programming languages and frameworks
- Cloud platforms and DevOps tools
- AI/ML terminology
- Blockchain and fintech terms
- Development tools and methodologies

## Development Workflow

1. **Create content**: Use appropriate `make new-*` command
2. **Write and preview**: Edit generated markdown file, use `make serve` to preview
3. **Quality check**: Run `make lint-md` and `make check`
4. **Publish**: Use `make publish FILE=path/to/post.md`
5. **Deploy**: Commit and push - Netlify handles automatic deployment

## Key Files and Directories

- `Makefile`: All development commands and automation
- `archetypes/`: Content templates for different post types
- `hugo.toml` / `hugo.production.toml`: Environment-specific configurations
- `netlify.toml`: Deployment configuration
- `.markdownlint.json`: Markdown linting rules
- `.cspell.json`: Spell check configuration and vocabulary
- `.github/workflows/`: CI/CD automation scripts
