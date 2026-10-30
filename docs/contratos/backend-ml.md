# Contrato inicial entre backend y Machine Learning

## Estado y referencia

**Provisional — propuesta de integración pendiente de aprobación.**

Este documento actualiza el borrador de la Etapa 0.5.4 a partir de los scripts, documentación, muestra sintética y pruebas versionadas del [PR #13](https://github.com/Krotzup/SynapDesk/pull/13), contrastados en el commit `5c9942457569555554b08174ee6a960794b4c354` el 29 de octubre de 2026. Sustituye la referencia al estado anterior `9cd0900`.

Al realizar esta revisión, el PR #13 y el [PR documental #14](https://github.com/Krotzup/SynapDesk/pull/14) figuran abiertos. La implementación descrita se considera una referencia técnica, no una funcionalidad incorporada a `main` ni una decisión aprobada por todo el equipo. No se ejecutaron pruebas, inferencias ni entrenamientos durante este contraste.

Las secciones diferencian el comportamiento observado en el PR de las condiciones propuestas para integrarlo. Este documento será la referencia única del contrato; debe evitarse mantener dos versiones diferentes en el PR de implementación ML y en el PR documental.

| Clasificación | Significado en esta revisión |
| --- | --- |
| `IMPLEMENTATION_OBSERVED` | Comportamiento contrastado por lectura de código versionado; no implica ejecución independiente. |
| `CONTRACT_APPROVED` | Acuerdo funcional aprobado explícitamente por el equipo; no se asigna este estado a propuestas por aparecer en el código. |
| `PENDING_DECISION` | Decisión de integración todavía pendiente; el contrato continúa provisional. |
| `PROPOSAL_PENDING_TEAM_DECISION` | Propuesta del frontend o del equipo que no constituye un campo público obligatorio. |

### Evidencia técnica utilizada

Las siguientes referencias están fijadas al commit observado y se consultaron en modo lectura, sin cambiar a la rama ML:

- [Inferencia: campos, activación de reglas y carga del artefacto](https://github.com/Krotzup/SynapDesk/blob/5c9942457569555554b08174ee6a960794b4c354/ml/predict_ticket.py).
- [Reglas: prioridad y conservación del resultado original](https://github.com/Krotzup/SynapDesk/blob/5c9942457569555554b08174ee6a960794b4c354/ml/ticket_rules.py).
- [Entrenamiento: filtrado, separación y formato de muestra](https://github.com/Krotzup/SynapDesk/blob/5c9942457569555554b08174ee6a960794b4c354/ml/train_ticket_classifier.py).
- [Pruebas de reglas](https://github.com/Krotzup/SynapDesk/blob/5c9942457569555554b08174ee6a960794b4c354/tests/ml/test_ticket_rules.py) y [pruebas de preparación y separación](https://github.com/Krotzup/SynapDesk/blob/5c9942457569555554b08174ee6a960794b4c354/tests/ml/test_train_ticket_classifier.py), inspeccionadas sin ejecutarlas.
- [README del clasificador](https://github.com/Krotzup/SynapDesk/blob/5c9942457569555554b08174ee6a960794b4c354/ml/README.md) y [CSV sintético](https://github.com/Krotzup/SynapDesk/blob/5c9942457569555554b08174ee6a960794b4c354/ml/samples/tickets_esp_sintetico.csv).

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

El entrenamiento usa una proporción de prueba de `0.2` y semilla predeterminada `42`. Realiza la separación por objetivo y prioriza `GroupShuffleSplit` con grupos definidos por el texto preparado. Si esa ruta no puede utilizarse, conserva una alternativa con `train_test_split`, estratificada cuando es posible y sin estratificación si esta falla. La inspección no convierte esa alternativa en una garantía de separación por grupos.

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

El entrenamiento normaliza espacios y secuencias literales `\n`; la inferencia solo aplica `strip()` a los campos. Antes de integrar se deberá compartir el mismo preprocesamiento entre entrenamiento e inferencia.

La validación debe comprobar el contenido antes de agregar los prefijos. Un texto formado únicamente por `Asunto:` y `Descripcion:` no se considerará contenido válido. **`RESOLVED_IN_OBSERVED_IMPLEMENTATION`:** el entrenamiento normaliza `subject` y `body` y descarta las filas donde ambos están vacíos antes de construir el texto. La prueba versionada de preparación incluye una fila con ambos campos vacíos y comprueba el filtrado; se verificaron el código y la existencia de esa prueba, no su ejecución en esta tarea. El filtrado conserva filas con al menos uno de los dos campos no vacío; esto no sustituye la validación propuesta del backend, que exige ambos campos.

El backend conservará el título y descripción originales. No se traducirá ni se alterará su significado. Los límites de longitud quedan pendientes de acuerdo. Los identificadores, contraseñas, credenciales y adjuntos no serán características del clasificador.

## Salida nativa del componente ML

El comando de inferencia produce una estructura como la siguiente. Los valores numéricos son ilustrativos, no una ejecución verificada:

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
        { "label": "critical", "confidence": 0.10 }
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
- El ejemplo generado por entrenamiento usa `top_3`, mientras que la inferencia usa `top3`. Para integración se propone unificar en `top3`; esta corrección todavía debe realizarse en ML.
- `modelVersion` es actualmente una marca temporal UTC con formato `YYYYMMDDHHMMSS`, no una versión semántica. Debe conservarse como texto y asociarse al artefacto exacto.

Los valores numéricos de `confidence` son estimaciones del modelo, no garantías ni porcentajes de acierto individual demostrados. El valor `null` en una decisión por regla no equivale a cero ni a certeza total. Los umbrales `0.75` y `0.50` propuestos en el PR no se adoptan como política aprobada.

La salida nativa mezcla camelCase y snake_case. Sin reglas, la inferencia añade `decision: "model"`, pero no añade sistemáticamente `model_label`, `model_confidence`, `confidence_source` ni `decision_source`. Con reglas habilitadas para prioridad, la función de reglas sí añade esos metadatos, incluso cuando no encuentra un disparador. Su presencia no se generaliza a los otros objetivos. No se renombran campos internos para hacerlos pasar por la API pública.

## Correspondencia con el dominio y frontend

| Objetivo del dataset | Salida ML | Campo del dominio | Estado |
| --- | --- | --- | --- |
| `type` | `clasificacion_sugerida.label` | `predictedCategory` | No equivalente automáticamente; definición pendiente |
| `priority` | `prioridad_estimada.label` | `predictedPriority` | Coincidencia técnica de valores `low`, `medium`, `high`, `critical`, sujeta al catálogo del artefacto y a la política funcional pendiente |
| `queue` | `area_responsable.label` | `predictedArea` | Debe aprobarse correspondencia de colas con áreas del proyecto |
| Metadato del artefacto | `modelName` | `modelName` | Directo |
| Metadato del artefacto | `modelVersion` | `modelVersion` | Directo |
| Metadatos del backend | No los devuelve ML | `id`, `ticketId`, `createdAt` | Generados o asociados por el backend |
| Probabilidad por objetivo | `confidence` numérico; `model_confidence` si interviene regla | `confidence` único actual | Representación pendiente; `confidence: null` por regla no se agrega como probabilidad |

### Tipo no equivale necesariamente a categoría

El PR documenta tipos como `incident`, `request`, `problem` y `change`. No demuestra que el modelo clasifique categorías temáticas como red, hardware o software.

Antes de asignar `clasificacion_sugerida` a `predictedCategory`, el equipo deberá decidir si la categoría del MVP representará el tipo de ticket o si el dominio necesita un campo independiente. Mientras no exista ese acuerdo, no se copiará la etiqueta a `predictedCategory`; se conservará como resultado nativo interno y el campo público permanecerá `null` si se expone.

### Prioridad y cobertura de `critical`

El dominio, el frontend y el README del clasificador contemplan `low`, `medium`, `high` y `critical`. El CSV sintético versionado contiene las cuatro prioridades, incluida `critical` en las filas originales 9 y 10. El código normaliza las etiquetas del dataset y no restringe la prioridad a tres clases.

Se mantendrá `critical` en el dominio. No se eliminará ni se inferirá convirtiendo automáticamente todo `high` en `critical`. La revisión publicada de Valentina reporta que el modelo también predice `critical`; esa ejecución y el catálogo del artefacto no se reprodujeron aquí (`NOT_VERIFIED` para la inferencia independiente). La presencia de la clase en documentación y muestra sí está contrastada. Su cobertura en cada artefacto depende del dataset y de las clases conservadas al entrenar; la asignación humana y las reglas adicionales siguen sujetas a criterios funcionales del equipo.

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

## Reglas de negocio: comportamiento observado y política propuesta

**IMPLEMENTATION_OBSERVED:** la regla urgent_priority busca expresiones como urgente, emergencia, crítico y caída total. Cuando encuentra un disparador, fuerza la etiqueta critical; no representa una nueva decisión aprobada para toda la arquitectura de SynapDesk.

Comportamiento contrastado en el commit de referencia:

- El entrenamiento deja business_rules_enabled desactivado por defecto; --enable-business-rules lo activa explícitamente.
- En inferencia, --enable-business-rules fuerza su activación y --disable-business-rules fuerza su desactivación. Sin esas opciones, predict(..., business_rules=None) consulta config.business_rules_enabled del artefacto, con False como alternativa si falta el dato. Por ello no se debe garantizar la desactivación para un artefacto que ya fue entrenado con reglas habilitadas.
- Se puede pasar business_rules=False explícitamente para asegurar la desactivación.
- Con reglas habilitadas para prioridad se conserva siempre la etiqueta original en model_label y, si existe confianza original, en model_confidence.
- Si no hay disparador, conserva label y confidence y añade decision y decision_source con valor model, más confidence_source: model.
- Si hay disparador, fija label: critical, confidence: null y confidence_source: not_applicable; mantiene model_label, model_confidence y top3 sin alterar el ranking estadístico.
- decision es business_rule si la etiqueta original era distinta de critical, o model_and_business_rule si ya era critical. En ambos casos decision_source es business_rule y se incluyen rule y trigger.

Fragmento ilustrativo de prioridad cuando una regla cambia medium por critical; no es una ejecución verificada ni la respuesta completa de los tres objetivos. Los nombres son los internos reales del clasificador:

~~~json
{
  "prioridad_estimada": {
    "label": "critical",
    "confidence": null,
    "top3": [
      { "label": "medium", "confidence": 0.65 },
      { "label": "high", "confidence": 0.20 },
      { "label": "critical", "confidence": 0.10 }
    ],
    "model_label": "medium",
    "model_confidence": 0.65,
    "confidence_source": "not_applicable",
    "decision": "business_rule",
    "decision_source": "business_rule",
    "rule": "urgent_priority",
    "trigger": "urgente"
  }
}
~~~

**PENDING_DECISION — política propuesta:** la regla no se adopta como política funcional aprobada. Para la primera integración se propone invocar explícitamente business_rules=False y utilizar el resultado estadístico sin reglas. La desactivación observada por defecto es compatible con esa propuesta, pero no demuestra aprobación del equipo.

Antes de habilitar reglas se propone:

1. Acordar los criterios funcionales de urgencia y prioridad critical, sin transformar todo high en critical.
2. Probar negaciones y falsos positivos; una coincidencia textual no demuestra por sí sola urgencia.
3. Mantener la conservación de etiqueta, confianza y ranking originales ya observada.
4. Separar la sugerencia de una regla de la predicción estadística.
5. Versionar y registrar la regla, su activación y su motivo, sin divulgar texto sensible.
6. Mantener confidence: null en decisiones por regla; nunca interpretarlo como probabilidad de cero o como certeza de 1.0.
7. Mantener métricas independientes para modelo y reglas.

El rechazo de configuraciones con reglas activas antes del acuerdo del equipo sigue siendo una propuesta para el adaptador, no comportamiento implementado del clasificador ni decisión aprobada en esta revisión.

## Artefacto, dependencias y entrega reproducible

El PR genera localmente:

| Archivo | Uso |
| --- | --- |
| `ml/artifacts/ticket_classifier_es/ticket_classifier.joblib` | Pipelines y metadatos del clasificador |
| `ml/artifacts/ticket_classifier_es/metrics.json` | Resultados y configuración del experimento |
| `ml/artifacts/ticket_classifier_es/sample_prediction.json` | Ejemplo del entrenamiento, no equivalente exacto al formato de inferencia |
| `ml/artifacts/ticket_classifier_es/prepared_tickets.csv` | Dataset preparado; no necesario para servir inferencia |

El artefacto actual contiene `model_name`, `model_version`, `targets`, `models` y `config`. Las clases reales deberán verificarse en cada pipeline mediante el catálogo del clasificador, no solo mediante ejemplos del README.

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

El PR recomienda Python 3.12. `requirements.txt` declara `pandas>=2.2`, `scikit-learn>=1.5` y `joblib>=1.4`; estos mínimos no fijan un entorno reproducible. Antes de desplegar deberá registrarse el entorno exacto del artefacto y comprobar su compatibilidad al cargarlo.

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

El código conserva una ruta alternativa con `train_test_split` si no puede usar la agrupación. No se certifica ausencia universal de fuga para esa ruta, para otros datasets ni para métricas históricas. Sigue pendiente comprobar las particiones efectivas y las etiquetas contradictorias de cada ejecución. El filtrado de textos vacíos y esta corrección no resuelven el preprocesamiento desigual entre entrenamiento e inferencia.

### Problemas técnicos que permanecen pendientes

| Tema | Evidencia y límite actual |
| --- | --- |
| Preprocesamiento | Entrenamiento usa `normalize_text`; inferencia construye el texto aplicando solo `strip()`. No está compartido. |
| Ranking | La muestra de entrenamiento usa `top_3`; la inferencia usa `top3`. La regla preserva el ranking recibido, no unifica sus nombres. |
| Carga del artefacto | `predict` ejecuta `joblib.load` en cada llamada. La carga única por proceso sigue propuesta. |
| Dependencias | Se declaran versiones mínimas con `>=`; el entorno exacto del artefacto no queda fijado por esas líneas. |
| Métricas | No se reprodujeron entrenamientos, inferencias ni resultados en esta tarea; los reportes no certifican el commit observado. |
| Separación | La ruta agrupada y su prueba están presentes; falta verificar las particiones reales y el comportamiento de la alternativa sin grupos. |

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
- Mismo texto normalizado no compartido entre entrenamiento y evaluación: existe prueba de la ruta agrupada; verificar también particiones reales y ruta alternativa.
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
| Equipo | Semántica tipo/categoría, mapeo cola/área, prioridad crítica, reglas de negocio, confianza pública y aprobación del contrato |

## Decisiones pendientes y bloqueos

1. Resolver si tipo equivale a categoría o requiere ampliar el dominio.
2. Aprobar el catálogo y mapeo de colas a áreas.
3. Mantener cobertura explícita de `critical` y definir criterios funcionales de prioridad.
4. Aprobar o descartar `urgent_priority` y validar su representación diferenciada de confianza antes de activarla; el código observado ya usa `null` para la decisión por regla.
5. Acordar confianza por objetivo y su representación en dominio, base y frontend.
6. Compartir preprocesamiento y unificar `top3`.
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
