#!/bin/bash
mkdir -p large_media_split
for f in *.mp4 *.webm; do
  [ -f "$f" ] || continue
  base=$(basename "$f" | sed 's/ /_/g')
  split -b 95m "$f" "large_media_split/${base}_part_"
done
echo "✅ Split complete. Use 'cat <file>_part_* > original' to rebuild."

