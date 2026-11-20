// Componentes de servidor: directo a BACKEND_INTERNAL_URL con las cookies permitidas (SSR).
// Componentes cliente: rutas relativas /api/v1/* hacia el proxy de mismo origen.
// Next elige el archivo según la condición "react-server" (ver "imports" en package.json).
import { getTransport } from "#transport";
import { ApiError, CsrfToken } from "@/types";
import { getAuthGeneration } from "./auth-sync";
import { SESSION_CHANGED } from "./errors";
import { clearCsrfToken, getCsrfToken } from "./csrf";

const API_PREFIX = "/api/v1";

type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

interface RequestOptions<TBody = unknown> {
  method?: HttpMethod;
  body?: TBody;
  headers?: Record<string, string>;
}

const MUTATING_METHODS: ReadonlySet<HttpMethod> = new Set(["POST", "PUT", "PATCH", "DELETE"]);

class HttpError {
  constructor(
    readonly status: number,
    readonly body: ApiError
  ) {}
}

// Se conserva la exportación desde aquí para los componentes que ya la importan de api.
export { SESSION_CHANGED };

const sessionChangedError = (): ApiError => ({
  error: {
    code: SESSION_CHANGED,
    message: "La sesión cambió mientras se preparaba la solicitud.",
    details: null,
    requestId: crypto.randomUUID(),
  },
});

async function send<TResponse, TBody>(
  endpoint: string,
  options: RequestOptions<TBody>,
  csrfToken?: string,
  prefix = API_PREFIX
): Promise<TResponse> {
  const { method = "GET", body, headers = {} } = options;
  const transport = await getTransport();

  const config: RequestInit = {
    method,
    // Con el proxy de mismo origen, el navegador envía la cookie de sesión.
    credentials: "same-origin",
    // Respuestas privadas: sin caché compartida entre usuarios.
    cache: "no-store",
    headers: {
      ...(body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
      ...headers,
      ...transport.headers,
    },
  };

  if (body !== undefined) {
    config.body = body instanceof FormData ? body : JSON.stringify(body);
  }

  const response = await transport.fetch(`${transport.baseUrl}${prefix}${endpoint}`, config);

  return readResponse<TResponse>(response);
}

async function readResponse<TResponse>(response: Response): Promise<TResponse> {
  if (!response.ok) {
    // Si la respuesta no trae el formato del contrato, se genera un error con requestId propio.
    const errorBody: ApiError = await response.json().catch(() => ({
      error: {
        code: "UNKNOWN_ERROR",
        message: "Error desconocido",
        details: null,
        requestId: crypto.randomUUID(),
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

const fetchCsrfToken = () =>
  process.env.NEXT_PUBLIC_TRUSTED_LOCAL_INGRESS === "true"
    ? send<CsrfToken, never>("/csrf", { method: "POST" }, undefined, "/api/local")
    : send<CsrfToken, never>("/auth/csrf", { method: "GET" });

// P8: descartar un token rechazado para que la próxima acción manual lo renueve.
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
    const token = await getCsrfToken(fetchCsrfToken);
    if (getAuthGeneration() !== generation) throw sessionChangedError();
    try {
      return await send<TResponse, TBody>(endpoint, options, token);
    } catch (error) {
      if (isCsrfInvalid(error) && getAuthGeneration() === generation) clearCsrfToken();
      throw error;
    }
  } catch (error) {
    // Hacia afuera se mantiene el formato del contrato ({ error: { code, message, ... } }) y se
    // agrega el estado HTTP, que el cuerpo no trae (409 y 503 se distinguen por estado).
    throw error instanceof HttpError ? { ...error.body, status: error.status } : error;
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
