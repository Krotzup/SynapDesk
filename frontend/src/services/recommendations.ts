import { api } from "@/lib/api";
import { Recommendation } from "@/types";

export const recommendationsService = {
  getByTicket: (ticketId: string): Promise<Recommendation> =>
    api.get(`/tickets/${ticketId}/recommendation`),

  accept: (id: string): Promise<Recommendation> =>
    api.patch(`/recommendations/${id}`, { status: "accepted" }),

  reject: (id: string): Promise<Recommendation> =>
    api.patch(`/recommendations/${id}`, { status: "rejected" }),

  modify: (id: string, modifiedContent: string): Promise<Recommendation> =>
    api.patch(`/recommendations/${id}`, { status: "modified", modifiedContent }),
};
