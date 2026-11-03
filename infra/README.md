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

### Backend básico y herramientas de persistencia

Completar las variables PostgreSQL del entorno elegido con credenciales locales privadas. Para pruebas, configurar `POSTGRES_TEST_*` en `localhost:5433`, con una base exclusiva distinta de desarrollo, y usar Alembic con `-x base=testing`; consultar el [procedimiento del backend](../backend/README.md). No ejecutar pruebas sobre desarrollo en `5432`.

La plantilla puede cargarse sin configurar autenticación: el par HMAC y las seis cuotas están comentados. El backend básico, `/api/v1/health` y las herramientas de persistencia no construyen estos servicios. `/api/v1/ready` comprueba la conexión a PostgreSQL y requiere que la base configurada esté disponible; copiar el ejemplo no crea bases ni credenciales.

### Configuración adicional antes de utilizar autenticación

Completar y descomentar **juntos** `AUTH_HMAC_CLAVE` y `AUTH_HMAC_ID_CLAVE`. Generar localmente una clave privada CSPRNG de al menos 32 bytes en base64 canónico mediante el comando incluido en [.env.example](../.env.example); mantener su salida fuera de registros, Git y variables `NEXT_PUBLIC_*`. No utilizar los marcadores ni claves ficticias de pruebas como credenciales.

Completar y descomentar las seis variables `AUTH_LIMITE_*` de cuenta e IP: intentos, ventana y bloqueo, todos enteros positivos. No hay cuotas implícitas ni limitación permisiva cuando faltan valores: la construcción del limitador falla. Los umbrales y duraciones requieren calibración; los intentos exitosos también consumen capacidad según la política provisional.

El servicio HMAC rechaza una clave ausente y la configuración rechaza un par HMAC incompleto, marcadores activos o valores inválidos. Se conservan los ejemplos Argon2id y CSRF provisionales. Las listas utilizan JSON: `AUTH_ORIGENES_PERMITIDOS=["http://localhost:3000"]` permite únicamente ese Origin local; `AUTH_PROXIES_AUTORIZADOS=[]` mantiene cerrada la confianza en IP. La integración HTTP y las decisiones pendientes corresponden a AUTH-07; véase la [guía de seguridad](../backend/app/seguridad/README.md).

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
