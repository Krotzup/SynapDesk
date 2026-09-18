import Link from "next/link";

// Datos de ejemplo manteniendo la lógica de la app
const ticketsList = [
  {
    id: "TCK-4827",
    title: "Error al conectar con la base de datos",
    user: "Carlos Méndez",
    area: "Backend",
    status: "Abierto",
    statusColor: "bg-[#DBEAFE] text-[#1E40AF] dot-bg-[#2563EB]",
    priority: "Alta",
    priorityColor: "bg-[#FEE2E2] text-[#DC2626]",
    date: "08 sep. 2025, 10:24",
  },
  {
    id: "TCK-4826",
    title: "Lentitud en el proceso de checkout",
    user: "Ana Torres",
    area: "Frontend",
    status: "En Proceso",
    statusColor: "bg-[#FEF3C7] text-[#92400E] dot-bg-[#D97706]",
    priority: "Media",
    priorityColor: "bg-[#FEF3C7] text-[#D97706]",
    date: "08 sep. 2025, 09:15",
  },
  {
    id: "TCK-4825",
    title: "Fallo en la autenticación mediante Google SSO",
    user: "Roberto Gómez",
    area: "Seguridad",
    status: "Abierto",
    statusColor: "bg-[#DBEAFE] text-[#1E40AF] dot-bg-[#2563EB]",
    priority: "Alta",
    priorityColor: "bg-[#FEE2E2] text-[#DC2626]",
    date: "07 sep. 2025, 18:30",
  },
  {
    id: "TCK-4824",
    title: "Actualizar documentación de API v2",
    user: "Laura Silva",
    area: "DevOps",
    status: "Resuelto",
    statusColor: "bg-[#D1FAE5] text-[#065F46] dot-bg-[#10B981]",
    priority: "Baja",
    priorityColor: "bg-[#F1F5F9] text-[#64748B]",
    date: "07 sep. 2025, 14:10",
  },
  {
    id: "TCK-4823",
    title: "Error de renderizado en panel de métricas",
    user: "Valentina González",
    area: "Frontend",
    status: "Resuelto",
    statusColor: "bg-[#D1FAE5] text-[#065F46] dot-bg-[#10B981]",
    priority: "Media",
    priorityColor: "bg-[#FEF3C7] text-[#D97706]",
    date: "06 sep. 2025, 11:45",
  },
];

export default function TicketsPage() {
  return (
    <div className="p-8 bg-[#F8FAFC] min-h-screen">
      <div className="max-w-7xl mx-auto space-y-6">
        
        {/* Encabezado y Acciones Principales */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-[#0F172A]">Gestión de Tickets</h1>
            <p className="text-sm text-[#64748B] mt-1">
              Visualiza, filtra y gestiona las solicitudes de soporte en tiempo real.
            </p>
          </div>

          <button className="inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-sm font-semibold rounded-xl transition-colors shadow-sm self-start sm:self-auto">
            <span>+</span> Nuevo Ticket
          </button>
        </div>

        {/* Tarjetas de Métricas Rápidas */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white p-5 rounded-2xl border border-[#E2E8F0] shadow-sm flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-[#64748B] uppercase tracking-wider">Total Tickets</p>
              <p className="text-2xl font-bold text-[#0F172A] mt-1">24</p>
            </div>
            <div className="h-10 w-10 bg-[#EFF6FF] text-[#2563EB] rounded-xl flex items-center justify-center font-bold text-lg">
              📋
            </div>
          </div>

          <div className="bg-white p-5 rounded-2xl border border-[#E2E8F0] shadow-sm flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-[#64748B] uppercase tracking-wider">Abiertos</p>
              <p className="text-2xl font-bold text-[#2563EB] mt-1">12</p>
            </div>
            <div className="h-10 w-10 bg-[#DBEAFE] text-[#1E40AF] rounded-xl flex items-center justify-center font-bold text-lg">
              🔓
            </div>
          </div>

          <div className="bg-white p-5 rounded-2xl border border-[#E2E8F0] shadow-sm flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-[#64748B] uppercase tracking-wider">En Proceso</p>
              <p className="text-2xl font-bold text-[#D97706] mt-1">7</p>
            </div>
            <div className="h-10 w-10 bg-[#FEF3C7] text-[#D97706] rounded-xl flex items-center justify-center font-bold text-lg">
              ⏳
            </div>
          </div>

          <div className="bg-white p-5 rounded-2xl border border-[#E2E8F0] shadow-sm flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-[#64748B] uppercase tracking-wider">Resueltos</p>
              <p className="text-2xl font-bold text-[#10B981] mt-1">5</p>
            </div>
            <div className="h-10 w-10 bg-[#D1FAE5] text-[#10B981] rounded-xl flex items-center justify-center font-bold text-lg">
              ✅
            </div>
          </div>
        </div>

        {/* Tabla / Listado de Tickets */}
        <div className="bg-white rounded-2xl border border-[#E2E8F0] shadow-sm overflow-hidden">
          <div className="p-5 border-b border-[#F1F5F9] flex flex-col sm:flex-row items-center justify-between gap-4">
            <h2 className="text-base font-bold text-[#0F172A]">Todos los Tickets</h2>
            <div className="flex items-center gap-3 w-full sm:w-auto">
              <input
                type="text"
                placeholder="Filtrar por título o ID..."
                className="w-full sm:w-64 bg-[#F8FAFC] border border-[#E2E8F0] text-xs rounded-xl px-3 py-2 text-[#0F172A] outline-none focus:border-[#2563EB]"
              />
            </div>
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
                  <tr key={ticket.id} className="hover:bg-[#F8FAFC]/80 transition-colors">
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
                    <td className="py-4 px-6 font-medium text-[#64748B]">{ticket.area}</td>
                    <td className="py-4 px-6">
                      <span className={`inline-flex items-center gap-1.5 text-[11px] font-semibold px-2.5 py-1 rounded-full ${ticket.statusColor}`}>
                        <span className="h-1.5 w-1.5 rounded-full bg-current" />
                        {ticket.status}
                      </span>
                    </td>
                    <td className="py-4 px-6">
                      <span className={`inline-block text-[11px] font-semibold px-2.5 py-0.5 rounded-full ${ticket.priorityColor}`}>
                        {ticket.priority}
                      </span>
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