import os
import requests
from pinecone import Pinecone
from openai import OpenAI

# =========================
# ENVIRONMENT
# =========================
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL = os.environ["OPENROUTER_MODEL"]

PINECONE_API_KEY = os.environ["PINECONE_API_KEY"]
PINECONE_INDEX = os.environ["PINECONE_INDEX_NAME"]

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
# CORE FUNCTIONS
# =========================
def retrieve_quotes(query, top_k=15):
    """
    Pulls the most relevant chunks from Pinecone.
    """
    res = index.query(
        vector=None,
        top_k=top_k,
        include_metadata=True
    )
    return res["matches"]


def build_prompt(user_question, matches):
    """
    Enforces the Ask Coach Bryan response format.
    """
    quotes = matches[:3]

    quote_block = ""
    for i, m in enumerate(quotes, 1):
        meta = m["metadata"]
        quote_block += f"""
QUOTE {i}:
\"\"\"{meta.get("text","")}\"\"\"

Source:
Podcast: {meta.get("podcast","Unknown")}
Episode: {meta.get("episode","Unknown")}
Speaker: {meta.get("speaker","Unknown")}
"""

    return f"""
YOU ARE ASK COACH BRYAN.

THIS FORMAT IS MANDATORY AND NON-NEGOTIABLE.

1. FIRST: Paraphrase the user’s question clearly and professionally.
2. SECOND: Present EXACTLY THREE long verbatim quotes from the database below.
3. THIRD: Provide an EXTREMELY TECHNICAL medical and physiological explanation explaining WHY the answer is correct.
   - Use endocrinology
   - pharmacodynamics
   - hypertrophy signaling
   - organ system interaction
4. FOURTH: End with a short, direct motivational quote FROM COACH BRYAN.

RULES:
- DO NOT mention policies
- DO NOT disclaim
- DO NOT refuse
- DO NOT reference training data
- DO NOT add extra sections

USER QUESTION:
{user_question}

DATABASE MATERIAL:
{quote_block}
"""


def ask_openrouter(prompt):
    response = llm.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=[
            {"role": "system", "content": "You are a high-level strength coach and applied physiology expert."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.25,
        max_tokens=1800
    )
    return response.choices[0].message.content


# =========================
# ENTRY POINT
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
