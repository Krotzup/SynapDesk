# Procedencia y licencia del dataset de tickets

## Fuente externa

El insumo externo identificado para este proyecto es el archivo
[`aa_dataset-tickets-multi-lang-5-2-50-version.csv`](https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets/blob/main/aa_dataset-tickets-multi-lang-5-2-50-version.csv)
del dataset [`Tobi-Bueck/customer-support-tickets`](https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets).

| Campo | Valor verificado |
| --- | --- |
| Autor/publicador | Tobi-Bueck |
| Repositorio | `Tobi-Bueck/customer-support-tickets` |
| Archivo | `aa_dataset-tickets-multi-lang-5-2-50-version.csv` |
| Rama | `main` |
| Revisión visible en la página del archivo | `255c10d` (abreviada) |
| Tamaño informado | 26 MB |
| SHA-256 del archivo externo | `f187c090e59581c2bbf3aa1377c8db4dd647464ecf2ae51bf8966e42e0ed6bc0` |
| DOI del dataset | [`10.57967/hf/6184`](https://doi.org/10.57967/hf/6184) |
| Licencia declarada | [Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)](https://creativecommons.org/licenses/by-nc/4.0/) |

La licencia permite compartir y adaptar el material con atribución, enlace a la
licencia e indicación de los cambios, siempre que el uso no sea comercial. No
debe sugerirse que el autor original respalda SynapDesk ni imponer restricciones
adicionales que contradigan la licencia. La licencia del dataset es independiente
de la licencia que el equipo defina para el código del proyecto y no reemplaza la
revisión de privacidad o de otros derechos aplicables al contenido de los tickets.

## Cadena local de transformación

Los hashes siguientes identifican artefactos diferentes; no deben usarse como si
correspondieran al mismo archivo.

| Etapa | Identidad y alcance |
| --- | --- |
| Fuente externa | Archivo anterior, SHA-256 `f187c090e59581c2bbf3aa1377c8db4dd647464ecf2ae51bf8966e42e0ed6bc0`. |
| Original local en español | `tickets_esp.csv`, 2.239 registros y 13 columnas, SHA-256 `ade38dba719f54bfd06d3fcd12a4c6ff031887eca5545a98c74fac97b10db11a`. Es una selección/adaptación local de la fuente externa, no una copia byte a byte. |
| Entrenamiento V2 | `tickets_esp_entrenamiento_v2.csv`, 2.239 registros, SHA-256 `a3792862678c009ca66dad41aeb3e1fbc0a55d4213fd3c39e5cd2e6586e6740a`. Conserva los textos del original local y aplica 143 decisiones confirmadas de prioridad, de las cuales 62 cambian la etiqueta. |

Según América Figueroa, algunos tickets utilizados ya estaban en español y otros
fueron traducidos para este proyecto. La ficha actual de Hugging Face declara
inglés y alemán como idiomas del dataset. No se conserva todavía una relación por
registro que distinga cuáles ya estaban en español, cuáles fueron traducidos, ni
el método o la fecha de cada traducción. Esta diferencia queda documentada como
una limitación de reproducibilidad; no se infiere ni se inventa ese historial.

El original local usa las columnas `indice_original`, `subject`, `body`, `answer`,
`type`, `queue`, `priority`, `business_type`, `tag_1`, `tag_2`, `tag_3`, `language`
y `origen`. La V2 solo cambia prioridades mediante las anotaciones versionadas;
no elimina palabras de urgencia ni reescribe los textos.

## Pendientes de reproducibilidad y distribución

Para reconstruir exactamente `tickets_esp.csv` desde el archivo externo aún se
necesita registrar:

- la correspondencia de cada registro local con su registro de origen;
- el criterio de selección de los 2.239 tickets;
- qué registros fueron traducidos y con qué método;
- la transformación y el mapeo de columnas aplicados;
- una referencia inmutable completa del archivo externo, además de la revisión
  abreviada visible y su SHA-256.

Por esta razón, el dataset local y sus derivados permanecen fuera de Git. Si se
distribuyen por otro medio, deben acompañarse de esta atribución, la licencia
CC BY-NC 4.0, una indicación de las modificaciones y la revisión de datos
sensibles correspondiente. No deben destinarse a uso comercial bajo esta
licencia.

Texto sugerido de atribución:

> Dataset derivado de “customer-support-tickets” de Tobi-Bueck, archivo
> `aa_dataset-tickets-multi-lang-5-2-50-version.csv`, DOI 10.57967/hf/6184,
> bajo CC BY-NC 4.0. SynapDesk seleccionó registros, conservó o adaptó contenido
> al español y revisó etiquetas de prioridad. Las modificaciones no implican el
> respaldo del autor original.
