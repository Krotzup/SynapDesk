import Link from "next/link";
import { notFound } from "next/navigation";
import { PriorityBadge, StatusBadge } from "@/components/ui/Badge";
import { isApiError } from "@/lib/errors";
import { formatDateTime, formatScore, shortId } from "@/lib/format";
import { recommendationsService } from "@/services/recommendations";
import { ticketsService } from "@/services/tickets";
import { RecommendationStatus, Ticket } from "@/types";

interface TicketDetailPageProps {
  params: Promise<{ id: string }>;
}

const recommendationStatusLabels: Record<RecommendationStatus, string> = {
  pending: "Pendiente de revisión",
  accepted: "Aceptada",
  modified: "Modificada",
  rejected: "Rechazada",
};

async function getTicket(id: string): Promise<Ticket> {
  try {
    return await ticketsService.getById(id);
  } catch (error) {
    if (isApiError(error) && error.error.code === "TICKET_NOT_FOUND") notFound();
    throw error;
  }
}

// Los fragmentos recuperados pueden comenzar a mitad de una oración.
function formatExcerpt(excerpt: string): string {
  return /^\p{Ll}/u.test(excerpt) ? `…${excerpt}` : excerpt;
}

export default async function TicketDetailPage({ params }: TicketDetailPageProps) {
  const { id } = await params;
  const [ticket, recommendations] = await Promise.all([
    getTicket(id),
    recommendationsService.getByTicket(id),
  ]);
  const recommendation = recommendations.at(-1) ?? null;

  return (
    <div className="p-6 bg-[#F8FAFC] min-h-screen">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start max-w-7xl mx-auto">
        {/* Panel central: Detalle del ticket */}
        <div className="lg:col-span-2 space-y-6 bg-white p-6 rounded-2xl border border-[#E2E8F0] shadow-sm">
          <Link
            href="/tickets"
            className="inline-flex items-center gap-2 text-sm text-[#2563EB] font-medium hover:underline"
          >
            ← Volver a tickets
          </Link>

          <div className="flex flex-wrap items-center gap-3">
            <span
              className="bg-[#2563EB] text-white font-bold text-xs px-3 py-1 rounded-md"
              title={ticket.id}
            >
              #{shortId(ticket.id)}
            </span>
            <h1 className="text-xl font-bold text-[#0F172A]">{ticket.title}</h1>
            <StatusBadge status={ticket.status} />
            <PriorityBadge priority={ticket.priority} />
          </div>

          <p className="text-sm text-[#475569] leading-relaxed">{ticket.description}</p>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 pt-4 border-t border-[#F1F5F9]">
            <div>
              <p className="text-xs text-[#94A3B8] font-medium">Usuario</p>
              <p className="text-sm font-semibold text-[#0F172A] mt-1">{ticket.createdBy.name}</p>
            </div>
            <div>
              <p className="text-xs text-[#94A3B8] font-medium">Fecha de creación</p>
              <p className="text-sm font-semibold text-[#0F172A] mt-1">
                {formatDateTime(ticket.createdAt)}
              </p>
            </div>
            <div>
              <p className="text-xs text-[#94A3B8] font-medium">Área</p>
              <p className="text-sm font-semibold text-[#0F172A] mt-1">
                {ticket.area ?? "Sin asignar"}
              </p>
            </div>
            <div>
              <p className="text-xs text-[#94A3B8] font-medium">Categoría</p>
              <p className="text-sm font-semibold text-[#0F172A] mt-1">
                {ticket.category ?? "Sin categoría"}
              </p>
            </div>
            <div>
              <p className="text-xs text-[#94A3B8] font-medium">Asignado a</p>
              <p className="text-sm font-semibold text-[#0F172A] mt-1">
                {ticket.assignedTo?.name ?? "Sin asignar"}
              </p>
            </div>
            {ticket.resolvedAt && (
              <div>
                <p className="text-xs text-[#94A3B8] font-medium">Fecha de resolución</p>
                <p className="text-sm font-semibold text-[#0F172A] mt-1">
                  {formatDateTime(ticket.resolvedAt)}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Panel derecho: Asistente IA */}
        <div className="bg-[#EEF2FF] p-6 rounded-2xl border border-[#818CF8] shadow-sm space-y-5">
          <div className="flex items-center gap-2 text-[#4338CA] font-bold text-lg">
            <span>🤖</span> Asistente IA
          </div>

          {/* La predicción ML depende de las decisiones pendientes del contrato backend-ML */}
          <div className="p-3 bg-white border border-dashed border-[#C7D2FE] rounded-xl text-xs text-[#64748B]">
            La clasificación automática (categoría y prioridad estimadas) se mostrará cuando se
            apruebe el contrato backend–ML.
          </div>

          {recommendation ? (
            <>
              <div>
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <p className="text-xs font-bold text-[#4338CA]">Recomendación generada</p>
                  <span className="text-[11px] font-semibold text-[#4338CA] bg-[#E0E7FF] px-2 py-0.5 rounded-full">
                    {recommendationStatusLabels[recommendation.status]}
                  </span>
                </div>
                <p className="text-xs text-[#1E293B] leading-relaxed">{recommendation.content}</p>
              </div>

              {/* Fuentes RAG con fragmento */}
              <div>
                <p className="text-xs font-bold text-[#4338CA] mb-2">Fuentes consultadas (RAG)</p>
                {recommendation.sources.length === 0 ? (
                  <p className="text-xs text-[#64748B]">
                    La recomendación no tiene fuentes asociadas.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {recommendation.sources.map((source) => (
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
                          <span className="text-[#94A3B8] group-open:rotate-180 transition-transform">
                            ▾
                          </span>
                        </summary>
                        <div className="mt-1 px-3 py-2 bg-white border border-[#C7D2FE] border-t-0 rounded-b-lg text-[11px] text-[#475569] leading-relaxed italic">
                          &ldquo;{formatExcerpt(source.excerpt)}&rdquo;
                        </div>
                      </details>
                    ))}
                  </div>
                )}
              </div>

              {/* Acciones Human-in-the-loop: solo para recomendaciones sin revisar */}
              {recommendation.status === "pending" && (
                <div className="pt-2 border-t border-[#C7D2FE] space-y-2">
                  <p className="text-xs font-bold text-[#4338CA] mb-2">Acciones sugeridas</p>

                  <button className="w-full flex items-center justify-center gap-2 py-2.5 bg-[#16A3A1] hover:bg-[#0F8E8C] text-white text-xs font-semibold rounded-xl transition-colors">
                    ✓ Aceptar y Resolver
                  </button>

                  <button className="w-full flex items-center justify-center gap-2 py-2.5 bg-white border border-[#CBD5E1] hover:bg-[#F8FAFC] text-[#0F172A] text-xs font-semibold rounded-xl transition-colors">
                    ✏️ Editar
                  </button>

                  <button className="w-full flex items-center justify-center gap-2 py-2.5 bg-white border border-[#E2E8F0] hover:bg-[#F8FAFC] text-[#475569] text-xs font-semibold rounded-xl transition-colors">
                    🔄 Reintentar
                  </button>

                  <button className="w-full flex items-center justify-center gap-2 py-2.5 bg-white hover:bg-[#FEF2F2] text-[#EF4444] text-xs font-semibold rounded-xl transition-colors">
                    🗑️ Descartar
                  </button>
                </div>
              )}
            </>
          ) : (
            <p className="text-xs text-[#64748B]">Aún no hay recomendaciones para este ticket.</p>
          )}
        </div>
      </div>
    </div>
  );
}
