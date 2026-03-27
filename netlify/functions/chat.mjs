// ---------------------------------------------------------------------------
// Knowledge base loader
// ---------------------------------------------------------------------------

import { createRequire } from "module";
import OpenAI from "openai";
import Anthropic from "@anthropic-ai/sdk";

const _require = createRequire(import.meta.url);

let _kb;
try {
  _kb = _require("./knowledge-base.json");
} catch (e) {
  console.error("[chat] Failed to load knowledge-base.json:", e.message);
  _kb = { chunks: [], timeline: [] };
}

// ---------------------------------------------------------------------------
// TF-IDF retrieval
// ---------------------------------------------------------------------------

const STOP_WORDS = new Set([
  "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
  "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
  "have", "has", "had", "do", "does", "did", "will", "would", "could",
  "should", "may", "might", "can", "what", "which", "who", "how", "when",
  "where", "why", "about", "talk", "tell", "show", "me", "you", "i",
  "that", "this", "it", "any", "all", "some", "there", "their", "they",
  "recent", "latest", "new", "worked", "built", "made", "hitesh",
]);

const SYNONYMS = {
  "projects":   "project",
  "posts":      "post",
  "blogs":      "blog",
  "articles":   "article",
  "k8s":        "kubernetes",
  "kube":       "kubernetes",
  "ml":         "learning",
  "llm":        "language",
  "llms":       "language",
  "ai":         "intelligence",
  "js":         "javascript",
  "ts":         "typescript",
  "db":         "database",
  "grpc":       "grpc",
  "yoe":        "experience",
  "exp":        "experience",
  "years":      "experience",
  "career":     "experience",
  "background": "experience",
  "reach":      "contact",
  "touch":      "contact",
  "contact":    "email",
  "connect":    "linkedin",
  "hire":       "email",
  "employer":   "company",
  "company":    "organization",
  "workplace":  "organization",
  "working":    "organization",
};

function tokenize(text) {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .filter((t) => t.length > 1 && !STOP_WORDS.has(t));
}

function expandTokens(tokens) {
  const expanded = [];
  for (const t of tokens) {
    expanded.push(t);
    if (SYNONYMS[t]) expanded.push(SYNONYMS[t]);
  }
  return expanded;
}

const TYPE_TOKENS = new Set(["post", "posts", "project", "projects", "blog", "blogs", "article", "articles"]);

function scoreChunk(queryTokens, chunk) {
  const expandedTokens = expandTokens(queryTokens);
  const wantsPost    = queryTokens.some((t) => t === "posts"    || t === "post");
  const wantsProject = queryTokens.some((t) => t === "projects" || t === "project");
  const typeBoost =
    (wantsPost    && chunk.type === "post")    ? 0.3 :
    (wantsProject && chunk.type === "project") ? 0.3 : 0;

  const contentTokens = expandedTokens.filter((t) => !TYPE_TOKENS.has(t));
  const titleTokens = tokenize(chunk.title || "");
  const bodyFields = [
    chunk.text || "",
    (chunk.tags || []).join(" "),
    (chunk.techStack || []).join(" "),
    chunk.summary || "",
    chunk.description || "",
    chunk.organization || "",
    chunk.role || "",
  ];
  const bodyTokens = tokenize(bodyFields.join(" "));
  const allTokens = [...titleTokens, ...bodyTokens];
  const total = allTokens.length || 1;

  let score = typeBoost;
  for (const token of contentTokens) {
    const tf = allTokens.filter((t) => t === token).length / total;
    const titleBoost = titleTokens.includes(token) ? 3 : 1;
    score += tf * titleBoost;
  }
  return score;
}

function retrieve(query, pageSlug, topK = 5) {
  const { chunks } = _kb;
  const queryTokens = tokenize(query);

  const bestBySlug = new Map();
  for (const chunk of chunks) {
    const score = scoreChunk(queryTokens, chunk);
    const isPriority = Boolean(pageSlug && chunk.slug === pageSlug);
    const existing = bestBySlug.get(chunk.slug);
    if (!existing || score > existing.score) {
      bestBySlug.set(chunk.slug, { chunk, score, isPriority });
    }
  }

  return Array.from(bestBySlug.values())
    .sort((a, b) => {
      if (a.isPriority !== b.isPriority) return a.isPriority ? -1 : 1;
      return b.score - a.score;
    })
    .slice(0, topK)
    .map((s) => ({ ...s.chunk, _priority: s.isPriority }));
}

// ---------------------------------------------------------------------------
// Prompt builder
// ---------------------------------------------------------------------------

function buildContext(chunks, timeline) {
  const parts = chunks.map((c) => {
    const label = c._priority
      ? (c.type === "project" ? `[CURRENT PAGE] Project: ${c.title}` : `[CURRENT PAGE] Post: ${c.title}`)
      : (c.type === "project" ? `Project: ${c.title}` : `Post: ${c.title}`);
    const lines = [label];
    if (c.organization) lines.push(`Organization: ${c.organization}`);
    if (c.role) lines.push(`Role: ${c.role}`);
    if (c.techStack) lines.push(`Tech stack: ${c.techStack.join(", ")}`);
    if (c.tags) lines.push(`Tags: ${c.tags.join(", ")}`);
    lines.push(`URL: ${c.url}`);
    lines.push(c.text);
    return lines.join("\n");
  });

  if (timeline && timeline.length > 0) {
    const timelineText = timeline
      .map((t) => `${t.period} — ${t.role}: ${t.summary} (${t.tech.join(", ")})`)
      .join("\n");
    parts.push(`Career Timeline:\n${timelineText}`);
  }

  return parts.join("\n\n---\n\n");
}

const SYSTEM_PROMPT = `You are a helpful assistant on Hitesh Pattanayak's personal blog and portfolio site.
Hitesh is a senior software engineer with expertise in Go, Kubernetes, distributed systems, and AI/ML.

You have two modes depending on what is asked:
1. BLOG/PROJECT CONTENT questions (e.g. "summarise this post", "what is TCP?", "explain DNS"): answer using the full text of the relevant post or project provided in the context. Explain concepts, summarise content, and answer technical questions directly from the post body.
2. PROFILE/EXPERIENCE questions (e.g. "what projects has Hitesh worked on?", "how to contact?"): answer using the facts, titles, and URLs from the context.

STRICT rules:
- When a [CURRENT PAGE] section is present in the context, questions like "what tech was used?", "summarise this", "what were the achievements?", "what was the role?" refer to THAT page only. Answer using [CURRENT PAGE] content — do not list other projects or posts unless explicitly asked.
- NEVER invent, guess, or paraphrase post titles or project names — copy them exactly from the context.
- NEVER use a URL that is not explicitly listed in the context. Always use the exact URL field from the context.
- ALWAYS format every post/project reference as a markdown link: [Exact Post Title](url). Never print bare titles, bare URLs, or "URL: ..." labels.
- If multiple posts or projects match, use a bullet list where each item is a markdown link: - [Title](url)
- If the context explicitly says something is not publicly disclosed or not shared, say that clearly — do NOT say you don't have the information.
- If the exact answer is absent but related content exists in the context, say what IS covered and link to the relevant post/project. Only say "I don't have that information in the blog content." when nothing related exists at all.
- When asked how to contact or reach someone, list ALL contact methods present in the context (phone, email, LinkedIn, GitHub).
- Be concise and conversational.
- Do not answer questions completely unrelated to Hitesh's work, blog, or the technical topics his posts cover.`;

// ---------------------------------------------------------------------------
// Rate limiting via Upstash Redis REST API
// ---------------------------------------------------------------------------

async function isRateLimited(ip) {
  const { UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN } = process.env;
  if (!UPSTASH_REDIS_REST_URL || !UPSTASH_REDIS_REST_TOKEN) return false;

  try {
    const key = `chat_rl:${ip}`;
    const res = await fetch(`${UPSTASH_REDIS_REST_URL}/pipeline`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${UPSTASH_REDIS_REST_TOKEN}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify([["INCR", key], ["EXPIRE", key, 3600]]),
    });
    const [[{ result: count }]] = await res.json();
    return count > 20;
  } catch {
    return false; // fail open
  }
}

// ---------------------------------------------------------------------------
// Streaming AI providers
// ---------------------------------------------------------------------------

async function* streamOpenAI(messages) {
  const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
  const stream = await client.chat.completions.create({
    model: "gpt-4o-mini",
    messages,
    stream: true,
    temperature: 0.5,
    max_tokens: 800,
  });
  for await (const chunk of stream) {
    const text = chunk.choices[0]?.delta?.content || "";
    if (text) yield text;
  }
}

async function* streamAnthropic(messages) {
  const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
  const [systemMsg, ...rest] = messages;
  const stream = client.messages.stream({
    model: "claude-haiku-4-5-20251001",
    max_tokens: 800,
    system: systemMsg.content,
    messages: rest,
  });
  for await (const event of stream) {
    if (event.type === "content_block_delta" && event.delta.type === "text_delta") {
      yield event.delta.text;
    }
  }
}

// ---------------------------------------------------------------------------
// CORS headers
// ---------------------------------------------------------------------------

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "Content-Type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

// ---------------------------------------------------------------------------
// Handler (Netlify Functions v2)
// ---------------------------------------------------------------------------

export default async (request) => {
  if (request.method === "OPTIONS") {
    return new Response("", { status: 200, headers: CORS_HEADERS });
  }

  if (request.method !== "POST") {
    return new Response("Method Not Allowed", { status: 405 });
  }

  // Rate limiting
  const ip = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || "unknown";
  if (await isRateLimited(ip)) {
    return new Response(
      JSON.stringify({ error: "Too many requests. Please try again in an hour." }),
      { status: 429, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } }
    );
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return new Response(
      JSON.stringify({ error: "Invalid JSON body" }),
      { status: 400, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } }
    );
  }

  const { message, history = [], page_slug } = body;
  if (!message || typeof message !== "string" || !message.trim()) {
    return new Response(
      JSON.stringify({ error: "message is required" }),
      { status: 400, headers: { ...CORS_HEADERS, "Content-Type": "application/json" } }
    );
  }

  const { timeline } = _kb;
  const relevantChunks = retrieve(message.trim(), page_slug || null);
  const context = buildContext(relevantChunks, timeline);

  const messages = [
    { role: "system", content: `${SYSTEM_PROMPT}\n\nContext:\n\n${context}` },
    ...history.filter((h) => h.role && h.content).map((h) => ({ role: h.role, content: h.content })),
    { role: "user", content: message.trim() },
  ];

  const provider = (process.env.AI_PROVIDER || "openai").toLowerCase();
  const tokenStream = provider === "anthropic" ? streamAnthropic(messages) : streamOpenAI(messages);

  const encoder = new TextEncoder();
  const readable = new ReadableStream({
    async start(controller) {
      try {
        for await (const text of tokenStream) {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify({ text })}\n\n`));
        }
        controller.enqueue(encoder.encode("data: [DONE]\n\n"));
      } catch (err) {
        console.error("Stream error:", err?.message || err);
        controller.enqueue(
          encoder.encode(`data: ${JSON.stringify({ error: "Failed to get a response. Please try again." })}\n\n`)
        );
      }
      controller.close();
    },
  });

  return new Response(readable, {
    status: 200,
    headers: {
      ...CORS_HEADERS,
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "X-Accel-Buffering": "no",
    },
  });
};
