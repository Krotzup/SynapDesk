import { api } from "@/lib/api";
import { PaginatedResponse, PaginationParams, User } from "@/types";

export const usersService = {
  getAll: (params?: PaginationParams): Promise<PaginatedResponse<User>> => {
    const query = new URLSearchParams(params as Record<string, string>).toString();
    return api.get(`/users${query ? `?${query}` : ""}`);
  },

  getById: (id: string): Promise<User> => api.get(`/users/${id}`),

  create: (data: Pick<User, "name" | "email" | "role">): Promise<User> => api.post("/users", data),

  update: (id: string, data: Partial<Pick<User, "name" | "role" | "isActive">>): Promise<User> =>
    api.patch(`/users/${id}`, data),

  // Desactivación lógica (no eliminación física)
  delete: (id: string): Promise<void> => api.delete(`/users/${id}`),
};
