# Frontend

Aplicación web de SynapDesk basada en Next.js y React.

## Stack

- Next.js 16 (App Router)
- React 19
- TypeScript
- Tailwind CSS

## Requisitos

- Node.js 20+
- npm

## Instalación

```bash
cd frontend
npm install
```

## Variables de entorno

Copiá el archivo de ejemplo y completá los valores:

```bash
cp ../.env.example .env.local
```

Ver `.env.example` en la raíz del proyecto para la lista completa de variables necesarias.

## Desarrollo local

```bash
npm run dev
```

La aplicación estará disponible en [http://localhost:3000](http://localhost:3000).

## Comandos disponibles

| Comando         | Descripción             |
| --------------- | ----------------------- |
| `npm run dev`   | Servidor de desarrollo  |
| `npm run build` | Build de producción     |
| `npm run start` | Servidor de producción  |
| `npm run lint`  | Verificación de linting |
