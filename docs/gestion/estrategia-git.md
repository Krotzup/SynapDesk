# Estrategia Git

SynapDesk utiliza un flujo basado en una rama principal estable y ramas de trabajo cortas.

## Rama principal

`main` representa el estado integrado y demostrable del proyecto. No se realizan cambios directos sobre ella.

## Ramas de trabajo

Cada tarea utiliza una rama creada desde una versión actualizada de `main`:

```text
funcionalidad/<descripcion>
correccion/<descripcion>
pruebas/<descripcion>
documentacion/<descripcion>
configuracion/<descripcion>
refactorizacion/<descripcion>
```

Las descripciones se escriben en español, con minúsculas y palabras separadas por guiones.

## Integración

1. Crear o asignar una tarea en GitHub Projects.
2. Crear una rama corta asociada a esa tarea.
3. Publicar cambios pequeños y coherentes.
4. Abrir un pull request hacia `main`.
5. Obtener al menos una revisión del equipo.
6. Corregir observaciones y superar comprobaciones automáticas.
7. Integrar mediante *squash merge*.
8. Eliminar la rama integrada.

## Protección recomendada para `main`

- exigir pull request antes de integrar;
- exigir al menos una aprobación;
- invalidar aprobaciones cuando aparezcan cambios nuevos;
- exigir resolución de conversaciones;
- impedir eliminación y actualización forzada;
- exigir comprobaciones automáticas cuando el flujo de CI exista.

## Conflictos

Quien creó el pull request es responsable de actualizar su rama y resolver los conflictos con apoyo del integrante dueño del área afectada.

## Responsabilidad de revisión

- Cambios de frontend: revisión principal de la responsable de frontend.
- Cambios de ML y datos: revisión principal de la responsable de ML/Data.
- Cambios de backend y arquitectura: revisión principal del responsable técnico.
- Cambios de contratos o integración: revisión de las áreas involucradas.
