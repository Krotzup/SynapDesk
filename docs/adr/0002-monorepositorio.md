# ADR-0002: Utilizar un monorepositorio

- Estado: aceptada
- Fecha: 2026-09-09
- Responsables: equipo SynapDesk

## Contexto

Frontend, backend y Machine Learning deben evolucionar mediante contratos compartidos y entregas integrables durante el semestre.

## Alternativas consideradas

1. Repositorio independiente para cada componente.
2. Un único repositorio para todos los componentes.

## Decisión

Mantener frontend, backend, Machine Learning, infraestructura y documentación en el repositorio `SynapDesk`.

## Razones

- Simplifica la coordinación de tres integrantes.
- Permite modificar contratos y consumidores en un mismo cambio.
- Centraliza documentación e instrucciones de ejecución.
- Facilita la entrega académica del proyecto completo.

## Consecuencias

### Positivas

- Visión integral del producto.
- Menor fragmentación de configuración y permisos.

### Negativas o riesgos

- Las automatizaciones deberán ejecutar solamente las comprobaciones necesarias para cada componente.
- Será necesario conservar responsables y límites claros por carpeta.

## Condiciones para revisar la decisión

Se reconsiderará si el repositorio crece hasta dificultar significativamente los permisos, las automatizaciones o los ciclos de entrega independientes.
