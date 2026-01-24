# Metodología del estudio  
## Análisis del atributo BGP ORIGIN en prefijos LACNIC

Este documento describe paso a paso la metodología utilizada para analizar el atributo **BGP ORIGIN** en prefijos pertenecientes a la región **LACNIC**, utilizando tablas BGP (RIBs) obtenidas desde colectores públicos.

El objetivo principal es garantizar que el estudio sea **reproducible**, **auditable** y **extensible** por terceros.

---

## 1. Alcance del análisis

- Región analizada: **LACNIC**
- Protocolos:
  - IPv4
  - IPv6
- Fuente de datos:
  - RIBs BGP (RouteViews / RIS)
  - Archivos oficiales `delegated-lacnic`
- Horizonte temporal:
  - Análisis mensual
  - Agregación anual mediante promedios
- Perspectiva:
  - Por colector
  - Por país (CC)
  - Comparación entre colectores

---

## 2. Descarga de archivos delegated (LACNIC)

Se utilizan los archivos oficiales publicados por LACNIC que contienen las asignaciones de prefijos IPv4 e IPv6 por país.

Fuente oficial:

https://ftp.lacnic.net/pub/stats/lacnic/



Para cada año en estudio se descarga un archivo `delegated-lacnic` por mes, así tendrás 12 archivos que servirán para evaluar las condiciones mes a mes.


Ejemplo:

```bash
wget https://ftp.lacnic.net/pub/stats/lacnic/archive/2025/delegated-lacnic-20250120
```


## 3. Descarga de RIBs BGP por colector


Se descargan tablas BGP completas (RIBs) desde colectores públicos. Descargar un archivo por mes en caso de querer estudiar el año completo, de esta manera tendremos 12 RIBs.


Ejemplo (RouteViews Chile):

```bash
wget https://archive.routeviews.org/route-views.chile/bgpdata/2025.01/RIBS/rib.20250120.2200.bz2
```

Se selecciona una RIB por mes, manteniendo:

- Mismo día del mes
- Misma hora (cuando es posible)
- Esto permite comparar la evolución temporal sin introducir sesgos por diferencias horarias.


## 4. Conversión de RIBs a texto

Los archivos RIB (.bz2) se convierten a texto plano utilizando bgpdump.

Ejemplo:

```bash
bgpdump -m rib.20250101.0000.bz2 > ribcl_2501.txt
```

Formato resultante (ejemplo):


TABLE_DUMP2|1766268001|B|200.23.206.1|61525|1.0.133.0/24|6939 38040 23969|IGP|...


## 5. Organización de archivos por colector

Los archivos convertidos se organizan en carpetas por colector:

colectores/

├── PE/

├── CL/

├── MX/

├── BR_RIO/

└── BR_Fortaleza/

Cada carpeta contiene los RIBs mensuales correspondientes a ese colector.


## 6. Filtrado de prefijos LACNIC (IPv4 e IPv6)

Se filtran los RIBs para conservar únicamente los prefijos pertenecientes a la región LACNIC, utilizando los archivos delegated-lacnic.

Este paso genera dos archivos por mes y por colector:

IPv4

IPv6

Script utilizado:

```bash
scripts/process_ribs_lacnic_by_month.sh
```

Ejemplo de ejecución:

```bash
./scripts/process_ribs_lacnic_by_month.sh \
  colectores/RIS_UY/ \
  delegated_lacnic/2025/ \
  outputs/RIS_UY_lacnic_txt
```

Salida:

outputs/RIS_UY_lacnic_txt/
├── ribuy_2501.txt.lacnic.v4.txt
├── ribuy_2501.txt.lacnic.v6.txt
├── ribuy_2502.txt.lacnic.v4.txt
├── ribuy_2502.txt.lacnic.v6.txt
└── ...

## 7. Cálculo de estadísticas ORIGIN (por colector)

Para cada colector se calculan:

- Estadísticas mensuales:

   Total de prefijos
   Distribución ORIGIN (IGP / INCOMPLETE / EGP)

- Resumen anual:

   Promedio de porcentajes mensuales

Script utilizado:

```bash
scripts/origin_stats_by_month_and_annual.py
```

Ejemplo IPv4:

```bash
python3 scripts/origin_stats_by_month_and_annual.py \
  --in-dir outputs/RIS_UY_lacnic_txt \
  --only v4 \
  --out-dir stats/RIS_UY \
  --collector RIS_UY \
  --annual-mode avg
```

Ejemplo IPv6:

```bash
python3 scripts/origin_stats_by_month_and_annual.py \
  --in-dir outputs/RIS_UY_lacnic_txt \
  --only v6 \
  --out-dir stats/RIS_UY \
  --collector RIS_UY \
  --annual-mode avg
```


Nota metodológica importante

El resumen anual no corresponde a una suma de prefijos, sino al promedio de los valores mensuales, evitando sobre-representar prefijos observados repetidamente en múltiples meses.


## 8. Estadísticas por país (CC)

A partir de los archivos filtrados por colector, se generan estadísticas agrupadas por país (CC), según el código presente en el archivo delegated-lacnic.

Script utilizado:

scripts/origin_stats_by_cc.py


Ejemplo:

```bash
python3 scripts/origin_stats_by_cc.py \
  --in-dir outputs/BRFOR_lacnic_txt \
  --only v4 \
  --out-dir stats/BRFOR \
  --collector BRFOR \
  --scope all \
  --top 10
```

Esto permite identificar países con mayor proporción de rutas INCOMPLETE o EGP.


## 9. Limitaciones del estudio

- Los datos reflejan la vista del colector, no una verdad global.

- Cambios en peers activos pueden alterar los resultados.

- El atributo ORIGIN puede ser utilizado de forma operativa más allá de su definición original.

- No se infiere intención errónea o mala práctica.


## 10. Reproducibilidad

El pipeline completo puede ejecutarse desde cero siguiendo este documento y el README.md, utilizando únicamente herramientas públicas y software libre.
