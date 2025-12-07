#!/usr/bin/env python3
"""
✅ Fixed OpenAI Ingestion Script — November 2025
Removes deprecated 'metadata' argument and adds safe logging.
"""

import os
from openai import OpenAI
from glob import glob

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def upload_transcript(filepath):
    """Upload a single transcript file to OpenAI for custom GPT ingestion."""
    filename = os.path.basename(filepath)
    try:
        with open(filepath, "rb") as f:
            # Upload file with the proper 'purpose' argument only
            file_obj = client.files.create(
                file=f,
                purpose="assistants"
            )
        print(f"✅ Uploaded: {filepath}")
        return file_obj
    except Exception as e:
        print(f"❌ Error uploading {filename}: {e}")
        return None


def main():
    print("\n🚀 Starting ingestion of transcripts...\n")

    base_dir = os.getcwd()
    transcript_files = glob(os.path.join(base_dir, "@*", "master_transcript1.txt"))

    if not transcript_files:
        print("⚠️ No transcripts found.")
        return

    uploaded_count = 0
    for file_path in transcript_files:
        result = upload_transcript(file_path)
        if result:
            uploaded_count += 1

    print(f"\n🎯 Ingestion complete — {uploaded_count} transcripts uploaded.\n")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
✅ Fixed OpenAI Ingestion Script — November 2025
Removes deprecated 'metadata' argument and adds safe logging.
"""

import os
from openai import OpenAI
from glob import glob

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def upload_transcript(filepath):
    """Upload a single transcript file to OpenAI for custom GPT ingestion."""
    filename = os.path.basename(filepath)
    try:
        with open(filepath, "rb") as f:
            # Upload file with the proper 'purpose' argument only
            file_obj = client.files.create(
                file=f,
                purpose="assistants"
            )
        print(f"✅ Uploaded: {filepath}")
        return file_obj
    except Exception as e:
        print(f"❌ Error uploading {filename}: {e}")
        return None


def main():
    print("\n🚀 Starting manual ingestion of transcripts...\n")

    base_dir = os.getcwd()
    transcript_files = glob(os.path.join(base_dir, "@*", "master_transcript1.txt"))

    if not transcript_files:
        print("⚠️ No transcripts found to upload.")
        return

    uploaded_count = 0
    for file_path in transcript_files:
        result = upload_transcript(file_path)
        if result:
            uploaded_count += 1

    print(f"\n🎯 Ingestion complete — {uploaded_count} transcripts uploaded.\n")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
sync_gpt_ingest.py
-----------------------------------
Manual ingestion of all master transcripts into your OpenAI GPT knowledge base.

Usage:
    python3 sync_gpt_ingest.py
Requirements:
    pip install openai tqdm
Environment:
    export OPENAI_API_KEY="your_api_key_here"
"""

import os
from openai import OpenAI
from tqdm import tqdm

def upload_transcripts_to_openai(base_dir="."):
    """
    Walks through the repo and uploads all master_transcript*.txt files to OpenAI.
    Each upload is stored for retrieval/assistant knowledge usage.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.startswith("sk-your"):
        raise SystemExit("❌ ERROR: Missing or placeholder API key. Run: export OPENAI_API_KEY='sk-REAL_KEY'")

    client = OpenAI(api_key=api_key)
    uploaded_count = 0

    print("\n🚀 Starting manual ingestion of transcripts...\n")

    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.startswith("master_transcript") and file.endswith(".txt"):
                path = os.path.join(root, file)
                try:
                    with open(path, "rb") as f:
                        client.files.create(
                            file=f,
                            purpose="assistants"
                        )
                    uploaded_count += 1
                    print(f"✅ Uploaded: {path}")
                except Exception as e:
                    print(f"⚠️ Failed to upload {path}: {e}")

    print(f"\n🎯 Ingestion complete — {uploaded_count} transcripts uploaded.\n")
    return uploaded_count


if __name__ == "__main__":
    try:
        repo_root = os.path.dirname(os.path.abspath(__file__))
        upload_transcripts_to_openai(repo_root)
    except Exception as e:
        print(f"❌ Error during upload: {e}")
#!/usr/bin/env python3
"""
sync_gpt_ingest.py
-----------------------------------
Manual ingestion of all master transcripts into your OpenAI GPT knowledge base.

Usage:
    python3 sync_gpt_ingest.py
Requirements:
    pip install openai tqdm
Environment:
    export OPENAI_API_KEY="your_api_key_here"
"""

import os
from openai import OpenAI
from tqdm import tqdm

def upload_transcripts_to_openai(base_dir="."):
    """
    Walks through the repo and uploads all master_transcript*.txt files to OpenAI.
    Each upload is stored for retrieval/assistant knowledge usage.
    """
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("❌ OPENAI_API_KEY not set. Run: export OPENAI_API_KEY='your_api_key'")

    uploaded_count = 0
    print("\n🚀 Starting manual ingestion of transcripts...\n")

    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.startswith("master_transcript") and file.endswith(".txt"):
                path = os.path.join(root, file)
                with open(path, "rb") as f:
                    client.files.create(
                        file=f,
                        purpose="assistants",
                        metadata={"channel": os.path.basename(root)}
                    )
                uploaded_count += 1
                print(f"✅ Uploaded: {path}")

    print(f"\n🎯 Ingestion complete — {uploaded_count} transcripts uploaded.\n")
    return uploaded_count


if __name__ == "__main__":
    try:
        repo_root = os.path.dirname(os.path.abspath(__file__))
        upload_transcripts_to_openai(repo_root)
    except Exception as e:
        print(f"❌ Error during upload: {e}")

