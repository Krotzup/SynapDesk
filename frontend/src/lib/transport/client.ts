// Transporte de los componentes cliente: rutas relativas /api/v1/* hacia el proxy de mismo
// origen (app/api/v1/[...path]), que reenvía a FastAPI. El navegador nunca conoce el destino.
// package.json ("imports" → "#transport") elige este archivo fuera de los componentes de servidor.

export interface Transport {
  baseUrl: string;
  headers: Record<string, string>;
  /** Hace la petición. En el servidor agrega tiempo de espera y rechaza redirecciones. */
  fetch: (url: string, init: RequestInit) => Promise<Response>;
}

export async function getTransport(): Promise<Transport> {
  return { baseUrl: "", headers: {}, fetch: (url, init) => fetch(url, init) };
}
