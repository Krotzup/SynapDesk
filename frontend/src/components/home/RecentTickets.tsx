import Link from "next/link";
import { connection } from "next/server";
import { PriorityBadge, StatusBadge } from "@/components/ui/Badge";
import { formatDateTime, shortId } from "@/lib/format";
import { ticketsService } from "@/services/tickets";
import { SectionError } from "./SectionError";

const RECENT_TICKETS_COUNT = 5;

/**
 * Últimos tickets registrados. No envía sort ni order: el contrato aún no define sus
 * valores, y se espera que GET /tickets devuelva primero los más recientes, como el mock.
 */
export async function RecentTickets() {
  await connection();

  const result = await ticketsService
    .getAll({ page: 1, pageSize: RECENT_TICKETS_COUNT })
    .catch(() => null);

  if (!result) {
    return <SectionError message="No se pudieron cargar los tickets recientes." />;
  }
  if (result.items.length === 0) {
    return (
      <p className="py-6 text-center text-sm text-[#94A3B8]">
        Todavía no hay tickets registrados.{" "}
        <Link href="/tickets/nuevo" className="text-[#2563EB] hover:underline">
          Crear el primero
        </Link>
      </p>
    );
  }

  return (
    <ul className="divide-y divide-[#F1F5F9]">
      {result.items.map((ticket) => (
        <li
          key={ticket.id}
          className="py-3.5 flex items-center justify-between gap-4 hover:bg-[#F8FAFC] px-2 rounded-xl transition-colors"
        >
          <div className="space-y-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-bold text-[#2563EB]" title={ticket.id}>
                #{shortId(ticket.id)}
              </span>
              <span className="whitespace-nowrap">
                <StatusBadge status={ticket.status} />
              </span>
              <span className="whitespace-nowrap">
                <PriorityBadge priority={ticket.priority} />
              </span>
            </div>
            <p className="text-sm font-semibold text-[#0F172A] truncate">{ticket.title}</p>
            <p className="text-xs text-[#94A3B8]">
              {ticket.createdBy.name} ·{" "}
              <span className="whitespace-nowrap">{formatDateTime(ticket.createdAt)}</span>
            </p>
          </div>
          <Link
            href={`/tickets/${ticket.id}`}
            className="shrink-0 whitespace-nowrap text-xs font-semibold text-[#2563EB] bg-[#EFF6FF] hover:bg-[#DBEAFE] px-3 py-1.5 rounded-lg transition-colors"
          >
            Atender →
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** Marcador mientras llegan los tickets. */
export function RecentTicketsFallback() {
  return (
    <ul className="divide-y divide-[#F1F5F9]" aria-busy="true" aria-label="Cargando tickets">
      {Array.from({ length: RECENT_TICKETS_COUNT }, (_, index) => (
        <li key={index} className="py-3.5 px-2 space-y-2 animate-pulse">
          <div className="h-3 w-40 rounded bg-[#F1F5F9]" />
          <div className="h-4 w-3/4 rounded bg-[#F1F5F9]" />
        </li>
      ))}
    </ul>
  );
}
