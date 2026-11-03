"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { PriorityBadge, StatusBadge } from "@/components/ui/Badge";
import { Button, buttonClassName } from "@/components/ui/Button";
import { USE_MOCKS } from "@/lib/config";
import { getFieldErrors, isApiError } from "@/lib/errors";
import { shortId } from "@/lib/format";
import { TICKET_DESCRIPTION_MAX, TICKET_TITLE_MAX, validateNewTicket } from "@/lib/ticket-rules";
import { ticketsService } from "@/services/tickets";
import { Ticket } from "@/types";

type Field = "title" | "description";
type FieldErrors = Partial<Record<Field, string>>;

const inputClass =
  "w-full rounded-lg border bg-white px-3 py-2.5 text-sm text-[#0F172A] placeholder-[#94A3B8] outline-none transition-colors focus:border-[#2563EB] focus:ring-2 focus:ring-[#2563EB]/20 disabled:bg-[#F8FAFC]";

function borderClass(hasError: boolean) {
  return hasError ? "border-[#EF4444]" : "border-[#E2E8F0]";
}

function toFieldErrors(details: { field: string; message: string }[]): FieldErrors {
  const errors: FieldErrors = {};
  for (const { field, message } of details) {
    if ((field === "title" || field === "description") && !errors[field]) errors[field] = message;
  }
  return errors;
}

// Mensaje general cuando el error no corresponde a un campo.
function generalErrorMessage(error: unknown): string {
  const code = isApiError(error) ? error.error.code : null;
  switch (code) {
    case "AUTHENTICATION_REQUIRED":
      return "Tu sesión expiró. Inicia sesión de nuevo para crear el ticket.";
    case "FORBIDDEN":
      return "No tienes permiso para crear tickets.";
    case "VALIDATION_ERROR":
      return "Revisa los datos del ticket.";
    default:
      // SERVICE_UNAVAILABLE, otros 5xx y fallos de red.
      return "No se pudo crear el ticket. Intenta nuevamente.";
  }
}

function CharacterCount({ value, max }: { value: string; max: number }) {
  const length = value.trim().length;
  return (
    <span className={`text-xs ${length > max ? "text-[#EF4444]" : "text-[#94A3B8]"}`}>
      {length}/{max}
    </span>
  );
}

export function NewTicketForm() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [generalError, setGeneralError] = useState<string | null>(null);
  const [needsLogin, setNeedsLogin] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [created, setCreated] = useState<Ticket | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;

    // Mismas reglas que el backend: se recortan los espacios antes de validar.
    const data = { title: title.trim(), description: description.trim() };
    const errors = toFieldErrors(validateNewTicket(data));
    setFieldErrors(errors);
    setGeneralError(null);
    setNeedsLogin(false);
    if (Object.keys(errors).length > 0) return;

    setSubmitting(true);
    try {
      const ticket = await ticketsService.create(data);
      if (USE_MOCKS) {
        // El listado y el detalle se generan en el servidor y no verían un ticket creado
        // en esta pestaña: con datos de ejemplo se confirma aquí mismo.
        setCreated(ticket);
        setSubmitting(false);
      } else {
        router.push(`/tickets/${ticket.id}`);
      }
    } catch (error) {
      const serverErrors = toFieldErrors(
        Object.entries(getFieldErrors(error)).map(([field, message]) => ({ field, message }))
      );
      setFieldErrors(serverErrors);
      // Si el 422 ya marca los campos, no hace falta repetirlo arriba.
      setGeneralError(Object.keys(serverErrors).length > 0 ? null : generalErrorMessage(error));
      setNeedsLogin(isApiError(error) && error.error.code === "AUTHENTICATION_REQUIRED");
      setSubmitting(false);
    }
  }

  function startOver() {
    setTitle("");
    setDescription("");
    setFieldErrors({});
    setGeneralError(null);
    setCreated(null);
  }

  if (created) {
    return (
      <div className="space-y-5" role="status">
        <div className="space-y-1">
          <h2 className="text-lg font-semibold text-[#0F172A]">Ticket creado</h2>
          <p className="text-sm text-[#64748B]">
            La solicitud quedó registrada. La clasificación se realizará por separado.
          </p>
        </div>
        <div className="rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] p-4 space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <span
              className="bg-[#2563EB] text-white font-bold text-xs px-3 py-1 rounded-md"
              title={created.id}
            >
              #{shortId(created.id)}
            </span>
            <StatusBadge status={created.status} />
            <PriorityBadge priority={created.priority} />
          </div>
          <p className="text-sm font-semibold text-[#0F172A] break-words">{created.title}</p>
          <p className="text-sm text-[#475569] whitespace-pre-line break-words">
            {created.description}
          </p>
        </div>
        <p className="text-xs text-[#92400E] bg-[#FEF3C7] border border-[#FDE68A] rounded-xl px-4 py-2.5">
          <strong>Datos de ejemplo:</strong> este ticket solo existe en esta pestaña y no aparece en
          el listado ni en el detalle. Con el backend real se abrirá el detalle del ticket creado.
        </p>
        <div className="flex flex-wrap gap-3">
          <Button type="button" variant="primary" onClick={startOver}>
            Crear otro ticket
          </Button>
          <Link href="/tickets" className={buttonClassName("secondary")}>
            Volver al listado
          </Link>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-5">
      {generalError && (
        <div
          role="alert"
          className="text-sm text-[#B91C1C] bg-[#FEF2F2] border border-[#FECACA] rounded-xl px-4 py-3"
        >
          {generalError}{" "}
          {needsLogin && (
            <Link href="/login" className="font-medium underline">
              Ir al inicio de sesión
            </Link>
          )}
        </div>
      )}

      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <label htmlFor="title" className="text-sm font-medium text-[#0F172A]">
            Título
          </label>
          <CharacterCount value={title} max={TICKET_TITLE_MAX} />
        </div>
        <input
          id="title"
          name="title"
          type="text"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Ej.: No puedo conectarme a la VPN desde casa"
          disabled={submitting}
          aria-invalid={Boolean(fieldErrors.title)}
          aria-describedby={fieldErrors.title ? "title-error" : undefined}
          className={`${inputClass} ${borderClass(Boolean(fieldErrors.title))}`}
        />
        {fieldErrors.title && (
          <p id="title-error" className="text-xs text-[#EF4444]">
            {fieldErrors.title}
          </p>
        )}
      </div>

      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <label htmlFor="description" className="text-sm font-medium text-[#0F172A]">
            Descripción
          </label>
          <CharacterCount value={description} max={TICKET_DESCRIPTION_MAX} />
        </div>
        <textarea
          id="description"
          name="description"
          rows={8}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="Describe el problema: qué ocurre, desde cuándo, a quién afecta y qué intentaste."
          disabled={submitting}
          aria-invalid={Boolean(fieldErrors.description)}
          aria-describedby={fieldErrors.description ? "description-error" : undefined}
          className={`${inputClass} ${borderClass(Boolean(fieldErrors.description))} resize-y`}
        />
        {fieldErrors.description && (
          <p id="description-error" className="text-xs text-[#EF4444]">
            {fieldErrors.description}
          </p>
        )}
      </div>

      <p className="text-xs text-[#64748B]">
        El ticket se crea como <strong>Abierto</strong> con prioridad <strong>Media</strong>. La
        clasificación se realiza por separado y la prioridad podrá ajustarse después.
      </p>

      <div className="flex flex-wrap gap-3">
        <Button type="submit" variant="primary" disabled={submitting}>
          {submitting ? "Creando ticket…" : "Crear ticket"}
        </Button>
        <Link href="/tickets" className={buttonClassName("secondary")}>
          Cancelar
        </Link>
      </div>
    </form>
  );
}
