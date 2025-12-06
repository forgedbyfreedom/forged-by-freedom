"""
debug_pinecone_source.py
----------------------------------------
Diagnose what Pinecone packages are installed
and where they’re coming from.
"""

import pkg_resources
import subprocess
import sys
import importlib.util

print("\n🔍 Checking installed Pinecone packages...\n")

for dist in pkg_resources.working_set:
    if "pinecone" in dist.key:
        print(f"📦 {dist.key}=={dist.version}  →  {dist.location}")

print("\n🔍 Checking if 'pinecone-client' is installed...\n")
subprocess.run([sys.executable, "-m", "pip", "show", "pinecone-client"])

print("\n🔍 Checking if 'pinecone' (new SDK) is installed...\n")
subprocess.run([sys.executable, "-m", "pip", "show", "pinecone"])

print("\n✅ Debug complete.\n")
