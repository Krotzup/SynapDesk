import { Recommendation } from "@/types";

/**
 * Separa la recomendación vigente (la más reciente) de las anteriores del ticket. El contrato no
 * fija el orden de GET /tickets/{id}/recommendations, así que se ordena por fecha de creación.
 * Se comparan instantes, no textos: la misma fecha puede llegar con o sin fracción de segundo, o
 * con otro desfase horario. Con fechas iguales desempata el id, para que el orden sea estable.
 * Las anteriores quedan de la más reciente a la más antigua.
 */
export function splitRecommendations(recommendations: readonly Recommendation[]): {
  latest: Recommendation | null;
  previous: Recommendation[];
} {
  const time = (value: string) => Date.parse(value);
  const sorted = [...recommendations].sort(
    (a, b) => time(a.createdAt) - time(b.createdAt) || a.id.localeCompare(b.id)
  );
  const latest = sorted.pop() ?? null;
  return { latest, previous: sorted.reverse() };
}
