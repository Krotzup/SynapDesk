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
}

const MUTATING_METHODS: ReadonlySet<HttpMethod> = new Set(["POST", "PUT", "PATCH", "DELETE"]);

class HttpError {
  constructor(readonly body: ApiError) {}
}

async function send<TResponse, TBody>(
  endpoint: string,
  options: RequestOptions<TBody>,
  csrfToken?: string
): Promise<TResponse> {
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

  if (!response.ok) {
    const errorBody: ApiError = await response.json().catch(() => ({
      error: {
        code: "UNKNOWN_ERROR",
        message: "Error desconocido",
        details: null,
        requestId: "",
      },
    }));
    throw new HttpError(errorBody);
  }

  // 204 No Content
  if (response.status === 204) {
    return undefined as TResponse;
  }

  return response.json() as Promise<TResponse>;
}

const fetchCsrfToken = () => send<CsrfToken, never>("/auth/csrf", { method: "GET" });

function isCsrfInvalid(error: unknown): boolean {
  return error instanceof HttpError && error.body.error.code === "CSRF_INVALID";
}

async function request<TResponse, TBody = unknown>(
  endpoint: string,
  options: RequestOptions<TBody> = {}
): Promise<TResponse> {
  // Las mutaciones del navegador llevan X-CSRF-Token. En el servidor (SSR) solo hay lecturas.
  const needsCsrf = typeof window !== "undefined" && MUTATING_METHODS.has(options.method ?? "GET");

  try {
    if (!needsCsrf) return await send<TResponse, TBody>(endpoint, options);

    const generation = getAuthGeneration();
    try {
      return await send<TResponse, TBody>(endpoint, options, await getCsrfToken(fetchCsrfToken));
    } catch (error) {
      // Único reintento permitido por el contrato: solo ante 403 CSRF_INVALID y si la sesión
      // no cambió (ni login ni logout, tampoco en otra pestaña). Otros errores no se reintentan.
      if (!isCsrfInvalid(error) || getAuthGeneration() !== generation) throw error;
      clearCsrfToken();
      const freshToken = await getCsrfToken(fetchCsrfToken);
      if (getAuthGeneration() !== generation) throw error;
      return await send<TResponse, TBody>(endpoint, options, freshToken);
    }
  } catch (error) {
    // Hacia afuera se mantiene el formato del contrato: { error: { code, message, ... } }.
    throw error instanceof HttpError ? error.body : error;
  }
}

export const api = {
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
