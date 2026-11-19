import { test } from "node:test";
import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import { capture, seal } from "./protocolo.mjs";
import { rutaPermitida } from "./rutas.mjs";
const key = randomBytes(32);
const origin = "http://127.0.0.1:3010";
const request = (method, url, extra = []) => ({ method, url,
  rawHeaders: ["Origin", origin, ...extra], socket: { remoteAddress: "127.0.0.2" } });
const headers = () => new Headers({ origin });
test("traducción única POST local CSRF a GET contractual conserva IP y controles", () => {
  const proof = seal(capture(request("POST", "/api/local/csrf")), "GET", "/api/v1/auth/csrf", headers(), key, "audiencia");
  const payload = JSON.parse(Buffer.from(proof.split(".")[0], "base64url"));
  assert.equal(payload.ip, "127.0.0.2");
  assert.equal(payload.method, "GET");
  assert.equal(payload.path, "/api/v1/auth/csrf");
});
for (const [method, source, targetMethod, target] of [
  ["GET", "/api/local/csrf", "GET", "/api/v1/auth/csrf"],
  ["POST", "/api/local/csrf?x=1", "GET", "/api/v1/auth/csrf"],
  ["POST", "/api/local/csrf", "GET", "/api/v1/auth/me"],
  ["POST", "/api/local/csrf", "POST", "/api/v1/auth/login"],
  ["POST", "/api/local/csrf", "GET", "/api/v1/auth/csrf?x=1"],
  ["GET", "/tickets", "GET", "/api/v1/tickets"],
]) test(`rechaza otra traducción ${method} ${source} a ${targetMethod} ${target}`, () => {
  assert.throws(() => seal(capture(request(method, source)), targetMethod, target, headers(), key, "audiencia"));
});
test("no traduce un Origin cambiado", () => {
  assert.throws(() => seal(capture(request("POST", "/api/local/csrf")), "GET", "/api/v1/auth/csrf",
    new Headers({ origin: "https://ajeno.invalid" }), key, "audiencia"));
});
test("no repara U+00A0 en Cookie al traducir CSRF", () => {
  const raw = request("POST", "/api/local/csrf", ["Cookie", "synapdesk_session_dev=abc\u00a0"]);
  const h = headers(); h.set("cookie", "synapdesk_session_dev=abc");
  assert.throws(() => seal(capture(raw), "GET", "/api/v1/auth/csrf", h, key, "audiencia"));
});
for (const name of ["Forwarded", "X-Forwarded-For", "X-Real-IP", "X-SynapDesk-Client-IP", "X-SynapDesk-Ingress-Evidence"])
  test(`rechaza procedencia aportada por el cliente: ${name}`, () => {
    assert.throws(() => capture(request("GET", "/api/v1/tickets", [name, "127.0.0.1"])));
  });
test("proyección permite solo quitar cookies ajenas sin cambiar credenciales", () => {
  const raw = request("GET", "/api/v1/tickets", ["Cookie", "other=1; synapdesk_session_dev=original"]);
  const h = headers(); h.set("cookie", "synapdesk_session_dev=original");
  const filter = original => {
    assert.equal(original, "other=1; synapdesk_session_dev=original");
    return "synapdesk_session_dev=original";
  };
  assert.doesNotThrow(() => seal(capture(raw), "GET", "/api/v1/tickets", h, key, "audiencia", filter));
  h.set("cookie", "synapdesk_session_dev=modificada");
  assert.throws(() => seal(capture(raw), "GET", "/api/v1/tickets", h, key, "audiencia", filter));
});
test("proyección no omite el rechazo del original antes de filtrar", () => {
  const raw = request("GET", "/api/v1/tickets", ["Cookie", "synapdesk_session_dev=original\u00a0"]);
  assert.throws(() => seal(capture(raw), "GET", "/api/v1/tickets", headers(), key, "audiencia", () => {throw new Error("P1");}));
});
for(const [name, original, repaired] of [
  ['NBSP', 'synapdesk_session_dev=original\u00a0', 'synapdesk_session_dev=original'],
  ['SP', 'synapdesk_session_dev=original ', 'synapdesk_session_dev=original'],
  ['duplicada', 'synapdesk_session_dev=uno; synapdesk_session_dev=dos', 'synapdesk_session_dev=dos'],
  ['descarte', 'synapdesk_session_dev=original', null],
]) test(`una regresión del filtro no puede acreditar ${name}`, () => {
  const raw = request('GET', '/api/v1/tickets', ['Cookie', original]);
  const h = headers(); if(repaired !== null) h.set('cookie', repaired);
  assert.throws(() => seal(capture(raw), 'GET', '/api/v1/tickets', h, key, 'audiencia', () => repaired));
});

const ssr = { ssr: true, publicOrigin: origin };
const sessionCookie = "synapdesk_session_dev=original";
const ssrHeaders = () => new Headers({ cookie: sessionCookie });
const projectCookie = () => sessionCookie;

const id = '11111111-1111-4111-8111-111111111111';
for (const [method, path] of [['GET', '/documentos'], ['GET', `/documentos/${id}`],
  ['GET', '/api/v1/documents?page=2'], ['POST', '/api/v1/documents'],
  ['GET', `/api/v1/documents/${id}`], ['DELETE', `/api/v1/documents/${id}`],
  ['GET', `/api/v1/tickets/${id}/prediction`], ['POST', `/api/v1/tickets/${id}/prediction`]]) {
  test(`lanzador permite ${method} ${path}`, () => assert.equal(rutaPermitida(method, path), true));
}
for (const [method, path] of [['PUT', '/api/v1/documents'], ['GET', '/api/v1/documents/no-id'],
  ['POST', `/api/v1/tickets/${id}/prediction?x=1`], ['GET', '/documentos/privado/extra']]) {
  test(`lanzador rechaza ${method} ${path}`, () => assert.equal(rutaPermitida(method, path), false));
}
for (const [source, target] of [['/documentos', '/api/v1/documents?page=1'],
  [`/documentos/${id}`, `/api/v1/documents/${id}`], [`/tickets/${id}`, `/api/v1/tickets/${id}/prediction`]]) {
  test(`SSR permite ${source} a ${target}`, () => {
    const context = capture(request('GET', source, ['Cookie', sessionCookie]));
    assert.doesNotThrow(() => seal(context, 'GET', target, ssrHeaders(), key, 'audiencia', projectCookie, ssr));
    assert.throws(() => seal(context, 'POST', target, ssrHeaders(), key, 'audiencia', projectCookie, ssr));
  });
}
test("SSR acredita lecturas desde la navegación y conserva socket, cookie y nonce único", () => {
  const navigation = capture(request("GET", "/tickets?page=2", ["Cookie", sessionCookie, "Sec-Fetch-Site", "same-origin"]));
  const attest = () => seal(navigation, "GET", "/api/v1/tickets?page=2&pageSize=10", ssrHeaders(), key, "audiencia", projectCookie, ssr);
  const first = JSON.parse(Buffer.from(attest().split(".")[0], "base64url"));
  const second = JSON.parse(Buffer.from(attest().split(".")[0], "base64url"));
  assert.equal(first.ip, "127.0.0.2");
  assert.equal(first.path, "/api/v1/tickets?page=2&pageSize=10");
  assert.notEqual(first.nonce, second.nonce);
});
test("SSR acepta navegación directa sin Origin ni Fetch-Site", () => {
  const navigation = capture({ method: "GET", url: "/tickets", rawHeaders: ["Cookie", sessionCookie], socket: {remoteAddress: "127.0.0.2"} });
  assert.doesNotThrow(() => seal(navigation, "GET", "/api/v1/metrics/summary", ssrHeaders(), key, "audiencia", projectCookie, ssr));
});
for (const [sourceMethod, source, targetMethod, target, extra] of [
  ["GET", "/tickets", "POST", "/api/v1/tickets", []],
  ["POST", "/tickets", "GET", "/api/v1/tickets", []],
  ["GET", "/api/v1/tickets", "GET", "/api/v1/tickets", []],
  ["GET", "/login", "GET", "/api/v1/tickets", []],
  ["GET", "/tickets", "GET", "/api/v1/auth/csrf", []],
  ["GET", "/tickets", "GET", "/api/v1/auth/me", []],
  ["GET", "/tickets", "GET", "/api/v1/tickets", ["Sec-Fetch-Site", "cross-site"]],
  ["GET", "/tickets", "GET", "/api/v1/tickets", ["X-CSRF-Token", "no-proyectar"]],
  ["GET", "/tickets", "GET", "/api/v1/tickets", ["Origin", origin]],
]) test(`SSR rechaza delegación ${sourceMethod} ${source} a ${targetMethod} ${target} ${extra[0] ?? ""}`, () => {
  const context = capture(request(sourceMethod, source, ["Cookie", sessionCookie, ...extra]));
  assert.throws(() => seal(context, targetMethod, target, ssrHeaders(), key, "audiencia", projectCookie, ssr));
});
test("SSR rechaza Origin ajeno, falta de proyección y credencial cambiada", () => {
  const navigation = capture(request("GET", "/tickets", ["Cookie", sessionCookie]));
  assert.throws(() => seal(navigation, "GET", "/api/v1/tickets", ssrHeaders(), key, "audiencia", undefined, ssr));
  assert.throws(() => seal(navigation, "GET", "/api/v1/tickets", ssrHeaders(), key, "audiencia", projectCookie, {ssr:true, publicOrigin:"https://ajeno.invalid"}));
  assert.throws(() => seal(navigation, "GET", "/api/v1/tickets", new Headers({cookie:sessionCookie + "x"}), key, "audiencia", projectCookie, ssr));
});
