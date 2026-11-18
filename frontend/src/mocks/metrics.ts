import type { MetricsService } from "@/services/metrics";
import { Metrics, Ticket, TicketStatus } from "@/types";
import { getMockTickets } from "./tickets";
import { simulateLatency } from "./utils";

function countTickets(tickets: readonly Ticket[], status: TicketStatus): number {
  return tickets.filter((ticket) => ticket.status === status).length;
}

// Resumen calculado a partir de los datos de ejemplo, para que coincida con el listado.
// Solo los conteos aprobados para el MVP, igual que el backend.
export const metricsMock: MetricsService = {
  getSummary: () => {
    const tickets = getMockTickets();
    const summary: Metrics = {
      totalTickets: tickets.length,
      openTickets: countTickets(tickets, "open"),
      inProgressTickets: countTickets(tickets, "in_progress"),
      resolvedTickets: countTickets(tickets, "resolved"),
      closedTickets: countTickets(tickets, "closed"),
    };
    return simulateLatency(summary);
  },
};
