import { api } from "@/lib/api";
import { USE_MOCKS } from "@/lib/config";
import { buildQuery } from "@/lib/params";
import { ticketsMock } from "@/mocks/tickets";
import { PaginatedResponse, Ticket, TicketListParams, TicketStatus } from "@/types";

export interface CreateTicketRequest {
  title: string;
  description: string;
}

const ticketsApi = {
  getAll: (params?: TicketListParams): Promise<PaginatedResponse<Ticket>> =>
    api.get(`/tickets${buildQuery(params)}`),

  getById: (id: string): Promise<Ticket> => api.get(`/tickets/${id}`),

  create: (data: CreateTicketRequest): Promise<Ticket> => api.post("/tickets", data),

  // Solo el estado (MVP02): asignación, edición libre y borrado no están aprobados.
  updateStatus: (id: string, data: { status: TicketStatus }): Promise<Ticket> =>
    api.patch(`/tickets/${id}`, data),
};

export type TicketsService = typeof ticketsApi;

export const ticketsService: TicketsService = USE_MOCKS ? ticketsMock : ticketsApi;
