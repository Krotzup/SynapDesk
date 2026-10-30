import { ticketsService } from "@/services/tickets";
import { Ticket, TicketStatus } from "@/types";

export interface TicketStatusSummary {
  total: number;
  open: number;
  inProgress: number;
  resolved: number;
}

// Tamaño de página usado para contar. Mientras el backend no ofrezca un resumen por
// estado, los conteos se calculan sobre los tickets de esta primera página.
const SUMMARY_PAGE_SIZE = 100;

function countByStatus(tickets: Ticket[], status: TicketStatus): number {
  return tickets.filter((ticket) => ticket.status === status).length;
}

/** Conteo de tickets por estado, compartido por el menú lateral y el listado. */
export async function getTicketStatusSummary(): Promise<TicketStatusSummary> {
  const { items, totalItems } = await ticketsService.getAll({ pageSize: SUMMARY_PAGE_SIZE });

  return {
    total: totalItems,
    open: countByStatus(items, "open"),
    inProgress: countByStatus(items, "in_progress"),
    resolved: countByStatus(items, "resolved"),
  };
}
