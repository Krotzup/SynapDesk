import { parseSearchResponse } from "../search-contract";

export interface SearchProxyConfig {
  backendUrl?: string;
  publicOrigin?: string;
  sessionCookieName?: string;
  allowHttpLocal?: boolean;
}

const noStore = { "Cache-Control": "no-store" };
const messages: Record<string, string> = {
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

function destination(config: SearchProxyConfig): string {
  if (
    !config.backendUrl ||
    !config.publicOrigin ||
    !config.sessionCookieName ||
    !/^[A-Za-z0-9_-]{1,80}$/.test(config.sessionCookieName)
  )
    throw new Error("Configuración incompleta.");
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
  try {
    target = destination(config);
  } catch {
    return failure(503, "SEARCH_UNAVAILABLE");
  }
  if (request.method !== "POST") return failure(405, "VALIDATION_ERROR");
  if (request.headers.get("origin") !== config.publicOrigin) return failure(403, "ORIGIN_INVALID");
  const cookies = (request.headers.get("cookie") ?? "")
    .split(";")
    .map((part) => part.trim())
    .filter(
      (part) =>
        part.indexOf("=") > 0 && part.slice(0, part.indexOf("=")) === config.sessionCookieName
    );
  if (
    cookies.length !== 1 ||
    !/^[A-Za-z0-9_-]{43}$/.test(cookies[0].slice(cookies[0].indexOf("=") + 1))
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
      signal: AbortSignal.timeout(15000),
    });
    const body = await response.json();
    if (!response.ok) {
      const code = body?.error?.code;
      if (
        [401, 403, 422, 503].includes(response.status) &&
        typeof code === "string" &&
        code in messages
      ) {
        const id = body.error.requestId;
        return failure(
          response.status,
          code,
          typeof id === "string" && /^[0-9a-f-]{36}$/i.test(id) ? id : undefined
        );
      }
      return failure(502, "SEARCH_UNAVAILABLE");
    }
    return Response.json(parseSearchResponse(body), { headers: noStore });
  } catch {
    return failure(502, "SEARCH_UNAVAILABLE");
  }
}
