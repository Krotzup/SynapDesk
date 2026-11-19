import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { render, screen } from "@testing-library/react";
import { ReviewMetrics } from "@/components/metrics/ReviewMetrics";
import { api } from "@/lib/api";
import { resetEnvironment, stubService } from "./helpers.mjs";

const originalFlag = process.env.AI_REVIEW_METRICS_ENABLED;
let stub;
afterEach(() => {
  stub?.restore();
  stub = undefined;
  if (originalFlag === undefined) delete process.env.AI_REVIEW_METRICS_ENABLED;
  else process.env.AI_REVIEW_METRICS_ENABLED = originalFlag;
  resetEnvironment();
});

test("HU10 apagada no consulta ni muestra conteos", async () => {
  delete process.env.AI_REVIEW_METRICS_ENABLED;
  stub = stubService(api, { get: async () => assert.fail("No debe consultar") });
  assert.equal(await ReviewMetrics(), null);
  assert.equal(stub.calls.get.length, 0);
});

test("HU10 muestra ceros y diferencia revisiones de exactitud y resolución", async () => {
  process.env.AI_REVIEW_METRICS_ENABLED = "true";
  stub = stubService(api, {
    get: async () => ({
      recommendationsAccepted: 0,
      recommendationsModified: 2,
      recommendationsRejected: 1,
    }),
  });
  render(await ReviewMetrics());
  assert.ok(screen.getByRole("heading", { name: "Revisiones de IA" }));
  for (const text of ["Aceptadas", "Modificadas", "Rechazadas", "0", "2", "1"])
    assert.ok(screen.getByText(text));
  assert.match(document.body.textContent, /No miden la exactitud/);
  assert.deepEqual(stub.calls.get, [["/metrics/recommendations"]]);
});

for (const data of [
  null,
  { recommendationsAccepted: -1 },
  { recommendationsAccepted: 0, recommendationsModified: 0, recommendationsRejected: "0" },
]) {
  test(`HU10 no transforma una respuesta inválida en cero: ${JSON.stringify(data)}`, async () => {
    process.env.AI_REVIEW_METRICS_ENABLED = "true";
    stub = stubService(api, { get: async () => data });
    render(await ReviewMetrics());
    assert.match(screen.getByRole("alert").textContent, /No se pudieron cargar/);
    assert.equal(screen.queryByText("0"), null);
  });
}
