import { api } from "@/lib/api";
import { USE_MOCKS } from "@/lib/config";
import { authMock } from "@/mocks/auth";
import { AuthResponse, CsrfToken } from "@/types";

export interface LoginRequest {
  email: string;
  password: string;
}

// Contrato de autenticación V1 (docs/contratos/autenticacion-v1.md), confirmado con el backend.
// La sesión viaja en una cookie HttpOnly que administra FastAPI: el frontend nunca la lee.
const authApi = {
  // 200 { csrfToken, expiresAt }. El cliente HTTP lo pide solo antes de una mutación.
  getCsrf: (): Promise<CsrfToken> => api.get("/auth/csrf"),

  // 200 { user }. Errores: INVALID_CREDENTIALS, RATE_LIMITED, CSRF_INVALID, ORIGIN_INVALID, 503.
  login: (data: LoginRequest): Promise<AuthResponse> =>
    api.post<AuthResponse, LoginRequest>("/auth/login", data),

  // 200 { user }, o 401 AUTHENTICATION_REQUIRED si no hay sesión válida.
  me: (): Promise<AuthResponse> => api.get("/auth/me"),

  // 204, también cuando no había sesión que cerrar.
  logout: (): Promise<void> => api.post("/auth/logout", {}),
};

export type AuthService = typeof authApi;

export const authService: AuthService = USE_MOCKS ? authMock : authApi;
