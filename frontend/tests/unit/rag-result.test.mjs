import assert from "node:assert/strict";
import { test } from "node:test";
import { readRagResponse } from "../proxy/rag-result.mjs";

const response = (status, payload) => ({ status: () => status, json: async () => payload });

test("acepta la abstención 422 y conserva la cobertura de revisión pendiente", async () => {
  const { summary, validContract } = await readRagResponse(
    response(422, { error: { code: "INSUFFICIENT_INFORMATION", message: "dato privado" } }),
    { ragExpectedOutcome: "either" }
  );
  assert.equal(validContract, true);
  assert.equal(summary.outcome, "abstention");
  assert.equal(summary.expectedOutcome, "either");
  assert.equal(summary.reviewVerified, false);
  assert.equal(JSON.stringify(summary).includes("dato privado"), false);
});

test("201 conserva el borrador para verificar fuentes y revisión fuera del diagnóstico", async () => {
  const draft = { status: "pending", content: "paso con cita", sources: [{}] };
  const { summary, payload, validContract } = await readRagResponse(response(201, draft), {
    ragMode: "fixture",
  });
  assert.equal(validContract, true);
  assert.equal(summary.outcome, "draft");
  assert.equal(summary.mode, "fixture");
  assert.equal(payload, draft);
  assert.equal(JSON.stringify(summary).includes(draft.content), false);
});

for (const [status, code] of [
  [422, "QUERY_TOKEN_LIMIT_EXCEEDED"],
  [503, "GENERATION_UNAVAILABLE"],
  [503, "INSUFFICIENT_INFORMATION"],
  [422, "codigo-privado"],
]) {
  test(`rechaza HTTP ${status} con código ${code}`, async () => {
    const { summary, validContract } = await readRagResponse(
      response(status, { error: { code } }),
      {}
    );
    assert.equal(validContract, false);
    assert.equal(summary.outcome, "error");
    assert.equal(summary.status, status);
    assert.equal(summary.errorCode, code === "codigo-privado" ? "UNEXPECTED_ERROR" : code);
  });
}

test("conserva HTTP y rechaza una respuesta no JSON sin copiar la excepción", async () => {
  const { summary, validContract } = await readRagResponse(
    {
      status: () => 502,
      json: async () => {
        throw new SyntaxError("cuerpo privado");
      },
    },
    {}
  );
  assert.equal(validContract, false);
  assert.equal(summary.status, 502);
  assert.equal(summary.responseJsonValid, false);
  assert.equal(JSON.stringify(summary).includes("cuerpo privado"), false);
});

for (const payload of [null, [], "texto"]) {
  test(`rechaza cuerpo 201 con forma ${JSON.stringify(payload)}`, async () => {
    assert.equal((await readRagResponse(response(201, payload), {})).validContract, false);
  });
}
