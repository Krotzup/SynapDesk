import { ApiError, PaginatedResponse, PaginationParams } from "@/types";

// Demora simulada para que los estados de carga sean visibles durante el desarrollo.
const LATENCY_MS = 300;

// Texto reservado para ver los estados de error sin apagar nada: como consulta en la
// búsqueda semántica o como búsqueda en el listado de tickets.
export const MOCK_ERROR_QUERY = "error-simulado";

/** Devuelve una copia de los datos tras la demora simulada, como lo haría la API. */
export function simulateLatency<T>(data: T): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(structuredClone(data)), LATENCY_MS));
}

/** Rechaza con el formato de error del contrato frontend-backend. */
export function rejectWithApiError(code: string, message: string): Promise<never> {
  const error: ApiError = {
    error: { code, message, details: null, requestId: crypto.randomUUID() },
  };
  return new Promise((_, reject) => setTimeout(() => reject(error), LATENCY_MS));
}

/** Pagina una lista en memoria con los mismos campos que PaginatedResponse. */
export function paginate<T>(items: T[], params?: PaginationParams): PaginatedResponse<T> {
  const page = params?.page ?? 1;
  const pageSize = params?.pageSize ?? 20;
  const start = (page - 1) * pageSize;

  return {
    items: items.slice(start, start + pageSize),
    page,
    pageSize,
    totalItems: items.length,
    totalPages: Math.ceil(items.length / pageSize),
  };
}
