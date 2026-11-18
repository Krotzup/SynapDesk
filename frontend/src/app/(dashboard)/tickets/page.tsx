import Link from "next/link";
import { connection } from "next/server";
import { Suspense } from "react";
import { TicketFilters } from "@/components/tickets/TicketFilters";
import {
  TicketListSummary,
  TicketListSummaryFallback,
} from "@/components/tickets/TicketListSummary";
import { TicketPagination } from "@/components/tickets/TicketPagination";
import { buttonClassName } from "@/components/ui/Button";
import { StatusBadge, PriorityBadge } from "@/components/ui/Badge";
import { formatDateTime, shortId } from "@/lib/format";
import { buildQuery } from "@/lib/params";
import { filtersForUrl, hasActiveFilters, parseTicketListParams } from "@/lib/ticket-filters";
import { ticketsService } from "@/services/tickets";

interface TicketsPageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export default async function TicketsPage({ searchParams }: TicketsPageProps) {
  // Renderiza en cada solicitud: el listado no debe obtenerse ni congelarse durante el build.
  await connection();
  const filters = parseTicketListParams(await searchParams);
  const filtered = hasActiveFilters(filters);
  // Los conteos se cargan aparte (TicketListSummary): si fallan, el listado se sigue mostrando.
  const result = await ticketsService.getAll(filters);
  const tickets = result.items;

  // Mensaje cuando la página no tiene tickets; lo usan la tabla y las tarjetas.
  const emptyMessage =
    result.totalItems > 0 ? (
      <>
        Esta página no tiene tickets.{" "}
        <Link
          href={`/tickets${buildQuery(filtersForUrl(filters))}`}
          className="text-[#2563EB] hover:underline"
        >
          Ir a la primera página
        </Link>
      </>
    ) : filtered ? (
      <>
        No hay tickets que coincidan con los filtros.{" "}
        <Link href="/tickets" className="text-[#2563EB] hover:underline">
          Limpiar filtros
        </Link>
      </>
    ) : (
      "No hay tickets registrados."
    );

  return (
    <div className="px-4 py-6 sm:p-6 lg:p-8 bg-[#F8FAFC] min-h-screen">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Encabezado */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-[#0F172A]">Gestión de tickets</h1>
            <p className="text-sm text-[#64748B] mt-1">
              Visualiza y gestiona las solicitudes de soporte.
            </p>
          </div>
          <Link
            href="/tickets/nuevo"
            className={buttonClassName("primary", false, "w-full sm:w-auto")}
          >
            + Nuevo ticket
          </Link>
        </div>

        {/* Métricas rápidas */}
        <Suspense fallback={<TicketListSummaryFallback />}>
          <TicketListSummary />
        </Suspense>

        {/* Tabla de tickets */}
        <div className="bg-white rounded-2xl border border-[#E2E8F0] shadow-sm overflow-hidden">
          <div className="p-4 sm:p-5 border-b border-[#F1F5F9] flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            <h2 className="text-base font-bold text-[#0F172A]">
              {filtered ? "Resultados" : "Todos los tickets"}
            </h2>
            {/* La key reinicia los campos cuando los filtros cambian desde otro lugar (menú lateral) */}
            <TicketFilters key={buildQuery(filtersForUrl(filters))} {...filters} />
          </div>

          {/* Teléfono: tarjetas. Desde 768 px: tabla. */}
          <ul className="md:hidden divide-y divide-[#F1F5F9]" aria-label="Tickets">
            {tickets.length === 0 && (
              <li className="py-10 px-4 text-center text-sm text-[#94A3B8]">{emptyMessage}</li>
            )}
            {tickets.map((ticket) => (
              <li key={ticket.id}>
                <Link
                  href={`/tickets/${ticket.id}`}
                  className="block space-y-2 px-4 py-4 hover:bg-[#F8FAFC] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#2563EB]"
                >
                  <span className="flex items-center justify-between gap-2 text-xs">
                    <span className="font-bold text-[#2563EB]" title={ticket.id}>
                      #{shortId(ticket.id)}
                    </span>
                    <span className="text-[#94A3B8]">{formatDateTime(ticket.createdAt)}</span>
                  </span>
                  <span className="block text-sm font-semibold text-[#0F172A] line-clamp-2">
                    {ticket.title}
                  </span>
                  <span className="flex flex-wrap items-center gap-2">
                    <StatusBadge status={ticket.status} />
                    <PriorityBadge priority={ticket.priority} />
                    <span className="text-xs text-[#64748B]">{ticket.area ?? "Sin asignar"}</span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>

          {/* Para que la tabla quepa sin desplazamiento lateral: Usuario y Fecha aparecen desde
              1280 px y Acción desde 1536 px (el ID y el asunto ya enlazan al detalle). */}
          <div className="hidden md:block overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-[#F8FAFC] text-[11px] font-bold text-[#64748B] uppercase tracking-wider border-b border-[#E2E8F0]">
                  <th className="py-3.5 px-4">ID</th>
                  <th className="py-3.5 px-4">Asunto</th>
                  <th className="py-3.5 px-4 hidden xl:table-cell">Usuario</th>
                  <th className="py-3.5 px-4">Área</th>
                  <th className="py-3.5 px-4">Estado</th>
                  <th className="py-3.5 px-4">Prioridad</th>
                  <th className="py-3.5 px-4 hidden xl:table-cell">Fecha</th>
                  <th className="py-3.5 px-4 text-right hidden 2xl:table-cell">Acción</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#F1F5F9] text-xs text-[#475569]">
                {tickets.length === 0 && (
                  <tr>
                    <td colSpan={8} className="py-10 px-4 text-center text-sm text-[#94A3B8]">
                      {emptyMessage}
                    </td>
                  </tr>
                )}
                {tickets.map((ticket) => (
                  <tr key={ticket.id} className="hover:bg-[#F8FAFC] transition-colors">
                    <td className="py-4 px-4 font-bold text-[#2563EB]">
                      <Link
                        href={`/tickets/${ticket.id}`}
                        className="hover:underline"
                        title={ticket.id}
                      >
                        #{shortId(ticket.id)}
                      </Link>
                    </td>
                    <td className="py-4 px-4 font-semibold text-[#0F172A]">
                      {/* El recorte necesita un bloque con ancho máximo: en la celda no funciona. */}
                      <Link
                        href={`/tickets/${ticket.id}`}
                        title={ticket.title}
                        className="block max-w-56 truncate hover:text-[#2563EB]"
                      >
                        {ticket.title}
                      </Link>
                    </td>
                    <td className="py-4 px-4 hidden xl:table-cell">{ticket.createdBy.name}</td>
                    <td className="py-4 px-4 text-[#64748B]">{ticket.area ?? "Sin asignar"}</td>
                    <td className="py-4 px-4 whitespace-nowrap">
                      <StatusBadge status={ticket.status} />
                    </td>
                    <td className="py-4 px-4 whitespace-nowrap">
                      <PriorityBadge priority={ticket.priority} />
                    </td>
                    <td className="py-4 px-4 text-[#94A3B8] whitespace-nowrap hidden xl:table-cell">
                      {formatDateTime(ticket.createdAt)}
                    </td>
                    <td className="py-4 px-4 text-right whitespace-nowrap hidden 2xl:table-cell">
                      <Link
                        href={`/tickets/${ticket.id}`}
                        className="inline-flex items-center text-xs font-semibold text-[#2563EB] hover:text-[#1D4ED8] bg-[#EFF6FF] hover:bg-[#DBEAFE] px-3 py-1.5 rounded-lg transition-colors"
                      >
                        Ver detalle →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <TicketPagination result={result} filters={filters} />
        </div>
      </div>
    </div>
  );
}
