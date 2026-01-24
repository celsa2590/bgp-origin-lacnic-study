# Interpretación de resultados  
## Atributo BGP ORIGIN en prefijos LACNIC

Este documento presenta lineamientos para interpretar correctamente los resultados obtenidos en el análisis del atributo **BGP ORIGIN** en prefijos de la región LACNIC.

Su objetivo es evitar lecturas erróneas, conclusiones apresuradas o atribuciones incorrectas de causa.

---

## 1. Qué representa este estudio (y qué no)

### Sí representa

- La **visión BGP** que tienen distintos colectores públicos.
- Cómo se propaga el atributo **ORIGIN** en rutas pertenecientes a LACNIC.
- Diferencias de comportamiento entre:
  - Países
  - Colectores
  - Protocolos (IPv4 vs IPv6)
- Cambios temporales en la distribución de ORIGIN.

### No representa

- Un juicio sobre la *calidad* de una red o de un operador.
- Un error de configuración por definición.
- El comportamiento real del plano de datos.
- La política interna completa de un operador.

---

## 2. Sobre el atributo BGP ORIGIN

El atributo ORIGIN es:
- **Well-known**
- **Mandatory**
- **Transitivo**

Sus valores posibles son:
- `IGP` (0)
- `EGP` (1)
- `INCOMPLETE` (2)

En la selección de rutas BGP, ORIGIN se evalúa **antes** que métricas internas como:
- MED
- IGP cost al next-hop

Por lo tanto, modificaciones deliberadas del ORIGIN pueden tener impacto directo en la selección de rutas.

---

## 3. Interpretación de porcentajes elevados de INCOMPLETE

Un porcentaje elevado de rutas con ORIGIN `INCOMPLETE` puede deberse a:

- Redistribución de rutas desde protocolos no-BGP.
- Uso de comandos `network` sin especificación explícita del ORIGIN.
- Herencia del valor por agregación o manipulación intermedia.
- Políticas históricas que no han sido revisadas.

Esto **no implica necesariamente** una mala práctica.

---

## 4. Casos observados de ORIGIN = EGP

Aunque el valor `EGP` se considera obsoleto desde el punto de vista histórico, el estudio muestra que:

- Sigue apareciendo de forma consistente en ciertos contextos.
- Puede estar asociado a decisiones operativas deliberadas.
- Puede utilizarse como **señal de preferencia** en redes con topologías complejas.

En particular, se observó que en redes con:
- Routers distribuidos geográficamente
- Múltiples puntos de salida (ASBR)

el atributo ORIGIN se utiliza como mecanismo adicional para influir en la selección de rutas antes de evaluar métricas internas.

---

## 5. Impacto de peers en las estadísticas globales

El análisis evidencia que:

- Un único peer puede alterar significativamente las estadísticas globales.
- La incorporación de nuevos peers en un colector puede:
  - Aumentar repentinamente la cantidad de rutas EGP o INCOMPLETE.
  - Cambiar la distribución por país.
- Comparaciones interanuales deben considerar cambios en:
  - Número de peers
  - Perfil de esos peers

Por esta razón, se incorporan análisis:
- Por colector
- Con exclusión selectiva de peers (exploratorio)

---

## 6. Diferencias entre colectores

Un mismo prefijo puede:

- Presentar valores ORIGIN distintos según el colector.
- Mantener el mismo `origin_asn` pero variar el ORIGIN.
- Reflejar políticas distintas aguas arriba del colector.

Esto refuerza la idea de que:
> **BGP no tiene una única verdad global, sino múltiples vistas coherentes localmente.**

---

## 7. IPv4 vs IPv6

El estudio muestra diferencias claras entre IPv4 e IPv6:

- Menor cantidad total de prefijos IPv6.
- Distribuciones ORIGIN distintas.
- Menor presencia de EGP en algunos contextos.
- Mayor homogeneidad en ciertos países.

Estas diferencias reflejan:
- Distintas etapas de madurez operativa.
- Menor historial de políticas heredadas en IPv6.

---

## 8. Evolución temporal

Las variaciones anuales deben interpretarse considerando:

- Cambios en peers activos.
- Cambios en políticas internas de operadores.
- Eventos operativos puntuales.
- Normalización progresiva de configuraciones.

Por este motivo, los valores anuales se calculan como **promedios de los valores mensuales**, evitando sobrerrepresentar rutas persistentes.

---

## 9. Interpretación responsable de los resultados

Este estudio propone una lectura basada en:

- Evidencia observacional.
- Contexto operativo.
- Validación con operadores cuando es posible.

No se pretende:
- Señalar errores.
- Exponer malas prácticas.
- Comparar operadores de forma competitiva.

Sino:
> **Visibilizar cómo se utiliza realmente BGP ORIGIN en la práctica.**

---

## 10. Conclusión interpretativa

El atributo ORIGIN, aunque simple en definición, continúa siendo utilizado como una herramienta operativa relevante.

Su uso actual refleja:
- Decisiones históricas
- Necesidades de ingeniería de tráfico
- Limitaciones del proceso de selección BGP

Comprender estos usos es clave para interpretar correctamente datos BGP y evitar conclusiones incompletas.

