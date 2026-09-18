import Link from "next/link";

const categories = [
  { name: "Todas las áreas", count: 18, active: true },
  { name: "Base de Datos", count: 5, active: false },
  { name: "Backend", count: 4, active: false },
  { name: "Frontend", count: 4, active: false },
  { name: "DevOps & Redes", count: 3, active: false },
  { name: "Seguridad", count: 2, active: false },
];

const documents = [
  {
    id: "DOC-001",
    title: "Manual_Postgres.pdf",
    category: "Base de Datos",
    size: "4.2 MB",
    uploadedBy: "Carlos Méndez",
    updatedAt: "12 ago. 2025",
    ragHits: 142,
    status: "Indexado",
  },
  {
    id: "DOC-002",
    title: "Guia_Despliegue_API.pdf",
    category: "DevOps & Redes",
    size: "2.8 MB",
    uploadedBy: "Valentina González",
    updatedAt: "01 sep. 2025",
    ragHits: 98,
    status: "Indexado",
  },
  {
    id: "DOC-003",
    title: "Politicas_Seguridad_2025.pdf",
    category: "Seguridad",
    size: "1.5 MB",
    uploadedBy: "Roberto Gómez",
    updatedAt: "15 ene. 2025",
    ragHits: 64,
    status: "Indexado",
  },
  {
    id: "DOC-004",
    title: "Estructura_Componentes_Frontend.md",
    category: "Frontend",
    size: "512 KB",
    uploadedBy: "Ana Torres",
    updatedAt: "20 ago. 2025",
    ragHits: 41,
    status: "Indexado",
  },
  {
    id: "DOC-005",
    title: "Configuracion_Pool_Conexiones.docx",
    category: "Backend",
    size: "1.1 MB",
    uploadedBy: "Carlos Méndez",
    updatedAt: "05 sep. 2025",
    ragHits: 87,
    status: "Indexado",
  },
];

export default function DocumentosPage() {
  return (
    <div className="p-8 bg-[#F8FAFC] min-h-screen">
      <div className="max-w-7xl mx-auto space-y-6">
        
        {/* Encabezado Principal */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-[#0F172A]">Base de Conocimientos Técnica</h1>
            <p className="text-sm text-[#64748B] mt-1">
              Documentación indexada para el motor RAG del Asistente IA y consultas del equipo.
            </p>
          </div>

          <button className="inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-sm font-semibold rounded-xl transition-colors shadow-sm self-start sm:self-auto">
            <span>📤</span> Subir Documento
          </button>
        </div>

        {/* Resumen Métrico RAG */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-white p-5 rounded-2xl border border-[#E2E8F0] shadow-sm flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-[#64748B] uppercase tracking-wider">Documentos Indexados</p>
              <p className="text-2xl font-bold text-[#0F172A] mt-1">18</p>
            </div>
            <div className="h-10 w-10 bg-[#EFF6FF] text-[#2563EB] rounded-xl flex items-center justify-center font-bold text-lg">
              📚
            </div>
          </div>

          <div className="bg-white p-5 rounded-2xl border border-[#E2E8F0] shadow-sm flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-[#64748B] uppercase tracking-wider">Consultas RAG este mes</p>
              <p className="text-2xl font-bold text-[#10B981] mt-1">432</p>
            </div>
            <div className="h-10 w-10 bg-[#D1FAE5] text-[#10B981] rounded-xl flex items-center justify-center font-bold text-lg">
              🎯
            </div>
          </div>

          <div className="bg-white p-5 rounded-2xl border border-[#E2E8F0] shadow-sm flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-[#64748B] uppercase tracking-wider">Tasa de Coincidencia</p>
              <p className="text-2xl font-bold text-[#2563EB] mt-1">94.8%</p>
            </div>
            <div className="h-10 w-10 bg-[#DBEAFE] text-[#1E40AF] rounded-xl flex items-center justify-center font-bold text-lg">
              ⚡
            </div>
          </div>
        </div>

        {/* Filtros por Categoría + Buscador */}
        <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4 bg-white p-4 rounded-2xl border border-[#E2E8F0] shadow-sm">
          <div className="flex items-center gap-2 overflow-x-auto pb-2 md:pb-0 scrollbar-none">
            {categories.map((cat) => (
              <button
                key={cat.name}
                className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-colors ${
                  cat.active
                    ? "bg-[#2563EB] text-white"
                    : "bg-[#F1F5F9] text-[#64748B] hover:bg-[#E2E8F0]"
                }`}
              >
                {cat.name} ({cat.count})
              </button>
            ))}
          </div>

          <div className="w-full md:w-64">
            <input
              type="text"
              placeholder="Buscar por nombre o contenido..."
              className="w-full bg-[#F8FAFC] border border-[#E2E8F0] text-xs rounded-xl px-3.5 py-2 text-[#0F172A] outline-none focus:border-[#2563EB]"
            />
          </div>
        </div>

        {/* Tabla / Listado de Documentos */}
        <div className="bg-white rounded-2xl border border-[#E2E8F0] shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-[#F8FAFC] text-[11px] font-bold text-[#64748B] uppercase tracking-wider border-b border-[#E2E8F0]">
                  <th className="py-3.5 px-6">Documento</th>
                  <th className="py-3.5 px-6">Categoría</th>
                  <th className="py-3.5 px-6">Tamaño</th>
                  <th className="py-3.5 px-6">Subido Por</th>
                  <th className="py-3.5 px-6">Última Actualización</th>
                  <th className="py-3.5 px-6 text-center">Impacto RAG</th>
                  <th className="py-3.5 px-6 text-right">Acción</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#F1F5F9] text-xs text-[#475569]">
                {documents.map((doc) => (
                  <tr key={doc.id} className="hover:bg-[#F8FAFC]/80 transition-colors">
                    <td className="py-4 px-6">
                      <div className="flex items-center gap-3">
                        <span className="p-2 bg-[#F1F5F9] text-[#2563EB] rounded-lg font-bold">📄</span>
                        <div>
                          <p className="font-bold text-[#0F172A] hover:text-[#2563EB] cursor-pointer">
                            {doc.title}
                          </p>
                          <span className="inline-flex items-center gap-1 text-[10px] text-[#10B981] font-semibold mt-0.5">
                            ● {doc.status}
                          </span>
                        </div>
                      </div>
                    </td>
                    <td className="py-4 px-6">
                      <span className="inline-block bg-[#EFF6FF] text-[#1D4ED8] text-[11px] font-semibold px-2.5 py-1 rounded-full">
                        {doc.category}
                      </span>
                    </td>
                    <td className="py-4 px-6 text-[#64748B]">{doc.size}</td>
                    <td className="py-4 px-6 font-medium text-[#0F172A]">{doc.uploadedBy}</td>
                    <td className="py-4 px-6 text-[#94A3B8]">{doc.updatedAt}</td>
                    <td className="py-4 px-6 text-center">
                      <span className="inline-block bg-[#F1F5F9] text-[#0F172A] text-[11px] font-bold px-2.5 py-1 rounded-lg">
                        {doc.ragHits} veces usado
                      </span>
                    </td>
                    <td className="py-4 px-6 text-right space-x-2">
                      <button className="text-xs font-semibold text-[#2563EB] hover:underline">
                        Ver
                      </button>
                      <button className="text-xs font-semibold text-[#64748B] hover:text-[#0F172A]">
                        Descargar
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