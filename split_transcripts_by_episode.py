#!/usr/bin/env python3
import os, re, json

ROOT = "./transcripts"
OUT_ROOT = "./split_transcripts"
os.makedirs(OUT_ROOT, exist_ok=True)

CHANNELS = [d for d in os.listdir(ROOT) if d.startswith("@")]

# Try to detect episode blocks by patterns
EPISODE_PATTERNS = [
    r"Episode\s*\d+[:\- ]",
    r"Ep\.\s*\d+[:\- ]",
    r"\n##+\s",  # markdown headers
    r"\n\s*TITLE[:\-]", 
]

summary = []

def split_channel(channel):
    path = os.path.join(ROOT, channel, "master_transcript1.txt")
    if not os.path.exists(path):
        return

    with open(path, "r") as f:
        text = f.read()

    chunks = re.split("|".join(EPISODE_PATTERNS), text)
    if len(chunks) <= 1:
        print(f"⚠️ {channel}: No clear episode delimiters found.")
        return

    ch_dir = os.path.join(OUT_ROOT, channel)
    os.makedirs(ch_dir, exist_ok=True)
    ep_summaries = []

    for i, chunk in enumerate(chunks):
        clean = chunk.strip()
        if len(clean) < 2000:
            continue
        title_match = re.search(r"^(.*)\n", clean)
        title = title_match.group(1).strip() if title_match else f"Episode {i+1}"
        title = re.sub(r'[^a-zA-Z0-9 _-]', '', title)[:80]

        filename = f"episode_{i+1:03d}_{title.replace(' ', '_')}.txt"
        outpath = os.path.join(ch_dir, filename)
        with open(outpath, "w") as f:
            f.write(clean)

        words = len(clean.split())
        ep_summaries.append({"title": title, "words": words})
    
    summary.append({
        "channel": channel,
        "episodes": len(ep_summaries),
        "words": sum(e["words"] for e in ep_summaries),
        "episodes_list": ep_summaries
    })
    print(f"✅ {channel}: {len(ep_summaries)} episodes split.")

for ch in CHANNELS:
    split_channel(ch)

with open("transcripts_summary.json", "w") as f:
    json.dump(summary, f, indent=2)

print("\n🎯 All channels processed.")
