// ---------------------------------------------------------------------------
// Knowledge base loader
// ---------------------------------------------------------------------------

let _kb;
try {
  // require() is resolved by esbuild at bundle time — works in both dev and prod
  _kb = require("./knowledge-base.json");
} catch (e) {
  console.error("[chat] Failed to load knowledge-base.json:", e.message);
  _kb = { chunks: [], timeline: [] };
}

function loadKnowledgeBase() {
  return _kb;
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

// Common aliases and plural/singular pairs
const SYNONYMS = {
  "projects":    "project",
  "posts":       "post",
  "blogs":       "blog",
  "articles":    "article",
  "k8s":         "kubernetes",
  "kube":        "kubernetes",
  "ml":          "learning",
  "llm":         "language",
  "llms":        "language",
  "ai":          "intelligence",
  "js":          "javascript",
  "ts":          "typescript",
  "db":          "database",
  "grpc":        "grpc",
  "yoe":         "experience",
  "exp":         "experience",
  "years":       "experience",
  "career":      "experience",
  "background":  "experience",
  "reach":       "contact",
  "touch":       "contact",
  "contact":     "email",
  "connect":     "linkedin",
  "hire":        "email",
  "employer":    "company",
  "company":     "organization",
  "workplace":   "organization",
  "working":     "organization",
};

function tokenize(text) {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .filter((t) => t.length > 1 && !STOP_WORDS.has(t));
}

// Expand query tokens with synonyms (adds alias alongside original)
function expandTokens(tokens) {
  const expanded = [];
  for (const t of tokens) {
    expanded.push(t);
    if (SYNONYMS[t]) expanded.push(SYNONYMS[t]);
  }
  return expanded;
}

// Type tokens handled separately — not scored against body text to avoid
// "post" matching the word "post" in every blog article's body.
const TYPE_TOKENS = new Set(["post", "posts", "project", "projects", "blog", "blogs", "article", "articles"]);

function scoreChunk(queryTokens, chunk) {
  const expandedTokens = expandTokens(queryTokens);

  // Type-filter boost: if query mentions posts/projects, reward matching chunk type
  const wantsPost    = queryTokens.some((t) => t === "posts"    || t === "post");
  const wantsProject = queryTokens.some((t) => t === "projects" || t === "project");
  const typeBoost =
    (wantsPost    && chunk.type === "post")    ? 0.3 :
    (wantsProject && chunk.type === "project") ? 0.3 : 0;

  // Strip type tokens before content scoring
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
  const { chunks } = loadKnowledgeBase();
  const queryTokens = tokenize(query);

  // Score every chunk, keep only the highest-scoring chunk per slug
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
    .map((s) => s.chunk);
}

// ---------------------------------------------------------------------------
// Prompt builder
// ---------------------------------------------------------------------------

function buildContext(chunks, timeline) {
  const parts = chunks.map((c) => {
    const lines = [
      c.type === "project" ? `Project: ${c.title}` : `Post: ${c.title}`,
    ];
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
      .map(
        (t) =>
          `${t.period} — ${t.role}: ${t.summary} (${t.tech.join(", ")})`
      )
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
// AI provider calls
// ---------------------------------------------------------------------------

async function callOpenAI(messages) {
  const { OpenAI } = require("openai");
  const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

  const response = await client.chat.completions.create({
    model: "gpt-4o-mini",
    messages,
    temperature: 0.5,
    max_tokens: 800,
  });

  return response.choices[0].message.content;
}

async function callAnthropic(messages) {
  const Anthropic = require("@anthropic-ai/sdk");
  const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

  const [systemMsg, ...rest] = messages;

  const response = await client.messages.create({
    model: "claude-haiku-4-5-20251001",
    max_tokens: 800,
    system: systemMsg.content,
    messages: rest,
  });

  return response.content[0].text;
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
// Handler
// ---------------------------------------------------------------------------

exports.handler = async (event) => {
  if (event.httpMethod === "OPTIONS") {
    return { statusCode: 200, headers: CORS_HEADERS, body: "" };
  }

  if (event.httpMethod !== "POST") {
    return { statusCode: 405, body: "Method Not Allowed" };
  }

  let body;
  try {
    body = JSON.parse(event.body || "{}");
  } catch {
    return {
      statusCode: 400,
      headers: CORS_HEADERS,
      body: JSON.stringify({ error: "Invalid JSON body" }),
    };
  }

  const { message, history = [], page_slug } = body;

  if (!message || typeof message !== "string" || !message.trim()) {
    return {
      statusCode: 400,
      headers: CORS_HEADERS,
      body: JSON.stringify({ error: "message is required" }),
    };
  }

  const { timeline } = loadKnowledgeBase();
  const relevantChunks = retrieve(message.trim(), page_slug || null);
  const context = buildContext(relevantChunks, timeline);

  const messages = [
    {
      role: "system",
      content: `${SYSTEM_PROMPT}\n\nContext:\n\n${context}`,
    },
    ...history
      .filter((h) => h.role && h.content)
      .map((h) => ({ role: h.role, content: h.content })),
    { role: "user", content: message.trim() },
  ];

  try {
    const provider = (process.env.AI_PROVIDER || "openai").toLowerCase();
    const reply =
      provider === "anthropic"
        ? await callAnthropic(messages)
        : await callOpenAI(messages);

    return {
      statusCode: 200,
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
      body: JSON.stringify({ reply }),
    };
  } catch (err) {
    console.error("AI provider error:", err?.message || err);
    return {
      statusCode: 500,
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
      body: JSON.stringify({
        error: "Failed to get a response. Please try again.",
      }),
    };
  }
};
