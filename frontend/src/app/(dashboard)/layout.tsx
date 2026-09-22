import { Header } from "@/components/layout/Header";
import { Sidebar } from "@/components/layout/Sidebar";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-[#F8FAFC] dark:bg-[#0B0F19] transition-colors">
      {/* Sidebar de arriba a abajo a la izquierda */}
      <Sidebar />

      {/* Columna derecha con Header y Contenido */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto bg-[#F8FAFC] dark:bg-[#0B0F19] transition-colors">
          {children}
        </main>
      </div>
    </div>
  );
}