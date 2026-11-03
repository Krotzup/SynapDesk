import { ApiError, ValidationErrorDetail } from "@/types";

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
