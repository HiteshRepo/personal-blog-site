VENV := .venv
PYTHON := $(VENV)/bin/python3

.PHONY: serve build clean generate diagrams venv

serve:
	hugo server -D

build:
	hugo --gc --minify

clean:
	rm -rf public/

venv:
	@command -v python3 >/dev/null 2>&1 || ( echo "Error: python3 is required"; exit 1 )
	@[ -d $(VENV) ] || python3 -m venv $(VENV)

diagrams: venv
	$(PYTHON) -m pip install -q matplotlib numpy
	$(PYTHON) scripts/generate_diagrams.py $(FILE)

generate: venv
	@[ "${FILE}" ] || ( echo "Error: FILE is required. Usage: make generate FILE=ideas/my-topic.md"; exit 1 )
	@[ -f "${FILE}" ] || ( echo "Error: File '${FILE}' does not exist."; exit 1 )
	$(PYTHON) -m pip install -q anthropic openai
	AI_PROVIDER=$${AI_PROVIDER:-claude} DRAFT=true $(PYTHON) scripts/generate_post.py "$(FILE)"

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
		echo '{"default":true,"MD013":{"line_length":500,"code_blocks":false,"tables":false},"MD033":{"allowed_elements":["br","img","a","div","span","details","summary"]},"MD041":false, "MD024": { "siblings_only": true }}' > .markdownlint.json; \
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
		echo '{"default":true,"MD013":{"line_length":500,"code_blocks":false,"tables":false},"MD033":{"allowed_elements":["br","img","a","div","span","details","summary"]},"MD041":false, "MD024": { "siblings_only": true }}' > .markdownlint.json; \
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
