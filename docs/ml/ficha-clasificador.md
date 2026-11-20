# Ficha de entrega del clasificador

20-11-2026. **Pendiente de artefacto autorizado; no habilita inferencia real.**

| Campo obligatorio | Estado/evidencia a aportar |
| --- | --- |
| Responsable y fuente confiable | América entrega y autoriza el archivo por canal controlado; pendiente |
| Archivo Joblib y versión | Pendiente; no se sustituye por un artefacto de muestra |
| SHA-256 | Pendiente calcular sobre el archivo entregado y contrastar con el valor comunicado por fuente confiable |
| Python y dependencias exactas | Pendiente entorno de ese artefacto; `ml/requirements.txt` fija dependencias del pipeline, no prueba su uso histórico |
| Dataset/manifiesto y licencia | Vincular versión/SHA y autorización con [procedencia](../../ml/DATASET_PROVENANCE.md) |
| Evaluación y particiones | Informe vigente por objetivo/clase, soporte, confusión, semilla y separación por textos; pendiente asociar a esta versión |
| Reglas | `urgent_priority` retirada; inferencia sin reglas; rechazar artefacto que la habilite |
| Catálogos y mapeos | Aprobar tipo→categoría y cola→área; no hay mapeos ratificados disponibles |
| Rendimiento | Carga, inferencia, RSS base/pico y entorno Linux; pendiente medición |
| Aprobaciones | ML sobre fuente/artefacto; equipo sobre mapeos; Felipe sobre adaptador/operación; pendientes |

El SHA identifica bytes, no acredita confianza por sí solo. Joblib puede
ejecutar código al cargar: solo se deserializa el artefacto de fuente autorizada,
en entorno controlado, después de verificar la huella. Registrar entorno exacto
y probar compatibilidad antes de habilitarlo; no entrenar al arrancar la API.

## Contrato de salida y degradación existente

El adaptador conserva `predictedType`, `suggestedQueue`, `predictedPriority`,
`predictedCategory`, `predictedArea`, `confidences` por `type`/`priority`/`queue`
y metadatos `modelName`/`modelVersion`. La confianza global `confidence` es null.
Los valores confirmados del ticket no se sobrescriben.

`CLASSIFIER_CATEGORY_MAPPING` y `CLASSIFIER_AREA_MAPPING` son mapeos explícitos,
sin equivalencias implícitas. Un tipo o cola sin mapeo conserva su etiqueta
predicha y deja categoría/área en null. Prioridad fuera de `low|medium|high`,
etiquetas vacías, objetivos ausentes o probabilidades inválidas producen
`CLASSIFICATION_UNAVAILABLE`; el ticket se conserva. La salida debe contrastarse
con los catálogos del artefacto autorizado durante su revisión de integración.

No existe un umbral aprobado de confianza insuficiente. Se muestran las
confianzas individuales como estimaciones, sin confirmar campos ni aplicar una
regla de negocio automática. Si el equipo exige abstención por objetivo debe
proponerla con evaluación y actualizar el contrato antes de activarla.

La ficha se completa con evidencias de la misma versión, no con valores
inventados ni con métricas de otro artefacto. Véase la [matriz MLOps propuesta](matriz-mlops.md).
