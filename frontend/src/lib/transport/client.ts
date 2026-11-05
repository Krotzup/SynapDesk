// Transporte de los componentes cliente: rutas relativas /api/v1/* hacia el proxy de mismo
// origen (app/api/v1/[...path]), que reenvía a FastAPI. El navegador nunca conoce el destino.
// package.json ("imports" → "#transport") elige este archivo fuera de los componentes de servidor.

export interface Transport {
  baseUrl: string;
  headers: Record<string, string>;
}

export async function getTransport(): Promise<Transport> {
  return { baseUrl: "", headers: {} };
}
