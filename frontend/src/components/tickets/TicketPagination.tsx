import Link from "next/link";
import { buildQuery } from "@/lib/params";
import { filtersForUrl } from "@/lib/ticket-filters";
import { PaginatedResponse, Ticket, TicketListParams } from "@/types";

interface TicketPaginationProps {
  result: PaginatedResponse<Ticket>;
  filters: TicketListParams;
}

const linkClass =
  "inline-flex items-center px-3 py-1.5 rounded-lg text-xs font-semibold border border-[#E2E8F0] text-[#2563EB] hover:bg-[#EFF6FF] transition-colors";
const disabledClass =
  "inline-flex items-center px-3 py-1.5 rounded-lg text-xs font-semibold border border-[#F1F5F9] text-[#CBD5E1] cursor-not-allowed";

/** Paginación del listado; cada enlace conserva los filtros activos. */
export function TicketPagination({ result, filters }: TicketPaginationProps) {
  const { page, pageSize, totalItems, totalPages } = result;
  if (totalItems === 0) return null;

  const first = (page - 1) * pageSize + 1;
  const last = Math.min(page * pageSize, totalItems);
  const noun = totalItems === 1 ? "ticket" : "tickets";
  const hrefFor = (target: number) =>
    `/tickets${buildQuery({ ...filtersForUrl(filters), page: target > 1 ? target : undefined })}`;

  return (
    <nav
      aria-label="Paginación de tickets"
      className="flex flex-col sm:flex-row items-center justify-between gap-3 px-6 py-4 border-t border-[#F1F5F9] text-xs text-[#64748B]"
    >
      <p>
        {first <= totalItems
          ? `Mostrando ${first}–${last} de ${totalItems} ${noun}`
          : `${totalItems} ${noun} en total`}
      </p>
      <div className="flex items-center gap-2">
        {page > 1 ? (
          <Link href={hrefFor(page - 1)} className={linkClass}>
            ← Anterior
          </Link>
        ) : (
          <span className={disabledClass} aria-disabled="true">
            ← Anterior
          </span>
        )}
        <span className="px-2 tabular-nums">
          Página {page} de {Math.max(totalPages, 1)}
        </span>
        {page < totalPages ? (
          <Link href={hrefFor(page + 1)} className={linkClass}>
            Siguiente →
          </Link>
        ) : (
          <span className={disabledClass} aria-disabled="true">
            Siguiente →
          </span>
        )}
      </div>
    </nav>
  );
}
