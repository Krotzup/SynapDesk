import { formatExcerpt, formatScore } from "@/lib/format";
import { RecommendationSource } from "@/types";

/** Fuentes RAG de una recomendación, con el fragmento recuperado desplegable. */
export function RecommendationSources({ sources }: { sources: RecommendationSource[] }) {
  return (
    <div>
      <p className="text-xs font-bold text-[#4338CA] mb-2">Fuentes consultadas (RAG)</p>
      {sources.length === 0 ? (
        <p className="text-xs text-[#64748B]">La recomendación no tiene fuentes asociadas.</p>
      ) : (
        <div className="space-y-2">
          {sources.map((source) => (
            <details key={source.documentChunkId} className="group">
              <summary className="flex items-center gap-2 cursor-pointer list-none bg-white border border-[#C7D2FE] rounded-lg px-3 py-2 text-xs font-medium text-[#4338CA] hover:bg-[#EEF2FF] transition-colors">
                <span>📑</span>
                <span className="flex-1">{source.title}</span>
                <span
                  className="text-[11px] text-[#64748B]"
                  title="Similitud semántica entre la consulta y el fragmento (no es un porcentaje de confianza)"
                >
                  Similitud {formatScore(source.score)}
                </span>
                <span className="text-[#94A3B8] group-open:rotate-180 transition-transform">▾</span>
              </summary>
              <div className="mt-1 px-3 py-2 bg-white border border-[#C7D2FE] border-t-0 rounded-b-lg text-[11px] text-[#475569] leading-relaxed italic">
                &ldquo;{formatExcerpt(source.excerpt)}&rdquo;
              </div>
            </details>
          ))}
        </div>
      )}
    </div>
  );
}
