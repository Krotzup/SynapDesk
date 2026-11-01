import { ApiError } from "@/types";

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
