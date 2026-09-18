import { api } from "@/lib/api";
import { buildQuery } from "@/lib/params";
import { PaginatedResponse, PaginationParams, Ticket, TicketPriority, TicketStatus } from "@/types";

interface CreateTicketRequest {
  title: string;
  description: string;
}

// Usa assignedToId (UUID) en lugar del objeto User completo
interface UpdateTicketRequest {
  title?: string;
  description?: string;
  status?: TicketStatus;
  priority?: TicketPriority;
  category?: string | null;
  area?: string | null;
  assignedToId?: string | null;
}

export const ticketsService = {
  getAll: (params?: PaginationParams): Promise<PaginatedResponse<Ticket>> =>
    api.get(`/tickets${buildQuery(params)}`),

  getById: (id: string): Promise<Ticket> => api.get(`/tickets/${id}`),

  create: (data: CreateTicketRequest): Promise<Ticket> => api.post("/tickets", data),

  update: (id: string, data: UpdateTicketRequest): Promise<Ticket> =>
    api.patch(`/tickets/${id}`, data),

  // Cierre o eliminación lógica
  delete: (id: string): Promise<void> => api.delete(`/tickets/${id}`),
};
