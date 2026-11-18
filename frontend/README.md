# Frontend

Aplicación web de SynapDesk basada en Next.js y React.

## Stack

- Next.js 16 (App Router)
- React 19
- TypeScript
- Tailwind CSS

## Requisitos

- Node.js 20 o superior
- npm

## Instalación

```bash
cd frontend
npm install
```

## Variables de entorno

Desde la carpeta `frontend/`, copia el archivo de ejemplo y completa los valores:

```bash
# Desde la raíz del repositorio
cp frontend/.env.example frontend/.env.local

# O desde dentro de frontend/
cp .env.example .env.local
```

Ver `frontend/.env.example` para la lista completa de variables necesarias.

> Las variables de entorno del frontend se configuran dentro de la carpeta `frontend/`,
> no en la raíz del repositorio.

## Desarrollo local

```bash
npm run dev
```

La aplicación estará disponible en [http://localhost:3000](http://localhost:3000).

> El puerto `3000` corresponde al frontend. El backend FastAPI corre en el puerto `8000`.
> No uses `localhost:3000` como URL del backend.

## Búsqueda semántica integrada

La pantalla `/busqueda` realiza la consulta desde el navegador después de
verificar sesión, mediante el servicio y el proxy de mismo origen
`POST /api/v1/search`. No hace POST de búsqueda durante SSR sin cookies/CSRF.
Con datos reales (`NEXT_PUBLIC_USE_MOCKS=false`) el proxy llama a FastAPI; con
mocks se conserva el aviso explícito de datos de ejemplo y similitud simulada.

Configurar exclusivamente en el servidor Next.js:

| Variable                     | Uso                                                                                                                    |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `BACKEND_INTERNAL_URL`       | Origen HTTPS fijo de FastAPI. Nunca se acepta del cliente ni se expone mediante NEXT_PUBLIC.                           |
| `BACKEND_SERVICE_CREDENTIAL` | Credencial privada SEC-01B, de 32 bytes codificados en base64url canónico. Debe coincidir con la política del backend. |
| `SEARCH_PUBLIC_ORIGIN`       | Origen público exacto, coincidente con el permitido por el backend.                                                    |
| `AUTH_COOKIE_PROFILE`        | Perfil obligatorio `local` o `production`. Usar el mismo valor en FastAPI y en Next.js.                                |
| `SEARCH_SESSION_COOKIE_NAME` | Comprobación opcional del nombre. Si se configura, debe coincidir con la cookie de sesión del perfil.                  |

Ejemplo de transporte local: frontend `http://localhost:3000` con perfil `local`,
backend `https://localhost:8000` con certificado de confianza y origen permitido explícito. No mezclar hosts dentro del
flujo de cookies. Los nombres concretos de cookies y el despliegue de autenticación
requieren su configuración acordada; no se aprueban automáticamente propuestas.

La ruta reenvía las cookies de autenticación reservadas, Origin, CSRF, Content-Type y
Sec-Fetch-Site cuando existe. Descarta Authorization y las cabeceras de IP
aportadas por el cliente y agrega su propio bearer SEC-01B. Rechaza destinos/redirecciones
arbitrarios y usa no-store, plazo finito y errores saneados. FastAPI
rechaza cookies ambiguas a partir de la representación original.
No funciona como proxy genérico para otras rutas.

El proxy general atiende `/auth/me` y `/auth/csrf`. La ruta específica de
búsqueda usa el mismo canal SEC-01B que el proxy general y SSR. Conserva su
límite de 8192 bytes y valida Origin. El
plazo común cubre la lectura de la petición y la respuesta. Según P8, tras
`CSRF_INVALID` la próxima acción manual obtiene un token nuevo.

La pantalla diferencia resultados, base vacía e información insuficiente;
muestra extractos, idioma y enlace HTTPS de la fuente cuando existen metadatos.
Conserva el máximo de 1000 caracteres y comunica 422
`QUERY_TOKEN_LIMIT_EXCEEDED` si se superan los 128 tokens del modelo, sin
truncamiento silencioso. Un cambio de sesión descarta resultados en tránsito.

La búsqueda requiere sesión y CSRF válidos. Para habilitarla a usuarios
finales, el transporte de AUTH-07 debe ofrecer login, logout, `/auth/me` y el
bootstrap de CSRF. Los ensayos E2E identifican cuándo simulan el bootstrap y
cuándo usan sesión, CSRF y búsqueda reales.

Ver [recuperación V1](../docs/contratos/recuperacion-semantica-v1.md). Para las
pruebas de contrato y proxy, sin servidor externo ni nuevas librerías de test:

```bash
npm test
```

El comando compila solo los helpers de búsqueda y ejecuta `node:test`. Sus
artefactos quedan excluidos de Git. Completar también `npm run lint` y
`npm run build` al modificar la integración.

## Comandos disponibles

| Comando                   | Descripción                                                             |
| ------------------------- | ----------------------------------------------------------------------- |
| `npm run dev`             | Servidor de desarrollo                                                  |
| `npm run build`           | Build de producción                                                     |
| `npm run start`           | Servidor de producción                                                  |
| `npm run lint`            | Verificación de linting                                                 |
| `npm run format`          | Formatea todo el código                                                 |
| `npm run format:check`    | Verifica formato sin modificar                                          |
| `npm run test:proxy`      | Pruebas proxy/SSR (unos 3 min)                                          |
| `npm run test:unit`       | Pruebas de lógica (`tests/unit`)                                        |
| `npm run test:components` | Pruebas de formularios con jsdom y Testing Library (`tests/components`) |

## Estado de implementación

- [x] Estructura de carpetas y configuración base
- [x] Cliente HTTP hacia el backend (`src/lib/api.ts`)
- [x] Tipos TypeScript del dominio (`src/types/index.ts`)
- [x] Servicios por entidad (`src/services/`)
- [x] Layout del dashboard con Sidebar y Header
- [x] Página de login (estructura base)
- [ ] Autenticación — pendiente de decisión técnica del equipo
- [ ] Protección de rutas — pendiente de definir mecanismo de autenticación
- [ ] Implementación de pantallas funcionales — pendiente de aprobación del contrato frontend-backend

> Los tipos en `src/types/index.ts` y los servicios en `src/services/` son **provisionales**.
> Deben revisarse y ajustarse cuando se apruebe el contrato frontend-backend
> (`docs/contratos/frontend-backend.md`) antes de implementar cada módulo.
