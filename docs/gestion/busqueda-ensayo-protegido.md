# HU07: búsqueda dentro del ensayo protegido

Este incremento parte de `main` después del #61 y es independiente del #60.
Integra la búsqueda HTTP existente en la composición local de testing: no
redefine relevancia, catálogos, límites de generación ni decisiones del PO.

## Recorrido reproducible

Desde `backend/`, con el entorno Python/Next/Edge y `PLAYWRIGHT_MODULE` preparados:

```powershell
./.venv/Scripts/python.exe -B -m herramientas.ingreso_local.demo `
  --frontend ../frontend --reporte ../artifacts/busqueda-demo-nueva.json `
  --browser-driver ../frontend/tests/proxy/browser-crud.mjs `
  --env-file ../.env --search --search-fixture
```

El modo fixture necesita solamente PostgreSQL de testing: crea una base propia
en loopback:5433, emite sesiones/CSRF reales y ejecuta Next y FastAPI con TLS
directo. El navegador inicia sesión como administrador y agente, navega a
`/busqueda`, recibe `POST /api/v1/search` y comprueba la fuente en la interfaz.
El resultado semántico es sintético, no acredita embeddings ni relevancia.
Este modo no requiere ni llama a Gemini. Los reportes rechazan sobrescritura.

Para recuperación real, omitir `--search-fixture` y configurar la conexión
semántica separada, el modelo y el perfil V2 vigente conforme a `ml/README.md`.
El uso de `--search` no necesita habilitar RAG ni proporcionar una clave LLM.
El ensayo RAG existente también recorre búsqueda cuando dispone de recuperación.
En modo real, una búsqueda sin cobertura puede devolver vacío; no se exige un
acierto sintético ni se altera el umbral para hacer pasar la prueba.

## Frontera y evidencia

La fábrica local registra búsqueda solo con `search_enabled`, perfil local y
cookie de sesión coincidente. El middleware exige Origin, canal SEC-01B,
cookies no ambiguas y sello de ingreso antes de la ruta. La ruta contractual
comprueba después sesión y CSRF persistidos. El lanzador permite exactamente
POST `/api/v1/search`, y GET `/busqueda`; no permite un proxy arbitrario.
El proxy Next usa origen y nombre de cookie del propio ensayo, sin heredar una
configuración productiva diferente. Se conservan los límites del proxy existente.

Las pruebas HTTP comprueban ambos roles, sello ausente, Origin ajeno, CSRF
inválido, éxito privado y dependencia no disponible. Son scopes HTTPS de
testing; el ensayo Edge es quien acredita el recorrido sobre sockets TLS.
Los reportes registran hashes de fuentes y la modalidad de recuperación y
confirman la eliminación de la base y cierre de procesos.

## Pendientes ajenos a este incremento

- Evaluación con la matriz MLOps y consultas reales anonimizadas, etiquetas
  revisadas de forma independiente y propuesta del umbral de relevancia.
- Propuesta del límite de generaciones con datos de latencia/consumo.
- Entrega y validación del artefacto del clasificador, entorno y métricas.
- Ratificación del equipo para tipo/categoría, colas/áreas, probabilidades,
  adaptador, «Aceptar y resolver» y métricas HU10.

El #59 y la retirada de la excepción del escáner (#61) ya están integrados.
HU06 y la representación pública de predicción se revisan en el #60. Este
documento no marca tarjetas de Trello como aprobadas o terminadas.
