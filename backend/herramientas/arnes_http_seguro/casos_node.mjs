// Cliente HTTP real. CA por solicitud; nunca desactiva validación TLS.
import fs from "node:fs";
import http from "node:http";
import https from "node:https";
import assert from "node:assert/strict";

const config = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const phase = process.argv[3];
const ca = fs.readFileSync(config.ca);
const results = [];
async function test(id, fn, gap = null) {
  try { await fn(); results.push({ id, passed: true, ...(gap ? { incompatibility: gap } : {}) }); }
  catch (error) {
    let message = String(error.message);
    for (const value of [...config.tokens, config.wrong, config.cookie, config.context, config.csrf, config.expiredContext, config.expiredCsrf]) message = message.replaceAll(value, '[REDACTED]');
    results.push({ id, passed: false, error_type: error.constructor.name, diagnostic: message.slice(0, 800) });
  }
}
function request(base, route, { headers = {}, method = "GET", trust = true, timeout = 45000 } = {}) {
  return new Promise((resolve, reject) => {
    const url = new URL(route, base);
    const transport = url.protocol === "https:" ? https : http;
    // Cada caso usa conexión propia: los 500 cierran el socket ASGI y no deben
    // contaminar la comprobación siguiente mediante keep-alive del cliente.
    if (Array.isArray(headers)) headers = [...headers, "Host", url.host];
    const options = { method, headers, timeout, agent: false, ...(url.protocol === "https:" && trust ? { ca } : {}) };
    const req = transport.request(url, options, (r) => {
      let body = "";
      r.setEncoding("utf8");
      r.on("data", (part) => body += part);
      r.on("end", () => resolve({ status: r.statusCode, headers: r.headers, body,
        json: () => JSON.parse(body) }));
      r.on("error", reject);
    });
    req.on("timeout", () => req.destroy(new Error("timeout")));
    req.on("error", reject);
    req.end();
  });
}
const bearer = (token = config.tokens[0]) => ({ Authorization: "Bearer " + token });
const origin = { Origin: config.origin };
function apiError(r, code, status) {
  assert.equal(r.status, status);
  assert.equal(r.headers["cache-control"], "no-store");
  assert.equal(r.headers["set-cookie"], undefined);
  assert.deepEqual(Object.keys(r.json().error).sort(), ["code", "details", "message", "requestId"]);
  assert.equal(r.json().error.code, code);
  assert.match(r.json().error.requestId, /^[0-9a-f-]{36}$/i);
  for (const secret of [...config.tokens, config.context, config.csrf]) assert(!r.body.includes(secret));
}
const flat = (entries) => entries.flatMap(([k, v]) => [k, v]);
const csrfHeaders = { ...origin, ...bearer(), Cookie: "synapdesk_csrf_context_dev=" + config.context, "X-CSRF-Token": config.csrf };

if (["unavailable", "hostname", "untrusted"].includes(phase)) {
  await test("PR30_CANAL_RECHAZADO_" + phase.toUpperCase(), async () => {
    apiError(await request(config.next, "/api/v1/ensayo/eco"), "SERVICE_UNAVAILABLE", 503);
  });
} else if (phase === "local") {
  await test("TLS_CA_HOSTNAME_Y_POSTGRESQL", async () => {
    const r = await request(config.backend, "/api/v1/ensayo/servicio", { headers: bearer() });
    assert.equal(r.status, 200); assert.equal(r.json().schema, "0007_recomendaciones_rag");
    assert.equal(r.json().service, "nextjs"); assert.equal(r.json().user_identity, false);
    assert.equal(r.json().ip_verified, false);
  });
  await test("TLS_CA_NO_CONFIADA", async () => { await assert.rejects(request(config.backend, "/api/v1/ensayo/eco", { trust: false })); });
  await test("TLS_HOSTNAME_INCORRECTO", async () => { await assert.rejects(request(config.backend.replace("localhost", "127.0.0.1"), "/api/v1/ensayo/eco"), { code: "ERR_TLS_CERT_ALTNAME_INVALID" }); });
  await test("NODE_SERVICIO_NO_DISPONIBLE", async () => { await assert.rejects(request(config.unavailable, "/api/v1/ensayo/eco"), { code: "ECONNREFUSED" }); });
  for (const [id, headers] of [["AUSENTE", {}], ["INCORRECTA", bearer(config.wrong)],
      ["ESQUEMA_INVALIDO", { Authorization: "Basic " + config.wrong }],
      ["DUPLICADA", flat([["Authorization", "Bearer " + config.tokens[0]], ["Authorization", "Bearer " + config.tokens[0]]])]]) {
    await test("SEC01B_" + id, async () => apiError(await request(config.backend, "/api/v1/ensayo/servicio", { headers }), "SERVICE_UNAVAILABLE", 503));
  }
  await test("SEC01B_VENCIDA", async () => apiError(await request(config.backend, "/api/v1/ensayo/vencida", { headers: bearer() }), "SERVICE_UNAVAILABLE", 503));
  await test("SEC01B_OTRO_ENTORNO", async () => apiError(await request(config.backend, "/api/v1/ensayo/otro-entorno", { headers: bearer() }), "SERVICE_UNAVAILABLE", 503));
  await test("SEC01B_ROTACION_SEGUNDA", async () => assert.equal((await request(config.backend, "/api/v1/ensayo/servicio", { headers: bearer(config.tokens[1]) })).status, 200));
  for (const name of ["X-Forwarded-For", "X-Real-IP", "Forwarded", "X-Forwarded-Proto", "X-SynapDesk-Client-IP"]) {
    await test("IP_NO_ACREDITADA_" + name, async () => apiError(await request(config.backend, "/api/v1/auth/csrf", { headers: { ...origin, ...bearer(), [name]: "198.51.100.7" } }), "SERVICE_UNAVAILABLE", 503));
  }
  await test("CSRF_PRODUCTIVO_CERRADO_CON_SEC01B", async () => apiError(await request(config.backend, "/api/v1/auth/csrf", { headers: { ...origin, ...bearer() } }), "SERVICE_UNAVAILABLE", 503));
  for (const [method, path] of [["POST", "login"], ["GET", "me"], ["POST", "logout"]]) {
    await test("RUTA_PRODUCTIVA_AUSENTE_" + path, async () => assert.equal((await request(config.backend, "/api/v1/auth/" + path, { method, headers: bearer() })).status, 404));
  }
  for (const [id, value] of [["VALIDA", config.origin], ["INVALIDA", "https://ajeno.invalid"], ["AUSENTE", null]]) {
    await test("ORIGIN_" + id, async () => {
      const h = { ...csrfHeaders }; if (value === null) delete h.Origin; else h.Origin = value;
      const r = await request(config.backend, "/api/v1/ensayo/controles", { method: "POST", headers: h });
      if (id === "VALIDA") assert.equal(r.status, 200); else apiError(r, "ORIGIN_INVALID", 403);
    });
  }
  await test("ORIGIN_PRECEDE_SERVICIO", async () => apiError(await request(config.backend, "/api/v1/ensayo/controles", { method: "POST" }), "ORIGIN_INVALID", 403));
  for (const [id, token] of [["AUSENTE", null], ["INVALIDO", config.wrong]]) {
    await test("CSRF_" + id, async () => {
      const h = { ...csrfHeaders }; if (token === null) delete h["X-CSRF-Token"]; else h["X-CSRF-Token"] = token;
      apiError(await request(config.backend, "/api/v1/ensayo/controles", { method: "POST", headers: h }), "CSRF_INVALID", 403);
    });
  }
  await test("CSRF_DUPLICADO", async () => apiError(await request(config.backend, "/api/v1/ensayo/controles", { method: "POST", headers: flat([...Object.entries(csrfHeaders), ["X-CSRF-Token", config.csrf]]) }), "CSRF_INVALID", 403));
  await test("ORIGIN_DUPLICADO", async () => apiError(await request(config.backend, "/api/v1/ensayo/controles", { method: "POST", headers: flat([...Object.entries(csrfHeaders), ["Origin", config.origin]]) }), "ORIGIN_INVALID", 403));
  await test("CSRF_CONTEXTO_VENCIDO", async () => apiError(await request(config.backend, "/api/v1/ensayo/controles", { method: "POST", headers: { ...csrfHeaders, Cookie: "synapdesk_csrf_context_dev=" + config.expiredContext, "X-CSRF-Token": config.expiredCsrf } }), "CSRF_INVALID", 403));
  for (const [id, headers, status] of [["SAME_ORIGIN", { "Sec-Fetch-Site": "same-origin" }, 200], ["CROSS_SITE", { "Sec-Fetch-Site": "cross-site" }, 403], ["AUSENTE", {}, 403]]) {
    await test("BOOTSTRAP_" + id, async () => assert.equal((await request(config.backend, "/api/v1/ensayo/bootstrap", { headers })).status, status));
  }
  for (const [id, cookie] of [["DUPLICADA", "synapdesk_session_dev=a; synapdesk_session_dev=b"], ["SIN_IGUAL", "synapdesk_session_dev"], ["VACIA", "synapdesk_session_dev="], ["COMILLAS", 'synapdesk_session_dev="a"'], ["CODIFICACION", "synapdesk_session_dev=%ZZ"], ["PERFIL_AJENO", "__Host-synapdesk_session=a"]]) {
    await test("COOKIE_BACKEND_RECHAZA_" + id, async () => apiError(await request(config.backend, "/api/v1/ensayo/eco", { headers: { Cookie: cookie } }), "INTERNAL_ERROR", 500));
  }
  await test("ERROR_BD_REAL", async () => apiError(await request(config.backend, "/api/v1/ensayo/fallo-bd"), "SERVICE_UNAVAILABLE", 503));
  await test("ERROR_SERIALIZACION", async () => apiError(await request(config.backend, "/api/v1/ensayo/serializacion"), "INTERNAL_ERROR", 500));
  await test("REQUEST_ID_NO_CLIENTE", async () => {
    const r = await request(config.backend, "/api/v1/ensayo/servicio", { headers: { ...bearer(), "X-Request-ID": "11111111-1111-4111-8111-111111111111" } });
    assert.notEqual(r.json().request_id, "11111111-1111-4111-8111-111111111111");
  });
  await test("NEXT_SUSTITUTO_SEC01B_TLS_POSTGRESQL", async () => {
    const r = await request(config.next, "/ensayo-canal/servicio", { headers: { ...origin, Authorization: "Bearer " + config.wrong, "X-Forwarded-For": "198.51.100.7" } });
    assert.equal(r.status, 200); assert.equal(r.json().schema, "0007_recomendaciones_rag");
    assert.equal(r.json().harness, config.identity); assert(!r.body.includes(config.tokens[0]));
  });
  await test("NEXT_SUSTITUTO_NO_ABRE_CSRF", async () => apiError(await request(config.next, "/ensayo-canal/csrf", { headers: origin }), "SERVICE_UNAVAILABLE", 503));
  await test("NEXT_SUSTITUTO_CSRF_PERSISTENTE_VALIDO", async () => {
    const r = await request(config.next, "/ensayo-canal/controles", { method: "POST", headers: csrfHeaders });
    assert.equal(r.status, 200); assert.equal(r.json().validated, true); assert.equal(r.json().business_effects, false);
  });
  await test("NEXT_SUSTITUTO_CSRF_AUSENTE", async () => {
    const h = { ...csrfHeaders }; delete h["X-CSRF-Token"];
    apiError(await request(config.next, "/ensayo-canal/controles", { method: "POST", headers: h }), "CSRF_INVALID", 403);
  });
  await test("NEXT_SUSTITUTO_CSRF_DUPLICADO", async () => apiError(await request(config.next, "/ensayo-canal/controles", { method: "POST", headers: flat([...Object.entries(csrfHeaders), ["X-CSRF-Token", config.csrf]]) }), "CSRF_INVALID", 403));
  await test("NEXT_SUSTITUTO_CONTEXTO_VENCIDO", async () => apiError(await request(config.next, "/ensayo-canal/controles", { method: "POST", headers: { ...csrfHeaders, Cookie: "synapdesk_csrf_context_dev=" + config.expiredContext, "X-CSRF-Token": config.expiredCsrf } }), "CSRF_INVALID", 403));
  for (const [id, h] of [["AUSENTE", {}], ["INVALIDO", { Origin: "https://ajeno.invalid" }]]) {
    await test("PR30_ORIGIN_" + id, async () => apiError(await request(config.next, "/api/v1/ensayo/controles", { method: "POST", headers: h }), "ORIGIN_INVALID", 403));
  }
  await test("PR30_SIN_CREDENCIAL_SERVICIO", async () => apiError(await request(config.next, "/api/v1/ensayo/servicio", { headers: { ...origin, ...bearer() } }), "SERVICE_UNAVAILABLE", 503), "PR30_NO_INYECTA_SEC01B");
  await test("PR30_FILTRA_CABECERAS", async () => {
    const r = await request(config.next, "/api/v1/ensayo/eco", { headers: { ...origin, ...bearer(), "X-Forwarded-For": "198.51.100.7", "X-Real-IP": "198.51.100.7", Forwarded: "for=198.51.100.7", "X-SynapDesk-Client-IP": "198.51.100.7", "X-CSRF-Token": config.csrf } });
    assert.equal(r.status, 200); assert.equal(r.json().authorization_present, false);
    assert.equal(r.json().forwarded_present, false); assert.equal(r.json().origin, config.origin);
    assert.equal(r.json().csrf_count, 1);
  });
  for (const [id, cookie, expected] of [["AUSENTE", "", false], ["VALIDA", "synapdesk_session_dev=" + config.cookie, true], ["DESCONOCIDA", "desconocida=a", false]]) {
    await test("PR30_COOKIE_" + id, async () => {
      const r = await request(config.next, "/api/v1/ensayo/eco", { headers: { Cookie: cookie } });
      assert.equal(r.status, 200); assert.equal(r.json().session, expected); assert.equal(r.json().unknown_cookie, false);
    });
  }
  for (const [id, cookie] of [["DUPLICADA", "synapdesk_session_dev=a; synapdesk_session_dev=b"], ["CODIFICACION", "synapdesk_session_dev=%ZZ"], ["VACIA", "synapdesk_session_dev="]]) {
    await test("PR30_COOKIE_RECHAZADA_" + id, async () => apiError(await request(config.next, "/api/v1/ensayo/eco", { headers: { Cookie: cookie } }), "INTERNAL_ERROR", 500));
  }
  await test("PR30_PIERDE_COOKIE_MALFORMADA", async () => {
    const r = await request(config.next, "/api/v1/ensayo/eco", { headers: { Cookie: "synapdesk_session_dev; synapdesk_csrf_context_dev=" + config.cookie } });
    assert.equal(r.status, 200); assert.equal(r.json().session, false); assert.equal(r.json().context, true);
  }, "PR30_COOKIE_SIN_IGUAL_SE_PIERDE");
  await test("PR30_OCULTA_MEZCLA_PERFILES", async () => {
    const r = await request(config.next, "/api/v1/ensayo/eco", { headers: { Cookie: "__Host-synapdesk_session=a; synapdesk_csrf_context_dev=" + config.cookie } });
    assert.equal(r.status, 200); assert.equal(r.json().context, true);
  }, "PR30_FILTRA_PERFIL_AJENO_ANTES_DE_RECHAZO");
  await test("PR30_CSRF_CERRADO", async () => apiError(await request(config.next, "/api/v1/auth/csrf", { headers: origin }), "SERVICE_UNAVAILABLE", 503));
  await test("PR30_MULTIPLES_COOKIES", async () => {
    const r = await request(config.next, "/api/v1/ensayo/eco", { headers: { Cookie: "synapdesk_session_dev=" + config.cookie + "; synapdesk_csrf_context_dev=" + config.context } });
    assert.equal(r.status, 200); assert.equal(r.json().session, true); assert.equal(r.json().context, true);
  });
  await test("PR30_ERROR_BD_SANEADO", async () => apiError(await request(config.next, "/api/v1/ensayo/fallo-bd"), "SERVICE_UNAVAILABLE", 503));
  await test("PR30_ERROR_SERIALIZACION_SANEADO", async () => apiError(await request(config.next, "/api/v1/ensayo/serializacion"), "INTERNAL_ERROR", 500));
  await test("PR30_REDIRECCION_RECHAZADA", async () => apiError(await request(config.next, "/api/v1/ensayo/redireccion"), "SERVICE_UNAVAILABLE", 503));
  await test("PR30_TIMEOUT_REAL_30S", async () => {
    const start = performance.now();
    apiError(await request(config.next, "/api/v1/ensayo/lento"), "SERVICE_UNAVAILABLE", 503);
    assert(performance.now() - start >= 29000);
  });
  await test("PR30_SSR_REAL_AISLADO", async () => {
    const read = async (cookie) => {
      const r = await request(config.next, "/", { headers: { Cookie: cookie } });
      const match = r.body.match(/<pre id="observado">([^<]*)<\/pre>/);
      assert(match); return JSON.parse(match[1].replaceAll("&quot;", '"').replaceAll("&amp;", "&"));
    };
    const [a, b] = await Promise.all([read("synapdesk_session_dev=" + config.cookie), read("desconocida=a")]);
    assert.equal(a.body.session, true); assert.equal(b.body.session, false);
    assert.equal(a.body.origin, null); assert.equal(a.body.authorization_present, false);
  });
  await test("PR30_SSR_SEC01B_AUSENTE", async () => {
    const r = await request(config.next, "/ssr-servicio");
    assert(r.body.includes("SERVICE_UNAVAILABLE"));
  }, "PR30_SSR_NO_INYECTA_SEC01B");
}

if (["local", "production"].includes(phase)) {
await test("PR30_SET_COOKIE_" + phase.toUpperCase(), async () => {
  const r = await request(config.next, "/api/v1/ensayo/cookies");
  assert.equal(r.status, 200); assert.equal(r.headers["cache-control"], "no-store");
  const cookies = r.headers["set-cookie"];
  assert.equal(cookies.length, 2); assert(cookies.every(c => !c.startsWith("desconocida=")));
  for (const c of cookies) {
    assert(c.includes("HttpOnly") && c.includes("SameSite=lax") && c.includes("Path=/") && !c.includes("Domain="));
    if (phase === "production") assert(c.startsWith("__Host-") && c.includes("Secure"));
    else assert(c.startsWith("synapdesk_") && !c.includes("Secure"));
  }
});
await test("PR30_BORRADO_COOKIE_" + phase.toUpperCase(), async () => {
  const r = await request(config.next, "/api/v1/ensayo/borrar-cookie");
  assert.equal(r.status, 204); assert.equal(r.body, "");
  assert.equal(r.headers["set-cookie"].length, 2);
  assert(r.headers["set-cookie"].every(c => c.includes("Max-Age=0") && !c.includes("Domain=")));
});
}
if (phase === "production") {
  await test("PR30_PERFIL_PRODUCTION_ENTRANTE", async () => {
    const r = await request(config.next, "/api/v1/ensayo/eco?profile=production", { headers: { Cookie: "__Host-synapdesk_session=" + config.cookie + "; __Host-synapdesk_csrf_context=" + config.cookie } });
    assert.equal(r.status, 200); assert.equal(r.json().session, true); assert.equal(r.json().context, true);
  });
}
console.log(JSON.stringify({ phase, results, passed: results.filter(r => r.passed).length,
  failed: results.filter(r => !r.passed).length }));
process.exitCode = results.some(r => !r.passed) ? 1 : 0;
