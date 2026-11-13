# Fuentes oficiales y reproducción del piloto

`procedimientos_oficiales.json` contiene los 15 procedimientos, sus URLs,
secciones, idiomas, UUID, aplicabilidad, hashes del HTML y texto extraído y la
procedencia/licencias del repositorio original. No incluye el contenido de las
páginas oficiales. Se conserva español publicado cuando existe y el original
inglés en los demás casos; no se generan traducciones.

Preparar `ml/requirements-corpus.txt` y ejecutar desde la raíz:

```powershell
python -m ml.tools.build_procedure_corpus --output ml/data/procedimientos_v1
```

Las páginas pueden cambiar su presentación sin cambiar el texto. Al descargar,
el preparador verifica la huella del texto extraído de cada documento y registra
en el manifiesto las huellas HTML esperada y recibida. Un texto distinto detiene
la preparación. Las licencias se verifican por sus bytes. Si se conservan los
snapshots HTML de la primera extracción, pueden usarse en modo de solo lectura
con la verificación exacta de sus huellas:

```powershell
python -m ml.tools.build_procedure_corpus --output ml/data/procedimientos_reproducidos --cache-dir ml/data/knowledge_base/piloto_v1
```

La carpeta destino debe ser nueva. Se verifican los 15 textos, 11 snapshots y
las licencias antes de escribir; se generan catálogo, casos y manifiesto. No se
ejecutan comandos contenidos en las fuentes. Solo se descargan URLs HTTPS de
hosts oficiales permitidos; se verifican los destinos de redirección y límites
de tamaño. Una fuente actualizada requiere otra versión y revisión del registro.

Los hashes permiten reproducir y auditar el contenido, no conceden derechos de
redistribución. Las licencias registradas se refieren al repositorio original;
deben revisarse avisos particulares y versiones traducidas antes de publicar los
textos. La distribución del corpus sigue marcada como pendiente. La reconstrucción
local conserva los avisos y las copias de licencia; los datos generados permanecen
excluidos de Git. El registro no declara una aprobación legal automática.

Cada documento se preserva completo en `documents/`; `retrieval/` contiene solo
título y cuerpo oficiales para el modelo. El catálogo identifica ambos archivos
y sus hashes con `preprocessingVersion=official_body_v1`. Esta separación evita
recuperar los pies editoriales de atribución/licencia como si fueran instrucciones
de soporte. Los metadatos se almacenan y muestran por separado. No se alteran los
originales para obtener esta variante, ni se cambian sus etiquetas de evaluación.

La cifra histórica 0,5138 pertenece a este corpus y sus consultas. No es un valor
predeterminado. Para verificar el mecanismo sin fuentes externas se incluyen dos
textos sintéticos y casos separados en `ml/examples/relevancia/`; sus umbrales
pueden ser diferentes. Los casos tienen estado sintético y requieren validación
humana para representar el uso real de una organización.

Para reproducir la variante de cuerpo oficial, configurar
`SYNAPDESK_SEMANTIC_DATABASE_URL` con una **base semántica propia y vacía**.
Después de preparar `ml/data/procedimientos_v1`, ejecutar desde la raíz con las
dependencias semánticas instaladas y destinos de informes nuevos.

```powershell
New-Item -ItemType Directory -Force ml/artifacts | Out-Null
python -m ml.tools.index_procedure_corpus --corpus ml/data/procedimientos_v1
python -m ml.semantic_retrieval.cli calibrate-relevance --cases ml/data/procedimientos_v1/cases.json --output ml/artifacts/piloto_perfil_v2.json
python -m ml.semantic_retrieval.cli evaluate-relevance --cases ml/examples/relevancia/piloto_evaluacion.json --relevance-profile ml/artifacts/piloto_perfil_v2.json --output ml/artifacts/piloto_evaluacion.json
```

El preparador genera 33 casos de calibración. El conjunto versionado de
evaluación contiene las 14 consultas sintéticas de la comparación original.
El perfil queda ligado a la identidad y revisión de esa base. Generar un perfil
nuevo al reconstruir el corpus en otra base.

El conjunto adicional `ml/examples/relevancia/parafrasis_evaluacion.json`
incluye 25 consultas etiquetadas. Las 21 con prefijo `PAR` son sintéticas y las
cuatro con prefijo `PUB` son adaptaciones al español de reportes públicos. En
las adaptaciones se conserva el síntoma técnico, se omiten identificadores
del texto y se registra el enlace de procedencia. Se asigna un documento
esperado cuando hay una guía concreta para el problema. «No tengo internet
en mi computador» se cuenta como una consulta con cobertura de diagnóstico
inicial. Se omite el documento esperado porque la guía apropiada depende de
la conexión y del alcance de la falla. Los casos fuera de alcance incluyen
solicitudes que comparten vocabulario con el corpus, como transferencias de
zonas DNS o credenciales de Docker Hub.

Evalúa el conjunto con el perfil del piloto ya calibrado y una ruta de salida
nueva. Los casos adicionales quedan reservados para evaluación.

```powershell
python -m ml.semantic_retrieval.cli evaluate-relevance --cases ml/examples/relevancia/parafrasis_evaluacion.json --relevance-profile ml/artifacts/piloto_perfil_v2.json --output ml/artifacts/parafrasis_evaluacion.json
```

El informe separa los casos con y sin cobertura que superaron el umbral y la
posición del documento esperado entre los primeros cinco fragmentos candidatos.
Ese ranking se calcula antes de filtrar. Para ver los fragmentos que superan
el umbral, ejecuta `search` con el mismo perfil. Este comando reproduce la
consulta de conectividad general del comentario de revisión.

```powershell
python -m ml.semantic_retrieval.cli search --query "No tengo internet en mi computador" --limit 5 --relevance-profile ml/artifacts/piloto_perfil_v2.json
```

Los reportes públicos y sus etiquetas editoriales permiten un ensayo
exploratorio. La validación representativa sigue requiriendo consultas de
soporte anonimizadas y etiquetas revisadas por alguien independiente.

El conjunto `ml/examples/relevancia/soporte_evaluacion.json` añade ocho
consultas sintéticas redactadas como solicitudes de soporte. Cuatro tienen una
guía esperada y cuatro requieren procedimientos ausentes del catálogo aunque
comparten vocabulario con él. Evalúalo con el mismo corpus y perfil V2 del
piloto. Los casos quedan reservados para evaluación.

```powershell
python -m ml.semantic_retrieval.cli evaluate-relevance --cases ml/examples/relevancia/soporte_evaluacion.json --relevance-profile ml/artifacts/piloto_perfil_v2.json --output ml/artifacts/soporte_evaluacion.json
```

Para revisar las etiquetas, pide a otra persona que contraste cada consulta
con el catálogo antes de ver los resultados del modelo. Debe confirmar si
alguna guía cubre la solicitud y, para las consultas con cobertura, si el
`expectedDocumentId` corresponde al procedimiento esperado. Si la cobertura
es ambigua, registra el motivo antes de interpretar el informe.
La [hoja de revisión ciega](../../docs/gestion/revision-ciega-relevancia-pr32.md)
incluye las ocho consultas, las guías y una plantilla para casos reales anonimizados.

Revisa por separado `counts.coveredRejected` (consultas cubiertas que se
abstuvieron) y `counts.uncoveredAccepted` (consultas fuera de cobertura que
recibieron resultados). Las observaciones por `queryId` permiten revisar
cada desacuerdo y consultar la posición del documento esperado cuando aplica.

Para comparar con la variante histórica, configurar una segunda base semántica
vacía. Indexar los archivos archivados del mismo catálogo con los mismos UUID.

```powershell
python -m ml.semantic_retrieval.cli init-db
$catalogoPiloto = Get-Content ml/data/procedimientos_v1/catalog.json -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($documentoPiloto in $catalogoPiloto.documents) {
    $archivoPiloto = Join-Path ml/data/procedimientos_v1 $documentoPiloto.file
    python -m ml.semantic_retrieval.cli index --document-id $documentoPiloto.documentId --title $documentoPiloto.title --file $archivoPiloto
    if ($LASTEXITCODE -ne 0) { throw "Falló la indexación de $($documentoPiloto.documentId)" }
}
python -m ml.semantic_retrieval.cli calibrate-relevance --cases ml/data/procedimientos_v1/cases.json --output ml/artifacts/piloto_historico_perfil.json
python -m ml.semantic_retrieval.cli evaluate-relevance --cases ml/examples/relevancia/piloto_evaluacion.json --relevance-profile ml/artifacts/piloto_historico_perfil.json --output ml/artifacts/piloto_historico_evaluacion.json
```
