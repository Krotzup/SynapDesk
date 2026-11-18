// Productor de evidencia: el servidor Node observa el socket antes de Next.
// El consumidor nunca utiliza X-Forwarded-* ni una IP declarada por el navegador.
import {createHash, createHmac, randomBytes} from 'node:crypto';
import {isIP} from 'node:net';

export const HEADER = 'x-synapdesk-ingress-evidence';
const NAMES = ['cookie', 'origin', 'sec-fetch-site', 'x-csrf-token'];
const sha = value => createHash('sha256').update(value).digest('hex');
const RESERVED = new Set(['synapdesk_session_dev', 'synapdesk_csrf_context_dev',
  '__Host-synapdesk_session', '__Host-synapdesk_csrf_context']);
function credentialPairs(values) {
  return values.flatMap(value => {
    if (/[^\x20-\x7e\t]/.test(value)) throw new Error('Invalid original Cookie representation.');
    return value.split(';').map(part => part.replace(/^[ \t]+/, '')).filter(part => {
      const separator = part.indexOf('=');
      const name = separator < 0 ? part : part.slice(0, separator);
      if (!/^[!#$%&'*+.^_`|~0-9A-Za-z-]+$/.test(name)) throw new Error('Invalid original Cookie name.');
      return RESERVED.has(name);
    });
  });
}
export function forbidden(name) {
  name = name.toLowerCase();
  return name === HEADER || name.startsWith('x-forwarded-') ||
    ['forwarded', 'x-real-ip', 'x-synapdesk-client-ip', 'x-synapdesk-ip-source'].includes(name);
}
export function capture(request) {
  const raw = request.rawHeaders;
  for (let i = 0; i < raw.length; i += 2) {
    if (forbidden(raw[i])) throw new Error('Untrusted ingress metadata.');
  }
  let ip = request.socket.remoteAddress;
  if (ip?.startsWith('::ffff:') && isIP(ip.slice(7)) === 4) ip = ip.slice(7);
  if (!isIP(ip)) throw new Error('Missing transport peer.');
  const controls = NAMES.map(name => [name, raw.filter((_, i) =>
    i % 2 === 1 && raw[i - 1].toLowerCase() === name)]);
  return Object.freeze({ip, method: request.method, path: request.url, rawControls: controls,
    controls: sha(JSON.stringify(controls))});
}
export function seal(context, method, path, headers, key, audience, filterCookies, delegation) {
  if (delegation?.ssr === true && typeof filterCookies !== 'function') throw new Error('Missing SSR projection.');
  const controls = NAMES.map(name => [name, headers.has(name) ? [headers.get(name)] : []]);
  let expected = context?.controls;
  if (context && filterCookies) {
    // Misma política P1 validada, aplicada a los originales antes de descartar cookies ajenas.
    const projected = context.rawControls.map(([name, values]) => {
      if(name !== 'cookie') return [name, values];
      const originals = credentialPairs(values);
      const filtered = filterCookies(values.length ? values.join('; ') : null, {preservePairEvidence: true});
      const outgoing = filtered === null ? [] : [filtered];
      // Invariante independiente: ni un filtro futuro puede reparar, escoger o borrar una credencial.
      if (JSON.stringify(originals) !== JSON.stringify(credentialPairs(outgoing))) {
        throw new Error('Credential representation changed.');
      }
      return [name, outgoing];
    });
    if (delegation?.ssr === true) {
      const source = new URL(context.path, 'http://ingreso.invalid').pathname;
      const target = new URL(path, 'http://ingreso.invalid').pathname;
      const navigation = /^\/(?:inicio|metricas|tickets(?:\/nuevo|\/[0-9a-f-]{36})?)$/i.test(source);
      const read = /^\/api\/v1\/(?:metrics\/summary|tickets(?:\/[0-9a-f-]{36}(?:\/recommendations)?)?)$/i.test(target);
      const original = Object.fromEntries(context.rawControls);
      if (!navigation || !read || context.method !== 'GET' || method !== 'GET' ||
          original.origin.length > 1 ||
          (original.origin.length && original.origin[0] !== delegation.publicOrigin) ||
          original['sec-fetch-site'].length > 1 ||
          original['sec-fetch-site'].some(value => !['same-origin', 'none'].includes(value)) ||
          original['x-csrf-token'].length) throw new Error('SSR delegation rejected.');
      // Solo lecturas de codigo: se conserva el socket y la representacion de credenciales.
      // Origin/Sec-Fetch-Site se validan arriba; no se inventa un Origin para SSR.
      for (const item of projected) if (item[0] !== 'cookie') item[1] = [];
    }
    expected = sha(JSON.stringify(projected));
  }
  // Única traducción BFF local: POST del navegador aporta Origin real; FastAPI conserva GET.
  const bootstrap = context?.method === 'POST' && context.path === '/api/local/csrf' &&
    method === 'GET' && path === '/api/v1/auth/csrf';
  if (!context || (!bootstrap && delegation?.ssr !== true && (context.method !== method || context.path !== path)) ||
      expected !== sha(JSON.stringify(controls)) || headers.has(HEADER)) {
    // No corregir un Cookie/Origin/CSRF modificado por el transporte.
    throw new Error('Ingress evidence mismatch.');
  }
  const payload = Buffer.from(JSON.stringify({v: 1, aud: audience, ip: context.ip,
    ts: Math.floor(Date.now() / 1000), nonce: randomBytes(16).toString('hex'),
    method, path, controls: expected})).toString('base64url');
  const signature = createHmac('sha256', key).update('synapdesk:ingreso-local:v1\0' + payload).digest('hex');
  return payload + '.' + signature;
}
