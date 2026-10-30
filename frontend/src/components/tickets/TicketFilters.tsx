"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { Button } from "@/components/ui/Button";
import { priorityLabels, statusLabels } from "@/components/ui/Badge";
import { buildQuery } from "@/lib/params";
import { hasActiveFilters, TICKET_PRIORITIES, TICKET_STATUSES } from "@/lib/ticket-filters";
import { TicketListParams } from "@/types";

const fieldClass =
  "bg-[#F8FAFC] border border-[#E2E8F0] text-xs rounded-xl px-3 py-2 text-[#0F172A] outline-none focus:border-[#2563EB]";

function formValue(data: FormData, name: string): string | undefined {
  const value = data.get(name);
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

/**
 * Filtros del listado. Los valores viven en la URL: cambiar un filtro vuelve a la
 * primera página y conserva el área, que todavía no tiene selector propio.
 */
export function TicketFilters(filters: TicketListParams) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  function apply(form: HTMLFormElement) {
    const data = new FormData(form);
    const query = buildQuery({
      status: formValue(data, "status"),
      priority: formValue(data, "priority"),
      area: filters.area,
      search: formValue(data, "search"),
    });
    startTransition(() => router.push(`/tickets${query}`));
  }

  return (
    <form
      role="search"
      aria-busy={isPending}
      onSubmit={(event) => {
        event.preventDefault();
        apply(event.currentTarget);
      }}
      className={`flex flex-wrap items-center gap-2 transition-opacity ${isPending ? "opacity-60" : ""}`}
    >
      <label htmlFor="ticket-search" className="sr-only">
        Buscar por título, área, categoría, usuario o ID
      </label>
      <input
        id="ticket-search"
        name="search"
        type="search"
        defaultValue={filters.search ?? ""}
        placeholder="Título, área, usuario o ID..."
        className={`${fieldClass} w-full sm:w-56 placeholder-[#94A3B8]`}
      />

      <label htmlFor="ticket-status" className="sr-only">
        Estado
      </label>
      <select
        id="ticket-status"
        name="status"
        defaultValue={filters.status ?? ""}
        onChange={(event) => apply(event.currentTarget.form!)}
        className={fieldClass}
      >
        <option value="">Todos los estados</option>
        {TICKET_STATUSES.map((status) => (
          <option key={status} value={status}>
            {statusLabels[status]}
          </option>
        ))}
      </select>

      <label htmlFor="ticket-priority" className="sr-only">
        Prioridad
      </label>
      <select
        id="ticket-priority"
        name="priority"
        defaultValue={filters.priority ?? ""}
        onChange={(event) => apply(event.currentTarget.form!)}
        className={fieldClass}
      >
        <option value="">Todas las prioridades</option>
        {TICKET_PRIORITIES.map((priority) => (
          <option key={priority} value={priority}>
            {priorityLabels[priority]}
          </option>
        ))}
      </select>

      <Button type="submit" variant="secondary" className="px-3! py-2! text-xs!">
        Buscar
      </Button>

      {/* El área solo llega por URL hasta que exista un catálogo de áreas */}
      {filters.area && (
        <Link
          href={`/tickets${buildQuery({ ...filters, area: undefined, page: undefined, pageSize: undefined })}`}
          className="inline-flex items-center gap-1 text-xs font-medium text-[#1D4ED8] bg-[#DBEAFE] rounded-full px-2.5 py-1 hover:bg-[#BFDBFE]"
          aria-label={`Quitar filtro de área ${filters.area}`}
        >
          Área: {filters.area} <span aria-hidden="true">✕</span>
        </Link>
      )}

      {hasActiveFilters(filters) && (
        <Link href="/tickets" className="text-xs font-medium text-[#64748B] hover:text-[#0F172A]">
          Limpiar filtros
        </Link>
      )}
    </form>
  );
}
