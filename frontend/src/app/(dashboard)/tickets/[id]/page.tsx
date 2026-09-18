interface TicketDetailPageProps {
  params: Promise<{ id: string }>;
}

export default async function TicketDetailPage({ params }: TicketDetailPageProps) {
  const { id } = await params;

  return (
    <div className="p-8 bg-[#F8FAFC] dark:bg-[#0B0F19] min-h-screen transition-colors">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start max-w-7xl mx-auto">
        
        {/* Panel Izquierdo: Detalle del Ticket */}
        <div className="lg:col-span-2 space-y-6 bg-white dark:bg-[#111827] p-6 rounded-2xl border border-[#E2E8F0] dark:border-[#1E293B] shadow-sm transition-colors">
          <a href="/tickets" className="inline-flex items-center gap-2 text-sm text-[#2563EB] dark:text-[#60A5FA] font-medium hover:underline mb-2">
            ← Volver a tickets
          </a>

          <div className="flex flex-wrap items-center gap-3">
            <span className="bg-[#2563EB] text-white font-bold text-xs px-3 py-1 rounded-md">
              #{id || "TCK-4827"}
            </span>
            <h1 className="text-xl font-bold text-[#0F172A] dark:text-white">Error al conectar con la base de datos</h1>
            <span className="inline-flex items-center gap-1.5 bg-[#DBEAFE] dark:bg-[#1E3A8A]/60 text-[#1E40AF] dark:text-[#93C5FD] text-xs font-semibold px-3 py-1 rounded-full">
              <span className="h-1.5 w-1.5 rounded-full bg-[#2563EB] dark:bg-[#60A5FA]" /> Abierto
            </span>
          </div>

          <p className="text-sm text-[#64748B] dark:text-[#94A3B8] leading-relaxed">
            No se puede conectar al servidor de base de datos desde la aplicación. El error aparece al intentar realizar la consulta.
          </p>

          <div className="grid grid-cols-3 gap-4 pt-4 border-t border-[#F1F5F9] dark:border-[#1E293B]">
            <div>
              <p className="text-xs text-[#94A3B8] font-medium">Usuario</p>
              <p className="text-sm font-semibold text-[#0F172A] dark:text-white mt-1">Carlos Méndez</p>
            </div>
            <div>
              <p className="text-xs text-[#94A3B8] font-medium">Fecha de creación</p>
              <p className="text-sm font-semibold text-[#0F172A] dark:text-white mt-1">08 sep. 2025, 10:24</p>
            </div>
            <div>
              <p className="text-xs text-[#94A3B8] font-medium">Área</p>
              <p className="text-sm font-semibold text-[#0F172A] dark:text-white mt-1">Backend</p>
            </div>
          </div>

          <div className="pt-4 border-t border-[#F1F5F9] dark:border-[#1E293B]">
            <p className="text-xs font-semibold text-[#64748B] dark:text-[#94A3B8] uppercase tracking-wider mb-2">Archivo adjunto</p>
            <div className="flex items-center justify-between p-3 bg-[#F8FAFC] dark:bg-[#1E293B]/40 border border-[#E2E8F0] dark:border-[#1E293B] rounded-xl max-w-md">
              <div className="flex items-center gap-3">
                <span className="p-2 bg-white dark:bg-[#1E293B] rounded-lg border border-[#E2E8F0] dark:border-[#334155] text-[#64748B] dark:text-[#94A3B8]">📄</span>
                <div>
                  <p className="text-xs font-semibold text-[#0F172A] dark:text-white">error_log.txt</p>
                  <p className="text-[11px] text-[#94A3B8]">2.4 MB</p>
                </div>
              </div>
              <button className="text-[#64748B] dark:text-[#94A3B8] hover:text-[#0F172A] dark:hover:text-white text-sm">↓</button>
            </div>
          </div>

          <div className="pt-4 border-t border-[#F1F5F9] dark:border-[#1E293B]">
            <p className="text-xs font-semibold text-[#64748B] dark:text-[#94A3B8] uppercase tracking-wider mb-2">Descripción adicional</p>
            <div className="p-4 bg-[#F8FAFC] dark:bg-[#1E293B]/40 border border-[#E2E8F0] dark:border-[#1E293B] rounded-xl text-sm text-[#475569] dark:text-[#CBD5E1]">
              Revisé los logs y parece un problema de conexión con el servidor. Adjunto el archivo con el error completo.
            </div>
          </div>
        </div>

        {/* Panel Derecho: Asistente IA */}
        <div className="bg-white dark:bg-[#111827] p-6 rounded-2xl border border-[#3B82F6]/30 dark:border-[#1E293B] shadow-sm space-y-5 transition-colors">
          <div className="flex items-center gap-2 text-[#2563EB] dark:text-[#60A5FA] font-bold text-lg">
            <span>🤖</span> Asistente IA
          </div>

          <div>
            <p className="text-xs text-[#94A3B8] font-medium mb-1">Categoría</p>
            <span className="inline-block bg-[#EFF6FF] dark:bg-[#1E3A8A]/50 text-[#1D4ED8] dark:text-[#93C5FD] text-xs font-semibold px-3 py-1 rounded-full">
              Base de Datos
            </span>
          </div>

          <div>
            <p className="text-xs text-[#94A3B8] font-medium mb-1">Prioridad Estimada</p>
            <span className="inline-block bg-[#FEE2E2] dark:bg-[#7F1D1D]/50 text-[#DC2626] dark:text-[#F87171] text-xs font-semibold px-3 py-1 rounded-full">
              🔴 Alta
            </span>
          </div>

          <div className="pt-2">
            <p className="text-xs text-[#2563EB] dark:text-[#60A5FA] font-bold mb-1">Recomendación Generada</p>
            <p className="text-xs text-[#475569] dark:text-[#CBD5E1] leading-relaxed">
              El error se debe a un problema de conexión con el servidor de base de datos. Verifica que el servicio esté en ejecución, revisa las credenciales de conexión y la configuración de red. Si el problema persiste, revisa los logs del servidor y la configuración del pool de conexiones.
            </p>
          </div>

          <div className="pt-2">
            <p className="text-xs text-[#2563EB] dark:text-[#60A5FA] font-bold mb-1">Fuentes Consultadas (RAG)</p>
            <div className="flex items-center gap-2 text-xs bg-[#EFF6FF] dark:bg-[#1E3A8A]/50 text-[#1D4ED8] dark:text-[#93C5FD] p-2 rounded-lg font-medium">
              📄 Manual_Postgres.pdf
            </div>
          </div>

          <div className="pt-4 border-t border-[#F1F5F9] dark:border-[#1E293B] space-y-2">
            <p className="text-xs text-[#2563EB] dark:text-[#60A5FA] font-bold mb-2">Acciones sugeridas</p>
            <button className="w-full py-2.5 bg-[#0D9488] hover:bg-[#0F766E] text-white text-xs font-semibold rounded-xl transition-colors">
              ✓ Aceptar y Resolver
            </button>
            <button className="w-full py-2.5 bg-white dark:bg-[#1E293B] border border-[#E2E8F0] dark:border-[#334155] hover:bg-[#F8FAFC] dark:hover:bg-[#334155] text-[#475569] dark:text-white text-xs font-semibold rounded-xl transition-colors">
              ✎ Editar
            </button>
            <button className="w-full py-2.5 bg-white dark:bg-[#1E293B] border border-[#E2E8F0] dark:border-[#334155] hover:bg-[#FEF2F2] dark:hover:bg-[#450A0A] text-[#EF4444] dark:text-[#F87171] text-xs font-semibold rounded-xl transition-colors">
              🗑 Descartar
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}