import Link from "next/link";

const areaMetrics = [
  { name: "Backend", total: 42, resolved: 38, avgTime: "18m", rate: 90 },
  { name: "Frontend", total: 35, resolved: 31, avgTime: "12m", rate: 88 },
  { name: "DevOps & Redes", total: 19, resolved: 17, avgTime: "25m", rate: 89 },
  { name: "Seguridad", total: 12, resolved: 12, avgTime: "15m", rate: 100 },
];

export default function MetricasPage() {
  return (
    <div className="p-8 bg-[#F8FAFC] dark:bg-[#0B0F19] min-h-screen transition-colors">
      <div className="max-w-7xl mx-auto space-y-6">
        
        {/* Encabezado Principal */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-[#0F172A] dark:text-white">Reportes y Métricas</h1>
            <p className="text-sm text-[#64748B] dark:text-[#94A3B8] mt-1">
              Análisis del rendimiento operacional, tiempos de respuesta e impacto de la IA.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <select className="bg-white dark:bg-[#111827] border border-[#E2E8F0] dark:border-[#1E293B] text-xs font-semibold rounded-xl px-3.5 py-2 text-[#0F172A] dark:text-white outline-none shadow-sm transition-colors">
              <option>Últimos 30 días</option>
              <option>Este mes</option>
              <option>Último trimestre</option>
            </select>

            <button className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-white dark:bg-[#111827] border border-[#E2E8F0] dark:border-[#1E293B] hover:bg-[#F8FAFC] dark:hover:bg-[#1E293B] text-[#0F172A] dark:text-white text-xs font-semibold rounded-xl transition-colors shadow-sm">
              <span>📊</span> Exportar PDF
            </button>
          </div>
        </div>

        {/* Tarjetas de Indicadores Clave (KPIs) */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white dark:bg-[#111827] p-5 rounded-2xl border border-[#E2E8F0] dark:border-[#1E293B] shadow-sm flex items-center justify-between transition-colors">
            <div>
              <p className="text-xs font-semibold text-[#64748B] dark:text-[#94A3B8] uppercase tracking-wider">Total Tickets Atendidos</p>
              <p className="text-2xl font-bold text-[#0F172A] dark:text-white mt-1">108</p>
              <span className="text-[11px] font-semibold text-[#10B981] dark:text-[#34D399]">↑ 12% vs mes anterior</span>
            </div>
            <div className="h-10 w-10 bg-[#EFF6FF] dark:bg-[#1E3A8A]/40 text-[#2563EB] dark:text-[#60A5FA] rounded-xl flex items-center justify-center font-bold text-lg">
              📈
            </div>
          </div>

          <div className="bg-white dark:bg-[#111827] p-5 rounded-2xl border border-[#E2E8F0] dark:border-[#1E293B] shadow-sm flex items-center justify-between transition-colors">
            <div>
              <p className="text-xs font-semibold text-[#64748B] dark:text-[#94A3B8] uppercase tracking-wider">Tasa de Resolución</p>
              <p className="text-2xl font-bold text-[#10B981] dark:text-[#34D399] mt-1">90.7%</p>
              <span className="text-[11px] font-semibold text-[#10B981] dark:text-[#34D399]">Meta: 85%</span>
            </div>
            <div className="h-10 w-10 bg-[#D1FAE5] dark:bg-[#064E3B]/40 text-[#10B981] dark:text-[#34D399] rounded-xl flex items-center justify-center font-bold text-lg">
              🎯
            </div>
          </div>

          <div className="bg-white dark:bg-[#111827] p-5 rounded-2xl border border-[#E2E8F0] dark:border-[#1E293B] shadow-sm flex items-center justify-between transition-colors">
            <div>
              <p className="text-xs font-semibold text-[#64748B] dark:text-[#94A3B8] uppercase tracking-wider">Tiempo Resp. Promedio</p>
              <p className="text-2xl font-bold text-[#2563EB] dark:text-[#60A5FA] mt-1">14m</p>
              <span className="text-[11px] font-semibold text-[#10B981] dark:text-[#34D399]">↓ 3m más rápido</span>
            </div>
            <div className="h-10 w-10 bg-[#DBEAFE] dark:bg-[#1E3A8A]/40 text-[#1E40AF] dark:text-[#93C5FD] rounded-xl flex items-center justify-center font-bold text-lg">
              ⚡
            </div>
          </div>

          <div className="bg-white dark:bg-[#111827] p-5 rounded-2xl border border-[#E2E8F0] dark:border-[#1E293B] shadow-sm flex items-center justify-between transition-colors">
            <div>
              <p className="text-xs font-semibold text-[#64748B] dark:text-[#94A3B8] uppercase tracking-wider">Sugerencias IA Aceptadas</p>
              <p className="text-2xl font-bold text-[#0F172A] dark:text-white mt-1">84%</p>
              <span className="text-[11px] font-semibold text-[#2563EB] dark:text-[#60A5FA]">432 casos resueltos con RAG</span>
            </div>
            <div className="h-10 w-10 bg-[#EFF6FF] dark:bg-[#1E3A8A]/40 text-[#2563EB] dark:text-[#60A5FA] rounded-xl flex items-center justify-center font-bold text-lg">
              🤖
            </div>
          </div>
        </div>

        {/* Sección de Paneles de Desglose */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
          
          {/* Tabla por Área/Departamento */}
          <div className="lg:col-span-2 bg-white dark:bg-[#111827] rounded-2xl border border-[#E2E8F0] dark:border-[#1E293B] shadow-sm p-6 space-y-4 transition-colors">
            <div className="border-b border-[#F1F5F9] dark:border-[#1E293B] pb-4">
              <h2 className="text-base font-bold text-[#0F172A] dark:text-white">Rendimiento por Área Técnica</h2>
              <p className="text-xs text-[#64748B] dark:text-[#94A3B8]">Métricas agregadas por departamento operacional</p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="text-[11px] font-bold text-[#64748B] dark:text-[#94A3B8] uppercase tracking-wider border-b border-[#E2E8F0] dark:border-[#1E293B]">
                    <th className="py-3 px-2">Área</th>
                    <th className="py-3 px-2">Total Tickets</th>
                    <th className="py-3 px-2">Resueltos</th>
                    <th className="py-3 px-2">Tiempo Prom.</th>
                    <th className="py-3 px-2 text-right">Efectividad</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#F1F5F9] dark:divide-[#1E293B] text-xs text-[#475569] dark:text-[#CBD5E1]">
                  {areaMetrics.map((area) => (
                    <tr key={area.name} className="hover:bg-[#F8FAFC] dark:hover:bg-[#1E293B]/50 transition-colors">
                      <td className="py-3.5 px-2 font-bold text-[#0F172A] dark:text-white">{area.name}</td>
                      <td className="py-3.5 px-2">{area.total}</td>
                      <td className="py-3.5 px-2 text-[#10B981] dark:text-[#34D399] font-semibold">{area.resolved}</td>
                      <td className="py-3.5 px-2 text-[#64748B] dark:text-[#94A3B8]">{area.avgTime}</td>
                      <td className="py-3.5 px-2 text-right">
                        <span className="inline-block bg-[#EFF6FF] dark:bg-[#1E3A8A]/50 text-[#1D4ED8] dark:text-[#93C5FD] text-[11px] font-bold px-2.5 py-0.5 rounded-full">
                          {area.rate}%
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Tarjeta de Métricas IA */}
          <div className="bg-white dark:bg-[#111827] rounded-2xl border border-[#E2E8F0] dark:border-[#1E293B] shadow-sm p-6 space-y-5 transition-colors">
            <div className="border-b border-[#F1F5F9] dark:border-[#1E293B] pb-3 flex items-center justify-between">
              <h2 className="text-base font-bold text-[#0F172A] dark:text-white">Impacto de Synapdesk IA</h2>
              <span className="text-xs text-[#2563EB] dark:text-[#60A5FA] font-bold">RAG Engine</span>
            </div>

            <div className="space-y-4 text-xs">
              <div>
                <div className="flex justify-between font-semibold text-[#0F172A] dark:text-white mb-1">
                  <span>Precisión de Clasificación</span>
                  <span>96%</span>
                </div>
                <div className="w-full h-2 bg-[#F1F5F9] dark:bg-[#1E293B] rounded-full overflow-hidden">
                  <div className="bg-[#2563EB] dark:bg-[#60A5FA] h-full rounded-full w-[96%]" />
                </div>
              </div>

              <div>
                <div className="flex justify-between font-semibold text-[#0F172A] dark:text-white mb-1">
                  <span>Ahorro Estimado de Tiempo</span>
                  <span>~4.5 hrs / día</span>
                </div>
                <div className="w-full h-2 bg-[#F1F5F9] dark:bg-[#1E293B] rounded-full overflow-hidden">
                  <div className="bg-[#10B981] dark:bg-[#34D399] h-full rounded-full w-[85%]" />
                </div>
              </div>

              <div>
                <div className="flex justify-between font-semibold text-[#0F172A] dark:text-white mb-1">
                  <span>Consultas resueltas sin escalamiento</span>
                  <span>62%</span>
                </div>
                <div className="w-full h-2 bg-[#F1F5F9] dark:bg-[#1E293B] rounded-full overflow-hidden">
                  <div className="bg-[#3B82F6] dark:bg-[#60A5FA] h-full rounded-full w-[62%]" />
                </div>
              </div>
            </div>

            <div className="pt-3 border-t border-[#F1F5F9] dark:border-[#1E293B] bg-[#F8FAFC] dark:bg-[#1E293B]/40 p-3 rounded-xl text-xs text-[#475569] dark:text-[#94A3B8]">
              💡 <span className="font-semibold text-[#0F172A] dark:text-white">Sugerencia del sistema:</span> Agregar más documentación sobre <i>DevOps</i> para elevar la precisión en esa categoría.
            </div>
          </div>

        </div>

      </div>
    </div>
  );
}