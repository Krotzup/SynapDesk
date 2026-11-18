import { Suspense } from "react";
import { DocumentList, DocumentListFallback } from "@/components/documents/DocumentList";
import { USE_MOCKS } from "@/lib/config";
import { parseDocumentListParams } from "@/lib/document-params";

interface DocumentosPageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export default async function DocumentosPage({ searchParams }: DocumentosPageProps) {
  const { page, pageSize } = parseDocumentListParams(await searchParams);

  return (
    <div className="px-4 py-6 sm:p-6 lg:p-8 bg-[#F8FAFC] min-h-screen">
      <div className="max-w-7xl mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-[#0F172A]">Base de Conocimientos</h1>
          <p className="text-sm text-[#64748B] mt-1">
            Documentos que el Asistente IA y la búsqueda semántica usan como fuente.
          </p>
        </div>

        {USE_MOCKS && (
          <p className="text-xs text-[#92400E] bg-[#FEF3C7] border border-[#FDE68A] rounded-xl px-4 py-2.5">
            <strong>Datos de ejemplo:</strong> los documentos son ficticios y no provienen del
            backend.
          </p>
        )}

        {/* Subir y retirar documentos esperan que el contrato defina formatos y tamaños. */}
        <section
          aria-labelledby="documentos-titulo"
          className="bg-white rounded-2xl border border-[#E2E8F0] shadow-sm overflow-hidden"
        >
          <h2
            id="documentos-titulo"
            className="p-4 sm:p-5 border-b border-[#F1F5F9] text-base font-bold text-[#0F172A]"
          >
            Documentos
          </h2>
          {/* La clave muestra el marcador de carga también al cambiar de página. */}
          <Suspense key={page} fallback={<DocumentListFallback />}>
            <DocumentList page={page} pageSize={pageSize} />
          </Suspense>
        </section>
      </div>
    </div>
  );
}
