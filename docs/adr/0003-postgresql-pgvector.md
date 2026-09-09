# ADR-0003: Utilizar PostgreSQL con pgvector

- Estado: aceptada
- Fecha: 2026-09-09
- Responsables: equipo SynapDesk

## Contexto

SynapDesk necesita almacenar datos relacionales y embeddings utilizados para recuperar documentos y tickets similares.

## Alternativas consideradas

1. PostgreSQL más una base vectorial independiente.
2. PostgreSQL con la extensión pgvector.
3. Persistencias separadas para cada módulo.

## Decisión

Utilizar PostgreSQL para la persistencia relacional y pgvector para los vectores durante el alcance semestral.

## Razones

- Reduce la cantidad de servicios que administrar.
- Permite relacionar vectores con tickets, documentos y metadatos.
- Simplifica desarrollo, pruebas y staging.
- Cubre el volumen esperado para el MVP.

## Consecuencias

### Positivas

- Una sola tecnología principal de persistencia.
- Consultas con filtros relacionales y similitud vectorial.
- Menor costo operacional.

### Negativas o riesgos

- El modelo de embeddings debe definir previamente la dimensión vectorial.
- Los índices vectoriales deberán evaluarse con datos representativos.

## Condiciones para revisar la decisión

Se reconsiderará si las mediciones demuestran que el volumen, la latencia o las necesidades de búsqueda exceden las capacidades razonables de PostgreSQL con pgvector.
