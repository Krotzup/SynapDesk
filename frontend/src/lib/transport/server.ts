import "server-only";

import { headers } from "next/headers";
import {
  BACKEND_TIMEOUT_MS,
  BackendChannelError,
  type BackendConfig,
  callBackend,
  filterCookieHeader,
  getBackendConfig,
  serviceUnavailableError,
} from "@/lib/backend-proxy";
import type { Transport } from "./client";

// Transporte de los componentes de servidor (adaptador SSR): usa el mismo canal que el proxy
// (credencial de servicio SEC-01B, HTTPS verificado, sin redirecciones, plazo y tope de tamaño) con
// las cookies reservadas de la petición actual. Se calcula en cada llamada; nada se guarda entre
// peticiones. No envía Origin ni pide token CSRF: en el servidor solo hay lecturas.
// package.json ("imports" → "#transport", condición "react-server") elige este archivo.

const failureMessages: Record<BackendChannelError["reason"], string> = {
  unavailable: "[ssr] No se pudo obtener la respuesta completa del backend.",
  redirect: "[ssr] El backend respondió con una redirección; no se sigue.",
  "response-too-large": "[ssr] La respuesta del backend supera el tamaño permitido.",
};

/** Petición SSR hacia FastAPI por el canal común. `path` es relativo (/api/v1/...). */
async function backendFetch(
  config: BackendConfig,
  path: string,
  init: RequestInit
): Promise<Response> {
  const body = typeof init.body === "string" ? new TextEncoder().encode(init.body) : undefined;
  try {
    const result = await callBackend(
      config,
      { method: init.method ?? "GET", path, headers: new Headers(init.headers), body, localRead: true },
      AbortSignal.timeout(BACKEND_TIMEOUT_MS)
    );
    return new Response(result.body, {
      status: result.response.status,
      statusText: result.response.statusText,
      headers: result.response.headers,
    });
  } catch (error) {
    console.error(
      error instanceof BackendChannelError
        ? failureMessages[error.reason]
        : failureMessages.unavailable
    );
    throw serviceUnavailableError();
  }
}

export async function getTransport(): Promise<Transport> {
  const config = getBackendConfig("ssr");
  if (!config) throw serviceUnavailableError();
  // Se usa la cabecera original para conservar cookies repetidas o mal formadas (el backend las
  // rechaza).
  const cookie = filterCookieHeader((await headers()).get("cookie"));
  return {
    // Ruta relativa: el destino lo agrega el canal desde la configuración.
    baseUrl: "",
    headers: cookie ? { Cookie: cookie } : {},
    fetch: (url, init) => backendFetch(config, url, init),
  };
}
