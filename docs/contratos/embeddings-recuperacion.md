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

## Validaciones, errores y límites

- Documento o consulta vacíos: `ValueError` o error de argumentos del CLI.
- `limit` fuera de 1–20: error de argumentos del CLI.
- Archivo UTF-8 inexistente o inválido: error de lectura. El archivo no puede superar 1 MB.
- Consulta de más de 1000 caracteres: error de argumentos del CLI.
- Base de datos ausente, esquema no preparado o dependencia no instalada: error de ejecución; el CLI no implementa aún el formato de errores HTTP.
- Reindexar un mismo documento y modelo reemplaza los fragmentos dentro de una transacción.
- Solo se indexan textos preparados, autorizados y sin información sensible; todavía no existe carga de archivos ni control de acceso del producto.

La futura ruta `POST /api/v1/search` conservará el contrato provisional en [frontend-backend.md](frontend-backend.md), pero requerirá revisión de autenticación, manejo uniforme de errores y criterio de relevancia antes de integrarse al backend.
