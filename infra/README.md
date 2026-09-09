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

## Base de datos de testing

El servicio `db_test` proporciona una base aislada para las futuras pruebas automatizadas. Utiliza el puerto local `5433` y almacenamiento temporal, por lo que sus datos no se conservan al eliminar o reiniciar el contenedor.

Iniciar únicamente la base de testing:

```bash
docker compose --profile testing up -d db_test
```

Comprobar su estado:

```bash
docker compose --profile testing ps
```

Verificar pgvector:

```bash
docker compose exec db_test psql -U synapdesk_test -d synapdesk_test -c "SELECT extversion FROM pg_extension WHERE extname = 'vector';"
```

Detener y eliminar el contenedor de testing:

```bash
docker compose --profile testing down
```

Este comando también puede detener servicios de desarrollo pertenecientes al mismo proyecto si están ejecutándose. Para detener exclusivamente testing se puede utilizar:

```bash
docker compose stop db_test
docker compose rm -f db_test
```

La base de testing nunca debe utilizar información importante ni datos personales.

## Separación de entornos

| Entorno | Servicio | Puerto local | Persistencia |
| --- | --- | ---: | --- |
| Desarrollo | `db` | `5432` | Volumen `datos_postgresql` |
| Testing | `db_test` | `5433` | Almacenamiento temporal |
| Staging | Por definir | No expuesto públicamente | Base dedicada |

## Diagnóstico

Consultar el estado:

```bash
docker compose ps
```

Consultar los registros de PostgreSQL:

```bash
docker compose logs db
```
