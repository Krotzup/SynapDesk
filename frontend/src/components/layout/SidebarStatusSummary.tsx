import { connection } from "next/server";
import { getTicketStatusSummary, TicketStatusSummary } from "@/lib/ticket-summary";

type SummaryKey = keyof TicketStatusSummary;

const statusItems: { key: SummaryKey; label: string; color: string }[] = [
  { key: "total", label: "Todos", color: "#38BDF8" },
  { key: "open", label: "Abiertos", color: "#38BDF8" },
  { key: "inProgress", label: "En Proceso", color: "#F59E0B" },
  { key: "resolved", label: "Resueltos", color: "#10B981" },
];

function StatusList({ summary }: { summary: TicketStatusSummary | null }) {
  return (
    <div className="flex flex-col gap-3">
      {statusItems.map((item) => (
        <div key={item.key} className="flex items-center justify-between text-[13px]">
          <div className="flex items-center gap-3">
            <span
              className="h-2 w-2 rounded-full shrink-0"
              style={{ backgroundColor: item.color }}
              aria-hidden="true"
            />
            <span className="text-[#94A3B8]">{item.label}</span>
          </div>
          <span className="min-w-[24px] text-center text-[11px] font-bold text-[#94A3B8] bg-[#1E293B] rounded-full px-2 py-0.5">
            {summary ? summary[item.key] : "–"}
          </span>
        </div>
      ))}
    </div>
  );
}

/** Conteos del menú lateral. Se renderiza en el servidor dentro de un Suspense. */
export async function SidebarStatusSummary() {
  // Los conteos se obtienen en cada solicitud, no durante el build.
  await connection();

  // Un fallo del backend no debe impedir mostrar el resto del panel.
  const summary = await getTicketStatusSummary().catch(() => null);
  return <StatusList summary={summary} />;
}

/** Marcador mientras llegan los conteos. */
export function SidebarStatusSummaryFallback() {
  return <StatusList summary={null} />;
}
