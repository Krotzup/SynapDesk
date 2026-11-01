// Zona horaria explícita para que la hora no dependa del servidor donde se renderiza.
const dateTimeFormatter = new Intl.DateTimeFormat("es-CL", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "America/Santiago",
});

const scoreFormatter = new Intl.NumberFormat("es-CL", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** Convierte una fecha ISO 8601 (UTC) a texto legible para el usuario. */
export function formatDateTime(isoDate: string): string {
  return dateTimeFormatter.format(new Date(isoDate));
}

/**
 * Formatea la similitud de una fuente RAG. No se muestra como porcentaje:
 * el score es una similitud coseno, no una probabilidad.
 */
export function formatScore(score: number): string {
  return scoreFormatter.format(score);
}

/** Versión corta del UUID para mostrar en tablas y encabezados. */
export function shortId(id: string): string {
  return id.slice(0, 8);
}
