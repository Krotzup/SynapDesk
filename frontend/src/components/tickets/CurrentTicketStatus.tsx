"use client";

import { StatusBadge } from "@/components/ui/Badge";
import { TicketStatus } from "@/types";
import { useTicketStatus } from "./demo-ticket-status";

/** Estado del ticket en el encabezado del detalle; refleja un cambio hecho en esta pestaña. */
export function CurrentTicketStatus({
  ticketId,
  status,
}: {
  ticketId: string;
  status: TicketStatus;
}) {
  return <StatusBadge status={useTicketStatus(ticketId, status)} />;
}
