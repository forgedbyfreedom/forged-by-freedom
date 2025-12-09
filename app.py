#!/usr/bin/env python3
import os
import json
import requests
from flask import Flask, request, render_template_string, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from openai import OpenAI
import os
from pinecone import Pinecone
from datetime import datetime

# ============================================================
# 🔐 Load Environment Variables
# ============================================================
load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

if not PINECONE_API_KEY:
    raise ValueError("❌ Missing Pinecone API key.")

print(f"✅ Environment loaded — Index: {PINECONE_INDEX}")

# ============================================================
# 🧠 Initialize Clients
# ============================================================
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX)

def get_ai_client():
    """Select OpenRouter (preferred) or fall back to OpenAI."""
    if OPENROUTER_API_KEY:
        print("🧩 Using OpenRouter unfiltered AI.")
        return OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)
    elif OPENAI_API_KEY:
        print("🧩 Falling back to OpenAI.")
        return OpenAI(api_key=OPENAI_API_KEY)
    else:
        raise ValueError("❌ No AI API key found.")
    
client = OpenAI(
    base_url=OPENROUTER_BASE_URL,
    api_key=OPENROUTER_API_KEY
)

# ============================================================
# 🧾 Load Podcast Stats (if available)
# ============================================================
try:
    with open("transcripts_summary.json", "r") as f:
        PODCAST_STATS = json.load(f)
except Exception:
    PODCAST_STATS = [{"channel": "⚙️ Loading...", "episodes": 0, "words": 0}]

# ============================================================
# 🎨 HTML Template (keeps your layout)
# ============================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Forged By Freedom AI Search</title>
<style>
  body { font-family: 'Inter', sans-serif; background: #0a0a0a; color: #eee; display: flex; margin: 0; min-height: 100vh; }
  .sidebar { width: 28%; background: linear-gradient(180deg,#0a0a0a,#111); border-left: 2px solid #00eaff55; padding: 25px; overflow-y: auto; }
  .main { flex-grow: 1; padding: 40px; }
  h1 { color: #00eaff; text-shadow: 0 0 25px #00eaffaa; text-align:center; }
  input { width: 60%; padding: 12px; border-radius: 8px; border: 1px solid #00eaff55; background: #111; color: #eee; }
  button { padding: 12px 25px; background: #00eaff; color: #000; border-radius: 8px; border:none; cursor:pointer; margin-left:10px; }
  .result { margin: 15px auto; background:#111; padding:15px; border-radius:10px; box-shadow:0 0 15px #00eaff22; max-width:800px; }
  footer { text-align:center; color:#777; margin-top:40px; font-size:0.85em; }
</style>
</head>
<body>
  <div class="main">
    <h1>FORGED BY FREEDOM SEARCH</h1>
    <form id="searchForm">
      <input type="text" id="query" placeholder="Search training, peptides, nutrition, mindset..." required>
      <button type="submit">Search</button>
    </form>

    <div id="results"></div>

    <footer>
      ForgedByFreedom.org • Strength • Discipline • Freedom<br>
      <small>Last updated: {{ timestamp }}</small>
    </footer>
  </div>

  <div class="sidebar">
    <h2>🎙️ Channels</h2>
    {% for p in podcast_stats %}
      <div class="result">
        <strong>{{ p.channel }}</strong><br>
        Episodes: {{ p.episodes }}<br>
        Words: {{ "{:,}".format(p.words) }}
      </div>
    {% endfor %}
  </div>

<script>
document.getElementById("searchForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = document.getElementById("query").value.trim();
  const resDiv = document.getElementById("results");
  resDiv.innerHTML = "<p>⏳ Searching...</p>";

  try {
    const res = await fetch("/api/search", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({query: q})
    });
    const data = await res.json();
    if (data.response) {
      resDiv.innerHTML = `
        <div class="result">
          <h3>💬 AI Summary</h3>
          <p>${data.response}</p>
          <h4>📚 Sources</h4>
          <ul>${(data.sources || []).map(s => `<li>${s}</li>`).join("")}</ul>
        </div>`;
    } else resDiv.innerHTML = "<p>⚠️ No response received.</p>";
  } catch (err) {
    console.error(err);
    resDiv.innerHTML = "<p>❌ Error connecting to AI.</p>";
  }
});
</script>
</body>
</html>
"""

# ============================================================
# 🔎 Flask API
# ============================================================
app = Flask(__name__)
CORS(app)

@app.route("/", methods=["GET"])
def home():
    return render_template_string(
        HTML_TEMPLATE,
        podcast_stats=PODCAST_STATS,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M")
    )

@app.route("/api/search", methods=["POST"])
def api_search():
    query = request.json.get("query", "").strip()
    if not query:
        return jsonify({"error": "Missing query"}), 400

    try:
        emb = client.embeddings.create(model="text-embedding-3-small", input=query).data[0].embedding
        res = index.query(vector=emb, top_k=5, include_metadata=True)
        context = "\n\n".join([m["metadata"].get("text", "")[:1500] for m in res["matches"]])
        sources = [m["metadata"].get("source", "Unknown") for m in res["matches"]]

        chat = client.chat.completions.create(
            model="nousresearch/hermes-2-pro",
            messages=[
                {"role": "system", "content": "You are a research assistant specializing in bodybuilding, biohacking, and human performance."},
                {"role": "user", "content": f"Query: {query}\n\nContext:\n{context}"}
            ]
        )
        response = chat.choices[0].message.content
        return jsonify({"response": response, "sources": sources})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================
# 🚀 Run App
# ============================================================
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5051)
