import assert from "node:assert/strict";
import { afterEach, describe, test } from "node:test";
import { createElement } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { router } from "next/navigation";
import { TicketStatusControl } from "@/components/tickets/TicketStatusControl";
import { ticketsService } from "@/services/tickets";
import { apiError, deferred, REQUEST_ID, resetEnvironment, stubService } from "./helpers.mjs";

const TICKET_ID = "5b0e7c3a-2f1d-4c8e-9a6b-1d2e3f4a5b01";

let stub;
afterEach(() => {
  stub?.restore();
  stub = undefined;
  resetEnvironment();
});

function renderControl(status = "open") {
  render(createElement(TicketStatusControl, { ticketId: TICKET_ID, status }));
}

const select = () => screen.getByLabelText("Cambiar estado");
const saveButton = () => screen.getByRole("button", { name: /Guardar estado|Guardando…/ });

function choose(status) {
  fireEvent.change(select(), { target: { value: status } });
}

function failWith(error) {
  return stubService(ticketsService, {
    updateStatus: async () => {
      throw error;
    },
  });
}

describe("TicketStatusControl", () => {
  test("muestra los cuatro estados, marca el actual y no permite guardar sin cambios", () => {
    renderControl("open");
    const options = [...select().options].map((option) => option.textContent);
    assert.deepEqual(options, ["Abierto (actual)", "En Proceso", "Resuelto", "Cerrado"]);
    assert.equal(saveButton().disabled, true);
    choose("resolved");
    assert.equal(saveButton().disabled, false);
  });

  test("guarda solo el estado, confirma en una región aria-live y actualiza la página", async () => {
    stub = stubService(ticketsService, {
      updateStatus: async (_id, { status }) => ({ id: TICKET_ID, status }),
    });
    renderControl("open");
    choose("in_progress");
    fireEvent.click(saveButton());

    const confirmation = await screen.findByText("Estado actualizado a «En Proceso».");
    assert.equal(confirmation.getAttribute("aria-live"), "polite");
    assert.deepEqual(stub.calls.updateStatus, [
      [TICKET_ID, { status: "in_progress", expectedStatus: "open" }],
    ]);
    assert.deepEqual(router.calls, [["refresh"]]);
    assert.equal(screen.queryByRole("alert"), null);
  });

  test("mientras guarda: «Guardando…», selector y botón deshabilitados", async () => {
    const pending = deferred();
    stub = stubService(ticketsService, { updateStatus: () => pending.promise });
    renderControl("open");
    choose("closed");
    fireEvent.click(saveButton());

    const button = await screen.findByRole("button", { name: "Guardando…" });
    assert.equal(button.disabled, true);
    assert.equal(select().disabled, true);
    fireEvent.submit(button.closest("form"));
    assert.equal(stub.calls.updateStatus.length, 1);

    pending.resolve({ id: TICKET_ID, status: "closed" });
    await screen.findByText("Estado actualizado a «Cerrado».");
  });

  test("409: avisa del conflicto, ofrece Recargar y muestra el código de referencia", async () => {
    stub = failWith(apiError(409, "TICKET_CONFLICT"));
    renderControl("open");
    choose("closed");
    fireEvent.click(saveButton());

    const alert = await screen.findByRole("alert");
    assert.match(
      alert.textContent,
      /El ticket cambió mientras lo editabas\. Recarga para ver la versión actual\./
    );
    assert.ok(screen.getByRole("button", { name: "Recargar" }));
    assert.match(alert.textContent, new RegExp(`Código de referencia: ${REQUEST_ID}`));
    // Sin reintento automático ni actualización de la página; se puede volver a intentar a mano.
    assert.equal(stub.calls.updateStatus.length, 1);
    assert.equal(router.calls.length, 0);
    assert.equal(saveButton().disabled, false);
    assert.equal(select().value, "closed");
  });

  test("409 se reconoce por estado HTTP, aunque el backend use otro error.code", async () => {
    stub = failWith(apiError(409, "CODIGO_AUN_NO_DEFINIDO"));
    renderControl("open");
    choose("resolved");
    fireEvent.click(saveButton());
    await screen.findByRole("button", { name: "Recargar" });
  });

  test("503: avisa que el servicio no está disponible, sin Recargar y sin reintento", async () => {
    stub = failWith(apiError(503, "SERVICE_UNAVAILABLE"));
    renderControl("resolved");
    choose("open");
    fireEvent.click(saveButton());

    const alert = await screen.findByRole("alert");
    assert.match(alert.textContent, /El servicio no está disponible en este momento/);
    assert.match(alert.textContent, new RegExp(REQUEST_ID));
    assert.equal(screen.queryByRole("button", { name: "Recargar" }), null);
    assert.equal(stub.calls.updateStatus.length, 1);
    assert.equal(saveButton().disabled, false);
  });

  test("401: pide iniciar sesión con un enlace al login", async () => {
    stub = failWith(apiError(401, "AUTHENTICATION_REQUIRED"));
    renderControl("open");
    choose("closed");
    fireEvent.click(saveButton());

    await screen.findByRole("alert");
    assert.equal(
      screen.getByRole("link", { name: "Ir al inicio de sesión" }).getAttribute("href"),
      "/login"
    );
  });

  test("422: muestra el mensaje del campo status", async () => {
    stub = failWith(
      apiError(422, "VALIDATION_ERROR", [{ field: "status", message: "Estado no válido." }])
    );
    renderControl("open");
    choose("closed");
    fireEvent.click(saveButton());

    const alert = await screen.findByRole("alert");
    assert.match(alert.textContent, /Estado no válido\./);
  });

  test("un error anterior desaparece al volver a guardar con éxito", async () => {
    let attempt = 0;
    stub = stubService(ticketsService, {
      updateStatus: async (_id, { status }) => {
        attempt += 1;
        if (attempt === 1) throw apiError(503, "SERVICE_UNAVAILABLE");
        return { id: TICKET_ID, status };
      },
    });
    renderControl("open");
    choose("closed");
    fireEvent.click(saveButton());
    await screen.findByRole("alert");

    fireEvent.click(saveButton());
    await screen.findByText("Estado actualizado a «Cerrado».");
    await waitFor(() => assert.equal(screen.queryByRole("alert"), null));
  });
});
