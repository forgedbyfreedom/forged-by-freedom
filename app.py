#!/usr/bin/env python3
import os
import json
from flask import Flask, request, render_template_string, jsonify
from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone
from datetime import datetime

# ============================================================
# 🔐 Load Environment Variables
# ============================================================
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX = os.getenv("PINECONE_INDEX_NAME", "forged-freedom-ai")
PINECONE_ENV = os.getenv("PINECONE_ENVIRONMENT", "us-east1-gcp")

if not OPENAI_API_KEY or not PINECONE_API_KEY:
    raise ValueError("❌ Missing API keys. Please check your .env file.")

print(f"✅ Loaded environment — Index: {PINECONE_INDEX}")

# ============================================================
# 🧠 Initialize Clients
# ============================================================
client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX)

# ============================================================
# 🧾 Load Podcast Stats (Dynamic)
# ============================================================
try:
    with open("transcripts_summary.json", "r") as f:
        PODCAST_STATS = json.load(f)
except Exception:
    PODCAST_STATS = [{"channel": "⚙️ Loading...", "episodes": 0, "words": 0}]

# ============================================================
# 🎨 HTML Template
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
    <form method="POST">
      <input type="text" name="query" placeholder="Search training, peptides, nutrition, mindset..." required>
      <button type="submit">Search</button>
    </form>

    {% if response %}
      <div class="result">
        <h3>💬 AI Summary</h3>
        <p>{{ response }}</p>
        <h4>📚 Sources</h4>
        <ul>{% for src in sources %}<li>{{ src }}</li>{% endfor %}</ul>
      </div>
    {% endif %}

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
</body>
</html>
"""

# ============================================================
# 🔎 Flask Routes
# ============================================================
app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def home():
    response, sources = None, []
    if request.method == "POST":
        query = request.form["query"].strip()
        if not query:
            return render_template_string(HTML_TEMPLATE, response=None, sources=[], podcast_stats=PODCAST_STATS, timestamp=datetime.now())

        print(f"🔍 Query received: {query}")

        try:
            q_emb = client.embeddings.create(model="text-embedding-3-small", input=query).data[0].embedding
            res = index.query(vector=q_emb, top_k=5, include_metadata=True)
            context = "\n\n".join([m["metadata"].get("text", "")[:1500] for m in res["matches"]])
            sources = [m["metadata"].get("source", "Unknown") for m in res["matches"]]

            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a bodybuilding and sports science research assistant for ForgedByFreedom.org. Summarize insights from the context factually and clearly."},
                    {"role": "user", "content": f"Query: {query}\n\nContext:\n{context}"}
                ]
            )
            response = completion.choices[0].message.content

        except Exception as e:
            response = f"⚠️ Error: {e}"

    return render_template_string(HTML_TEMPLATE, response=response, sources=sources, podcast_stats=PODCAST_STATS, timestamp=datetime.now().strftime('%Y-%m-%d %H:%M'))

@app.route("/api/search", methods=["POST"])
def api_search():
    """Optional JSON endpoint for other apps or dashboards."""
    data = request.json
    query = data.get("query", "")
    if not query:
        return jsonify({"results": []})

    try:
        q_emb = client.embeddings.create(model="text-embedding-3-small", input=query).data[0].embedding
        res = index.query(vector=q_emb, top_k=5, include_metadata=True)
        return jsonify({"results": res["matches"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================
# 🚀 Run App
# ============================================================
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5051)
