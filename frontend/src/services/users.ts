import { api } from "@/lib/api";
import { buildQuery } from "@/lib/params";
import { PaginatedResponse, PaginationParams, Role, User } from "@/types";

interface CreateUserRequest {
  name: string;
  email: string;
  role: Role;
}

interface UpdateUserRequest {
  name?: string;
  role?: Role;
  isActive?: boolean;
}

export const usersService = {
  getAll: (params?: PaginationParams): Promise<PaginatedResponse<User>> =>
    api.get(`/users${buildQuery(params)}`),

  getById: (id: string): Promise<User> => api.get(`/users/${id}`),

  create: (data: CreateUserRequest): Promise<User> => api.post("/users", data),

  update: (id: string, data: UpdateUserRequest): Promise<User> => api.patch(`/users/${id}`, data),

  // Desactivación lógica (no eliminación física)
  delete: (id: string): Promise<void> => api.delete(`/users/${id}`),
};
