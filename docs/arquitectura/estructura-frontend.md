# Estructura del frontend

Aplicación web de SynapDesk basada en Next.js 16 con App Router, React 19, TypeScript y Tailwind CSS.

## Estructura de carpetas

```text
frontend/
├── src/
│   ├── app/                                  ← App Router de Next.js (rutas = carpetas)
│   │   │
│   │   ├── (auth)/                           ← Grupo de rutas públicas, sin sesión requerida
│   │   │   │                                    Layout centrado, sin sidebar ni header
│   │   │   ├── layout.tsx                    ← Layout de pantalla completa centrado
│   │   │   └── login/
│   │   │       └── page.tsx                  ← /login — formulario de inicio de sesión
│   │   │
│   │   ├── (dashboard)/                      ← Grupo de rutas protegidas, requieren sesión
│   │   │   │                                    Layout con sidebar y header
│   │   │   ├── layout.tsx                    ← Layout del dashboard (sidebar + header + contenido)
│   │   │   │
│   │   │   ├── tickets/
│   │   │   │   ├── page.tsx                  ← /tickets — listado de todos los tickets
│   │   │   │   │                                Filtros por estado, prioridad y área
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx              ← /tickets/:id — detalle de un ticket
│   │   │   │                                    Muestra clasificación automática (ML),
│   │   │   │                                    recomendación del LLM con fuentes citadas
│   │   │   │                                    e interfaz Human-in-the-loop
│   │   │   │                                    (aceptar / modificar / rechazar)
│   │   │   │
│   │   │   ├── documentos/
│   │   │   │   └── page.tsx                  ← /documentos — base de conocimiento
│   │   │   │                                    Subir, listar y eliminar documentos técnicos
│   │   │   │                                    (manuales, procedimientos, soluciones)
│   │   │   │                                    que alimentan el RAG para recomendaciones
│   │   │   │
│   │   │   ├── busqueda/
│   │   │   │   └── page.tsx                  ← /busqueda — búsqueda semántica
│   │   │   │                                    El agente escribe una consulta en lenguaje
│   │   │   │                                    natural y obtiene documentos relevantes
│   │   │   │                                    ordenados por similitud semántica
│   │   │   │
│   │   │   ├── metricas/
│   │   │   │   └── page.tsx                  ← /metricas — panel de resultados
│   │   │   │                                    Total de tickets, tickets resueltos,
│   │   │   │                                    tiempo promedio de resolución,
│   │   │   │                                    recomendaciones aceptadas / modificadas /
│   │   │   │                                    rechazadas
│   │   │   │
│   │   │   └── admin/
│   │   │       └── page.tsx                  ← /admin — gestión de usuarios y roles
│   │   │                                        Listar usuarios, cambiar roles
│   │   │                                        (admin / agente), dar de baja
│   │   │                                        Solo accesible para rol admin
│   │   │
│   │   ├── layout.tsx                        ← Layout raíz (fuentes, metadata global, html/body)
│   │   ├── page.tsx                          ← / — redirige a /login o /tickets según sesión
│   │   └── globals.css                       ← Estilos globales y configuración base de Tailwind
│   │
│   ├── components/                           ← Componentes React reutilizables
│   │   ├── ui/                               ← Componentes genéricos sin lógica de negocio
│   │   │                                        Button, Input, Modal, Badge, Spinner,
│   │   │                                        Card, Table, Pagination, Alert, etc.
│   │   └── layout/                           ← Componentes estructurales de la app
│   │                                            Header, Sidebar, Footer, NavItem
│   │
│   ├── lib/                                  ← Utilidades y configuración técnica
│   │   └── api.ts                            ← Cliente HTTP hacia el backend
│   │                                            Centraliza base URL, headers, manejo de
│   │                                            errores y métodos GET/POST/PUT/PATCH/DELETE
│   │
│   ├── hooks/                                ← Custom hooks de React
│   │                                            useTickets, useAuth, usePagination,
│   │                                            useSearch, useDocuments, etc.
│   │
│   ├── types/                                ← Tipos e interfaces TypeScript
│   │   └── index.ts                          ← User, Role, Ticket, TicketStatus,
│   │                                            TicketPriority, Recommendation,
│   │                                            RecommendationSource, RecommendationStatus,
│   │                                            Document, SearchResult, Metrics, ApiError
│   │
│   └── services/                             ← Llamadas a la API del backend organizadas por entidad
│       ├── tickets.ts                        ← getAll, getById, create, update, delete
│       ├── users.ts                          ← getAll, getById, update, delete
│       ├── documents.ts                      ← getAll, getById, delete
│       ├── search.ts                         ← semantic(query)
│       ├── metrics.ts                        ← get()
│       └── recommendations.ts               ← getByTicket, accept, reject, modify
│
├── public/                                   ← Archivos estáticos (imágenes, íconos, fuentes)
│
├── .env.local                                ← Variables de entorno locales (no se versiona)
├── .prettierrc                               ← Reglas de formateo (LF, 2 espacios, 100 cols)
├── .prettierignore                           ← Archivos excluidos de Prettier
├── eslint.config.mjs                         ← Reglas de ESLint integradas con Prettier
├── next.config.ts                            ← Configuración de Next.js
├── postcss.config.mjs                        ← Configuración de PostCSS para Tailwind
├── tsconfig.json                             ← Configuración de TypeScript
├── package.json                              ← Dependencias y scripts (dev, build, lint, format)
└── README.md                                 ← Instrucciones de instalación y desarrollo
```

## Variables de entorno

Las variables del frontend se definen en `frontend/.env.local` (no se versiona).
Están documentadas en `.env.example` en la raíz del repositorio.

| Variable | Descripción | Ejemplo |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | URL base del backend FastAPI | `http://localhost:8000` |

El prefijo `NEXT_PUBLIC_` es obligatorio para que Next.js exponga la variable al navegador.
Las variables sin ese prefijo solo están disponibles en el servidor.

## Grupos de rutas (paréntesis)

Los grupos `(auth)` y `(dashboard)` son una feature de Next.js App Router que agrupa rutas
sin afectar la URL. Permiten tener layouts distintos:

- `(auth)` → pantalla centrada, sin navegación, para usuarios sin sesión
- `(dashboard)` → sidebar + header, para usuarios autenticados

## Convenciones

- Nomenclatura de carpetas y archivos en inglés (convención de Next.js)
- Nombres de variables, funciones y tipos en inglés
- Commits, PRs y documentación en español
- Formateo automático con Prettier al correr `npm run format`
- Verificación con ESLint al correr `npm run lint`
