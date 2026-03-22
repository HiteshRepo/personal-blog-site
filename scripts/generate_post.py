#!/usr/bin/env python3
"""Generate a Hugo blog post from a rough ideas file using AI."""

import os
import re
import sys
import datetime
from pathlib import Path

AI_DISCLAIMER = (
    "> **Note:** This post was AI-generated from rough notes "
    "using the blog generation workflow.\n\n"
)


def parse_ideas_file(filepath):
    """Parse an ideas file and extract title, type, tags, images, bullets, and raw diagrams."""
    content = Path(filepath).read_text()

    # Split off the ## Raw Diagrams section before parsing bullets
    raw_diagrams = []
    main_content = content
    if "## Raw Diagrams" in content:
        main_content, diagrams_section = content.split("## Raw Diagrams", 1)
        raw_diagrams = re.findall(r'(```[^\n]*\n.*?```)', diagrams_section, re.DOTALL)

    lines = main_content.strip().split("\n")

    title = None
    post_type = "technical"
    tags = []
    images = []
    bullets = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# "):
            title = stripped[2:].strip()
        elif re.match(r"^[-*]\s+type\s*:", stripped, re.IGNORECASE):
            post_type = stripped.split(":", 1)[1].strip().lower()
        elif re.match(r"^[-*]\s+tags\s*:", stripped, re.IGNORECASE):
            tags_str = stripped.split(":", 1)[1].strip()
            tags = [t.strip() for t in tags_str.split(",") if t.strip()]
        elif re.match(r"^[-*]\s+images\s*:", stripped, re.IGNORECASE):
            images_str = stripped.split(":", 1)[1].strip()
            images = [i.strip() for i in images_str.split(",") if i.strip()]
        elif re.match(r"^[-*]\s+", stripped):
            bullet = re.sub(r"^[-*]\s+", "", stripped)
            if bullet:
                bullets.append(bullet)

    if not title:
        title = Path(filepath).stem.replace("-", " ").title()

    return title, post_type, tags, images, bullets, raw_diagrams


def slugify(text):
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def build_prompt(title, post_type, bullets, images=None, raw_diagrams=None):
    type_desc = {
        "technical": "technical engineering",
        "ai": "AI/ML",
        "nontech": "opinion/non-technical",
    }.get(post_type, "technical engineering")

    bullets_text = "\n".join(f"- {b}" for b in bullets)

    images_section = ""
    if images:
        image_list = "\n".join(f"  ![descriptive alt text]({img})" for img in images)
        images_section = f"""
Available images — embed these inline where they best illustrate the surrounding text.
Use descriptive alt text. Place each image immediately after the paragraph it supports.
{image_list}
"""

    diagrams_section = ""
    if raw_diagrams:
        diagrams_text = "\n\n".join(raw_diagrams)
        diagrams_section = f"""
Verbatim diagrams — embed these inline where they best illustrate the surrounding text.
Include them EXACTLY as shown (do not modify the content inside the code fences).
{diagrams_text}
"""

    return f"""You are writing a {type_desc} blog post titled "{title}".

The author is a software engineer. Write in their voice: clear, direct, practical.
Use real examples and code where relevant.

Rough ideas/outline to cover:
{bullets_text}
{images_section}{diagrams_section}
Format your response EXACTLY as follows (no extra text before or after):

SUMMARY: <one sentence describing the post>

<full post content in markdown>

Requirements for the post content:
- Do NOT include YAML frontmatter (no ---)
- Do NOT repeat the title as a heading at the top
- Start directly with an introduction paragraph
- Use ## for major sections, ### for subsections
- Include code blocks with language tags where relevant
- End with a brief conclusion
- Tone: conversational but technical
- Length: 800-1500 words"""


def parse_ai_response(response):
    """Extract summary and content from the AI response."""
    lines = response.strip().split("\n")
    summary = ""
    content_start = 0

    for i, line in enumerate(lines):
        if line.startswith("SUMMARY:"):
            summary = line[len("SUMMARY:"):].strip()
            content_start = i + 1
            break

    # Skip any blank lines after SUMMARY
    while content_start < len(lines) and not lines[content_start].strip():
        content_start += 1

    content = "\n".join(lines[content_start:]).strip()
    return summary, content


def generate_with_claude(prompt, api_key):
    try:
        import anthropic
    except ImportError:
        print("Error: anthropic package not installed. Run: pip install anthropic", file=sys.stderr)
        sys.exit(1)

    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def generate_with_openai(prompt, api_key):
    try:
        from openai import OpenAI
    except ImportError:
        print("Error: openai package not installed. Run: pip install openai", file=sys.stderr)
        sys.exit(1)

    model = os.environ.get("OPENAI_MODEL", "gpt-4o")
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def main():
    if len(sys.argv) < 2:
        print("Usage: generate_post.py <ideas-file>", file=sys.stderr)
        sys.exit(1)

    ideas_file = sys.argv[1]
    provider = os.environ.get("AI_PROVIDER", "claude").lower()
    # draft=true locally, false in GH workflow (set via env DRAFT=false)
    is_draft = os.environ.get("DRAFT", "true").lower() != "false"

    title, post_type, tags, images, bullets, raw_diagrams = parse_ideas_file(ideas_file)
    slug = slugify(title)
    output_path = Path("content/posts") / f"{slug}.md"

    print(f"Title:    {title}")
    print(f"Type:     {post_type}")
    print(f"Tags:     {tags}")
    print(f"Images:   {images}")
    print(f"Diagrams: {len(raw_diagrams)} code block(s)")
    print(f"Provider: {provider}")
    print(f"Draft:    {is_draft}")
    print(f"Output:   {output_path}")

    prompt = build_prompt(title, post_type, bullets, images, raw_diagrams)

    if provider == "claude":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("Error: ANTHROPIC_API_KEY not set", file=sys.stderr)
            sys.exit(1)
        raw = generate_with_claude(prompt, api_key)
    elif provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("Error: OPENAI_API_KEY not set", file=sys.stderr)
            sys.exit(1)
        raw = generate_with_openai(prompt, api_key)
    else:
        print(f"Error: Unknown provider '{provider}'. Use 'claude' or 'openai'", file=sys.stderr)
        sys.exit(1)

    summary, content = parse_ai_response(raw)

    now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S-07:00")
    tags_yaml = ", ".join(f'"{t}"' for t in tags)
    draft_val = "true" if is_draft else "false"

    frontmatter = (
        f"---\n"
        f'title: "{title}"\n'
        f"date: {now}\n"
        f'summary: "{summary}"\n'
        f"draft: {draft_val}\n"
        f"ai_generated: true\n"
        f"tags: [{tags_yaml}]\n"
        f"categories: []\n"
        f"---\n\n"
    )

    final_content = frontmatter + AI_DISCLAIMER + content + "\n"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(final_content)

    print(f"\nGenerated: {output_path}")
    # Used by GH workflow to construct the tag
    print(f"SLUG={slug}")


if __name__ == "__main__":
    main()
