const usersList = [
  {
    name: "Valentina González",
    email: "v.gonzalez@synapdesk.com",
    role: "admin",
    roleLabel: "Administrador",
    isActive: true,
  },
  {
    name: "Carlos Méndez",
    email: "c.mendez@synapdesk.com",
    role: "agent",
    roleLabel: "Agente",
    isActive: true,
  },
  {
    name: "Ana Torres",
    email: "a.torres@synapdesk.com",
    role: "agent",
    roleLabel: "Agente",
    isActive: true,
  },
  {
    name: "Roberto Gómez",
    email: "r.gomez@synapdesk.com",
    role: "agent",
    roleLabel: "Agente",
    isActive: false,
  },
];

export default function AdminPage() {
  return (
    <div className="p-8 bg-[#F8FAFC] min-h-screen">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Encabezado */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-[#0F172A]">Administración de usuarios</h1>
            <p className="text-sm text-[#64748B] mt-1">
              Gestión de acceso, roles y estado de las cuentas del equipo.
            </p>
          </div>
          <button className="inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-sm font-semibold rounded-xl transition-colors shadow-sm self-start sm:self-auto">
            + Invitar usuario
          </button>
        </div>

        {/* Tabla de usuarios */}
        <div className="bg-white rounded-2xl border border-[#E2E8F0] shadow-sm overflow-hidden">
          <div className="p-5 border-b border-[#F1F5F9] flex flex-col sm:flex-row items-center justify-between gap-4">
            <h2 className="text-base font-bold text-[#0F172A]">Usuarios registrados</h2>
            <input
              type="text"
              placeholder="Buscar por nombre o correo..."
              className="w-full sm:w-64 bg-[#F8FAFC] border border-[#E2E8F0] text-xs rounded-xl px-3 py-2 text-[#0F172A] placeholder-[#94A3B8] outline-none focus:border-[#2563EB]"
            />
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-[#F8FAFC] text-[11px] font-bold text-[#64748B] uppercase tracking-wider border-b border-[#E2E8F0]">
                  <th className="py-3.5 px-6">Usuario</th>
                  <th className="py-3.5 px-6">Rol</th>
                  <th className="py-3.5 px-6">Estado</th>
                  <th className="py-3.5 px-6 text-right">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#F1F5F9] text-xs text-[#475569]">
                {usersList.map((user) => (
                  <tr key={user.email} className="hover:bg-[#F8FAFC] transition-colors">
                    <td className="py-3.5 px-6">
                      <p className="font-semibold text-[#0F172A]">{user.name}</p>
                      <p className="text-[11px] text-[#94A3B8]">{user.email}</p>
                    </td>
                    <td className="py-3.5 px-6">
                      <span className="inline-block bg-[#EFF6FF] text-[#1D4ED8] text-[11px] font-semibold px-2.5 py-1 rounded-full">
                        {user.roleLabel}
                      </span>
                    </td>
                    <td className="py-3.5 px-6">
                      {user.isActive ? (
                        <span className="inline-flex items-center gap-1.5 bg-[#D1FAE5] text-[#065F46] text-[11px] font-semibold px-2.5 py-0.5 rounded-full">
                          <span className="h-1.5 w-1.5 rounded-full bg-[#10B981]" />
                          Activo
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 bg-[#F1F5F9] text-[#64748B] text-[11px] font-semibold px-2.5 py-0.5 rounded-full">
                          <span className="h-1.5 w-1.5 rounded-full bg-[#94A3B8]" />
                          Inactivo
                        </span>
                      )}
                    </td>
                    <td className="py-3.5 px-6 text-right space-x-3">
                      <button className="text-xs font-semibold text-[#2563EB] hover:underline">
                        Editar
                      </button>
                      <button className="text-xs font-semibold text-[#EF4444] hover:underline">
                        {user.isActive ? "Desactivar" : "Activar"}
                      </button>
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
