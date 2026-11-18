"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { Button } from "@/components/ui/Button";
import { priorityLabels, statusLabels } from "@/components/ui/Badge";
import { buildQuery } from "@/lib/params";
import {
  hasActiveFilters,
  TICKET_FILTERS_ENABLED,
  TICKET_FILTERS_NOTICE,
  TICKET_PRIORITIES,
  TICKET_STATUSES,
} from "@/lib/ticket-filters";
import { TicketListParams } from "@/types";

const fieldClass =
  "bg-[#F8FAFC] border border-[#E2E8F0] text-xs rounded-xl px-3 py-2 min-h-11 md:min-h-0 text-[#0F172A] outline-none focus:border-[#2563EB]";

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
  const activeCount = [filters.search, filters.status, filters.priority, filters.area].filter(
    Boolean
  ).length;
  // Bajo 768 px los filtros quedan detrás del botón "Filtros"; desde ahí, siempre a la vista.
  // La key del listado vuelve a montar este componente al aplicar un filtro: con filtros activos
  // el panel empieza abierto, para elegir el siguiente sin volver a tocar "Filtros".
  const [isOpen, setIsOpen] = useState(activeCount > 0);

  if (!TICKET_FILTERS_ENABLED) return <DisabledTicketFilters />;

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
    <div className="w-full lg:w-auto">
      <Button
        type="button"
        variant="secondary"
        fullWidth
        className="md:hidden"
        aria-expanded={isOpen}
        aria-controls="filtros-listado"
        onClick={() => setIsOpen(!isOpen)}
      >
        Filtros{activeCount > 0 ? ` (${activeCount})` : ""}
        <span aria-hidden="true">{isOpen ? "▲" : "▼"}</span>
      </Button>
      <form
        id="filtros-listado"
        role="search"
        // Nombre propio para distinguirlo del buscador de la cabecera con un lector de pantalla.
        aria-label="Filtros del listado"
        aria-busy={isPending}
        onSubmit={(event) => {
          event.preventDefault();
          apply(event.currentTarget);
        }}
        className={`${isOpen ? "mt-3 flex" : "hidden"} md:mt-0 md:flex flex-col md:flex-row md:flex-wrap md:items-center gap-2 transition-opacity ${isPending ? "opacity-60" : ""}`}
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
          className={`${fieldClass} w-full md:w-56 placeholder-[#94A3B8]`}
        />

        <label htmlFor="ticket-status" className="sr-only">
          Estado
        </label>
        <select
          id="ticket-status"
          name="status"
          defaultValue={filters.status ?? ""}
          onChange={(event) => apply(event.currentTarget.form!)}
          className={`${fieldClass} w-full md:w-auto`}
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
          className={`${fieldClass} w-full md:w-auto`}
        >
          <option value="">Todas las prioridades</option>
          {TICKET_PRIORITIES.map((priority) => (
            <option key={priority} value={priority}>
              {priorityLabels[priority]}
            </option>
          ))}
        </select>

        <Button
          type="submit"
          variant="secondary"
          className="w-full md:w-auto md:px-3! md:py-2! md:text-xs!"
        >
          Buscar
        </Button>

        {/* El área solo llega por URL hasta que exista un catálogo de áreas */}
        {filters.area && (
          <Link
            href={`/tickets${buildQuery({ ...filters, area: undefined, page: undefined, pageSize: undefined })}`}
            className="inline-flex items-center justify-center gap-1 text-xs font-medium text-[#1D4ED8] bg-[#DBEAFE] rounded-full px-2.5 py-1 min-h-11 md:min-h-0 hover:bg-[#BFDBFE]"
            aria-label={`Quitar filtro de área ${filters.area}`}
          >
            Área: {filters.area} <span aria-hidden="true">✕</span>
          </Link>
        )}

        {hasActiveFilters(filters) && (
          <Link
            href="/tickets"
            className="inline-flex items-center justify-center min-h-11 md:min-h-0 text-xs font-medium text-[#64748B] hover:text-[#0F172A]"
          >
            Limpiar filtros
          </Link>
        )}
      </form>
    </div>
  );
}

/**
 * Filtros desactivados mientras el backend no los implementa: desde 768 px se ven los campos
 * deshabilitados; en el teléfono, solo el aviso.
 */
function DisabledTicketFilters() {
  return (
    <div className="w-full lg:w-auto space-y-2">
      <fieldset
        disabled
        aria-describedby="filtros-aviso"
        className="hidden md:flex md:flex-row md:flex-wrap md:items-center gap-2 opacity-60"
      >
        <legend className="sr-only">Filtros del listado</legend>
        <label htmlFor="ticket-search" className="sr-only">
          Buscar por título, área, categoría, usuario o ID
        </label>
        <input
          id="ticket-search"
          type="search"
          placeholder="Título, área, usuario o ID..."
          className={`${fieldClass} md:w-56 placeholder-[#94A3B8] cursor-not-allowed`}
        />
        <label htmlFor="ticket-status" className="sr-only">
          Estado
        </label>
        <select id="ticket-status" className={`${fieldClass} cursor-not-allowed`}>
          <option>Todos los estados</option>
        </select>
        <label htmlFor="ticket-priority" className="sr-only">
          Prioridad
        </label>
        <select id="ticket-priority" className={`${fieldClass} cursor-not-allowed`}>
          <option>Todas las prioridades</option>
        </select>
      </fieldset>
      <p id="filtros-aviso" className="text-xs text-[#64748B] lg:text-right">
        {TICKET_FILTERS_NOTICE}
      </p>
    </div>
  );
}
