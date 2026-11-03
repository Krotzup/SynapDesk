import "server-only";

// Reglas del proxy de mismo origen hacia FastAPI (contrato de autenticación V1, sección 3).
// Solo de servidor: el destino y las listas permitidas nunca llegan al navegador.

export const API_PREFIX = "/api/v1";

// Pensado para la generación de recomendaciones con LLM; provisional.
const TIMEOUT_MS = 30_000;

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

// Hacia el navegador. Set-Cookie se copia aparte, una cabecera por cookie.
const FORWARDED_RESPONSE_HEADERS = ["content-type", "retry-after"] as const;

const BODYLESS_STATUS = new Set([204, 205, 304]);

/** Cookies de sesión y de contexto CSRF del entorno (AUTH_COOKIE_PROFILE, "local" por defecto). */
export function allowedCookieNames(): readonly string[] {
  return process.env.AUTH_COOKIE_PROFILE === "production"
    ? COOKIE_PROFILES.production
    : COOKIE_PROFILES.local;
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

/**
 * Deja en la cabecera Cookie solo las cookies permitidas. Si una viene repetida se conservan todas
 * sus apariciones: el backend rechaza la ambigüedad, el proxy no elige una.
 */
export function filterCookieHeader(cookieHeader: string | null): string | null {
  if (!cookieHeader) return null;
  const allowed = new Set(allowedCookieNames());
  const kept = cookieHeader
    .split(";")
    .map((part) => part.trim())
    .filter((part) => {
      const separator = part.indexOf("=");
      return separator > 0 && allowed.has(part.slice(0, separator).trim());
    });
  return kept.length > 0 ? kept.join("; ") : null;
}

function proxyError(status: number, code: string, message: string): Response {
  return Response.json(
    { error: { code, message, details: null, requestId: crypto.randomUUID() } },
    { status, headers: { "Cache-Control": "no-store" } }
  );
}

export const ALLOWED_METHODS = "DELETE, GET, PATCH, POST, PUT";

/** Respuesta para los métodos que el proxy no reenvía. */
export function methodNotAllowed(): Response {
  const response = proxyError(405, "METHOD_NOT_ALLOWED", "Método no permitido.");
  response.headers.set("Allow", ALLOWED_METHODS);
  return response;
}

const unavailable = () =>
  proxyError(503, "SERVICE_UNAVAILABLE", "El servicio no está disponible en este momento.");

/** Reenvía la petición del navegador a FastAPI conservando /api/v1 y filtrando cabeceras. */
export async function proxyToBackend(request: Request, segments: string[]): Promise<Response> {
  const backend = getBackendOrigin();
  if (!backend) {
    console.error("[proxy] BACKEND_INTERNAL_URL no está configurada o no es una URL http(s).");
    return unavailable();
  }

  // Next entrega los segmentos ya decodificados: se rechazan los que cambiarían la ruta.
  if (segments.length === 0 || segments.some((s) => s === "" || s === "." || s === "..")) {
    return proxyError(404, "NOT_FOUND", "La ruta solicitada no existe.");
  }
  const path = segments.map(encodeURIComponent).join("/");
  const target = `${backend}${API_PREFIX}/${path}${new URL(request.url).search}`;

  const headers = new Headers();
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value !== null) headers.set(name, value);
  }
  const cookie = filterCookieHeader(request.headers.get("cookie"));
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
      signal: AbortSignal.timeout(TIMEOUT_MS),
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
  for (const setCookie of response.headers.getSetCookie()) {
    responseHeaders.append("set-cookie", setCookie);
  }

  return new Response(BODYLESS_STATUS.has(response.status) ? null : response.body, {
    status: response.status,
    headers: responseHeaders,
  });
}
