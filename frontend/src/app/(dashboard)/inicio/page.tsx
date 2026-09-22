import Link from "next/link";

const recentTickets = [
  {
    id: "TCK-4827",
    title: "Error al conectar con la base de datos",
    status: "Abierto",
    statusColor: "bg-[#DBEAFE] dark:bg-[#1E3A8A]/60 text-[#1E40AF] dark:text-[#93C5FD]",
    date: "Hace 10 min",
  },
  {
    id: "TCK-4826",
    title: "Lentitud en el proceso de checkout",
    status: "En Proceso",
    statusColor: "bg-[#FEF3C7] dark:bg-[#78350F]/50 text-[#92400E] dark:text-[#FDE68A]",
    date: "Hace 1 hora",
  },
  {
    id: "TCK-4825",
    title: "Fallo en la autenticación mediante Google SSO",
    status: "Abierto",
    statusColor: "bg-[#DBEAFE] dark:bg-[#1E3A8A]/60 text-[#1E40AF] dark:text-[#93C5FD]",
    date: "Hace 3 horas",
  },
];

const kbArticles = [
  { title: "Manual_Postgres.pdf", category: "Base de Datos" },
  { title: "Guia_Despliegue_API.pdf", category: "DevOps" },
  { title: "Politicas_Seguridad_2025.pdf", category: "Seguridad" },
];

export default function InicioPage() {
  return (
    <div className="p-8 bg-[#F8FAFC] dark:bg-[#0B0F19] min-h-screen transition-colors">
      <div className="max-w-7xl mx-auto space-y-8">
        
        {/* Banner de Bienvenida */}
        <div className="bg-gradient-to-r from-[#0B132B] to-[#1E3A8A] dark:from-[#090D16] dark:to-[#1E293B] rounded-2xl p-6 sm:p-8 text-white shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6 border border-transparent dark:border-[#1E293B]">
          <div className="space-y-2">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
              ¡Hola, Valentina! 👋
            </h1>
            <p className="text-sm text-[#94A3B8] max-w-xl">
              Bienvenida a Synapdesk. Aquí tienes un resumen general de las solicitudes activas y el estado del sistema.
            </p>
          </div>
          <Link
            href="/tickets"
            className="px-5 py-2.5 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-sm font-semibold rounded-xl transition-colors shadow-md whitespace-nowrap"
          >
            Ver todos los tickets →
          </Link>
        </div>

        {/* Tarjetas de Métricas Rápidas (SVG sin emojis) */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          
          <div className="bg-white dark:bg-[#111827] p-5 rounded-2xl border border-[#E2E8F0] dark:border-[#1E293B] shadow-sm flex items-center justify-between transition-colors">
            <div>
              <p className="text-xs font-semibold text-[#64748B] dark:text-[#94A3B8] uppercase tracking-wider">Tickets Activos</p>
              <p className="text-2xl font-bold text-[#0F172A] dark:text-white mt-1">19</p>
            </div>
            <div className="h-10 w-10 bg-[#EFF6FF] dark:bg-[#1E3A8A]/40 text-[#2563EB] dark:text-[#60A5FA] rounded-xl flex items-center justify-center">
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 5v2m0 4v2m0 4v2M5 5a2 2 0 00-2 2v3a2 2 0 110 4v3a2 2 0 002 2h14a2 2 0 002-2v-3a2 2 0 110-4V7a2 2 0 00-2-2H5z" />
              </svg>
            </div>
          </div>

          <div className="bg-white dark:bg-[#111827] p-5 rounded-2xl border border-[#E2E8F0] dark:border-[#1E293B] shadow-sm flex items-center justify-between transition-colors">
            <div>
              <p className="text-xs font-semibold text-[#64748B] dark:text-[#94A3B8] uppercase tracking-wider">Requieren Atención</p>
              <p className="text-2xl font-bold text-[#DC2626] dark:text-[#EF4444] mt-1">4</p>
            </div>
            <div className="h-10 w-10 bg-[#FEE2E2] dark:bg-[#7F1D1D]/40 text-[#DC2626] dark:text-[#F87171] rounded-xl flex items-center justify-center">
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
          </div>

          <div className="bg-white dark:bg-[#111827] p-5 rounded-2xl border border-[#E2E8F0] dark:border-[#1E293B] shadow-sm flex items-center justify-between transition-colors">
            <div>
              <p className="text-xs font-semibold text-[#64748B] dark:text-[#94A3B8] uppercase tracking-wider">Resueltos Hoy</p>
              <p className="text-2xl font-bold text-[#10B981] dark:text-[#34D399] mt-1">8</p>
            </div>
            <div className="h-10 w-10 bg-[#D1FAE5] dark:bg-[#064E3B]/40 text-[#10B981] dark:text-[#34D399] rounded-xl flex items-center justify-center">
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          </div>

          <div className="bg-white dark:bg-[#111827] p-5 rounded-2xl border border-[#E2E8F0] dark:border-[#1E293B] shadow-sm flex items-center justify-between transition-colors">
            <div>
              <p className="text-xs font-semibold text-[#64748B] dark:text-[#94A3B8] uppercase tracking-wider">Tiempo Resp. Prom.</p>
              <p className="text-2xl font-bold text-[#0F172A] dark:text-white mt-1">14m</p>
            </div>
            <div className="h-10 w-10 bg-[#F1F5F9] dark:bg-[#1E293B] text-[#64748B] dark:text-[#94A3B8] rounded-xl flex items-center justify-center">
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          </div>
        </div>

        {/* Sección de dos columnas */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
          
          {/* Tickets Recientes */}
          <div className="lg:col-span-2 bg-white dark:bg-[#111827] rounded-2xl border border-[#E2E8F0] dark:border-[#1E293B] shadow-sm p-6 space-y-4 transition-colors">
            <div className="flex items-center justify-between border-b border-[#F1F5F9] dark:border-[#1E293B] pb-4">
              <div>
                <h2 className="text-base font-bold text-[#0F172A] dark:text-white">Tickets Recientes</h2>
                <p className="text-xs text-[#64748B] dark:text-[#94A3B8]">Últimas solicitudes registradas en el sistema</p>
              </div>
              <Link href="/tickets" className="text-xs font-semibold text-[#2563EB] dark:text-[#60A5FA] hover:underline">
                Ver todo
              </Link>
            </div>

            <div className="divide-y divide-[#F1F5F9] dark:divide-[#1E293B]">
              {recentTickets.map((ticket) => (
                <div key={ticket.id} className="py-3.5 flex items-center justify-between gap-4 hover:bg-[#F8FAFC] dark:hover:bg-[#1E293B]/50 px-2 rounded-xl transition-colors">
                  <div className="space-y-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-[#2563EB] dark:text-[#60A5FA]">#{ticket.id}</span>
                      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${ticket.statusColor}`}>
                        {ticket.status}
                      </span>
                    </div>
                    <p className="text-sm font-semibold text-[#0F172A] dark:text-white truncate">
                      {ticket.title}
                    </p>
                  </div>
                  <div className="flex items-center gap-4 shrink-0">
                    <span className="text-xs text-[#94A3B8] hidden sm:inline">{ticket.date}</span>
                    <Link
                      href={`/tickets/${ticket.id}`}
                      className="text-xs font-semibold text-[#2563EB] dark:text-[#60A5FA] bg-[#EFF6FF] dark:bg-[#1E3A8A]/50 hover:bg-[#DBEAFE] dark:hover:bg-[#1E3A8A] px-3 py-1.5 rounded-lg transition-colors"
                    >
                      Atender →
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Columna Derecha: Base de Conocimientos */}
          <div className="space-y-6">
            <div className="bg-white dark:bg-[#111827] rounded-2xl border border-[#E2E8F0] dark:border-[#1E293B] shadow-sm p-6 space-y-4 transition-colors">
              <div className="border-b border-[#F1F5F9] dark:border-[#1E293B] pb-3 flex items-center justify-between">
                <h2 className="text-base font-bold text-[#0F172A] dark:text-white">Base de Conocimientos</h2>
                <span className="text-xs text-[#2563EB] dark:text-[#60A5FA] font-bold">RAG</span>
              </div>
              <p className="text-xs text-[#64748B] dark:text-[#94A3B8]">
                Documentos más consultados por la IA para resolver casos:
              </p>

              <div className="space-y-2">
                {kbArticles.map((doc, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-3 bg-[#F8FAFC] dark:bg-[#1E293B]/40 border border-[#E2E8F0] dark:border-[#1E293B] rounded-xl hover:border-[#2563EB]/40 transition-colors cursor-pointer"
                  >
                    <div className="flex items-center gap-3">
                      <div className="p-1.5 bg-[#EFF6FF] dark:bg-[#1E3A8A]/40 text-[#2563EB] dark:text-[#60A5FA] rounded-lg">
                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                      </div>
                      <div>
                        <p className="text-xs font-semibold text-[#0F172A] dark:text-white">{doc.title}</p>
                        <p className="text-[10px] text-[#94A3B8]">{doc.category}</p>
                      </div>
                    </div>
                    <span className="text-xs text-[#94A3B8]">→</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-gradient-to-br from-[#EFF6FF] to-[#DBEAFE] dark:from-[#1E3A8A]/30 dark:to-[#1E293B] rounded-2xl border border-[#3B82F6]/30 p-5 text-[#1E40AF] dark:text-[#93C5FD] space-y-3">
              <div className="flex items-center gap-2 font-bold text-sm">
                <svg className="h-5 w-5 text-[#2563EB] dark:text-[#60A5FA]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
                Asistente Synapdesk
              </div>
              <p className="text-xs leading-relaxed text-[#1E3A8A] dark:text-[#BFDBFE]">
                El motor de Inteligencia Artificial está analizando los tickets entrantes para sugerir soluciones automáticas con base en tu documentación.
              </p>
            </div>
          </div>

        </div>

      </div>
    </div>
  );
}