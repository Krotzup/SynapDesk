# Machine Learning

Componente de Machine Learning de SynapDesk para clasificar tickets de soporte,
estimar su prioridad y sugerir el area responsable. El modelo funciona como
asistencia para el agente; la decision final permanece bajo supervision humana.

## Stack

- Python
- Pandas
- Scikit-learn
- Joblib
- TF-IDF
- SGDClassifier con `log_loss`

## Requisitos

- Python 3.12 (misma versión menor que el CI)
- pip
- CSV de tickets en espanol ubicado localmente en `ml/data/raw/tickets_esp.csv`
  o el dataset sintetico versionado en `ml/samples/tickets_esp_sintetico.csv`
  para verificar el pipeline.

El dataset y los artefactos generados no se versionan en Git. Debe confirmarse
la licencia, procedencia y ausencia de informacion sensible antes de compartir
el CSV fuera del entorno local.

El lector exige CSV con comas, comillas válidas y UTF-8 (admite BOM). Rechaza
filas con campos desalineados sin omitirlas ni sustituir caracteres. Renombrar
un archivo o envolver una fila CSV en una celda no corrige su formato.

Las seis dependencias de `requirements.txt` tienen versiones exactas. Los
artefactos y métricas registran Python, esas dependencias, SHA-256 del dataset,
catálogos de clases y cantidad de textos compartidos entre las particiones.

## Auditoria local de etiquetas

La preparacion existente normaliza textos y etiquetas, descarta filas vacias y
duplicados exactos. Para revisar posibles inconsistencias de prioridad sin
alterar el CSV original ni las etiquetas usadas para entrenar:

```bash
python ml/audit_ticket_dataset.py \
  --input-csv ml/data/raw/tickets_esp.csv \
  --language es \
  --output-dir ml/artifacts/data_quality
```

Si el CSV esta fuera del repositorio, sustituye `--input-csv` por su ruta local.
El script genera `data_quality.json` con conteos y SHA-256, y
`priority_review_candidates.csv` con el numero de fila del registro en el CSV
(incluyendo la cabecera), la prioridad actual y la señal detectada. La lista no
incluye el texto del ticket. Ambos archivos quedan en `ml/artifacts/`, excluido
de Git.

La ejecución histórica anterior a esta revisión con el CSV completo encontró 2 duplicados exactos, ninguna fila
sin texto y ningun texto con prioridades contradictorias. Encontro tambien
132 candidatos: 113 etiquetados `medium` y 19 `low` pese a contener una señal
lexical de urgencia. Son casos para revisar, no errores confirmados. No se
cambio ninguna etiqueta ni se reentreno el modelo a partir de la lista. La
correccion de prioridades exige criterios funcionales aprobados y revision
humana de los tickets originales.

Para aplicar correcciones humanas sin modificar el CSV fuente, consulta
[Correcciones reproducibles de prioridad](CORRECCIONES_PRIORIDAD.md).

## Instalacion

Desde la raiz del repositorio, usando Git Bash:

```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -r ml/requirements.txt
```

Para comprobar que el entorno esta activo:

```bash
which python
python --version
```

## Dataset

El pipeline principal utiliza `ml/data/raw/tickets_esp.csv`. Ese archivo no se
versiona porque puede contener datos externos o sensibles. Para verificar el
pipeline sin exponer datos reales se incluye
`ml/samples/tickets_esp_sintetico.csv`.

- El CSV completo utilizado en la evaluacion local contiene 2.239 registros
  en espanol; 2.237 quedan despues del filtrado y la eliminacion de duplicados.
  Su SHA-256 es
  `ade38dba719f54bfd06d3fcd12a4c6ff031887eca5545a98c74fac97b10db11a`.
  El archivo permanece fuera del repositorio.
- La muestra sintetica versionada contiene 12 tickets con `language = es`.
- Entradas del modelo: `subject` y `body`.
- Objetivos: `type`, `priority` y `queue`.
- `answer` no se utiliza como entrada para evitar fuga de informacion.

Las etiquetas tecnicas se conservan para mantener el contrato del sistema:

- Tipo: `incident`, `request`, `problem`, `change`.
- Prioridad: `low`, `medium`, `high`, `critical`.
- Area: nombres tecnicos como `technical_support` o `it_support`.

## Entrenamiento

Desde la raiz del repositorio:

```bash
python ml/train_ticket_classifier.py \
  --input-csv ml/data/raw/tickets_esp.csv \
  --language es \
  --output-dir ml/artifacts/ticket_classifier_es
```

El entrenamiento limpia el texto, normaliza las etiquetas, elimina filas
invalidas y duplicados, separa entrenamiento y prueba y genera las metricas.
La separación agrupa por texto preparado. Si no puede construir una partición
válida, falla explícitamente; no recurre a separar filas que comparten texto.

Verificacion reproducible con dataset sintetico:

```bash
python ml/train_ticket_classifier.py \
  --input-csv ml/samples/tickets_esp_sintetico.csv \
  --language es \
  --min-target-count 1 \
  --max-features 2000 \
  --output-dir ml/artifacts/ticket_classifier_sample
```

## Prediccion

```bash
python ml/predict_ticket.py \
  --model ml/artifacts/ticket_classifier_es/ticket_classifier.joblib \
  --subject "URGENTE: no puedo entrar al correo" \
  --body "Necesito recuperar el acceso inmediatamente para trabajar." \
  --enable-business-rules
```

La respuesta entrega:

- `clasificacion_sugerida`;
- `prioridad_estimada`;
- `area_responsable`;
- confianza y tres clases probables cuando el modelo las entrega;
- version del modelo;
- decision y trazabilidad de las reglas aplicadas.

## Mapeo a MLPrediction

Hasta que el contrato Backend-ML quede cerrado en el PR documental, la
integracion debe tratar esta salida como un adaptador interno hacia
`MLPrediction`:

| Salida ML | Campo sugerido en dominio | Nota |
| --- | --- | --- |
| `predictions.clasificacion_sugerida.label` | `predictedCategory` | Mapeo pendiente: tipo no equivale automáticamente a categoría temática. |
| `predictions.prioridad_estimada.label` | `predictedPriority` | Puede venir del modelo o de una regla aprobada. |
| `predictions.area_responsable.label` | `predictedArea` | Correspondencia de cola con área pendiente de aprobación. |
| `predictions.*.confidence` | `confidence` o detalle por salida | Confianza estadistica solo cuando `confidence_source = model`. |
| `modelName` | `modelName` | Nombre del artefacto cargado. |
| `modelVersion` | `modelVersion` | Version exacta del entrenamiento. |
| `predictions.*.top3` | metadata adicional | Ranking estadístico, también en la muestra generada durante entrenamiento. |
| `decision`, `decision_source`, `rule`, `trigger` | metadata adicional | Trazabilidad de reglas y procedencia. |
| `model_label`, `model_confidence` | metadata adicional | Resultado estadistico original cuando hubo regla. |

Si `decision_source = business_rule`, la prioridad final no debe interpretarse
como una prediccion estadistica con certeza total. En ese caso `confidence`
queda en `null` y la confianza del clasificador queda en `model_confidence`.

Cada objetivo devuelve siempre estas diez claves internas: `label`,
`confidence`, `top3`, `decision`, `decision_source`, `confidence_source`,
`model_label`, `model_confidence`, `rule`, `trigger`. Sin regla aplicada,
los resultados estadísticos conservan `decision_source: model`; `rule` y
`trigger` son `null`. Un clasificador sin probabilidades devuelve confianza y
procedencia de confianza `null`, con `top3: []`.

Se conservan los nombres internos existentes para evitar una migración
innecesaria. El futuro adaptador traducirá a camelCase según el acuerdo del
PR #14. No se agregan DTO ni se aprueba el mapeo de confianza pública en este PR.

## Reglas de negocio

Las reglas de negocio estan desactivadas por defecto hasta que el equipo
apruebe sus criterios funcionales. La regla `urgent_priority`, cuando se activa
explicitamente, fuerza `priority = critical` cuando el asunto o cuerpo
contiene señales fuertes de urgencia, por ejemplo:

- `urgente`;
- `urgencia`;
- `emergencia`;
- `crítico`/`crítica` con contexto, como `falla crítica` o `es crítico`;
- `inmediatamente`;
- `alta prioridad`;
- `caida total` o `caída total`;
- `interrupcion total` o `interrupción total`.

Negaciones explicitas cercanas a la señal, como `no es urgente`, `sin urgencia`
o `no es una emergencia`, así como `no es nada urgente`, `no urgente` y
`no creo que sea urgente`, no activan la regla. Una `revisión crítica` del
manual tampoco es un disparador. La deteccion es lexical y no
resuelve todos los matices del lenguaje; sus criterios requieren validacion
funcional antes de activar la regla por defecto.

La palabra `urgente` sola no es un criterio suficiente para corregir etiquetas
del dataset ni una política aprobada de prioridad. La regla sigue siendo un
experimento opcional; las correcciones humanas se basan en impacto y no la
habilitan. En inferencia sin opción explícita se hereda la configuración del
artefacto; usa `--disable-business-rules` para asegurar su desactivación.

Cuando se aplica la regla, la respuesta incluye `decision = business_rule`
(o `model_and_business_rule` si el modelo ya predijo `critical`),
`decision_source`, `rule`, `trigger`, `model_label`, `model_confidence` y
`confidence_source`. En decisiones por regla, `confidence` queda en `null`
porque la confianza estadistica corresponde al modelo y se conserva en
`model_confidence`.

Para comparar únicamente el resultado estadistico del modelo:

```bash
python ml/predict_ticket.py \
  --model ml/artifacts/ticket_classifier_es/ticket_classifier.joblib \
  --subject "URGENTE: no puedo entrar al correo" \
  --body "Necesito recuperar el acceso inmediatamente para trabajar."
```

## Artefactos generados

El entrenamiento genera localmente:

```text
ml/artifacts/ticket_classifier_es/
├── prepared_tickets.csv
├── ticket_classifier.joblib
├── metrics.json
└── sample_prediction.json
```

Estos archivos son reproducibles y estan excluidos de Git. No se deben subir
con `git add -f`.

## Comandos disponibles

| Comando | Descripcion |
| --- | --- |
| `python ml/train_ticket_classifier.py` | Prepara el CSV y entrena el modelo. |
| `python ml/predict_ticket.py` | Ejecuta una prediccion local. |
| `python ml/audit_ticket_dataset.py --input-csv <ruta>` | Genera una lista local de prioridades para revision humana, sin corregir etiquetas. |
| `python -m py_compile ml/*.py` | Comprueba la sintaxis de los scripts. |
| `python -m unittest discover -s tests -t . -v` | Ejecuta las pruebas sin colisión entre `tests.ml` y el módulo `ml`. |
| `python ml/train_ticket_classifier.py --enable-business-rules` | Evalua con reglas deterministas aprobadas. |

## Resultados de la copia editada validada (1 de noviembre de 2026)

Se utilizó la información de `tickets_esp_utf8.csv` y la estructura de su
referencia, sin modificar ninguna fuente. La utilidad
`reconcile_ticket_export.py` produjo 2.220 registros de estructura comprobada;
19 registros ambiguos fueron excluidos del conjunto final por autorización del
usuario y permanecen respaldados. La copia final es
`ml/artifacts/revision_pr13/dataset_final/tickets_esp_utf8_sin_ambiguos.csv`.
Los 139 registros
editados se conservan íntegramente en las copias y diferencias locales. De los
63 cambios manuales de prioridad, 62 están en la copia entrenable y uno en revisión.

El entrenamiento con Python 3.12.4 y las dependencias fijadas, sin reglas,
conservó 2.218 registros después de deduplicar: 1.774/444 por objetivo y cero
textos compartidos entre particiones.

| Objetivo | Macro F1 | Weighted F1 |
| --- | ---: | ---: |
| Tipo | 0,6984 | 0,7116 |
| Prioridad | 0,6191 | 0,6540 |
| Área/cola | 0,6886 | 0,6084 |

La copia aprende prioridades `low`, `medium` y `high`. Los valores corresponden
al conjunto final seleccionado, con 19 exclusiones declaradas; no constituyen
mejora demostrada sobre el experimento
histórico: cambiaron textos, población y particiones. Las métricas completas,
artefacto, auditoría y comprobaciones de inferencia están localmente en
`ml/artifacts/revision_pr13/`, excluido de Git. La auditoría actual identifica
55 candidatos léxicos para revisión humana, no 55 errores confirmados.

## Resultados históricos del CSV completo (anteriores a esta revisión)

Los siguientes valores identifican el dataset y código anteriores. No son
resultados del CSV actualizado ni de esta revisión. No deben atribuirse al
archivo nuevo hasta completar su validación y entrenamiento.

El 31 de octubre de 2026 se ejecuto el codigo del commit
`5c9942457569555554b08174ee6a960794b4c354` con el CSV identificado arriba,
`--language es` y los demas parametros predeterminados: `test_size=0.2`,
`random_state=42`, `min_target_count=2`, `max_features=120000` y reglas de
negocio desactivadas. Entorno de la ejecucion: Python 3.14.7, pandas 3.0.6,
scikit-learn 1.9.1 y joblib 1.6.0. Las cifras se tomaron del `metrics.json`
generado en esa misma ejecucion.

Para repetirla con una copia autorizada del mismo CSV (verifica su SHA-256
antes de comparar resultados):

```bash
python ml/train_ticket_classifier.py \
  --input-csv "<ruta-local-a-tickets_esp.csv>" \
  --language es \
  --output-dir ml/artifacts/ticket_classifier_es
```

| Salida | train_rows | test_rows | Macro F1 | Weighted F1 |
| --- | ---: | ---: | ---: | ---: |
| Clasificacion sugerida (`type`) | 1.789 | 448 | 0,6835 | 0,6899 |
| Prioridad solo modelo (`priority`) | 1.789 | 448 | 0,6225 | 0,6313 |
| Area responsable (`queue`) | 1.789 | 448 | 0,6500 | 0,5992 |

En esta particion, la interseccion de textos entre entrenamiento y prueba fue
0 para cada uno de los tres objetivos.

El CSV completo solo contiene `low`, `medium` y `high` como prioridades. Por
ello, el modelo entrenado con este CSV no puede predecir `critical` por si
solo; la regla experimental puede imponer esa etiqueta cuando se habilita.
Sus criterios funcionales y su evaluacion siguen pendientes. Estas metricas
no miden el efecto de la regla ni constituyen umbrales de aceptacion aprobados.

### Interpretacion segura de la prioridad

La prioridad tuvo Macro F1 de 0,6225 en la particion de prueba. En una prueba
local, el texto `URGENTE: no puedo entrar al correo` produjo `low` con
`confidence` aproximada de 0,638 cuando las reglas estaban desactivadas. Esto
demuestra que esa salida puede contradecir una señal de urgencia; no es una
prioridad lista para aplicarse automaticamente. La probabilidad del clasificador
no se ha calibrado ni validado como medida de seguridad. El agente humano debe
revisar el contexto antes de decidir la prioridad final.

En esa auditoría histórica del CSV completo, 627 tickets contenían una señal
detectada por la regla léxica de entonces: 495 estaban etiquetados `high`, 113 `medium` y 19 `low`.
Tampoco existe la etiqueta `critical` en ese CSV. Por eso activar la regla por
defecto o cambiar la prioridad de salida exige acordar criterios de negocio y
evaluarlos con datos etiquetados para ese fin.

## Verificacion reproducible con la muestra sintetica

Resultados reproducidos el 1 de noviembre de 2026 con los cambios locales de
esta revisión, 12 tickets sintéticos y el comando de verificación de arriba.
Entorno: Python 3.12.4, pandas 2.3.3, scikit-learn 1.9.1, joblib 1.6.0,
NumPy 2.3.4, SciPy 1.18.1 y threadpoolctl 3.7.0. Reglas desactivadas;
intersección de textos entre particiones: cero en los tres objetivos.

| Salida | train_rows | test_rows | Macro F1 | Weighted F1 |
| --- | ---: | ---: | ---: | ---: |
| Clasificacion sugerida (`type`) | 9 | 3 | 0,1667 | 0,2222 |
| Prioridad solo modelo (`priority`) | 9 | 3 | 0,0000 | 0,0000 |
| Area responsable (`queue`) | 9 | 3 | 0,0000 | 0,0000 |

Estos valores solo verifican que el pipeline entrena y evalua con datos
sinteticos; tres ejemplos de prueba por objetivo no permiten estimar su calidad
para tickets reales. La regla determinista requiere evaluacion aparte despues
de aprobar sus criterios funcionales.

## Estado de implementacion

- [x] Dataset en espanol analizado y preparado.
- [x] Entrenamiento de modelos para tipo, prioridad y area.
- [x] Prediccion local mediante artefacto `.joblib`.
- [x] Regla de urgencia compartida entre evaluacion y prediccion, desactivada por defecto.
- [x] Metricas y pipeline ML documentados.
- [x] Pruebas automatizadas del modulo ML.
- [ ] Integracion del modelo dentro de un backend FastAPI.
- [ ] Montaje del modelo dentro de un servicio Docker.

## Documentacion relacionada

- [Pipeline de dataset y modelo](DATASET_ML_PIPELINE.md)
- [Estrategia de entornos](../docs/arquitectura/entornos.md)
- [Correcciones de prioridad](CORRECCIONES_PRIORIDAD.md)
- [Seguimiento de la revisión del PR #13](REVISION_PR13.md)

El backend FastAPI y el servicio de inferencia se integraran en una etapa
posterior. Actualmente `compose.yaml` levanta PostgreSQL y pgvector, pero no
ejecuta el entrenamiento ni carga el modelo automaticamente.
