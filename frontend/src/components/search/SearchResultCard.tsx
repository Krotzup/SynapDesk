import { formatExcerpt, formatScore, shortId } from "@/lib/format";
import { safeSourceUrl, type SearchResultGroup } from "@/lib/search-contract";

const SCORE_HINT =
  "Similitud semántica entre la consulta y el fragmento. Va de −1 a 1; mientras más alta, más cercano el significado. No es un porcentaje de confianza.";

export function SearchResultCard({ group }: { group: SearchResultGroup }) {
  const { document, fragments } = group;
  const source = safeSourceUrl(document.sourceUrl);
  const language = document.language?.split("-")[0];
  return (
    <article className="bg-white p-5 rounded-2xl border border-[#E2E8F0] shadow-sm space-y-3">
      <div className="min-w-0">
        <h2 className="text-sm font-semibold text-[#0F172A]">📑 {document.title}</h2>
        <p className="text-xs text-[#64748B] mt-0.5" title={document.documentId}>
          Documento #{shortId(document.documentId)}
        </p>
      </div>
      <div className="flex flex-wrap gap-3 text-xs text-[#64748B]">
        {document.language && (
          <span>
            Idioma:{" "}
            {language === "es" ? "Español" : language === "en" ? "Inglés" : document.language}
          </span>
        )}
        {source && (
          <a
            href={source}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-[#2563EB] hover:underline"
          >
            Ver fuente original ↗
          </a>
        )}
      </div>
      <ul className="space-y-3">
        {fragments.map((fragment) => (
          <li key={fragment.documentChunkId} className="space-y-1 border-l-2 border-[#C7D2FE] pl-3">
            <span
              className="inline-flex rounded-full bg-[#E0E7FF] px-2.5 py-0.5 text-xs font-medium text-[#3730A3]"
              title={SCORE_HINT}
            >
              Similitud {formatScore(fragment.score)}
            </span>
            <p className="text-sm text-[#475569] leading-relaxed italic" lang={fragment.language}>
              &ldquo;{formatExcerpt(fragment.excerpt)}&rdquo;
            </p>
          </li>
        ))}
      </ul>
    </article>
  );
}
