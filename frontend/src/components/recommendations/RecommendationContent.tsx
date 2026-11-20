"use client";

import { RecommendationSource } from "@/types";

/** Solo enlaza referencias que coinciden con las fuentes conservadas del borrador. */
export function RecommendationContent({
  content,
  sources,
  recommendationId,
}: {
  content: string;
  sources: RecommendationSource[];
  recommendationId: string;
}) {
  const parts = content.split(/(\[[0-9a-f-]{36}(?:,\s*[0-9a-f-]{36})*\])/gi);
  return (
    <>
      {parts.map((part, index) => {
        if (!part.startsWith("[")) return part;
        const indices = part
          .slice(1, -1)
          .split(/,\s*/)
          .map((ref) => sources.findIndex((source) => source.documentChunkId === ref));
        if (indices.some((sourceIndex) => sourceIndex < 0)) return part;
        return (
          <span key={index}>
            {indices.map((sourceIndex, position) => {
              const id = `source-${recommendationId}-${sources[sourceIndex].documentChunkId}`;
              return (
                <a
                  key={`${sourceIndex}-${position}`}
                  href={`#${id}`}
                  className="font-semibold text-[#4338CA] underline mr-1"
                  aria-label={`Consultar fuente ${sourceIndex + 1}: ${sources[sourceIndex].title}`}
                  onClick={() => {
                    const details = document.getElementById(id);
                    if (details instanceof HTMLDetailsElement) {
                      details.open = true;
                      details.querySelector("summary")?.focus();
                    }
                  }}
                >
                  [Fuente {sourceIndex + 1}]
                </a>
              );
            })}
          </span>
        );
      })}
    </>
  );
}
