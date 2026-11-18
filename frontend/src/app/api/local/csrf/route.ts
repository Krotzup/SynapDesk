import "server-only";
import { backendApiError, proxyToBackend, serviceUnavailableError } from "@/lib/backend-proxy";

export const dynamic = "force-dynamic";

// BFF exclusivamente local. La variable pública nunca habilita esta frontera por sí sola.
export async function POST(request: Request): Promise<Response> {
  const bridge = (
    process as unknown as Record<
      symbol,
      {
        localTesting?: boolean;
        publicOrigin?: string;
      }
    >
  )[Symbol.for("synapdesk.mvp04.ingress")];
  const failure = (status: number, body: ReturnType<typeof serviceUnavailableError>) =>
    Response.json(body, { status, headers: { "Cache-Control": "no-store" } });
  if (bridge?.localTesting !== true) return failure(503, serviceUnavailableError());
  if (
    request.headers.get("origin") !== bridge.publicOrigin ||
    (request.headers.has("sec-fetch-site") &&
      request.headers.get("sec-fetch-site") !== "same-origin")
  ) {
    return failure(
      403,
      backendApiError("ORIGIN_INVALID", "El origen de la solicitud no está permitido.")
    );
  }
  return proxyToBackend(
    new Request(new URL("/api/v1/auth/csrf", request.url), {
      method: "GET",
      headers: request.headers,
    }),
    ["auth", "csrf"]
  );
}
