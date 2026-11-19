// Servidor Next de ensayo: capacidad privada y contexto por petición, nunca confianza desde HTTP.
import fs from 'node:fs';
import http from 'node:http';
import {AsyncLocalStorage} from 'node:async_hooks';
import {createRequire} from 'node:module';
import {randomUUID} from 'node:crypto';
import {capture, seal} from './protocolo.mjs';

const config = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
if (config.appEnv !== 'testing' || !/^synapdesk_auth07_sec01a_[a-f0-9]{32}$/.test(config.database) ||
    !/^https:\/\/localhost:\d+$/.test(config.backend) || !/^[a-f0-9]{32}$/.test(config.audience)) {
  throw new Error('Local ingress configuration rejected.');
}
const key = Buffer.from(config.ingressKey, 'base64url');
if (key.length !== 32) throw new Error('Invalid ingress key.');
const require = createRequire(config.repo + '/frontend/package.json');
const storage = new AsyncLocalStorage();
const attest = (method, path, headers, filterCookies, ssr = false) =>
  seal(storage.getStore(), method, path, headers, key, config.audience, filterCookies,
    {ssr, publicOrigin: `http://127.0.0.1:${config.port}`});
process[Symbol.for('synapdesk.mvp04.ingress')] = Object.freeze({attest,
  localTesting: true, publicOrigin: `http://127.0.0.1:${config.port}`});
const next = require('next');
const application = next({dev: true, dir: config.project, hostname: '127.0.0.1', port: config.port, webpack: true});
await application.prepare();
const handle = application.getRequestHandler();
const allowed = new Map([['/api/v1/auth/csrf', 'GET'], ['/api/v1/auth/login', 'POST'], ['/api/v1/auth/me', 'GET']]);
allowed.set('/api/v1/auth/logout', 'POST');
allowed.set('/api/local/csrf', 'POST');
const failure = response => {
  response.writeHead(503, {'Content-Type': 'application/json', 'Cache-Control': 'no-store'});
  response.end(JSON.stringify({error: {code: 'SERVICE_UNAVAILABLE',
    message: 'El servicio no está disponible temporalmente.', details: null, requestId: randomUUID()}}));
};
const server = http.createServer((request, response) => {
  if (request.method === 'GET' && request.url === '/_mvp04/ready') {
    response.writeHead(200, {'Content-Type': 'application/json', 'Cache-Control': 'no-store'});
    response.end(JSON.stringify({harness: config.identity}));
    return;
  }
  const parsed = new URL(request.url, 'http://ingreso.invalid');
  const hosts = request.rawHeaders.filter((_, i) => i % 2 === 1 && request.rawHeaders[i-1].toLowerCase() === 'host');
  if (hosts.length !== 1 || hosts[0] !== `127.0.0.1:${config.port}`) { failure(response); return; }
  if (parsed.searchParams.has('password')) { failure(response); return; }
  const pathname = parsed.pathname;
  const lecturaTickets = request.method === 'GET' &&
    (pathname === '/api/v1/tickets' || pathname === '/api/v1/metrics/summary' ||
      /^\/api\/v1\/tickets\/[0-9a-f-]{36}$/i.test(pathname));
  const escrituraTickets = (request.method === 'POST' && pathname === '/api/v1/tickets') ||
    (request.method === 'PATCH' && /^\/api\/v1\/tickets\/[0-9a-f-]{36}$/i.test(pathname));
  const interfaz = request.method === 'GET' && (!pathname.startsWith('/api/') &&
    (pathname === '/' || pathname === '/login' || pathname === '/inicio' ||
      pathname === '/tickets' || pathname === '/tickets/nuevo' || /^\/tickets\/[0-9a-f-]{36}$/i.test(pathname) ||
      pathname.startsWith('/_next/') || pathname === '/favicon.ico'));
  if (allowed.get(request.url) !== request.method && !lecturaTickets && !escrituraTickets && !interfaz) {
    response.writeHead(404, {'Cache-Control': 'no-store'}).end();
    return;
  }
  try {
    const context = capture(request);
    storage.run(context, () => Promise.resolve(handle(request, response)).catch(() => {
      if (!response.headersSent) failure(response); else response.destroy();
    }));
  } catch { failure(response); }
});
server.listen(config.port, '127.0.0.1');
