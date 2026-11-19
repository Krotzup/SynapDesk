import { RecommendationStatusBadge } from "@/components/ui/Badge";
import { formatDateTime } from "@/lib/format";
import { Recommendation } from "@/types";
import { RecommendationSources } from "./RecommendationSources";
import { RecommendationContent } from "./RecommendationContent";

/**
 * Recomendaciones anteriores del ticket, de la más reciente a la más antigua. Muestra el
 * contenido original de la IA, que nunca se sobrescribe, con su estado, fecha y fuentes.
 */
export function RecommendationHistory({ recommendations }: { recommendations: Recommendation[] }) {
  if (recommendations.length === 0) return null;

  return (
    <section aria-labelledby="historial-recomendaciones" className="pt-4 border-t border-[#C7D2FE]">
      <h3 id="historial-recomendaciones" className="text-xs font-bold text-[#4338CA] mb-2">
        Recomendaciones anteriores ({recommendations.length})
      </h3>
      <ol className="space-y-2">
        {recommendations.map((recommendation) => (
          <li key={recommendation.id}>
            <details className="group bg-white border border-[#C7D2FE] rounded-xl">
              <summary className="flex min-h-11 cursor-pointer list-none items-center gap-2 px-3 py-2 text-xs text-[#475569] rounded-xl hover:bg-[#EEF2FF] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#2563EB]">
                <span className="flex-1">{formatDateTime(recommendation.createdAt)}</span>
                <RecommendationStatusBadge status={recommendation.status} />
                <span
                  aria-hidden="true"
                  className="text-[#94A3B8] group-open:rotate-180 transition-transform"
                >
                  ▾
                </span>
              </summary>
              <div className="space-y-3 px-3 pb-3">
                <div>
                  <p className="text-[11px] font-semibold text-[#64748B] mb-1">
                    Contenido original de la IA
                  </p>
                  <p className="text-xs text-[#0F172A] leading-relaxed whitespace-pre-line">
                    <RecommendationContent
                      content={recommendation.content}
                      sources={recommendation.sources}
                      recommendationId={recommendation.id}
                    />
                  </p>
                </div>
                <RecommendationSources
                  sources={recommendation.sources}
                  recommendationId={recommendation.id}
                />
                {recommendation.review && (
                  <div className="space-y-1 text-xs text-[#475569]">
                    <p>Revisada el {formatDateTime(recommendation.review.reviewedAt)}</p>
                    {recommendation.review.modifiedContent && (
                      <p className="whitespace-pre-line">
                        Versión del especialista: {recommendation.review.modifiedContent}
                      </p>
                    )}
                    {recommendation.review.feedback && (
                      <p className="whitespace-pre-line">
                        Comentario: {recommendation.review.feedback}
                      </p>
                    )}
                  </div>
                )}
              </div>
            </details>
          </li>
        ))}
      </ol>
    </section>
  );
}
