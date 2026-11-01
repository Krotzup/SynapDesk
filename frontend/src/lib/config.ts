// Activa los datos de ejemplo de src/mocks mientras el backend no expone las rutas.
// Se controla con NEXT_PUBLIC_USE_MOCKS en .env.local; cualquier valor distinto de "true"
// hace que los services llamen al backend real.
export const USE_MOCKS = process.env.NEXT_PUBLIC_USE_MOCKS === "true";
