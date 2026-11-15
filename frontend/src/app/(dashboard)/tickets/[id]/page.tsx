import Link from "next/link";
import { notFound } from "next/navigation";
import { AssistantRecommendation } from "@/components/recommendations/AssistantRecommendation";
import { PriorityBadge, StatusBadge } from "@/components/ui/Badge";
import { isApiError } from "@/lib/errors";
import { formatDateTime, shortId } from "@/lib/format";
import { recommendationsService } from "@/services/recommendations";
import { ticketsService } from "@/services/tickets";
import { Ticket } from "@/types";

interface TicketDetailPageProps {
  params: Promise<{ id: string }>;
}

async function getTicket(id: string): Promise<Ticket> {
  try {
    return await ticketsService.getById(id);
  } catch (error) {
    if (isApiError(error) && error.error.code === "TICKET_NOT_FOUND") notFound();
    throw error;
  }
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

          {/* La clave reinicia el panel cuando el servidor entrega otra versión (router.refresh) */}
          <AssistantRecommendation
            key={recommendation ? `${recommendation.id}:${recommendation.status}` : "none"}
            ticketId={ticket.id}
            initialRecommendation={recommendation}
          />
        </div>
      </div>
    </div>
  );
}
