// Pruebas de regresión del proxy de mismo origen y del adaptador SSR (PR #30), con un backend
// falso real (node:http). Ejecutar desde frontend/: npm run test:proxy (tarda unos 2 min por las
// cuatro pruebas del tiempo de espera de 30 s). No necesitan Next, el backend real ni PostgreSQL.
import { after, before, beforeEach, describe, test } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const SESSION =
  "synapdesk_session_dev=s3cr3t-sesion; HttpOnly; Path=/; SameSite=Lax; Max-Age=28800";
const CONTEXT = "synapdesk_csrf_context_dev=s3cr3t-contexto; HttpOnly; Path=/; SameSite=Lax";
const DELETE = "synapdesk_session_dev=; HttpOnly; Path=/; SameSite=Lax; Max-Age=0";
const PROD_SESSION = "__Host-synapdesk_session=s3cr3t-prod; HttpOnly; Secure; Path=/; SameSite=Lax";
const PROD_CONTEXT = "__Host-synapdesk_csrf_context=s3cr3t-prod-ctx; HttpOnly; Secure; Path=/";
const OTHER = "tracker=s3cr3t-ajeno; Path=/";

// ── Backend falso ──
let hits = 0;
let lastHeaders = {};
const responses = {
  "/api/v1/one": [SESSION],
  "/api/v1/two": [SESSION, CONTEXT],
  "/api/v1/mixed-unknown": [SESSION, OTHER],
  "/api/v1/mixed-profiles": [SESSION, PROD_SESSION, PROD_CONTEXT, CONTEXT],
  "/api/v1/many": [SESSION, OTHER, CONTEXT, "sin-signo-igual", PROD_SESSION],
  "/api/v1/delete": [DELETE],
  "/api/v1/duplicate": [SESSION, "synapdesk_session_dev=otro; Path=/"],
  "/api/v1/prod": [PROD_SESSION, SESSION, PROD_CONTEXT],
};
const backend = http.createServer((req, res) => {
  hits += 1;
  lastHeaders = req.headers;
  const path = req.url.split("?")[0];
  if (path === "/api/v1/redirect") {
    res.writeHead(302, { Location: "http://evil.invalid/robar" }).end();
  } else if (path === "/api/v1/slow") {
    setTimeout(() => res.writeHead(200).end("{}"), 35_000).unref();
  } else if (path === "/api/v1/slow-body") {
    // Cabeceras de inmediato y cuerpo incompleto hasta después del plazo (revisión del 12-11).
    res.writeHead(200, { "Content-Type": "application/json" });
    res.flushHeaders();
    res.write('{"parcial":');
    setTimeout(() => res.end("true}"), 35_000).unref();
  } else if (path === "/api/v1/cut-body") {
    // Cabeceras de inmediato y conexión cortada a mitad del cuerpo.
    res.writeHead(200, { "Content-Type": "application/json", "Content-Length": "100" });
    res.write('{"parcial":');
    setTimeout(() => res.destroy(), 50).unref();
  } else if (path === "/api/v1/not-json") {
    res.writeHead(500, { "Content-Type": "text/plain" }).end("fallo interno");
  } else if (path === "/api/v1/backend-error") {
    res.writeHead(403, { "Content-Type": "application/json" }).end(
      JSON.stringify({
        error: {
          code: "FORBIDDEN",
          message: "x",
          details: null,
          requestId: "11111111-1111-4111-8111-111111111111",
        },
      })
    );
  } else if (path === "/api/v1/echo") {
    res.writeHead(200, { "Content-Type": "application/json" }).end(JSON.stringify(req.headers));
  } else {
    res.writeHead(200, { "Content-Type": "application/json", "Set-Cookie": responses[path] ?? [] });
    res.end("{}");
  }
});
let backendUrl;
let closedUrl;

// ── Registros: ningún valor de cookie debe aparecer ──
const logs = [];
const original = { error: console.error, warn: console.warn };

let proxy;
let ssr;
let api;

before(async () => {
  await new Promise((r) => backend.listen(0, "127.0.0.1", r));
  backendUrl = `http://127.0.0.1:${backend.address().port}`;
  const closed = http.createServer();
  await new Promise((r) => closed.listen(0, "127.0.0.1", r));
  closedUrl = `http://127.0.0.1:${closed.address().port}`;
  await new Promise((r) => closed.close(r));
  console.error = (...a) => logs.push(a.join(" "));
  console.warn = (...a) => logs.push(a.join(" "));
  proxy = await import("@/lib/backend-proxy");
  ssr = await import("@/lib/transport/server");
  ({ api } = await import("@/lib/api"));
});
after(() => {
  Object.assign(console, original);
  backend.close();
});
beforeEach(() => {
  process.env.BACKEND_INTERNAL_URL = backendUrl;
  process.env.AUTH_COOKIE_PROFILE = "local";
  globalThis.__requestCookie = undefined;
});

const call = (path, init = {}) =>
  proxy.proxyToBackend(
    new Request(`http://localhost:3000/api/v1/${path}`, init),
    path.split("?")[0].split("/")
  );

async function expectContractError(response, status, code) {
  assert.equal(response.status, status);
  assert.equal(response.headers.get("cache-control"), "no-store");
  const body = await response.json();
  assert.equal(body.error.code, code);
  assert.match(body.error.requestId, UUID, "requestId no vacío y válido");
  assert.equal(body.error.details, null);
  return body.error.requestId;
}

async function expectThrownContractError(promise, code = "SERVICE_UNAVAILABLE") {
  try {
    await promise;
  } catch (error) {
    assert.equal(error?.error?.code, code);
    assert.match(error.error.requestId, UUID, "requestId no vacío y válido");
    assert.ok(!JSON.stringify(error).includes("127.0.0.1"), "sin direcciones internas");
    return error.error.requestId;
  }
  assert.fail("se esperaba un error");
}

// ── Hallazgo 1: AUTH_COOKIE_PROFILE estricto ──
describe("1. AUTH_COOKIE_PROFILE", () => {
  test("local selecciona solo las cookies de desarrollo", () => {
    assert.deepEqual(
      [...proxy.allowedCookieNames()],
      ["synapdesk_session_dev", "synapdesk_csrf_context_dev"]
    );
  });
  test("production selecciona solo las cookies __Host-", () => {
    process.env.AUTH_COOKIE_PROFILE = "production";
    assert.deepEqual(
      [...proxy.allowedCookieNames()],
      ["__Host-synapdesk_session", "__Host-synapdesk_csrf_context"]
    );
  });
  test("variable ausente: local por defecto", () => {
    delete process.env.AUTH_COOKIE_PROFILE;
    assert.deepEqual(
      [...proxy.allowedCookieNames()],
      ["synapdesk_session_dev", "synapdesk_csrf_context_dev"]
    );
  });
  for (const value of ["productionn", "", "Production", " local", "dev"]) {
    test(`valor inválido ${JSON.stringify(value)}: sin perfil (no se elige local en silencio)`, () => {
      process.env.AUTH_COOKIE_PROFILE = value;
      assert.equal(proxy.allowedCookieNames(), null);
    });
  }
  test("proxy con perfil inválido: 503 con requestId y no llama al backend", async () => {
    process.env.AUTH_COOKIE_PROFILE = "productionn";
    const before = hits;
    await expectContractError(
      await call("one", { headers: { cookie: "synapdesk_session_dev=x" } }),
      503,
      "SERVICE_UNAVAILABLE"
    );
    assert.equal(hits, before);
    assert.ok(logs.some((l) => l.includes("AUTH_COOKIE_PROFILE")));
  });
  test("SSR con perfil inválido: error del contrato con requestId", async () => {
    process.env.AUTH_COOKIE_PROFILE = "productionn";
    await expectThrownContractError(ssr.getTransport());
  });
  test("production reenvía hacia FastAPI solo las cookies __Host-", async () => {
    process.env.AUTH_COOKIE_PROFILE = "production";
    await call("echo", {
      headers: {
        cookie:
          "synapdesk_session_dev=dev; __Host-synapdesk_session=p; otra=1; __Host-synapdesk_csrf_context=c",
      },
    });
    assert.equal(lastHeaders.cookie, "__Host-synapdesk_session=p; __Host-synapdesk_csrf_context=c");
  });
});

// ── Hallazgo 2: Set-Cookie filtrado ──
describe("2. Set-Cookie del backend", () => {
  const cookiesOf = (response) => response.headers.getSetCookie();
  test("una cookie autorizada pasa intacta", async () => {
    assert.deepEqual(cookiesOf(await call("one")), [SESSION]);
  });
  test("dos cookies autorizadas pasan como cabeceras separadas", async () => {
    assert.deepEqual(cookiesOf(await call("two")), [SESSION, CONTEXT]);
  });
  test("una autorizada y una desconocida: solo la autorizada", async () => {
    assert.deepEqual(cookiesOf(await call("mixed-unknown")), [SESSION]);
  });
  test("perfiles mezclados (local): no pasan las __Host-", async () => {
    assert.deepEqual(cookiesOf(await call("mixed-profiles")), [SESSION, CONTEXT]);
  });
  test("perfiles mezclados (production): no pasan las _dev", async () => {
    process.env.AUTH_COOKIE_PROFILE = "production";
    assert.deepEqual(cookiesOf(await call("prod")), [PROD_SESSION, PROD_CONTEXT]);
  });
  test("varios Set-Cookie: se procesan uno por uno, en orden, sin unir", async () => {
    const cookies = cookiesOf(await call("many"));
    assert.deepEqual(cookies, [SESSION, CONTEXT]);
    assert.ok(cookies.every((c) => !c.includes(", synapdesk")));
  });
  test("borrado de una cookie autorizada conserva Max-Age=0 y atributos", async () => {
    assert.deepEqual(cookiesOf(await call("delete")), [DELETE]);
  });
  test("cookie autorizada repetida: pasan ambas, sin normalizar", async () => {
    assert.equal(cookiesOf(await call("duplicate")).length, 2);
  });
  test("las no autorizadas no llegan al navegador y el registro no tiene valores", async () => {
    logs.length = 0;
    const response = await call("many");
    const raw = [...response.headers].map(([k, v]) => `${k}: ${v}`).join("\n");
    assert.ok(
      !raw.includes("tracker") && !raw.includes("__Host-") && !raw.includes("sin-signo-igual")
    );
    const log = logs.join("\n");
    assert.match(log, /tracker/);
    assert.ok(!log.includes("s3cr3t"), "ningún valor de cookie en los registros");
  });
});

// ── Hallazgo 3: requestId en los errores propios ──
describe("3. requestId en errores del proxy y del SSR", () => {
  test("proxy sin BACKEND_INTERNAL_URL", async () => {
    delete process.env.BACKEND_INTERNAL_URL;
    await expectContractError(await call("one"), 503, "SERVICE_UNAVAILABLE");
  });
  test("proxy con backend desconectado", async () => {
    process.env.BACKEND_INTERNAL_URL = closedUrl;
    await expectContractError(await call("one"), 503, "SERVICE_UNAVAILABLE");
  });
  test("proxy con redirección rechazada (sin Location)", async () => {
    const response = await call("redirect");
    assert.equal(response.headers.get("location"), null);
    await expectContractError(response, 503, "SERVICE_UNAVAILABLE");
  });
  test("proxy con ruta inválida (404) y método no permitido (405)", async () => {
    await expectContractError(
      await proxy.proxyToBackend(new Request("http://localhost:3000/api/v1/x"), [".."]),
      404,
      "NOT_FOUND"
    );
    const r = proxy.methodNotAllowed();
    assert.equal(r.headers.get("allow"), proxy.ALLOWED_METHODS);
    await expectContractError(r, 405, "METHOD_NOT_ALLOWED");
  });
  test("cada error tiene un requestId distinto y no usa el del navegador", async () => {
    delete process.env.BACKEND_INTERNAL_URL;
    const init = { headers: { "x-request-id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa" } };
    const a = await expectContractError(await call("one", init), 503, "SERVICE_UNAVAILABLE");
    const b = await expectContractError(await call("one", init), 503, "SERVICE_UNAVAILABLE");
    assert.notEqual(a, b);
    assert.ok(![a, b].includes("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"));
  });
  test("los errores del backend pasan sin cambios (su requestId se conserva)", async () => {
    const response = await call("backend-error");
    assert.equal(response.status, 403);
    assert.equal((await response.json()).error.requestId, "11111111-1111-4111-8111-111111111111");
  });
  test("SSR sin BACKEND_INTERNAL_URL", async () => {
    delete process.env.BACKEND_INTERNAL_URL;
    await expectThrownContractError(api.get("/one"));
  });
  test("SSR con backend desconectado", async () => {
    process.env.BACKEND_INTERNAL_URL = closedUrl;
    await expectThrownContractError(api.get("/one"));
  });
  test("SSR con redirección: no la sigue", async () => {
    const before = hits;
    await expectThrownContractError(api.get("/redirect"));
    assert.equal(hits, before + 1, "una sola petición, sin seguir Location");
  });
  test("SSR con respuesta que no es JSON: error con requestId propio", async () => {
    await expectThrownContractError(api.get("/not-json"), "UNKNOWN_ERROR");
  });
  test("SSR reenvía solo las cookies del perfil", async () => {
    globalThis.__requestCookie = "synapdesk_session_dev=a; otra=b; __Host-synapdesk_session=c";
    await api.get("/echo");
    assert.equal(lastHeaders.cookie, "synapdesk_session_dev=a");
  });
  test("proxy: tiempo de espera de 30 s → 503 con requestId", { timeout: 40_000 }, async () => {
    const start = Date.now();
    await expectContractError(await call("slow"), 503, "SERVICE_UNAVAILABLE");
    assert.ok(Date.now() - start >= 29_500);
  });
  test("SSR: tiempo de espera de 30 s → error con requestId", { timeout: 40_000 }, async () => {
    const start = Date.now();
    await expectThrownContractError(api.get("/slow"));
    assert.ok(Date.now() - start >= 29_500);
  });
});

// ── Revisión del 12-11: el plazo cubre también el cuerpo de la respuesta ──
describe("4. Cuerpo demorado o cortado después de las cabeceras", () => {
  test(
    "proxy: cabeceras 200 y cuerpo demorado → 503 con requestId",
    { timeout: 40_000 },
    async () => {
      const start = Date.now();
      await expectContractError(await call("slow-body"), 503, "SERVICE_UNAVAILABLE");
      assert.ok(Date.now() - start >= 29_500, "espera el plazo completo");
    }
  );
  test(
    "SSR: cabeceras 200 y cuerpo demorado → error con requestId",
    { timeout: 40_000 },
    async () => {
      const start = Date.now();
      await expectThrownContractError(api.get("/slow-body"));
      assert.ok(Date.now() - start >= 29_500, "espera el plazo completo");
    }
  );
  test("proxy: conexión cortada a mitad del cuerpo → 503 con requestId", async () => {
    await expectContractError(await call("cut-body"), 503, "SERVICE_UNAVAILABLE");
  });
  test("SSR: conexión cortada a mitad del cuerpo → error con requestId", async () => {
    await expectThrownContractError(api.get("/cut-body"));
  });
});

// ── Regresión de lo que ya funcionaba ──
describe("Regresión", () => {
  test("cabeceras de IP y arbitrarias no llegan a FastAPI; Origin y X-CSRF-Token sí", async () => {
    await call("echo", {
      method: "POST",
      body: "{}",
      headers: {
        origin: "http://localhost:3000",
        "x-csrf-token": "tok",
        "content-type": "application/json",
        "x-forwarded-for": "203.0.113.7",
        "x-real-ip": "203.0.113.8",
        "x-synapdesk-client-ip": "203.0.113.9",
        forwarded: "for=203.0.113.10",
        authorization: "Bearer x",
      },
    });
    assert.equal(lastHeaders.origin, "http://localhost:3000");
    assert.equal(lastHeaders["x-csrf-token"], "tok");
    for (const h of [
      "x-forwarded-for",
      "x-real-ip",
      "x-synapdesk-client-ip",
      "forwarded",
      "authorization",
    ]) {
      assert.equal(lastHeaders[h], undefined, h);
    }
  });
  test("todas las respuestas llevan no-store", async () => {
    assert.equal((await call("one")).headers.get("cache-control"), "no-store");
  });
});
