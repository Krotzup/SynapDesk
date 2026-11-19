import assert from "node:assert/strict";
import { describe, test } from "node:test";
import { readinessStatus, serviceStatusLabels } from "@/lib/service-status";

const READY = { status: "ready", service: "synapdesk-backend", database: "ok" };
const apiError = (status, code) => ({
  status,
  error: { code, message: "x", details: null, requestId: "8d1f3c52-7a4e-4b9a-9c2d-5e6f7a8b9c0d" },
});

describe("readinessStatus (GET /api/v1/ready)", () => {
  test("200 con status ready y database ok: disponible", () => {
    assert.equal(readinessStatus({ ok: true, value: READY }), "available");
  });

  test("una respuesta 200 con otra forma no se da por disponible", () => {
    assert.equal(readinessStatus({ ok: true, value: { status: "ok" } }), "unreachable");
    assert.equal(readinessStatus({ ok: true, value: null }), "unreachable");
    assert.equal(
      readinessStatus({ ok: true, value: { ...READY, database: "error" } }),
      "unreachable"
    );
  });

  test("503 DATABASE_UNAVAILABLE: la API responde pero la base no", () => {
    assert.equal(
      readinessStatus({ ok: false, error: apiError(503, "DATABASE_UNAVAILABLE") }),
      "database-unavailable"
    );
  });

  test("otros errores (proxy, red o 503 genérico): sin conexión", () => {
    assert.equal(
      readinessStatus({ ok: false, error: apiError(503, "SERVICE_UNAVAILABLE") }),
      "unreachable"
    );
    assert.equal(
      readinessStatus({ ok: false, error: new TypeError("fetch failed") }),
      "unreachable"
    );
  });

  test("cada estado tiene su texto", () => {
    assert.deepEqual(Object.keys(serviceStatusLabels).sort(), [
      "available",
      "database-unavailable",
      "demo",
      "unreachable",
    ]);
  });
});
