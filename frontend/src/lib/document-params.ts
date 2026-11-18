import { parsePage } from "@/lib/params";

export const DOCUMENT_PAGE_SIZE = 10;

/**
 * Parámetros del listado de documentos desde la URL. El contrato de GET /documents solo define
 * la paginación: no hay búsqueda ni filtros, así que cualquier otro parámetro se ignora.
 */
export function parseDocumentListParams(
  searchParams: Record<string, string | string[] | undefined>
): { page: number; pageSize: number } {
  return { page: parsePage(searchParams.page), pageSize: DOCUMENT_PAGE_SIZE };
}
