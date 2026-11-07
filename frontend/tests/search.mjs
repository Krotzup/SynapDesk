import { test } from "node:test";
import assert from "node:assert/strict";
import proxy from "../artifacts/search-tests/lib/server/search-proxy.js";
import contract from "../artifacts/search-tests/lib/search-contract.js";
const { forwardSemanticSearch } = proxy;
const { parseSearchResponse, safeSourceUrl, emptySearchMessage } = contract;
const config = {
  backendUrl: "https://backend.invalid",
  publicOrigin: "https://desk.invalid",
  sessionCookieName: "test_session",
};
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
      Cookie: `analytics=ignored; test_session=${sid}`,
      "X-CSRF-Token": "synthetic-token",
      ...headers,
    },
    body: JSON.stringify(body),
  });
}

test("empty states are distinct and source URLs reject credentials and executable schemes", () => {
  assert.notEqual(
    emptySearchMessage("no_documents").title,
    emptySearchMessage("insufficient_information").title
  );
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
  assert.equal(captured.options.headers.Cookie, `test_session=${sid}`);
  assert.equal(captured.options.headers.Authorization, undefined);
  assert.equal(captured.options.headers["X-Forwarded-For"], undefined);
  assert.equal(captured.options.redirect, "error");
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
    [{ Cookie: `test_session=${sid}; test_session=${sid}` }, 401],
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

test("only configured HTTPS or explicitly allowed loopback HTTP destinations are accepted", async () => {
  const send = async () => Response.json({ status: "no_documents", items: [] });
  for (const backendUrl of [
    "http://remote.invalid",
    "https://user:secret@backend.invalid",
    "https://backend.invalid/other",
    "https://backend.invalid/?target=other",
  ]) {
    assert.equal(
      (await forwardSemanticSearch(request(), { ...config, backendUrl }, send)).status,
      503
    );
  }
  assert.equal(
    (
      await forwardSemanticSearch(
        request(),
        { ...config, backendUrl: "http://127.0.0.1:8000", allowHttpLocal: true },
        send
      )
    ).status,
    200
  );
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
  for (const [cookieProfile, name] of [
    ["local", "synapdesk_session_dev"],
    ["production", "__Host-synapdesk_session"],
  ]) {
    const cookie = `${name}=${sid}`;
    const profiledRequest = () =>
      request(undefined, { Cookie: `${cookie}; synapdesk_csrf_context_dev=ignored` });
    const profileConfig = { ...config, sessionCookieName: undefined, cookieProfile };
    const result = await forwardSemanticSearch(
      profiledRequest(),
      profileConfig,
      async (_, init) => {
        assert.equal(init.headers.Cookie, cookie);
        return Response.json({ status: "no_documents", items: [] });
      }
    );
    assert.equal(result.status, 200);
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
