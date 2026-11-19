import assert from "node:assert/strict";
import { afterEach, describe, test } from "node:test";
import { createElement } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { router } from "next/navigation";
import { AssistantRecommendation } from "@/components/recommendations/AssistantRecommendation";
import { recommendationsService } from "@/services/recommendations";
import { apiError, deferred, REQUEST_ID, resetEnvironment, stubService } from "./helpers.mjs";

const TICKET_ID = "64f10aed-c41c-46a3-91dd-f2cbcd5eb79f";
const PENDING = {
  id: "9a8b7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d",
  ticketId: TICKET_ID,
  content: "Reinicia el servicio de base de datos y revisa las credenciales.",
  status: "pending",
  sources: [],
  createdAt: "2026-10-28T10:30:00Z",
};

let stub;
afterEach(() => {
  stub?.restore();
  stub = undefined;
  resetEnvironment();
});

function renderPanel(initialRecommendation = PENDING) {
  render(createElement(AssistantRecommendation, { ticketId: TICKET_ID, initialRecommendation }));
}

const button = (name) => screen.getByRole("button", { name });
const failReview = (error) =>
  stubService(recommendationsService, {
    review: async () => {
      throw error;
    },
  });

function openEdit() {
  fireEvent.click(button("✏️ Editar"));
  return screen.getByLabelText("Texto de la recomendación");
}

function openDiscard() {
  fireEvent.click(button("🗑️ Descartar"));
  return screen.getByLabelText("Motivo (opcional)");
}

describe("AssistantRecommendation: sin recomendación", () => {
  test("ofrece generar, muestra «Generando recomendación…» y actualiza la página al terminar", async () => {
    const pending = deferred();
    stub = stubService(recommendationsService, { generate: () => pending.promise });
    renderPanel(null);

    assert.ok(screen.getByText("Aún no hay recomendaciones para este ticket."));
    fireEvent.click(button("Generar recomendación"));
    assert.deepEqual(stub.calls.generate, [[TICKET_ID]]);
    const busy = await screen.findByRole("button", { name: "Generando recomendación…" });
    assert.equal(busy.disabled, true);

    pending.resolve(PENDING);
    await waitFor(() => assert.deepEqual(router.calls, [["refresh"]]));
  });

  test("403 FORBIDDEN al generar: mensaje propio de generar", async () => {
    stub = stubService(recommendationsService, {
      generate: async () => {
        throw apiError(403, "FORBIDDEN");
      },
    });
    renderPanel(null);
    fireEvent.click(button("Generar recomendación"));
    const alert = await screen.findByRole("alert");
    assert.match(alert.textContent, /No tienes permiso para generar recomendaciones\./);
  });
});

describe("AssistantRecommendation: editar", () => {
  test("abre el campo con el contenido y el foco en él", () => {
    renderPanel();
    const field = openEdit();
    assert.equal(field.value, PENDING.content);
    assert.equal(document.activeElement, field);
  });

  test("vacío o sin cambios: avisa en el campo y no llama al servicio", () => {
    stub = stubService(recommendationsService, { review: async () => undefined });
    renderPanel();
    const field = openEdit();

    fireEvent.change(field, { target: { value: "   " } });
    fireEvent.click(button("Guardar cambios"));
    assert.equal(
      screen.getByText("Escribe el texto de la recomendación.").id,
      "recommendation-content-error"
    );
    assert.equal(field.getAttribute("aria-invalid"), "true");

    fireEvent.change(field, { target: { value: `  ${PENDING.content}  ` } });
    fireEvent.click(button("Guardar cambios"));
    assert.ok(screen.getByText("No hiciste cambios. Edita el texto o cancela."));
    assert.equal(stub.calls.review.length, 0);
  });

  test("envía modified con el texto recortado y el comentario solo si se escribió", async () => {
    const pending = deferred();
    stub = stubService(recommendationsService, { review: () => pending.promise });
    renderPanel();
    fireEvent.change(openEdit(), { target: { value: "  Texto corregido por el agente.  " } });
    fireEvent.change(screen.getByLabelText("¿Qué cambiaste? (opcional)"), {
      target: { value: "  Faltaba un paso.  " },
    });
    fireEvent.click(button("Guardar cambios"));

    assert.ok(await screen.findByRole("button", { name: "Guardando…" }));
    assert.deepEqual(stub.calls.review, [
      [
        PENDING.id,
        {
          decision: "modified",
          modifiedContent: "Texto corregido por el agente.",
          feedback: "Faltaba un paso.",
        },
      ],
    ]);
    pending.resolve();
    await waitFor(() => assert.deepEqual(router.calls, [["refresh"]]));
  });

  test("sin comentario, no envía feedback", async () => {
    stub = stubService(recommendationsService, { review: async () => undefined });
    renderPanel();
    fireEvent.change(openEdit(), { target: { value: "Otro texto." } });
    fireEvent.click(button("Guardar cambios"));
    await waitFor(() => assert.equal(stub.calls.review.length, 1));
    assert.deepEqual(stub.calls.review[0][1], {
      decision: "modified",
      modifiedContent: "Otro texto.",
    });
  });
});

describe("AssistantRecommendation: descartar y cancelar", () => {
  test("descartar envía rejected con el motivo recortado y muestra «Descartando…»", async () => {
    const pending = deferred();
    stub = stubService(recommendationsService, { review: () => pending.promise });
    renderPanel();
    const reason = openDiscard();
    assert.equal(document.activeElement, reason);
    fireEvent.change(reason, { target: { value: "  No corresponde al ticket.  " } });
    fireEvent.click(button("Descartar"));

    assert.ok(await screen.findByRole("button", { name: "Descartando…" }));
    assert.deepEqual(stub.calls.review, [
      [PENDING.id, { decision: "rejected", feedback: "No corresponde al ticket." }],
    ]);
    pending.resolve();
    await waitFor(() => assert.deepEqual(router.calls, [["refresh"]]));
  });

  test("descartar sin motivo envía solo la decisión", async () => {
    stub = stubService(recommendationsService, { review: async () => undefined });
    renderPanel();
    openDiscard();
    fireEvent.click(button("Descartar"));
    await waitFor(() => assert.equal(stub.calls.review.length, 1));
    assert.deepEqual(stub.calls.review[0][1], { decision: "rejected" });
  });

  test("cancelar devuelve el foco al botón que abrió el formulario", async () => {
    renderPanel();
    openEdit();
    fireEvent.click(button("Cancelar"));
    await waitFor(() => assert.equal(document.activeElement, button("✏️ Editar")));

    openDiscard();
    fireEvent.click(button("Cancelar"));
    await waitFor(() => assert.equal(document.activeElement, button("🗑️ Descartar")));
  });
});

describe("AssistantRecommendation: errores", () => {
  test("422 en modifiedContent: el mensaje queda junto a su campo, sin aviso general", async () => {
    stub = failReview(
      apiError(422, "VALIDATION_ERROR", [{ field: "modifiedContent", message: "Texto muy largo." }])
    );
    renderPanel();
    const field = openEdit();
    fireEvent.change(field, { target: { value: "Texto nuevo." } });
    fireEvent.click(button("Guardar cambios"));

    const message = await screen.findByText("Texto muy largo.");
    assert.equal(message.id, "recommendation-content-error");
    assert.equal(field.getAttribute("aria-invalid"), "true");
    assert.equal(field.getAttribute("aria-describedby"), "recommendation-content-error");
    assert.equal(screen.queryByRole("alert"), null);
  });

  test("422 en feedback: el mensaje queda junto al motivo, sin aviso general", async () => {
    stub = failReview(
      apiError(422, "VALIDATION_ERROR", [{ field: "feedback", message: "Motivo muy largo." }])
    );
    renderPanel();
    const reason = openDiscard();
    fireEvent.click(button("Descartar"));

    const message = await screen.findByText("Motivo muy largo.");
    assert.equal(message.id, "review-feedback-error");
    assert.equal(reason.getAttribute("aria-invalid"), "true");
    assert.equal(reason.getAttribute("aria-describedby"), "review-feedback-error");
    assert.equal(screen.queryByRole("alert"), null);
  });

  test("401: pide iniciar sesión con un enlace al login", async () => {
    stub = failReview(apiError(401, "AUTHENTICATION_REQUIRED"));
    renderPanel();
    openDiscard();
    fireEvent.click(button("Descartar"));
    const alert = await screen.findByRole("alert");
    assert.match(alert.textContent, /Tu sesión expiró\. Inicia sesión de nuevo para continuar\./);
    assert.equal(
      screen.getByRole("link", { name: "Ir al inicio de sesión" }).getAttribute("href"),
      "/login"
    );
  });

  test("RECOMMENDATION_ALREADY_REVIEWED: pide recargar", async () => {
    stub = failReview(apiError(409, "RECOMMENDATION_ALREADY_REVIEWED"));
    renderPanel();
    openDiscard();
    fireEvent.click(button("Descartar"));
    const alert = await screen.findByRole("alert");
    assert.match(
      alert.textContent,
      /Esta recomendación ya fue revisada\. Recarga la página para ver su estado\./
    );
  });

  test("503: mensaje de respaldo de la acción con el código de referencia, sin reintento", async () => {
    stub = failReview(apiError(503, "SERVICE_UNAVAILABLE"));
    renderPanel();
    fireEvent.change(openEdit(), { target: { value: "Texto nuevo." } });
    fireEvent.click(button("Guardar cambios"));
    const alert = await screen.findByRole("alert");
    assert.match(
      alert.textContent,
      /No se pudo guardar la recomendación editada\. Intenta nuevamente\./
    );
    assert.match(alert.textContent, new RegExp(`Código de referencia: ${REQUEST_ID}`));
    assert.equal(stub.calls.review.length, 1);
    assert.equal(router.calls.length, 0);
  });

  test("403 FORBIDDEN al revisar: mensaje propio de revisar", async () => {
    stub = failReview(apiError(403, "FORBIDDEN"));
    renderPanel();
    openDiscard();
    fireEvent.click(button("Descartar"));
    const alert = await screen.findByRole("alert");
    assert.match(alert.textContent, /No tienes permiso para revisar recomendaciones\./);
  });
});

describe("AssistantRecommendation: aceptar y resolver", () => {
  test("queda deshabilitado y descrito por accept-note", () => {
    renderPanel();
    const accept = button("✓ Aceptar y resolver");
    assert.equal(accept.disabled, true);
    assert.equal(accept.getAttribute("aria-describedby"), "accept-note");
    assert.match(
      document.getElementById("accept-note").textContent,
      /Disponible cuando el backend/
    );
  });
});
