import "server-only";

import type { ApiError } from "@/types";

// Canal de servidor hacia FastAPI, común al proxy de mismo origen y al adaptador SSR
// (lib/transport/server.ts). Sigue el contrato de autenticación V1, SEC-01B
// (docs/contratos/comunicacion-interna-segura-v1.md) y la especificación del PR #30
// (docs/contratos/integracion-http-pr30-pr32-v1.md, sección 3). Solo de servidor: el destino,
// la credencial de servicio y las listas permitidas nunca llegan al navegador.

export const API_PREFIX = "/api/v1";

// Plazo único para la operación completa: lectura de la petición del navegador, conexión y TLS,
// espera y lectura de la respuesta. Provisional (C06): no es un presupuesto productivo aprobado.
export const BACKEND_TIMEOUT_MS = 30_000;

// Límites provisionales de tamaño (C05/C06 pendientes de medición y acuerdo).
export const MAX_REQUEST_BODY_BYTES = 1024 * 1024;
export const MAX_RESPONSE_BODY_BYTES = 5 * 1024 * 1024;

const COOKIE_PROFILES = {
  // Nombres propuestos en el contrato de autenticación V1 (C02); aún no definitivos.
  local: ["synapdesk_session_dev", "synapdesk_csrf_context_dev"],
  production: ["__Host-synapdesk_session", "__Host-synapdesk_csrf_context"],
} as const;

// Nombres reservados de los dos perfiles. Hacia FastAPI se reenvían todas sus apariciones, tal
// como llegaron, para que el backend rechace una cookie mal formada, repetida o de otro perfil.
const RESERVED_COOKIE_NAMES: ReadonlySet<string> = new Set(Object.values(COOKIE_PROFILES).flat());

// Hacia FastAPI solo viajan estas cabeceras del navegador. Se descartan, entre otras, Host,
// Authorization, X-Forwarded-*, Forwarded, X-Real-IP, X-SynapDesk-Client-IP y X-Request-ID.
// Authorization la genera el servidor (credencial de servicio SEC-01B).
const FORWARDED_REQUEST_HEADERS = [
  "accept",
  "content-type",
  "origin",
  "sec-fetch-site",
  "x-csrf-token",
] as const;

// Hacia el navegador. Set-Cookie se copia aparte, una cabecera por cookie y solo las del perfil.
const FORWARDED_RESPONSE_HEADERS = ["content-type", "retry-after"] as const;

// Estados que no llevan cuerpo; también los usa el adaptador SSR.
export const BODYLESS_STATUS: ReadonlySet<number> = new Set([204, 205, 304]);

/**
 * Cookies de sesión y de contexto CSRF que el perfil activo acepta en las respuestas
 * (Set-Cookie). AUTH_COOKIE_PROFILE es obligatoria: ausente, vacía u otro valor distinto de
 * "local" o "production" es un error de configuración y devuelve null. No se elige un perfil en
 * silencio (C02).
 */
export function allowedCookieNames(): readonly string[] | null {
  const profile = process.env.AUTH_COOKIE_PROFILE;
  if (profile === "local" || profile === "production") return COOKIE_PROFILES[profile];
  return null;
}

/**
 * Origen de FastAPI según BACKEND_INTERNAL_URL, o null si no es válido. Se exige HTTPS (SEC-01B) y
 * que la variable sea exactamente el origen: sin usuario ni contraseña, ruta, query ni "#". No se
 * "repara" un valor dudoso tomando su origen.
 */
export function getBackendOrigin(): string | null {
  const value = process.env.BACKEND_INTERNAL_URL;
  if (!value) return null;
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    return null;
  }
  if (url.protocol !== "https:" || url.username || url.password) return null;
  if (value !== url.origin && value !== `${url.origin}/`) return null;
  return url.origin;
}

/**
 * Credencial de servicio SEC-01B desde BACKEND_SERVICE_CREDENTIAL (nombre provisional, C07):
 * exactamente 32 bytes en base64url canónico sin relleno (43 caracteres). null si falta o no
 * cumple el formato. Nunca se registra ni se devuelve al navegador.
 */
export function getServiceCredential(): string | null {
  const value = process.env.BACKEND_SERVICE_CREDENTIAL;
  if (!value || !/^[A-Za-z0-9_-]{43}$/.test(value)) return null;
  const bytes = Buffer.from(value, "base64url");
  return bytes.length === 32 && bytes.toString("base64url") === value ? value : null;
}

export interface BackendConfig {
  origin: string;
  /** Cookies del perfil activo que pueden volver al navegador en Set-Cookie. */
  cookieNames: ReadonlySet<string>;
  credential: string;
}

/**
 * Destino, perfil de cookies y credencial, comunes al proxy y al adaptador SSR. Si algo falta o
 * no es válido lo registra (solo el nombre de la variable, nunca su valor) y devuelve null: quien
 * llama responde 503 sin contactar al backend.
 */
export function getBackendConfig(source: "proxy" | "ssr"): BackendConfig | null {
  const origin = getBackendOrigin();
  if (!origin) {
    console.error(
      `[${source}] BACKEND_INTERNAL_URL no está configurada o no es un origen https:// válido.`
    );
  }
  const cookieNames = allowedCookieNames();
  if (!cookieNames) {
    console.error(
      `[${source}] AUTH_COOKIE_PROFILE falta o no es válida; usa "local" o "production".`
    );
  }
  const credential = getServiceCredential();
  if (!credential) {
    console.error(`[${source}] BACKEND_SERVICE_CREDENTIAL falta o no tiene el formato esperado.`);
  }
  return origin && cookieNames && credential
    ? { origin, cookieNames: new Set(cookieNames), credential }
    : null;
}

/**
 * Espacio opcional de las cabeceras Cookie y Set-Cookie: solo espacio y tabulador (RFC 6265 y
 * RFC 9110). No se usa trim(), que también quita U+00A0 y otros espacios Unicode: convertiría una
 * cookie no canónica (por ejemplo, "\u00A0synapdesk_session_dev=…") en una reservada válida.
 */
function stripOws(value: string): string {
  return value.replace(/^[ \t]+|[ \t]+$/g, "");
}

/**
 * Cabecera Cookie hacia FastAPI: solo las cookies con nombre reservado (de los dos perfiles), con
 * todas sus apariciones y sin modificarlas. Una cookie reservada sin "=", repetida, vacía o de
 * otro perfil no se descarta ni se elige un valor: llega al backend, que la rechaza (P1). Las
 * demás cookies del navegador no se reenvían.
 */
export function filterCookieHeader(
  cookieHeader: string | null,
  { preservePairEvidence = false } = {}
): string | null {
  if (!cookieHeader) return null;
  const kept = cookieHeader
    .split(";")
    .map((part) => (preservePairEvidence ? part.replace(/^[ \t]+/, "") : stripOws(part)))
    .filter((part) => {
      const separator = part.indexOf("=");
      const rawName = separator === -1 ? part : part.slice(0, separator);
      // En búsqueda se conserva incluso un nombre con espacio no canónico para
      // que FastAPI pueda rechazarlo junto con el resto de la evidencia.
      const name = preservePairEvidence
        ? rawName.replace(/^[\s\u0085]+|[\s\u0085]+$/g, "")
        : stripOws(rawName);
      return RESERVED_COOKIE_NAMES.has(name);
    });
  if (!kept.length) return null;
  const filtered = kept.join("; ");
  // Headers elimina OWS al final de la cabecera. Mantener un delimitador si
  // se filtró el par que seguía a un valor con espacios sin recortar.
  return preservePairEvidence && /[ \t]$/.test(filtered) ? `${filtered};` : filtered;
}

/** Nombre de la cookie de una cabecera Set-Cookie ("nombre=valor; atributos"). */
function setCookieName(setCookie: string): string {
  const separator = setCookie.indexOf("=");
  return separator > 0 ? stripOws(setCookie.slice(0, separator)) : "";
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

// 413 con un código existente del contrato; la clasificación definitiva depende de C05.
const requestTooLarge = () =>
  proxyError(413, backendApiError("VALIDATION_ERROR", "La solicitud supera el tamaño permitido."));

/**
 * Lee un cuerpo completo con un tope de bytes y dentro del plazo de la señal. Devuelve null si
 * supera el tope (sin seguir leyendo) y lanza si el plazo vence o la conexión se corta.
 */
export async function readLimited(
  stream: ReadableStream<Uint8Array> | null,
  limit: number,
  signal: AbortSignal
): Promise<Uint8Array<ArrayBuffer> | null> {
  if (!stream) return new Uint8Array(0);
  const reader = stream.getReader();
  const cancel = () => void reader.cancel().catch(() => {});
  if (signal.aborted) {
    cancel();
    throw signal.reason;
  }
  signal.addEventListener("abort", cancel, { once: true });
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > limit) {
        cancel();
        return null;
      }
      chunks.push(value);
    }
  } finally {
    signal.removeEventListener("abort", cancel);
  }
  if (signal.aborted) throw signal.reason;
  const body = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return body;
}

/** Motivo de un fallo del canal; el proxy y el SSR lo convierten en su error del contrato. */
export type BackendChannelFailure = "unavailable" | "redirect" | "response-too-large";

export class BackendChannelError extends Error {
  constructor(readonly reason: BackendChannelFailure) {
    super(`Fallo del canal hacia el backend: ${reason}`);
  }
}

export interface BackendRequest {
  method: string;
  /** Ruta con /api/v1 y query; el destino lo fija siempre la configuración. */
  path: string;
  headers: Headers;
  body?: Uint8Array<ArrayBuffer>;
  /** Solo el adaptador SSR de codigo puede delegar una lectura local acreditada. */
  localRead?: boolean;
}

/**
 * Llamada común hacia FastAPI. Agrega exactamente una cabecera Authorization con la credencial de
 * servicio (reemplaza cualquier valor previo), usa HTTPS con la verificación de certificado y
 * nombre de Node (sin desactivarla), no sigue redirecciones y lee la respuesta completa con tope
 * de tamaño dentro del plazo de la señal. Lanza BackendChannelError sin detalles internos.
 */
export async function callBackend(
  config: BackendConfig,
  request: BackendRequest,
  signal: AbortSignal
): Promise<{ response: Response; body: Uint8Array<ArrayBuffer> | null }> {
  const headers = new Headers(request.headers);
  headers.delete("authorization");
  headers.set("authorization", `Bearer ${config.credential}`);

  // Capacidad privada instalada solo por el lanzador testing; no procede de HTTP/env publico.
  const bridge = (
    process as unknown as Record<
      symbol,
      {
        localTesting?: boolean;
        attest: (
          method: string,
          path: string,
          headers: Headers,
          filter: typeof filterCookieHeader,
          ssr: boolean
        ) => string;
      }
    >
  )[Symbol.for("synapdesk.mvp04.ingress")];
  if (bridge?.localTesting === true) {
    headers.set(
      "x-synapdesk-ingress-evidence",
      bridge.attest(
        request.method,
        request.path,
        headers,
        filterCookieHeader,
        request.localRead === true
      )
    );
  }

  let response: Response;
  try {
    response = await fetch(`${config.origin}${request.path}`, {
      method: request.method,
      headers,
      body: request.body,
      // No seguir redirecciones: llevarían la credencial y las cookies a otro destino.
      redirect: "manual",
      cache: "no-store",
      signal,
    });
  } catch {
    // Backend apagado, sin red, certificado o nombre no válidos, o plazo vencido.
    throw new BackendChannelError("unavailable");
  }
  if (response.status >= 300 && response.status < 400) {
    await response.body?.cancel().catch(() => {});
    throw new BackendChannelError("redirect");
  }
  if (BODYLESS_STATUS.has(response.status)) {
    await response.body?.cancel().catch(() => {});
    return { response, body: null };
  }
  let body: Uint8Array<ArrayBuffer> | null;
  try {
    body = await readLimited(response.body, MAX_RESPONSE_BODY_BYTES, signal);
  } catch {
    // Plazo vencido o conexión cortada a mitad del cuerpo.
    throw new BackendChannelError("unavailable");
  }
  if (body === null) throw new BackendChannelError("response-too-large");
  return { response, body };
}

/** Reenvía la petición del navegador a FastAPI conservando /api/v1 y filtrando cabeceras. */
export async function proxyToBackend(request: Request, segments: string[]): Promise<Response> {
  const config = getBackendConfig("proxy");
  if (!config) return unavailable();

  // Next entrega los segmentos ya decodificados: se rechazan los que cambiarían la ruta.
  if (segments.length === 0 || segments.some((s) => s === "" || s === "." || s === "..")) {
    return proxyError(404, backendApiError("NOT_FOUND", "La ruta solicitada no existe."));
  }
  const path = `${API_PREFIX}/${segments.map(encodeURIComponent).join("/")}${new URL(request.url).search}`;

  const headers = new Headers();
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value !== null) headers.set(name, value);
  }
  const cookie = filterCookieHeader(request.headers.get("cookie"));
  if (cookie) headers.set("cookie", cookie);

  // El plazo empieza aquí y cubre también la lectura del cuerpo que envía el navegador.
  const signal = AbortSignal.timeout(BACKEND_TIMEOUT_MS);

  let body: Uint8Array<ArrayBuffer> | undefined;
  if (request.method !== "GET" && request.method !== "HEAD") {
    const declared = Number(request.headers.get("content-length"));
    if (declared > MAX_REQUEST_BODY_BYTES) return requestTooLarge();
    let read: Uint8Array<ArrayBuffer> | null;
    try {
      read = await readLimited(request.body, MAX_REQUEST_BODY_BYTES, signal);
    } catch {
      return unavailable();
    }
    if (read === null) return requestTooLarge();
    if (read.byteLength > 0) body = read;
  }

  let result: Awaited<ReturnType<typeof callBackend>>;
  try {
    result = await callBackend(config, { method: request.method, path, headers, body }, signal);
  } catch {
    return unavailable();
  }
  const { response } = result;

  const responseHeaders = new Headers({ "Cache-Control": "no-store" });
  for (const name of FORWARDED_RESPONSE_HEADERS) {
    const value = response.headers.get(name);
    if (value !== null) responseHeaders.set(name, value);
  }
  // Solo las cookies del perfil activo, cada una en su propia cabecera y sin modificar sus
  // atributos (también las de borrado). Las repetidas pasan todas: el proxy no las normaliza.
  let dropped = 0;
  for (const setCookie of response.headers.getSetCookie()) {
    if (config.cookieNames.has(setCookieName(setCookie))) {
      responseHeaders.append("set-cookie", setCookie);
    } else {
      dropped += 1;
    }
  }
  if (dropped > 0) {
    // Solo un conteo: ni nombres elegidos por el backend, ni valores, ni atributos.
    console.warn(`[proxy] Se descartaron ${dropped} Set-Cookie no permitidos por el perfil.`);
  }

  return new Response(result.body, { status: response.status, headers: responseHeaders });
}
