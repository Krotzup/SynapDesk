# Diseño visual del frontend

Este documento define los criterios visuales, de tipografía e interacción que guiarán
el desarrollo de los mockups y la implementación de la interfaz de SynapDesk.

Debe consultarse antes de diseñar cualquier pantalla o componente nuevo.

**El mockup aprobado tiene precedencia sobre cualquier criterio de este documento.**
Ante cualquier contradicción, el mockup gana.

---

## Objetivo

Construir una interfaz limpia, corporativa y moderna orientada a agentes de soporte TI.
El estilo de referencia es el de plataformas SaaS técnicas como Vercel o Jira Service Management:
espacio en blanco generoso, bordes sutiles y jerarquía visual clara.

La interfaz debe transmitir confianza y precisión, dado que los agentes toman decisiones
a partir de sugerencias generadas por inteligencia artificial.

---

## Paleta de colores

### Fondo y superficies

| Uso | Color | Valor |
|---|---|---|
| Fondo general de la app | Gris neutro claro | `#F8FAFC` |
| Tarjetas, paneles e insumos | Blanco puro | `#FFFFFF` |
| Bordes y separadores | Gris muy sutil | `#E2E8F0` |
| Fondo de adjuntos y elementos secundarios | Gris suave | `#F1F5F9` |

Evitar sombras pesadas. Preferir bordes de 1px sobre `box-shadow` pronunciadas.

### Barra lateral (Sidebar)

| Uso | Color | Valor |
|---|---|---|
| Fondo del sidebar | Gris oscuro noche | `#0F172A` |
| Texto de ítems inactivos | Gris plata | `#94A3B8` |
| Ícono y texto del ítem activo | Cian vivo | `#38BDF8` |
| Fondo del ítem activo | Gris oscuro medio | `#1E293B` |

### Texto

| Uso | Color | Valor |
|---|---|---|
| Títulos y encabezados | Gris muy oscuro | `#0F172A` |
| Texto de cuerpo y descripción | Gris medio | `#334155` |
| Metadatos, fechas y etiquetas | Gris | `#475569` |
| Texto secundario y placeholders | Gris plata | `#94A3B8` |

Evitar el negro puro (`#000000`) en cualquier texto.

### Color de marca y acciones

| Uso | Color | Valor |
|---|---|---|
| Botones primarios, enlaces y navegación activa | Azul corporativo | `#2563EB` |
| ID de ticket y elementos de acción destacados | Azul corporativo | `#2563EB` |
| Estado hover del azul | Azul oscuro | `#1D4ED8` |

### Color identificador de IA

El violeta/índigo está reservado de forma exclusiva para todo elemento que provenga
del modelo de lenguaje o de Machine Learning.

| Uso | Color | Valor |
|---|---|---|
| Fondo del panel del Asistente IA | Violeta pastel | `#EEF2FF` |
| Borde del panel del Asistente IA | Violeta suave | `#818CF8` |
| Título e íconos del Asistente IA | Índigo oscuro | `#4338CA` |
| Fondo de badges de categoría IA | Índigo muy claro | `#E0E7FF` |
| Texto de badges de categoría IA | Índigo oscuro | `#3730A3` |
| Borde de chips de fuentes RAG | Índigo claro | `#C7D2FE` |
| Texto de chips de fuentes RAG | Índigo oscuro | `#4338CA` |
| Avatar / indicador de usuario | Violeta | `#6366F1` |

No usar este color para elementos que no sean de origen automático o de IA.

### Estados de prioridad (badges)

| Prioridad | Fondo badge | Texto badge |
|---|---|---|
| Baja | `#DCFCE7` | `#16A34A` |
| Media | `#FEF9C3` | `#D97706` |
| Alta | `#FEE2E2` | `#991B1B` |
| Crítica | `#FEE2E2` | `#991B1B` |

### Botones de acción Human-in-the-loop

| Acción | Fondo | Borde | Texto | Ícono |
|---|---|---|---|---|
| Aceptar y Resolver | `#16A3A1` (verde/teal) | — | `#FFFFFF` | ✓ |
| Editar | `#FFFFFF` | `#CBD5E1` | `#0F172A` | ✏️ |
| Descartar | `#FFFFFF` | — | `#EF4444` | 🗑️ |
| Reintentar | `#FFFFFF` | `#E2E8F0` | `#475569` | — |

---

## Tipografía

### Fuente principal

**Inter** — fuente sans-serif de alta legibilidad en interfaces técnicas.
Es la fuente que más se aproxima al estilo visual del mockup aprobado.

Se reemplaza Geist (fuente por defecto de `create-next-app`) por Inter
mediante `next/font/google` para evitar layout shift.

### Jerarquía de tamaños

| Elemento | Tamaño | Peso | Interlineado |
|---|---|---|---|
| Títulos de sección | 18–20px | Semibold (600) | — |
| Título de ticket / Encabezados de panel | 15–16px | Medium (500) | — |
| Texto de cuerpo y descripción | 14px | Regular (400) | 1.5 |
| Metadatos, fechas y etiquetas | 12–13px | Regular (400) | — |

---

## Estructura visual de pantallas

### Header (barra superior)

| Elemento | Valor |
|---|---|
| Fondo | `#FFFFFF` |
| Borde inferior | `#E2E8F0` |
| Logo / nombre | `#2563EB` |
| Buscador global | Fondo `#F1F5F9`, placeholder `#94A3B8` |
| Avatar de usuario | Fondo `#6366F1`, texto `#FFFFFF` |
| Nombre de usuario | `#0F172A` |

### Sidebar (barra lateral)

Fondo oscuro `#0F172A` con ítems de navegación.
El ítem activo tiene fondo `#1E293B` e ícono/texto en `#38BDF8`.
Los ítems inactivos usan texto `#94A3B8`.

Sección **Estado** al pie del sidebar con contadores de tickets por estado:
- Todos: badge con número
- Abiertos
- En Proceso
- Resueltos

### Panel central (detalle del ticket)

Tarjeta blanca (`#FFFFFF`) con borde `#E2E8F0`.

Elementos:
- ID del ticket: badge azul `#2563EB`
- Estado: badge de color según estado
- Título: `#0F172A`, Medium (500)
- Descripción: `#334155`, Regular (400)
- Metadatos (Usuario, Fecha, Área): etiquetas `#94A3B8` + valor `#475569`
- Archivo adjunto: fondo `#F1F5F9`, ícono + nombre + tamaño
- Descripción adicional: área de texto con fondo `#F1F5F9`

### Panel derecho (Asistente IA)

Tarjeta con fondo `#EEF2FF` y borde `#818CF8`.

Secciones en orden:
1. Título: ícono 🤖 + "Asistente IA" en `#4338CA`
2. Categoría: badge con fondo `#E0E7FF` y texto `#3730A3`
3. Prioridad estimada: badge de prioridad con ícono de alerta
4. Recomendación generada: texto `#1E293B`, Regular (400)
5. Fuentes consultadas (RAG): chips con borde `#C7D2FE` y texto `#4338CA`
6. Acciones: botones Aceptar / Editar / Descartar en orden vertical

---

## Módulo de IA: reglas de interacción

### Diferenciación visual obligatoria

Todo contenido generado automáticamente por el LLM o el modelo de Machine Learning
debe estar dentro del panel derecho con fondo `#EEF2FF` y borde `#818CF8`.
Incluye título con ícono 🤖 y etiqueta visible.

### Visualización de fuentes RAG

Cada fuente recuperada se muestra como chip al pie de la recomendación:

```
📑 Manual_Postgres.pdf
```

Fondo `#FFFFFF`, borde `#C7D2FE`, texto `#4338CA`.
Al hacer clic se despliega el fragmento exacto usado como contexto.

### Acciones de validación humana (Human-in-the-loop)

Cuatro acciones en orden vertical con jerarquía clara:

| Acción | Operación |
|---|---|
| **Aceptar y Resolver** | Registra decisión `accepted` y cierra el flujo |
| **Editar** | Abre área de texto editable pre-completada con la recomendación |
| **Descartar** | Registra decisión `rejected` — no genera nueva recomendación |
| **Reintentar** | Solicita nueva recomendación al LLM — la anterior queda en historial |

El contenido original de la recomendación no se sobreescribe jamás.

---

## Layout y adaptabilidad

### Enfoque desktop-first

- Resolución mínima de referencia: **1366 × 768**
- Resolución óptima: **1920 × 1080**

### Estructura de columnas (pantalla de ticket)

```
┌─────────────┬──────────────────────────────┬───────────────────────┐
│   Sidebar   │     Panel central            │   Panel IA (derecho)  │
│  ~190px     │     flex-1                   │   ~320px              │
│  #0F172A    │     Detalle del ticket       │   #EEF2FF             │
└─────────────┴──────────────────────────────┴───────────────────────┘
```

### Adaptabilidad en pantallas pequeñas

En resoluciones menores a 1280px, el panel del Asistente IA se colapsa
en un Drawer lateral deslizable. Se activa mediante un botón fijo en el borde derecho.

---

## Pantallas a cubrir con mockups

En orden de prioridad:

1. **Login** — pantalla de acceso al sistema
2. **Listado de tickets** — vista principal del agente con filtros por estado
3. **Detalle de ticket** — panel central + Asistente IA + fuentes RAG + validación
4. **Búsqueda semántica** — consulta en lenguaje natural + resultados con score
5. **Gestión de documentos** — carga y listado de documentación técnica
6. **Panel de métricas** — resumen de resultados
7. **Administración de usuarios** — solo para rol admin

---

## Decisiones pendientes

- Ícono definitivo del indicador de IA (actualmente 🤖, puede reemplazarse por SVG)
- Comportamiento del Drawer en tablet
- Visualización de estados de procesamiento de documentos (pending, processing, processed, failed)
- Indicador de confianza del modelo ML: ¿porcentaje, barra de progreso o badge?
- Modo oscuro: no está en el alcance inicial, pero no debe bloquearse en la implementación
- Botón Reintentar: definir si va junto a Descartar o en una sección separada
