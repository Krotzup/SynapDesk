import Link from "next/link";

export default function TicketNotFound() {
  return (
    <div className="p-8 bg-[#F8FAFC] min-h-screen">
      <div className="max-w-xl mx-auto mt-16 bg-white p-8 rounded-2xl border border-[#E2E8F0] shadow-sm text-center space-y-3">
        <h1 className="text-lg font-bold text-[#0F172A]">Ticket no encontrado</h1>
        <p className="text-sm text-[#64748B]">
          El ticket que buscas no existe o ya no está disponible.
        </p>
        <Link
          href="/tickets"
          className="inline-flex items-center gap-2 text-sm text-[#2563EB] font-medium hover:underline"
        >
          ← Volver a tickets
        </Link>
      </div>
    </div>
  );
}
