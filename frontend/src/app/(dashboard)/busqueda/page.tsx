import Link from "next/link";
import { connection } from "next/server";
import type { ReactNode } from "react";
import { SearchForm } from "@/components/search/SearchForm";
import { SearchResults } from "@/components/search/SearchResults";
import { USE_MOCKS } from "@/lib/config";
import { buildQuery } from "@/lib/params";
import { MAX_QUERY_LENGTH, parseSemanticSearchParams } from "@/lib/search-params";

interface BusquedaPageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

const EXAMPLE_QUERIES = [
  "No tengo conexión a la red",
  "Cómo revisar la dirección IP de Windows",
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
          <SearchResults key={`${query}|${limit}`} query={query} limit={limit} />
        )}
      </div>
    </div>
  );
}
