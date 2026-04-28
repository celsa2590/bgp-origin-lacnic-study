#!/usr/bin/env bash
set -euo pipefail

# 01_dump_rib_to_text.sh
#
# Convierte archivos RIB/MRT comprimidos o sin comprimir a texto usando bgpdump -m.
#
# Uso:
#   ./scripts/01_dump_rib_to_text.sh <RIB_FILE_O_DIR> <OUT_DIR> [COLLECTOR]
#
# Ejemplos:
#   ./scripts/01_dump_rib_to_text.sh data/raw/route-views.chile data/text/CL CL
#   ./scripts/01_dump_rib_to_text.sh data/raw/route-views.chile/rib.20250101.0000.bz2 data/text/CL CL
#
# Salida:
#   <OUT_DIR>/<collector>_YYYYMMDD_HHMM.txt
#   o, si no se puede inferir fecha/hora:
#   <OUT_DIR>/<collector>_<basename>.txt
#
# Requisitos:
#   - bgpdump instalado y disponible en PATH

IN_PATH="${1:-}"
OUT_DIR="${2:-}"
COLLECTOR="${3:-}"

if [[ -z "$IN_PATH" || -z "$OUT_DIR" ]]; then
  echo "Uso: $0 <RIB_FILE_O_DIR> <OUT_DIR> [COLLECTOR]"
  exit 1
fi

if ! command -v bgpdump >/dev/null 2>&1; then
  echo "ERROR: bgpdump no está instalado o no está en PATH"
  exit 1
fi

if [[ ! -e "$IN_PATH" ]]; then
  echo "ERROR: no existe la ruta de entrada: $IN_PATH"
  exit 1
fi

mkdir -p "$OUT_DIR"

infer_collector() {
  local path="$1"
  local collector="$2"

  if [[ -n "$collector" ]]; then
    echo "$collector"
    return
  fi

  # Si no se pasó collector, usar nombre del directorio padre
  local parent
  parent="$(basename "$(dirname "$path")")"

  # Normalizar un poco
  parent="${parent// /_}"
  parent="${parent//-/_}"

  if [[ -n "$parent" && "$parent" != "." && "$parent" != "/" ]]; then
    echo "$parent"
  else
    echo "collector"
  fi
}

infer_datetime() {
  local base="$1"

  # Ejemplos esperados:
  # rib.20250101.0000.bz2
  # updates.20250315.1200.gz
  # collector_20250101_0000.txt
  # rib20250101_0000
  #
  # Salida:
  # YYYYMMDD_HHMM

  local ymd=""
  local hm=""

  if [[ "$base" =~ ([0-9]{8})[._-]?([0-9]{4}) ]]; then
    ymd="${BASH_REMATCH[1]}"
    hm="${BASH_REMATCH[2]}"
    echo "${ymd}_${hm}"
    return
  fi

  echo ""
}

strip_known_extensions() {
  local name="$1"

  name="${name%.bz2}"
  name="${name%.gz}"
  name="${name%.xz}"
  name="${name%.mrt}"
  name="${name%.rib}"
  name="${name%.txt}"

  echo "$name"
}

build_output_name() {
  local rib="$1"
  local collector="$2"

  local base
  base="$(basename "$rib")"

  local base_noext
  base_noext="$(strip_known_extensions "$base")"

  local dt
  dt="$(infer_datetime "$base_noext")"

  if [[ -n "$dt" ]]; then
    echo "${collector}_${dt}.txt"
  else
    # fallback seguro
    local cleaned="${base_noext// /_}"
    cleaned="${cleaned//-/_}"
    echo "${collector}_${cleaned}.txt"
  fi
}

process_file() {
  local rib="$1"

  if [[ ! -f "$rib" ]]; then
    echo "SKIP: no es archivo regular: $rib"
    return
  fi

  local collector
  collector="$(infer_collector "$rib" "$COLLECTOR")"

  local out_name
  out_name="$(build_output_name "$rib" "$collector")"

  local out_txt="${OUT_DIR%/}/${out_name}"

  if [[ -s "$out_txt" ]]; then
    echo "SKIP: ya existe $out_txt"
    return
  fi

  echo "Procesando:"
  echo "  input : $rib"
  echo "  output: $out_txt"

  # bgpdump lee directamente .bz2/.gz si el build lo soporta.
  # Si tu instalación no lo soporta, aquí habría que descomprimir antes.
  bgpdump -m "$rib" > "$out_txt"

  if [[ ! -s "$out_txt" ]]; then
    echo "ERROR: salida vacía para $rib"
    rm -f "$out_txt"
    exit 1
  fi

  echo "OK: $out_txt"
}

if [[ -d "$IN_PATH" ]]; then
  shopt -s nullglob

  files=()
  for f in "$IN_PATH"/*; do
    [[ -f "$f" ]] || continue
    files+=("$f")
  done

  if [[ ${#files[@]} -eq 0 ]]; then
    echo "No se encontraron archivos en: $IN_PATH"
    exit 0
  fi

  for f in "${files[@]}"; do
    process_file "$f"
  done
else
  process_file "$IN_PATH"
fi
