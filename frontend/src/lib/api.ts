import { ApiError, CsrfToken } from "@/types";
import { getAuthGeneration } from "./auth-sync";
import { clearCsrfToken, getCsrfToken } from "./csrf";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API_PREFIX = "/api/v1";

type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

interface RequestOptions<TBody = unknown> {
  method?: HttpMethod;
  body?: TBody;
  headers?: Record<string, string>;
  sameOrigin?: boolean;
}

const MUTATING_METHODS: ReadonlySet<HttpMethod> = new Set(["POST", "PUT", "PATCH", "DELETE"]);

class HttpError {
  constructor(
    readonly status: number,
    readonly body: ApiError
  ) {}
}

// Código solo del frontend (no viene del backend): la sesión cambió (login o logout, también en
// otra pestaña) mientras se preparaba la mutación, así que no se envía con un contexto distinto.
export const SESSION_CHANGED = "SESSION_CHANGED";

const sessionChangedError = (): ApiError => ({
  error: {
    code: SESSION_CHANGED,
    message: "La sesión cambió mientras se preparaba la solicitud.",
    details: null,
    requestId: "",
  },
});

async function send<TResponse, TBody>(
  endpoint: string,
  options: RequestOptions<TBody>,
  csrfToken?: string
): Promise<TResponse> {
  if (options.sameOrigin) {
    const response = await fetch(`${API_PREFIX}${endpoint}`, {
      method: options.method ?? "GET",
      credentials: "same-origin",
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
        ...options.headers,
      },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
    return readResponse<TResponse>(response);
  }
  const { method = "GET", body, headers = {} } = options;

  const config: RequestInit = {
    method,
    // Con el proxy de mismo origen, el navegador enviará la cookie de sesión.
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
      ...headers,
    },
  };

  if (body !== undefined) {
    config.body = JSON.stringify(body);
  }

  const response = await fetch(`${BASE_URL}${API_PREFIX}${endpoint}`, config);

  return readResponse<TResponse>(response);
}

async function readResponse<TResponse>(response: Response): Promise<TResponse> {
  if (!response.ok) {
    const errorBody: ApiError = await response.json().catch(() => ({
      error: {
        code: "UNKNOWN_ERROR",
        message: "Error desconocido",
        details: null,
        requestId: "",
      },
    }));
    throw new HttpError(response.status, errorBody);
  }

  // 204 No Content
  if (response.status === 204) {
    return undefined as TResponse;
  }

  return response.json() as Promise<TResponse>;
}

const fetchCsrfToken = (sameOrigin = false) =>
  send<CsrfToken, never>("/auth/csrf", { method: "GET", sameOrigin });

// Solo un 403 con código CSRF_INVALID permite el reintento: el mismo código con otro estado,
// u otro código con 403, no se reintentan.
function isCsrfInvalid(error: unknown): boolean {
  return (
    error instanceof HttpError && error.status === 403 && error.body.error.code === "CSRF_INVALID"
  );
}

async function request<TResponse, TBody = unknown>(
  endpoint: string,
  options: RequestOptions<TBody> = {}
): Promise<TResponse> {
  // Las mutaciones del navegador llevan X-CSRF-Token. En el servidor (SSR) solo hay lecturas.
  const needsCsrf = typeof window !== "undefined" && MUTATING_METHODS.has(options.method ?? "GET");

  try {
    if (!needsCsrf) return await send<TResponse, TBody>(endpoint, options);

    // La sesión no debe cambiar (ni login ni logout, tampoco en otra pestaña) entre que se pide
    // el token y se envía la mutación; si cambia, la mutación no se envía.
    const generation = getAuthGeneration();
    const token = await getCsrfToken(() => fetchCsrfToken(options.sameOrigin));
    if (getAuthGeneration() !== generation) throw sessionChangedError();
    try {
      return await send<TResponse, TBody>(endpoint, options, token);
    } catch (error) {
      // Único reintento permitido por el contrato: solo ante HTTP 403 + CSRF_INVALID y si la
      // sesión no cambió. Si el reintento también falla, se devuelve ese error sin reintentar más.
      if (!isCsrfInvalid(error) || getAuthGeneration() !== generation) throw error;
      clearCsrfToken();
      const freshToken = await getCsrfToken(() => fetchCsrfToken(options.sameOrigin));
      if (getAuthGeneration() !== generation) throw sessionChangedError();
      return await send<TResponse, TBody>(endpoint, options, freshToken);
    }
  } catch (error) {
    // Hacia afuera se mantiene el formato del contrato: { error: { code, message, ... } }.
    throw error instanceof HttpError ? error.body : error;
  }
}

export const api = {
  postSameOrigin: <TResponse, TBody = unknown>(endpoint: string, body: TBody) =>
    request<TResponse, TBody>(endpoint, { method: "POST", body, sameOrigin: true }),
  get: <TResponse>(endpoint: string, headers?: Record<string, string>) =>
    request<TResponse>(endpoint, { method: "GET", headers }),

  post: <TResponse, TBody = unknown>(endpoint: string, body: TBody) =>
    request<TResponse, TBody>(endpoint, { method: "POST", body }),

  put: <TResponse, TBody = unknown>(endpoint: string, body: TBody) =>
    request<TResponse, TBody>(endpoint, { method: "PUT", body }),

  patch: <TResponse, TBody = unknown>(endpoint: string, body: TBody) =>
    request<TResponse, TBody>(endpoint, { method: "PATCH", body }),

  delete: <TResponse>(endpoint: string) => request<TResponse>(endpoint, { method: "DELETE" }),
};
