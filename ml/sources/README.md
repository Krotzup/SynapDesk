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

Las páginas pueden cambiar: el preparador rechaza hashes diferentes en lugar de
alterar silenciosamente el piloto. Si se conservan los snapshots de la primera
extracción, pueden utilizarse en modo de solo lectura:

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
