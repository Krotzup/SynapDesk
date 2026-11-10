import "server-only";

import { headers } from "next/headers";
import {
  BACKEND_TIMEOUT_MS,
  filterCookieHeader,
  getBackendConfig,
  serviceUnavailableError,
} from "@/lib/backend-proxy";
import type { Transport } from "./client";

// Transporte de los componentes de servidor (adaptador SSR): directo a FastAPI con las cookies
// permitidas de la petición actual. Se calcula en cada llamada; nada se guarda entre peticiones.
// No envía Origin ni pide token CSRF: en el servidor solo hay lecturas.
// package.json ("imports" → "#transport", condición "react-server") elige este archivo.
// Mismas reglas que el proxy: perfil de cookies válido, tiempo de espera, sin seguir redirecciones
// y errores del contrato con un requestId generado aquí.

/** fetch hacia FastAPI con las mismas protecciones que el proxy (lib/backend-proxy.ts). */
async function backendFetch(url: string, init: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      // No seguir redirecciones: podrían llevar las cookies a otro host.
      redirect: "manual",
      signal: AbortSignal.timeout(BACKEND_TIMEOUT_MS),
    });
  } catch {
    // Backend apagado, sin red o tiempo de espera agotado.
    console.error("[ssr] No se pudo obtener respuesta del backend.");
    throw serviceUnavailableError();
  }
  if (response.status >= 300 && response.status < 400) {
    await response.body?.cancel();
    console.error("[ssr] El backend respondió con una redirección; no se sigue.");
    throw serviceUnavailableError();
  }
  return response;
}

export async function getTransport(): Promise<Transport> {
  const config = getBackendConfig("ssr");
  if (!config) throw serviceUnavailableError();
  // Se usa la cabecera original para conservar cookies repetidas (el backend las rechaza).
  const cookie = filterCookieHeader((await headers()).get("cookie"), config.cookieNames);
  return {
    baseUrl: config.origin,
    headers: cookie ? { Cookie: cookie } : {},
    fetch: backendFetch,
  };
}
