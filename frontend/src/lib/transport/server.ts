import "server-only";

import { headers } from "next/headers";
import { filterCookieHeader, getBackendOrigin } from "@/lib/backend-proxy";
import { ApiError } from "@/types";
import type { Transport } from "./client";

// Transporte de los componentes de servidor (adaptador SSR): directo a FastAPI con las cookies
// permitidas de la petición actual. Se calcula en cada llamada; nada se guarda entre peticiones.
// No envía Origin ni pide token CSRF: en el servidor solo hay lecturas.
// package.json ("imports" → "#transport", condición "react-server") elige este archivo.

export async function getTransport(): Promise<Transport> {
  const baseUrl = getBackendOrigin();
  if (!baseUrl) {
    console.error("[ssr] BACKEND_INTERNAL_URL no está configurada o no es una URL http(s).");
    const error: ApiError = {
      error: {
        code: "SERVICE_UNAVAILABLE",
        message: "El servicio no está disponible en este momento.",
        details: null,
        requestId: "",
      },
    };
    throw error;
  }
  // Se usa la cabecera original para conservar cookies repetidas (el backend las rechaza).
  const cookie = filterCookieHeader((await headers()).get("cookie"));
  return { baseUrl, headers: cookie ? { Cookie: cookie } : {} };
}
