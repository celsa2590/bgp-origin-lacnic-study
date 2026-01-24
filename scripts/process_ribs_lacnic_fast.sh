#!/usr/bin/env bash
# process_ribs_lacnic_fast.sh
#
# Lee archivos RIB en formato TABLE_DUMP2 (texto), filtra solo prefijos LACNIC usando delegated,
# y genera 2 archivos por cada RIB de entrada: uno IPv4 y otro IPv6.
#
# Entrada esperada (líneas):
# TABLE_DUMP2|<ts>|B|<peer_ip>|<peer_asn>|<prefix>|<as_path>|<origin>|<next_hop>|...
#
# Salida (por línea):
# prefix|cc|origin|origin_asn|peer_ip|peer_asn|next_hop|as_path|timestamp
#
# Uso:
#   ./process_ribs_lacnic_fast.sh <IN_DIR> <DELEGATED_FILE> [OUT_DIR]
#
# Ejemplo:
#   ./process_ribs_lacnic_fast.sh PE /ruta/delegated/delegated-lacnic-20251231.txt PE_out
#
set -euo pipefail

IN_DIR="${1:-}"
DELEGATED="${2:-}"
OUT_DIR="${3:-}"

if [[ -z "$IN_DIR" || -z "$DELEGATED" ]]; then
  echo "Uso: $0 <IN_DIR> <DELEGATED_FILE> [OUT_DIR]"
  exit 1
fi
if [[ ! -d "$IN_DIR" ]]; then
  echo "ERROR: IN_DIR no existe: $IN_DIR"
  exit 1
fi
if [[ ! -f "$DELEGATED" ]]; then
  echo "ERROR: DELEGATED no existe: $DELEGATED"
  exit 1
fi

if [[ -z "$OUT_DIR" ]]; then
  OUT_DIR="${IN_DIR%/}/lacnic_txt"
fi
mkdir -p "$OUT_DIR"

# Procesa cada rib*.txt dentro del directorio
shopt -s nullglob
RIBS=( "$IN_DIR"/*.txt )
if [[ ${#RIBS[@]} -eq 0 ]]; then
  echo "No se encontraron .txt en: $IN_DIR"
  exit 0
fi

for rib in "${RIBS[@]}"; do
  base="$(basename "$rib")"
  out_v4="${OUT_DIR}/${base}.lacnic.v4.txt"
  out_v6="${OUT_DIR}/${base}.lacnic.v6.txt"

  echo "==> Procesando: $rib"
  echo "    -> $out_v4"
  echo "    -> $out_v6"

  # Python inline para:
  # - cargar delegated-lacnic (formato RIR stats)
  # - armar tries (PyTricia) para v4/v6 con CC
  # - leer rib TABLE_DUMP2, filtrar prefijos que caen en LACNIC
  # - emitir 2 archivos (v4 y v6)
  python3 - "$DELEGATED" "$rib" "$out_v4" "$out_v6" << 'PY'
import sys
import ipaddress
import pytricia

delegated_path = sys.argv[1]
rib_path       = sys.argv[2]
out_v4_path    = sys.argv[3]
out_v6_path    = sys.argv[4]

# Trie: key = prefix CIDR, value = cc
t4 = pytricia.PyTricia(32)
t6 = pytricia.PyTricia(128)

def add_v4_range_to_trie(start_ip: str, count: int, cc: str):
    # start_ip + count (cantidad de IPs) -> sumariza a CIDRs
    start = ipaddress.IPv4Address(start_ip)
    end = ipaddress.IPv4Address(int(start) + int(count) - 1)
    for net in ipaddress.summarize_address_range(start, end):
        t4.insert(str(net), cc)

def add_v6_prefix_to_trie(start_ip: str, plen: int, cc: str):
    net = ipaddress.IPv6Network(f"{start_ip}/{plen}", strict=False)
    t6.insert(str(net), cc)

def load_delegated_lacnic():
    # Soporta formato RIR stats "delegated-lacnic-*" (no "prefix-per-line")
    # Ejemplos:
    # lacnic|BR|ipv4|200.160.0.0|65536|19970210|allocated
    # lacnic|MX|ipv6|2806:10ae::|32|20190801|allocated
    #
    # Notas:
    # - IPv4: value = cantidad de direcciones
    # - IPv6: value = longitud de prefijo
    #
    with open(delegated_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) < 7:
                continue
            rir, cc, rtype, start, value, date, status = parts[:7]
            if rir.lower() != "lacnic":
                continue
            if status.lower() not in ("allocated", "assigned"):
                continue

            try:
                if rtype == "ipv4":
                    add_v4_range_to_trie(start, int(value), cc)
                elif rtype == "ipv6":
                    add_v6_prefix_to_trie(start, int(value), cc)
                else:
                    # asn u otros
                    continue
            except Exception:
                # líneas raras en delegated; se ignoran
                continue

def get_cc(prefix: str):
    # Devuelve CC por longest-match; None si no es LACNIC
    try:
        if ":" in prefix:
            net = ipaddress.IPv6Network(prefix, strict=False)
            key = t6.get_key(str(net.network_address) + f"/{net.prefixlen}")  # exact if present
            # PyTricia longest-match sobre el address:
            cc = t6.get(net.network_address) if net is not None else None
            return cc
        else:
            net = ipaddress.IPv4Network(prefix, strict=False)
            cc = t4.get(net.network_address)
            return cc
    except Exception:
        return None

def origin_asn_from_aspath(as_path: str):
    # Último ASN del AS_PATH como origin_asn (maneja AS_SET simple si aparece)
    toks = as_path.strip().split()
    if not toks:
        return ""
    last = toks[-1].strip()
    # En caso de {123,456} tomamos el contenido sin llaves (no perfecto, pero usable)
    if last.startswith("{") and last.endswith("}"):
        last = last[1:-1]
    return last

load_delegated_lacnic()

# Procesa RIB TABLE_DUMP2
# Campos esperados:
# 0:TABLE_DUMP2 1:ts 2:type(B/A) 3:peer_ip 4:peer_asn 5:prefix 6:as_path 7:origin 8:next_hop ...
read_lines = 0
exp_v4 = 0
exp_v6 = 0
invalid = 0

f4 = open(out_v4_path, "w", encoding="utf-8")
f6 = open(out_v6_path, "w", encoding="utf-8")

for line in open(rib_path, "r", encoding="utf-8", errors="ignore"):
    if not line.startswith("TABLE_DUMP2|"):
        continue
    read_lines += 1
    parts = line.rstrip("\n").split("|")
    if len(parts) < 9:
        continue

    ts       = parts[1].strip()
    peer_ip  = parts[3].strip()
    peer_asn = parts[4].strip()
    prefix   = parts[5].strip()
    as_path  = parts[6].strip()
    origin   = parts[7].strip()
    next_hop = parts[8].strip()

    if not prefix:
        continue

    # Validación prefix y filtro LACNIC vía delegated trie
    cc = get_cc(prefix)
    if cc is None:
        continue  # no es LACNIC

    oasn = origin_asn_from_aspath(as_path)

    out = f"{prefix}|{cc}|{origin}|{oasn}|{peer_ip}|{peer_asn}|{next_hop}|{as_path}|{ts}\n"
    if ":" in prefix:
        f6.write(out)
        exp_v6 += 1
    else:
        f4.write(out)
        exp_v4 += 1

    if read_lines % 1_000_000 == 0:
        print(f"[progreso] leidas={read_lines} exportadas_v4={exp_v4} exportadas_v6={exp_v6} invalid_prefix={invalid}", file=sys.stderr)

f4.close()
f6.close()

print(f"[fin] leidas={read_lines} exportadas_v4={exp_v4} exportadas_v6={exp_v6} invalid_prefix={invalid}", file=sys.stderr)
PY

done

echo "OK. Salidas en: $OUT_DIR"
