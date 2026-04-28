#!/usr/bin/env bash
set -euo pipefail

BASE="/home/celsa/Documentos/bgp-origin-lacnic-study"

YEAR="2026"
MONTH="04"
START_DAY=1
END_DAY=28

DELEGATED="$BASE/data/delegated/2026/delegated-lacnic-202604"

declare -A URLS
URLS["CL"]="https://archive.routeviews.org/route-views.chile/bgpdata/2026.04/RIBS"
URLS["BR_RIO"]="https://archive.routeviews.org/route-views.rio/bgpdata/2026.04/RIBS"

COLLECTORS=("CL" "BR_RIO")

if [[ ! -f "$DELEGATED" ]]; then
  echo "ERROR: no existe delegated: $DELEGATED"
  exit 1
fi

for collector in "${COLLECTORS[@]}"; do
  echo "==============================="
  echo "Colector: $collector"
  echo "==============================="

  RAW_DIR="$BASE/data/raw_daily/$YEAR/$MONTH/$collector"
  TEXT_DIR="$BASE/data/text_daily/$YEAR/$MONTH/$collector"
  OUT_DIR="$BASE/outputs_daily/$YEAR/$MONTH/$collector"

  mkdir -p "$RAW_DIR" "$TEXT_DIR" "$OUT_DIR"

  for day in $(seq -w "$START_DAY" "$END_DAY"); do
    DATE="${YEAR}${MONTH}${day}"
    RIB="rib.${DATE}.0000.bz2"

    RAW_FILE="$RAW_DIR/$RIB"
    TEXT_FILE="$TEXT_DIR/${collector}_${DATE}_0000.txt"
    OUT_V4="$OUT_DIR/${collector}_${DATE}_0000.lacnic.v4.txt"
    OUT_V6="$OUT_DIR/${collector}_${DATE}_0000.lacnic.v6.txt"

    echo "---- $collector $DATE ----"

    if [[ ! -s "$RAW_FILE" ]]; then
      wget -O "$RAW_FILE" "${URLS[$collector]}/$RIB"
    else
      echo "SKIP download: $RAW_FILE"
    fi

    if [[ ! -s "$TEXT_FILE" ]]; then
      "$BASE/scripts/01_dump_rib_to_text.sh" "$RAW_FILE" "$TEXT_DIR" "$collector"
    else
      echo "SKIP bgpdump: $TEXT_FILE"
    fi

    if [[ -s "$OUT_V4" && -s "$OUT_V6" ]]; then
      echo "SKIP filter: outputs existen"
    else
      python3 "$BASE/scripts/02_filter_lacnic_prefixes.py" \
        --rib "$TEXT_FILE" \
        --delegated "$DELEGATED" \
        --collector "$collector" \
        --out-dir "$OUT_DIR"
    fi
  done
done

echo "✅ Procesamiento diario abril 2026 completado hasta día $END_DAY"
