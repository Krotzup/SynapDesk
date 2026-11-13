import { parseSearchResponse } from "../search-contract";

export interface SearchProxyConfig {
  backendUrl?: string;
  publicOrigin?: string;
  sessionCookieName?: string;
  cookieProfile?: string;
  allowHttpLocal?: boolean;
}

const noStore = { "Cache-Control": "no-store" };
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

function failure(status: number, code: string, requestId: string = crypto.randomUUID()) {
  return Response.json(
    {
      error: {
        code,
        message: messages[code] ?? messages.SEARCH_UNAVAILABLE,
        details: null,
        requestId,
      },
    },
    { status, headers: noStore }
  );
}

function rateLimited(response: Response, requestId: string | undefined) {
  const result = failure(429, "RATE_LIMITED", requestId);
  const retryAfter = response.headers.get("retry-after");
  if (
    retryAfter &&
    (/^[0-9]{1,10}$/.test(retryAfter) ||
      (Number.isFinite(Date.parse(retryAfter)) &&
        new Date(retryAfter).toUTCString() === retryAfter))
  ) {
    result.headers.set("Retry-After", retryAfter);
  }
  return result;
}

function sessionCookieName(config: SearchProxyConfig): string {
  let profileName: string | undefined;
  if (config.cookieProfile === "local") profileName = "synapdesk_session_dev";
  else if (config.cookieProfile === "production") profileName = "__Host-synapdesk_session";
  else if (config.cookieProfile !== undefined) throw new Error("Perfil de cookies inválido.");
  const name = profileName ?? config.sessionCookieName;
  if (
    !name ||
    !/^[A-Za-z0-9_-]{1,80}$/.test(name) ||
    (profileName && config.sessionCookieName && config.sessionCookieName !== profileName)
  )
    throw new Error("Configuración de cookie incompatible.");
  return name;
}

function destination(config: SearchProxyConfig): string {
  if (!config.backendUrl || !config.publicOrigin) throw new Error("Configuración incompleta.");
  const url = new URL(config.backendUrl);
  const local = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
  const origin = new URL(config.publicOrigin);
  const publicLocal = ["localhost", "127.0.0.1", "[::1]"].includes(origin.hostname);
  if (
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    url.pathname !== "/" ||
    (url.protocol !== "https:" && !(url.protocol === "http:" && local && config.allowHttpLocal)) ||
    origin.origin !== config.publicOrigin ||
    (origin.protocol !== "https:" &&
      !(origin.protocol === "http:" && publicLocal && config.allowHttpLocal))
  )
    throw new Error("Destino no autorizado.");
  return new URL("/api/v1/search", url).toString();
}

async function readBody(request: Request): Promise<string> {
  const reader = request.body?.getReader();
  if (!reader) throw new Error("Falta JSON.");
  const parts: Uint8Array[] = [];
  let length = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    length += value.length;
    if (length > 8192) {
      await reader.cancel();
      throw new Error("Cuerpo excesivo.");
    }
    parts.push(value);
  }
  const bytes = new Uint8Array(length);
  let offset = 0;
  for (const part of parts) {
    bytes.set(part, offset);
    offset += part.length;
  }
  return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
}

export async function forwardSemanticSearch(
  request: Request,
  config: SearchProxyConfig,
  send: typeof fetch = fetch
): Promise<Response> {
  let target: string;
  let cookieName: string;
  try {
    target = destination(config);
    cookieName = sessionCookieName(config);
  } catch {
    return failure(503, "SERVICE_UNAVAILABLE");
  }
  if (request.method !== "POST") return failure(405, "VALIDATION_ERROR");
  if (request.headers.get("origin") !== config.publicOrigin) return failure(403, "ORIGIN_INVALID");
  const cookies = (request.headers.get("cookie") ?? "")
    .split(";")
    .map((part) => part.trim())
    .filter((part) => part.indexOf("=") > 0 && part.slice(0, part.indexOf("=")) === cookieName);
  // Cookie-octet excluye espacios, comillas, comas, punto y coma y barras inversas.
  // FastAPI valida el formato de la credencial y la sesión.
  const cookieValue = cookies[0]?.slice(cookies[0].indexOf("=") + 1) ?? "";
  if (
    cookies.length !== 1 ||
    !/^[\x21\x23-\x2b\x2d-\x3a\x3c-\x5b\x5d-\x7e]{1,4096}$/.test(cookieValue)
  ) {
    return failure(401, "AUTHENTICATION_REQUIRED");
  }
  const csrf = request.headers.get("x-csrf-token");
  if (!csrf || csrf.length > 4096 || csrf.includes(",")) return failure(403, "CSRF_INVALID");
  let payload: { query: string; limit: number };
  try {
    if (!(request.headers.get("content-type") ?? "").toLowerCase().startsWith("application/json"))
      throw new Error();
    const body = JSON.parse(await readBody(request));
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
    return failure(422, "VALIDATION_ERROR");
  }
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Cookie: cookies[0],
    Origin: request.headers.get("origin")!,
    "X-CSRF-Token": csrf,
  };
  const site = request.headers.get("sec-fetch-site");
  if (site) headers["Sec-Fetch-Site"] = site;
  try {
    const response = await send(target, {
      method: "POST",
      body: JSON.stringify(payload),
      headers,
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(30000),
    });
    const body = await response.json();
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
