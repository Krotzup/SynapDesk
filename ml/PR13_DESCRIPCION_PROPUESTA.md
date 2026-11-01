## Objetivo

Corregir los falsos positivos de la regla experimental, compartir la preparación
textual y estabilizar la salida del clasificador local de tickets en español.
Permitir correcciones humanas de prioridad reproducibles sin modificar el CSV.

## Cambios realizados

- Negaciones ampliadas y contexto requerido para `crítico/crítica`, con regresiones.
- Diez claves por objetivo y `top3` en muestra e inferencia, mediante constructor común.
- Preprocesamiento compartido y validación de entrada antes de cargar el artefacto.
- Versiones exactas y metadatos de entorno, dataset, clases y particiones.
- Correcciones por registro con validación de hashes y aplicación antes de filtros.
- Separación por grupos sin fallback que pueda compartir textos.
- CI con descubrimiento desde la raíz y preparación para las pruebas de #16.
- Documentación de criterios de impacto, límites de la regla y evidencia actual.

## Validación ejecutada

- Python 3.12.4 y versiones de `ml/requirements.txt` ya instaladas; sin instalación adicional.
- 25 pruebas propias aprobadas y 29 combinadas con las cuatro de #16 en una copia aislada.
- Entrenamiento e inferencia con la muestra sintética: 12 registros, partición 9/3,
  cero textos compartidos; Macro F1 / Weighted F1 de tipo 0,1667 / 0,2222,
  prioridad 0 / 0 y área 0 / 0. No constituyen métricas de calidad real.
- Verificadas las seis frases negativas del comentario, ejemplos positivos y
  reglas explícitamente desactivadas con un artefacto generado en Python 3.12.
- Cambios del usuario preservados: 139 registros editados, incluidos 63 cambios
  de prioridad, sin alterar las fuentes y fuera de Git.
- Copia reproducible con 2.220 registros de estructura comprobada, incluidos
  62 cambios de prioridad; 19 registros ambiguos excluidos por autorización
  del usuario y preservados por separado. El conjunto final está en
  `ml/artifacts/revision_pr13/dataset_final/tickets_esp_utf8_sin_ambiguos.csv`.
- Entrenamiento sobre 2.218 registros después de deduplicar: 1.774/444 por objetivo,
  cero textos compartidos. Macro F1 / Weighted F1: tipo 0,6984 / 0,7116;
  prioridad 0,6191 / 0,6540; área 0,6886 / 0,6084. Cubre el conjunto final
  seleccionado; las 19 exclusiones quedan declaradas.
- Doce casos de inferencia verificados con ese artefacto; `pip check` correcto.

## Estado y revisión pendiente

- Las 19 exclusiones autorizadas cierran el bloqueo estructural del dataset
  final; no se requiere inventar ni reparar sus fronteras cuerpo/respuesta.
- No reutilizar resultados históricos ni presentar el conjunto reducido como
  si conservara los 2.239 registros originales.
- Revisión humana de los motivos de prioridad y decisiones de contrato en #14.

La regla permanece experimental y desactivada por defecto. Este cambio no
implementa FastAPI, no modifica DTO públicos ni autoriza asignaciones automáticas.

## Coordinación

Título de squash propuesto: `Agrega clasificador ML de tickets TI`.
Tras integrar #13, en la rama original de #16 conservar ambas secciones del
README y unificar pruebas bajo `tests/ml/`, usando `-t .`. La validación aislada
del descubrimiento no equivale a ejecutar el prototipo con PostgreSQL/embeddings.

Esta descripción corresponde a las correcciones de #13. Su publicación fue
autorizada por América Figueroa. Esa autorización no sustituye la revisión
independiente de otro integrante. No se autoriza merge ni cambios en #14/#16.
