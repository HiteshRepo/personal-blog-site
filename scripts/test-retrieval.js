#!/usr/bin/env node
/**
 * Quick local test for the chat retrieval logic.
 * Run: node scripts/test-retrieval.js "your query here"
 */

const fs = require("fs");
const path = require("path");

const KB_PATH = path.join(__dirname, "../netlify/functions/knowledge-base.json");

let kb;
try {
  kb = JSON.parse(fs.readFileSync(KB_PATH, "utf8"));
  console.log(`Loaded KB: ${kb.chunks.length} chunks\n`);
} catch (e) {
  console.error("Failed to load knowledge-base.json:", e.message);
  process.exit(1);
}

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

const query = process.argv[2] || "what posts talk about ai?";
const queryTokens = tokenize(query);

console.log(`Query: "${query}"`);
console.log(`Tokens after stop-word filter: [${queryTokens.join(", ")}]\n`);

const scored = kb.chunks
  .map((chunk) => ({ chunk, score: scoreChunk(queryTokens, chunk) }))
  .sort((a, b) => b.score - a.score)
  .slice(0, 8);

console.log("Top 8 chunks:");
scored.forEach(({ chunk, score }, i) => {
  console.log(`  ${i + 1}. [score=${score.toFixed(5)}] [${chunk.type}] "${chunk.title}" (${chunk.url})`);
});
