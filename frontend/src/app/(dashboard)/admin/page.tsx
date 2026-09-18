import Link from "next/link";

const usersList = [
  {
    name: "Valentina González",
    email: "v.gonzalez@synapdesk.com",
    role: "Administrador",
    status: "Activo",
    statusColor: "bg-[#D1FAE5] text-[#065F46]",
  },
  {
    name: "Carlos Méndez",
    email: "c.mendez@synapdesk.com",
    role: "Soporte Senior",
    status: "Activo",
    statusColor: "bg-[#D1FAE5] text-[#065F46]",
  },
  {
    name: "Ana Torres",
    email: "a.torres@synapdesk.com",
    role: "Soporte Frontend",
    status: "Activo",
    statusColor: "bg-[#D1FAE5] text-[#065F46]",
  },
  {
    name: "Roberto Gómez",
    email: "r.gomez@synapdesk.com",
    role: "Seguridad",
    status: "Inactivo",
    statusColor: "bg-[#F1F5F9] text-[#64748B]",
  },
];

export default function AdminPage() {
  return (
    <div className="p-8 bg-[#F8FAFC] min-h-screen">
      <div className="max-w-7xl mx-auto space-y-6">
        
        {/* Encabezado Principal */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-[#0F172A]">Configuración del Sistema</h1>
            <p className="text-sm text-[#64748B] mt-1">
              Administra usuarios, roles, reglas de asignación y parámetros de la IA.
            </p>
          </div>

          <button className="inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-sm font-semibold rounded-xl transition-colors shadow-sm self-start sm:self-auto">
            <span>+</span> Invitar Usuario
          </button>
        </div>

        {/* Navegación por Pestañas de Configuración */}
        <div className="flex items-center gap-2 border-b border-[#E2E8F0] pb-2 overflow-x-auto">
          <button className="px-4 py-2 bg-[#2563EB] text-white text-xs font-semibold rounded-xl shadow-sm">
            Gestión de Usuarios
          </button>
          <button className="px-4 py-2 bg-white border border-[#E2E8F0] hover:bg-[#F8FAFC] text-[#64748B] text-xs font-semibold rounded-xl transition-colors">
            Parámetros de IA / RAG
          </button>
          <button className="px-4 py-2 bg-white border border-[#E2E8F0] hover:bg-[#F8FAFC] text-[#64748B] text-xs font-semibold rounded-xl transition-colors">
            Notificaciones
          </button>
          <button className="px-4 py-2 bg-white border border-[#E2E8F0] hover:bg-[#F8FAFC] text-[#64748B] text-xs font-semibold rounded-xl transition-colors">
            Integraciones API
          </button>
        </div>

        {/* Sección Principal: Gestión de Usuarios */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
          
          {/* Tabla de Usuarios (2 columnas en Desktop) */}
          <div className="lg:col-span-2 bg-white rounded-2xl border border-[#E2E8F0] shadow-sm p-6 space-y-4">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-[#F1F5F9] pb-4">
              <div>
                <h2 className="text-base font-bold text-[#0F172A]">Usuarios Registrados</h2>
                <p className="text-xs text-[#64748B]">Personal con acceso a la plataforma</p>
              </div>

              <input
                type="text"
                placeholder="Buscar por nombre o email..."
                className="w-full sm:w-56 bg-[#F8FAFC] border border-[#E2E8F0] text-xs rounded-xl px-3 py-2 text-[#0F172A] outline-none focus:border-[#2563EB]"
              />
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="text-[11px] font-bold text-[#64748B] uppercase tracking-wider border-b border-[#E2E8F0]">
                    <th className="py-3.5 px-3">Usuario</th>
                    <th className="py-3.5 px-3">Rol</th>
                    <th className="py-3.5 px-3">Estado</th>
                    <th className="py-3.5 px-3 text-right">Acción</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#F1F5F9] text-xs text-[#475569]">
                  {usersList.map((user) => (
                    <tr key={user.email} className="hover:bg-[#F8FAFC] transition-colors">
                      <td className="py-3.5 px-3">
                        <div>
                          <p className="font-bold text-[#0F172A]">{user.name}</p>
                          <p className="text-[11px] text-[#94A3B8]">{user.email}</p>
                        </div>
                      </td>
                      <td className="py-3.5 px-3">
                        <span className="inline-block bg-[#EFF6FF] text-[#1D4ED8] text-[11px] font-semibold px-2.5 py-1 rounded-full">
                          {user.role}
                        </span>
                      </td>
                      <td className="py-3.5 px-3">
                        <span className={`inline-block text-[10px] font-semibold px-2.5 py-0.5 rounded-full ${user.statusColor}`}>
                          ● {user.status}
                        </span>
                      </td>
                      <td className="py-3.5 px-3 text-right space-x-2">
                        <button className="text-xs font-semibold text-[#2563EB] hover:underline">
                          Editar
                        </button>
                        <button className="text-xs font-semibold text-[#EF4444] hover:underline">
                          Eliminar
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Panel Lateral de Ajustes de IA / RAG */}
          <div className="space-y-6">
            <div className="bg-white rounded-2xl border border-[#E2E8F0] shadow-sm p-6 space-y-4">
              <div className="border-b border-[#F1F5F9] pb-3 flex items-center justify-between">
                <h2 className="text-base font-bold text-[#0F172A]">Ajustes de IA (RAG)</h2>
                <span className="text-xs text-[#2563EB] font-bold">Configuración</span>
              </div>

              <div className="space-y-4 text-xs">
                <div>
                  <label className="block font-semibold text-[#0F172A] mb-1">
                    Modelo de Lenguaje Activo
                  </label>
                  <select className="w-full bg-[#F8FAFC] border border-[#E2E8F0] text-xs rounded-xl p-2.5 text-[#0F172A] outline-none">
                    <option>Gemini 1.5 Pro (Recomendado)</option>
                    <option>Gemini 1.5 Flash</option>
                  </select>
                </div>

                <div>
                  <label className="block font-semibold text-[#0F172A] mb-1">
                    Umbral de Confianza RAG
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    defaultValue="80"
                    className="w-full accent-[#2563EB]"
                  />
                  <div className="flex justify-between text-[10px] text-[#94A3B8] mt-0.5">
                    <span>Flexible (50%)</span>
                    <span className="font-bold text-[#2563EB]">80%</span>
                    <span>Estrictamente exacto (95%)</span>
                  </div>
                </div>

                <div className="pt-2 border-t border-[#F1F5F9] space-y-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" defaultChecked className="rounded text-[#2563EB] focus:ring-0" />
                    <span className="font-medium text-[#0F172A]">Auto-clasificar área al crear ticket</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" defaultChecked className="rounded text-[#2563EB] focus:ring-0" />
                    <span className="font-medium text-[#0F172A]">Generar sugerencias de solución RAG</span>
                  </label>
                </div>

                <button className="w-full py-2.5 bg-[#2563EB] hover:bg-[#1D4ED8] text-white font-semibold rounded-xl transition-colors shadow-sm mt-2">
                  Guardar Cambios
                </button>
              </div>
            </div>
          </div>

        </div>

      </div>
    </div>
  );
}