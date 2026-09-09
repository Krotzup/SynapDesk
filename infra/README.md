# Infraestructura

Configuración reproducible de los servicios requeridos por SynapDesk.

## Requisitos

- Docker Desktop con el motor WSL 2 activo.
- Docker Compose incluido en Docker Desktop.

No es necesario instalar PostgreSQL ni pgvector directamente en Windows.

## Preparación

Desde la raíz del repositorio, crear la configuración local a partir de la plantilla:

```bash
cp .env.example .env
```

La contraseña de `POSTGRES_PASSWORD` debe modificarse en `.env`. Este archivo es local y no se incorpora a Git.

## Iniciar PostgreSQL

```bash
docker compose up -d db
```

Comprobar el estado:

```bash
docker compose ps
```

El servicio debe aparecer como `healthy`.

## Verificar pgvector

```bash
docker compose exec db psql -U synapdesk_app -d synapdesk -c "SELECT extversion FROM pg_extension WHERE extname = 'vector';"
```

En una base creada por primera vez, el script `postgres/init/001-habilitar-pgvector.sql` activa automáticamente la extensión.

## Detener los servicios

```bash
docker compose down
```

Este comando conserva el volumen y los datos. La opción `-v` elimina el volumen y debe utilizarse solamente cuando exista una razón explícita para reiniciar completamente la base local.

## Diagnóstico

Consultar el estado:

```bash
docker compose ps
```

Consultar los registros de PostgreSQL:

```bash
docker compose logs db
```
