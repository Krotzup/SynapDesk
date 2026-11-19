import { api } from "@/lib/api";
import { Readiness } from "@/types";

// Rutas públicas de estado del backend: no requieren sesión ni CSRF. Con datos de ejemplo no se
// consultan (ver ServiceStatus), porque no hay backend al que preguntar.
export const systemService = {
  getReadiness: (): Promise<Readiness> => api.get("/ready"),
};
