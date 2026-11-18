import { useSyncExternalStore } from "react";
import { USE_MOCKS } from "@/lib/config";
import { TicketStatus } from "@/types";

// Con datos de ejemplo, el cambio de estado se hace en el navegador y el detalle se arma en el
// servidor, que no lo ve. El estado nuevo se guarda aquí, por ticket, mientras dure la pestaña.
// Con el backend real no se usa: router.refresh() trae el estado guardado.
const statusByTicket = new Map<string, TicketStatus>();
const listeners = new Set<() => void>();

export function setDemoTicketStatus(ticketId: string, status: TicketStatus) {
  if (!USE_MOCKS) return;
  statusByTicket.set(ticketId, status);
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Estado vigente del ticket: el cambiado en esta pestaña (datos de ejemplo) o el del servidor. */
export function useTicketStatus(ticketId: string, serverStatus: TicketStatus): TicketStatus {
  const demo = useSyncExternalStore(
    subscribe,
    () => statusByTicket.get(ticketId),
    () => undefined
  );
  return demo ?? serverStatus;
}
