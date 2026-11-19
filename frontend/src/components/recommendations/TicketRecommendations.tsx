import { SectionError } from "@/components/home/SectionError";
import { splitRecommendations } from "@/lib/recommendation-history";
import { recommendationsService } from "@/services/recommendations";
import { AssistantRecommendation } from "./AssistantRecommendation";
import { RecommendationHistory } from "./RecommendationHistory";

/**
 * Recomendaciones del ticket en el Asistente IA. Son opcionales: si fallan, el detalle y el
 * cambio de estado se siguen mostrando. Se renderiza dentro de un Suspense.
 */
export async function TicketRecommendations({ ticketId }: { ticketId: string }) {
  const recommendations = await recommendationsService.getByTicket(ticketId).catch(() => null);

  // Sin la lista no se ofrece «Generar»: no se sabe si ya hay una recomendación pendiente.
  if (!recommendations) {
    return <SectionError message="No se pudieron cargar las recomendaciones del ticket." />;
  }

  const { latest: recommendation, previous } = splitRecommendations(recommendations);
  return (
    <>
      {/* La clave reinicia el panel cuando el servidor entrega otra versión (router.refresh) */}
      <AssistantRecommendation
        key={recommendation ? `${recommendation.id}:${recommendation.status}` : "none"}
        ticketId={ticketId}
        initialRecommendation={recommendation}
      />
      <RecommendationHistory recommendations={previous} />
    </>
  );
}

/** Marcador mientras llegan las recomendaciones. */
export function TicketRecommendationsFallback() {
  return (
    <div aria-busy="true" className="space-y-2 animate-pulse">
      <div className="h-4 w-40 rounded bg-[#E0E7FF]" />
      <div className="h-24 rounded-xl border border-[#C7D2FE] bg-white" />
      <span className="sr-only">Cargando recomendaciones…</span>
    </div>
  );
}
