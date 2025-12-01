import os
from flask import Flask, request, render_template_string
from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec

# ============================================================
# 🔐 Load Environment Variables
# ============================================================
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

if not OPENAI_API_KEY or not PINECONE_API_KEY:
    raise ValueError("❌ Missing API keys. Please check your .env file.")

print("✅ Loaded API keys from .env successfully.")

# ============================================================
# 🧠 Initialize Clients
# ============================================================
client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)

INDEX_NAME = "forged-freedom-ai"
DIMENSION = 3072

if INDEX_NAME not in pc.list_indexes().names():
    print(f"⚙️ Creating Pinecone index '{INDEX_NAME}' with dimension={DIMENSION}...")
    pc.create_index(
        name=INDEX_NAME,
        dimension=DIMENSION,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )
else:
    print(f"✅ Using existing Pinecone index: {INDEX_NAME}")

index = pc.Index(INDEX_NAME)

# ============================================================
# ⚙️ Flask App Setup
# ============================================================
app = Flask(__name__)

# Mock channel stats — Replace later with your analyzer data
PODCAST_STATS = [
    {"channel": "@ThinkBIGBodybuilding", "episodes": 3, "words": 6165260},
    {"channel": "@rxmuscle", "episodes": 1, "words": 3067492},
    {"channel": "@RenaissancePeriodization", "episodes": 1, "words": 2310648},
    {"channel": "@PeterAttiaMD", "episodes": 1, "words": 2287646},
    {"channel": "@bodybuildingcom", "episodes": 1, "words": 1971720},
    {"channel": "@FoundMyFitness", "episodes": 1, "words": 1499848},
]

# ============================================================
# 💅 HTML TEMPLATE
# ============================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Forged By Freedom AI Search</title>
<style>
  body {
    font-family: 'Inter', sans-serif;
    background: radial-gradient(circle at top left, #0a0a0a 0%, #000 100%);
    color: #eee;
    margin: 0;
    display: flex;
    min-height: 100vh;
  }

  /* Sidebar */
  .sidebar {
    width: 28%;
    background: linear-gradient(180deg, #0a0a0a 0%, #111 100%);
    border-left: 2px solid #00eaff55;
    padding: 25px;
    box-shadow: -4px 0 20px #00eaff22;
    overflow-y: auto;
  }

  .sidebar h2 {
    color: #00eaff;
    text-align: center;
    text-shadow: 0 0 15px #00eaff;
  }

  .podcast-list {
    margin-top: 20px;
  }

  .podcast-item {
    background: #111;
    border: 1px solid #00eaff33;
    padding: 10px 15px;
    border-radius: 10px;
    margin: 8px 0;
    box-shadow: 0 0 8px #00eaff11;
  }

  .podcast-item:hover {
    box-shadow: 0 0 15px #00eaff55;
    transform: translateY(-2px);
    transition: all 0.2s ease-in-out;
  }

  .podcast-item strong { color: #00eaff; }

  /* Main content */
  .main {
    flex-grow: 1;
    padding: 40px;
  }

  header {
    text-align: center;
    margin-bottom: 30px;
  }

  h1 {
    color: #00eaff;
    text-shadow: 0 0 25px #00eaffaa;
  }

  p.subtitle {
    color: #aaa;
    margin-top: -10px;
  }

  form {
    text-align: center;
    margin-bottom: 40px;
  }

  input[type=text] {
    width: 60%;
    padding: 12px;
    border-radius: 10px;
    border: 1px solid #00eaff33;
    background: #0a0a0a;
    color: #eee;
    font-size: 1em;
    box-shadow: 0 0 8px #00eaff22;
  }

  button {
    padding: 12px 25px;
    background: #00eaff;
    color: #000;
    font-weight: bold;
    border: none;
    border-radius: 10px;
    cursor: pointer;
    margin-left: 10px;
    box-shadow: 0 0 10px #00eaff88;
  }

  button:hover {
    background: #00bcd4;
    box-shadow: 0 0 20px #00eaff;
  }

  .results {
    max-width: 800px;
    margin: 0 auto;
    background: #111;
    padding: 25px;
    border-radius: 12px;
    box-shadow: 0 0 25px #00eaff22;
  }

  .results h3 {
    color: #00eaff;
  }

  ul {
    color: #aaa;
  }

  footer {
    text-align: center;
    padding: 30px;
    color: #777;
    margin-top: 50px;
  }
</style>
</head>
<body>
  <div class="main">
    <header>
      <h1>FORGED BY FREEDOM AI SEARCH</h1>
      <p class="subtitle">The world’s largest bodybuilding, performance, and nutrition database</p>
    </header>

    <form method="POST">
      <input type="text" name="query" placeholder="Search training, anabolics, psychology, peptides..." required>
      <button type="submit">Search</button>
    </form>

    {% if response %}
    <div class="results">
      <h3>💬 AI Response:</h3>
      <p>{{ response }}</p>
      <h4>📚 Top Sources:</h4>
      <ul>
        {% for src in sources %}
          <li>{{ src }}</li>
        {% endfor %}
      </ul>
    </div>
    {% endif %}

    <footer>
      Provided by <b>ForgedByFreedom.org</b><br>
      Strength • Discipline • Freedom<br>
      <small>Nothing here is medical advice — research purposes only.</small>
    </footer>
  </div>

  <div class="sidebar">
    <h2>🎙️ Podcast Channels</h2>
    <div class="podcast-list">
      {% for p in podcast_stats %}
        <div class="podcast-item">
          <strong>{{ p.channel }}</strong><br>
          Episodes: {{ p.episodes }}<br>
          Words: {{ "{:,}".format(p.words) }}
        </div>
      {% endfor %}
    </div>
  </div>
</body>
</html>
"""

# ============================================================
# 🔎 Flask Route
# ============================================================
@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        query = request.form["query"].strip()
        print(f"🔍 Query: {query}")

        # Embed query
        embedding = client.embeddings.create(
            model="text-embedding-3-large",
            input=query
        ).data[0].embedding

        # Search in Pinecone
        results = index.query(vector=embedding, top_k=5, include_metadata=True)
        context = "\n\n".join([m["metadata"].get("text", "") for m in results["matches"]])
        sources = [m["metadata"].get("source", "Unknown") for m in results["matches"]]

        # Generate AI summary
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "You are an expert bodybuilding research assistant working for ForgedByFreedom.org. "
                    "Summarize insights from bodybuilding podcasts accurately, citing show and episode names. "
                    "Avoid medical advice; focus on education."
                )},
                {"role": "user", "content": f"Query: {query}\n\nContext:\n{context}"}
            ]
        )
        response_text = completion.choices[0].message.content

        return render_template_string(
            HTML_TEMPLATE, response=response_text, sources=sources, podcast_stats=PODCAST_STATS
        )

    return render_template_string(HTML_TEMPLATE, response=None, sources=[], podcast_stats=PODCAST_STATS)

# ============================================================
# 🚀 Run Flask App
# ============================================================
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5051)
