# Contrato inicial entre backend y modelo de Machine Learning

## Estado

**Provisional**

## Proposito

Este documento define el contrato inicial entre el backend FastAPI y el componente de Machine Learning de SynapDesk.

El objetivo del modelo es analizar el asunto y la descripcion de un ticket para entregar:

- clasificacion sugerida;
- prioridad estimada;
- area responsable sugerida;
- nivel de confianza por cada prediccion.

Las predicciones no reemplazan la decision humana. Deben presentarse como apoyo para el agente de soporte y registrarse separadas de los valores validados del ticket.

## Contexto del proyecto

SynapDesk busca apoyar la gestion de tickets de soporte TI mediante Machine Learning, recuperacion semantica, RAG y modelos de lenguaje.

Dentro del flujo general, el modelo de Machine Learning actua en la primera etapa:

```text
Ticket -> Machine Learning -> Recuperacion semantica -> RAG -> LLM -> Recomendacion -> Validacion humana
```

Este contrato cubre unicamente el componente de Machine Learning para clasificacion, prioridad y area responsable.

## Dataset utilizado

El experimento actual utiliza un CSV de tickets en español con las siguientes columnas:

```text
indice_original, subject, body, answer, type, queue, priority,
business_type, tag_1, tag_2, tag_3, language, origen
```

Para el entrenamiento se filtra la columna `language` usando solo registros con valor `es`.

Resumen del dataset utilizado:

| Elemento | Valor |
| --- | ---: |
| Filas totales del CSV | 2.239 |
| Filas usadas en espanol | 2.237 |
| Porcentaje de prueba | 20% |
| Filas de entrenamiento | 13.070 |
| Filas de prueba | 3.268 |
| Semilla aleatoria | 42 |

No se utiliza la columna `answer` como entrada del modelo, porque al momento de crear un ticket nuevo la respuesta todavia no existe. Usarla durante el entrenamiento produciria fuga de informacion y metricas artificialmente optimistas.

## Variables de entrada del modelo

El modelo recibe informacion disponible al crear un ticket:

| Campo | Tipo | Obligatorio | Descripcion |
| --- | --- | --- | --- |
| `subject` | `string` | Si | Asunto o titulo breve del ticket. |
| `body` | `string` | Si | Descripcion entregada por el usuario. |

El texto interno usado para inferencia se construye concatenando ambos campos:

```text
Asunto: <subject>
Descripcion: <body>
```

## Variables objetivo

| Columna del CSV | Salida del sistema | Descripcion |
| --- | --- | --- |
| `type` | `clasificacion_sugerida` | Tipo sugerido del ticket, por ejemplo `incident`, `request`, `problem` o `change`. |
| `priority` | `prioridad_estimada` | Prioridad estimada del ticket, por ejemplo `low`, `medium` o `high`. |
| `queue` | `area_responsable` | Area o cola responsable sugerida, por ejemplo `technical_support` o `it_support`. |

## Preparacion de datos

El pipeline inicial realiza estas acciones:

1. Carga el CSV de tickets en español.
2. Valida que existan las columnas requeridas.
3. Normaliza el valor de `language`.
4. Filtra registros con `language == "es"`.
5. Limpia saltos de linea y espacios repetidos en `subject` y `body`.
6. Construye el campo textual de entrenamiento.
7. Normaliza etiquetas a minusculas y formato tecnico con guiones bajos.
8. Elimina registros sin texto o sin etiquetas.
9. Elimina duplicados exactos por texto y etiquetas.
10. Descarta clases con menos de `min_target_count`.
11. Divide entrenamiento y prueba usando `test_size = 0.2`.

El script versionado para este proceso es:

```text
ml/train_ticket_classifier.py
```

## Modelo seleccionado

La primera version usa:

```text
TF-IDF + SGDClassifier(loss="log_loss")
```

Configuracion principal:

| Parametro | Valor |
| --- | --- |
| Vectorizador | `TfidfVectorizer` |
| N-gramas | 1 a 2 |
| Maximo de caracteristicas | 120.000 |
| Clasificador | `SGDClassifier` |
| Funcion de perdida | `log_loss` |
| Balanceo | `class_weight="balanced"` |
| Semilla | 42 |

Esta seleccion es adecuada como modelo base para el MVP porque:

- entrena rapido con miles de tickets;
- es simple de explicar y defender en el informe del proyecto;
- funciona bien en clasificacion de texto corto y mediano;
- entrega probabilidades para mostrar confianza al agente;
- no requiere GPU;
- se puede cargar facilmente desde FastAPI mediante un artefacto `.joblib`;
- permite comparar metricas antes de justificar modelos mas complejos.

## Resultados iniciales en español

Metricas obtenidas sobre el conjunto de prueba:

| Salida | Macro F1 | Weighted F1 | Interpretacion |
| --- | ---: | ---: | --- |
| `clasificacion_sugerida` | 0,7131 | 0,7120 | Baseline en español; requiere más datos o ajuste. |
| `prioridad_estimada` | 0,6658 | 0,6859 | Baseline del modelo; la regla de urgencia se evalúa aparte. |
| `area_responsable` | 0,7108 | 0,6479 | Útil como sugerencia, con revisión humana. |

Conclusion tecnica:

El modelo en español es un baseline funcional, pero todavía necesita más datos y revisión humana. La regla de urgencia no sustituye al modelo: se aplica de manera explícita y queda registrada en la respuesta.

## Criterio de uso recomendado

Para el MVP se recomienda:

- mostrar siempre la confianza asociada a cada prediccion;
- mostrar las tres clases mas probables cuando sea posible;
- permitir que el agente acepte, modifique o rechace la sugerencia;
- registrar la prediccion original, la decision humana y la version del modelo;
- evitar automatizar asignaciones criticas si la confianza es baja;
- volver a entrenar cuando aumente el dataset en español y se revisen las etiquetas conflictivas.

Regla determinista actual:

Las señales fuertes de urgencia (`urgente`, `urgencia`, `emergencia`, `crítico`, `inmediatamente`, `alta prioridad`, `caída total`, entre otras) producen `prioridad_estimada.label = "high"`. La respuesta incluye `decision = "business_rule"` o `"model_and_business_rule"`, además de `rule` y `trigger`.

Regla inicial sugerida:

| Confianza | Uso recomendado |
| ---: | --- |
| `>= 0.75` | Sugerencia fuerte, visible como recomendacion principal. |
| `0.50 - 0.74` | Sugerencia media, requiere revision del agente. |
| `< 0.50` | Sugerencia debil, mostrar advertencia o pedir revision manual. |

Estos umbrales son provisionales y deberan ajustarse con datos reales del proyecto.

## Artefactos locales

El entrenamiento genera los siguientes archivos locales:

| Archivo | Proposito |
| --- | --- |
| `ml/artifacts/ticket_classifier_es/prepared_tickets.csv` | Dataset filtrado y preparado. |
| `ml/artifacts/ticket_classifier_es/ticket_classifier.joblib` | Artefacto del modelo entrenado. |
| `ml/artifacts/ticket_classifier_es/metrics.json` | Métricas del experimento y comparación con reglas. |
| `ml/artifacts/ticket_classifier_es/sample_prediction.json` | Ejemplo de salida del modelo. |

Estos artefactos no deben subirse directamente a Git si son grandes o reproducibles localmente. El repositorio ya excluye carpetas como `data/` y `artifacts/`.

## Ejecucion local

Instalacion de dependencias:

```bash
pip install -r ml/requirements.txt
```

Entrenamiento en español:

```bash
python ml/train_ticket_classifier.py \
  --input-csv ml/data/raw/tickets_esp.csv \
  --language es \
  --output-dir ml/artifacts/ticket_classifier_es
```

Prediccion local:

```bash
python ml/predict_ticket.py \
  --model ml/artifacts/ticket_classifier_es/ticket_classifier.joblib \
  --subject "No puedo acceder al correo corporativo" \
  --body "Outlook rechaza mi contrasena y necesito recuperar el acceso."
```

## Contrato de inferencia

### Entrada

El backend debera enviar al componente ML:

```json
{
  "subject": "No puedo acceder al correo corporativo",
  "body": "Outlook rechaza mi contrasena y necesito recuperar el acceso para enviar reportes urgentes."
}
```

Validaciones minimas:

| Campo | Regla |
| --- | --- |
| `subject` | Debe ser texto no vacio. |
| `body` | Debe ser texto no vacio. |
| `subject` + `body` | Deben contener informacion suficiente para clasificar. |

### Salida

Respuesta esperada:

```json
{
  "modelName": "synapdesk_tfidf_sgd_ticket_classifier",
  "modelVersion": "20260917171525",
  "predictions": {
    "clasificacion_sugerida": {
      "label": "incident",
      "confidence": 0.5773,
      "top3": [
        { "label": "incident", "confidence": 0.5773 },
        { "label": "problem", "confidence": 0.1795 },
        { "label": "change", "confidence": 0.1383 }
      ]
    },
    "prioridad_estimada": {
      "label": "low",
      "confidence": 0.4044,
      "top3": [
        { "label": "low", "confidence": 0.4044 },
        { "label": "medium", "confidence": 0.3550 },
        { "label": "high", "confidence": 0.2406 }
      ]
    },
    "area_responsable": {
      "label": "it_support",
      "confidence": 0.3425,
      "top3": [
        { "label": "it_support", "confidence": 0.3425 },
        { "label": "technical_support", "confidence": 0.1499 },
        { "label": "service_outages_and_maintenance", "confidence": 0.1317 }
      ]
    }
  }
}
```

Los valores de `confidence` deben interpretarse como apoyo operativo, no como certeza absoluta.

## Integracion sugerida con backend

Cuando se implemente FastAPI, se recomienda aislar el modelo en un servicio interno, por ejemplo:

```text
backend/app/ml/ticket_classifier.py
```

Responsabilidades sugeridas:

- cargar el artefacto `.joblib` una sola vez al iniciar el backend;
- exponer una funcion interna para predecir un ticket;
- validar entradas antes de inferir;
- mapear la respuesta al modelo de dominio `MLPrediction`;
- registrar `modelName`, `modelVersion` y fecha de prediccion;
- manejar errores sin exponer rutas internas ni trazas completas al frontend.

## Errores esperados

| Codigo interno | Causa | Manejo recomendado |
| --- | --- | --- |
| `ML_MODEL_NOT_FOUND` | No existe el artefacto entrenado. | Registrar error y devolver respuesta controlada. |
| `ML_INVALID_INPUT` | El ticket no contiene texto valido. | Responder con error de validacion. |
| `ML_PREDICTION_FAILED` | Fallo inesperado durante inferencia. | Registrar detalle interno y devolver error generico. |
| `ML_MODEL_VERSION_MISMATCH` | Version de modelo distinta a la esperada. | Bloquear despliegue o advertir en logs. |

Formato sugerido de error interno:

```json
{
  "error": {
    "code": "ML_INVALID_INPUT",
    "message": "El ticket no contiene texto suficiente para generar una prediccion.",
    "details": null
  }
}
```

## Limitaciones conocidas

- El modelo actual fue entrenado con tickets en español; el resultado puede degradarse si el usuario mezcla idiomas o usa vocabulario distinto al dataset.
- La prioridad y el area responsable tienen desempeno moderado, por lo que requieren validacion humana.
- El dataset publico puede no representar completamente el entorno real de una organizacion chilena.
- Las probabilidades del modelo deben calibrarse y evaluarse nuevamente si se cambia el algoritmo o el dataset.

## Mejoras futuras

Opciones para siguientes iteraciones:

- ampliar el dataset en español y revisar etiquetas conflictivas;
- comparar contra `LinearSVC` calibrado;
- probar `ComplementNB` como baseline adicional;
- evaluar BETO o RoBERTa en espanol si el baseline no alcanza los objetivos;
- medir matrices de confusion por salida;
- ajustar umbrales de confianza por objetivo;
- registrar retroalimentacion humana para reentrenamiento posterior;
- versionar experimentos mediante practicas ligeras de MLOps.

## Criterios de aceptacion

Este contrato se considerara aceptado cuando:

- el equipo confirme que `subject` y `body` son las entradas minimas del modelo;
- backend y ML acuerden la estructura de respuesta;
- se documenten las metricas del experimento inicial;
- se mantenga la separacion entre prediccion automatica y decision humana;
- los errores esperados esten definidos;
- no se suban datasets, artefactos pesados ni informacion sensible al repositorio;
- el documento sea revisado mediante pull request.
