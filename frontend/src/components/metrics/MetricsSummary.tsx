import Link from "next/link";
import { connection } from "next/server";
import { SectionError } from "@/components/home/SectionError";
import { buttonClassName } from "@/components/ui/Button";
import { metricsService } from "@/services/metrics";
import { ticketListHrefForStatus } from "@/lib/ticket-filters";
import { Metrics, TicketStatus } from "@/types";

type CountKey = "openTickets" | "inProgressTickets" | "resolvedTickets" | "closedTickets";

// Un conteo por estado; enlaza al listado filtrado solo si los filtros están habilitados.
const statusCounts: { key: CountKey; label: string; status: TicketStatus; dot: string }[] = [
  { key: "openTickets", label: "Abiertos", status: "open", dot: "bg-[#2563EB]" },
  { key: "inProgressTickets", label: "En proceso", status: "in_progress", dot: "bg-[#D97706]" },
  { key: "resolvedTickets", label: "Resueltos", status: "resolved", dot: "bg-[#10B981]" },
  { key: "closedTickets", label: "Cerrados", status: "closed", dot: "bg-[#64748B]" },
];

const cardClassName = "bg-white p-5 rounded-2xl border border-[#E2E8F0] shadow-sm";

function StatusCard({
  href,
  label,
  dot,
  value,
}: {
  href: string | undefined;
  label: string;
  dot: string;
  value: number | string | undefined;
}) {
  const content = (
    <>
      <span className="flex items-center gap-2 text-xs font-semibold text-[#64748B] uppercase tracking-wider">
        <span className={`h-2 w-2 rounded-full ${dot}`} aria-hidden="true" />
        {label}
      </span>
      <span className="block text-2xl font-bold text-[#0F172A] mt-1">{value}</span>
    </>
  );
  return href ? (
    <Link
      href={href}
      className={`${cardClassName} block hover:border-[#2563EB]/40 transition-colors`}
    >
      {content}
    </Link>
  ) : (
    <div className={`${cardClassName} block`}>{content}</div>
  );
}

function Counts({ summary, loading = false }: { summary: Metrics | null; loading?: boolean }) {
  const value = (count: number | undefined) => (summary ? count : "–");
  return (
    <div className="space-y-4" aria-busy={loading}>
      <Link
        href="/tickets"
        className={`${cardClassName} flex items-center justify-between hover:border-[#2563EB]/40 transition-colors`}
      >
        <span>
          <span className="block text-xs font-semibold text-[#64748B] uppercase tracking-wider">
            Total de tickets
          </span>
          <span className="block text-3xl font-bold text-[#0F172A] mt-1">
            {value(summary?.totalTickets)}
          </span>
        </span>
        <span className="text-xs font-semibold text-[#2563EB]">Ver listado →</span>
      </Link>

      <ul className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        {statusCounts.map((item) => (
          <li key={item.key}>
            <StatusCard
              href={ticketListHrefForStatus(item.status)}
              label={item.label}
              dot={item.dot}
              value={value(summary?.[item.key])}
            />
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Conteos de tickets por estado desde GET /metrics/summary. Se renderiza dentro de un Suspense. */
export async function MetricsSummary() {
  await connection();

  const summary = await metricsService.getSummary().catch(() => null);
  if (!summary) {
    return (
      <div className="space-y-3">
        <Counts summary={null} />
        <SectionError message="No se pudieron cargar las métricas." />
      </div>
    );
  }
  if (summary.totalTickets === 0) {
    return (
      <div className={`${cardClassName} space-y-3 text-center py-10`}>
        <p className="text-sm font-semibold text-[#0F172A]">Todavía no hay tickets registrados</p>
        <p className="text-xs text-[#64748B]">
          Los conteos por estado aparecerán cuando se cree el primer ticket.
        </p>
        <Link href="/tickets/nuevo" className={buttonClassName("primary", false, "inline-flex")}>
          Crear ticket
        </Link>
      </div>
    );
  }
  return <Counts summary={summary} />;
}

/** Marcador mientras llegan los conteos. */
export function MetricsSummaryFallback() {
  return <Counts summary={null} loading />;
}
