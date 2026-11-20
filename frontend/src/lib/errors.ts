import { ApiError, ValidationErrorDetail } from "@/types";

// Código solo del frontend (no viene del backend): la sesión cambió (login o logout, también en
// otra pestaña) mientras se preparaba la mutación, así que no se envía con un contexto distinto.
export const SESSION_CHANGED = "SESSION_CHANGED";

/**
 * Indica si un valor lanzado por el cliente HTTP tiene el formato de error
 * definido en el contrato frontend-backend.
 */
export function isApiError(value: unknown): value is ApiError {
  if (typeof value !== "object" || value === null || !("error" in value)) return false;
  const { error } = value as { error: unknown };
  return (
    typeof error === "object" &&
    error !== null &&
    typeof (error as { code?: unknown }).code === "string"
  );
}

/** 401 de /me u otra ruta protegida: no hay sesión válida (no confundir con un fallo temporal). */
export function isAuthenticationRequired(value: unknown): boolean {
  return isApiError(value) && value.error.code === "AUTHENTICATION_REQUIRED";
}

function isValidationDetail(value: unknown): value is ValidationErrorDetail {
  if (typeof value !== "object" || value === null) return false;
  const { field, message } = value as Record<string, unknown>;
  return typeof field === "string" && typeof message === "string";
}

/**
 * Mensajes por campo de un 422 VALIDATION_ERROR (details: [{ field, message }]).
 * Devuelve un objeto vacío para cualquier otro error o un details con otra forma.
 */
export function getFieldErrors(value: unknown): Record<string, string> {
  if (!isApiError(value) || value.error.code !== "VALIDATION_ERROR") return {};
  const { details } = value.error;
  if (!Array.isArray(details)) return {};
  const errors: Record<string, string> = {};
  for (const detail of details) {
    // Se conserva el primer mensaje de cada campo.
    if (isValidationDetail(detail) && !(detail.field in errors)) {
      errors[detail.field] = detail.message;
    }
  }
  return errors;
}

/** Código de referencia del error (requestId del contrato), para informarlo a soporte. */
export function errorRequestId(value: unknown): string | null {
  return isApiError(value) && value.error.requestId ? value.error.requestId : null;
}

export type ErrorKind =
  "conflict" | "forbidden" | "notFound" | "validation" | "unavailable" | "authentication" | "other";

export interface ErrorDescription {
  kind: ErrorKind;
  message: string;
  requestId: string | null;
}

const GENERIC_MESSAGE = "No se pudo completar la acción. Intenta de nuevo.";

/**
 * Traduce un error del cliente HTTP a un mensaje para la persona, según el contrato
 * (docs/contratos/frontend-backend.md). 409 y 503 se reconocen por estado HTTP, porque el
 * contrato no fija su error.code. No reintenta nada: solo describe el error.
 */
export function describeError(value: unknown): ErrorDescription {
  const requestId = errorRequestId(value);
  if (!isApiError(value)) return { kind: "other", message: GENERIC_MESSAGE, requestId };
  const { status } = value;
  const { code } = value.error;

  if (status === 409) {
    return {
      kind: "conflict",
      message:
        code === "TICKET_TRANSITION_INVALID"
          ? "Ese cambio de estado no está permitido. Recarga el ticket y revisa las transiciones disponibles."
          : "El ticket cambió mientras lo editabas. Recarga para ver la versión actual.",
      requestId,
    };
  }
  if (status === 401 || code === "AUTHENTICATION_REQUIRED") {
    return {
      kind: "authentication",
      message: "Tu sesión expiró. Inicia sesión de nuevo para continuar.",
      requestId,
    };
  }
  if (code === SESSION_CHANGED) {
    return {
      kind: "other",
      message: "La sesión cambió en otra pestaña. Revisa tu sesión e intenta de nuevo.",
      requestId,
    };
  }
  if (status === 403 || code === "FORBIDDEN") {
    return { kind: "forbidden", message: "No tienes permiso para esta acción.", requestId };
  }
  if (code === "TICKET_NOT_FOUND") {
    return {
      kind: "notFound",
      message: "El ticket que buscas no existe o ya no está disponible.",
      requestId,
    };
  }
  if (status === 422 || code === "VALIDATION_ERROR") {
    const details = value.error.details;
    const first = Array.isArray(details) ? details.find(isValidationDetail) : undefined;
    return {
      kind: "validation",
      message: first?.message ?? "Los datos enviados no son válidos.",
      requestId,
    };
  }
  if (status === 503) {
    return {
      kind: "unavailable",
      message: "El servicio no está disponible en este momento. Intenta de nuevo más tarde.",
      requestId,
    };
  }
  return { kind: "other", message: GENERIC_MESSAGE, requestId };
}
