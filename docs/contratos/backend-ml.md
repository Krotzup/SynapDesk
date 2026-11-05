# Contrato inicial entre backend y Machine Learning

## Estado y referencia

**Provisional — propuesta de integración pendiente de aprobación.**

El clasificador del [PR #13](https://github.com/Krotzup/SynapDesk/pull/13) se incorporó a `main` mediante `0d37072`; el [contrato documental #14](https://github.com/Krotzup/SynapDesk/pull/14), mediante `55fb431`. La revisión inicial del 29 de octubre de 2026 describía `5c99424`. Esta actualización del 5 de noviembre distingue el código integrado de las opciones experimentales de la rama de mejoras del clasificador.

La integración FastAPI del clasificador sigue sin implementarse. Las variantes, evaluaciones y herramientas de exportación descritas en la documentación ML son experimentales hasta su revisión e integración; su presencia no aprueba taxonomías, reglas de negocio, umbrales ni un modelo de producción.

Las secciones diferencian el comportamiento observado en el PR de las condiciones propuestas para integrarlo. Este documento será la referencia única del contrato; debe evitarse mantener dos versiones diferentes en el PR de implementación ML y en el PR documental.

| Clasificación | Significado en esta revisión |
| --- | --- |
| `IMPLEMENTATION_OBSERVED` | Comportamiento contrastado por lectura de código versionado; no implica ejecución independiente. |
| `CONTRACT_APPROVED` | Acuerdo funcional aprobado explícitamente por el equipo; no se asigna este estado a propuestas por aparecer en el código. |
| `PENDING_DECISION` | Decisión de integración todavía pendiente; el contrato continúa provisional. |
| `PROPOSAL_PENDING_TEAM_DECISION` | Propuesta del frontend o del equipo que no constituye un campo público obligatorio. |

### Evidencia técnica utilizada

Las referencias relativas permiten contrastar la implementación correspondiente a la revisión de este documento. Para reproducir una entrega se debe fijar su commit, artefacto, hashes y entorno, sin asumir que una rama de trabajo está aprobada:

- [Inferencia y preprocesamiento compartido](../../ml/predict_ticket.py), [normalización](../../ml/text_preprocessing.py) y [salida uniforme](../../ml/prediction_output.py).
- [Reglas de prioridad](../../ml/ticket_rules.py) y [entrenamiento](../../ml/train_ticket_classifier.py).
- [Pruebas ML](../../tests/ml/), [README](../../ml/README.md) y [muestra sintética](../../ml/samples/tickets_esp_sintetico.csv).
- [Evaluación experimental](../../ml/CLASSIFIER_EVALUATION.md) y [exportación/procedencia del dataset](../../ml/CORRECCIONES_PRIORIDAD.md).

## Propósito y alcance

Acordar la entrada, salida, adaptación al dominio, versionado, validaciones y manejo de errores entre FastAPI y el clasificador de tickets.

El baseline del PR analiza el asunto y cuerpo de un ticket y produce tres salidas:

- tipo de ticket;
- prioridad estimada;
- cola o área responsable sugerida.

Este contrato no cubre embeddings, pgvector, recuperación semántica, RAG ni generación de recomendaciones mediante LLM. Las características TF-IDF del clasificador no son los embeddings documentales que se almacenarán con pgvector.

Las predicciones asistirán al agente y no modificarán automáticamente los valores validados del ticket.

## Decisiones técnicas respaldadas por el PR

| Elemento | Implementación observada | Alcance de la decisión |
| --- | --- | --- |
| Entradas | `subject` y `body` | Información disponible al crear un ticket |
| Objetivos | `type`, `priority`, `queue` | Tres clasificadores independientes |
| Framework | scikit-learn | Baseline actual; no exige PyTorch ni TensorFlow |
| Vectorización | `TfidfVectorizer` | Texto con unigramas y bigramas |
| Clasificador | `SGDClassifier(loss="log_loss")` | Una pipeline por objetivo |
| Balanceo | `class_weight="balanced"` | Configuración del baseline |
| Serialización | Joblib | Artefacto `.joblib` con pipelines y metadatos |
| Inferencia | Función Python y comando de consola | No hay endpoint ML ni integración FastAPI implementados |
| Identificación | `modelName`, `modelVersion` | Nombre y versión devueltos por la inferencia |
| Evaluación | Macro F1, Weighted F1 y reporte por clase | Resultados del modelo separados de resultados con reglas |
| Exclusión de entradas | `answer` no se utiliza | Evita usar una respuesta que no existe al crear el ticket |

Configuración adicional observada: `max_features=120000`, `ngram_range=(1, 2)`, `min_df=2`, `sublinear_tf=True`, `strip_accents="unicode"`, `alpha=1e-5`, `max_iter=1000` y `tol=1e-3`.

El entrenamiento usa una proporción de prueba de `0.2` y semilla predeterminada `42`, aplicada también al clasificador. Usa `GroupShuffleSplit` por texto preparado; ante grupos insuficientes o entrenamiento con menos de dos clases falla sin alternativa que separe filas del mismo grupo. La evaluación experimental añade `GroupKFold` y ajustes internos, separados del entrenamiento habitual. Los caracteres pueden habilitarse por objetivo, sin cambiar el baseline predeterminado.

Estos parámetros describen el experimento, no umbrales definitivos de calidad ni un compromiso de conservar el algoritmo en todas las versiones.

## Arquitectura de integración propuesta

Para mantener el monolito modular, se propone un adaptador Python interno del backend que cargue el artefacto una vez por proceso y ejecute inferencias sin entrenar durante una petición.

La propuesta requiere implementación y aprobación. El PR actual carga el archivo mediante `joblib.load` en cada llamada a `predict`; todavía no cumple el ciclo de carga propuesto para FastAPI.

No se requiere inicialmente un microservicio ni una nueva API HTTP para el modelo. El frontend solo se comunicará con el backend.

Flujo previsto:

1. El backend valida y registra el ticket.
2. El adaptador transforma `title` y `description` a `subject` y `body`.
3. Se ejecutan las pipelines del artefacto autorizado.
4. El backend valida las salidas y las adapta al dominio cuando exista un mapeo aprobado.
5. El backend persiste la predicción, la versión y los metadatos permitidos.
6. El frontend recibe únicamente la representación pública acordada.

El registro del ticket no dependerá del éxito del clasificador. El comportamiento síncrono o asíncrono, los tiempos máximos y los reintentos requieren una decisión adicional.

## Entrada: dominio y componente ML

| Campo del backend | Campo de ML | Regla |
| --- | --- | --- |
| `title` | `subject` | Texto no vacío |
| `description` | `body` | Texto no vacío |
| `ticketId` | No se envía actualmente | El backend conserva la asociación con el ticket |
| `requestId` | No se envía actualmente | El backend conserva la trazabilidad de la operación |

Entrada textual del componente ML:

```json
{
  "subject": "No puedo acceder al correo corporativo",
  "body": "Outlook rechaza mi contraseña y necesito recuperar el acceso."
}
```

La función actual es `predict(model_path, subject, body, business_rules=None)`. Recibe una ruta de artefacto además del texto; esa ruta será configuración interna del backend y nunca un parámetro libre enviado por el frontend.

`ticketId` y `requestId` serán metadatos de la operación gestionados por el backend. No deben exigirse como campos devueltos por un modelo que actualmente no los recibe. En una futura ejecución asíncrona, el trabajo deberá transportarlos explícitamente.

### Preprocesamiento y validación

El formato textual actual es:

```text
Asunto: <subject>
Descripcion: <body>
```

Entrenamiento e inferencia reutilizan `build_text` y `normalize_text` de `ml/text_preprocessing.py`: normalizan espacios y secuencias literales `\n`. La inferencia rechaza tipos no textuales y campos simultáneamente vacíos tras normalizar antes de cargar Joblib. No se eliminan palabras de urgencia para alinear textos con etiquetas.

La validación debe comprobar el contenido antes de agregar los prefijos. Un texto formado únicamente por `Asunto:` y `Descripcion:` no se considerará contenido válido. **`RESOLVED_IN_OBSERVED_IMPLEMENTATION`:** el entrenamiento normaliza `subject` y `body` y descarta las filas donde ambos están vacíos antes de construir el texto. La prueba versionada de preparación incluye una fila con ambos campos vacíos y comprueba el filtrado; se verificaron el código y la existencia de esa prueba, no su ejecución en esta tarea. El filtrado conserva filas con al menos uno de los dos campos no vacío; esto no sustituye la validación propuesta del backend, que exige ambos campos.

El backend conservará el título y descripción originales. No se traducirá ni se alterará su significado. Los límites de longitud quedan pendientes de acuerdo. Los identificadores, contraseñas, credenciales y adjuntos no serán características del clasificador.

## Salida nativa del componente ML

El comando de inferencia produce una estructura como la siguiente. El ejemplo está abreviado; omite los metadatos uniformes descritos debajo. Los valores numéricos son ilustrativos, no una ejecución verificada:

```json
{
  "modelName": "synapdesk_tfidf_sgd_ticket_classifier",
  "modelVersion": "20261005163000",
  "businessRulesEnabled": false,
  "predictions": {
    "clasificacion_sugerida": {
      "label": "incident",
      "confidence": 0.71,
      "top3": [
        { "label": "incident", "confidence": 0.71 },
        { "label": "request", "confidence": 0.18 },
        { "label": "problem", "confidence": 0.08 }
      ],
      "decision": "model"
    },
    "prioridad_estimada": {
      "label": "medium",
      "confidence": 0.65,
      "top3": [
        { "label": "medium", "confidence": 0.65 },
        { "label": "high", "confidence": 0.20 },
        { "label": "low", "confidence": 0.10 }
      ],
      "decision": "model"
    },
    "area_responsable": {
      "label": "it_support",
      "confidence": 0.62,
      "top3": [
        { "label": "it_support", "confidence": 0.62 },
        { "label": "technical_support", "confidence": 0.25 },
        { "label": "service_outages_and_maintenance", "confidence": 0.13 }
      ],
      "decision": "model"
    }
  }
}
```

### Reglas del formato

- `modelName` y `modelVersion` serán cadenas no vacías.
- El artefacto baseline deberá incluir los tres objetivos declarados. La ausencia inesperada de uno es un error de salida, no una predicción válida con valor vacío.
- Cada objetivo incluirá `label` y `decision`.
- Sin intervención de reglas, el baseline utiliza `predict_proba`; la confianza estadística por objetivo debe ser finita y estar dentro de `[0, 1]`. Cuando interviene una regla, `confidence` es `null` y la probabilidad original, si existe, se conserva en `model_confidence`; no se asigna probabilidad estadística a la etiqueta impuesta.
- `top3` contendrá hasta tres clases diferentes del catálogo del objetivo, ordenadas por probabilidad estadística descendente. La regla de urgencia no lo modifica; su primera etiqueta puede diferir de la etiqueta final impuesta por la regla.
- La suma de `top3` puede ser menor que `1` si existen más de tres clases.
- Una futura versión sin probabilidades requerirá actualizar el contrato; no se inventarán valores de confianza.
- La muestra del entrenamiento y la inferencia comparten `top3` y el formato definido por `prediction_output.py`.
- `modelVersion` es actualmente una marca temporal UTC con formato `YYYYMMDDHHMMSS`, no una versión semántica. Debe conservarse como texto y asociarse al artefacto exacto.

Los valores numéricos de `confidence` son estimaciones del modelo, no garantías ni porcentajes de acierto individual demostrados. El valor `null` en una decisión por regla no equivale a cero ni a certeza total. Los umbrales `0.75` y `0.50` propuestos en el PR no se adoptan como política aprobada.

La salida nativa conserva camelCase en la envoltura y snake_case en los metadatos internos. Cada objetivo devuelve siempre diez claves: `label`, `confidence`, `top3`, `decision`, `decision_source`, `confidence_source`, `model_label`, `model_confidence`, `rule` y `trigger`, con `null` cuando no aplican. Esto no redefine el DTO público ni autoriza renombrar campos de la API; el adaptador pendiente deberá hacer la conversión acordada.

## Correspondencia con el dominio y frontend

| Objetivo del dataset | Salida ML | Campo del dominio | Estado |
| --- | --- | --- | --- |
| `type` | `clasificacion_sugerida.label` | `predictedCategory` | No equivalente automáticamente; definición pendiente |
| `priority` | `prioridad_estimada.label` | `predictedPriority` | Coincidencia técnica de valores `low`, `medium`, `high`, sujeta al catálogo del artefacto y a la política funcional pendiente |
| `queue` | `area_responsable.label` | `predictedArea` | Debe aprobarse correspondencia de colas con áreas del proyecto |
| Metadato del artefacto | `modelName` | `modelName` | Directo |
| Metadato del artefacto | `modelVersion` | `modelVersion` | Directo |
| Metadatos del backend | No los devuelve ML | `id`, `ticketId`, `createdAt` | Generados o asociados por el backend |
| Probabilidad por objetivo | `confidence` numérico; `model_confidence` si interviene regla | `confidence` único actual | Representación pendiente; `confidence: null` por regla no se agrega como probabilidad |

### Tipo no equivale necesariamente a categoría

El PR documenta tipos como `incident`, `request`, `problem` y `change`. No demuestra que el modelo clasifique categorías temáticas como red, hardware o software.

Antes de asignar `clasificacion_sugerida` a `predictedCategory`, el equipo deberá decidir si la categoría del MVP representará el tipo de ticket o si el dominio necesita un campo independiente. Mientras no exista ese acuerdo, no se copiará la etiqueta a `predictedCategory`; se conservará como resultado nativo interno y el campo público permanecerá `null` si se expone.

### Catálogo vigente de prioridad

Tras la confirmación de América Figueroa, el catálogo de esta rama se limita a
`low`, `medium` y `high` en ML, frontend y persistencia. Se retiraron `critical`
y la regla que la imponía por señales léxicas. El CSV original y V2 no contienen
esa clase y no requieren cambios adicionales.

La migración `0003_retirar_prioridad_critical`, posterior a la persistencia de
autenticación ya integrada, convierte los tickets existentes de `critical` a
`high` e instala la restricción de tres valores. Se conserva la migración
inicial como antecedente. El downgrade restaura el catálogo anterior sin
reconstruir etiquetas convertidas. La migración requiere aplicación explícita;
no se ejecutó al preparar este cambio.

### Confianza única frente a confianza por objetivo

El [modelo de dominio](../arquitectura/modelo-dominio.md) actual contiene un único `confidence`. ML produce confianza por objetivo, que no debe promediarse ni sustituirse por el máximo sin una definición aprobada; cuando una regla impone la prioridad, su `confidence` es `null` y se distingue de `model_confidence`. La adaptación a la API pública seguirá los campos camelCase del [contrato frontend–backend](frontend-backend.md), UUID como texto y fechas UTC gestionadas por el backend; no se presenta la salida interna mixta como un nuevo formato público aprobado.

Se propone preservar internamente las confianzas por objetivo y actualizar el dominio, la persistencia, el contrato frontend–backend y los tipos del frontend mediante un cambio coordinado. Hasta definir esa representación, el campo público único podrá permanecer `null`; no se ocultará que falta el acuerdo.

Este documento no modifica por sí solo los tipos existentes ni aprueba nuevos campos públicos.

### Propuestas del frontend pendientes de decisión

Todas las siguientes se clasifican como **`PROPOSAL_PENDING_TEAM_DECISION`**:

- Exponer confianza por objetivo: categoría, prioridad y área, en lugar de inventar una agregación numérica.
- Mostrar la prioridad impuesta por regla como decisión determinista, con `decisionSource` y `trigger`. `decisionSource` sería un nombre público propuesto; el clasificador utiliza actualmente `decision_source` y `trigger` internos. No se aprueba su traducción ni su obligatoriedad aquí.
- Representar el estado de predicción mediante `pending`, `available` y `unavailable`, además del formato de error.

Estas propuestas no se incorporan a ejemplos definitivos de API, no crean DTO ni estados aprobados y no modifican el contrato frontend–backend.

## Retirada de la regla de urgencia

La prioridad procede del modelo. Se eliminaron las funciones que imponían
`critical`; el detector léxico solo permanece para la auditoría del dataset.
`--enable-business-rules` y la activación programática producen error.
`--disable-business-rules` sigue disponible por compatibilidad.

La inferencia rechaza artefactos con prioridades fuera de `low`, `medium`,
`high`. Los artefactos antiguos que habilitan reglas también se rechazan por
defecto; pueden usarse con desactivación explícita únicamente si su catálogo
es compatible. `businessRulesEnabled` siempre es `false`. Se conservan las diez
claves internas por objetivo: `decision` y `decision_source` valen `model`,
`rule` y `trigger` son `null`, y las probabilidades siguen siendo del modelo.

Las referencias a reglas en revisiones y métricas históricas no describen la
implementación vigente. No se aprueban nuevas reglas ni campos públicos.

## Artefacto, dependencias y entrega reproducible

El PR genera localmente:

| Archivo | Uso |
| --- | --- |
| `ml/artifacts/ticket_classifier_es/ticket_classifier.joblib` | Pipelines y metadatos del clasificador |
| `ml/artifacts/ticket_classifier_es/metrics.json` | Resultados y configuración del experimento |
| `ml/artifacts/ticket_classifier_es/sample_prediction.json` | Ejemplo del entrenamiento, no equivalente exacto al formato de inferencia |
| `ml/artifacts/ticket_classifier_es/prepared_tickets.csv` | Dataset preparado; no necesario para servir inferencia |

El artefacto contiene `model_name`, `model_version`, `targets`, `models`, `config`, `runtime` y `dataset`. La procedencia de un derivado incluye su propio hash, el del original y las correcciones ya aplicadas. Las clases reales deberán verificarse en cada pipeline, no solo mediante ejemplos del README. La validación de anotaciones no certifica calidad, licencia, calibración ni aprobación del modelo.

América deberá entregar, además del código:

- artefacto autorizado, ubicación accesible y checksum;
- versión exacta de Python y dependencias utilizadas;
- catálogo de clases de los tres objetivos;
- identificación, procedencia y licencia del dataset;
- métricas reales de la misma ejecución que produjo el artefacto;
- preprocesamiento compartido;
- instrucciones reproducibles de entrenamiento e inferencia;
- muestra sintética o mecanismo autorizado para verificar el pipeline sin publicar datos sensibles;
- limitaciones conocidas y pruebas automatizadas.

ML usa Python 3.12 como referencia. `requirements.txt` fija versiones exactas de pandas, scikit-learn, Joblib, NumPy, SciPy y threadpoolctl; artefactos y métricas registran el entorno efectivo. No es un bloqueo universal de dependencias transitivas ni una verificación automática de compatibilidad al cargar Joblib. Esa comprobación sigue siendo responsabilidad de la integración.

El dataset completo y los artefactos generados están excluidos de Git; la muestra sintética indicada en las referencias sí está versionada. No se usarán `git add -f` ni notebooks como sustituto del mecanismo de distribución. Solo se cargarán artefactos de procedencia autorizada; no se aceptarán archivos `.joblib` cargados por usuarios finales.

El entrenamiento deberá ejecutarse fuera de las peticiones HTTP. El backend tampoco deberá descargar o entrenar silenciosamente un modelo cuando no encuentre el artefacto.

## Datos y métricas del experimento

La descripción histórica del PR declara 2.239 filas originales y 2.237 después de eliminar duplicados. La versión anterior del contrato del clasificador indicaba además 13.070 filas de entrenamiento y 3.268 de prueba, cifras incompatibles con ese total; ese archivo ya no está en el árbol del clasificador observado. Se conserva aquí la discrepancia como antecedente pendiente de aclaración, no como un contrato vigente del PR #13.

No se adoptan esas cantidades contradictorias. Los conteos definitivos deberán proceder de `metrics.json`, incluidos `rows_after_filter`, `train_rows` y `test_rows` por objetivo. La separación individual por objetivo debe documentarse; no se asumirá un único conjunto de evaluación común.

Métricas históricas reportadas en el PR y conservadas como antecedente, no reproducidas en esta revisión. El README observado mantiene los mismos valores de tipo, prioridad del modelo y área pese al cambio de separación; no se verificó que procedan de una ejecución del commit actual. La fila con reglas corresponde al reporte anterior, cuya regla usaba high. No se atribuyen estos números a la regla critical ni al nuevo esquema de evaluación:

| Salida evaluada | Macro F1 | Weighted F1 |
| --- | ---: | ---: |
| Tipo de ticket | 0,7131 | 0,7120 |
| Prioridad: solo modelo | 0,6658 | 0,6859 |
| Prioridad: con reglas | 0,6602 | 0,6793 |
| Cola/área | 0,7108 | 0,6479 |

Estas métricas no demuestran que exista una clasificación temática de categoría ni constituyen umbrales de aceptación aprobados. En el reporte histórico la regla no mejoraba el F1 de prioridad; no se extrapola esa comparación al código actual. Se requieren métricas y particiones de la misma ejecución que produjo cada artefacto.

**`RESOLVED_IN_OBSERVED_IMPLEMENTATION` para el caso cubierto:** la separación prioriza grupos por texto preparado mediante `GroupShuffleSplit`; la prueba versionada incluye un texto repetido con etiquetas distintas y comprueba que no aparezca en ambos subconjuntos. Esto corrige el camino principal que antes podía repartir textos equivalentes entre entrenamiento y evaluación. La evidencia de esta revisión es estática: código y prueba existentes, sin ejecución independiente.

La implementación vigente eliminó la alternativa `train_test_split` y comparte preprocesamiento. Los conteos y métricas actuales se documentan en `ml/README.md`; la tabla anterior se conserva únicamente como antecedente histórico del primer experimento. No debe utilizarse para evaluar las variantes actuales ni sustituir los reportes ligados al dataset y configuración efectivos.

### Problemas técnicos que permanecen pendientes

| Tema | Evidencia y límite actual |
| --- | --- |
| Preprocesamiento y ranking | Compartidos y uniformes en ML; pendientes de verificar en el adaptador FastAPI cuando exista. |
| Carga del artefacto | `predict` ejecuta `joblib.load` en cada llamada. La carga única por proceso sigue propuesta. |
| Dependencias | Seis versiones fijadas y entorno registrado; falta la verificación operacional de compatibilidad del artefacto. |
| Métricas | El experimento actual y sus límites figuran en ML; la validación independiente y los umbrales de aceptación siguen pendientes. |
| Separación | Por grupos sin fallback por filas; revisar conteos, catálogos y ausencia de textos compartidos en cada entrega. |

## Persistencia y validación humana

El backend será el único responsable de escribir las predicciones en PostgreSQL. ML no modificará tickets ni accederá directamente a las tablas del dominio.

Se conservarán la asociación con el ticket, fecha UTC, nombre y versión del artefacto, resultados originales, confianzas por objetivo y configuración de reglas. La representación física de los detalles adicionales deberá acordarse antes de implementar la migración.

La operación no cambiará automáticamente `category`, `priority`, `area`, asignación, estado o resolución del ticket. La aceptación de una sugerencia requerirá una acción autorizada y trazable según el contrato funcional correspondiente.

Los reintentos no deberán sobrescribir silenciosamente el historial; la política de nuevas predicciones e idempotencia queda pendiente.

## Validaciones del adaptador

El backend deberá verificar:

- configuración y procedencia del artefacto;
- versión compatible y catálogos disponibles;
- título y descripción válidos antes de inferir;
- respuesta con los tres objetivos esperados;
- etiquetas pertenecientes al catálogo de cada objetivo;
- números finitos en el rango acordado;
- coherencia de etiqueta, confianza y ranking según el origen de decisión: ante regla, validar `confidence: null`, `confidence_source: "not_applicable"` y conservar `model_label`, `model_confidence` y ranking estadístico, sin exigir que el primer puesto coincida con la etiqueta impuesta;
- reglas deshabilitadas mientras no estén aprobadas;
- ausencia de metadatos sensibles en las respuestas públicas;
- mapeos al dominio aprobados antes de escribir campos públicos.

Los textos y resultados no deberán registrarse indiscriminadamente en logs.

## Errores y degradación controlada

El script actual no entrega un formato uniforme de errores; puede propagar excepciones. La siguiente interfaz deberá implementarse en el adaptador del backend:

| Código interno propuesto | Situación | Tratamiento |
| --- | --- | --- |
| `ML_INVALID_INPUT` | Texto inválido | Rechazar inferencia y conservar coherencia con la validación del ticket |
| `ML_MODEL_UNAVAILABLE` | Artefacto ausente o no cargable | Mantener disponible la gestión de tickets y registrar fallo |
| `ML_VERSION_UNSUPPORTED` | Versiones o esquema incompatibles | No usar el artefacto; corregir configuración |
| `ML_INFERENCE_FAILED` | Excepción durante inferencia | No inventar una predicción |
| `ML_INVALID_OUTPUT` | Objetivos, etiquetas o probabilidades inválidos | No persistir como resultado válido |
| `ML_RULES_NOT_APPROVED` | Reglas activadas sin acuerdo | Rechazar esa configuración de inferencia |
| `ML_TIMEOUT` | Tiempo máximo excedido | Aplicar el mecanismo de ejecución y cancelación acordado |

Los nombres del PR `ML_MODEL_NOT_FOUND`, `ML_PREDICTION_FAILED` y `ML_MODEL_VERSION_MISMATCH` deberán traducirse a los códigos acordados si se utilizan en el componente ML.

Para errores que se expongan por la API se seguirá el formato del [contrato frontend–backend](frontend-backend.md):

```json
{
  "error": {
    "code": "ML_MODEL_UNAVAILABLE",
    "message": "La clasificación automática no está disponible temporalmente.",
    "details": null,
    "requestId": "4762428a-c356-44d7-8f43-e48fc16e393a"
  }
}
```

Este ejemplo no define el código HTTP ni convierte automáticamente una creación exitosa de ticket en un error HTTP. La exposición de ausencia de predicción, procesamiento pendiente y fallo deberá acordarse con el frontend.

No se aplicarán reintentos indiscriminados. Tiempos máximos, ejecución y cancelación, idempotencia y política de recuperación siguen pendientes. Un timeout no está implementado por el simple hecho de documentar su código.

## Pruebas mínimas antes de integrar

- Validación de columnas requeridas y textos vacíos en el dataset: existen código y prueba versionados del filtrado, sin ejecución independiente en esta revisión.
- Preprocesamiento equivalente entre entrenamiento e inferencia.
- Mismo texto preparado no compartido entre entrenamiento y evaluación: existe prueba agrupada; verificar las particiones de cada ejecución sin introducir fallback por filas.
- Carga del artefacto autorizado y rechazo de versiones incompatibles.
- Inferencia válida con tres objetivos y catálogos verificables.
- Reglas explícitamente deshabilitadas en el adaptador inicial.
- Salidas sin objetivos, clases desconocidas, `NaN`, infinito o confianza fuera de rango.
- Correspondencia de `title`/`description` con `subject`/`body`.
- Conservación de `ticketId`, `requestId`, fecha y versión por el backend.
- Ausencia de escritura automática sobre decisiones humanas.
- Ticket conservado cuando ML falla.
- Pruebas con y sin reglas, incluida negación, antes de proponer su activación.

La comprobación con `py_compile` valida sintaxis, no reemplaza estas pruebas ni reproduce las métricas del modelo.

## Responsabilidades

| Integrante/componente | Responsabilidades |
| --- | --- |
| América / ML | Dataset, licencia, preprocesamiento, pipelines, artefacto, catálogos, métricas, dependencias, pruebas y ejemplos reproducibles |
| Felipe / backend | Adaptador, validación, asociación con tickets, configuración, errores, persistencia, trazabilidad y pruebas de integración |
| Valentina / frontend | Presentación de predicciones y sus limitaciones; cambios coordinados de tipos y estados de carga/error |
| Equipo | Semántica tipo/categoría, mapeo cola/área, criterios de prioridad, futuras reglas de negocio, confianza pública y aprobación del contrato |

## Decisiones pendientes y bloqueos

1. Resolver si tipo equivale a categoría o requiere ampliar el dominio.
2. Aprobar el catálogo y mapeo de colas a áreas.
3. Verificar el catálogo vigente `low`, `medium`, `high` y la aplicación explícita de su migración.
4. Verificar la inferencia sin la regla `urgent_priority`, retirada en esta rama.
5. Acordar confianza por objetivo y su representación en dominio, base y frontend.
6. Verificar en el futuro adaptador el preprocesamiento compartido y `top3`, ya implementados en ML.
7. Completar procedencia/licencia, artefacto y entorno exacto; la muestra sintética ya está versionada y permite verificar el pipeline, pero no reproduce las métricas del dataset completo.
8. Corregir conteos documentales y confirmar particiones efectivas y métricas actuales; el filtrado y la ruta agrupada están corregidos en la implementación observada, sin certificación de todos los caminos.
9. Definir ejecución, límites, timeout, recuperación e idempotencia.
10. Aprobar el adaptador interno y un único PR responsable del contrato.

Estos pendientes bloquean la integración completa; no impiden inicializar FastAPI ni desarrollar la persistencia relacional independiente del modelo.

## Criterios de aceptación

La revisión de esta actualización documental puede realizarse como provisional sin resolver las diez decisiones del equipo. Los criterios siguientes describen el cierre del contrato y de su integración; no convierten las propuestas en acuerdos aprobados.

### Aprobación documental

- Felipe y América acuerdan entrada y salida nativas.
- El equipo resuelve los mapeos al dominio sin equiparar conceptos diferentes silenciosamente.
- La política de reglas y probabilidades queda explícita.
- Se acuerdan metadatos, errores y responsabilidades.
- Se identifica un único documento autoritativo y se aprueba mediante PR.

### Aprobación de la integración funcional

- El artefacto se carga en un entorno reproducible fuera del notebook.
- Se dispone de catálogos y métricas verificables de la misma versión.
- El backend cumple los mapeos y validaciones aprobados.
- Se preservan predicciones originales y decisiones humanas.
- Se verifica la degradación controlada ante fallo del modelo.
- Pasan las pruebas mínimas y se documentan resultados y limitaciones.

Aprobar el documento no significa que la integración esté implementada o que sus pruebas hayan sido ejecutadas.
