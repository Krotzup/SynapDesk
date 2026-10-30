import type { RecommendationsService } from "@/services/recommendations";
import { Recommendation, RecommendationStatus, ReviewDecision } from "@/types";
import { rejectWithApiError, simulateLatency } from "./utils";

// Recomendaciones ficticias. El score es similitud coseno (rango -1 a 1), no un porcentaje.
const recommendations: Recommendation[] = [
  {
    id: "459235aa-e33a-4e19-9055-b085319ff895",
    ticketId: "64f10aed-c41c-46a3-91dd-f2cbcd5eb79f",
    content:
      "El error se debe a un problema de conexión con el servidor de base de datos. Verifica que el servicio esté en ejecución, revisa las credenciales de conexión y la configuración de red. Si el problema persiste, revisa los logs del servidor y la configuración del pool de conexiones.",
    status: "pending",
    sources: [
      {
        documentId: "5e923ab0-5cee-4c50-b0dc-35fa54ca54aa",
        documentChunkId: "77223789-bd19-4642-a550-b4f52210320c",
        title: "Manual de PostgreSQL",
        excerpt:
          "Verifique el estado del servicio PostgreSQL y que el puerto 5432 esté habilitado en el firewall. Compruebe que las credenciales del pool de conexiones sean correctas.",
        score: 0.82,
      },
      {
        documentId: "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d",
        documentChunkId: "6e7f8a9b-0c1d-4e2f-9a3b-4c5d6e7f8a9b",
        title: "Procedimiento de conectividad",
        excerpt:
          "asignada en el switch. Si después de reiniciar el adaptador la red sigue sin funcionar, documente los resultados y escale al equipo de redes.",
        score: 0.61,
      },
    ],
    createdAt: "2026-10-28T13:26:00Z",
  },
  {
    id: "b7c8d9e0-f1a2-4b3c-8d4e-5f6a7b8c9d0e",
    ticketId: "9c8d7e6f-5a4b-4c3d-8e2f-1a0b9c8d7e03",
    content:
      "Revisa las consultas del proceso de pago con mayor tiempo de respuesta y habilita caché para el catálogo de productos.",
    status: "accepted",
    sources: [
      {
        documentId: "2b3c4d5e-6f7a-4b8c-9d0e-1f2a3b4c5d6e",
        documentChunkId: "8f9a0b1c-2d3e-4f4a-8b5c-6d7e8f9a0b1c",
        title: "Guía de rendimiento de aplicaciones",
        excerpt:
          "Identifique las consultas lentas con el registro de duración y priorice las que se ejecutan en cada solicitud.",
        score: 0.74,
      },
    ],
    createdAt: "2026-10-28T12:20:00Z",
  },
];

const statusByDecision: Record<ReviewDecision, RecommendationStatus> = {
  accepted: "accepted",
  modified: "modified",
  rejected: "rejected",
};

function notFound() {
  return rejectWithApiError("RECOMMENDATION_NOT_FOUND", "La recomendación solicitada no existe.");
}

export const recommendationsMock: RecommendationsService = {
  generate: (ticketId) => {
    const recommendation: Recommendation = {
      id: crypto.randomUUID(),
      ticketId,
      content:
        "Recomendación de ejemplo generada sin LLM. Se reemplazará por la respuesta real del backend.",
      status: "pending",
      sources: [],
      createdAt: new Date().toISOString(),
    };
    recommendations.push(recommendation);
    return simulateLatency(recommendation);
  },

  getByTicket: (ticketId) =>
    simulateLatency(
      recommendations
        .filter((item) => item.ticketId === ticketId)
        .sort((a, b) => a.createdAt.localeCompare(b.createdAt))
    ),

  getById: (id) => {
    const recommendation = recommendations.find((item) => item.id === id);
    return recommendation ? simulateLatency(recommendation) : notFound();
  },

  review: (id, data) => {
    const recommendation = recommendations.find((item) => item.id === id);
    if (!recommendation) return notFound();

    recommendation.status = statusByDecision[data.decision];
    if (data.decision === "modified" && data.modifiedContent) {
      recommendation.content = data.modifiedContent;
    }
    return simulateLatency(undefined);
  },
};
