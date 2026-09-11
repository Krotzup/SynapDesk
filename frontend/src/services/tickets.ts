import { api } from "@/lib/api";
import { PaginatedResponse, PaginationParams, Ticket } from "@/types";

export const ticketsService = {
  getAll: (params?: PaginationParams): Promise<PaginatedResponse<Ticket>> => {
    const query = new URLSearchParams(params as Record<string, string>).toString();
    return api.get(`/tickets${query ? `?${query}` : ""}`);
  },

  getById: (id: string): Promise<Ticket> => api.get(`/tickets/${id}`),

  create: (data: Pick<Ticket, "title" | "description">): Promise<Ticket> =>
    api.post("/tickets", data),

  update: (
    id: string,
    data: Partial<
      Pick<
        Ticket,
        "title" | "description" | "status" | "priority" | "area" | "category" | "assignedTo"
      >
    >
  ): Promise<Ticket> => api.patch(`/tickets/${id}`, data),

  // Cierre o eliminación lógica
  delete: (id: string): Promise<void> => api.delete(`/tickets/${id}`),
};
