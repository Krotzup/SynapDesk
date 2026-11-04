import { CsrfToken } from "@/types";
import { onAuthChange } from "./auth-sync";

// Token CSRF del contrato de autenticación V1 (Synchronizer Token).
// - Se guarda solo en memoria: nunca en localStorage, cookies propias ni la URL.
// - Se pide cuando hace falta (antes de la primera mutación), no al cargar la página.
// - Las solicitudes simultáneas comparten una misma obtención.
// - Se renueva cuando faltan menos de RENEW_MARGIN_MS para su vencimiento.

// Margen provisional: el contrato no fija un número (los tiempos son PROVISIONAL_CONFIGURATION).
const RENEW_MARGIN_MS = 60_000;

let current: { token: string; expiresAtMs: number } | null = null;
let pending: Promise<string> | null = null;

// Tras un login o logout el contexto cambia y el token anterior deja de servir.
if (typeof window !== "undefined") {
  onAuthChange(() => clearCsrfToken());
}

export function clearCsrfToken() {
  current = null;
  pending = null;
}

/** Devuelve un token vigente, pidiéndolo con fetchToken solo si no hay uno en memoria. */
export function getCsrfToken(fetchToken: () => Promise<CsrfToken>): Promise<string> {
  if (current && current.expiresAtMs - Date.now() > RENEW_MARGIN_MS) {
    return Promise.resolve(current.token);
  }
  if (!pending) {
    const request = fetchToken()
      .then(({ csrfToken, expiresAt }) => {
        // Solo se guarda si nadie limpió el token mientras se esperaba la respuesta.
        if (pending === request) current = { token: csrfToken, expiresAtMs: Date.parse(expiresAt) };
        return csrfToken;
      })
      .finally(() => {
        if (pending === request) pending = null;
      });
    pending = request;
  }
  return pending;
}
