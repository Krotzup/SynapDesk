import { connection } from "next/server";
import { SectionError } from "@/components/home/SectionError";
import { metricsService } from "@/services/metrics";
import { Metrics } from "@/types";

// Conteos globales desde GET /metrics/summary, los mismos del menú lateral.
const cards: {
  label: string;
  value: (summary: Metrics) => number;
  icon: string;
  bg: string;
  text: string;
}[] = [
  {
    label: "Total tickets",
    value: (summary) => summary.totalTickets,
    icon: "📋",
    bg: "bg-[#EFF6FF]",
    text: "text-[#2563EB]",
  },
  {
    label: "Abiertos",
    value: (summary) => summary.openTickets,
    icon: "🔓",
    bg: "bg-[#DBEAFE]",
    text: "text-[#1E40AF]",
  },
  {
    label: "En proceso",
    value: (summary) => summary.inProgressTickets,
    icon: "⏳",
    bg: "bg-[#FEF3C7]",
    text: "text-[#D97706]",
  },
  {
    label: "Resueltos",
    value: (summary) => summary.resolvedTickets,
    icon: "✅",
    bg: "bg-[#D1FAE5]",
    text: "text-[#10B981]",
  },
];

function SummaryCards({
  summary,
  loading = false,
}: {
  summary: Metrics | null;
  loading?: boolean;
}) {
  return (
    // 2 × 2 hasta 1024 px, en una fila desde ahí.
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4" aria-busy={loading}>
      {cards.map((card) => (
        <div
          key={card.label}
          className="bg-white p-4 sm:p-5 rounded-2xl border border-[#E2E8F0] shadow-sm flex items-center justify-between gap-2"
        >
          <div>
            <p className="text-xs font-semibold text-[#64748B] uppercase tracking-wider">
              {card.label}
            </p>
            <p className={`text-2xl font-bold mt-1 ${card.text}`}>
              {summary ? card.value(summary) : "–"}
            </p>
          </div>
          <div
            className={`hidden sm:flex h-10 w-10 shrink-0 ${card.bg} ${card.text} rounded-xl items-center justify-center text-lg`}
            aria-hidden="true"
          >
            {card.icon}
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * Conteos del listado. Son opcionales: si fallan, la tabla de tickets se sigue mostrando.
 * Se renderiza dentro de un Suspense.
 */
export async function TicketListSummary() {
  await connection();

  const summary = await metricsService.getSummary().catch(() => null);
  if (!summary) {
    return (
      <div className="space-y-3">
        <SummaryCards summary={null} />
        <SectionError message="No se pudieron cargar los conteos de tickets." />
      </div>
    );
  }
  return <SummaryCards summary={summary} />;
}

/** Marcador mientras llegan los conteos. */
export function TicketListSummaryFallback() {
  return <SummaryCards summary={null} loading />;
}
