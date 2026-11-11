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

Las consultas incluidas son sintéticas o adaptaciones de reportes públicos.
Sus etiquetas son exploratorias y están pendientes de revisión independiente.
El CSV del clasificador no se utiliza como sustituto de etiquetas de relevancia
documental. Un caso aceptado puede mostrar una guía que no responde a la
consulta. Por eso se registran por separado abstención y ranking.

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

### Evaluación con paráfrasis nuevas

Se evaluaron 25 consultas etiquetadas con el perfil del cuerpo oficial
(15 documentos y 340 fragmentos), sin reajustar el corte (0,4982). El CLI midió
los candidatos antes del corte y el servicio de recuperación comprobó
los estados y los fragmentos devueltos con un límite de cinco.

| Medida | Resultado |
| --- | ---: |
| Consultas con cobertura que mostraron algún resultado | 14/16 |
| Consultas sin cobertura con `insufficient_information` | 7/9 |
| Documento esperado primero, antes del corte | 8/15 |
| Documento esperado entre los cinco candidatos, antes del corte | 14/15 |
| Documento esperado primero, en los resultados devueltos | 7/15 |
| Documento esperado incluido en los resultados devueltos | 13/15 |

Las cuatro adaptaciones de reportes públicos mostraron la guía esperada
entre los resultados devueltos, dos de ellas en primer lugar. La paráfrasis
DNS `PAR-01` devolvió la guía esperada en el cuarto fragmento.

El servicio se abstuvo al buscar cómo montar una ruta desde CMD (`PAR-14`),
aunque la guía esperada era el primer candidato. En cambio, mostró guías
para transferencias de zona DNS (`PAR-15`) y Wi-Fi con EAP-TLS (`PAR-19`),
dos tareas que el corpus no explica. Ambos falsos positivos obtuvieron
mayor similitud que la consulta cubierta rechazada. Ajustar solo el corte
no corrige los tres casos a la vez.

«No tengo internet en mi computador» (`PAR-21`) reporta un problema de
conectividad. Las guías permiten orientar comprobaciones iniciales, como
verificar la conexión y si otros equipos están afectados. La prueba devolvió
`insufficient_information`, por lo que cuenta como la segunda abstención
con cobertura. La consulta entra en la métrica de cobertura. Para el ranking
se usan los 15 casos con una guía específica asignada. En la interfaz, el
aviso pide indicar el sistema afectado, el mensaje de error o los intentos
previos antes de volver a buscar. Los casos, la procedencia y los comandos
están en
[Fuentes y reproducción](../../ml/sources/README.md).

### Medición local de concurrencia

Se ejecutaron tres rondas de cuatro solicitudes simultáneas por escenario
contra FastAPI, el modelo multilingüe y dos bases PostgreSQL de prueba
separadas para autenticación y recuperación. Se indexaron 15 documentos
con 340 fragmentos. Las sesiones y los tokens CSRF se generaron con los
servicios internos.

| Medida por solicitud | Una sesión compartida | Cuatro sesiones independientes |
| --- | ---: | ---: |
| Latencia mediana | 728,0 ms | 639,9 ms |
| Latencia máxima | 1549,2 ms | 832,9 ms |
| Tiempo mediano con conexión de autenticación ocupada | 664,8 ms | 605,1 ms |
| Espera mediana por el bloqueo del modelo | 0,0 ms | 178,7 ms |

Las 12 solicitudes de cada escenario respondieron correctamente. La conexión
de autenticación permanece ocupada durante gran parte de la solicitud. Se midió
la espera por el bloqueo del modelo, con un máximo de 449,5 ms entre sesiones
independientes. El ensayo no instrumentó la espera por bloqueos SQL ni estima
capacidad de producción. Cualquier ajuste de la transacción requiere preservar
las garantías de revocación y validación CSRF.

### Evaluación adicional y concurrencia

El índice reconstruido conservó la huella del corpus de 15 documentos y 340
fragmentos. La calibración con las 33 consultas originales reprodujo el umbral
de 0,4981627604760416. La restauración del respaldo conservó la huella y la
revisión necesarias para utilizar el nuevo perfil V2.

Se evaluaron ocho consultas sintéticas. Tres de las cuatro consultas con
cobertura devolvieron resultados. Tres de las cuatro fuera de cobertura
también devolvieron resultados. El documento esperado fue el primer candidato
en dos de los cuatro casos con guía asignada. Las etiquetas quedan pendientes
de revisión independiente con la
[hoja de revisión ciega](revision-ciega-relevancia-pr32.md).

El ensayo adicional envió 124 solicitudes locales a FastAPI con el modelo y
PostgreSQL reales y sesiones de prueba emitidas por los servicios internos.
Todas devolvieron HTTP 200. El p95 se calculó por rango más cercano.

| Solicitudes simultáneas | Sesiones | Solicitudes | Latencia p95 | Conexión de autenticación ocupada p95 | Espera del modelo p95 |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | Una | 12 | 586 ms | 570 ms | 0 ms |
| 4 | Compartida | 24 | 1394 ms | 1355 ms | 0 ms |
| 4 | Independientes | 24 | 884 ms | 837 ms | 356 ms |
| 8 | Compartida | 32 | 2424 ms | 2282 ms | 0 ms |
| 8 | Independientes | 32 | 1373 ms | 1269 ms | 850 ms |

Se observaron hasta ocho conexiones de autenticación simultáneas. La espera
del modelo aumentó con sesiones independientes. La causa de la mayor latencia
con sesión compartida queda por medir, incluida la posible espera por bloqueos
SQL. Los valores corresponden a un entorno local y una sola consulta.

## Referencias

- [Contrato de recuperación V1](../contratos/recuperacion-semantica-v1.md).
- [Backend y configuración](../../backend/README.md#búsqueda-semántica-protegida-optativa).
- [Frontend integrado](../../frontend/README.md#búsqueda-semántica-integrada).
- [Fuentes y reproducción](../../ml/sources/README.md).
