# Diseño visual del frontend

Este documento define los criterios visuales, de tipografía e interacción que guiarán
el desarrollo de los mockups y la implementación de la interfaz de SynapDesk.

Debe consultarse antes de diseñar cualquier pantalla o componente nuevo.

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

Evitar sombras pesadas. Preferir bordes de 1px sobre `box-shadow` pronunciadas.

### Texto

| Uso | Color | Valor |
|---|---|---|
| Títulos y encabezados | Gris muy oscuro | `#0F172A` |
| Texto de cuerpo y descripción | Gris medio | `#475569` |
| Metadatos, fechas y etiquetas | Gris claro | `#94A3B8` |

Evitar el negro puro (`#000000`) en cualquier texto.

### Color de marca y acciones

| Uso | Color | Valor |
|---|---|---|
| Botones primarios, enlaces y navegación activa | Azul corporativo | `#2563EB` |
| Estados hover del azul | Azul oscuro | `#1D4ED8` |

### Color identificador de IA

El violeta/índigo está reservado de forma exclusiva para todo elemento que provenga
del modelo de lenguaje o de Machine Learning.

| Uso | Color | Valor |
|---|---|---|
| Bordes de contenedores de IA | Violeta suave | `#818CF8` |
| Badges, íconos e indicadores de IA | Índigo | `#6366F1` |
| Fondo sutil de secciones de IA | Índigo muy claro | `#EEF2FF` |

No usar este color para elementos que no sean de origen automático o de IA.

### Estados de prioridad (badges)

| Prioridad | Color | Valor |
|---|---|---|
| Baja | Verde | `#16A34A` |
| Media | Amarillo/Naranja | `#D97706` |
| Alta | Rojo | `#DC2626` |
| Crítica | Rojo | `#DC2626` |

---

## Tipografía

### Fuente principal

**Inter** (primera opción) o **Roboto** (alternativa).
Ambas priorizan la legibilidad en pantallas de alta densidad y bloques de texto largo,
lo que es relevante para mostrar manuales técnicos y respuestas generadas por el LLM.

En Next.js se carga mediante `next/font/google` para evitar layout shift.

### Jerarquía de tamaños

| Elemento | Tamaño | Peso | Interlineado |
|---|---|---|---|
| Títulos de sección | 18–20px | Semibold (600) | — |
| Título de ticket / Encabezados de panel | 15–16px | Medium (500) | — |
| Texto de cuerpo y descripción | 14px | Regular (400) | 1.5 |
| Metadatos, fechas y etiquetas | 12–13px | Regular (400) | — |

---

## Módulo de IA: reglas de interacción

### Diferenciación visual obligatoria

Todo contenido generado automáticamente por el LLM o el modelo de Machine Learning
debe estar dentro de un contenedor con:

- Borde sutil en `#818CF8`
- Fondo `#EEF2FF`
- Ícono distintivo (por definir en implementación)
- Etiqueta visible: **"Sugerencia de IA"**

Esto aplica a: categoría predicha, prioridad sugerida y respuesta redactada por el LLM.

### Visualización de fuentes RAG

Cada fuente recuperada por el sistema RAG se muestra como un chip o tarjeta colapsable
al pie de la respuesta generada.

Formato del chip:

```
[Manual_Servidores_v2.pdf — Pág. 14]
```

Al hacer hover o clic, se despliega el fragmento exacto de texto que el LLM usó como contexto.

### Acciones de validación humana (Human-in-the-loop)

La sección de revisión tiene tres acciones con jerarquía visual clara:

| Acción | Tipo de botón | Color |
|---|---|---|
| Aceptar y enviar | Primario | Azul `#2563EB` |
| Editar | Secundario con borde | Gris neutro |
| Descartar / Reintentar | Terciario o texto | Gris sutil o rojo suave |

Al presionar **Editar**, se abre un área de texto editable con la respuesta pre-completada.
El contenido original de la recomendación no se sobreescribe: se guarda la versión modificada por separado.

---

## Layout y adaptabilidad

### Enfoque desktop-first

El diseño prioriza monitores de agentes de soporte:

- Resolución mínima de referencia: **1366 × 768**
- Resolución óptima: **1920 × 1080**

### Estructura de columnas (pantalla de ticket)

La vista de detalle de un ticket usa un layout de 2 a 3 columnas:

| Columna | Contenido |
|---|---|
| Izquierda | Lista de tickets o navegación contextual |
| Centro | Detalle del ticket: título, descripción, metadatos, predicciones ML |
| Derecha | Asistente IA: respuesta del LLM, fuentes RAG y acciones de validación |

### Adaptabilidad en pantallas pequeñas

En laptops o resoluciones menores a 1280px, la columna del Asistente IA
se colapsa en un panel lateral deslizable (Drawer) para conservar el espacio
de lectura del contenido del ticket.

El Drawer se abre mediante un botón fijo o una pestaña visible en el borde derecho.

---

## Pantallas a cubrir con mockups

En orden de prioridad:

1. **Login** — pantalla de acceso al sistema
2. **Listado de tickets** — vista principal del agente
3. **Detalle de ticket** — vista central con predicciones ML, respuesta LLM, fuentes RAG y validación
4. **Búsqueda semántica** — ingreso de consulta y visualización de resultados con scores
5. **Gestión de documentos** — carga y listado de documentación técnica
6. **Panel de métricas** — resumen de resultados
7. **Administración de usuarios** — solo para rol admin

---

## Decisiones pendientes

- Ícono y nombre exacto para el indicador de IA en los contenedores de sugerencias
- Comportamiento del Drawer en tablet (¿colapsa igual que en laptop?)
- Definición visual de estados de procesamiento de documentos (pending, processing, processed, failed)
- Indicador de confianza del modelo ML: ¿porcentaje, barra de progreso o badge?
- Modo oscuro: no está en el alcance inicial, pero no debe bloquearse en la implementación
