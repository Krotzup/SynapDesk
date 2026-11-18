import {
  API_PREFIX,
  BACKEND_TIMEOUT_MS,
  callBackend,
  filterCookieHeader,
  getBackendConfig,
  readLimited,
} from "../backend-proxy";
import { parseSearchResponse } from "../search-contract";

export interface SearchProxyConfig {
  publicOrigin?: string;
  sessionCookieName?: string;
}

const noStore = { "Cache-Control": "no-store" };
const MAX_SEARCH_BODY_BYTES = 8192;
const messages: Record<string, string> = {
  SERVICE_UNAVAILABLE: "El servicio no está disponible en este momento.",
  AUTHENTICATION_REQUIRED: "Debes iniciar sesión para buscar en los documentos.",
  ORIGIN_INVALID: "El origen de la solicitud no está permitido.",
  CSRF_INVALID: "No se pudo validar el contexto de seguridad. Inténtalo nuevamente.",
  VALIDATION_ERROR: "Revisa la consulta y la cantidad de resultados.",
  QUERY_TOKEN_LIMIT_EXCEEDED:
    "La consulta supera los 128 tokens del modelo. Acórtala sin perder el problema principal.",
  SEARCH_PROFILE_STALE: "La base de conocimientos cambió; el servicio debe recalibrarse.",
  SEARCH_NOT_READY: "La base de conocimientos todavía no está preparada.",
  SEARCH_CONFIGURATION_ERROR: "La búsqueda requiere una configuración de base independiente.",
  SEARCH_UNAVAILABLE: "La búsqueda no está disponible temporalmente.",
  DEPENDENCY_UNAVAILABLE: "No se pudo verificar la sesión temporalmente.",
  RATE_LIMITED: "Se alcanzó el límite de solicitudes. Espera antes de volver a buscar.",
};

function failure(
  status: number,
  code: string,
  requestId: string = crypto.randomUUID(),
  message = messages[code] ?? messages.SEARCH_UNAVAILABLE
) {
  return Response.json(
    {
      error: {
        code,
        message,
        details: null,
        requestId,
      },
    },
    { status, headers: noStore }
  );
}

function rateLimited(response: Response, requestId: string | undefined) {
  const retryAfter = response.headers.get("retry-after");
  if (
    retryAfter &&
    (/^[0-9]{1,10}$/.test(retryAfter) ||
      (Number.isFinite(Date.parse(retryAfter)) &&
        new Date(retryAfter).toUTCString() === retryAfter))
  ) {
    const seconds = /^[0-9]+$/.test(retryAfter)
      ? Number(retryAfter)
      : Math.max(0, Math.ceil((Date.parse(retryAfter) - Date.now()) / 1000));
    const message =
      seconds > 0
        ? `Se alcanzó el límite de solicitudes. Vuelve a buscar en ${seconds} ${seconds === 1 ? "segundo" : "segundos"}.`
        : messages.RATE_LIMITED;
    const result = failure(429, "RATE_LIMITED", requestId, message);
    result.headers.set("Retry-After", retryAfter);
    return result;
  }
  return failure(429, "RATE_LIMITED", requestId);
}

function validPublicOrigin(value: string | undefined, localProfile: boolean): boolean {
  if (!value || !URL.canParse(value)) return false;
  const origin = new URL(value);
  if (origin.origin !== value) return false;
  const publicLocal = ["localhost", "127.0.0.1", "[::1]"].includes(origin.hostname);
  return (
    origin.protocol === "https:" || (origin.protocol === "http:" && publicLocal && localProfile)
  );
}

export async function forwardSemanticSearch(
  request: Request,
  config: SearchProxyConfig
): Promise<Response> {
  const backend = getBackendConfig("proxy");
  if (!backend) return failure(503, "SERVICE_UNAVAILABLE");
  // En el perfil común, la sesión precede a la cookie de contexto.
  const [cookieName] = backend.cookieNames;
  if (
    !validPublicOrigin(config.publicOrigin, process.env.AUTH_COOKIE_PROFILE === "local") ||
    (config.sessionCookieName !== undefined && config.sessionCookieName !== cookieName)
  ) {
    return failure(503, "SERVICE_UNAVAILABLE");
  }
  if (request.method !== "POST") return failure(405, "VALIDATION_ERROR");
  if (request.headers.get("origin") !== config.publicOrigin) return failure(403, "ORIGIN_INVALID");
  const cookie = filterCookieHeader(request.headers.get("cookie"), { preservePairEvidence: true });
  if (!cookie) {
    return failure(401, "AUTHENTICATION_REQUIRED");
  }
  const csrf = request.headers.get("x-csrf-token");
  if (!csrf || csrf.length > 4096 || csrf.includes(",")) return failure(403, "CSRF_INVALID");
  const signal = AbortSignal.timeout(BACKEND_TIMEOUT_MS);
  const decoder = new TextDecoder("utf-8", { fatal: true });
  let payload: { query: string; limit: number };
  try {
    if (!(request.headers.get("content-type") ?? "").toLowerCase().startsWith("application/json"))
      throw new Error();
    const bytes = await readLimited(request.body, MAX_SEARCH_BODY_BYTES, signal);
    if (bytes === null) throw new Error();
    const body = JSON.parse(decoder.decode(bytes));
    if (
      !body ||
      typeof body !== "object" ||
      Object.keys(body).some((key) => !["query", "limit"].includes(key)) ||
      typeof body.query !== "string" ||
      !body.query.trim() ||
      Array.from(body.query.trim()).length > 1000 ||
      (body.limit !== undefined &&
        (!Number.isInteger(body.limit) || body.limit < 1 || body.limit > 20))
    )
      throw new Error();
    payload = { query: body.query.trim(), limit: body.limit ?? 5 };
  } catch {
    if (signal.aborted) return failure(503, "SERVICE_UNAVAILABLE");
    return failure(422, "VALIDATION_ERROR");
  }
  const headers = new Headers({
    "Content-Type": "application/json",
    Cookie: cookie,
    Origin: request.headers.get("origin")!,
    "X-CSRF-Token": csrf,
  });
  const site = request.headers.get("sec-fetch-site");
  if (site) headers.set("Sec-Fetch-Site", site);
  try {
    const { response, body: bytes } = await callBackend(
      backend,
      {
        method: "POST",
        path: `${API_PREFIX}/search`,
        headers,
        body: new TextEncoder().encode(JSON.stringify(payload)),
      },
      signal
    );
    const body = JSON.parse(decoder.decode(bytes ?? undefined));
    if (!response.ok) {
      const code = body?.error?.code;
      const id = body?.error?.requestId;
      const requestId = typeof id === "string" && /^[0-9a-f-]{36}$/i.test(id) ? id : undefined;
      if (response.status === 429 && code === "RATE_LIMITED") {
        return rateLimited(response, requestId);
      }
      if (
        [401, 403, 422, 503].includes(response.status) &&
        typeof code === "string" &&
        Object.hasOwn(messages, code)
      ) {
        return failure(response.status, code, requestId);
      }
      return failure(503, "SERVICE_UNAVAILABLE");
    }
    return Response.json(parseSearchResponse(body), { headers: noStore });
  } catch {
    return failure(503, "SERVICE_UNAVAILABLE");
  }
}
