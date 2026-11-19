import { connection } from "next/server";
import { USE_MOCKS } from "@/lib/config";
import { readinessStatus, ServiceStatus, serviceStatusLabels } from "@/lib/service-status";
import { systemService } from "@/services/system";

// Colores sobre el fondo oscuro del menú (#0F172A); el texto conserva #94A3B8 (6,96:1). La línea
// superior lo separa de los conteos por estado, para que no se lea como un estado de tickets.
const dotColors: Record<ServiceStatus, string> = {
  available: "#10B981",
  "database-unavailable": "#F59E0B",
  unreachable: "#F87171",
  demo: "#64748B",
};

function StatusLine({
  status,
  loading = false,
}: {
  status: ServiceStatus | null;
  loading?: boolean;
}) {
  return (
    <p
      className="mt-4 flex items-center gap-3 border-t border-[#1E293B] pt-4 text-[13px] text-[#94A3B8]"
      aria-busy={loading || undefined}
    >
      <span
        className="h-2 w-2 shrink-0 rounded-full"
        style={{ backgroundColor: status ? dotColors[status] : "#334155" }}
        aria-hidden="true"
      />
      {status ? serviceStatusLabels[status] : "Comprobando el servicio…"}
    </p>
  );
}

/**
 * Estado del backend en el menú lateral, desde GET /api/v1/ready. Se consulta en el servidor en
 * cada carga de página (sin sondeo). Con datos de ejemplo no hay backend: se indica así. Se
 * renderiza dentro de un Suspense, para que una respuesta lenta no retrase el resto del menú.
 */
export async function SidebarServiceStatus() {
  if (USE_MOCKS) return <StatusLine status="demo" />;
  await connection();
  const status = await systemService.getReadiness().then(
    (value) => readinessStatus({ ok: true, value }),
    (error) => readinessStatus({ ok: false, error })
  );
  return <StatusLine status={status} />;
}

/** Marcador mientras se consulta el estado. */
export function SidebarServiceStatusFallback() {
  return <StatusLine status={null} loading />;
}
