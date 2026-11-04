import type { Metadata } from "next";
import Link from "next/link";
import { NewTicketForm } from "@/components/tickets/NewTicketForm";
import { USE_MOCKS } from "@/lib/config";

export const metadata: Metadata = {
  title: "Nuevo ticket | SynapDesk",
};

export default function NewTicketPage() {
  return (
    <div className="p-8 bg-[#F8FAFC] min-h-screen">
      <div className="max-w-3xl mx-auto space-y-6">
        <Link
          href="/tickets"
          className="inline-flex items-center gap-2 text-sm text-[#2563EB] font-medium hover:underline"
        >
          ← Volver a tickets
        </Link>

        <div>
          <h1 className="text-2xl font-bold text-[#0F172A]">Nuevo ticket</h1>
          <p className="text-sm text-[#64748B] mt-1">
            Registra una solicitud de soporte con un título breve y una descripción del problema.
          </p>
        </div>

        {/* Evita confundir los datos de ejemplo con tickets guardados en el backend */}
        {USE_MOCKS && (
          <p className="text-xs text-[#92400E] bg-[#FEF3C7] border border-[#FDE68A] rounded-xl px-4 py-2.5">
            <strong>Datos de ejemplo:</strong> el ticket no se guarda en el backend. Escribe
            &quot;error-simulado&quot; como título para ver el error del servicio.
          </p>
        )}

        <div className="bg-white p-6 rounded-2xl border border-[#E2E8F0] shadow-sm">
          <NewTicketForm />
        </div>
      </div>
    </div>
  );
}
