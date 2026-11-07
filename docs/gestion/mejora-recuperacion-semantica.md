# Mejoras de recuperación semántica

## Alcance

Continuación del prototipo del PR #16, integrado en main mediante `9d4376a`.
Se implementa en una rama nueva solicitada como `mejora-recuperacion-semantica`.
Conserva el monolito modular, FastAPI como autoridad y PostgreSQL + pgvector;
no introduce microservicios, un modelo definitivo ni un proveedor LLM.

## Criterios de aceptación técnicos

1. Medir ranking con `expectedDocumentId` opcional sin confundir cobertura con
   documento correcto; evaluar casos nuevos sin alterar el umbral ni reutilizar
   consultas de calibración.
2. Reproducir el mecanismo con textos/casos sintéticos incluidos y reconstruir
   las fuentes oficiales con registro, versiones, atribución y hashes verificables.
3. Preservar documentos originales; indexar cuerpo/título oficiales por separado
   de los pies editoriales añadidos por el proyecto, conservando procedencia fuera
   de los embeddings y comparando las variantes sobre las mismas consultas.
4. Rechazar el uso de bases del backend y controlar esquema/pgvector ausentes,
   sin trazas ni detalles privados en las respuestas públicas.
5. Validar perfiles V2 por identidad y revisión de corpus con una consulta acotada,
   sin leer todos los vectores por petición; invalidar cambios SQL externos y
   reindexaciones dentro de la misma transacción.
6. Exponer búsqueda optativa con sesión y CSRF reales, errores contractuales,
   respuestas privadas y estados separados para resultados, base vacía e
   información insuficiente.
7. Integrar el frontend al final: proxy dedicado de mismo origen, cookie permitida,
   Origin/CSRF, destino fijo sin redirecciones, límites de consulta, fuentes,
   idioma y prevención de respuestas obsoletas al cambiar sesión.

## Validación y límites

Las consultas incluidas son sintéticas y están marcadas como pendientes de
revisión humana. Los manuales oficiales no son un conjunto de consultas reales
anonimizadas. El CSV del clasificador no se utiliza como sustituto de etiquetas
de relevancia documental. Un mejor score o un caso aceptado no prueba suficiencia
de la respuesta; se registran también los desaciertos de documento esperado.

La revisión por corpus es experimental y no sustituye un catálogo documental
definitivo ni las futuras políticas de acceso, versionado histórico o retención.
Los perfiles de producción y su evaluación representativa requieren validación
humana. La distribución de textos oficiales/traducciones sigue pendiente de
revisar avisos y licencias; el repositorio contiene metadatos/preparador, no las
copias de las páginas.

AUTH-07 incluye login/logout, `/auth/me` y bootstrap CSRF HTTP.
La búsqueda reutiliza sus servicios internos sin abrir una ruta pública ni
fabricar identidades. Las pruebas de navegador usan un doble explícito de las
rutas de bootstrap, junto con sesión/CSRF persistentes y recuperación reales;
eso no constituye validación completa de autenticación de producción.

## Comparación exploratoria del contenido indexado

Se compararon los mismos 15 documentos y las mismas consultas sintéticas antes
y después de separar los pies editoriales del cuerpo oficial. Se conservaron
las etiquetas, el modelo y su revisión. Cada variante se calibró con sus 33
casos y se evaluó sin reajuste sobre otros 14 casos ya existentes.

| Medida | Copia con pies editoriales | Cuerpo oficial separado |
| --- | --- | --- |
| Fragmentos indexados | 357 | 340 |
| Documento correcto primero, calibración | 26/30 | 27/30 |
| Documento correcto entre cinco fragmentos, calibración | 29/30 | 30/30 |
| Documento correcto primero, evaluación | 5/7 | 6/7 |
| Documento correcto entre cinco fragmentos, evaluación | 7/7 | 7/7 |

Ambas variantes conservaron los 30 casos con cobertura de calibración y los
7 de evaluación; rechazaron los 3 y 7 casos sin cobertura, respectivamente.
Los cortes obtenidos fueron aproximadamente 0,5138 y 0,4982, propios de cada
versión del corpus. No deben copiarse como valores universales.

Son conjuntos pequeños y consultas conocidas previamente: esta comparación
orienta la mejora de preprocesamiento, pero no es una evaluación ciega ni
representativa de tickets reales. Todavía queda un desacierto de primer
documento entre las siete consultas con cobertura de evaluación. La revisión
humana del contenido recuperado sigue siendo necesaria.

La receta para reconstruir el cuerpo oficial desde fuentes públicas, generar
el perfil V2 y evaluar las 14 consultas está en
[Fuentes y reproducción](../../ml/sources/README.md).

Para una evaluación representativa, reservar consultas anonimizadas distintas
de la calibración y acordar con soporte qué documentos responden cada caso.
Medir cobertura, rechazos y ranking por separado. Si se amplía el corpus,
registrar su versión y repetir el proceso con el perfil correspondiente.

La autorización conserva la transacción abierta hasta obtener el resultado.
Para evaluar su costo, comparar solicitudes simultáneas de una misma sesión
con solicitudes de sesiones independientes y registrar la espera de bloqueos
y la latencia. Cualquier cambio al alcance de la transacción debe preservar
las garantías de revocación y validación CSRF.

## Referencias

- [Contrato de recuperación V1](../contratos/recuperacion-semantica-v1.md).
- [Backend y configuración](../../backend/README.md#búsqueda-semántica-protegida-optativa).
- [Frontend integrado](../../frontend/README.md#búsqueda-semántica-integrada).
- [Fuentes y reproducción](../../ml/sources/README.md).
