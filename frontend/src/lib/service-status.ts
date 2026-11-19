import { isApiError } from "@/lib/errors";
import { Readiness } from "@/types";

export type ServiceStatus = "available" | "database-unavailable" | "unreachable" | "demo";

/**
 * Traduce el resultado de GET /api/v1/ready a un estado para la interfaz. Solo una respuesta
 * «ready» con la base «ok» cuenta como disponible; 503 DATABASE_UNAVAILABLE indica que la API
 * responde pero la base no; cualquier otro error (red, proxy sin configurar, respuesta inesperada)
 * se trata como sin conexión.
 */
export function readinessStatus(
  result: { ok: true; value: unknown } | { ok: false; error: unknown }
): ServiceStatus {
  if (result.ok) {
    const value = result.value as Partial<Readiness> | null;
    return value?.status === "ready" && value.database === "ok" ? "available" : "unreachable";
  }
  if (isApiError(result.error) && result.error.error.code === "DATABASE_UNAVAILABLE") {
    return "database-unavailable";
  }
  return "unreachable";
}

export const serviceStatusLabels: Record<ServiceStatus, string> = {
  available: "Servicio disponible",
  "database-unavailable": "Base de datos no disponible",
  unreachable: "Sin conexión con el servidor",
  demo: "Datos de ejemplo",
};
