import { methodNotAllowed, proxyToBackend } from "@/lib/backend-proxy";

// Proxy de mismo origen: el navegador pide /api/v1/* a Next.js y este reenvía a FastAPI
// (BACKEND_INTERNAL_URL). Se usa un Route Handler y no rewrites para controlar cada cabecera.

interface ProxyContext {
  params: Promise<{ path: string[] }>;
}

async function handler(request: Request, { params }: ProxyContext) {
  const { path } = await params;
  return proxyToBackend(request, path);
}

export { handler as DELETE, handler as GET, handler as PATCH, handler as POST, handler as PUT };

// Next implementaría HEAD a partir de GET y lo enviaría al backend: solo se aceptan los métodos
// anteriores. OPTIONS lo responde Next sin llamar al backend; TRACE y CONNECT no llegan aquí.
export const HEAD = methodNotAllowed;
