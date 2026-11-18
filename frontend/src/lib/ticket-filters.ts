import { parsePage } from "@/lib/params";
import { TicketListParams, TicketPriority, TicketStatus } from "@/types";

export const TICKET_PAGE_SIZE = 10;

/**
 * Filtros del listado (búsqueda, estado, prioridad y área). El backend MVP02 no los implementa
 * y pide no enviarlos esperando que se ignoren: quedan desactivados hasta que el contrato
 * apruebe sus valores. Para reactivarlos basta con cambiar esta constante.
 */
export const TICKET_FILTERS_ENABLED = false;

/** Aviso que acompaña a los filtros mientras están desactivados. */
export const TICKET_FILTERS_NOTICE =
  "Los filtros y la búsqueda de tickets se habilitarán cuando el backend los implemente.";

/** Enlace al listado filtrado por estado, o undefined mientras los filtros estén desactivados. */
export function ticketListHrefForStatus(
  status: TicketStatus,
  enabled: boolean = TICKET_FILTERS_ENABLED
): string | undefined {
  return enabled ? `/tickets?status=${status}` : undefined;
}

export const TICKET_STATUSES: readonly TicketStatus[] = [
  "open",
  "in_progress",
  "resolved",
  "closed",
];
export const TICKET_PRIORITIES: readonly TicketPriority[] = ["low", "medium", "high"];

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
 * en lugar de enviarse al backend. Con los filtros desactivados solo se lee la página.
 */
export function parseTicketListParams(
  searchParams: SearchParams,
  enabled: boolean = TICKET_FILTERS_ENABLED
): TicketListParams {
  if (!enabled) {
    return { page: parsePage(searchParams.page), pageSize: TICKET_PAGE_SIZE };
  }
  return {
    status: oneOf(TICKET_STATUSES, first(searchParams.status)),
    priority: oneOf(TICKET_PRIORITIES, first(searchParams.priority)),
    area: first(searchParams.area),
    search: first(searchParams.search),
    page: parsePage(searchParams.page),
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
