HUGO_VERSION := 0.134.3
HUGO := hugo
HUGO_OPTS := --gc --minify
PORT := 1313

# Default target
.PHONY: help
help:
	@echo "Available commands:"
	@echo "  make serve        - Start local development server"
	@echo "  make build        - Build site locally"
	@echo "  make clean        - Clean build artifacts"
	@echo "  make new-post     - Create a new post (usage: make new-post TITLE='My Post Title' SECTION=technical)"
	@echo "  make new-tech     - Create a new technical post (usage: make new-tech TITLE='My Tech Post')"
	@echo "  make new-nontech  - Create a new non-technical post (usage: make new-nontech TITLE='My Non-Tech Post')"
	@echo "  make new-ai       - Create a new AI-related post (usage: make new-ai TITLE='My AI Post')"
	@echo "  make publish      - Publish a draft post (usage: make publish FILE=path/to/post.md)"
	@echo "  make preview      - Build and serve the production site locally"
	@echo "  make check        - Check for common issues"
	@echo "  make lint-md      - Run markdownlint on all markdown files"
	@echo "  make lint-md-fix  - Run markdownlint and fix all auto-fixable issues"

.PHONY: serve
serve:
	$(HUGO) server -D -p $(PORT)

.PHONY: build
build:
	$(HUGO) $(HUGO_OPTS)

.PHONY: clean
clean:
	rm -rf public/
	rm -f .hugo_build.lock

.PHONY: new-post
new-post:
	@[ "${TITLE}" ] || ( echo "Error: TITLE is required. Usage: make new-post TITLE='My Post Title' SECTION=technical"; exit 1 )
	@[ "${SECTION}" ] || ( echo "Error: SECTION is required. Usage: make new-post TITLE='My Post Title' SECTION=technical"; exit 1 )
	@if [ "$(SECTION)" = "technical" ]; then \
		$(HUGO) new --kind technical content/$(SECTION)/$(shell echo "${TITLE}" | tr '[:upper:]' '[:lower:]' | tr ' ' '-').md; \
	elif [ "$(SECTION)" = "nontechnical" ]; then \
		$(HUGO) new --kind nontechnical content/$(SECTION)/$(shell echo "${TITLE}" | tr '[:upper:]' '[:lower:]' | tr ' ' '-').md; \
	else \
		$(HUGO) new content/$(SECTION)/$(shell echo "${TITLE}" | tr '[:upper:]' '[:lower:]' | tr ' ' '-').md; \
	fi
	@echo "Created new post: content/$(SECTION)/$(shell echo "${TITLE}" | tr '[:upper:]' '[:lower:]' | tr ' ' '-').md"

.PHONY: new-tech
new-tech:
	@[ "${TITLE}" ] || ( echo "Error: TITLE is required. Usage: make new-tech TITLE='My Tech Post'"; exit 1 )
	$(HUGO) new --kind technical content/technical/$(shell echo "${TITLE}" | tr '[:upper:]' '[:lower:]' | tr ' ' '-').md
	@echo "Created new technical post: content/technical/$(shell echo "${TITLE}" | tr '[:upper:]' '[:lower:]' | tr ' ' '-').md"

.PHONY: new-nontech
new-nontech:
	@[ "${TITLE}" ] || ( echo "Error: TITLE is required. Usage: make new-nontech TITLE='My Non-Tech Post'"; exit 1 )
	$(HUGO) new --kind nontechnical content/nontechnical/$(shell echo "${TITLE}" | tr '[:upper:]' '[:lower:]' | tr ' ' '-').md
	@echo "Created new non-technical post: content/nontechnical/$(shell echo "${TITLE}" | tr '[:upper:]' '[:lower:]' | tr ' ' '-').md"

.PHONY: new-ai
new-ai:
	@[ "${TITLE}" ] || ( echo "Error: TITLE is required. Usage: make new-ai TITLE='My AI Post'"; exit 1 )
	$(HUGO) new --kind ai content/technical/ai/$(shell echo "${TITLE}" | tr '[:upper:]' '[:lower:]' | tr ' ' '-').md
	@echo "Created new AI post: content/technical/ai/$(shell echo "${TITLE}" | tr '[:upper:]' '[:lower:]' | tr ' ' '-').md"

.PHONY: publish
publish:
	@[ "${FILE}" ] || ( echo "Error: FILE is required. Usage: make publish FILE=path/to/post.md"; exit 1 )
	@if [ ! -f "$(FILE)" ]; then \
		echo "Error: File $(FILE) does not exist."; \
		exit 1; \
	fi
	@sed -i '' -e 's/draft: true/draft: false/' "$(FILE)"
	@echo "Published $(FILE) (draft status set to false)"

.PHONY: preview
preview:
	$(HUGO) $(HUGO_OPTS) --baseURL="http://localhost:$(PORT)"
	$(HUGO) server --port $(PORT) --bind 0.0.0.0 --disableFastRender

.PHONY: check
check:
	@echo "Checking for draft posts..."
	@grep -r "draft: true" content/ || echo "No draft posts found."
	@echo "Checking for broken links..."
	$(HUGO) --baseURL="http://localhost" && echo "Site built successfully. To check for broken links, install htmlproofer."

.PHONY: lint-md
lint-md:
	@echo "Running markdownlint on all markdown files..."
	@if ! command -v markdownlint >/dev/null 2>&1; then \
		echo "markdownlint-cli not found. Installing globally..."; \
		npm install -g markdownlint-cli; \
	fi
	@if [ ! -f .markdownlint.json ]; then \
		echo "Creating markdownlint configuration..."; \
		echo '{"default":true,"MD013":{"line_length":120,"code_blocks":false,"tables":false},"MD033":{"allowed_elements":["br","img","a","div","span","details","summary"]},"MD041":false}' > .markdownlint.json; \
	fi
	markdownlint \
		--config .markdownlint.json \
		--ignore node_modules \
		--ignore themes \
		--ignore public \
		--ignore resources \
		'**/*.md'

.PHONY: lint-md-fix
lint-md-fix:
	@echo "Running markdownlint with auto-fix on all markdown files..."
	@if ! command -v markdownlint >/dev/null 2>&1; then \
		echo "markdownlint-cli not found. Installing globally..."; \
		npm install -g markdownlint-cli; \
	fi
	@if [ ! -f .markdownlint.json ]; then \
		echo "Creating markdownlint configuration..."; \
		echo '{"default":true,"MD013":{"line_length":120,"code_blocks":false,"tables":false},"MD033":{"allowed_elements":["br","img","a","div","span","details","summary"]},"MD041":false}' > .markdownlint.json; \
	fi
	markdownlint \
		--config .markdownlint.json \
		--ignore node_modules \
		--ignore themes \
		--ignore public \
		--ignore resources \
		--fix \
		'**/*.md'
	@echo "Auto-fixable markdown issues have been resolved."
