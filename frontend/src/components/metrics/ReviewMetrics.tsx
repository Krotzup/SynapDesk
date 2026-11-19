import { connection } from "next/server";
import { SectionError } from "@/components/home/SectionError";
import { api } from "@/lib/api";
import { USE_MOCKS } from "@/lib/config";

const counts = [
  ["recommendationsAccepted", "Aceptadas"],
  ["recommendationsModified", "Modificadas"],
  ["recommendationsRejected", "Rechazadas"],
] as const;
type ReviewCounts = Record<(typeof counts)[number][0], number>;

export async function ReviewMetrics() {
  if (process.env.AI_REVIEW_METRICS_ENABLED !== "true") return null;
  await connection();
  if (USE_MOCKS) {
    return <p>Las métricas de revisiones de IA requieren el backend con datos reales.</p>;
  }
  const data = await api.get<ReviewCounts>("/metrics/recommendations").catch(() => null);
  if (!data || counts.some(([key]) => !Number.isSafeInteger(data[key]) || data[key] < 0)) {
    return <SectionError message="No se pudieron cargar las revisiones de IA." />;
  }
  return (
    <section aria-labelledby="review-metrics-title" className="space-y-3">
      <h2 id="review-metrics-title" className="text-lg font-semibold">
        Revisiones de IA
      </h2>
      <p className="text-sm text-[#64748B]">
        Conteos históricos globales de revisiones registradas. No miden la exactitud del modelo ni
        indican que un ticket esté resuelto. Los borradores pendientes no se incluyen.
      </p>
      <dl className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {counts.map(([key, label]) => (
          <div key={key} className="bg-white p-5 rounded-2xl border border-[#E2E8F0]">
            <dt className="text-sm text-[#64748B]">{label}</dt>
            <dd className="text-2xl font-bold text-[#0F172A]">{data[key]}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
