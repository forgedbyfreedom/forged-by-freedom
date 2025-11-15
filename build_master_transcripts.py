import os

# ====== CONFIG ======
BASE_DIR = "/Users/weero/thinkbig_podcast/transcripts/@ThinkBIGBodybuilding"
OUTPUT_PREFIX = os.path.join(BASE_DIR, "master_transcript")
MAX_SIZE_MB = 100  # split after each ~100 MB
# ====================

def combine_transcripts():
    txt_files = [os.path.join(BASE_DIR, f) for f in os.listdir(BASE_DIR) if f.endswith(".txt")]
    txt_files.sort(key=os.path.getmtime)  # sort by modified date
    
    if not txt_files:
        print("⚠️ No .txt transcript files found.")
        return

    output_index = 1
    current_size = 0
    output_file = f"{OUTPUT_PREFIX}{output_index}.txt"
    out = open(output_file, "w", encoding="utf-8")

    for file in txt_files:
        with open(file, "r", encoding="utf-8", errors="ignore") as f:
            content = f"\n\n=== {os.path.basename(file)} ===\n\n" + f.read()
            out.write(content)
            current_size = os.path.getsize(output_file) / (1024 * 1024)
            if current_size >= MAX_SIZE_MB:
                out.close()
                print(f"✅ Created {output_file} ({current_size:.2f} MB)")
                output_index += 1
                output_file = f"{OUTPUT_PREFIX}{output_index}.txt"
                out = open(output_file, "w", encoding="utf-8")
                current_size = 0

    out.close()
    print(f"✅ Finished! Last file: {output_file}")

if __name__ == "__main__":
    combine_transcripts()

