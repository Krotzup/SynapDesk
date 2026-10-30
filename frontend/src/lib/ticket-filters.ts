import { TicketListParams, TicketPriority, TicketStatus } from "@/types";

export const TICKET_PAGE_SIZE = 10;

export const TICKET_STATUSES: readonly TicketStatus[] = [
  "open",
  "in_progress",
  "resolved",
  "closed",
];
export const TICKET_PRIORITIES: readonly TicketPriority[] = ["low", "medium", "high", "critical"];

type SearchParams = Record<string, string | string[] | undefined>;

function first(value: string | string[] | undefined): string | undefined {
  const raw = Array.isArray(value) ? value[0] : value;
  return raw?.trim() || undefined;
}

function oneOf<T extends string>(values: readonly T[], value: string | undefined): T | undefined {
  return values.find((item) => item === value);
}

/**
 * Lee los filtros del listado desde la URL. Los valores desconocidos se ignoran
 * en lugar de enviarse al backend.
 */
export function parseTicketListParams(searchParams: SearchParams): TicketListParams {
  const page = Number(first(searchParams.page));

  return {
    status: oneOf(TICKET_STATUSES, first(searchParams.status)),
    priority: oneOf(TICKET_PRIORITIES, first(searchParams.priority)),
    area: first(searchParams.area),
    search: first(searchParams.search),
    page: Number.isInteger(page) && page >= 1 ? page : 1,
    pageSize: TICKET_PAGE_SIZE,
  };
}

/** Indica si el listado tiene algún filtro aplicado (sin contar la paginación). */
export function hasActiveFilters(params: TicketListParams): boolean {
  return Boolean(params.status || params.priority || params.area || params.search);
}

/** Parámetros que se conservan en la URL al cambiar de página (pageSize es fijo). */
export function filtersForUrl(params: TicketListParams): TicketListParams {
  const { status, priority, area, search } = params;
  return { status, priority, area, search };
}
