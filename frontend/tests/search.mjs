import { test } from "node:test";
import assert from "node:assert/strict";
import { api } from "../src/lib/api.ts";
import { forwardSemanticSearch as search } from "../src/lib/server/search-proxy.ts";
import {
  parseSearchResponse,
  safeSourceUrl,
  emptySearchMessage,
  groupSearchResults,
} from "../src/lib/search-contract.ts";
const config = {
  backendUrl: "https://backend.invalid",
  publicOrigin: "https://desk.invalid",
  cookieProfile: "local",
  serviceCredential: Buffer.alloc(32, 7).toString("base64url"),
};

async function forwardSemanticSearch(request, config, send = fetch) {
  const overrides = {
    BACKEND_INTERNAL_URL: config.backendUrl,
    AUTH_COOKIE_PROFILE: config.cookieProfile,
    BACKEND_SERVICE_CREDENTIAL: config.serviceCredential,
  };
  const previous = Object.fromEntries(
    Object.keys(overrides).map((name) => [name, process.env[name]])
  );
  function assign(values) {
    for (const [name, value] of Object.entries(values)) {
      if (value === undefined) delete process.env[name];
      else process.env[name] = value;
    }
  }

  const originalFetch = globalThis.fetch;
  assign(overrides);
  globalThis.fetch = send;
  try {
    return await search(request, config);
  } finally {
    globalThis.fetch = originalFetch;
    assign(previous);
  }
}
const sid = "A".repeat(43);
const item = {
  documentId: "11111111-1111-4111-8111-111111111111",
  documentChunkId: "22222222-2222-4222-8222-222222222222",
  title: "DNS",
  excerpt: "Revise el servidor.",
  score: 0.7,
  sourceUrl: "https://learn.microsoft.com/es-es/",
  language: "es",
};
function request(body = { query: "DNS", limit: 5 }, headers = {}) {
  return new Request("https://desk.invalid/api/v1/search", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Origin: "https://desk.invalid",
      Cookie: `analytics=ignored; synapdesk_session_dev=${sid}`,
      "X-CSRF-Token": "synthetic-token",
      ...headers,
    },
    body: JSON.stringify(body),
  });
}

test("empty states are distinct and source URLs reject credentials and executable schemes", () => {
  const noDocuments = emptySearchMessage("no_documents");
  const insufficientInformation = emptySearchMessage("insufficient_information");
  assert.equal(noDocuments.title, "La base de conocimientos está vacía");
  assert.equal(insufficientInformation.title, "Información insuficiente");
  assert.match(insufficientInformation.message, /el mensaje de error.*vuelve a buscar/);
  assert.equal(
    safeSourceUrl("https://learn.microsoft.com/es-es/"),
    "https://learn.microsoft.com/es-es/"
  );
  for (const value of [
    "javascript:alert(1)",
    "https://secret@site.invalid/",
    "http://site.invalid",
    "https://site.invalid/a b",
  ])
    assert.equal(safeSourceUrl(value), null);
});

test("response contract rejects inconsistent states, scores, IDs and unsafe sources", () => {
  assert.deepEqual(parseSearchResponse({ status: "results", items: [item] }).items, [item]);
  for (const value of [
    { status: "results", items: [] },
    { status: "no_documents", items: [item] },
    { status: "unknown", items: [] },
    ...[NaN, Infinity, 1.5].map((score) => ({ status: "results", items: [{ ...item, score }] })),
    { status: "results", items: [{ ...item, documentId: "invalid" }] },
    { status: "results", items: [{ ...item, sourceUrl: "javascript:alert(1)" }] },
  ])
    assert.throws(() => parseSearchResponse(value));
});

test("fixed same-origin proxy forwards only session, origin and CSRF without redirects or shared cache", async () => {
  let captured;
  const response = await forwardSemanticSearch(
    request(undefined, {
      Authorization: "must-not-forward",
      "X-Forwarded-For": "must-not-forward",
    }),
    config,
    async (url, options) => {
      captured = { url, options };
      return Response.json(
        { status: "results", items: [item] },
        { headers: { "Set-Cookie": "must-not-forward=1" } }
      );
    }
  );
  assert.equal(response.status, 200);
  assert.equal(captured.url, "https://backend.invalid/api/v1/search");
  assert.equal(captured.options.headers.get("cookie"), `synapdesk_session_dev=${sid}`);
  assert.equal(captured.options.headers.get("authorization"), `Bearer ${config.serviceCredential}`);
  assert.equal(captured.options.headers.get("x-forwarded-for"), null);
  assert.equal(captured.options.redirect, "manual");
  assert.equal(captured.options.cache, "no-store");
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.equal(response.headers.get("set-cookie"), null);
});

test("ambiguous cookies, invalid origin and missing CSRF are rejected before contacting backend", async () => {
  let calls = 0;
  const send = async () => {
    calls++;
    throw new Error();
  };
  for (const [headers, status] of [
    [{ Cookie: `synapdesk_session_dev=${sid}; synapdesk_session_dev=${sid}` }, 401],
    [{ Cookie: "synapdesk_session_dev=" }, 401],
    [{ Cookie: "synapdesk_session_dev=one,two" }, 401],
    [{ Cookie: "other=value" }, 401],
    [{ Origin: "https://evil.invalid" }, 403],
    [{ "X-CSRF-Token": "" }, 403],
  ])
    assert.equal(
      (await forwardSemanticSearch(request(undefined, headers), config, send)).status,
      status
    );
  assert.equal(calls, 0);
});

test("valid cookie pairs preserve the credential without forwarding unrelated cookies", async () => {
  const cookie = `synapdesk_session_dev=${sid}`;
  const response = await forwardSemanticSearch(
    request(undefined, { Cookie: `analytics=ignored; \t${cookie}; unrelated=value` }),
    config,
    async (_, init) => {
      assert.equal(init.headers.get("cookie"), cookie);
      return Response.json({ status: "no_documents", items: [] });
    }
  );
  assert.equal(response.status, 200);
});

test("malformed auth cookies are rejected without normalizing or dropping them", async () => {
  for (const cookie of [
    `synapdesk_session_dev=${sid} ; analytics=ignored`,
    `synapdesk_session_dev=${sid}; synapdesk_session_dev =${sid}`,
    `synapdesk_session_dev=${sid}; synapdesk_session_dev`,
    `synapdesk_session_dev="${sid}"`,
    `synapdesk_session_dev=${sid}=`,
  ]) {
    const response = await forwardSemanticSearch(
      request(undefined, { Cookie: cookie }),
      config,
      async () => assert.fail("Una cookie malformada no debe reenviarse")
    );
    assert.equal(response.status, 401);
    assert.equal((await response.json()).error.code, "AUTHENTICATION_REQUIRED");
  }
});

test("a rejected search POST stays rejected and a manual retry gets a fresh CSRF token", async (t) => {
  const originalWindow = Object.getOwnPropertyDescriptor(globalThis, "window");
  Object.defineProperty(globalThis, "window", { configurable: true, value: {} });
  t.after(() => {
    if (originalWindow) Object.defineProperty(globalThis, "window", originalWindow);
    else delete globalThis.window;
  });
  t.mock.method(globalThis, "BroadcastChannel", function () {
    return {};
  });
  const attempts = [];
  let tokenRequests = 0;
  const error = {
    error: { code: "CSRF_INVALID", message: "Token rechazado.", details: null, requestId: "" },
  };
  t.mock.method(globalThis, "fetch", async (url, options) => {
    attempts.push([options.method, url, options.headers["X-CSRF-Token"]]);
    if (url === "/api/v1/auth/csrf") {
      return Response.json({
        csrfToken: `token-${++tokenRequests}`,
        expiresAt: new Date(Date.now() + 600_000).toISOString(),
      });
    }
    return attempts.length === 2
      ? Response.json(error, { status: 403 })
      : Response.json({ status: "no_documents", items: [] });
  });
  const submit = () => api.post("/search", { query: "DNS" });
  await assert.rejects(submit(), (actual) => {
    assert.deepEqual(actual, error);
    return true;
  });
  assert.deepEqual(attempts, [
    ["GET", "/api/v1/auth/csrf", undefined],
    ["POST", "/api/v1/search", "token-1"],
  ]);
  assert.deepEqual(await submit(), { status: "no_documents", items: [] });
  assert.deepEqual(attempts.slice(2), [
    ["GET", "/api/v1/auth/csrf", undefined],
    ["POST", "/api/v1/search", "token-2"],
  ]);
});

test("rate limiting preserves only valid Retry-After values and sanitizes the body", async () => {
  for (const [retryAfter, expected] of [
    ["30", "30"],
    ["0", "0"],
    ["Wed, 21 Oct 2037 07:28:00 GMT", "Wed, 21 Oct 2037 07:28:00 GMT"],
    ["Invalid Date", null],
    ["private-credentials", null],
  ]) {
    const response = await forwardSemanticSearch(request(), config, async () =>
      Response.json(
        { error: { code: "RATE_LIMITED", message: "private-credentials" } },
        { status: 429, headers: { "Retry-After": retryAfter, "Set-Cookie": "private=1" } }
      )
    );
    assert.equal(response.status, 429);
    assert.equal(response.headers.get("retry-after"), expected);
    assert.equal(response.headers.get("cache-control"), "no-store");
    assert.equal(response.headers.get("set-cookie"), null);
    const body = await response.json();
    assert.equal(body.error.code, "RATE_LIMITED");
    if (retryAfter === "30") assert.match(body.error.message, /30 segundos/);
    else if (retryAfter === "0" || expected === null)
      assert.doesNotMatch(body.error.message, /segundos?/);
    assert.ok(!JSON.stringify(body).includes("private-credentials"));
  }
});

test("results group by document and Spanish preference preserves every fragment and score", () => {
  const english = { ...item, language: "en" };
  const spanish = {
    ...item,
    documentId: "33333333-3333-4333-8333-333333333333",
    documentChunkId: "44444444-4444-4444-8444-444444444444",
    language: "es-CL",
    score: 0.65,
  };
  const secondEnglish = {
    ...english,
    documentChunkId: "55555555-5555-4555-8555-555555555555",
    score: 0.6,
  };
  const items = [english, spanish, secondEnglish];
  const groups = groupSearchResults(items);
  assert.deepEqual(
    groups.map((group) => group.fragments),
    [[english, secondEnglish], [spanish]]
  );
  assert.deepEqual(
    groupSearchResults(items, true).map((group) => group.fragments),
    [[spanish], [english, secondEnglish]]
  );
  assert.deepEqual(items, [english, spanish, secondEnglish]);
});

test("SEC-01B requires HTTPS and a canonical server credential before contacting FastAPI", async () => {
  let calls = 0;
  const send = async () => {
    calls++;
    return Response.json({ status: "no_documents", items: [] });
  };
  for (const backendUrl of [
    "http://remote.invalid",
    "http://127.0.0.1:8000",
    "https://user:secret@backend.invalid",
    "https://backend.invalid/other",
    "https://backend.invalid/?target=other",
  ]) {
    assert.equal(
      (await forwardSemanticSearch(request(), { ...config, backendUrl }, send)).status,
      503
    );
  }
  for (const serviceCredential of [undefined, "malformed", "B".repeat(43)]) {
    const response = await forwardSemanticSearch(request(), { ...config, serviceCredential }, send);
    assert.equal(response.status, 503);
    assert.equal(response.headers.get("cache-control"), "no-store");
  }
  assert.equal(calls, 0);
});

test("invalid or excessive requests do not echo their contents", async () => {
  for (const body of [
    { query: "private-sensitive".repeat(1000) },
    { query: "red", limit: true },
    { query: "red", limit: 21 },
    { query: "red", target: "private-sensitive" },
  ]) {
    const response = await forwardSemanticSearch(request(body), config, async () => {
      throw new Error("must not call");
    });
    assert.equal(response.status, 422);
    assert.ok(!(await response.text()).includes("private-sensitive"));
  }
});

test("search keeps its 8192-byte input limit and rejects malformed UTF-8", async () => {
  const body = '{"query":"DNS"}';
  const headers = request().headers;
  const withBody = (payload) =>
    new Request("https://desk.invalid/api/v1/search", { method: "POST", headers, body: payload });
  let calls = 0;
  const send = async () => {
    calls++;
    return Response.json({ status: "no_documents", items: [] });
  };

  const exact = body.padEnd(8192);
  assert.equal((await forwardSemanticSearch(withBody(exact), config, send)).status, 200);
  assert.equal((await forwardSemanticSearch(withBody(exact + " "), config, send)).status, 422);
  const malformed = Uint8Array.from([...new TextEncoder().encode('{"query":"'), 0xff, 34, 125]);
  assert.equal((await forwardSemanticSearch(withBody(malformed), config, send)).status, 422);
  assert.equal(calls, 1);
});

test("upstream errors and network failures never expose provider messages or private data", async () => {
  const failed = await forwardSemanticSearch(request(), config, async () => {
    throw new Error("private-credentials");
  });
  assert.equal(failed.status, 503);
  const failure = await failed.json();
  assert.equal(failure.error.code, "SERVICE_UNAVAILABLE");
  assert.ok(!JSON.stringify(failure).includes("private-credentials"));
  const stale = await forwardSemanticSearch(request(), config, async () =>
    Response.json(
      {
        error: {
          code: "SEARCH_PROFILE_STALE",
          message: "private-credentials",
          details: "private-credentials",
        },
      },
      { status: 503 }
    )
  );
  assert.equal(stale.status, 503);
  const body = await stale.json();
  assert.equal(body.error.code, "SEARCH_PROFILE_STALE");
  assert.ok(!JSON.stringify(body).includes("private-credentials"));
});

test("cookie profiles match the shared proxy and reject conflicting settings", async () => {
  for (const [cookieProfile, name, context, otherContext] of [
    [
      "local",
      "synapdesk_session_dev",
      "synapdesk_csrf_context_dev",
      "__Host-synapdesk_csrf_context",
    ],
    [
      "production",
      "__Host-synapdesk_session",
      "__Host-synapdesk_csrf_context",
      "synapdesk_csrf_context_dev",
    ],
  ]) {
    const cookie = `${name}=${sid}`;
    const profiledRequest = () => request(undefined, { Cookie: `${cookie}; ${context}=${sid}` });
    const profileConfig = { ...config, sessionCookieName: undefined, cookieProfile };
    const result = await forwardSemanticSearch(
      profiledRequest(),
      profileConfig,
      async (_, init) => {
        assert.equal(init.headers.get("cookie"), cookie);
        return Response.json({ status: "no_documents", items: [] });
      }
    );
    assert.equal(result.status, 200);
    const mixed = await forwardSemanticSearch(
      request(undefined, { Cookie: `${cookie}; ${otherContext}=${sid}` }),
      profileConfig,
      async () => assert.fail("No debe reenviar perfiles mezclados")
    );
    assert.equal(mixed.status, 401);
    const incompatible = await forwardSemanticSearch(
      profiledRequest(),
      { ...profileConfig, sessionCookieName: "different_session" },
      async () => assert.fail("La configuración incompatible no debe reenviar la petición")
    );
    assert.equal(incompatible.status, 503);
  }
});

test("valid empty statuses are preserved through the proxy", async () => {
  for (const status of ["no_documents", "insufficient_information"]) {
    const response = await forwardSemanticSearch(request(), config, async () =>
      Response.json({ status, items: [] })
    );
    assert.deepEqual(await response.json(), { status, items: [] });
  }
});
