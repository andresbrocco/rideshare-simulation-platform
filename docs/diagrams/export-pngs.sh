#!/usr/bin/env bash
# Export all .excalidraw files to .png at 2x scale.
# Requires: excalidraw-cli (https://github.com/nicolo-ribaudo/excalidraw-cli)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

failed=0
exported=0

while IFS= read -r -d '' excalidraw; do
  output="${excalidraw%.excalidraw}.png"
  rel_path="${excalidraw#"$SCRIPT_DIR"/}"

  echo "[$((exported + failed + 1))] Exporting $rel_path..."
  if excalidraw-cli convert "$excalidraw" --format png --scale 2 --output "$output" 2>&1; then
    exported=$((exported + 1))
  else
    echo "  FAILED: $rel_path"
    failed=$((failed + 1))
  fi
done < <(find "$SCRIPT_DIR" -name "*.excalidraw" -print0 | sort -z)

echo ""
echo "Done. Exported: $exported, Failed: $failed"
