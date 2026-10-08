# Contrato inicial entre backend y Machine Learning

## Estado y referencia

**Provisional — propuesta de integración pendiente de aprobación.**

Este documento actualiza el borrador de la Etapa 0.5.4 a partir de los scripts y la documentación del [PR #13](https://github.com/Krotzup/SynapDesk/pull/13), revisados en el commit `9cd0900b79ff69cf2d013a1b3bd53d6db42c70d8` el 5 de octubre de 2026.

Al realizar esta revisión, el PR figura cerrado y sin fusionar. La implementación descrita se considera una referencia técnica, no una funcionalidad incorporada a `main` ni una decisión aprobada por todo el equipo.

Las secciones diferencian el comportamiento observado en el PR de las condiciones propuestas para integrarlo. Este documento será la referencia única del contrato; debe evitarse mantener dos versiones diferentes en el PR de implementación ML y en el PR documental.

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

El entrenamiento usa una proporción de prueba de `0.2` y semilla predeterminada `42`. Realiza la separación por objetivo, con estratificación cuando puede aplicarla y una alternativa sin estratificación cuando esta falla.

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

La validación debe comprobar cada campo antes de agregar los prefijos. Un texto formado únicamente por `Asunto:` y `Descripcion:` no se considerará contenido válido. El script de entrenamiento actual puede conservar filas con ambos campos vacíos debido a esos prefijos; deberá corregirse y probarse.

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
        { "label": "high", "confidence": 0.25 },
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
- El baseline utiliza `predict_proba`; deberá devolver confianza por objetivo, finita y dentro de `[0, 1]`, asociada a la clase predicha.
- `top3` contendrá hasta tres clases diferentes del catálogo del objetivo, ordenadas por probabilidad descendente.
- La suma de `top3` puede ser menor que `1` si existen más de tres clases.
- Una futura versión sin probabilidades requerirá actualizar el contrato; no se inventarán valores de confianza.
- El ejemplo generado por entrenamiento usa `top_3`, mientras que la inferencia usa `top3`. Para integración se propone unificar en `top3`; esta corrección todavía debe realizarse en ML.
- `modelVersion` es actualmente una marca temporal UTC con formato `YYYYMMDDHHMMSS`, no una versión semántica. Debe conservarse como texto y asociarse al artefacto exacto.

Los valores de `confidence` son estimaciones del modelo, no garantías ni porcentajes de acierto individual demostrados. Los umbrales `0.75` y `0.50` propuestos en el PR no se adoptan como política aprobada.

## Correspondencia con el dominio y frontend

| Objetivo del dataset | Salida ML | Campo del dominio | Estado |
| --- | --- | --- | --- |
| `type` | `clasificacion_sugerida.label` | `predictedCategory` | No equivalente automáticamente; definición pendiente |
| `priority` | `prioridad_estimada.label` | `predictedPriority` | Mapeo directo para `low`, `medium`, `high`, sujeto a catálogo del artefacto |
| `queue` | `area_responsable.label` | `predictedArea` | Debe aprobarse correspondencia de colas con áreas del proyecto |
| Metadato del artefacto | `modelName` | `modelName` | Directo |
| Metadato del artefacto | `modelVersion` | `modelVersion` | Directo |
| Metadatos del backend | No los devuelve ML | `id`, `ticketId`, `createdAt` | Generados o asociados por el backend |
| Probabilidad por objetivo | `confidence` de cada salida | `confidence` único actual | Agregación o ampliación pendiente |

### Tipo no equivale necesariamente a categoría

El PR documenta tipos como `incident`, `request`, `problem` y `change`. No demuestra que el modelo clasifique categorías temáticas como red, hardware o software.

Antes de asignar `clasificacion_sugerida` a `predictedCategory`, el equipo deberá decidir si la categoría del MVP representará el tipo de ticket o si el dominio necesita un campo independiente. Mientras no exista ese acuerdo, no se copiará la etiqueta a `predictedCategory`; se conservará como resultado nativo interno y el campo público permanecerá `null` si se expone.

### Prioridad y cobertura de `critical`

El dominio y el frontend contemplan `low`, `medium`, `high` y `critical`. El PR documenta únicamente las tres primeras para el baseline.

Se mantendrá `critical` en el dominio. No se eliminará ni se inferirá convirtiendo automáticamente todo `high` en `critical`. El baseline no garantiza predicciones `critical`; su asignación humana y cualquier regla adicional deberán respetar los permisos y criterios funcionales que se acuerden.

### Confianza única frente a confianza por objetivo

El dominio actual contiene un único `confidence`. ML produce tres valores, que no deben promediarse ni sustituirse por el máximo sin una definición aprobada.

Se propone preservar internamente las confianzas por objetivo y actualizar el dominio, la persistencia, el contrato frontend–backend y los tipos del frontend mediante un cambio coordinado. Hasta definir esa representación, el campo público único podrá permanecer `null`; no se ocultará que falta el acuerdo.

Este documento no modifica por sí solo los tipos existentes ni aprueba nuevos campos públicos.

## Reglas de negocio: comportamiento observado y política propuesta

El PR incluye `urgent_priority`, que busca expresiones como `urgente`, `emergencia`, `crítico` y `caída total` y fuerza la etiqueta `high`.

Comportamiento observado:

- el comando de inferencia activa reglas por defecto;
- la función puede recibir `business_rules=False` para desactivarlas;
- `decision` puede ser `model`, `business_rule` o `model_and_business_rule`;
- se incluyen `rule` y `trigger` cuando se aplica la regla;
- la confianza original pasa a `model_confidence` y `confidence` cambia a `1.0`;
- se modifica el ranking de clases, agregando `high` con `1.0`;
- no se conserva explícitamente la etiqueta original cuando es sustituida.

**La regla no se adopta como política funcional aprobada.** Para la primera integración se propone invocar explícitamente `business_rules=False` y utilizar el resultado estadístico sin reglas. Esta política deberá ser confirmada por el equipo y probada; no implica que el PR ya tenga ese comportamiento por defecto.

Antes de habilitar reglas se deberá:

1. Acordar el significado de urgencia y su relación con `high` y `critical`.
2. Probar negaciones y falsos positivos; la búsqueda de una palabra no demuestra por sí sola urgencia.
3. Conservar etiqueta, confianza y ranking originales del modelo.
4. Separar la sugerencia de una regla de la predicción estadística.
5. Versionar y registrar la regla, su activación y su motivo, sin divulgar texto sensible.
6. No representar una decisión determinista como una probabilidad estadística de `1.0`.
7. Mantener métricas independientes para modelo y reglas.

Si se recibe una salida con reglas habilitadas antes de este acuerdo, el adaptador la rechazará como configuración no soportada en lugar de persistirla como una predicción pura.

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

Los datasets y artefactos generados están excluidos de Git. No se usarán `git add -f` ni notebooks como sustituto del mecanismo de distribución. Solo se cargarán artefactos de procedencia autorizada; no se aceptarán archivos `.joblib` cargados por usuarios finales.

El entrenamiento deberá ejecutarse fuera de las peticiones HTTP. El backend tampoco deberá descargar o entrenar silenciosamente un modelo cuando no encuentre el artefacto.

## Datos y métricas del experimento

El PR declara 2.239 filas originales y 2.237 después de eliminar duplicados. Su contrato también indica 13.070 filas de entrenamiento y 3.268 de prueba, cifras incompatibles con ese total.

No se adoptan esas cantidades contradictorias. Los conteos definitivos deberán proceder de `metrics.json`, incluidos `rows_after_filter`, `train_rows` y `test_rows` por objetivo. La separación individual por objetivo debe documentarse; no se asumirá un único conjunto de evaluación común.

Métricas reportadas en el PR, no reproducidas en esta revisión por ausencia del CSV y artefacto:

| Salida evaluada | Macro F1 | Weighted F1 |
| --- | ---: | ---: |
| Tipo de ticket | 0,7131 | 0,7120 |
| Prioridad: solo modelo | 0,6658 | 0,6859 |
| Prioridad: con reglas | 0,6602 | 0,6793 |
| Cola/área | 0,7108 | 0,6479 |

Estas métricas no demuestran que exista una clasificación temática de categoría ni constituyen umbrales de aceptación aprobados. La regla reportada no mejora el F1 de prioridad frente a las etiquetas del dataset.

El entrenamiento elimina duplicados por texto y etiquetas; un mismo texto con etiquetas diferentes puede permanecer y aparecer en ambos subconjuntos. Antes de aceptar las métricas deberá verificarse la separación por grupos de texto normalizado y revisarse las etiquetas contradictorias.

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
- coherencia de etiqueta, confianza y ranking;
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

Para errores que se expongan por la API se seguirá el formato frontend–backend:

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

- Validación de columnas requeridas y textos vacíos en el dataset.
- Preprocesamiento equivalente entre entrenamiento e inferencia.
- Mismo texto normalizado no compartido entre entrenamiento y evaluación.
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
4. Aprobar o descartar `urgent_priority` y corregir su representación de probabilidades antes de activarla.
5. Acordar confianza por objetivo y su representación en dominio, base y frontend.
6. Compartir preprocesamiento y unificar `top3`.
7. Entregar dataset o muestra reproducible, licencia, artefacto y entorno exacto.
8. Corregir conteos y confirmar particiones, ausencia de fuga y métricas reales.
9. Definir ejecución, límites, timeout, recuperación e idempotencia.
10. Aprobar el adaptador interno y un único PR responsable del contrato.

Estos pendientes bloquean la integración completa; no impiden inicializar FastAPI ni desarrollar la persistencia relacional independiente del modelo.

## Criterios de aceptación

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
