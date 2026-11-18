import { Pagination } from "@/components/ui/Pagination";
import { buildQuery } from "@/lib/params";
import { filtersForUrl } from "@/lib/ticket-filters";
import { PaginatedResponse, Ticket, TicketListParams } from "@/types";

interface TicketPaginationProps {
  result: PaginatedResponse<Ticket>;
  filters: TicketListParams;
}

/** Paginación del listado; cada enlace conserva los filtros activos. */
export function TicketPagination({ result, filters }: TicketPaginationProps) {
  return (
    <Pagination
      result={result}
      hrefFor={(target) =>
        `/tickets${buildQuery({ ...filtersForUrl(filters), page: target > 1 ? target : undefined })}`
      }
      label="Paginación de tickets"
      noun={["ticket", "tickets"]}
    />
  );
}
