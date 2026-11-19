import Link from "next/link";
import { notFound } from "next/navigation";
import { RetireDocument } from "@/components/documents/DocumentActions";
import { DocumentStatusBadge } from "@/components/ui/Badge";
import { formatDateTime } from "@/lib/format";
import { isApiError } from "@/lib/errors";
import { documentsService } from "@/services/documents";

export default async function DocumentDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const document = await documentsService.getById(id).catch((error) => {
    if (isApiError(error) && error.error.code === "DOCUMENT_NOT_FOUND") notFound();
    throw error;
  });
  return (
    <div className="p-4 sm:p-6 max-w-4xl mx-auto space-y-5">
      <Link href="/documentos" className="text-[#2563EB] underline">
        ← Volver a documentos
      </Link>
      <article className="p-5 bg-white border border-[#E2E8F0] rounded-2xl space-y-4">
        <h1 className="text-2xl font-bold text-[#0F172A]">{document.title}</h1>
        <DocumentStatusBadge status={document.processingStatus} />
        {document.description && (
          <p className="text-[#475569] whitespace-pre-line">{document.description}</p>
        )}
        <dl className="text-sm text-[#475569] space-y-2">
          <div>
            <dt className="font-semibold inline">Archivo: </dt>
            <dd className="inline break-all">{document.originalFilename}</dd>
          </div>
          <div>
            <dt className="font-semibold inline">Tipo: </dt>
            <dd className="inline">{document.contentType}</dd>
          </div>
          <div>
            <dt className="font-semibold inline">Subido por: </dt>
            <dd className="inline">{document.uploadedBy.name}</dd>
          </div>
          <div>
            <dt className="font-semibold inline">Creado: </dt>
            <dd className="inline">{formatDateTime(document.createdAt)}</dd>
          </div>
        </dl>
        <RetireDocument documentId={document.id} />
      </article>
    </div>
  );
}
