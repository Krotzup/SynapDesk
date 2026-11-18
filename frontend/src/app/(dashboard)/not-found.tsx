import { NotFoundState } from "@/components/layout/NotFoundState";

// Página "no encontrado" del panel: se muestra con el menú lateral y la cabecera. La usan las
// direcciones desconocidas (ver [...rest]/page.tsx) y cualquier notFound() del panel que no tenga
// una página propia más específica.
export default function DashboardNotFound() {
  return (
    <NotFoundState
      title="Página no encontrada"
      message="La dirección que buscas no existe o cambió de lugar."
      primaryLink={{ href: "/inicio", label: "Ir al inicio" }}
      secondaryLink={{ href: "/tickets", label: "Ver tickets" }}
    />
  );
}
