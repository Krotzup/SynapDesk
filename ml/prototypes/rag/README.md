# Piloto RAG de SynapDesk

Prueba local con Python 3.9 o posterior, sin paquetes adicionales, GPU ni conexión. Ejecuta los comandos desde la raíz del repositorio.

```text
python ml/prototypes/rag/piloto_rag.py
python -m unittest tests.ml.test_piloto_rag -v
```

El primer comando debe informar `10/10 casos correctos` y salir con código 0. La suite de `unittest` también se ejecuta en CI.

## Casos y resultados esperados

| Caso | Ticket sintético | Contexto preparado | Resultado esperado |
|---|---|---|---|
| R01 | El portal abre por IP, pero falla por nombre. | P01, DNS. | Borrador que compruebe la resolución. Cita P01. |
| R02 | Revisar parámetros de una IP fija en Windows. | P02, configuración IP. | Borrador que consulte la configuración y mantenga intacta la concesión. Cita P02. |
| R03 | Verificar acceso TCP 443 desde Windows. | P05, Test-NetConnection. | Borrador que proponga comprobar el puerto. Cita P05. |
| R04 | Registrar la versión de WSL antes de un ensayo. | P12, comandos WSL. | Borrador que consulte la versión. Cita P12. |
| R05 | Docker no puede publicar el puerto 8080. | P14, puertos de Docker, y T01, caso resuelto ficticio. | Identificar el ocupante y usar T01 como antecedente. Citas P14 y T01. |
| R06 | Recuperar un archivo eliminado. | Vacío. | Información insuficiente. Se omite el generador. |
| R07 | Averiguar la política de retención de correo. | P01, DNS. | Información insuficiente. El fragmento es irrelevante. |
| R08 | Confirmar si se puede renovar DHCP durante el turno. | Dos políticas ficticias incompatibles. | Información insuficiente. Se requiere una fuente autorizada que resuelva el conflicto. |
| R09 | El portal funciona por IP, pero falla por nombre. | P01 y un fragmento ficticio con una instrucción ajena. | Borrador de diagnóstico DNS. Solo cita P01. |
| R10 | Comprobar qué ocupa el puerto 8080. | P14. El simulador devuelve una cita inventada. | Salida inválida. Se descarta el borrador. |

Las referencias Pxx corresponden a una revisión fija del manifiesto de recuperación semántica. Los textos del script son resúmenes sintéticos. Sus identificadores de fragmento pertenecen al ensayo. T01 y S01–S03 son materiales ficticios. [Manifiesto del PR #32](https://github.com/Krotzup/SynapDesk/blob/ac9f02516becb8f1c4a02c149131835b8e8a6b2e/ml/sources/procedimientos_oficiales.json)

## Alcance de la verificación

Las respuestas predefinidas permiten comprobar la omisión del generador cuando el contexto está vacío, la aceptación de citas del contexto, el rechazo de citas inventadas y las tres decisiones de revisión sin modificar el borrador original. El ensayo también rechaza una edición vacía. Con R05 y R09 se comprueba el texto completo del borrador y la cita de cada paso, además de la lista de fuentes. Los casos R07–R09 fijan expectativas para una futura evaluación con un modelo. El simulador reproduce esas salidas mediante respuestas fijas.

Para evaluar un LLM real, conservar los tickets y resultados esperados, ocultar las expectativas al generador y revisar manualmente el respaldo de cada paso, la utilidad y la abstención. Registrar versión del modelo, versión del prompt, IDs de los fragmentos y latencia. Para evaluar la recuperación real, alimentar el mismo conjunto de tickets al servicio del #32 y registrar qué fuentes recupera. La autenticación, el proxy y la persistencia quedan para la prueba integrada.
