const allowed = new Map([['/api/v1/auth/csrf', 'GET'], ['/api/v1/auth/login', 'POST'], ['/api/v1/auth/me', 'GET']]);
allowed.set('/api/v1/auth/logout', 'POST');
allowed.set('/api/local/csrf', 'POST');
allowed.set('/api/v1/search', 'POST');
allowed.set('/api/v1/metrics/recommendations', 'GET');

export function rutaPermitida(method, url) {
  const parsed = new URL(url, "http://ingreso.invalid");
  const pathname = parsed.pathname;
  const lecturaTickets = method === 'GET' &&
    (pathname === '/api/v1/tickets' || pathname === '/api/v1/metrics/summary' ||
      /^\/api\/v1\/tickets\/[0-9a-f-]{36}$/i.test(pathname));
  const escrituraTickets = (method === 'POST' && pathname === '/api/v1/tickets') ||
    (method === 'PATCH' && /^\/api\/v1\/tickets\/[0-9a-f-]{36}$/i.test(pathname));
  const recomendaciones = !parsed.search && (
    (method === 'GET' && (
      /^\/api\/v1\/tickets\/[0-9a-f-]{36}\/recommendations$/i.test(pathname) ||
      /^\/api\/v1\/recommendations\/[0-9a-f-]{36}$/i.test(pathname))) ||
    (method === 'POST' && (
      /^\/api\/v1\/tickets\/[0-9a-f-]{36}\/recommendations$/i.test(pathname) ||
      /^\/api\/v1\/recommendations\/[0-9a-f-]{36}\/reviews$/i.test(pathname))));
  const documentos = (method === 'GET' && (pathname === '/api/v1/documents' ||
      /^\/api\/v1\/documents\/[0-9a-f-]{36}$/i.test(pathname))) || (!parsed.search && (
      (method === 'POST' && pathname === '/api/v1/documents') ||
      (method === 'DELETE' && /^\/api\/v1\/documents\/[0-9a-f-]{36}$/i.test(pathname))));
  const predicciones = !parsed.search && ['GET', 'POST'].includes(method) &&
    /^\/api\/v1\/tickets\/[0-9a-f-]{36}\/prediction$/i.test(pathname);
  const interfaz = method === 'GET' && (!pathname.startsWith('/api/') &&
    (pathname === '/' || pathname === '/login' || pathname === '/inicio' ||
      pathname === '/metricas' || pathname === '/busqueda' || pathname === '/documentos' || /^\/documentos\/[0-9a-f-]{36}$/i.test(pathname) ||
      pathname === '/tickets' || pathname === '/tickets/nuevo' || /^\/tickets\/[0-9a-f-]{36}$/i.test(pathname) ||
      pathname.startsWith('/_next/') || pathname === '/favicon.ico'));
  return allowed.get(url) === method || lecturaTickets || escrituraTickets || recomendaciones || documentos || predicciones || interfaz;
}
