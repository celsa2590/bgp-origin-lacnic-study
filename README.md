# BGP ORIGIN en la práctica  
## Análisis de inconsistencias observadas en prefijos LACNIC

Este repositorio documenta un estudio reproducible sobre el uso del atributo **BGP ORIGIN** en prefijos pertenecientes a la región **LACNIC**, a partir del análisis de tablas BGP (RIBs) obtenidas desde distintos colectores públicos.

El trabajo analiza la distribución de los valores **IGP**, **INCOMPLETE** y **EGP**, su evolución temporal y las diferencias observadas entre colectores, países y peers.

---

## 🎯 Objetivos del estudio

- Analizar el uso real del atributo **BGP ORIGIN** en prefijos LACNIC.
- Identificar inconsistencias del atributo entre distintos colectores de rutas.
- Evaluar la evolución temporal del atributo (mensual y anual).
- Obtener estadísticas agregadas por país (CC).
- Identificar el impacto de decisiones operativas de ciertos peers en los resultados globales.
- Proveer un **pipeline reproducible** para la comunidad técnica.

---

## 📦 Fuentes de datos

### Delegated files (LACNIC)
Archivos oficiales de asignaciones de prefijos IPv4 e IPv6:
https://ftp.lacnic.net/pub/stats/lacnic/


Ejemplo:
```bash
wget https://ftp.lacnic.net/pub/stats/lacnic/archive/2025/delegated-lacnic-20250101
```

## RIBs BGP (RouteViews / RIS)

- Tablas BGP completas desde colectores públicos:

https://archive.routeviews.org/route-views.chile/bgpdata/2025.01/RIBS/

## 🧱 Estructura del repositorio

bgp-origin-lacnic-study/
├── colectores/          # RIBs convertidos a texto, organizados por colector
├── delegated_lacnic/    # Archivos delegated-lacnic por año
├── scripts/             # Scripts de procesamiento y análisis
├── outputs/             # RIBs filtrados (solo prefijos LACNIC, v4/v6)
├── stats/               # Resultados estadísticos (mensual, anual, por país)
├── docs/                # Documentación metodológica
├── README.md
└── .gitignore

⚠️ Los directorios colectores/, outputs/ y stats/ no se versionan por contener grandes volúmenes de datos.

🛠️ Dependencias

bgpdump
Python ≥ 3.8
Herramientas estándar de Unix (awk, grep, sort, uniq)
Instalación de bgpdump (Debian/Ubuntu):

```bash
sudo apt install bgpdump
```

🔬 Metodología (resumen)

Descarga de archivos delegated-lacnic por mes del año seleccionado.
Descarga de RIBs BGP por colector y mes.
Conversión de RIBs a texto usando bgpdump.
Filtrado de prefijos exclusivamente LACNIC (IPv4 e IPv6).
Generación de estadísticas ORIGIN:
- Por mes
- Promedios anuales
- Por país (CC)
Análisis comparativo entre colectores.
Identificación de peers con impacto significativo en los resultados.

El detalle completo del pipeline se encuentra en:
📄 docs/methodology.md

▶️ Ejecución básica
Filtrar RIBs a prefijos LACNIC (por mes)

./scripts/process_ribs_lacnic_by_month.sh \
  colectores/RIS_UY/ \
  delegated_lacnic/2025/ \
  outputs/RIS_UY_lacnic_txt

Genera, por cada mes:
*.lacnic.v4.txt
*.lacnic.v6.txt

Estadísticas ORIGIN por mes y anual
IPv4:
python3 scripts/origin_stats_by_month_and_annual.py \
  --in-dir outputs/RIS_UY_lacnic_txt \
  --only v4 \
  --out-dir stats/RIS_UY \
  --collector RIS_UY \
  --annual-mode avg

IPv6:
python3 scripts/origin_stats_by_month_and_annual.py \
  --in-dir outputs/RIS_UY_lacnic_txt \
  --only v6 \
  --out-dir stats/RIS_UY \
  --collector RIS_UY \
  --annual-mode avg

Estadísticas por país (CC)
python3 scripts/origin_stats_by_cc.py \
  --in-dir outputs/BRFOR_lacnic_txt \
  --only v4 \
  --out-dir stats/BRFOR \
  --collector BRFOR \
  --scope all \
  --top 10

⚠️ Consideraciones importantes

El atributo ORIGIN puede ser modificado deliberadamente por operadores como parte de decisiones operativas internas.

Cambios en la composición de peers de un colector pueden alterar significativamente las estadísticas agregadas.

El estudio contempla análisis con y sin exclusión de peers específicos, cuando corresponde.

📣 Contexto académico y operativo

Este trabajo se inspira y dialoga con discusiones presentadas en foros técnicos como RIPE y LACNIC, incluyendo charlas sobre el uso práctico del atributo BGP ORIGIN en redes reales.

El objetivo no es juzgar configuraciones, sino entender y visibilizar prácticas operativas existentes.

👤 Autora

Celsa Sánchez
Ingeniera en Telecomunicaciones
NIC Chile
Embajadora I+D LACNIC 2024

📄 Licencia

Este repositorio se publica con fines educativos y de investigación.
Los datos BGP pertenecen a sus respectivas fuentes originales.
