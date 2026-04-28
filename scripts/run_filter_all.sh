#!/usr/bin/env bash

set -e

BASE="/home/celsa/Documentos/bgp-origin-lacnic-study"

TEXT_DIR="$BASE/data/text"
DELEGATED_DIR="$BASE/data/delegated/2025"
OUTPUT_DIR="$BASE/outputs"

# Lista de colectores (nombre = carpeta = collector)
COLLECTORS=("CL" "MX" "PE" "BR_FOR" "BR_RIO")

for collector in "${COLLECTORS[@]}"; do

    echo "==============================="
    echo "Procesando colector: $collector"
    echo "==============================="

    IN_DIR="$TEXT_DIR/$collector"
    OUT_DIR="$OUTPUT_DIR/$collector"

    mkdir -p "$OUT_DIR"

    for rib in "$IN_DIR"/*.txt; do

        base=$(basename "$rib")

        # extraer YYYYMM desde nombre tipo CL_20250201_0000.txt
        yyyymm=$(echo "$base" | grep -o '[0-9]\{8\}' | cut -c1-6)

        delegated_file="$DELEGATED_DIR/delegated-lacnic-$yyyymm"

        if [[ ! -f "$delegated_file" ]]; then
            echo "⚠️ No existe delegated para $yyyymm → saltando $base"
            continue
        fi

        echo "→ $collector | $base | delegated $yyyymm"

        python3 scripts/02_filter_lacnic_prefixes.py \
            --rib "$rib" \
            --delegated "$delegated_file" \
            --collector "$collector" \
            --out-dir "$OUT_DIR"

    done

done

echo "✅ Todos los colectores procesados"
