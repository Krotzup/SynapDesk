import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { StatusBadge, PriorityBadge } from "@/components/ui/Badge";
import { TicketStatus, TicketPriority } from "@/types";

const ticketsList = [
  {
    id: "TCK-4827",
    title: "Error al conectar con la base de datos",
    user: "Carlos Méndez",
    area: "Backend",
    status: "open" as TicketStatus,
    priority: "high" as TicketPriority,
    date: "08 sep. 2025, 10:24",
  },
  {
    id: "TCK-4826",
    title: "Lentitud en el proceso de checkout",
    user: "Ana Torres",
    area: "Frontend",
    status: "in_progress" as TicketStatus,
    priority: "medium" as TicketPriority,
    date: "08 sep. 2025, 09:15",
  },
  {
    id: "TCK-4825",
    title: "Fallo en la autenticación mediante Google SSO",
    user: "Roberto Gómez",
    area: "Seguridad",
    status: "open" as TicketStatus,
    priority: "high" as TicketPriority,
    date: "07 sep. 2025, 18:30",
  },
  {
    id: "TCK-4824",
    title: "Actualizar documentación de API v2",
    user: "Laura Silva",
    area: "DevOps",
    status: "resolved" as TicketStatus,
    priority: "low" as TicketPriority,
    date: "07 sep. 2025, 14:10",
  },
  {
    id: "TCK-4823",
    title: "Error de renderizado en panel de métricas",
    user: "Valentina González",
    area: "Frontend",
    status: "resolved" as TicketStatus,
    priority: "medium" as TicketPriority,
    date: "06 sep. 2025, 11:45",
  },
];

export default function TicketsPage() {
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
          {[
            {
              label: "Total tickets",
              value: "24",
              icon: "📋",
              bg: "bg-[#EFF6FF]",
              text: "text-[#2563EB]",
            },
            {
              label: "Abiertos",
              value: "12",
              icon: "🔓",
              bg: "bg-[#DBEAFE]",
              text: "text-[#1E40AF]",
            },
            {
              label: "En proceso",
              value: "7",
              icon: "⏳",
              bg: "bg-[#FEF3C7]",
              text: "text-[#D97706]",
            },
            {
              label: "Resueltos",
              value: "5",
              icon: "✅",
              bg: "bg-[#D1FAE5]",
              text: "text-[#10B981]",
            },
          ].map((card) => (
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
                {ticketsList.map((ticket) => (
                  <tr key={ticket.id} className="hover:bg-[#F8FAFC] transition-colors">
                    <td className="py-4 px-6 font-bold text-[#2563EB]">
                      <Link href={`/tickets/${ticket.id}`} className="hover:underline">
                        #{ticket.id}
                      </Link>
                    </td>
                    <td className="py-4 px-6 font-semibold text-[#0F172A] max-w-xs truncate">
                      <Link href={`/tickets/${ticket.id}`} className="hover:text-[#2563EB]">
                        {ticket.title}
                      </Link>
                    </td>
                    <td className="py-4 px-6">{ticket.user}</td>
                    <td className="py-4 px-6 text-[#64748B]">{ticket.area}</td>
                    <td className="py-4 px-6">
                      <StatusBadge status={ticket.status} />
                    </td>
                    <td className="py-4 px-6">
                      <PriorityBadge priority={ticket.priority} />
                    </td>
                    <td className="py-4 px-6 text-[#94A3B8]">{ticket.date}</td>
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
