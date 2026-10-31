export const SEARCH_LIMITS = [5, 10, 20] as const;
export const DEFAULT_SEARCH_LIMIT = 5;
export const MAX_QUERY_LENGTH = 1000;

export type SearchLimit = (typeof SEARCH_LIMITS)[number];

export interface SemanticSearchParams {
  query: string;
  limit: SearchLimit;
  // La consulta supera MAX_QUERY_LENGTH y no se envía al backend.
  tooLong: boolean;
}

type SearchParams = Record<string, string | string[] | undefined>;

function first(value: string | string[] | undefined): string {
  const raw = Array.isArray(value) ? value[0] : value;
  return raw?.trim() ?? "";
}

/**
 * Lee la consulta y la cantidad de resultados desde la URL (/busqueda?q=&limit=).
 * Una cantidad desconocida se reemplaza por la predeterminada.
 */
export function parseSemanticSearchParams(searchParams: SearchParams): SemanticSearchParams {
  const query = first(searchParams.q);
  const limit = Number(first(searchParams.limit));

  return {
    query,
    limit: SEARCH_LIMITS.find((item) => item === limit) ?? DEFAULT_SEARCH_LIMIT,
    tooLong: query.length > MAX_QUERY_LENGTH,
  };
}
