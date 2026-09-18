import { PaginationParams } from "@/types";

/**
 * Construye un query string a partir de parámetros de paginación,
 * omitiendo los valores undefined para evitar enviar parámetros vacíos.
 */
export function buildQuery(params?: PaginationParams): string {
  if (!params) return "";
  const query = new URLSearchParams();
  if (params.page !== undefined) query.set("page", String(params.page));
  if (params.pageSize !== undefined) query.set("pageSize", String(params.pageSize));
  if (params.search !== undefined) query.set("search", params.search);
  if (params.sort !== undefined) query.set("sort", params.sort);
  if (params.order !== undefined) query.set("order", params.order);
  const str = query.toString();
  return str ? `?${str}` : "";
}
