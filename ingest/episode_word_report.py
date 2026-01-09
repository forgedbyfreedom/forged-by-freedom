from pathlib import Path

BASE = Path("ingest/channels")
total_files = 0
total_words = 0

for f in BASE.rglob("*.txt"):
    text = f.read_text(errors="ignore")
    total_files += 1
    total_words += len(text.split())

print("\n📊 LOCAL CONTENT AUDIT")
print(f"• Episodes: {total_files}")
print(f"• Words: {total_words:,}")
