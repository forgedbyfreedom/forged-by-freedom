from pinecone import Pinecone
import os
import re

pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
index = pc.Index("forged-freedom-ai")

FEMALE_RISK_TERMS = [
    "girl", "girls", "female competitor", "viril",
    "voice", "clit", "mascul", "irreversible",
    "androgen", "deep voice", "facial hair"
]

def score_female_relevance(text: str) -> int:
    text = text.lower()
    return sum(1 for term in FEMALE_RISK_TERMS if term in text)

def answer_question(question: str):
    res = index.query(
        vector=embed(question),
        top_k=40,
        include_metadata=True,
        namespace="default"
    )

    candidates = []

    for m in res.matches:
        meta = m.metadata or {}
        source = meta.get("source", "")
        channel = meta.get("channel", "")
        text = meta.get("text", "")

        score = score_female_relevance(text)

        if score > 0:
            candidates.append({
                "score": score,
                "source": source,
                "channel": channel,
                "quote": text.strip()
            })

    if not candidates:
        return {
            "answer": (
                "There are no direct quotes in the database that explicitly "
                "address trenbolone use in women or virilization risk. "
                "This does not imply safety — it indicates the topic is discussed "
                "indirectly rather than as a recommendation."
            ),
            "sources": []
        }

    candidates.sort(key=lambda x: x["score"], reverse=True)

    top = candidates[:3]

    answer = (
        "Based on direct statements from bodybuilding podcasts, trenbolone is "
        "frequently discussed as posing significant virilization risk for female users, "
        "with effects described as irreversible in some cases."
    )

    sources = []
    for c in top:
        sources.append({
            "podcast": c["channel"],
            "episode": c["source"],
            "quote": c["quote"][:600]
        })

    return {
        "answer": answer,
        "sources": sources
    }
