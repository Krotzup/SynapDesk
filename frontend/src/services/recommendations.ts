import { api } from "@/lib/api";
import { USE_MOCKS } from "@/lib/config";
import { recommendationsMock } from "@/mocks/recommendations";
import { HumanReview, Recommendation } from "@/types";

const recommendationsApi = {
  // Genera una nueva recomendación para el ticket
  generate: (ticketId: string): Promise<Recommendation> =>
    api.post(`/tickets/${ticketId}/recommendations`, {}),

  // Lista todas las recomendaciones de un ticket
  getByTicket: (ticketId: string): Promise<Recommendation[]> =>
    api.get(`/tickets/${ticketId}/recommendations`),

  // Consulta una recomendación específica
  getById: (id: string): Promise<Recommendation> => api.get(`/recommendations/${id}`),

  // Registra la revisión humana (aceptar / modificar / rechazar)
  // El backend determina el revisor mediante la sesión — no se envía reviewerId
  review: (id: string, data: HumanReview): Promise<void> =>
    api.post(`/recommendations/${id}/reviews`, data),
};

export type RecommendationsService = typeof recommendationsApi;

export const recommendationsService: RecommendationsService = USE_MOCKS
  ? recommendationsMock
  : recommendationsApi;
