#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
02_filter_lacnic_prefixes.py

Filtra un RIB en formato bgpdump (TABLE_DUMP2) para quedarse solo con prefijos LACNIC,
y genera archivos compactos v4 y v6.

Salida:
prefix|cc|origin|origin_asn|origin_asn_type|peer_ip|peer_asn|next_hop|as_path|timestamp|collector
"""

import argparse
import ipaddress
import pytricia
import sys
import re
import os

# ----------------------------
# Regex para AS_PATH parsing
# ----------------------------

ASN_RE = re.compile(r'^\d+$')
AS_SET_RE = re.compile(r'^\{[0-9, ]+\}$')
CONFED_SEQ_RE = re.compile(r'^\([0-9 ]+\)$')
CONFED_SET_RE = re.compile(r'^\[[0-9, ]+\]$')


# ----------------------------
# Normalización origin ASN
# ----------------------------

def normalize_origin_asn(as_path: str):
    if not as_path:
        return "", "unknown"

    tokens = as_path.strip().split()
    if not tokens:
        return "", "unknown"

    i = len(tokens) - 1

    while i >= 0:
        tok = tokens[i].strip()

        if not tok:
            i -= 1
            continue

        if ASN_RE.match(tok):
            return tok, "simple"

        if AS_SET_RE.match(tok):
            return "", "as_set"

        if CONFED_SEQ_RE.match(tok) or CONFED_SET_RE.match(tok):
            i -= 1
            continue

        # reconstrucción bloques partidos
        if tok.endswith(")") or tok.endswith("]"):
            open_char = "(" if tok.endswith(")") else "["
            block = tok
            i -= 1
            while i >= 0 and not block.startswith(open_char):
                block = tokens[i] + " " + block
                i -= 1
            continue

        if tok.endswith("}"):
            block = tok
            i -= 1
            while i >= 0 and not block.startswith("{"):
                block = tokens[i] + " " + block
                i -= 1
            if AS_SET_RE.match(block):
                return "", "as_set"
            continue

        i -= 1

    return "", "unknown"


# ----------------------------
# Carga delegated
# ----------------------------

def load_delegated(delegated_path):
    t4 = pytricia.PyTricia(32)
    t6 = pytricia.PyTricia(128)

    with open(delegated_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue

            parts = line.strip().split("|")
            if len(parts) < 7:
                continue

            rir, cc, rtype, start, value, date, status = parts[:7]

            if rir.lower() != "lacnic":
                continue

            if status.lower() not in ("allocated", "assigned"):
                continue

            try:
                if rtype == "ipv4":
                    start_ip = ipaddress.IPv4Address(start)
                    end_ip = ipaddress.IPv4Address(int(start_ip) + int(value) - 1)

                    for net in ipaddress.summarize_address_range(start_ip, end_ip):
                        t4.insert(str(net), cc)

                elif rtype == "ipv6":
                    net = ipaddress.IPv6Network(f"{start}/{value}", strict=False)
                    t6.insert(str(net), cc)

            except Exception:
                continue

    return t4, t6


def get_cc(prefix, t4, t6):
    try:
        if ":" in prefix:
            net = ipaddress.IPv6Network(prefix, strict=False)
            return t6.get(str(net.network_address))
        else:
            net = ipaddress.IPv4Network(prefix, strict=False)
            return t4.get(str(net.network_address))
    except Exception:
        return None


# ----------------------------
# MAIN
# ----------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rib", required=True, help="Archivo RIB en texto (bgpdump -m)")
    parser.add_argument("--delegated", required=True, help="Archivo delegated-lacnic")
    parser.add_argument("--collector", required=True, help="Nombre del colector")
    parser.add_argument("--out-dir", required=True, help="Directorio salida")

    args = parser.parse_args()

    rib_file = args.rib
    collector = args.collector

    base = os.path.basename(rib_file).replace(".txt", "")

    out_v4 = f"{args.out_dir}/{base}.lacnic.v4.txt"
    out_v6 = f"{args.out_dir}/{base}.lacnic.v6.txt"


    print("Cargando delegated...")
    t4, t6 = load_delegated(args.delegated)

    f4 = open(out_v4, "w", encoding="utf-8")
    f6 = open(out_v6, "w", encoding="utf-8")

    print("Procesando RIB...")

    read = 0
    exported_v4 = 0
    exported_v6 = 0

    with open(rib_file, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:

            if not line.startswith("TABLE_DUMP2|"):
                continue

            read += 1

            parts = line.strip().split("|")
            if len(parts) < 9:
                continue

            ts = parts[1]
            peer_ip = parts[3]
            peer_asn = parts[4]
            prefix = parts[5]
            as_path = parts[6]
            origin = parts[7]
            next_hop = parts[8]

            cc = get_cc(prefix, t4, t6)
            if cc is None:
                continue

            origin_asn, origin_type = normalize_origin_asn(as_path)

            out_line = (
                f"{prefix}|{cc}|{origin}|{origin_asn}|{origin_type}|"
                f"{peer_ip}|{peer_asn}|{next_hop}|{as_path}|{ts}|{collector}\n"
            )

            if ":" in prefix:
                f6.write(out_line)
                exported_v6 += 1
            else:
                f4.write(out_line)
                exported_v4 += 1

            if read % 1_000_000 == 0:
                print(f"[progreso] leidas={read} v4={exported_v4} v6={exported_v6}", file=sys.stderr)

    f4.close()
    f6.close()

    print("FIN")
    print(f"leidas={read}")
    print(f"exportadas_v4={exported_v4}")
    print(f"exportadas_v6={exported_v6}")


if __name__ == "__main__":
    main()
