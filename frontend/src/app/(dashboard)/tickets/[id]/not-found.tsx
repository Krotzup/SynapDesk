import { NotFoundState } from "@/components/layout/NotFoundState";

export default function TicketNotFound() {
  return (
    <NotFoundState
      title="Ticket no encontrado"
      message="El ticket que buscas no existe o ya no está disponible."
      primaryLink={{ href: "/tickets", label: "← Volver a tickets" }}
    />
  );
}
