import type { CreateTicketRequest } from "@/services/tickets";
import { ValidationErrorDetail } from "@/types";

// Reglas para crear tickets propuestas por Felipe el 03-11-2026 (aún no escritas en el
// contrato). Se cuentan los caracteres después de quitar los espacios del inicio y del final.
export const TICKET_TITLE_MIN = 5;
export const TICKET_TITLE_MAX = 150;
export const TICKET_DESCRIPTION_MIN = 10;
export const TICKET_DESCRIPTION_MAX = 5000;

function lengthError(
  field: string,
  label: string,
  value: string,
  min: number,
  max: number
): ValidationErrorDetail | null {
  if (value.length === 0) return { field, message: `Ingresa ${label}.` };
  if (value.length < min) return { field, message: `Debe tener al menos ${min} caracteres.` };
  if (value.length > max) return { field, message: `Debe tener como máximo ${max} caracteres.` };
  return null;
}

/** Valida un ticket nuevo ya recortado. Devuelve los errores con la forma de details del 422. */
export function validateNewTicket({
  title,
  description,
}: CreateTicketRequest): ValidationErrorDetail[] {
  return [
    lengthError("title", "un título", title, TICKET_TITLE_MIN, TICKET_TITLE_MAX),
    lengthError(
      "description",
      "una descripción",
      description,
      TICKET_DESCRIPTION_MIN,
      TICKET_DESCRIPTION_MAX
    ),
  ].filter((error): error is ValidationErrorDetail => error !== null);
}
