import { NotFoundState } from "@/components/layout/NotFoundState";

// Respaldo para un 404 que no pase por el panel. Sin menú ni sesión: solo lleva al inicio, que
// a su vez pide iniciar sesión si hace falta.
export default function RootNotFound() {
  return (
    <NotFoundState
      title="Página no encontrada"
      message="La dirección que buscas no existe o cambió de lugar."
      primaryLink={{ href: "/inicio", label: "Ir al inicio" }}
    />
  );
}
