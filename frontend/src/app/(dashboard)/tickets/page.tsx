import Link from "next/link";
import { connection } from "next/server";
import { Button } from "@/components/ui/Button";
import { StatusBadge, PriorityBadge } from "@/components/ui/Badge";
import { formatDateTime, shortId } from "@/lib/format";
import { getTicketStatusSummary } from "@/lib/ticket-summary";
import { ticketsService } from "@/services/tickets";

export default async function TicketsPage() {
  // Renderiza en cada solicitud: el listado no debe obtenerse ni congelarse durante el build.
  await connection();
  const [{ items: tickets }, summary] = await Promise.all([
    ticketsService.getAll({ pageSize: 50 }),
    getTicketStatusSummary(),
  ]);

  // Mismos conteos que el menú lateral.
  const summaryCards = [
    {
      label: "Total tickets",
      value: summary.total,
      icon: "📋",
      bg: "bg-[#EFF6FF]",
      text: "text-[#2563EB]",
    },
    {
      label: "Abiertos",
      value: summary.open,
      icon: "🔓",
      bg: "bg-[#DBEAFE]",
      text: "text-[#1E40AF]",
    },
    {
      label: "En proceso",
      value: summary.inProgress,
      icon: "⏳",
      bg: "bg-[#FEF3C7]",
      text: "text-[#D97706]",
    },
    {
      label: "Resueltos",
      value: summary.resolved,
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
          <div className="p-5 border-b border-[#F1F5F9] flex flex-col sm:flex-row items-center justify-between gap-4">
            <h2 className="text-base font-bold text-[#0F172A]">Todos los tickets</h2>
            <input
              type="text"
              placeholder="Filtrar por título o ID..."
              className="w-full sm:w-64 bg-[#F8FAFC] border border-[#E2E8F0] text-xs rounded-xl px-3 py-2 text-[#0F172A] placeholder-[#94A3B8] outline-none focus:border-[#2563EB]"
            />
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
                      No hay tickets registrados.
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
                    <td className="py-4 px-6">
                      <StatusBadge status={ticket.status} />
                    </td>
                    <td className="py-4 px-6">
                      <PriorityBadge priority={ticket.priority} />
                    </td>
                    <td className="py-4 px-6 text-[#94A3B8]">{formatDateTime(ticket.createdAt)}</td>
                    <td className="py-4 px-6 text-right">
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
        </div>
      </div>
    </div>
  );
}
