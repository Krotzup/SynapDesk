import { notFound } from "next/navigation";

// Toda dirección que no corresponde a otra ruta llega aquí, para que su página "no encontrado"
// se muestre dentro del panel ((dashboard)/not-found.tsx) y no en la página raíz sin menú.
// Las rutas existentes (/login, /api/v1/*, /tickets/...) tienen prioridad sobre esta.
export default function UnknownDashboardRoute() {
  notFound();
}
