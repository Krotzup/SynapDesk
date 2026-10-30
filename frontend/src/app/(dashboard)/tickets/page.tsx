import Link from "next/link";
import { connection } from "next/server";
import { TicketFilters } from "@/components/tickets/TicketFilters";
import { TicketPagination } from "@/components/tickets/TicketPagination";
import { Button } from "@/components/ui/Button";
import { StatusBadge, PriorityBadge } from "@/components/ui/Badge";
import { formatDateTime, shortId } from "@/lib/format";
import { buildQuery } from "@/lib/params";
import { filtersForUrl, hasActiveFilters, parseTicketListParams } from "@/lib/ticket-filters";
import { metricsService } from "@/services/metrics";
import { ticketsService } from "@/services/tickets";

interface TicketsPageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export default async function TicketsPage({ searchParams }: TicketsPageProps) {
  // Renderiza en cada solicitud: el listado no debe obtenerse ni congelarse durante el build.
  await connection();
  const filters = parseTicketListParams(await searchParams);
  const filtered = hasActiveFilters(filters);
  const [result, summary] = await Promise.all([
    ticketsService.getAll(filters),
    metricsService.getSummary(),
  ]);
  const tickets = result.items;

  // Conteos globales desde GET /metrics/summary, los mismos del menú lateral.
  const summaryCards = [
    {
      label: "Total tickets",
      value: summary.totalTickets,
      icon: "📋",
      bg: "bg-[#EFF6FF]",
      text: "text-[#2563EB]",
    },
    {
      label: "Abiertos",
      value: summary.openTickets,
      icon: "🔓",
      bg: "bg-[#DBEAFE]",
      text: "text-[#1E40AF]",
    },
    {
      label: "En proceso",
      value: summary.inProgressTickets,
      icon: "⏳",
      bg: "bg-[#FEF3C7]",
      text: "text-[#D97706]",
    },
    {
      label: "Resueltos",
      value: summary.resolvedTickets,
      icon: "✅",
      bg: "bg-[#D1FAE5]",
      text: "text-[#10B981]",
    },
  ];

  return (
    <div className="p-8 bg-[#F8FAFC] min-h-screen">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Encabezado */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-[#0F172A]">Gestión de tickets</h1>
            <p className="text-sm text-[#64748B] mt-1">
              Visualiza, filtra y gestiona las solicitudes de soporte.
            </p>
          </div>
          <Button variant="primary">+ Nuevo ticket</Button>
        </div>

        {/* Métricas rápidas */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {summaryCards.map((card) => (
            <div
              key={card.label}
              className="bg-white p-5 rounded-2xl border border-[#E2E8F0] shadow-sm flex items-center justify-between"
            >
              <div>
                <p className="text-xs font-semibold text-[#64748B] uppercase tracking-wider">
                  {card.label}
                </p>
                <p className={`text-2xl font-bold mt-1 ${card.text}`}>{card.value}</p>
              </div>
              <div
                className={`h-10 w-10 ${card.bg} ${card.text} rounded-xl flex items-center justify-center text-lg`}
              >
                {card.icon}
              </div>
            </div>
          ))}
        </div>

        {/* Tabla de tickets */}
        <div className="bg-white rounded-2xl border border-[#E2E8F0] shadow-sm overflow-hidden">
          <div className="p-5 border-b border-[#F1F5F9] flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            <h2 className="text-base font-bold text-[#0F172A]">
              {filtered ? "Resultados" : "Todos los tickets"}
            </h2>
            {/* La key reinicia los campos cuando los filtros cambian desde otro lugar (menú lateral) */}
            <TicketFilters key={buildQuery(filtersForUrl(filters))} {...filters} />
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-[#F8FAFC] text-[11px] font-bold text-[#64748B] uppercase tracking-wider border-b border-[#E2E8F0]">
                  <th className="py-3.5 px-6">ID</th>
                  <th className="py-3.5 px-6">Asunto</th>
                  <th className="py-3.5 px-6">Usuario</th>
                  <th className="py-3.5 px-6">Área</th>
                  <th className="py-3.5 px-6">Estado</th>
                  <th className="py-3.5 px-6">Prioridad</th>
                  <th className="py-3.5 px-6">Fecha</th>
                  <th className="py-3.5 px-6 text-right">Acción</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#F1F5F9] text-xs text-[#475569]">
                {tickets.length === 0 && (
                  <tr>
                    <td colSpan={8} className="py-10 px-6 text-center text-sm text-[#94A3B8]">
                      {result.totalItems > 0 ? (
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
                      )}
                    </td>
                  </tr>
                )}
                {tickets.map((ticket) => (
                  <tr key={ticket.id} className="hover:bg-[#F8FAFC] transition-colors">
                    <td className="py-4 px-6 font-bold text-[#2563EB]">
                      <Link
                        href={`/tickets/${ticket.id}`}
                        className="hover:underline"
                        title={ticket.id}
                      >
                        #{shortId(ticket.id)}
                      </Link>
                    </td>
                    <td className="py-4 px-6 font-semibold text-[#0F172A] max-w-xs truncate">
                      <Link href={`/tickets/${ticket.id}`} className="hover:text-[#2563EB]">
                        {ticket.title}
                      </Link>
                    </td>
                    <td className="py-4 px-6">{ticket.createdBy.name}</td>
                    <td className="py-4 px-6 text-[#64748B]">{ticket.area ?? "Sin asignar"}</td>
                    <td className="py-4 px-6 whitespace-nowrap">
                      <StatusBadge status={ticket.status} />
                    </td>
                    <td className="py-4 px-6 whitespace-nowrap">
                      <PriorityBadge priority={ticket.priority} />
                    </td>
                    <td className="py-4 px-6 text-[#94A3B8] whitespace-nowrap">
                      {formatDateTime(ticket.createdAt)}
                    </td>
                    <td className="py-4 px-6 text-right whitespace-nowrap">
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
