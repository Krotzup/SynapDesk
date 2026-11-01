import { formatExcerpt, formatScore, shortId } from "@/lib/format";
import { SearchResult } from "@/types";

const SCORE_HINT =
  "Similitud semántica entre la consulta y el fragmento. Va de −1 a 1; mientras más alta, más cercano el significado. No es un porcentaje de confianza.";

export function SearchResultCard({ result }: { result: SearchResult }) {
  return (
    <article className="bg-white p-5 rounded-2xl border border-[#E2E8F0] shadow-sm space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-[#0F172A]">📑 {result.title}</h2>
          <p className="text-xs text-[#64748B] mt-0.5" title={result.documentId}>
            Documento #{shortId(result.documentId)}
          </p>
        </div>
        <span
          className="inline-flex items-center rounded-full bg-[#E0E7FF] px-2.5 py-0.5 text-xs font-medium text-[#3730A3] whitespace-nowrap cursor-help"
          title={SCORE_HINT}
        >
          Similitud {formatScore(result.score)}
        </span>
      </div>
      <p className="text-sm text-[#475569] leading-relaxed italic border-l-2 border-[#C7D2FE] pl-3">
        &ldquo;{formatExcerpt(result.excerpt)}&rdquo;
      </p>
    </article>
  );
}
