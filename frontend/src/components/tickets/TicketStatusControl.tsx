"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { statusLabels } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ErrorReference } from "@/components/ui/ErrorReference";
import { describeError, ErrorDescription } from "@/lib/errors";
import { TICKET_STATUSES } from "@/lib/ticket-filters";
import { ticketsService } from "@/services/tickets";
import { TicketStatus } from "@/types";
import { setDemoTicketStatus, useTicketStatus } from "./demo-ticket-status";

interface TicketStatusControlProps {
  ticketId: string;
  status: TicketStatus;
}

/**
 * Cambio de estado con precondición del estado observado. El backend valida
 * transiciones y fechas; los rechazos se muestran sin reintento automático.
 */
export function TicketStatusControl({ ticketId, status: serverStatus }: TicketStatusControlProps) {
  const router = useRouter();
  const current = useTicketStatus(ticketId, serverStatus);
  const [selected, setSelected] = useState<TicketStatus>(current);
  const [saving, setSaving] = useState(false);
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState<ErrorDescription | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving || selected === current) return;
    setSaving(true);
    setError(null);
    setConfirmation("");
    try {
      const updated = await ticketsService.updateStatus(ticketId, {
        status: selected,
        expectedStatus: current,
      });
      setDemoTicketStatus(ticketId, updated.status);
      setSelected(updated.status);
      setConfirmation(`Estado actualizado a «${statusLabels[updated.status]}».`);
      router.refresh();
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
        <div className="flex-1 sm:max-w-xs">
          <label htmlFor="ticket-new-status" className="block text-xs font-medium text-[#475569]">
            Cambiar estado
          </label>
          <select
            id="ticket-new-status"
            value={selected}
            disabled={saving}
            onChange={(event) => {
              setSelected(event.target.value as TicketStatus);
              setConfirmation("");
            }}
            className="mt-1 w-full min-h-11 sm:min-h-0 rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] px-3 py-2.5 text-sm text-[#0F172A] outline-none focus:border-[#2563EB] disabled:opacity-60"
          >
            {TICKET_STATUSES.map((option) => (
              <option key={option} value={option}>
                {statusLabels[option]}
                {option === current ? " (actual)" : ""}
              </option>
            ))}
          </select>
        </div>
        <Button
          type="submit"
          variant="primary"
          className="w-full sm:w-auto"
          disabled={saving || selected === current}
        >
          {saving ? "Guardando…" : "Guardar estado"}
        </Button>
      </div>

      {/* Confirmación breve para lectores de pantalla y a la vista. */}
      <p aria-live="polite" className="text-xs font-medium text-[#047857] min-h-4">
        {confirmation}
      </p>

      {error && (
        <div
          role="alert"
          className="rounded-xl border border-[#FECACA] bg-[#FEF2F2] px-3 py-2.5 text-sm text-[#B91C1C]"
        >
          <p>
            {error.message}{" "}
            {error.kind === "authentication" && (
              <Link href="/login" className="font-medium underline">
                Ir al inicio de sesión
              </Link>
            )}
          </p>
          {error.kind === "conflict" && (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="mt-2 w-full sm:w-auto"
              onClick={() => window.location.reload()}
            >
              Recargar
            </Button>
          )}
          <ErrorReference requestId={error.requestId} />
        </div>
      )}
    </form>
  );
}
