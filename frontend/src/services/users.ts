import { api } from "@/lib/api";
import { User } from "@/types";

export const usersService = {
  getAll: (): Promise<User[]> => api.get("/users"),

  getById: (id: string): Promise<User> => api.get(`/users/${id}`),

  update: (id: string, data: Partial<Pick<User, "name" | "role">>): Promise<User> =>
    api.patch(`/users/${id}`, data),

  delete: (id: string): Promise<void> => api.delete(`/users/${id}`),
};
