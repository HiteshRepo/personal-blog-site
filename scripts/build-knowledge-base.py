#!/usr/bin/env python3
"""
Build the AI chat knowledge base from all published posts, projects, and resume.

Reads content/posts/*.md, content/projects/*.md, and resume.md, chunks the
content into ~400-word pieces, and writes netlify/functions/knowledge-base.json.

Uses only stdlib — no pip dependencies required.
"""

import re
import json
import pathlib

ROOT = pathlib.Path(__file__).parent.parent
BASE_URL = "https://hiteshpattanayak.info"
CONTENT_DIRS = [
    ("post", ROOT / "content" / "posts"),
    ("project", ROOT / "content" / "projects"),
]
RESUME_FILE = ROOT / "resume.md"
OUTPUT = ROOT / "netlify" / "functions" / "knowledge-base.json"
CHUNK_WORDS = 400


def parse_frontmatter(text):
    """Extract YAML frontmatter and body from a markdown file."""
    if not text.startswith("---"):
        return {}, text

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text

    fm_lines = parts[1].strip().splitlines()
    body = parts[2].strip()

    meta = {}
    for line in fm_lines:
        if ":" not in line:
            continue
        key, _, raw = line.partition(":")
        key = key.strip()
        value = raw.strip().strip("\"'")

        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1]
            meta[key] = [v.strip().strip("\"'") for v in inner.split(",") if v.strip()]
        elif value.lower() == "true":
            meta[key] = True
        elif value.lower() == "false":
            meta[key] = False
        else:
            meta[key] = value

    return meta, body


def clean_markdown(text):
    """Strip markdown/HTML syntax, leaving readable plain text."""
    text = re.sub(r"```[\s\S]*?```", "", text)             # fenced code blocks
    text = re.sub(r"`[^`]+`", "", text)                    # inline code
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)                      # images
    text = re.sub(r"\[([^\]]+)\]\(([^\)]+)\)", r"\1 (\2)", text)    # links → text (url)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)  # headings
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)  # bold/italic
    text = re.sub(r"<[^>]+>", "", text)                    # HTML tags
    text = re.sub(r"\n{3,}", "\n\n", text)                 # excess blank lines
    return text.strip()


def chunk_text(text, chunk_words=CHUNK_WORDS):
    """Split text into chunks of approximately chunk_words words each."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_words):
        chunk = " ".join(words[i : i + chunk_words])
        if chunk.strip():
            chunks.append(chunk)
    return chunks


def process_file(filepath, content_type):
    """Parse a markdown file and return a list of knowledge base chunks."""
    text = filepath.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)

    if meta.get("draft") is True:
        return []
    if filepath.name == "_index.md":
        return []

    slug = filepath.stem
    title = meta.get("title", slug)
    clean_body = clean_markdown(body)
    text_chunks = chunk_text(clean_body)

    if not text_chunks:
        return []

    chunks = []
    for i, chunk_content in enumerate(text_chunks):
        chunk = {
            "id": f"{slug}-{i}",
            "type": content_type,
            "slug": slug,
            "title": title,
            "url": f"{BASE_URL}/{content_type}s/{slug}/",
            "text": chunk_content,
        }

        if content_type == "post":
            if meta.get("tags"):
                chunk["tags"] = meta["tags"]
            if meta.get("categories"):
                chunk["categories"] = meta["categories"]
            if meta.get("summary"):
                chunk["summary"] = meta["summary"]
        elif content_type == "project":
            if meta.get("techStack"):
                chunk["techStack"] = meta["techStack"]
            if meta.get("organization"):
                chunk["organization"] = meta["organization"]
            if meta.get("role"):
                chunk["role"] = meta["role"]
            if meta.get("description"):
                chunk["description"] = meta["description"]

        chunks.append(chunk)

    return chunks


def process_resume(filepath):
    """Parse resume.md (no frontmatter) into knowledge base chunks."""
    if not filepath.exists():
        return []

    text = filepath.read_text(encoding="utf-8")
    clean_body = clean_markdown(text)
    text_chunks = chunk_text(clean_body)

    chunks = []
    for i, chunk_content in enumerate(text_chunks):
        chunks.append({
            "id": f"resume-{i}",
            "type": "resume",
            "slug": "resume",
            "title": "Hitesh Pattanayak — Resume",
            "url": f"{BASE_URL}/resume/Hitesh-Pattanayak-Resume-2024.pdf",
            "text": chunk_content,
        })

    return chunks


# About — concise fact summary; kept in sync with resume.md
ABOUT = {
    "id": "about-hitesh",
    "type": "about",
    "slug": "about",
    "title": "About Hitesh Pattanayak",
    "url": f"{BASE_URL}/",
    "text": (
        "Hitesh Pattanayak is a Senior Data Engineer and Senior Software Engineer with "
        "10+ years of professional software engineering experience (career started January 2018). "
        "He specialises in Go, Python, Kubernetes, distributed systems, data engineering, "
        "and AI/ML integration. "
        "Current company/employer: Improving (https://www.improving.com/). "
        "Current role: Senior Data Engineer at Improving (since July 2025). "
        "Previous companies: Cognizant, Infosys, Sureify, Thoughtworks, Infracloud Technologies. "
        "Location / address: Bhubaneswar, Odisha, India. "
        "Education: Bachelor of Technology in Electrical & Electronics Engineering, "
        "Gandhi Institute for Technological Advancement (GITA), Biju Patnaik University of "
        "Technology (BPUT), Bhubaneswar, graduated March 2015. "
        "Contact information — all ways to reach or get in touch with Hitesh: "
        "Phone: +91 9503955631. "
        "Email: pattanayak.hitesh03@gmail.com. "
        "LinkedIn (DM available): https://www.linkedin.com/in/hitesh-pattanayak/. "
        "GitHub: https://github.com/HiteshRepo. "
        "Published books: "
        "Book 1: 'Ultimate Certified Kubernetes Application Developer (CKAD) Certification Guide' published by OrangeAva — "
        "https://orangeava.in/products/ultimate-certified-kubernetes-application-developer-ckad-certification-guide. "
        "Book 2: 'Modern API Design with gRPC' published by OrangeAva — "
        "https://orangeava.com/products/modern-api-design-with-grpc. "
        "Conference talk 1: 'gRPC Load Balancing' at GopherCon 2023 — "
        "https://www.youtube.com/watch?v=X8b-cxR-FxY. "
        "Conference talk 2: 'Microservice Communication using gRPC' — "
        "https://www.linkedin.com/feed/update/urn:li:activity:7078232488233373696. "
        "External blog post 1: 'Bare metal K8s cluster provisioning using AWS EKSA' on InfraCloud — "
        "https://www.infracloud.io/blogs/provisioning-kubernetes-bare-metal-using-aws-eks-anywhere/. "
        "External blog post 2: 'Understanding gRPC Concepts, Use Cases & Best Practices' on InfraCloud — "
        "https://www.infracloud.io/blogs/understanding-grpc-concepts-best-practices/. "
        "Open source contributions: AWS EKS Anywhere, Alcionai Corso (Microsoft 365 backup), GPTScript AI. "
        "Recognition: AWS Community Builder 2023–2024. "
        "AI work on current project: RAG pipeline for semantic search over M365 backup data using CosmosDB hybrid vector search and Azure OpenAI; "
        "natural language query to structured metadata filter conversion using few-shot Chat Completions; "
        "Elastic dashboard changelog tool (Python + Anthropic API); AI-assisted security fix tool using Cycode findings. "
        "Personal AI tools built: status updator (scans JIRA, Confluence, GitHub for weekly summaries), "
        "blog generator workflow (Claude/OpenAI from idea files), "
        "AI chat assistant on personal blog (TF-IDF RAG + Netlify Functions + OpenAI gpt-4o-mini)."
    ),
}

# Career timeline
TIMELINE = [
    {
        "period": "Jan 2018–Jul 2020",
        "role": "Software Developer at Cognizant & Infosys",
        "tech": ["RPA", "Python", "UIPath", "automation", "web applications"],
        "summary": (
            "Started career building RPA (Robotic Process Automation) bots and web applications "
            "for enterprise clients. Automated repetitive business processes using UIPath and Python, "
            "and built supporting web UIs. This phase established a strong foundation in scripting, "
            "process thinking, and understanding how software solves real business problems. "
            "The automation mindset from this period has carried through every subsequent role."
        ),
    },
    {
        "period": "Aug 2020–Sep 2021",
        "role": "Software Engineer at Sureify",
        "tech": ["React", "Node.js", "TypeScript", "microservices", "REST APIs"],
        "summary": (
            "Transitioned from RPA scripting into full product engineering. Built a visual "
            "configuration platform that allowed insurance companies to design and deploy "
            "customer-facing workflows without code. This role introduced microservices architecture, "
            "REST API design, and working in a product-focused engineering team. "
            "Marked the shift away from automation tooling toward building scalable software products."
        ),
    },
    {
        "period": "Oct 2021–Jul 2022",
        "role": "Senior Consultant at Thoughtworks",
        "tech": ["Go", "gRPC", "Apache Kafka", "TimescaleDB", "PostgreSQL", "Kubernetes", "microservices"],
        "summary": (
            "Major technical leap: adopted Go as the primary language and moved fully into "
            "distributed backend systems. Architected a high-throughput cryptocurrency trading "
            "platform for Voyager Inc., handling real-time market data with Kafka, time-series "
            "storage with TimescaleDB, and inter-service communication via gRPC. "
            "This was the turning point from generalist engineer to backend/distributed systems specialist. "
            "Go and Kubernetes became the core of every subsequent role."
        ),
    },
    {
        "period": "Aug 2022–Dec 2023",
        "role": "Software Engineer at Infracloud Technologies",
        "tech": ["Go", "Kubernetes", "bare metal provisioning", "DHCP", "TFTP", "Tinkerbell", "Terraform", "Pulumi"],
        "summary": (
            "Deepened Kubernetes expertise by moving from application-layer to infrastructure-layer work. "
            "Built a bare metal Kubernetes cluster provisioning platform using Tinkerbell, handling "
            "low-level network protocols (DHCP, TFTP, iPXE) for automated server bootstrapping. "
            "Also worked on cloud infrastructure automation with Terraform and Pulumi. "
            "This role completed the progression from writing application code to owning the "
            "infrastructure that runs it — a key step toward data and platform engineering."
        ),
    },
    {
        "period": "Jan 2024–Oct 2024",
        "role": "Core Contributor, Open Source (Canario/Corso)",
        "tech": ["Go", "Microsoft Graph API", "S3", "Azure", "CLI design", "CI/CD"],
        "summary": (
            "Contributed to Corso (now Canario), an open-source Microsoft 365 backup and restore solution. "
            "Built CLI interfaces and backend systems for Exchange, OneDrive, SharePoint, and Teams backup "
            "via the Microsoft Graph API. Working in a large open-source Go codebase reinforced "
            "software design principles, API integration patterns, and working with cloud storage at scale. "
            "This was also the first deep exposure to the Microsoft 365 ecosystem, which directly "
            "informed the data pipeline and RAG work that followed at Improving."
        ),
    },
    {
        "period": "Nov 2024–Jun 2025",
        "role": "Senior Software Engineer at Improving",
        "organization": "Improving (https://www.improving.com/)",
        "tech": ["Go", "Auth0", "CosmosDB", "Kubernetes", "RBAC", "OpenAPI", "Azure Key Vault"],
        "summary": (
            "Built an enterprise-grade authentication and user management microservice for a "
            "multi-tenant SaaS platform. Integrated Auth0 with a custom RBAC system supporting "
            "100+ permissions across Azure and Kubernetes workloads. Designed the CosmosDB data "
            "layer with optimised partitioning and comprehensive testing. "
            "This role added security and identity engineering to the skillset — complementing "
            "the infrastructure and distributed systems background built at Thoughtworks and Infracloud."
        ),
    },
    {
        "period": "Jul 2025–present",
        "role": "Senior Data Engineer at Improving",
        "organization": "Improving (https://www.improving.com/)",
        "tech": ["Go", "Python", "Databricks", "Apache Spark", "Delta Lake", "Azure Event Hubs",
                 "CosmosDB", "Azure OpenAI", "RAG", "vector search"],
        "summary": (
            "Current role: architecting data pipeline infrastructure that processes Microsoft 365 "
            "workload events at petabyte scale using Databricks, Apache Spark, and Delta Lake. "
            "Built high-volume streaming ingestion with Azure Event Hubs and Container Apps. "
            "Extended into AI engineering: implemented a RAG (Retrieval-Augmented Generation) "
            "semantic search pipeline using CosmosDB hybrid vector search and Azure OpenAI, "
            "and built tooling that uses LLMs to generate human-readable changelogs and apply "
            "AI-assisted security fixes. "
            "This role represents the convergence of the full career arc: automation roots, "
            "Go/distributed systems expertise, Kubernetes infrastructure knowledge, M365 domain "
            "experience from open source, and now AI/ML applied to real data engineering problems."
        ),
    },
]


def build():
    all_chunks = []

    for content_type, content_dir in CONTENT_DIRS:
        if not content_dir.exists():
            print(f"  Warning: {content_dir} does not exist, skipping.")
            continue

        for filepath in sorted(content_dir.glob("*.md")):
            chunks = process_file(filepath, content_type)
            all_chunks.extend(chunks)
            if chunks:
                print(f"  [{content_type}] {filepath.name} → {len(chunks)} chunk(s)")
            else:
                print(f"  [{content_type}] {filepath.name} → skipped (draft or empty)")

    resume_chunks = process_resume(RESUME_FILE)
    all_chunks.extend(resume_chunks)
    if resume_chunks:
        print(f"  [resume] resume.md → {len(resume_chunks)} chunk(s)")

    kb = {"chunks": [ABOUT] + all_chunks, "timeline": TIMELINE}

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(kb, indent=2, ensure_ascii=False), encoding="utf-8")
    total = len(kb["chunks"])
    print(f"\nDone. {total} chunks written to {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    print("Building knowledge base...")
    build()
