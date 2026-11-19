import { Suspense } from "react";
import { MetricsSummary, MetricsSummaryFallback } from "@/components/metrics/MetricsSummary";
import { USE_MOCKS } from "@/lib/config";
import { ReviewMetrics } from "@/components/metrics/ReviewMetrics";

export default function MetricasPage() {
  return (
    <div className="px-4 py-6 sm:p-6 lg:p-8 bg-[#F8FAFC] min-h-screen">
      <div className="max-w-7xl mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-[#0F172A]">Reportes y Métricas</h1>
          <p className="text-sm text-[#64748B] mt-1">
            Consulta los conteos de tickets por estado y las métricas habilitadas.
          </p>
        </div>

        {USE_MOCKS && (
          <p className="text-xs text-[#92400E] bg-[#FEF3C7] border border-[#FDE68A] rounded-xl px-4 py-2.5">
            <strong>Datos de ejemplo:</strong> los conteos se calculan con los tickets ficticios del
            listado y no provienen del backend.
          </p>
        )}

        <Suspense fallback={<MetricsSummaryFallback />}>
          <MetricsSummary />
        </Suspense>
        <Suspense fallback={<p>Cargando revisiones de IA…</p>}>
          <ReviewMetrics />
        </Suspense>
      </div>
    </div>
  );
}
