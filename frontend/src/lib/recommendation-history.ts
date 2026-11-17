import { Recommendation } from "@/types";

/**
 * Separa la recomendación vigente (la más reciente) de las anteriores del ticket. El contrato no
 * fija el orden de GET /tickets/{id}/recommendations, así que se ordena por fecha de creación.
 * Las anteriores quedan de la más reciente a la más antigua.
 */
export function splitRecommendations(recommendations: readonly Recommendation[]): {
  latest: Recommendation | null;
  previous: Recommendation[];
} {
  const sorted = [...recommendations].sort((a, b) => a.createdAt.localeCompare(b.createdAt));
  const latest = sorted.pop() ?? null;
  return { latest, previous: sorted.reverse() };
}
