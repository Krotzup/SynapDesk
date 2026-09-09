# Contribuir a SynapDesk

Este documento define las reglas mínimas de colaboración para el equipo de SynapDesk.

## Idioma

La documentación, las historias, los criterios de aceptación y las descripciones de los pull requests se redactan en español. Los nombres técnicos del código se mantienen en inglés cuando sea la convención del lenguaje, framework o herramienta utilizada.

## Flujo de trabajo

1. Actualizar la rama `main` local.
2. Crear una rama corta para una sola tarea.
3. Implementar y verificar el cambio.
4. Crear un pull request hacia `main`.
5. Solicitar la revisión de al menos un integrante.
6. Corregir observaciones y comprobar la integración continua.
7. Integrar mediante *squash merge*.

No se realizan cambios directos sobre `main`.

## Nombres de ramas

Formato:

```text
<tipo>/<descripcion-breve-en-espanol>
```

Tipos permitidos:

- `funcionalidad`: nueva capacidad del producto;
- `correccion`: solución de un defecto;
- `pruebas`: incorporación o ajuste de pruebas;
- `documentacion`: cambios documentales;
- `configuracion`: infraestructura, herramientas o configuración;
- `refactorizacion`: mejora interna sin alterar comportamiento.

Ejemplos:

```text
funcionalidad/crear-ticket
correccion/validar-rol-agente
pruebas/autenticacion
documentacion/contrato-modelo-ml
configuracion/estructura-inicial
```

## Commits

Los mensajes deben ser breves, imperativos y estar en español:

```text
Agrega estructura inicial del backend
Documenta contrato de inferencia ML
Corrige validacion del estado del ticket
```

No se deben utilizar mensajes imprecisos como `cambios`, `arreglos` o `update`.

## Pull requests

Cada pull request debe:

- resolver una tarea concreta;
- explicar qué cambia y por qué;
- incluir pruebas cuando corresponda;
- documentar migraciones o variables nuevas;
- evitar cambios ajenos a la tarea;
- contar con al menos una aprobación.

## Definición de Terminado

Una tarea se considera terminada cuando, según corresponda:

- cumple sus criterios de aceptación;
- incluye validaciones y manejo de errores;
- contiene pruebas automatizadas;
- no expone secretos ni datos sensibles;
- actualiza documentación y migraciones;
- supera las comprobaciones automáticas;
- fue revisada por otro integrante;
- puede ejecutarse en el entorno acordado.
