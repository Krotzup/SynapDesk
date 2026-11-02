import Link from "next/link";
import { connection } from "next/server";
import { ReactNode, Suspense } from "react";
import { RetryButton } from "@/components/search/RetryButton";
import { SearchForm } from "@/components/search/SearchForm";
import { SearchResultCard } from "@/components/search/SearchResultCard";
import { USE_MOCKS } from "@/lib/config";
import { isApiError } from "@/lib/errors";
import { buildQuery } from "@/lib/params";
import { MAX_QUERY_LENGTH, parseSemanticSearchParams, SearchLimit } from "@/lib/search-params";
import { searchService, SearchResponse } from "@/services/search";

interface BusquedaPageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

const EXAMPLE_QUERIES = [
  "No puedo conectarme a la VPN desde casa",
  "Cómo restablecer mi contraseña",
  "La impresora no imprime y los documentos quedan en cola",
];

function Notice({ icon, title, children }: { icon: string; title: string; children: ReactNode }) {
  return (
    <div className="bg-white p-8 rounded-2xl border border-[#E2E8F0] shadow-sm text-center space-y-3">
      <p className="text-3xl" aria-hidden="true">
        {icon}
      </p>
      <h2 className="text-base font-semibold text-[#0F172A]">{title}</h2>
      <div className="text-sm text-[#64748B] space-y-3">{children}</div>
    </div>
  );
}

function ResultsSkeleton() {
  return (
    <div className="space-y-4 animate-pulse" aria-busy="true" aria-live="polite">
      {Array.from({ length: 3 }, (_, index) => (
        <div key={index} className="h-32 bg-white border border-[#E2E8F0] rounded-2xl" />
      ))}
      <span className="sr-only">Buscando fragmentos…</span>
    </div>
  );
}

async function SearchResults({ query, limit }: { query: string; limit: SearchLimit }) {
  let response: SearchResponse;
  try {
    response = await searchService.semantic(query, limit);
  } catch (error) {
    // Solo se muestra el mensaje del contrato; otros errores (red, CORS) usan uno genérico.
    const message = isApiError(error)
      ? error.error.message
      : "No fue posible comunicarse con el servicio de búsqueda.";
    return (
      <Notice icon="⚠️" title="No se pudo completar la búsqueda">
        <p>{message}</p>
        <RetryButton />
      </Notice>
    );
  }

  if (response.items.length === 0) {
    return (
      <Notice icon="🔍" title="Sin resultados">
        <p>
          No se encontraron fragmentos relacionados con la consulta. Prueba describiendo el problema
          con otras palabras.
        </p>
      </Notice>
    );
  }

  return (
    <section className="space-y-4" aria-label="Resultados de la búsqueda">
      <p className="text-sm text-[#475569]">
        {response.items.length === 1
          ? "1 fragmento encontrado"
          : `${response.items.length} fragmentos encontrados`}
        , ordenados por similitud.
      </p>
      <p className="text-xs text-[#3730A3] bg-[#EEF2FF] border border-[#C7D2FE] rounded-xl px-4 py-2.5">
        ℹ️ La similitud indica qué tan cercano es el significado del fragmento a la consulta. No es
        una probabilidad ni un porcentaje de acierto: revisa el contenido antes de aplicarlo.
      </p>
      {response.items.map((result) => (
        <SearchResultCard key={result.documentChunkId} result={result} />
      ))}
    </section>
  );
}

export default async function BusquedaPage({ searchParams }: BusquedaPageProps) {
  // Renderiza en cada solicitud: la búsqueda depende de la URL.
  await connection();
  const { query, limit, tooLong } = parseSemanticSearchParams(await searchParams);

  return (
    <div className="p-8 bg-[#F8FAFC] min-h-screen">
      <div className="max-w-4xl mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-[#0F172A]">Búsqueda semántica</h1>
          <p className="text-sm text-[#64748B] mt-1">
            Describe el problema en lenguaje natural y encuentra los fragmentos más cercanos de la
            base de conocimientos.
          </p>
        </div>

        {/* Evita confundir los datos de ejemplo con resultados del modelo de embeddings */}
        {USE_MOCKS && (
          <p className="text-xs text-[#92400E] bg-[#FEF3C7] border border-[#FDE68A] rounded-xl px-4 py-2.5">
            <strong>Datos de ejemplo:</strong> los documentos son ficticios y la similitud se simula
            contando palabras en común con la consulta. No proviene del modelo de embeddings.
          </p>
        )}

        <div className="bg-white p-5 rounded-2xl border border-[#E2E8F0] shadow-sm">
          {/* key: el formulario se reinicia cuando la URL cambia desde un enlace */}
          <SearchForm key={`${query}|${limit}`} query={query} limit={limit} />
        </div>

        {!query ? (
          <Notice icon="💡" title="Busca en la base de conocimientos">
            <p>Prueba con una de estas consultas:</p>
            <ul className="flex flex-col items-center gap-2">
              {EXAMPLE_QUERIES.map((example) => (
                <li key={example}>
                  <Link
                    href={`/busqueda${buildQuery({ q: example, limit })}`}
                    className="inline-block text-sm font-medium text-[#1D4ED8] bg-[#DBEAFE] rounded-full px-3 py-1 hover:bg-[#BFDBFE]"
                  >
                    {example}
                  </Link>
                </li>
              ))}
            </ul>
          </Notice>
        ) : tooLong ? (
          <Notice icon="✂️" title="La consulta es demasiado larga">
            <p>Usa como máximo {MAX_QUERY_LENGTH} caracteres.</p>
          </Notice>
        ) : (
          <Suspense key={`${query}|${limit}`} fallback={<ResultsSkeleton />}>
            <SearchResults query={query} limit={limit} />
          </Suspense>
        )}
      </div>
    </div>
  );
}
