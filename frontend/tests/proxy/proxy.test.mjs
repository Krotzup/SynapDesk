// Pruebas del canal de servidor hacia FastAPI: proxy de mismo origen y adaptador SSR (PR #30),
// con SEC-01B (credencial de servicio y HTTPS verificado) y un backend falso real (node:https).
// Ejecutar desde frontend/: npm run test:proxy (tests/proxy/run.mjs genera la CA de prueba; tarda
// unos 2,5 min por las pruebas del plazo de 30 s). No necesitan Next, el backend real ni PostgreSQL.
import { after, before, beforeEach, describe, test } from "node:test";
import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import { readFileSync } from "node:fs";
import https from "node:https";
import path from "node:path";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const SESSION =
  "synapdesk_session_dev=s3cr3t-sesion; HttpOnly; Path=/; SameSite=Lax; Max-Age=28800";
const CONTEXT = "synapdesk_csrf_context_dev=s3cr3t-contexto; HttpOnly; Path=/; SameSite=Lax";
const DELETE = "synapdesk_session_dev=; HttpOnly; Path=/; SameSite=Lax; Max-Age=0";
const PROD_SESSION = "__Host-synapdesk_session=s3cr3t-prod; HttpOnly; Secure; Path=/; SameSite=Lax";
const PROD_CONTEXT = "__Host-synapdesk_csrf_context=s3cr3t-prod-ctx; HttpOnly; Secure; Path=/";
const OTHER = "tracker=s3cr3t-ajeno; Path=/";
const MIB = 1024 * 1024;

// Credencial de servicio de prueba: 32 bytes aleatorios en base64url (43 caracteres).
const CREDENTIAL = randomBytes(32).toString("base64url");

// ── Certificados generados por run.mjs (CA agregada solo a este proceso) ──
const tlsDir = process.env.PROXY_TEST_TLS_DIR;
if (!tlsDir) throw new Error("Ejecutar con npm run test:proxy (tests/proxy/run.mjs).");
const tls = (name) => ({
  key: readFileSync(path.join(tlsDir, `${name}.key`)),
  cert: readFileSync(path.join(tlsDir, `${name}.crt`)),
});

// ── Backend falso ──
let hits = 0;
let lastHeaders = {};
let lastRawHeaders = [];
let lastBodyLength = 0;
const responses = {
  "/api/v1/one": [SESSION],
  "/api/v1/two": [SESSION, CONTEXT],
  "/api/v1/mixed-unknown": [SESSION, OTHER],
  "/api/v1/mixed-profiles": [SESSION, PROD_SESSION, PROD_CONTEXT, CONTEXT],
  "/api/v1/many": [SESSION, OTHER, CONTEXT, "sin-signo-igual", PROD_SESSION],
  "/api/v1/delete": [DELETE],
  "/api/v1/duplicate": [SESSION, "synapdesk_session_dev=otro; Path=/"],
  "/api/v1/prod": [PROD_SESSION, SESSION, PROD_CONTEXT],
  // U+00A0 junto al nombre: no es la cookie autorizada aunque se parezca.
  "/api/v1/nbsp": [`\u00A0${SESSION}`, "synapdesk_session_dev\u00A0=x; Path=/", CONTEXT],
};
function handle(req, res) {
  hits += 1;
  lastHeaders = req.headers;
  lastRawHeaders = req.rawHeaders;
  const path = req.url.split("?")[0];
  let received = 0;
  req.on("data", (chunk) => (received += chunk.length));
  req.on("end", () => {
    lastBodyLength = received;
    if (path === "/api/v1/redirect") {
      res.writeHead(302, { Location: "https://evil.invalid/robar" }).end();
    } else if (path === "/api/v1/slow") {
      setTimeout(() => res.writeHead(200).end("{}"), 35_000).unref();
    } else if (path === "/api/v1/slow-body") {
      // Cabeceras de inmediato y cuerpo incompleto hasta después del plazo.
      res.writeHead(200, { "Content-Type": "application/json" });
      res.flushHeaders();
      res.write('{"parcial":');
      setTimeout(() => res.end("true}"), 35_000).unref();
    } else if (path === "/api/v1/cut-body") {
      res.writeHead(200, { "Content-Type": "application/json", "Content-Length": "100" });
      res.write('{"parcial":');
      setTimeout(() => res.destroy(), 50).unref();
    } else if (path === "/api/v1/huge") {
      // Respuesta mayor que el tope de 5 MiB.
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(Buffer.alloc(6 * MIB, 0x20));
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
    } else if (path === "/api/v1/search") {
      res.writeHead(200, { "Content-Type": "application/json", "Set-Cookie": [SESSION] });
      res.end(JSON.stringify({ status: "no_documents", items: [] }));
    } else if (path === "/api/v1/echo") {
      res.writeHead(200, { "Content-Type": "application/json" }).end(JSON.stringify(req.headers));
    } else {
      res.writeHead(200, {
        "Content-Type": "application/json",
        "Set-Cookie": responses[path] ?? [],
      });
      res.end("{}");
    }
  });
}
const servers = [];
async function listen(name, handler = handle) {
  const server = https.createServer(tls(name), handler);
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  servers.push(server);
  return `https://127.0.0.1:${server.address().port}`;
}
let backendUrl;
let otherNameUrl;
let foreignCaUrl;
let closedUrl;

// ── Registros: ningún valor de cookie ni la credencial deben aparecer ──
const logs = [];
const original = { error: console.error, warn: console.warn };

let proxy;
let ssr;
let api;

before(async () => {
  backendUrl = await listen("servidor");
  otherNameUrl = await listen("servidor-otro-nombre");
  foreignCaUrl = await listen("servidor-ca-ajena");
  const closed = https.createServer(tls("servidor"));
  await new Promise((r) => closed.listen(0, "127.0.0.1", r));
  closedUrl = `https://127.0.0.1:${closed.address().port}`;
  await new Promise((r) => closed.close(r));
  console.error = (...a) => logs.push(a.join(" "));
  console.warn = (...a) => logs.push(a.join(" "));
  proxy = await import("@/lib/backend-proxy");
  ssr = await import("@/lib/transport/server");
  ({ api } = await import("@/lib/api"));
});
after(() => {
  Object.assign(console, original);
  for (const server of servers) server.close();
  assert.ok(!logs.join("\n").includes(CREDENTIAL), "la credencial nunca aparece en los registros");
});
beforeEach(() => {
  process.env.BACKEND_INTERNAL_URL = backendUrl;
  process.env.AUTH_COOKIE_PROFILE = "local";
  process.env.BACKEND_SERVICE_CREDENTIAL = CREDENTIAL;
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
  const text = await response.text();
  assert.ok(!text.includes(CREDENTIAL), "sin la credencial en la respuesta");
  assert.ok(!text.includes("127.0.0.1"), "sin direcciones internas");
  const body = JSON.parse(text);
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
    const text = JSON.stringify(error);
    assert.ok(!text.includes("127.0.0.1"), "sin direcciones internas");
    assert.ok(!text.includes(CREDENTIAL), "sin la credencial");
    return error.error.requestId;
  }
  assert.fail("se esperaba un error");
}

// Cuántas veces llegó una cabecera al backend (rawHeaders conserva las repeticiones).
const rawCount = (name) =>
  lastRawHeaders.filter((value, index) => index % 2 === 0 && value.toLowerCase() === name).length;

// ── SEC-01B: credencial de servicio ──
describe("1. Credencial de servicio (SEC-01B)", () => {
  test("proxy: exactamente una Authorization con la credencial del servidor", async () => {
    await call("echo", { headers: { authorization: "Bearer del-navegador" } });
    assert.equal(rawCount("authorization"), 1);
    assert.equal(lastHeaders.authorization, `Bearer ${CREDENTIAL}`);
  });
  test("SSR: exactamente una Authorization con la credencial del servidor", async () => {
    await api.get("/echo", { Authorization: "Bearer inyectada" });
    assert.equal(rawCount("authorization"), 1);
    assert.equal(lastHeaders.authorization, `Bearer ${CREDENTIAL}`);
  });
  test("la credencial no vuelve al navegador", async () => {
    const response = await call("one");
    const raw = [...response.headers].map(([k, v]) => `${k}: ${v}`).join("\n");
    assert.ok(!raw.includes(CREDENTIAL) && !(await response.text()).includes(CREDENTIAL));
  });
  const invalid = {
    ausente: undefined,
    vacía: "",
    "42 caracteres": CREDENTIAL.slice(0, 42),
    "44 caracteres": `${CREDENTIAL}A`,
    "con relleno =": `${CREDENTIAL.slice(0, 42)}=`,
    "base64 estándar (+ y /)": `${"+/".repeat(21)}A`,
    "no canónica (último carácter)": `${CREDENTIAL.slice(0, 42)}${CREDENTIAL.at(-1) === "B" ? "C" : "B"}`,
    "con espacios": ` ${CREDENTIAL}`,
  };
  for (const [name, value] of Object.entries(invalid)) {
    test(`credencial ${name}: 503 sin contactar al backend`, async () => {
      if (value === undefined) delete process.env.BACKEND_SERVICE_CREDENTIAL;
      else process.env.BACKEND_SERVICE_CREDENTIAL = value;
      logs.length = 0;
      const before = hits;
      await expectContractError(await call("one"), 503, "SERVICE_UNAVAILABLE");
      await expectThrownContractError(api.get("/one"));
      assert.equal(hits, before);
      assert.ok(logs.some((l) => l.includes("BACKEND_SERVICE_CREDENTIAL")));
      if (value) assert.ok(!logs.join("\n").includes(value), "sin el valor en el registro");
    });
  }
});

// ── Destino: BACKEND_INTERNAL_URL estricta y HTTPS verificado ──
describe("2. Destino y TLS", () => {
  const port = () => new URL(backendUrl).port;
  const hostile = () => ({
    "http en claro": `http://127.0.0.1:${port()}`,
    "con usuario y contraseña": `https://u:p@127.0.0.1:${port()}`,
    "con ruta": `https://127.0.0.1:${port()}/api`,
    "con query": `https://127.0.0.1:${port()}?x=1`,
    "con #": `https://127.0.0.1:${port()}#a`,
    "otro esquema": `ftp://127.0.0.1:${port()}`,
    "no es URL": "127.0.0.1:8000",
  });
  test("origen https exacto, con o sin / final", () => {
    process.env.BACKEND_INTERNAL_URL = `${backendUrl}/`;
    assert.equal(proxy.getBackendOrigin(), backendUrl);
  });
  // Los nombres se fijan aquí; las URL se calculan dentro de cada prueba, cuando ya existe el
  // servidor de prueba.
  const hostileNames = [
    "http en claro",
    "con usuario y contraseña",
    "con ruta",
    "con query",
    "con #",
    "otro esquema",
    "no es URL",
  ];
  for (const name of hostileNames) {
    test(`URL ${name}: 503 sin contactar al backend`, async () => {
      process.env.BACKEND_INTERNAL_URL = hostile()[name];
      const before = hits;
      await expectContractError(await call("one"), 503, "SERVICE_UNAVAILABLE");
      await expectThrownContractError(api.get("/one"));
      assert.equal(hits, before);
    });
  }
  test("CA no confiada: 503 en proxy y SSR", async () => {
    process.env.BACKEND_INTERNAL_URL = foreignCaUrl;
    await expectContractError(await call("echo"), 503, "SERVICE_UNAVAILABLE");
    await expectThrownContractError(api.get("/echo"));
  });
  test("certificado con otro nombre: 503 en proxy y SSR", async () => {
    process.env.BACKEND_INTERNAL_URL = otherNameUrl;
    await expectContractError(await call("echo"), 503, "SERVICE_UNAVAILABLE");
    await expectThrownContractError(api.get("/echo"));
  });
  test("con CA y nombre válidos responde el backend", async () => {
    assert.equal((await call("one")).status, 200);
  });
});

test("la ruta específica de búsqueda comparte SEC-01B y conserva sus validaciones", async (t) => {
  const { POST } = await import("@/app/api/v1/search/route");
  const origin = "https://desk.invalid";
  const previousOrigin = process.env.SEARCH_PUBLIC_ORIGIN;
  process.env.SEARCH_PUBLIC_ORIGIN = origin;
  t.after(() => {
    if (previousOrigin === undefined) delete process.env.SEARCH_PUBLIC_ORIGIN;
    else process.env.SEARCH_PUBLIC_ORIGIN = previousOrigin;
  });
  const search = (extra = {}) =>
    POST(
      new Request(`${origin}/api/v1/search`, {
        method: "POST",
        body: JSON.stringify({ query: "DNS", limit: 3 }),
        headers: {
          Origin: origin,
          Cookie: "tracker=otro; synapdesk_session_dev=credencial-sesion",
          "Content-Type": "application/json",
          "X-CSRF-Token": "token-de-prueba",
          Authorization: "Bearer enviado-por-navegador",
          "X-Forwarded-For": "127.0.0.1",
          ...extra,
        },
      })
    );

  const beforeSearch = hits;
  const response = await search();
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { status: "no_documents", items: [] });
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.equal(response.headers.get("set-cookie"), null);
  assert.equal(lastHeaders.authorization, `Bearer ${CREDENTIAL}`);
  assert.equal(lastHeaders.cookie, "synapdesk_session_dev=credencial-sesion");
  assert.equal(lastHeaders.origin, origin);
  assert.equal(lastHeaders["x-csrf-token"], "token-de-prueba");
  assert.equal(lastHeaders["x-forwarded-for"], undefined);
  assert.equal((await search({ Cookie: "" })).status, 401);
  assert.equal((await search({ Origin: "https://other.invalid" })).status, 403);
  assert.equal((await search({ "X-CSRF-Token": "" })).status, 403);
  for (const url of [otherNameUrl, foreignCaUrl]) {
    process.env.BACKEND_INTERNAL_URL = url;
    assert.equal((await search()).status, 503);
  }
  assert.equal(hits, beforeSearch + 1);
});

// ── AUTH_COOKIE_PROFILE obligatoria ──
describe("3. AUTH_COOKIE_PROFILE", () => {
  test("local: Set-Cookie de desarrollo", () => {
    assert.deepEqual(
      [...proxy.allowedCookieNames()],
      ["synapdesk_session_dev", "synapdesk_csrf_context_dev"]
    );
  });
  test("production: Set-Cookie __Host-", () => {
    process.env.AUTH_COOKIE_PROFILE = "production";
    assert.deepEqual(
      [...proxy.allowedCookieNames()],
      ["__Host-synapdesk_session", "__Host-synapdesk_csrf_context"]
    );
  });
  for (const value of [undefined, "productionn", "", "Production", " local", "dev"]) {
    test(`valor ${value === undefined ? "ausente" : JSON.stringify(value)}: sin perfil`, () => {
      if (value === undefined) delete process.env.AUTH_COOKIE_PROFILE;
      else process.env.AUTH_COOKIE_PROFILE = value;
      assert.equal(proxy.allowedCookieNames(), null);
    });
  }
  test("perfil ausente: 503 en proxy y SSR, sin contactar al backend", async () => {
    delete process.env.AUTH_COOKIE_PROFILE;
    const before = hits;
    logs.length = 0;
    await expectContractError(await call("one"), 503, "SERVICE_UNAVAILABLE");
    await expectThrownContractError(ssr.getTransport());
    assert.equal(hits, before);
    assert.ok(logs.some((l) => l.includes("AUTH_COOKIE_PROFILE")));
  });
});

// ── Cookies hacia FastAPI: sin ocultar ni reparar (A04–A06) ──
describe("4. Cookies hacia el backend", () => {
  const sent = async (cookie) => {
    await call("echo", { headers: { cookie } });
    return lastHeaders.cookie;
  };
  test("A04: sesión sin '=' junto a contexto válido llega tal cual", async () => {
    assert.equal(
      await sent("synapdesk_session_dev; synapdesk_csrf_context_dev=ctx"),
      "synapdesk_session_dev; synapdesk_csrf_context_dev=ctx"
    );
  });
  test("A05: perfiles mezclados llegan los dos (el backend rechaza la mezcla)", async () => {
    assert.equal(
      await sent("synapdesk_session_dev=a; otra=1; __Host-synapdesk_csrf_context=b"),
      "synapdesk_session_dev=a; __Host-synapdesk_csrf_context=b"
    );
  });
  test("A05: también con el perfil production activo", async () => {
    process.env.AUTH_COOKIE_PROFILE = "production";
    assert.equal(
      await sent("__Host-synapdesk_session=p; synapdesk_session_dev=d"),
      "__Host-synapdesk_session=p; synapdesk_session_dev=d"
    );
  });
  const unchanged = {
    "repetida idéntica": "synapdesk_session_dev=a; synapdesk_session_dev=a",
    "repetida distinta": "synapdesk_session_dev=a; synapdesk_session_dev=b",
    vacía: "synapdesk_session_dev=",
    "con comillas": 'synapdesk_session_dev="a"',
    "con %codificación": "synapdesk_session_dev=%ZZ",
  };
  for (const [name, cookie] of Object.entries(unchanged)) {
    test(`A06: ${name} llega sin cambios`, async () => {
      assert.equal(await sent(cookie), cookie);
    });
  }
  test("las cookies no reservadas no se reenvían", async () => {
    assert.equal(await sent("otra=1; tracker=2"), undefined);
  });
  // Solo espacio y tabulador son separadores: U+00A0 no se recorta (antes trim() lo quitaba y la
  // cookie no canónica llegaba limpia, como si fuera la reservada).
  test("U+00A0 antes del nombre: no se confunde con la reservada ni llega limpia", async () => {
    assert.equal(await sent("\u00A0synapdesk_session_dev=abc"), undefined);
    assert.equal(
      await sent("\u00A0synapdesk_session_dev=x; synapdesk_csrf_context_dev=ctx"),
      "synapdesk_csrf_context_dev=ctx"
    );
  });
  test("U+00A0 entre el nombre y el '=': no es la cookie reservada", async () => {
    assert.equal(await sent("synapdesk_session_dev\u00A0=abc"), undefined);
  });
  test("U+00A0 al final del valor: la cookie reservada llega sin cambios", async () => {
    assert.equal(await sent("synapdesk_session_dev=abc\u00A0"), "synapdesk_session_dev=abc\u00A0");
  });
  test("espacios y tabuladores alrededor del ';' siguen siendo separadores", async () => {
    assert.equal(
      await sent("synapdesk_session_dev=a;\tsynapdesk_csrf_context_dev=b ;  otra=1"),
      "synapdesk_session_dev=a; synapdesk_csrf_context_dev=b"
    );
  });
  test("SSR: U+00A0 junto al nombre tampoco se recorta", async () => {
    globalThis.__requestCookie =
      "\u00A0synapdesk_session_dev=a; synapdesk_session_dev\u00A0=b; synapdesk_csrf_context_dev=ctx";
    await api.get("/echo");
    assert.equal(lastHeaders.cookie, "synapdesk_csrf_context_dev=ctx");
  });
  // Otros espacios Unicode no pueden viajar en una cabecera HTTP (Node rechaza valores sobre
  // U+00FF); igual se comprueba el filtro directamente, como defensa adicional.
  test("filtro: U+2003, U+3000 y U+FEFF junto al nombre no se recortan", () => {
    assert.equal(
      proxy.filterCookieHeader(
        "\u2003synapdesk_session_dev=a; \u3000synapdesk_session_dev=b; \uFEFFsynapdesk_session_dev=c"
      ),
      null
    );
    assert.equal(
      proxy.filterCookieHeader("\uFEFFsynapdesk_session_dev=a; synapdesk_csrf_context_dev=ctx"),
      "synapdesk_csrf_context_dev=ctx"
    );
  });
  test("SSR reenvía las cookies reservadas de la petición, también las ambiguas", async () => {
    globalThis.__requestCookie =
      "synapdesk_session_dev; otra=b; __Host-synapdesk_session=c; synapdesk_session_dev=d";
    await api.get("/echo");
    assert.equal(
      lastHeaders.cookie,
      "synapdesk_session_dev; __Host-synapdesk_session=c; synapdesk_session_dev=d"
    );
  });
});

// ── Set-Cookie hacia el navegador ──
describe("5. Set-Cookie del backend", () => {
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
  test("U+00A0 junto al nombre en Set-Cookie: no pasa como autorizada", async () => {
    assert.deepEqual(cookiesOf(await call("nbsp")), [CONTEXT]);
  });
  test("cookie autorizada repetida: pasan ambas, sin normalizar", async () => {
    assert.equal(cookiesOf(await call("duplicate")).length, 2);
  });
  test("las descartadas solo se cuentan en el registro: sin nombres ni valores", async () => {
    logs.length = 0;
    const response = await call("many");
    const raw = [...response.headers].map(([k, v]) => `${k}: ${v}`).join("\n");
    assert.ok(
      !raw.includes("tracker") && !raw.includes("__Host-") && !raw.includes("sin-signo-igual")
    );
    const log = logs.join("\n");
    assert.match(log, /Se descartaron 3 Set-Cookie/);
    assert.ok(!log.includes("tracker") && !log.includes("s3cr3t"));
  });
});

// ── Errores, correlación y no-store ──
describe("6. Errores del proxy y del SSR", () => {
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
  test("SSR no envía Origin", async () => {
    await api.get("/echo");
    assert.equal(lastHeaders.origin, undefined);
  });
});

// ── Tamaños: petición y respuesta acotadas (A13) ──
describe("7. Límites de tamaño", () => {
  test("petición de más de 1 MiB: 413 sin contactar al backend", async () => {
    const before = hits;
    await expectContractError(
      await call("echo", { method: "POST", body: Buffer.alloc(MIB + 1, 0x61) }),
      413,
      "VALIDATION_ERROR"
    );
    assert.equal(hits, before);
  });
  test("Content-Length declarado mayor que el límite: 413 sin leer el cuerpo", async () => {
    const before = hits;
    await expectContractError(
      await call("echo", {
        method: "POST",
        body: "{}",
        headers: { "content-length": String(MIB + 1) },
      }),
      413,
      "VALIDATION_ERROR"
    );
    assert.equal(hits, before);
  });
  test("petición de exactamente 1 MiB: llega completa", async () => {
    const response = await call("size", { method: "POST", body: Buffer.alloc(MIB, 0x61) });
    assert.equal(response.status, 200);
    assert.equal(lastBodyLength, MIB);
  });
  test("respuesta de más de 5 MiB: 503 en proxy y SSR", async () => {
    await expectContractError(await call("huge"), 503, "SERVICE_UNAVAILABLE");
    await expectThrownContractError(api.get("/huge"));
  });
  test(
    "cuerpo de la petición que no termina: 503 al vencer el plazo, sin contactar al backend",
    { timeout: 40_000 },
    async () => {
      const before = hits;
      const start = Date.now();
      const stream = new ReadableStream({
        start(controller) {
          controller.enqueue(new TextEncoder().encode('{"parcial":'));
        },
      });
      await expectContractError(
        await call("echo", { method: "POST", body: stream, duplex: "half" }),
        503,
        "SERVICE_UNAVAILABLE"
      );
      assert.ok(Date.now() - start >= 29_500, "espera el plazo completo");
      assert.equal(hits, before);
    }
  );
});

// ── Plazo de 30 s: cabeceras y cuerpo de la respuesta ──
describe("8. Plazo de 30 s", () => {
  test("proxy: sin respuesta → 503 con requestId", { timeout: 40_000 }, async () => {
    const start = Date.now();
    await expectContractError(await call("slow"), 503, "SERVICE_UNAVAILABLE");
    assert.ok(Date.now() - start >= 29_500);
  });
  test("SSR: sin respuesta → error con requestId", { timeout: 40_000 }, async () => {
    const start = Date.now();
    await expectThrownContractError(api.get("/slow"));
    assert.ok(Date.now() - start >= 29_500);
  });
  test("proxy: cabeceras 200 y cuerpo demorado → 503", { timeout: 40_000 }, async () => {
    const start = Date.now();
    await expectContractError(await call("slow-body"), 503, "SERVICE_UNAVAILABLE");
    assert.ok(Date.now() - start >= 29_500, "espera el plazo completo");
  });
  test("SSR: cabeceras 200 y cuerpo demorado → error", { timeout: 40_000 }, async () => {
    const start = Date.now();
    await expectThrownContractError(api.get("/slow-body"));
    assert.ok(Date.now() - start >= 29_500, "espera el plazo completo");
  });
  test("proxy: conexión cortada a mitad del cuerpo → 503", async () => {
    await expectContractError(await call("cut-body"), 503, "SERVICE_UNAVAILABLE");
  });
  test("SSR: conexión cortada a mitad del cuerpo → error", async () => {
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
        "x-request-id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      },
    });
    assert.equal(lastHeaders.origin, "http://localhost:3000");
    assert.equal(lastHeaders["x-csrf-token"], "tok");
    for (const h of [
      "x-forwarded-for",
      "x-real-ip",
      "x-synapdesk-client-ip",
      "forwarded",
      "x-request-id",
    ]) {
      assert.equal(lastHeaders[h], undefined, h);
    }
  });
  test("Origin duplicado llega tal cual (sin elegir un valor)", async () => {
    const headers = new Headers();
    headers.append("origin", "http://localhost:3000");
    headers.append("origin", "http://evil.invalid");
    await call("echo", { method: "POST", body: "{}", headers });
    assert.equal(lastHeaders.origin, "http://localhost:3000, http://evil.invalid");
  });
  test("todas las respuestas llevan no-store", async () => {
    assert.equal((await call("one")).headers.get("cache-control"), "no-store");
  });
});
