import Link from "next/link";
import { connection } from "next/server";
import { metricsService } from "@/services/metrics";
import { Metrics } from "@/types";
import { SectionError } from "./SectionError";

interface SummaryCard {
  label: string;
  value: (summary: Metrics) => number;
  // Sin href: no hay un filtro que agrupe varios estados en el listado.
  href?: string;
  color: string;
  iconBg: string;
  iconPath: string;
}

// Solo campos de GET /metrics/summary, los mismos del menú lateral y del listado.
const cards: SummaryCard[] = [
  {
    label: "Tickets activos",
    value: (summary) => summary.openTickets + summary.inProgressTickets,
    color: "text-[#0F172A]",
    iconBg: "bg-[#EFF6FF] text-[#2563EB]",
    iconPath:
      "M15 5v2m0 4v2m0 4v2M5 5a2 2 0 00-2 2v3a2 2 0 110 4v3a2 2 0 002 2h14a2 2 0 002-2v-3a2 2 0 110-4V7a2 2 0 00-2-2H5z",
  },
  {
    label: "Abiertos",
    value: (summary) => summary.openTickets,
    href: "/tickets?status=open",
    color: "text-[#1D4ED8]",
    iconBg: "bg-[#DBEAFE] text-[#1D4ED8]",
    iconPath:
      "M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4",
  },
  {
    label: "En proceso",
    value: (summary) => summary.inProgressTickets,
    href: "/tickets?status=in_progress",
    color: "text-[#D97706]",
    iconBg: "bg-[#FEF3C7] text-[#D97706]",
    iconPath: "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z",
  },
  {
    label: "Resueltos",
    value: (summary) => summary.resolvedTickets,
    href: "/tickets?status=resolved",
    color: "text-[#10B981]",
    iconBg: "bg-[#D1FAE5] text-[#10B981]",
    iconPath: "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z",
  },
];

const cardClassName =
  "bg-white p-5 rounded-2xl border border-[#E2E8F0] shadow-sm flex items-center justify-between";

function SummaryCards({
  summary,
  loading = false,
}: {
  summary: Metrics | null;
  loading?: boolean;
}) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4" aria-busy={loading}>
      {cards.map((card) => {
        const content = (
          <>
            <div>
              <p className="text-xs font-semibold text-[#64748B] uppercase tracking-wider">
                {card.label}
              </p>
              <p className={`text-2xl font-bold mt-1 ${card.color}`}>
                {summary ? card.value(summary) : "–"}
              </p>
            </div>
            <div className={`h-10 w-10 ${card.iconBg} rounded-xl flex items-center justify-center`}>
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
                  d={card.iconPath}
                />
              </svg>
            </div>
          </>
        );
        return card.href ? (
          <Link
            key={card.label}
            href={card.href}
            className={`${cardClassName} hover:border-[#2563EB]/40 transition-colors`}
          >
            {content}
          </Link>
        ) : (
          <div key={card.label} className={cardClassName}>
            {content}
          </div>
        );
      })}
    </div>
  );
}

/** Conteos de Inicio desde GET /metrics/summary. Se renderiza dentro de un Suspense. */
export async function HomeSummary() {
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
export function HomeSummaryFallback() {
  return <SummaryCards summary={null} loading />;
}
