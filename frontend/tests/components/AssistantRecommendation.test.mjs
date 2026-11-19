import assert from "node:assert/strict";
import { afterEach, describe, test } from "node:test";
import { createElement } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { router } from "next/navigation";
import { AssistantRecommendation } from "@/components/recommendations/AssistantRecommendation";
import { recommendationsService } from "@/services/recommendations";
import { resetEnvironment, stubService } from "./helpers.mjs";

const ticketId = "5b0e7c3a-2f1d-4c8e-9a6b-1d2e3f4a5b01";
const recommendation = {
  id: "1f1d7c3a-2f1d-4c8e-9a6b-1d2e3f4a5b02",
  ticketId,
  content: "Consultar la configuración DNS.",
  status: "pending",
  sources: [],
  createdAt: "2026-11-19T00:00:00Z",
  review: null,
};

let stub;
afterEach(() => {
  stub?.restore();
  stub = undefined;
  resetEnvironment();
});

describe("AssistantRecommendation", () => {
  test("genera un borrador para el ticket y muestra la revisión disponible", async () => {
    stub = stubService(recommendationsService, {
      generate: async () => recommendation,
    });
    render(createElement(AssistantRecommendation, { ticketId, initialRecommendation: null }));
    fireEvent.click(screen.getByRole("button", { name: "Generar recomendación" }));

    await screen.findByText(recommendation.content);
    assert.deepEqual(stub.calls.generate, [[ticketId]]);
    assert.ok(screen.getByRole("button", { name: /Aceptar recomendación/ }));
    assert.deepEqual(router.calls, [["refresh"]]);
  });

  test("acepta la recomendación sin resolver el ticket ni alterar el contenido original", async () => {
    stub = stubService(recommendationsService, {
      review: async () => undefined,
    });
    render(
      createElement(AssistantRecommendation, { ticketId, initialRecommendation: recommendation })
    );
    assert.match(
      screen.getByText(/el estado del ticket se cambia por separado/i).textContent,
      /separado/
    );
    fireEvent.click(screen.getByRole("button", { name: /Aceptar recomendación/ }));

    await screen.findByText("La recomendación fue aceptada.");
    assert.deepEqual(stub.calls.review, [[recommendation.id, { decision: "accepted" }]]);
    assert.ok(screen.getByText(recommendation.content));
    assert.deepEqual(router.calls, [["refresh"]]);
  });
});
