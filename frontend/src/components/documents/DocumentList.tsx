import Link from "next/link";
import { connection } from "next/server";
import { RetryButton } from "@/components/ui/RetryButton";
import { DocumentStatusBadge } from "@/components/ui/Badge";
import { Pagination } from "@/components/ui/Pagination";
import { formatContentType, formatDateTime } from "@/lib/format";
import { buildQuery } from "@/lib/params";
import { documentsService } from "@/services/documents";

interface DocumentListProps {
  page: number;
  pageSize: number;
}

const hrefFor = (page: number) => `/documentos${buildQuery({ page: page > 1 ? page : undefined })}`;

/**
 * Documentos de la base de conocimientos (GET /documents). Muestra solo los campos del
 * contrato: título, descripción, archivo, tipo, estado de procesamiento, autor y fecha.
 */
export async function DocumentList({ page, pageSize }: DocumentListProps) {
  await connection();
  const result = await documentsService.getAll({ page, pageSize }).catch(() => null);

  if (!result) {
    return (
      <div
        role="alert"
        className="m-4 sm:m-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl border border-[#FECACA] bg-[#FEF2F2] px-4 py-3"
      >
        <p className="text-sm text-[#991B1B]">
          No se pudieron cargar los documentos. Puede ser algo temporal; intenta de nuevo.
        </p>
        <RetryButton />
      </div>
    );
  }

  const documents = result.items;
  if (documents.length === 0) {
    return (
      <p className="py-10 px-4 text-center text-sm text-[#94A3B8]">
        {result.totalItems > 0 ? (
          <>
            Esta página no tiene documentos.{" "}
            <Link href="/documentos" className="text-[#2563EB] hover:underline">
              Ir a la primera página
            </Link>
          </>
        ) : (
          "Todavía no hay documentos en la base de conocimientos."
        )}
      </p>
    );
  }

  return (
    <>
      {/* Teléfono: tarjetas. Desde 768 px: tabla. */}
      <ul className="md:hidden divide-y divide-[#F1F5F9]" aria-label="Documentos">
        {documents.map((document) => (
          <li key={document.id} className="space-y-2 px-4 py-4">
            <div className="flex items-start justify-between gap-3">
              <p className="text-sm font-semibold text-[#0F172A]">{document.title}</p>
              <span className="shrink-0">
                <DocumentStatusBadge status={document.processingStatus} />
              </span>
            </div>
            {document.description && (
              <p className="text-xs text-[#64748B] line-clamp-2">{document.description}</p>
            )}
            <p className="text-xs text-[#94A3B8] break-all">
              {document.originalFilename} · {formatContentType(document.contentType)}
            </p>
            <p className="text-xs text-[#94A3B8]">
              {document.uploadedBy.name} · {formatDateTime(document.createdAt)}
            </p>
          </li>
        ))}
      </ul>

      <div className="hidden md:block overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-[#F8FAFC] text-[11px] font-bold text-[#64748B] uppercase tracking-wider border-b border-[#E2E8F0]">
              <th className="py-3.5 px-4">Documento</th>
              <th className="py-3.5 px-4">Archivo</th>
              <th className="py-3.5 px-4">Estado</th>
              <th className="py-3.5 px-4 hidden lg:table-cell">Subido por</th>
              <th className="py-3.5 px-4 hidden xl:table-cell">Fecha</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#F1F5F9] text-xs text-[#475569]">
            {documents.map((document) => (
              <tr key={document.id} className="hover:bg-[#F8FAFC] transition-colors">
                <td className="py-4 px-4">
                  <p className="font-semibold text-[#0F172A]">{document.title}</p>
                  {document.description && (
                    <p className="mt-0.5 text-[11px] text-[#64748B] line-clamp-1">
                      {document.description}
                    </p>
                  )}
                </td>
                <td className="py-4 px-4">
                  <p className="max-w-48 truncate" title={document.originalFilename}>
                    {document.originalFilename}
                  </p>
                  <p className="text-[11px] text-[#94A3B8]">
                    {formatContentType(document.contentType)}
                  </p>
                </td>
                <td className="py-4 px-4 whitespace-nowrap">
                  <DocumentStatusBadge status={document.processingStatus} />
                </td>
                <td className="py-4 px-4 hidden lg:table-cell font-medium text-[#0F172A]">
                  {document.uploadedBy.name}
                </td>
                <td className="py-4 px-4 hidden xl:table-cell text-[#94A3B8] whitespace-nowrap">
                  {formatDateTime(document.createdAt)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Pagination
        result={result}
        hrefFor={hrefFor}
        label="Paginación de documentos"
        noun={["documento", "documentos"]}
      />
    </>
  );
}

/** Marcador mientras llegan los documentos. */
export function DocumentListFallback() {
  return (
    <ul className="space-y-2 p-4 sm:p-5" aria-busy="true" aria-label="Cargando documentos">
      {Array.from({ length: 5 }, (_, index) => (
        <li key={index} className="h-14 rounded-xl bg-[#F8FAFC] animate-pulse" />
      ))}
    </ul>
  );
}
