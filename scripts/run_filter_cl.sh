#!/usr/bin/env bash

set -e

BASE_DIR="/home/celsa/Documentos/bgp-origin-lacnic-study"

TEXT_DIR="$BASE_DIR/data/text/CL"
DELEGATED_DIR="$BASE_DIR/data/delegated/2025"
OUT_DIR="$BASE_DIR/outputs/CL"

mkdir -p "$OUT_DIR"

for rib in $TEXT_DIR/*.txt; do

    base=$(basename "$rib")

    # extraer YYYYMM desde nombre tipo CL_20250201_0000.txt
    yyyymm=$(echo "$base" | grep -o '[0-9]\{8\}' | cut -c1-6)

    delegated_file="$DELEGATED_DIR/delegated-lacnic-$yyyymm"

    if [[ ! -f "$delegated_file" ]]; then
        echo "⚠️ No existe delegated para $yyyymm → saltando"
        continue
    fi

    echo "Procesando $base con delegated $yyyymm"

    python3 scripts/02_filter_lacnic_prefixes.py \
        --rib "$rib" \
        --delegated "$delegated_file" \
        --collector CL \
        --out-dir "$OUT_DIR"

done
