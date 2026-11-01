# Seguimiento de las correcciones del PR #13

Revisión del 1 de noviembre de 2026 preparada sobre `154c640`, en la rama original
`funcionalidad/clasificador-tickets-es`. Tras la validación, América Figueroa
autorizó commit, push y actualización del título/descripción exclusivamente de
#13. No se autoriza merge ni cambios en #14/#16. Los CSV fuente y artefactos
reales permanecen locales, fuera del control de versiones.

## Correspondencia con el comentario revisado

| Solicitud o recomendación | Resultado |
| --- | --- |
| Negaciones: `no es nada urgente`, `no es para nada urgente`, `no urgente`, `nada urgente`, `no creo que sea urgente` | Expresión corregida; regresiones e inferencia con artefacto sintético verificadas. |
| `revisión crítica` sin urgencia | No dispara; se exige contexto para `crítico/crítica`. |
| Mantener ejemplos positivos de la revisión | Regresiones para servicio, ERP, facturación y bodega. La regla permanece experimental y desactivada por defecto. |
| Diez claves por objetivo | Constructor compartido; sin regla aplicada se informa procedencia `model`, con `rule` y `trigger` nulos. |
| `top_3` frente a `top3` | Muestra e inferencia usan `top3` mediante el mismo constructor. |
| Preprocesamiento compartido | Normalización y construcción textual en `text_preprocessing.py`, con prueba de equivalencia. |
| Convención interna y API | Se conservan nombres internos; el futuro adaptador y los DTO públicos pertenecen al acuerdo del #14. No se modifica ese contrato desde este PR. |
| Versiones y Python del CI | Dependencias fijadas y artefacto sintético generado con Python 3.12.4; versiones guardadas en artefacto y métricas. |
| Descubrimiento de pruebas | CI usa `discover -s tests -t . -v`. Validación combinada con pruebas de #16 en una carpeta aislada, sin merge. |
| Coordinación del README y orden de integración | Procedimiento abajo; conservar ambas secciones cuando #16 incorpore el clasificador integrado. |
| Correcciones de etiquetas reproducibles | CSV aparte y manifiesto con hashes; aplicación previa a filtros y separación, pruebas sin modificar el origen. |
| Evitar fuga en una partición alternativa | Eliminado el fallback por filas; la separación falla si no puede cumplir las condiciones por grupos. |

## Evidencia ejecutada

- 25 pruebas propias aprobadas con Python 3.12.4.
- 29 pruebas aprobadas en una copia temporal combinando las 25 actuales y las
  cuatro de #16 (`cd2fa7b`). No se descargaron embeddings ni se usó PostgreSQL.
- Entrenamiento sintético: 12 registros, 9 de entrenamiento y 3 de prueba por
  objetivo, sin textos compartidos. Macro F1 / Weighted F1: tipo
  0,1667 / 0,2222; prioridad 0 / 0; área 0 / 0.
- Inferencia real del artefacto sintético con las seis frases negativas de la
  revisión, ejemplos positivos y reglas desactivadas. No confundir que una
  regla no se aplique con que el modelo estadístico acierte su etiqueta.
- Artefactos locales excluidos de Git en `ml/artifacts/revision_pr13/`.

La muestra solo comprueba ejecución, no calidad para tickets reales. Las
métricas históricas del CSV completo permanecen identificadas como anteriores;
no se atribuyen al dataset actualizado ni a esta revisión.

## Datos del usuario: preservación y exclusión autorizada

Se preservaron copias byte por byte de los dos archivos aportados, fuera del
control de versiones, en `ml/artifacts/revision_pr13/dataset_preservation/`.
La comparación del archivo de referencia (CP932) con el exportado UTF-8
identificó 139 registros editados y 63 cambios de prioridad: 60 de `medium` a
`high`, uno de `low` a `high` y dos de `low` a `medium`. También hay cambios
de texto y eliminación de etiquetas; se conservan en `cambios_usuario.json`.

`correcciones_prioridad.csv` registra las 63 diferencias con un motivo honesto
de importación manual. No afirma que se hayan revisado semánticamente todos
los tickets según los criterios de impacto. No se aplica automáticamente al
archivo editado, porque esas prioridades ya están cambiadas.

Los dos archivos contienen una capa CSV externa de tres columnas separadas
por punto y coma. Inicialmente el editado tenía 75 registros que no se podían
recuperar como 13 campos mediante lectura estricta. Con la referencia se
restituyeron 56 separadores de etiquetas opcionales de correspondencia única,
conservando sus valores eliminados como celdas vacías. No se restauró el texto
o la prioridad del archivo anterior.

`reconcile_ticket_export.py` reproduce una copia UTF-8 con 2.220 registros y
separa los 19 ambiguos en `registros_estructura_dudosa.json`, conservando su
información completa. Algunos cuerpos de esos registros mezclan respuesta;
no se adivina la frontera ni se usan para entrenar. La reproducción obtuvo
exactamente el mismo SHA-256 de la copia: `3b22106ca1bf3cfe1f1990e429bd721cc45edaca2c6dae61a56c39684a6e7d3e`.

De las 63 diferencias de prioridad, 62 están en la copia entrenable y una en
los registros de revisión. Las 139 ediciones permanecen preservadas en el
archivo de diferencias y la copia completa del usuario.

El usuario autorizó después excluir las 19 filas ambiguas del dataset final.
Se creó `ml/artifacts/revision_pr13/dataset_final/tickets_esp_utf8_sin_ambiguos.csv`
con los 2.220 registros restantes. Los originales y el respaldo de filas
excluidas permanecen intactos. Esta exclusión cierra el bloqueo estructural
para el conjunto final seleccionado; ya no se exige reparar esas 19 filas.
De los 63 cambios manuales de prioridad se conservan 62 en el conjunto final;
el restante pertenece a una fila cuya exclusión fue autorizada.

`dataset_final/validacion_final.json` registra autorización, números de
registro excluidos, hashes, conteos y correspondencia con las métricas. Se
verificó que el conjunto final es idéntico byte por byte al archivo entrenado,
por lo que no se repitió innecesariamente el entrenamiento. Las 25 pruebas
propias se ejecutaron nuevamente y aprobaron después de crear la copia final.

Los hashes y el diagnóstico están en `preservation_report.json`; se verificó
que las copias conservan exactamente los bytes de sus fuentes. Una futura
comparación de métricas deberá declarar que también hubo cambios de texto,
sin atribuir sus efectos únicamente al cambio de prioridades.

## Entrenamiento de la copia validada

Python 3.12.4, dependencias fijadas y reglas desactivadas. Los 2.220 registros
producen 2.218 después de eliminar duplicados; 1.774 de entrenamiento y 444 de
prueba por objetivo, con cero textos compartidos.

| Objetivo | Macro F1 | Weighted F1 |
| --- | ---: | ---: |
| Tipo | 0,6984 | 0,7116 |
| Prioridad | 0,6191 | 0,6540 |
| Área/cola | 0,6886 | 0,6084 |

Estos resultados corresponden a todo el conjunto final de 2.220 registros,
con las 19 exclusiones autorizadas declaradas, y no son directamente
comparables con el experimento histórico: cambiaron registros, textos y
particiones. El artefacto aprende `low`, `medium` y `high`; no aprende `critical`.
Se verificaron doce casos de inferencia sobre ese artefacto (seis negativos,
cinco positivos y uno con reglas forzadamente desactivadas). La auditoría
detectó 55 candidatos léxicos pendientes de revisión, no errores confirmados.

También se verificó un entrenamiento sintético con una corrección ficticia y
manifiesto; las métricas registraron exactamente una etiqueta cambiada.
`pip check` no encontró dependencias rotas. `git diff --check` y análisis de
sintaxis pasaron. Los errores temporales iniciales se resolvieron ejecutando
las pruebas con acceso al directorio temporal, sin eliminar validaciones.

## Coordinación con #16 y #14

Orden operativo propuesto: revisar e integrar #13; después actualizar la rama
original de #16, mover sus pruebas a `tests/ml/` y conservar las secciones del
clasificador y recuperación en `ml/README.md`. No hay dependencia funcional que
obligue ese orden. El CI instala dependencias semánticas cuando su archivo esté
presente, conservando las restricciones del clasificador.

La prueba aislada ya confirma que `tests.ml` no oculta `ml.semantic_retrieval`
con el descubrimiento desde la raíz. No afirma un merge real ni que el flujo
PostgreSQL + embeddings esté validado.

#14 debe actualizar posteriormente su referencia a este cambio, la estructura
uniforme, preprocesamiento y versiones. La política de `critical`, el mapeo
tipo/categoría y cola/área y la confianza pública requieren decisión del equipo.

## Publicación autorizada de #13

Título acordado: `Agrega clasificador ML de tickets TI`.
La publicación utiliza la descripción preparada y agrega el commit exacto y
evidencia verificable. La autorización de la autora para publicar no se
presenta como una aprobación independiente del equipo. El estado de publicación
se verifica en GitHub; no se ejecuta merge como parte de esta entrega.

## Lista de cierre del comentario

| Punto | Estado comprobado |
| --- | --- |
| Cinco negaciones nuevas y `revisión crítica` | Corregido y probado. |
| Cinco ejemplos positivos de la revisión | Conservados y probados. |
| Pruebas de reglas y confianza original preservada | Implementadas y aprobadas. |
| Diez claves uniformes por objetivo | Implementado y probado con/sin reglas. |
| `top3` en entrenamiento e inferencia | Corregido. |
| `text_preprocessing.py` compartido | Implementado y equivalencia probada. |
| Versiones exactas de pandas, scikit-learn, joblib, NumPy y SciPy | Fijadas; también threadpoolctl. |
| Artefacto generado con Python 3.12 | Completado en Python 3.12.4; metadatos de entorno guardados. |
| Dataset final sin las 19 filas autorizadas | Completado en copia separada, con trazabilidad. |
| Métricas y README locales actualizados | Completado; 2.218 filas tras deduplicar, 1.774/444 por objetivo. |
| Comando CI `discover -s tests -t .` | Corregido; verificación aislada conjunta de 29 pruebas ya aprobada. |
| Convención interna compatible | Conservada y documentada; acuerdo formal y DTO público en #14 pendientes. |
| Carpeta única de pruebas y README combinado en rama real de #16 | Preparado y probado en copia aislada; ajuste de esa rama pendiente. |
| Orden de merge | Propuesto y documentado; ejecución pendiente de autorización y revisión. |
| Descripción y título de squash del PR | Preparados; publicación autorizada exclusivamente para #13. |
| Aprobación final del equipo | Pendiente; no sustituida por esta verificación. |

Por tanto, las correcciones técnicas locales de #13 y su dataset final están
verificadas. No se declara el 100 % de cierre de coordinación/publicación de
todos los PR ni una revisión semántica exhaustiva de todas las etiquetas.
