# Machine Learning

Espacio para experimentación, entrenamiento, evaluación y entrega de modelos versionados de SynapDesk. Los notebooks no se utilizarán directamente como componentes ejecutables del backend.

## Prototipo de embeddings y recuperación semántica

`semantic_retrieval/` contiene un primer flujo ejecutable, aislado de la API: texto UTF-8 controlado → fragmentos → embeddings → PostgreSQL con pgvector → búsqueda de fragmentos. No procesa PDF ni tickets, no autentica usuarios y no genera recomendaciones. Usa una tabla experimental para no fijar todavía el esquema de documentos del producto.

El candidato inicial es [paraphrase-multilingual-MiniLM-L12-v2](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2), fijado a la revisión declarada en `semantic_retrieval/config.py`. Produce 384 dimensiones. Se eligió para probar contenido en español, no como selección definitiva. Se usará el mismo modelo y revisión al indexar y consultar; los resultados de otras versiones no se mezclan. Los textos se dividen en ventanas de 96 tokens con 16 de solapamiento, por debajo del máximo de 128 tokens publicado para este modelo.

El prototipo acepta archivos de hasta 1 MB y consultas de hasta 1000 caracteres. La búsqueda utiliza distancia coseno exacta de pgvector y convierte cada distancia a similitud con `score = 1 - distancia_coseno`. El rango matemático es [-1, 1]; un valor alto indica mayor semejanza, pero **no es una probabilidad ni una medida calibrada de confianza**. No se fija todavía un umbral de relevancia. Los resultados incluyen los identificadores de documento y fragmento para conservar la fuente.

### Ejecutar en desarrollo local

Desde la raíz del repositorio, con Python, Docker Desktop y la base `db` de `compose.yaml` iniciada:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r ml/requirements-semantic.txt
docker compose up -d db
$env:SYNAPDESK_SEMANTIC_DATABASE_URL = "postgresql://synapdesk_app:<clave-local>@localhost:5432/synapdesk"
.\.venv\Scripts\python.exe -m ml.semantic_retrieval.cli init-db
.\.venv\Scripts\python.exe -m ml.semantic_retrieval.cli index --document-id 11111111-1111-4111-8111-111111111111 --title "Conectividad" --file ml/examples/connectividad.txt
.\.venv\Scripts\python.exe -m ml.semantic_retrieval.cli index --document-id 22222222-2222-4222-8222-222222222222 --title "Impresora" --file ml/examples/impresora.txt
.\.venv\Scripts\python.exe -m ml.semantic_retrieval.cli search --query "No puedo acceder a la red de la oficina" --limit 5
```

Sustituir `<clave-local>` por la contraseña configurada en `.env`; si contiene caracteres especiales, codificarlos para una URL. La variable solo se usa en el proceso local y no debe incorporarse a Git. La primera ejecución descargará el modelo. El comando `index` reemplaza atómicamente los fragmentos de ese documento y esa versión del modelo. `init-db` es repetible y no borra datos. La respuesta de `search` tiene forma `{"items":[...]}`, compatible en estructura con el contrato provisional de búsqueda, pero todavía no hay endpoint HTTP.

### Verificación y siguientes decisiones

Ejecutar las pruebas que no requieren descargas ni base de datos:

```powershell
py -m unittest discover -s ml/tests -v
```

Antes de usar este candidato en el producto, preparar consultas reales anonimizadas con fragmentos relevantes etiquetados y comparar modelos mediante Recall@5, MRR@5, latencia, tamaño y costo operacional. Revisar errores, contenido sensible y casos sin resultados útiles. Elegir luego dimensión, umbral, política de indexación, tipo de índice vectorial y esquema definitivo; al integrar el backend, exponer `POST /api/v1/search` con autenticación y el contrato vigente. Los tickets históricos, extracción documental y RAG quedan para incrementos posteriores.
