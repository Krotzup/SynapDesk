import type { MetricsService } from "@/services/metrics";
import { Metrics, RecommendationStatus, Ticket, TicketStatus } from "@/types";
import { getMockRecommendations } from "./recommendations";
import { getMockTickets } from "./tickets";
import { simulateLatency } from "./utils";

const HOUR_MS = 60 * 60 * 1000;

function countTickets(tickets: readonly Ticket[], status: TicketStatus): number {
  return tickets.filter((ticket) => ticket.status === status).length;
}

function countRecommendations(status: RecommendationStatus): number {
  return getMockRecommendations().filter((item) => item.status === status).length;
}

// Promedio de horas entre la creación y la resolución de los tickets resueltos.
function averageResolutionHours(tickets: readonly Ticket[]): number {
  const durations = tickets
    .filter((ticket) => ticket.resolvedAt)
    .map((ticket) => Date.parse(ticket.resolvedAt!) - Date.parse(ticket.createdAt));
  if (durations.length === 0) return 0;
  const average = durations.reduce((sum, value) => sum + value, 0) / durations.length / HOUR_MS;
  return Math.round(average * 10) / 10;
}

// Resumen calculado a partir de los datos de ejemplo, para que coincida con el listado.
export const metricsMock: MetricsService = {
  getSummary: () => {
    const tickets = getMockTickets();
    const summary: Metrics = {
      totalTickets: tickets.length,
      openTickets: countTickets(tickets, "open"),
      inProgressTickets: countTickets(tickets, "in_progress"),
      resolvedTickets: countTickets(tickets, "resolved"),
      avgResolutionTimeHours: averageResolutionHours(tickets),
      recommendationsAccepted: countRecommendations("accepted"),
      recommendationsModified: countRecommendations("modified"),
      recommendationsRejected: countRecommendations("rejected"),
    };
    return simulateLatency(summary);
  },
};
