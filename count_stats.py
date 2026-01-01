import os
import re

root = "api/transcripts"
episode_count = 0
word_count = 0

for channel in os.listdir(root):
    channel_path = os.path.join(root, channel)
    if os.path.isdir(channel_path):
        for file in os.listdir(channel_path):
            if file.endswith(".txt"):
                episode_count += 1
                with open(os.path.join(channel_path, file), "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
                    word_count += len(re.findall(r"\w+", text))

print("episodes:", episode_count)
print("words:", word_count)

