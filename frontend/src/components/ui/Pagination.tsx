import Link from "next/link";
import { PaginatedResponse } from "@/types";

interface PaginationProps {
  result: Omit<PaginatedResponse<unknown>, "items">;
  /** Enlace a una página; conserva los filtros del listado. */
  hrefFor: (page: number) => string;
  /** Nombre de la región para lectores de pantalla, por ejemplo "Paginación de tickets". */
  label: string;
  /** Sustantivo en singular y plural para "Mostrando 1–10 de 14 tickets". */
  noun: readonly [singular: string, plural: string];
}

const linkClass =
  "inline-flex flex-1 sm:flex-none items-center justify-center min-h-11 sm:min-h-0 px-4 sm:px-3 py-1.5 rounded-lg text-sm sm:text-xs font-semibold border border-[#E2E8F0] text-[#2563EB] hover:bg-[#EFF6FF] transition-colors";
const disabledClass =
  "inline-flex flex-1 sm:flex-none items-center justify-center min-h-11 sm:min-h-0 px-4 sm:px-3 py-1.5 rounded-lg text-sm sm:text-xs font-semibold border border-[#F1F5F9] text-[#CBD5E1] cursor-not-allowed";

/** Paginación de un listado: rango mostrado, Anterior y Siguiente (en el teléfono, de 44 px). */
export function Pagination({ result, hrefFor, label, noun }: PaginationProps) {
  const { page, pageSize, totalItems, totalPages } = result;
  if (totalItems === 0) return null;

  const first = (page - 1) * pageSize + 1;
  const last = Math.min(page * pageSize, totalItems);
  const word = totalItems === 1 ? noun[0] : noun[1];

  return (
    <nav
      aria-label={label}
      className="flex flex-col sm:flex-row items-center justify-between gap-3 px-4 sm:px-6 py-4 border-t border-[#F1F5F9] text-xs text-[#64748B]"
    >
      <p>
        {first <= totalItems
          ? `Mostrando ${first}–${last} de ${totalItems} ${word}`
          : `${totalItems} ${word} en total`}
      </p>
      <div className="flex w-full sm:w-auto items-center gap-2">
        {page > 1 ? (
          <Link href={hrefFor(page - 1)} className={linkClass}>
            ← Anterior
          </Link>
        ) : (
          <span className={disabledClass} aria-disabled="true">
            ← Anterior
          </span>
        )}
        <span className="px-2 tabular-nums whitespace-nowrap">
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
