import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { createElement, Fragment } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { RecommendationContent } from "@/components/recommendations/RecommendationContent";
import { RecommendationSources } from "@/components/recommendations/RecommendationSources";
import { AssistantRecommendation } from "@/components/recommendations/AssistantRecommendation";
import { TicketPrediction } from "@/components/tickets/TicketPrediction";
import { predictionsService } from "@/services/predictions";
import { recommendationsService } from "@/services/recommendations";
import { apiError, resetEnvironment, stubService } from "./helpers.mjs";

let stub;
afterEach(() => {
  stub?.restore();
  stub = undefined;
  resetEnvironment();
});

const refs = ["11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"];
const sources = refs.map((id, i) => ({
  documentId: id,
  documentChunkId: id,
  title: `Documento ${i + 1}`,
  excerpt: "Consultar DNS",
  score: 0.75,
}));

test("una cita con varios fragmentos abre la fuente correspondiente sin exponer UUID como etiqueta", () => {
  render(
    createElement(
      Fragment,
      null,
      createElement(RecommendationContent, {
        content: `Comprobar DNS [${refs.join(", ")}]`,
        sources,
        recommendationId: "r1",
      }),
      createElement(RecommendationSources, { sources, recommendationId: "r1" })
    )
  );
  const link = screen.getByRole("link", { name: "Consultar fuente 2: Documento 2" });
  assert.equal(link.textContent, "[Fuente 2]");
  const details = document.getElementById(`source-r1-${refs[1]}`);
  assert.equal(details.open, false);
  fireEvent.click(link);
  assert.equal(details.open, true);
  assert.equal(document.activeElement, details.querySelector("summary"));
});

test("una referencia desconocida permanece como texto y no inventa un enlace", () => {
  render(
    createElement(RecommendationContent, {
      content: `Paso [${refs[0]}]`,
      sources: [],
      recommendationId: "r1",
    })
  );
  assert.equal(screen.queryByRole("link"), null);
});

test("la predicción distingue tipo, categoría no mapeada y prioridad estimada", async () => {
  stub = stubService(predictionsService, {
    get: async () => ({
      predictedType: "incident",
      predictedCategory: null,
      predictedPriority: "high",
      predictedArea: null,
      modelName: "modelo",
      modelVersion: "v1",
      confidences: { type: 0.8, priority: 0.7, queue: 0.6 },
    }),
  });
  render(createElement(TicketPrediction, { ticketId: "t1" }));
  await screen.findByText("incident");
  assert.ok(screen.getByText("Alta"));
  assert.equal(screen.getAllByText("Sin correspondencia definida").length, 2);
  assert.match(document.body.textContent, /No cambia los valores del ticket/);
});

for (const [code, message] of [
  ["INSUFFICIENT_INFORMATION", /no alcanza para generar/],
  ["GENERATION_INVALID", /respuesta inválida/],
  ["GENERATION_UNAVAILABLE", /no está disponible temporalmente/],
  ["SEARCH_PROFILE_STALE", /base de conocimientos cambió/],
]) {
  test(`el asistente comunica ${code} sin mostrar un borrador`, async () => {
    stub = stubService(recommendationsService, {
      generate: async () => {
        throw apiError(code === "INSUFFICIENT_INFORMATION" ? 422 : 503, code);
      },
    });
    render(
      createElement(AssistantRecommendation, {
        ticketId: `ticket-${code}`,
        initialRecommendation: null,
      })
    );
    fireEvent.click(screen.getByRole("button", { name: "Generar recomendación" }));
    assert.match((await screen.findByRole("alert")).textContent, message);
    assert.equal(stub.calls.generate.length, 1);
    assert.equal(screen.queryByText("Recomendación generada"), null);
  });
}
