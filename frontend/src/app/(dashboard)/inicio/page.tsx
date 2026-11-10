import Link from "next/link";
import { Suspense } from "react";
import { HomeSummary, HomeSummaryFallback } from "@/components/home/HomeSummary";
import { RecentDocuments, RecentDocumentsFallback } from "@/components/home/RecentDocuments";
import { RecentTickets, RecentTicketsFallback } from "@/components/home/RecentTickets";
import { WelcomeGreeting } from "@/components/home/WelcomeGreeting";
import { USE_MOCKS } from "@/lib/config";

// Cada bloque pide sus datos por separado: si uno falla, los demás se siguen mostrando.
export default function InicioPage() {
  return (
    <div className="p-8 bg-[#F8FAFC] min-h-screen">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Banner de bienvenida */}
        <div className="bg-gradient-to-r from-[#0B132B] to-[#1E3A8A] rounded-2xl p-6 sm:p-8 text-white shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
          <WelcomeGreeting />
          <Link
            href="/tickets"
            className="px-5 py-2.5 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-sm font-semibold rounded-xl transition-colors shadow-md whitespace-nowrap"
          >
            Ver todos los tickets →
          </Link>
        </div>

        {USE_MOCKS && (
          <p className="text-xs text-[#92400E] bg-[#FEF3C7] border border-[#FDE68A] rounded-xl px-4 py-2.5">
            <strong>Datos de ejemplo:</strong> los tickets, conteos y documentos son ficticios y no
            provienen del backend.
          </p>
        )}

        {/* Métricas rápidas */}
        <Suspense fallback={<HomeSummaryFallback />}>
          <HomeSummary />
        </Suspense>

        {/* Dos columnas */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
          {/* Tickets recientes */}
          <section className="lg:col-span-2 bg-white rounded-2xl border border-[#E2E8F0] shadow-sm p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-[#F1F5F9] pb-4">
              <div>
                <h2 className="text-base font-bold text-[#0F172A]">Tickets recientes</h2>
                <p className="text-xs text-[#64748B]">
                  Últimas solicitudes registradas en el sistema
                </p>
              </div>
              <Link
                href="/tickets"
                className="text-xs font-semibold text-[#2563EB] hover:underline"
              >
                Ver todo
              </Link>
            </div>
            <Suspense fallback={<RecentTicketsFallback />}>
              <RecentTickets />
            </Suspense>
          </section>

          <div className="space-y-6">
            {/* Base de conocimientos */}
            <section className="bg-white rounded-2xl border border-[#E2E8F0] shadow-sm p-6 space-y-4">
              <div className="border-b border-[#F1F5F9] pb-3 flex items-center justify-between">
                <h2 className="text-base font-bold text-[#0F172A]">Base de conocimientos</h2>
                <Link
                  href="/documentos"
                  className="text-xs font-semibold text-[#2563EB] hover:underline"
                >
                  Ver todo
                </Link>
              </div>
              <p className="text-xs text-[#64748B]">
                Documentos incorporados recientemente. El Asistente IA usa los procesados como
                fuentes.
              </p>
              <Suspense fallback={<RecentDocumentsFallback />}>
                <RecentDocuments />
              </Suspense>
            </section>

            <div className="bg-[#EEF2FF] rounded-2xl border border-[#C7D2FE] p-5 space-y-3">
              <div className="flex items-center gap-2 font-bold text-sm text-[#4338CA]">
                <svg
                  className="h-5 w-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                  />
                </svg>
                Asistente SynapDesk
              </div>
              <p className="text-xs leading-relaxed text-[#3730A3]">
                En el detalle de cada ticket, el Asistente IA propone una solución con las fuentes
                que usó. Tú decides si aceptarla, editarla o descartarla.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
