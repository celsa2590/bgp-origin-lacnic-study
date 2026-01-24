#!/usr/bin/env bash
# process_ribs_lacnic_by_month.sh

set -euo pipefail

IN_DIR="$1"          # ej: PE
DELEGATED_DIR="$2"   # ej: delegated/
OUT_DIR="$3"         # ej: PE_out

mkdir -p "$OUT_DIR"

for rib in "$IN_DIR"/*.txt; do
  base="$(basename "$rib")"

  # Ej: ribpe_2501.txt → 202501
  YYMM="$(echo "$base" | grep -o '[0-9]\{4\}')"
  YEAR="20${YYMM:0:2}"
  MONTH="${YYMM:2:2}"

  delegated="${DELEGATED_DIR}/delegated-lacnic-${YEAR}${MONTH}*"

  if ! ls $delegated 1>/dev/null 2>&1; then
    echo "⚠️  No delegated para $YEAR-$MONTH, saltando $base"
    continue
  fi

  delegated_file="$(ls $delegated | head -1)"

  echo "▶ $base  ↔  $(basename "$delegated_file")"

base="$(basename "${rib}")"
OUT_V4="${OUT_DIR}/${base}.lacnic.v4.txt"
OUT_V6="${OUT_DIR}/${base}.lacnic.v6.txt"

if [[ -s "${OUT_V4}" || -s "${OUT_V6}" ]]; then
  echo "==> SKIP (ya existe salida): ${base}"
  continue
fi


  ./scripts/process_ribs_lacnic_fast.sh \
    "$IN_DIR" \
    "$delegated_file" \
    "$OUT_DIR"
done
