import { fetch } from 'wix-fetch';
import { getSecret } from 'wix-secrets-backend';

const TOP_K = 12;
const MIN_LONG_QUOTE_CHARS = 300;

export async function runAIEngine(question) {
  const embedding = await embed(question);
  const matches = await queryPinecone(embedding);
  const evidence = extractEvidence(matches);

  if (!evidence.length) {
    throw new Error("INSUFFICIENT_DB_EVIDENCE");
  }

  const prompt = buildPrompt(question, evidence);
  return await runOpenRouter(prompt);
}

/* ---------- EMBEDDING ---------- */
async function embed(text) {
  const key = await getSecret("OPENROUTER_API_KEY");
  const base = process.env.OPENROUTER_BASE_URL;

  const r = await fetch(`${base}/embeddings`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${key}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      model: process.env.OPENROUTER_EMBED_MODEL,
      input: text
    })
  });

  const j = await r.json();
  return j.data[0].embedding;
}

/* ---------- PINECONE ---------- */
async function queryPinecone(vector) {
  const key = await getSecret("PINECONE_API_KEY");
  const host = process.env.PINECONE_HOST;

  const r = await fetch(`https://${host}/query`, {
    method: "POST",
    headers: {
      "Api-Key": key,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      vector,
      topK: TOP_K,
      includeMetadata: true
    })
  });

  const j = await r.json();
  return j.matches || [];
}

/* ---------- EVIDENCE ---------- */
function extractEvidence(matches) {
  const valid = matches
    .map(m => m.metadata)
    .filter(m => m?.text && m.text.length > 50);

  const long = valid.filter(v => v.text.length >= MIN_LONG_QUOTE_CHARS);

  if (valid.length >= 3) return valid.slice(0, 3);
  if (long.length >= 1) return [long[0]];
  return [];
}

/* ---------- PROMPT ---------- */
function buildPrompt(question, quotes) {
  const formatted = quotes.map((q, i) => `
"${q.text}"
— ${q.speaker}, ${q.podcast} (${q.episode})
`).join("\n");

  return `
Paraphrase the question.
Answer ONLY using the quotes.
Explain the medical WHY.
End with a Coach Bryan quote.

Question:
${question}

Evidence:
${formatted}
`;
}

/* ---------- COMPLETION ---------- */
async function runOpenRouter(prompt) {
  const key = await getSecret("OPENROUTER_API_KEY");
  const base = process.env.OPENROUTER_BASE_URL;

  const r = await fetch(`${base}/chat/completions`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${key}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      model: process.env.OPENROUTER_MODEL,
      messages: [{ role: "user", content: prompt }],
      temperature: 0.15
    })
  });

  const j = await r.json();
  return j.choices[0].message.content;
}
