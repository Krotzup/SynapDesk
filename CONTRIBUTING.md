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

### Sincronización con `main`

Cada nueva rama de trabajo debe crearse a partir de una copia local actualizada de `main`.

Después de que un Pull Request sea aprobado y fusionado en `main`, cada integrante debe actualizar su rama `main` local antes de comenzar una nueva tarea:

```bash
git checkout main
git pull origin main
```

Una vez actualizado `main`, las nuevas ramas de trabajo deben crearse desde esa versión:

```bash
git checkout -b <tipo>/<descripcion-breve-en-espanol>
```

No se deben crear nuevas ramas a partir de una rama anterior ya fusionada, cerrada o desactualizada.

#### Ramas de trabajo que ya están en desarrollo

Si `main` recibe nuevos cambios mientras una rama de trabajo continúa activa, **no se deben incorporar automáticamente esos cambios mediante un merge**.

Primero se debe actualizar la referencia del repositorio remoto:

```bash
git fetch origin
```

Luego se debe comprobar si la rama activa quedó detrás de `main` y si los nuevos cambios afectan archivos, contratos o componentes relacionados con el trabajo en curso.

La incorporación de cambios recientes de `main` a una rama activa debe realizarse solamente cuando sea necesaria y después de revisar posibles conflictos o impactos sobre el trabajo existente.

No se debe eliminar, sobrescribir ni reemplazar trabajo válido de la rama activa únicamente para igualarla con `main`.

### Integración de cambios en `main`

Las ramas de trabajo **no deben fusionarse directamente en `main` desde el entorno local**.

Todo cambio destinado a `main` debe seguir este flujo:

1. trabajar en una rama independiente;
2. guardar y publicar los cambios mediante commits y `push`;
3. crear un Pull Request hacia `main`;
4. solicitar la revisión de al menos otro integrante del equipo;
5. corregir los hallazgos encontrados durante la revisión;
6. aprobar el Pull Request;
7. realizar el merge en GitHub únicamente después de la aprobación;
8. actualizar posteriormente las copias locales de `main`.

No se debe utilizar:

```bash
git checkout main
git merge <rama-de-trabajo>
```

como mecanismo normal de integración del proyecto.

Tampoco se debe utilizar `git push --force`, `git reset --hard` ni reescribir el historial compartido para resolver una sincronización.

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
