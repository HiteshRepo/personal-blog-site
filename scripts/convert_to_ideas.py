#!/usr/bin/env python3
"""Convert a raw notes file into a structured ideas file using AI.

The output ideas file is ready to use with generate_post.py and generate_diagrams.py.

Usage:
    python3 scripts/convert_to_ideas.py ideas/my-notes.md
    python3 scripts/convert_to_ideas.py ideas/my-notes.md ideas/blog-1-my-post.md

Via make:
    make convert FILE=ideas/my-notes.md
    make convert FILE=ideas/my-notes.md OUTPUT=ideas/blog-1-my-post.md
"""

import os
import re
import sys
from pathlib import Path


SYSTEM_PROMPT = """\
You are a technical blog planning assistant.
Convert raw notes into a structured ideas file for AI-assisted blog generation.
Respond ONLY with the ideas file content — no preamble, no explanation.\
"""

USER_PROMPT_TEMPLATE = """\
Convert the raw notes below into a structured ideas file.

## Ideas file format

```
# Blog Title Here
- type: ai          # ai | technical | nontech
- tags: tag1, tag2, tag3
- images: /images/<subdir>/img1.png, /images/<subdir>/img2.png
- bullet point capturing one key idea
- another bullet point
```

## Rules

1. Title: derive a clear, specific blog title from the content.
2. Type: choose ai, technical, or nontech based on the subject matter.
3. Tags: 4–8 specific, relevant tags (lowercase, hyphen-separated if multi-word).
4. Images: scan the raw notes for any `![...](<filename>)` references.
   - Rewrite each image path as `/images/<subdir>/<filename>` where <subdir> is
     the last directory component of the source file path: {subdir}
   - List only images actually referenced in the notes.
   - If no images are referenced, omit the images line entirely.
5. Bullets: distil the content into 15–25 clear, specific bullet points.
   - Each bullet should capture one distinct, valuable idea.
   - Be concrete and technical — include numbers, formulas, and examples where they appear.
   - Do NOT include vague bullets like "explain the concept".
   - Do NOT use sub-bullets; keep it a flat list.
   - Do NOT start bullets with "type:", "tags:", or "images:".

## Raw notes

{content}
"""


def extract_code_blocks(content):
    """Extract all fenced code blocks from raw content, preserving their fences."""
    blocks = []
    for match in re.finditer(r'(```[^\n]*\n.*?```)', content, re.DOTALL):
        block = match.group(1).strip()
        if block:
            blocks.append(block)
    return blocks


def detect_images(content, subdir):
    """Find image references in the raw content and rewrite their paths."""
    pattern = re.compile(r'!\[.*?\]\(([^)]+)\)')
    images = []
    for match in pattern.findall(content):
        filename = Path(match).name
        images.append(f"/images/{subdir}/{filename}")
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for img in images:
        if img not in seen:
            seen.add(img)
            unique.append(img)
    return unique


def generate_with_claude(system_prompt, user_prompt, api_key):
    try:
        import anthropic
    except ImportError:
        print("Error: anthropic package not installed. Run: pip install anthropic",
              file=sys.stderr)
        sys.exit(1)

    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return message.content[0].text


def generate_with_openai(system_prompt, user_prompt, api_key):
    try:
        from openai import OpenAI
    except ImportError:
        print("Error: openai package not installed. Run: pip install openai",
              file=sys.stderr)
        sys.exit(1)

    model = os.environ.get("OPENAI_MODEL", "gpt-4o")
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content


def derive_output_path(input_path):
    """Default output: same dir, same stem with -ideas suffix."""
    p = Path(input_path)
    return p.parent / f"{p.stem}-ideas{p.suffix}"


def main():
    if len(sys.argv) < 2:
        print("Usage: convert_to_ideas.py <notes-file> [output-file]", file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None

    if not Path(input_path).exists():
        print(f"Error: {input_path} does not exist", file=sys.stderr)
        sys.exit(1)

    content = Path(input_path).read_text()
    subdir = Path(input_path).parent.name
    provider = os.environ.get("AI_PROVIDER", "claude").lower()

    if output_path is None:
        output_path = str(derive_output_path(input_path))

    print(f"Input:    {input_path}")
    print(f"Output:   {output_path}")
    print(f"Provider: {provider}")

    user_prompt = USER_PROMPT_TEMPLATE.format(content=content, subdir=subdir)

    if provider == "claude":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("Error: ANTHROPIC_API_KEY not set", file=sys.stderr)
            sys.exit(1)
        result = generate_with_claude(SYSTEM_PROMPT, user_prompt, api_key)
    elif provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("Error: OPENAI_API_KEY not set", file=sys.stderr)
            sys.exit(1)
        result = generate_with_openai(SYSTEM_PROMPT, user_prompt, api_key)
    else:
        print(f"Error: Unknown provider '{provider}'. Use 'claude' or 'openai'",
              file=sys.stderr)
        sys.exit(1)

    # Strip markdown code fences if the model wrapped the output
    result = re.sub(r'^```[^\n]*\n', '', result.strip())
    result = re.sub(r'\n```$', '', result)

    # Append code block diagrams from raw notes so they survive into generate_post
    code_blocks = extract_code_blocks(content)
    if code_blocks:
        diagrams_text = "\n\n".join(code_blocks)
        result = result.strip() + f"\n\n## Raw Diagrams\n\n{diagrams_text}"
        print(f"  Preserved {len(code_blocks)} code block diagram(s) from raw notes")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(result.strip() + "\n")
    print(f"\nConverted: {output_path}")


if __name__ == "__main__":
    main()
