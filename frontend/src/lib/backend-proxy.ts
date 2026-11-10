import "server-only";

import type { ApiError } from "@/types";

// Reglas del proxy de mismo origen hacia FastAPI (contrato de autenticación V1, sección 3).
// Solo de servidor: el destino y las listas permitidas nunca llegan al navegador.

export const API_PREFIX = "/api/v1";

// Pensado para la generación de recomendaciones con LLM; provisional. También lo usa el
// adaptador SSR (lib/transport/server.ts).
export const BACKEND_TIMEOUT_MS = 30_000;

const COOKIE_PROFILES = {
  // Nombres propuestos en el contrato de autenticación V1 (sección 6); aún no definitivos.
  local: ["synapdesk_session_dev", "synapdesk_csrf_context_dev"],
  production: ["__Host-synapdesk_session", "__Host-synapdesk_csrf_context"],
} as const;

// Hacia FastAPI solo viajan estas cabeceras. Se descartan, entre otras, X-Forwarded-*,
// Forwarded, X-Real-IP, X-SynapDesk-Client-IP, Authorization y Host enviadas por el navegador.
const FORWARDED_REQUEST_HEADERS = [
  "accept",
  "content-type",
  "origin",
  "sec-fetch-site",
  "x-csrf-token",
] as const;

// Hacia el navegador. Set-Cookie se copia aparte, una cabecera por cookie y solo las del perfil.
const FORWARDED_RESPONSE_HEADERS = ["content-type", "retry-after"] as const;

const BODYLESS_STATUS = new Set([204, 205, 304]);

/**
 * Cookies de sesión y de contexto CSRF según AUTH_COOKIE_PROFILE. Si la variable no existe se usa
 * "local". Un valor distinto de "local" o "production" (también vacío) es un error de
 * configuración: devuelve null y no se elige otro perfil en silencio.
 */
export function allowedCookieNames(): readonly string[] | null {
  const profile = process.env.AUTH_COOKIE_PROFILE;
  if (profile === undefined) return COOKIE_PROFILES.local;
  if (profile === "local" || profile === "production") return COOKIE_PROFILES[profile];
  return null;
}

/** Origen de FastAPI según BACKEND_INTERNAL_URL, o null si falta o no es una URL http(s). */
export function getBackendOrigin(): string | null {
  const value = process.env.BACKEND_INTERNAL_URL;
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? url.origin : null;
  } catch {
    return null;
  }
}

export interface BackendConfig {
  origin: string;
  cookieNames: ReadonlySet<string>;
}

/**
 * Destino y cookies permitidas, comunes al proxy y al adaptador SSR. Si algo no es válido lo
 * registra (sin valores secretos) y devuelve null: quien llama responde 503.
 */
export function getBackendConfig(source: "proxy" | "ssr"): BackendConfig | null {
  const origin = getBackendOrigin();
  if (!origin) {
    console.error(`[${source}] BACKEND_INTERNAL_URL no está configurada o no es una URL http(s).`);
  }
  const cookieNames = allowedCookieNames();
  if (!cookieNames) {
    console.error(
      `[${source}] AUTH_COOKIE_PROFILE tiene un valor no válido; usa "local" o "production".`
    );
  }
  return origin && cookieNames ? { origin, cookieNames: new Set(cookieNames) } : null;
}

/**
 * Deja en la cabecera Cookie solo las cookies permitidas. Si una viene repetida se conservan todas
 * sus apariciones: el backend rechaza la ambigüedad, el proxy no elige una.
 */
export function filterCookieHeader(
  cookieHeader: string | null,
  allowed: ReadonlySet<string>
): string | null {
  if (!cookieHeader) return null;
  const kept = cookieHeader
    .split(";")
    .map((part) => part.trim())
    .filter((part) => {
      const separator = part.indexOf("=");
      return separator > 0 && allowed.has(part.slice(0, separator).trim());
    });
  return kept.length > 0 ? kept.join("; ") : null;
}

/** Nombre de la cookie de una cabecera Set-Cookie ("nombre=valor; atributos"). */
function setCookieName(setCookie: string): string {
  const separator = setCookie.indexOf("=");
  return separator > 0 ? setCookie.slice(0, separator).trim() : "";
}

/**
 * Error del contrato (ApiErrorBody) con un requestId nuevo generado en el servidor. No se reutiliza
 * ningún identificador enviado por el navegador.
 */
export function backendApiError(code: string, message: string): ApiError {
  return { error: { code, message, details: null, requestId: crypto.randomUUID() } };
}

export const serviceUnavailableError = () =>
  backendApiError("SERVICE_UNAVAILABLE", "El servicio no está disponible en este momento.");

function proxyError(status: number, body: ApiError): Response {
  return Response.json(body, { status, headers: { "Cache-Control": "no-store" } });
}

export const ALLOWED_METHODS = "DELETE, GET, PATCH, POST, PUT";

/** Respuesta para los métodos que el proxy no reenvía. */
export function methodNotAllowed(): Response {
  const response = proxyError(405, backendApiError("METHOD_NOT_ALLOWED", "Método no permitido."));
  response.headers.set("Allow", ALLOWED_METHODS);
  return response;
}

const unavailable = () => proxyError(503, serviceUnavailableError());

/** Reenvía la petición del navegador a FastAPI conservando /api/v1 y filtrando cabeceras. */
export async function proxyToBackend(request: Request, segments: string[]): Promise<Response> {
  const config = getBackendConfig("proxy");
  if (!config) return unavailable();

  // Next entrega los segmentos ya decodificados: se rechazan los que cambiarían la ruta.
  if (segments.length === 0 || segments.some((s) => s === "" || s === "." || s === "..")) {
    return proxyError(404, backendApiError("NOT_FOUND", "La ruta solicitada no existe."));
  }
  const path = segments.map(encodeURIComponent).join("/");
  const target = `${config.origin}${API_PREFIX}/${path}${new URL(request.url).search}`;

  const headers = new Headers();
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value !== null) headers.set(name, value);
  }
  const cookie = filterCookieHeader(request.headers.get("cookie"), config.cookieNames);
  if (cookie) headers.set("cookie", cookie);

  let body: ArrayBuffer | undefined;
  if (request.method !== "GET" && request.method !== "HEAD") {
    const buffer = await request.arrayBuffer();
    if (buffer.byteLength > 0) body = buffer;
  }

  let response: Response;
  try {
    response = await fetch(target, {
      method: request.method,
      headers,
      body,
      // No seguir redirecciones: podrían llevar las cookies a otro host.
      redirect: "manual",
      cache: "no-store",
      signal: AbortSignal.timeout(BACKEND_TIMEOUT_MS),
    });
  } catch {
    // Backend apagado, sin red o tiempo de espera agotado.
    return unavailable();
  }

  if (response.status >= 300 && response.status < 400) {
    await response.body?.cancel();
    return unavailable();
  }

  const responseHeaders = new Headers({ "Cache-Control": "no-store" });
  for (const name of FORWARDED_RESPONSE_HEADERS) {
    const value = response.headers.get(name);
    if (value !== null) responseHeaders.set(name, value);
  }
  // Solo las cookies del perfil activo, cada una en su propia cabecera y sin modificar sus
  // atributos (también las de borrado). Las repetidas pasan todas: el proxy no las normaliza.
  const dropped: string[] = [];
  for (const setCookie of response.headers.getSetCookie()) {
    const name = setCookieName(setCookie);
    if (config.cookieNames.has(name)) responseHeaders.append("set-cookie", setCookie);
    else dropped.push(name || "(sin nombre)");
  }
  if (dropped.length > 0) {
    // Solo los nombres: nunca valores ni atributos.
    console.warn(`[proxy] Set-Cookie no permitido descartado: ${dropped.join(", ")}.`);
  }

  return new Response(BODYLESS_STATUS.has(response.status) ? null : response.body, {
    status: response.status,
    headers: responseHeaders,
  });
}
