import { api } from "@/lib/api";
import { USE_MOCKS } from "@/lib/config";
import { buildQuery } from "@/lib/params";
import { ticketsMock } from "@/mocks/tickets";
import { PaginatedResponse, PaginationParams, Ticket, TicketPriority, TicketStatus } from "@/types";

export interface CreateTicketRequest {
  title: string;
  description: string;
}

// Usa assignedToId (UUID) en lugar del objeto User completo
export interface UpdateTicketRequest {
  title?: string;
  description?: string;
  status?: TicketStatus;
  priority?: TicketPriority;
  category?: string | null;
  area?: string | null;
  assignedToId?: string | null;
}

const ticketsApi = {
  getAll: (params?: PaginationParams): Promise<PaginatedResponse<Ticket>> =>
    api.get(`/tickets${buildQuery(params)}`),

  getById: (id: string): Promise<Ticket> => api.get(`/tickets/${id}`),

  create: (data: CreateTicketRequest): Promise<Ticket> => api.post("/tickets", data),

  update: (id: string, data: UpdateTicketRequest): Promise<Ticket> =>
    api.patch(`/tickets/${id}`, data),

  // Cierre o eliminación lógica
  delete: (id: string): Promise<void> => api.delete(`/tickets/${id}`),
};

export type TicketsService = typeof ticketsApi;

export const ticketsService: TicketsService = USE_MOCKS ? ticketsMock : ticketsApi;
