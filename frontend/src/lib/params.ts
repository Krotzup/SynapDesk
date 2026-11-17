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

/**
 * Número de página leído de la URL (?page=). Cualquier valor que no sea un entero mayor o igual
 * a 1 (vacío, texto, decimal, negativo) se trata como la primera página.
 */
export function parsePage(value: string | string[] | undefined): number {
  const raw = Array.isArray(value) ? value[0] : value;
  const page = Number(raw?.trim() || undefined);
  return Number.isInteger(page) && page >= 1 ? page : 1;
}
