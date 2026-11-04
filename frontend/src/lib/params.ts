/**
 * Construye un query string a partir de parámetros de listado (paginación y filtros),
 * omitiendo los valores undefined o vacíos para evitar enviar parámetros vacíos.
 */
export function buildQuery<T extends object>(params?: T): string {
  if (!params) return "";
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") query.set(key, String(value));
  }
  const str = query.toString();
  return str ? `?${str}` : "";
}
