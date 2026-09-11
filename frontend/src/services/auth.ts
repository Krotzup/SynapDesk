import { api } from "@/lib/api";
import { User } from "@/types";

interface LoginRequest {
  email: string;
  password: string;
}

// El mecanismo definitivo de autenticación está pendiente de decisión técnica.
// Estas rutas son provisionales según el contrato inicial frontend-backend.
export const authService = {
  login: (data: LoginRequest): Promise<unknown> => api.post("/auth/login", data),

  logout: (): Promise<void> => api.post("/auth/logout", {}),

  me: (): Promise<User> => api.get("/auth/me"),
};
