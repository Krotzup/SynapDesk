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

## Comandos disponibles

| Comando                | Descripción                    |
| ---------------------- | ------------------------------ |
| `npm run dev`          | Servidor de desarrollo         |
| `npm run build`        | Build de producción            |
| `npm run start`        | Servidor de producción         |
| `npm run lint`         | Verificación de linting        |
| `npm run format`       | Formatea todo el código        |
| `npm run format:check` | Verifica formato sin modificar |

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
