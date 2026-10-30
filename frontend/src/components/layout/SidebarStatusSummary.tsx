import Link from "next/link";
import { connection } from "next/server";
import { metricsService } from "@/services/metrics";
import { Metrics } from "@/types";

type CountKey = "totalTickets" | "openTickets" | "inProgressTickets" | "resolvedTickets";

// Cada estado enlaza al listado de tickets con el filtro correspondiente.
const statusItems: { key: CountKey; label: string; color: string; href: string }[] = [
  { key: "totalTickets", label: "Todos", color: "#38BDF8", href: "/tickets" },
  { key: "openTickets", label: "Abiertos", color: "#38BDF8", href: "/tickets?status=open" },
  {
    key: "inProgressTickets",
    label: "En Proceso",
    color: "#F59E0B",
    href: "/tickets?status=in_progress",
  },
  {
    key: "resolvedTickets",
    label: "Resueltos",
    color: "#10B981",
    href: "/tickets?status=resolved",
  },
];

function StatusList({ summary }: { summary: Metrics | null }) {
  return (
    <div className="flex flex-col gap-1">
      {statusItems.map((item) => (
        <Link
          key={item.key}
          href={item.href}
          className="flex items-center justify-between text-[13px] rounded-lg px-2 py-1.5 -mx-2 hover:bg-[#1E293B]/50 transition-colors"
        >
          <span className="flex items-center gap-3">
            <span
              className="h-2 w-2 rounded-full shrink-0"
              style={{ backgroundColor: item.color }}
              aria-hidden="true"
            />
            <span className="text-[#94A3B8]">{item.label}</span>
          </span>
          <span className="min-w-[24px] text-center text-[11px] font-bold text-[#94A3B8] bg-[#1E293B] rounded-full px-2 py-0.5">
            {summary ? summary[item.key] : "–"}
          </span>
        </Link>
      ))}
    </div>
  );
}

/** Conteos del menú lateral desde GET /metrics/summary. Se renderiza dentro de un Suspense. */
export async function SidebarStatusSummary() {
  // Los conteos se obtienen en cada solicitud, no durante el build.
  await connection();

  // Un fallo del backend no debe impedir mostrar el resto del panel.
  const summary = await metricsService.getSummary().catch(() => null);
  return <StatusList summary={summary} />;
}

/** Marcador mientras llegan los conteos. */
export function SidebarStatusSummaryFallback() {
  return <StatusList summary={null} />;
}
