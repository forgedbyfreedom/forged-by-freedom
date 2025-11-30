#!/usr/bin/env python3
import os, json
from flask import Flask, request, render_template_string
from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone

# Load env keys
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("forged-freedom-ai")

# Load summary JSON
SUMMARY_PATH = "transcripts_summary.json"
if os.path.exists(SUMMARY_PATH):
    with open(SUMMARY_PATH, "r") as f:
        channel_data = json.load(f)
else:
    channel_data = []

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>ForgedByFreedom Knowledge Engine</title>
<style>
body { font-family: 'Inter', sans-serif; background-color: #0d1117; color: #f0f0f0; display: flex; flex-direction: row; margin: 0; }
.main { flex: 3; padding: 40px; }
.sidebar { flex: 1.2; background-color: #11161e; border-left: 2px solid #00ff99; padding: 20px; overflow-y: auto; max-height: 100vh; }
h1 { color: #00ff99; font-size: 1.8em; }
h2 { color: #00cc88; }
textarea { width: 100%; height: 120px; background-color: #1c2128; border-radius: 10px; color: #fff; border: none; padding: 12px; }
button { background-color: #00ff99; color: #111; border: none; border-radius: 8px; padding: 10px 20px; cursor: pointer; margin-top: 10px; font-weight: bold; }
button:hover { background-color: #00cc88; }
.answer-box { background-color: #161b22; border-radius: 10px; padding: 20px; margin-top: 20px; border: 1px solid #00ff99; }
.sources { background-color: #0e1117; border-left: 4px solid #00ff99; padding: 10px 15px; margin-top: 15px; border-radius: 6px; }
details { margin-bottom: 10px; background-color: #11161e; border-radius: 6px; padding: 6px 8px; }
summary { cursor: pointer; font-weight: bold; color: #00ff99; }
ul { list-style-type: none; padding-left: 10px; }
li { color: #ccc; font-size: 0.9em; }
.footer { margin-top: 40px; font-size: 0.85em; color: #777; border-top: 1px solid #222; padding-top: 15px; }
</style>
</head>
<body>
<div class="main">
  <h1>ForgedByFreedom.org AI Knowledge Engine</h1>
  <p>The world's largest bodybuilding information database.<br>
  {{total_channels}} channels • {{total_episodes}} episodes • {{total_words}} words indexed.</p>

  <form method="POST">
    <textarea name="query" placeholder="Ask about bodybuilding, PEDs, recovery, supplements...">{{query}}</textarea><br>
    <button type="submit">Search</button>
  </form>

  {% if answer %}
  <div class="answer-box">
    <h2>AI Response:</h2>
    <pre>{{answer}}</pre>
    {% if sources %}
    <div class="sources">
      <h3>🔍 Top Sources:</h3>
      <ul>
      {% for s in sources %}
        <li><strong>{{s.channel}}</strong> — {{s.show}} / {{s.episode}}</li>
      {% endfor %}
      </ul>
    </div>
    {% endif %}
  </div>
  {% endif %}

  <div class="footer">
    Provided by <strong>Forged By Freedom Strength & Nutrition</strong><br>
    STRENGTH • DISCIPLINE • FREEDOM<br>
    <a href="https://ForgedByFreedom.org" style="color:#00ff99;">Visit ForgedByFreedom.org</a><br>
    <em>All content is for research purposes only. Not medical advice.</em>
  </div>
</div>

<div class="sidebar">
  <h2>📻 Podcast Channels</h2>
  {% for ch in channels %}
  <details>
    <summary>{{ch.channel}} ({{ch.episodes}})</summary>
    <ul>
    {% for ep in ch.episodes_list %}
      <li>{{ep.title}} — {{ep.words}} words</li>
    {% endfor %}
    </ul>
  </details>
  {% endfor %}
</div>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def home():
    answer, query, sources = None, "", []
    if request.method == "POST":
        query = request.form["query"]
        emb = client.embeddings.create(input=query, model="text-embedding-3-large").data[0].embedding
        results = index.query(vector=emb, top_k=5, include_metadata=True)
        context_text = "\n\n".join([m.metadata.get("text", "") for m in results.matches])
        sources = [{"channel": m.metadata.get("channel", "Unknown"), "show": m.metadata.get("show", "Unknown"), "episode": m.metadata.get("episode", "N/A")} for m in results.matches]

        prompt = f"You are a bodybuilding expert. Cite relevant shows and episodes.\n\nQuestion: {query}\n\nContext:\n{context_text[:12000]}"
        ai_response = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}])
        answer = ai_response.choices[0].message.content.strip()

    totals = {
        "channels": len(channel_data),
        "episodes": sum(ch["episodes"] for ch in channel_data),
        "words": sum(ch["words"] for ch in channel_data)
    }

    return render_template_string(HTML, answer=answer, query=query, sources=sources,
                                  channels=channel_data, total_channels=totals["channels"],
                                  total_episodes=totals["episodes"], total_words=f"{totals['words']:,}")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
