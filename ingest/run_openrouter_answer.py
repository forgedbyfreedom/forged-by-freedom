#!/usr/bin/env python3
import os
from pinecone import Pinecone
from openai import OpenAI
import requests

# =========================
# ENV
# =========================
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL = os.environ["OPENROUTER_MODEL"]

PINECONE_API_KEY = os.environ["PINECONE_API_KEY"]
PINECONE_INDEX = os.environ["PINECONE_INDEX_NAME"]

EMBED_MODEL = "text-embedding-3-large"

NAMESPACES = [
    "thinkbig_priority",
    "anabolic_bodybuilding_priority",
    "women_steroids",
    "medical_primary",
    "transcripts",
    "default",
    ""  # legacy
]

# =========================
# CLIENTS
# =========================
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX)

llm = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url=OPENROUTER_BASE_URL
)

# =========================
# EMBEDDING
# =========================
def embed_query(text: str):
    r = requests.post(
        "https://openrouter.ai/api/v1/embeddings",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"model": EMBED_MODEL, "input": text},
        timeout=60
    )
    data = r.json()
    return data["data"][0]["embedding"]

# =========================
# RETRIEVAL
# =========================
def retrieve_quotes(query, top_k=25):
    vector = embed_query(query)
    all_matches = []

    for ns in NAMESPACES:
        try:
            res = index.query(
                vector=vector,
                top_k=top_k,
                include_metadata=True,
                namespace=ns
            )
            all_matches.extend(res.matches)
        except Exception:
            continue

    # Deduplicate by ID
    seen = set()
    deduped = []
    for m in all_matches:
        if m.id not in seen:
            seen.add(m.id)
            deduped.append(m)

    # Strong bias toward female-risk content when relevant
    def score(m):
        t = (m.metadata.get("text","") + m.metadata.get("source","")).lower()
        score = 0
        for w in ["female","women","viril","voice","clit","tren"]:
            if w in t:
                score += 2
        return score

    deduped.sort(key=score, reverse=True)
    return deduped[:top_k]

# =========================
# PROMPT
# =========================
def build_prompt(user_question, matches):
    quotes = matches[:3]

    quote_block = ""
    for i, m in enumerate(quotes, 1):
        meta = m.metadata or {}
        quote_block += f"""
QUOTE {i}:
\"\"\"{meta.get("text","")}\"\"\"

Source:
Podcast: {meta.get("channel","Unknown")}
Episode: {meta.get("source","Unknown")}
Speaker: {meta.get("speaker","Unknown")}
"""

    return f"""
YOU ARE ASK COACH BRYAN.

FORMAT IS MANDATORY.

1. Restate the question.
2. Present EXACTLY THREE verbatim quotes.
3. Provide an EXTREMELY TECHNICAL explanation using endocrinology and physiology.
4. End with a short Coach Bryan statement.

USER QUESTION:
{user_question}

DATABASE MATERIAL:
{quote_block}
"""

# =========================
# ASK MODEL
# =========================
def ask_openrouter(prompt):
    response = llm.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=[
            {"role": "system", "content": "You are an applied physiology expert."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.25,
        max_tokens=1800
    )
    return response.choices[0].message.content

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    print("\nAsk Coach Bryan\n")
    question = input("❓ Question: ").strip()

    matches = retrieve_quotes(question)
    prompt = build_prompt(question, matches)
    answer = ask_openrouter(prompt)

    print("\n" + "=" * 60)
    print(answer)
    print("=" * 60 + "\n")
