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
 * Número de página leído de la URL (?page=). Solo se aceptan dígitos: cualquier otro valor
 * (vacío, texto, decimal, negativo, notación científica como "1e2" o hexadecimal como "0x10")
 * o un número fuera del rango seguro se trata como la primera página.
 */
export function parsePage(value: string | string[] | undefined): number {
  const raw = (Array.isArray(value) ? value[0] : value)?.trim() ?? "";
  const page = /^\d+$/.test(raw) ? Number(raw) : NaN;
  return Number.isSafeInteger(page) && page >= 1 ? page : 1;
}
