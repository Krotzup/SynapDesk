import { api } from "@/lib/api";
import { Ticket } from "@/types";

export const ticketsService = {
  getAll: (): Promise<Ticket[]> => api.get("/tickets"),

  getById: (id: string): Promise<Ticket> => api.get(`/tickets/${id}`),

  create: (data: Pick<Ticket, "title" | "description">): Promise<Ticket> =>
    api.post("/tickets", data),

  update: (id: string, data: Partial<Ticket>): Promise<Ticket> => api.patch(`/tickets/${id}`, data),

  delete: (id: string): Promise<void> => api.delete(`/tickets/${id}`),
};
