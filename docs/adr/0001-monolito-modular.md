# ADR-0001: Adoptar un monolito modular

- Estado: aceptada
- Fecha: 2026-09-09
- Responsables: equipo SynapDesk

## Contexto

SynapDesk debe integrar autenticación, tickets, documentos, Machine Learning, recuperación semántica, RAG, LLM y validación humana. El equipo está compuesto por tres integrantes y debe entregar un producto funcional durante un semestre.

## Alternativas consideradas

1. Monolito sin límites internos explícitos.
2. Monolito modular.
3. Arquitectura de microservicios.

## Decisión

Implementar el backend como un monolito modular desplegado inicialmente como una sola aplicación FastAPI.

## Razones

- Reduce la complejidad operacional.
- Facilita las pruebas y transacciones.
- Permite una integración progresiva.
- Mantiene límites internos claros entre dominios.
- Es alcanzable por un equipo de tres integrantes.

## Consecuencias

### Positivas

- Un solo backend que desarrollar, probar y desplegar.
- Comunicación interna simple.
- Menor costo de infraestructura.

### Negativas o riesgos

- Los límites modulares deben vigilarse mediante revisión de código.
- Un acoplamiento descuidado podría convertirlo en un monolito desorganizado.

## Condiciones para revisar la decisión

Se reconsiderará únicamente si aparecen necesidades comprobables de escalamiento o aislamiento que no puedan resolverse dentro del monolito modular.
