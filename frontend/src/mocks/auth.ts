import type { AuthService } from "@/services/auth";
import { AuthUser } from "@/types";
import { rejectWithApiError, simulateLatency } from "./utils";

// Inicio de sesión SIMULADO para desarrollar sin backend. No protege nada: la sesión de
// ejemplo se guarda en una cookie legible por el navegador, a diferencia de la real
// (HttpOnly y validada por FastAPI). Solo se usa con NEXT_PUBLIC_USE_MOCKS=true.

export const MOCK_PASSWORD = "demo1234";

export const mockAuthAccounts: AuthUser[] = [
  { id: "5b0e2a47-3c1d-4f6e-9a8b-7c6d5e4f3a21", email: "admin@synapdesk.local", role: "admin" },
  { id: "9d4c3b2a-1e0f-4a9b-8c7d-6e5f4a3b2c10", email: "agente@synapdesk.local", role: "agent" },
  // Cuenta para probar un fallo temporal: inicia sesión, pero /me responde 503.
  {
    id: "2f1e0d9c-8b7a-4c6d-9e5f-4a3b2c1d0e98",
    email: "sin-servicio@synapdesk.local",
    role: "agent",
  },
];

// Correos que fuerzan errores del login sin importar la contraseña.
const RATE_LIMITED_EMAIL = "limite-simulado@synapdesk.local";
const UNAVAILABLE_EMAIL = "error-simulado@synapdesk.local";
const UNSTABLE_EMAIL = "sin-servicio@synapdesk.local";

const SESSION_COOKIE = "synapdesk_mock_session";

function readSession(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${SESSION_COOKIE}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

function writeSession(userId: string | null) {
  if (typeof document === "undefined") return;
  document.cookie = userId
    ? `${SESSION_COOKIE}=${encodeURIComponent(userId)}; Path=/; SameSite=Lax`
    : `${SESSION_COOKIE}=; Path=/; Max-Age=0; SameSite=Lax`;
}

function unavailable() {
  return rejectWithApiError(
    "SERVICE_UNAVAILABLE",
    "El servicio no está disponible en este momento. Intenta nuevamente."
  );
}

export const authMock: AuthService = {
  getCsrf: () =>
    simulateLatency({
      csrfToken: `token-de-ejemplo-${crypto.randomUUID()}`,
      expiresAt: new Date(Date.now() + 10 * 60_000).toISOString(),
    }),

  login: ({ email, password }) => {
    // Normalización propuesta en el contrato: sin espacios exteriores y en minúsculas.
    // La contraseña no se modifica.
    const normalized = email.trim().toLowerCase();
    if (normalized === UNAVAILABLE_EMAIL) return unavailable();
    if (normalized === RATE_LIMITED_EMAIL) {
      return rejectWithApiError(
        "RATE_LIMITED",
        "Se superó el número de intentos permitido. Intenta más tarde."
      );
    }
    const user = mockAuthAccounts.find((account) => account.email === normalized);
    // Mismo error para cuenta inexistente y contraseña incorrecta, como exige el contrato.
    if (!user || password !== MOCK_PASSWORD) {
      return rejectWithApiError("INVALID_CREDENTIALS", "Correo o contraseña incorrectos.");
    }
    writeSession(user.id);
    return simulateLatency({ user });
  },

  me: () => {
    const user = mockAuthAccounts.find((account) => account.id === readSession());
    if (!user) {
      return rejectWithApiError("AUTHENTICATION_REQUIRED", "Debes iniciar sesión para continuar.");
    }
    if (user.email === UNSTABLE_EMAIL) return unavailable();
    return simulateLatency({ user });
  },

  logout: () => {
    writeSession(null);
    return simulateLatency(undefined);
  },
};
