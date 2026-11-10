import { connection } from "next/server";
import { DocumentStatusBadge } from "@/components/ui/Badge";
import { formatDateTime } from "@/lib/format";
import { documentsService } from "@/services/documents";
import { SectionError } from "./SectionError";

const RECENT_DOCUMENTS_COUNT = 4;

/** Últimos documentos incorporados a la base de conocimientos. */
export async function RecentDocuments() {
  await connection();

  const result = await documentsService
    .getAll({ page: 1, pageSize: RECENT_DOCUMENTS_COUNT })
    .catch(() => null);

  if (!result) {
    return <SectionError message="No se pudieron cargar los documentos." />;
  }
  if (result.items.length === 0) {
    return (
      <p className="py-4 text-center text-xs text-[#94A3B8]">
        Todavía no hay documentos en la base de conocimientos.
      </p>
    );
  }

  return (
    <ul className="space-y-2">
      {result.items.map((document) => (
        <li
          key={document.id}
          className="flex items-start justify-between gap-3 p-3 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl"
        >
          <div className="flex items-start gap-3 min-w-0">
            <div className="p-1.5 bg-[#EFF6FF] text-[#2563EB] rounded-lg shrink-0">
              <svg
                className="h-4 w-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
            </div>
            <div className="min-w-0">
              <p className="text-xs font-semibold text-[#0F172A]">{document.title}</p>
              <p className="text-[11px] text-[#94A3B8] truncate" title={document.originalFilename}>
                {document.originalFilename}
              </p>
              <p className="text-[11px] text-[#94A3B8] whitespace-nowrap">
                {formatDateTime(document.createdAt)}
              </p>
            </div>
          </div>
          <span className="shrink-0 whitespace-nowrap">
            <DocumentStatusBadge status={document.processingStatus} />
          </span>
        </li>
      ))}
    </ul>
  );
}

/** Marcador mientras llegan los documentos. */
export function RecentDocumentsFallback() {
  return (
    <ul className="space-y-2" aria-busy="true" aria-label="Cargando documentos">
      {Array.from({ length: RECENT_DOCUMENTS_COUNT }, (_, index) => (
        <li
          key={index}
          className="h-[66px] rounded-xl bg-[#F8FAFC] border border-[#E2E8F0] animate-pulse"
        />
      ))}
    </ul>
  );
}
