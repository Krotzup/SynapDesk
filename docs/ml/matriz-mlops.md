# Matriz MLOps propuesta

Versión 0.1 — 20 de noviembre de 2026. **Propuesta para revisión; no aprobada.**
Responde a la devolución PO/backend compartida por el solicitante. La evaluación
con modelos reales, las pruebas Render y las mediciones operativas pertenecen
a la habilitación posterior; no se presentan como nuevas funciones del PR #60.

## Datos, autorización y particiones

| Activo | Procedencia y versión | Autorización/evidencia pendiente |
| --- | --- | --- |
| Tickets de clasificación | [Ficha de procedencia](../../ml/DATASET_PROVENANCE.md): fuente externa, original local y derivado V2 tienen SHA diferentes | Acreditar autorización del archivo concreto y trazabilidad de selección/traducción; la licencia documentada no sustituye privacidad ni aprobación |
| Muestra sintética | `ml/samples/tickets_esp_sintetico.csv`, versionada | Solo verificación del pipeline; no reproduce métricas del dataset real |
| Corpus semántico | Inventario indexado, fuentes y revisión del corpus del informe de ejecución | Registrar permisos, hashes y revisión exacta; no basta el nombre del corpus |
| Consultas de evaluación | América coordina consultas autorizadas y anonimizadas | No recibidas; revisa relevancia una persona distinta de quien genera predicciones |
| Entradas para Gemini Free | Solo sintéticas o públicas expresamente autorizadas | Prohibidos tickets reales, datos personales, credenciales e información interna identificable; un texto anonimizado de tickets reales no queda autorizado por esa sola transformación |

Registrar SHA del CSV, manifiesto de correcciones, cantidades originales y
preparadas, exclusiones y razón, semilla y pertenencia a particiones. El
entrenamiento existente separa por grupos del texto preparado; no debe compartir
texto entre entrenamiento y prueba ni ajustar el vocabulario con la prueba.
La comparación experimental utiliza validación cruzada por grupos, descrita en
[evaluación del clasificador](../../ml/CLASSIFIER_EVALUATION.md).

La ficha de cada ejecución debe distinguir entrenamiento, validación para
seleccionar candidatos/umbrales y prueba reservada. No afirmar que existe una
partición adicional de validación si el informe solo contiene train/test o CV.
Si se elige un candidato con los resultados de CV, se necesita una prueba
reservada para estimar su desempeño final sin reutilizar esa selección.
Registrar solapamientos, clases ausentes y soporte por clase; no cambiar
silenciosamente a particiones por filas si faltan grupos.

## Matriz de métricas y responsables

| Componente | Registro y métricas | Resultado medido de habilitación | Criterio/umbral y responsable |
| --- | --- | --- | --- |
| Clasificación: tipo | Accuracy, macro/weighted F1, precision/recall/F1 y soporte por clase; confusión y catálogo exacto | Pendiente vincular informe del artefacto autorizado | América propone con datos; PO ratifica y Felipe valida adaptador |
| Clasificación: prioridad | Mismas métricas para `low`, `medium`, `high`; errores entre clases; sin regla `urgent_priority` | Pendiente vincular informe vigente del mismo dataset/modelo | Sin umbral de confianza aprobado; conservar confianza por objetivo |
| Clasificación: cola | Métricas por clase y soporte; distinguir cola de área de dominio | Pendiente junto al mapeo autorizado | Equipo define cola→área; Felipe valida contrato |
| Recuperación | Precision@K, Recall@K, MRR, score promedio de relevantes; resultados y juicios ordenados | Pendiente consultas autorizadas con revisión independiente | Perfil V2 experimental; sin umbral productivo aprobado |
| RAG: respuesta y fuentes | Pertinencia humana, fuentes visibles, exactitud y conservación de citas | Pendiente ejecución y revisión de los cinco casos | Propuesta EA3 enlazada abajo; PO revisa criterios con evidencia |
| RAG: abstención | Tasa de fallback correcto, ausencia de fuentes inventadas y falsos positivos/negativos | Pendiente casos positivos y sin evidencia revisados | No equiparar cualquier abstención a éxito |
| Operación | Tiempo de carga, latencia de inferencia/generación, RSS pico, tokens reportados y errores/timeouts | Pendiente medición con artefactos/modelos reales | América mide; Felipe revisa capacidad/seguridad; PO acuerda límites |

Los informes históricos de [ML](../../ml/CLASSIFIER_EVALUATION.md) son
antecedentes; no se copian sus cifras como medición del artefacto aún no
entregado. Distinguir explícitamente **propuesto**, **medido** y **ratificado**.
No se inventan porcentajes mínimos ni un corte global de confianza/relevancia.

## Evaluación reproducible y aceptación

La [especificación RAG EA3](evaluacion-rag-ea3.md) conserva el extracto recibido
de la sección 2.4 del curso. Sus cinco criterios numéricos son insumos propuestos,
no ratificación de la matriz integral. El evaluador local y su CLI conservan
fecha, commit, inventario indexado, modelos, consulta, top K, juicios, salida
RAG y observaciones; los registros privados quedan bajo `artifacts/`.

Para cada ejecución registrar también entorno exacto, huellas de configuración,
particiones, procedimiento de revisión independiente y responsable. Conservar
todos los resultados, incluidos fallos y abstenciones, sin seleccionar solo
los ejemplos favorables. No usar consultas reservadas para ajustar el perfil.
Un informe de fixtures verifica integración; no demuestra calidad ML/LLM.

La [ficha del clasificador](ficha-clasificador.md) define la entrega requerida
sin deserializar archivos desconocidos. Reproducir entrenamiento/evaluación con
los scripts existentes y las dependencias fijadas de `ml/requirements.txt`;
identificar el commit y mantener los datos privados fuera de Git.

Condiciones para habilitar inferencia real:

- [ ] Dataset, corpus y consultas autorizados y versionados por sus hashes.
- [ ] Artefacto confiable, SHA verificado y entorno exacto de entrenamiento/inferencia.
- [ ] Métricas por objetivo/clase y particiones verificables de esa versión.
- [ ] Relevancia y citas revisadas por persona independiente; fallback revisado.
- [ ] Mapeos explícitos aprobados y comportamiento ante desconocidos documentado.
- [ ] Umbrales propuestos a partir de mediciones y ratificación del PO registrada.
- [ ] Recursos y cuotas verificados; memoria y tiempo de carga medidos.
- [ ] Felipe aprueba transporte, autenticación y autorización del despliegue gratuito.

Ninguna casilla se cierra por pasar CI. La aprobación independiente del PR y
las ratificaciones funcionales se registran en GitHub por sus responsables.

## Gemini y capacidad gratuita

Identificador implementado: `gemini-3.5-flash-lite`. La documentación oficial
consultada el 20-11-2026 publica entrada/salida gratuitas para ese modelo en
[Free Tier](https://ai.google.dev/gemini-api/docs/pricing#gemini-3.5-flash-lite).
Esto identifica un candidato; no verifica acceso ni cuotas de la cuenta del
proyecto. Los [límites efectivos](https://ai.google.dev/gemini-api/docs/rate-limits)
se consultan en AI Studio y pueden cambiar. No se activó facturación ni se
efectuaron llamadas con datos reales para esta actualización.

América debe registrar modelo exacto, fecha, nivel Free y RPM/TPM/RPD observados
en la cuenta, sin publicar claves. Después medirá latencia y consumo con datos
sintéticos/autorizados para proponer límites globales y por usuario. No se
derivan cuotas de tablas ajenas a la cuenta ni se cambia automáticamente a pago.

Para Render, medir en Linux con un worker: entorno/contenedor exacto, CPU,
memoria disponible, RSS base y pico, tiempo de carga y primera/subsecuentes
inferencias. Medir clasificador y embeddings por separado y combinados; incluir
concurrencia prevista y margen. Se puede capturar RSS pico y tiempo con
`/usr/bin/time -v` ejecutando las inferencias sintéticas en el entorno controlado.
No cargar Joblib hasta verificar procedencia y SHA, ni descargar dependencias
o modelos durante una petición. Guardar comandos, versión/hash del artefacto,
salidas y limitaciones en el informe privado. Falta el artefacto autorizado:
no hay mediciones reales ni una afirmación de que quepan en la instancia Free.

El Web Service Free público con HTTPS y autenticación entre servicios es una
alternativa **en evaluación**. Felipe debe verificar la terminación TLS y su
compatibilidad con SEC-01B antes de aprobarla. El Blueprint privado de pago
existente no está autorizado para este presupuesto; no se aplicará. La imagen
ligera construida anteriormente no acredita embeddings ni despliegue real.
