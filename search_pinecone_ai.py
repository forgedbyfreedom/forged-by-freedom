import os
from openai import OpenAI
from pinecone import Pinecone
import textwrap

# -----------------------------
# 🔑 Load API Keys
# -----------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-your-openai-key")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "pcsk-your-pinecone-key")

# Initialize clients
openai_client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)
index_name = "forged-transcripts"
index = pc.Index(index_name)

# -----------------------------
# 🔍 Ask AI + Pinecone
# -----------------------------
def search_pinecone(query: str, top_k: int = 5):
    # Create embedding for the query
    query_embedding = openai_client.embeddings.create(
        model="text-embedding-3-large",
        input=query
    ).data[0].embedding

    # Search Pinecone for similar chunks
    results = index.query(vector=query_embedding, top_k=top_k, include_metadata=True)
    return results

def answer_query(query: str):
    print(f"\n🧠 Query: {query}\n")
    results = search_pinecone(query)
    
    # Combine top matches into context
    context_chunks = []
    for match in results.matches:
        text = match.metadata.get("text", "")
        score = match.score
        context_chunks.append(f"[Score {score:.3f}] {text[:400]}")
    
    combined_context = "\n".join(context_chunks)

    # Ask GPT to synthesize the answer
    prompt = f"""
    You are a helpful assistant that answers based on bodybuilding, fitness, or health podcast transcripts.
    Use the context below to answer the question concisely but informatively.

    ---CONTEXT---
    {combined_context}

    ---QUESTION---
    {query}
    """

    completion = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )

    answer = completion.choices[0].message.content
    print("💬 AI Answer:\n")
    print(textwrap.fill(answer, width=90))

# -----------------------------
# 🚀 Run interactively
# -----------------------------
if __name__ == "__main__":
    while True:
        query = input("\nAsk a question about the transcripts (or 'exit' to quit): ")
        if query.lower() == "exit":
            break
        answer_query(query)
