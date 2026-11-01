// Estado de carga del listado y del detalle mientras los services responden.
export default function TicketsLoading() {
  return (
    <div className="p-8 bg-[#F8FAFC] min-h-screen" aria-busy="true" aria-live="polite">
      <div className="max-w-7xl mx-auto space-y-6 animate-pulse">
        <div className="h-8 w-64 bg-[#E2E8F0] rounded-lg" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }, (_, index) => (
            <div key={index} className="h-24 bg-white border border-[#E2E8F0] rounded-2xl" />
          ))}
        </div>
        <div className="h-80 bg-white border border-[#E2E8F0] rounded-2xl" />
        <span className="sr-only">Cargando tickets…</span>
      </div>
    </div>
  );
}
