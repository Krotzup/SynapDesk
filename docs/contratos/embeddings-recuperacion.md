# Contrato experimental de embeddings y recuperación

## Estado

**Provisional.** Se aplica al prototipo en `ml/semantic_retrieval/`, no constituye una API pública ni una decisión definitiva sobre el modelo.

## Entrada y salida del generador de embeddings

Entrada: lista no vacía de textos Unicode no vacíos. Salida: un vector finito y no nulo de 384 números por texto, en el mismo orden, normalizado a longitud 1. El prototipo usa `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` con una revisión fijada en `config.py`. Indexación y consulta deben usar exactamente el mismo `modelId`. Se rechazan texto vacío, dimensiones inesperadas y valores no finitos.

Ejemplo conceptual: `["No hay conexión a la red"] -> [[0.012, ...]]` (vector abreviado; no corresponde a una inferencia real).

## Entrada y salida de la recuperación

La indexación recibe `documentId` UUID, `title`, texto UTF-8 y su `modelId`. Produce fragmentos con posición e identificadores estables, guardados en `semantic_prototype_chunks` junto al vector. La búsqueda recibe `query` no vacía y `limit` de 1 a 20; devuelve `items` ordenados por similitud coseno descendente. Cada elemento contiene `documentId`, `documentChunkId`, `title`, `excerpt` y `score`.

```json
{
  "items": [
    {
      "documentId": "11111111-1111-4111-8111-111111111111",
      "documentChunkId": "3f96b5e6-4cef-5e5e-b346-3955236e50f6",
      "title": "Conectividad",
      "excerpt": "Revise la configuración de red...",
      "score": 0.82
    }
  ]
}
```

El ejemplo ilustra la forma de respuesta; sus identificadores, texto y puntaje no son resultados de una ejecución. El valor de `score` se calcula como `1 - distancia_coseno`, con rango [-1, 1]. No representa probabilidad. Una consulta sin fragmentos indexados para ese modelo devuelve `{"items": []}`.

## Relevancia y abstención experimental

La búsqueda interna admite `min_score` opcional, finito entre -1 y 1. Con ese
filtro devuelve únicamente fragmentos con `score >= min_score`, preservando los
cinco campos, el orden y el límite. Sin umbral conserva su comportamiento previo.

El CLI activa el filtro mediante `search --relevance-profile <archivo.json>`.
Si no hay fragmentos que alcancen el corte, devuelve `{"items": []}` en stdout
y «Información insuficiente» en stderr, con salida 0. Esto significa que no hay
evidencia que supere el criterio de ese corpus; no demuestra que la pregunta sea
imposible de responder en otras fuentes. No se agregan campos a la API pública.

`calibrate-relevance --cases <consultas.json> --output <perfil-nuevo.json>` genera
un perfil experimental asociado a `modelId` y a una huella de los fragmentos y
vectores. Las consultas requieren `queryId`, `query` y `answerable` booleano, con
ambas clases y sin duplicados. Se preservan todas las consultas con cobertura
observadas y, bajo esa condición, se maximiza el rechazo de las que no la tienen.
Los empates o solapamientos se registran sin fingir que se separaron.

El perfil guarda el umbral, las huellas y los resultados de calibración. No se
sobrescribe ni se aplica a un modelo o corpus diferente: esos casos producen
error controlado (salida 2), sin buscar automáticamente sin filtro. La búsqueda
con perfil usa una instantánea de solo lectura para verificar y consultar el
mismo corpus. Las etiquetas, la evaluación independiente y la aprobación del
perfil para producción requieren revisión humana. No existe un umbral global
aprobado ni una garantía de que todo fragmento aceptado responda correctamente.

## Validaciones, errores y límites

- Documento o consulta vacíos: `ValueError` o error de argumentos del CLI.
- `limit` fuera de 1–20: error de argumentos del CLI.
- Archivo inexistente, ilegible, vacío o UTF-8 inválido: error controlado de argumentos del CLI (salida 2), sin traza. El archivo no puede superar 1 MB.
- Consulta de más de 1000 caracteres o que supera el límite real del modelo (128 tokens, incluidos los especiales): error de argumentos del CLI. No se trunca silenciosamente. La misma validación de tokens se aplica a los fragmentos antes de generar embeddings.
- PostgreSQL inaccesible, base inexistente o conexión rechazada: error controlado de argumentos del CLI (salida 2), sin traza, URL ni detalles de credenciales. Se configura un timeout de conexión de cinco segundos.
- Esquema no preparado o dependencia no instalada: error de ejecución; el CLI no implementa aún el formato de errores HTTP.
- Reindexar un mismo documento y modelo reemplaza los fragmentos dentro de una transacción.
- Solo se indexan textos preparados, autorizados y sin información sensible; todavía no existe carga de archivos ni control de acceso del producto.

La verificación usa una base propia del prototipo (`synapdesk_semantic_test`)
dentro de `db_test`, separada de `synapdesk_test`, que pertenece a las pruebas
del backend. La tabla experimental no participa en las migraciones de Alembic.

La futura ruta `POST /api/v1/search` conservará el contrato provisional en [frontend-backend.md](frontend-backend.md), pero requerirá revisión de autenticación, manejo uniforme de errores y criterio de relevancia antes de integrarse al backend.
