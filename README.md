# 📊 BGP ORIGIN Behavior in the LACNIC Region

## Overview

This project analyzes the behavior of the BGP **ORIGIN attribute** across multiple route collectors in the LACNIC region.

The study focuses on:

- Consistency of ORIGIN across collectors
- Temporal stability (monthly and daily)
- Identification of strong inconsistency cases
- Correlation between ORIGIN and **RPKI validation**

---

## 🎯 Objectives

- Evaluate whether ORIGIN is consistent across the Internet
- Identify prefixes with conflicting ORIGIN values
- Analyze behavior differences per collector
- Determine whether inconsistencies are related to RPKI

---

## 📦 Data Sources

### BGP Data
- RouteViews collectors:
  - CL (Chile)
  - MX (Mexico)
  - BR_FOR (Fortaleza)
  - BR_RIO (Rio de Janeiro)
  - PE (Peru)

### Allocation Data
- LACNIC delegated files:
https://ftp.lacnic.net/pub/stats/lacnic/archive/


### RPKI Data
- Historical ROAs:
https://ftp.ripe.net/rpki/lacnic.tal/


---

## ⚙️ Pipeline

```text
01 → Convert RIB to text (bgpdump)
02 → Filter LACNIC prefixes
03 → Compute ORIGIN statistics
05 → Detect strong inconsistency cases
06 → Correlate ORIGIN with RPKI
07 → Aggregate results
08 → Daily analysis (optional)
```

### 📁 Repository Structure

scripts/        → analysis scripts  

data/           → input data (not versioned)  

outputs/        → filtered prefixes (not versioned)  

stats/          → analysis results  

stats_daily/    → daily analysis outputs  

docs/           → methodology and notes  


Note: Large datasets (RIBs, outputs) are intentionally excluded from the repository.

---

### 🔧 Requirements

Install dependencies:  

apt install bgpdump  

pip install pytricia  


## 🧩 Scripts Description

01_dump_rib_to_text.sh  
→ Converts RIB dumps to text format using bgpdump

02_filter_lacnic_prefixes.py  
→ Filters only LACNIC prefixes using delegated files

03_origin_monthly_annual.py  
→ Computes ORIGIN statistics (IGP, INCOMPLETE, EGP, MIXED)

05_strong_cases.py  
→ Detects prefixes with inconsistent ORIGIN across collectors

06_rpki_correlation.py  
→ Correlates ORIGIN with RPKI validation

07_rpki_summary_from_reports.py  
→ Aggregates RPKI results across collectors

08_origin_daily_stats.py  
→ Computes daily ORIGIN statistics (time-series analysis)



## 🔍 ORIGIN Categories

- IGP  
- INCOMPLETE  
- EGP  
- MIXED → prefix observed with different ORIGIN values across paths  



## 📊 Example Result

BR_RIO:  
MIXED ≈ 90%  

CL:  
MIXED ≈ 0%  
  
→ Different collectors observe completely different routing behavior  


---


### 🚀 How to Reproduce the Analysis  

1. Download RIB

Example:  

wget https://archive.routeviews.org/route-views.chile/bgpdata/2025.01/RIBS/rib.20250101.0000.bz2

2. Convert to text  

./scripts/01_dump_rib_to_text.sh rib.bz2 output_dir CL

3. Download delegated file  

wget https://ftp.lacnic.net/pub/stats/lacnic/archive/2025/delegated-lacnic-20250101

4. Filter LACNIC prefixes  

python3 scripts/02_filter_lacnic_prefixes.py \
  --rib data/text/CL/CL_20250101_0000.txt \
  --delegated data/delegated/2025/delegated-lacnic-202501 \
  --collector CL \
  --out-dir outputs/CL

5. Compute ORIGIN statistics  

python3 scripts/03_origin_monthly_annual.py \
  --in-dir outputs/CL \
  --only v4 \
  --out-dir stats/CL \
  --collector CL \
  --annual-mode avg

6. Strong inconsistency cases  

python3 scripts/05_strong_cases.py \
  --in-dirs outputs/CL outputs/MX outputs/BR_RIO \
  --only v4 \
  --out-dir stats/strong_cases

7. RPKI correlation  

python3 scripts/06_rpki_correlation.py \
  --in-dirs outputs/CL outputs/MX outputs/BR_RIO \
  --only v4 \
  --roa-dir data/rpki_raw \
  --out-dir stats/rpki/v4 \
  --scope all

8. Daily analysis (optional)  

Daily analysis allows:  
- temporal stability evaluation  
- anomaly detection  
- operational behavior analysis  

Example for April 2026:  
./scripts/run_daily_april_2026.sh

### 📊 Key Findings  

ORIGIN is not globally consistent
Behavior strongly depends on the collector
~8% of prefixes show persistent inconsistencies
RPKI validation does not explain ORIGIN differences
INCOMPLETE often correlates with higher RPKI validity
EGP is still used operationally in modern networks

### Notes  

This project analyzes control-plane data only
Results depend on collector visibility
RPKI snapshots must match the same period as BGP data

## ⚠️ Limitations

- Results depend on collector visibility  
- Only control-plane data is analyzed  
- No data-plane validation  
- RPKI snapshots must match BGP timeline  

### 📬 Author

Celsa Sánchez  
NIC Chile
