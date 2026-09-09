# Estrategia de entornos

SynapDesk separa desarrollo, testing y staging para evitar que las pruebas o configuraciones locales afecten datos compartidos.

## Desarrollo

Cada integrante ejecuta localmente PostgreSQL con pgvector mediante el servicio `db`. Los datos se conservan en un volumen de Docker y no se comparten entre computadores.

## Testing

Las pruebas automatizadas utilizarán el servicio `db_test`, una base independiente con credenciales, puerto y almacenamiento propios. Los datos son desechables y no deben reutilizarse como datos de desarrollo.

## Staging

Staging será un entorno compartido para validar la integración del producto antes de la demostración. Utilizará configuración y credenciales independientes, migraciones controladas y datos ficticios o anonimizados.

El proveedor de staging se seleccionará después de medir los requisitos de backend, base de datos, almacenamiento documental y servicios de inteligencia artificial.

## Reglas

- No reutilizar credenciales entre entornos.
- No copiar datos sensibles a testing o staging.
- No ejecutar pruebas automatizadas contra desarrollo o staging.
- No versionar archivos `.env`.
- Mantener `.env.example` actualizado cuando aparezcan variables nuevas.
- Ejecutar cambios de esquema mediante migraciones cuando el backend las incorpore.
