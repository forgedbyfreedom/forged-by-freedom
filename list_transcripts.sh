#!/usr/bin/env bash
echo "================= TRANSCRIPT INDEX ================="
for dir in $(find . -type d -name "@*" | sort); do
  echo ""
  echo "🎙️ Channel: $(basename "$dir")"
  echo "-----------------------------------------------"
  i=1
  for file in $(find "$dir" -maxdepth 1 -type f -name "*.txt" ! -name "master_transcript1.txt" | sort); do
    echo "$i. $(basename "$file")"
    ((i++))
  done
done
echo ""
echo "===================================================="

