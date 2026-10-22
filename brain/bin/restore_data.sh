#!/usr/bin/env bash
# Unpack the committed backtest tags (data/tags/*.gz) into a working directory
# that every scorer takes as its SCRATCH_DIR argument, and build the "fixed"
# view (ORB exports with corrected stop fills under their old names).
# Usage: brain/bin/restore_data.sh [DIR]   (default $BRAIN_DATA or /tmp/brain_data)
set -euo pipefail
cd "$(dirname "$0")/../.."
D="${1:-${BRAIN_DATA:-/tmp/brain_data}}"
mkdir -p "$D/fixed"
for f in data/tags/*.gz; do
  out="$D/$(basename "${f%.gz}")"
  [ -s "$out" ] || gunzip -c "$f" > "$out"
done
for f in "$D"/*_tags.txt; do ln -sf "$f" "$D/fixed/$(basename "$f")"; done
ln -sf "$D/S1FILL_tags.txt" "$D/fixed/S1VW_tags.txt"
ln -sf "$D/YMFILL_tags.txt" "$D/fixed/XYM_tags.txt"
echo "$D"
