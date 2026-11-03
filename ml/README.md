# Machine Learning

Espacio para experimentación, entrenamiento, evaluación y entrega de modelos versionados de SynapDesk. Los notebooks no se utilizarán directamente como componentes ejecutables del backend.

## Prototipo de embeddings y recuperación semántica

`semantic_retrieval/` implementa el flujo local de textos UTF-8 controlados →
fragmentos → embeddings → PostgreSQL + pgvector → búsqueda. Es un prototipo
experimental; la integración HTTP, autenticación, extracción de PDF y RAG siguen
pendientes. Su tabla experimental no fija el esquema documental del producto.

El candidato es `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`,
revisión `e8f8c211226b894fcb81acc59f3b34ba3efd5f42`, con 384 dimensiones.
Indexación y consulta usan exactamente el mismo `modelId`. Se fragmenta en
ventanas de 96 tokens con 16 de solapamiento. Antes de generar vectores se
comprueba el límite real del modelo: 128 tokens, incluidos los especiales.
Las consultas que lo superen se rechazan explícitamente, sin truncarlas.
También se conserva el límite de 1000 caracteres por consulta y 1 MB por archivo.

`score = 1 - distancia_coseno` es similitud en [-1, 1], no probabilidad ni
confianza calibrada. La búsqueda exacta filtra por modelo y devuelve
`documentId`, `documentChunkId`, `title`, `excerpt` y `score`. Sin documentos
para ese modelo devuelve `{"items": []}`. Sin umbral de relevancia, obtener
resultados no garantiza que respondan a la consulta.

### Entorno y comandos

Usar Python 3.12 en un entorno virtual y las versiones fijadas, junto con las
restricciones del clasificador cuando se prueben juntos. La revisión del modelo se fija
independientemente de las versiones de las bibliotecas. Las dependencias
transitivas pueden variar; registrar el entorno de la ejecución.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r ml/requirements-semantic.txt
.\.venv\Scripts\python.exe -m pip check
```

Al validar junto al clasificador en una copia de `main`, instalar en una sola
operación `-r ml/requirements.txt -r ml/requirements-semantic.txt` para respetar
sus versiones fijadas. Esa combinación se verifica por separado; no requiere
fusionar las ramas para realizar una simulación local.

En Windows, Docker Desktop con backend WSL 2 permite usar la imagen del proyecto.
Si falta WSL, seguir la [instalación oficial de Microsoft](https://learn.microsoft.com/windows/wsl/install)
y después la [instalación de Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/).
Completar cualquier reinicio requerido antes de ejecutar los contenedores.

Usar exclusivamente `db_test` para la verificación. Configurar localmente las
variables de pruebas de `.env.example`, sin subir credenciales, e iniciar:

```powershell
docker compose --profile testing up -d db_test
docker compose --profile testing ps db_test
$env:SYNAPDESK_SEMANTIC_DATABASE_URL = "postgresql://synapdesk_test:<clave-de-pruebas>@localhost:5433/synapdesk_test"
.\.venv\Scripts\python.exe -X utf8 -m ml.semantic_retrieval.cli init-db
.\.venv\Scripts\python.exe -X utf8 -m ml.semantic_retrieval.cli index --document-id 11111111-1111-4111-8111-111111111111 --title "Conectividad" --file ml/examples/conectividad.txt
.\.venv\Scripts\python.exe -X utf8 -m ml.semantic_retrieval.cli index --document-id 22222222-2222-4222-8222-222222222222 --title "Impresora" --file ml/examples/impresora.txt
.\.venv\Scripts\python.exe -X utf8 -m ml.semantic_retrieval.cli search --query "No puedo acceder a la red de la oficina" --limit 5
.\.venv\Scripts\python.exe -X utf8 -m ml.semantic_retrieval.cli search --query "La impresora no imprime" --limit 5
```

Sustituir la contraseña de ejemplo por la de la base de pruebas y codificarla
para URL si contiene caracteres especiales. El CLI no carga `.env`
automáticamente. No pegar la conexión real ni sus credenciales en la evidencia.
La primera carga puede descargar el modelo; las siguientes reutilizan la caché.
`init-db` es repetible. Reindexar reemplaza atómicamente los fragmentos de ese
documento y modelo, con UUID estables para cada posición.

Archivos inexistentes, ilegibles, vacíos, UTF-8 inválido, tamaño excesivo y
consultas inválidas producen un error de argumentos controlado (salida 2).
Para comprobar el caso solicitado, repetir `index` con un archivo inexistente:
el error debe describir la lectura fallida, sin traza y antes de cargar el modelo.

### Criterios verificables y pruebas

Los siguientes criterios técnicos concretan la verificación del prototipo;
la aceptación del PR corresponde al equipo:

1. Inicializar PostgreSQL con pgvector e indexar ambos ejemplos con el modelo
   real fijado. Registrar versiones y salidas efectivamente obtenidas.
2. Recuperar conectividad primero para la consulta de red e impresora primero
   para la de impresión, con los cinco campos y orden descendente por similitud.
   Dos ejemplos no permiten estimar calidad general ni fijar umbrales.
3. Verificar vectores finitos, no nulos, normalizados y de 384 dimensiones;
   textos preparados dentro del límite del modelo, incluidos tokens especiales.
4. Reindexar sin duplicados y con identificadores estables. Comprobar rollback
   de una inserción fallida y aislamiento entre modelos.
5. Rechazar entradas inválidas, devolver lista vacía sin documentos del modelo
   y superar las pruebas automatizadas junto con las del clasificador.

Las pruebas rápidas no necesitan PostgreSQL ni descargar un modelo:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -t . -v
```

Para activar las pruebas del tokenizador con subpalabras y los vectores reales,
primero disponer del modelo/revisión en caché y ejecutar:

```powershell
$env:SYNAPDESK_RUN_SEMANTIC_MODEL_TESTS = "1"
.\.venv\Scripts\python.exe -X utf8 -m unittest tests.ml.test_semantic_chunking tests.ml.test_semantic_integration.RealSemanticModelTests -v
```

La prueba de base de datos real requiere su variable específica, para evitar
usar por accidente la conexión del producto. Crea un esquema de nombre único y
revierte su transacción completa al salir; no reemplaza documentos del producto.
Verifica el flujo real, reindexación, rollback y aislamiento, e imprime un JSON
`semantic_evidence` con resultados y versiones, sin la conexión ni contraseñas:

```powershell
$env:SYNAPDESK_SEMANTIC_TEST_DATABASE_URL = $env:SYNAPDESK_SEMANTIC_DATABASE_URL
.\.venv\Scripts\python.exe -X utf8 -m unittest tests.ml.test_semantic_integration.RealSemanticDatabaseTests -v
```

Sin sus variables de activación, las pruebas reales se informan como omitidas;
no constituyen evidencia de integración ejecutada. Guardar la salida real de
los comandos del CLI y de esta prueba en la descripción o comentarios del PR.

### Decisiones futuras

Evaluar consultas anonimizadas con relevancia etiquetada mediante Recall@5,
MRR@5, latencia, tamaño y costo antes de elegir el modelo definitivo, el umbral
para «información insuficiente», un índice vectorial o la política de indexación.
Un fragmento puede comenzar a mitad de frase por el solapamiento; acordar su
presentación con frontend (por ejemplo, una elipsis) al conectar resultados
reales. Estas propuestas no autorizan cambiar el frontend ni la API pública.

Contrato experimental: [embeddings-recuperacion.md](../docs/contratos/embeddings-recuperacion.md).
