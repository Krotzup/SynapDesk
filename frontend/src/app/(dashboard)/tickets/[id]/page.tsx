import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { AssistantPanel } from "@/components/recommendations/AssistantPanel";
import {
  TicketRecommendations,
  TicketRecommendationsFallback,
} from "@/components/recommendations/TicketRecommendations";
import { CurrentTicketStatus } from "@/components/tickets/CurrentTicketStatus";
import { TicketStatusControl } from "@/components/tickets/TicketStatusControl";
import { PriorityBadge } from "@/components/ui/Badge";
import { USE_MOCKS } from "@/lib/config";
import { isApiError } from "@/lib/errors";
import { MOCK_CONFLICT_TICKET_ID, MOCK_UNAVAILABLE_TICKET_ID } from "@/mocks/tickets";
import { formatDateTime, shortId } from "@/lib/format";
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
  // Las recomendaciones se cargan aparte (TicketRecommendations): si fallan, el detalle se
  // sigue mostrando.
  const ticket = await getTicket(id);

  return (
    // Bajo 1280 px, el margen derecho deja libre el botón fijo del Asistente IA.
    <div className="pl-4 pr-14 py-6 sm:pl-6 sm:pr-16 xl:p-6 bg-[#F8FAFC] min-h-screen">
      {/* Desde 1280 px, detalle y Asistente IA lado a lado; antes, una columna y el Asistente en un Drawer. */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 items-start max-w-7xl mx-auto">
        {/* Panel central: Detalle del ticket */}
        <div className="xl:col-span-2 space-y-6 bg-white p-4 sm:p-6 rounded-2xl border border-[#E2E8F0] shadow-sm">
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
            <CurrentTicketStatus ticketId={ticket.id} status={ticket.status} />
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

          {/* Cambio de estado (HU04): lo único editable del ticket en el MVP. */}
          <section
            aria-labelledby="estado-ticket"
            className="space-y-3 pt-4 border-t border-[#F1F5F9]"
          >
            <h2 id="estado-ticket" className="text-sm font-bold text-[#0F172A]">
              Estado del ticket
            </h2>
            {USE_MOCKS && (
              <p className="text-xs text-[#92400E] bg-[#FEF3C7] border border-[#FDE68A] rounded-xl px-3 py-2">
                <strong>Datos de ejemplo:</strong> el cambio de estado solo dura en esta pestaña y
                no aparece en el listado. Para ver los errores, cambia el estado de «Solicitud de
                notebook para nuevo integrante» (#{shortId(MOCK_CONFLICT_TICKET_ID)}, conflicto 409)
                o de «Impresora de recepción sin responder» (#
                {shortId(MOCK_UNAVAILABLE_TICKET_ID)}, servicio no disponible).
              </p>
            )}
            {/* La clave reinicia el control cuando el servidor entrega otro estado. */}
            <TicketStatusControl key={ticket.status} ticketId={ticket.id} status={ticket.status} />
          </section>
        </div>

        {/* Panel derecho: Asistente IA */}
        <AssistantPanel>
          {/* La predicción ML depende de las decisiones pendientes del contrato backend-ML */}
          <div className="p-3 bg-white border border-dashed border-[#C7D2FE] rounded-xl text-xs text-[#64748B]">
            La clasificación automática (categoría y prioridad estimadas) se mostrará cuando se
            apruebe el contrato backend–ML.
          </div>

          <Suspense fallback={<TicketRecommendationsFallback />}>
            <TicketRecommendations ticketId={ticket.id} />
          </Suspense>
        </AssistantPanel>
      </div>
    </div>
  );
}
