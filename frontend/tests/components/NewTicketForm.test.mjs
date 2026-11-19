import assert from "node:assert/strict";
import { afterEach, describe, test } from "node:test";
import { createElement } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { router } from "next/navigation";
import { NewTicketForm } from "@/components/tickets/NewTicketForm";
import { ticketsService } from "@/services/tickets";
import { apiError, deferred, REQUEST_ID, resetEnvironment, stubService } from "./helpers.mjs";

const TICKET = {
  id: "5b0e7c3a-2f1d-4c8e-9a6b-1d2e3f4a5b01",
  title: "No puedo conectarme a la VPN",
  description: "Desde ayer la VPN no conecta desde casa.",
  status: "open",
  priority: "medium",
};

let stub;
afterEach(() => {
  stub?.restore();
  stub = undefined;
  resetEnvironment();
});

function fill(title, description) {
  fireEvent.change(screen.getByLabelText("Título"), { target: { value: title } });
  fireEvent.change(screen.getByLabelText("Descripción"), { target: { value: description } });
}

function submit() {
  fireEvent.click(screen.getByRole("button", { name: "Crear ticket" }));
}

describe("NewTicketForm", () => {
  test("valida en el cliente antes de enviar y marca cada campo", () => {
    stub = stubService(ticketsService, { create: async () => TICKET });
    render(createElement(NewTicketForm));
    fill("   ", "corta");
    submit();

    assert.equal(stub.calls.create.length, 0);
    assert.equal(screen.getByText("Ingresa un título.").id, "title-error");
    assert.equal(screen.getByText("Debe tener al menos 10 caracteres.").id, "description-error");
    assert.equal(screen.getByLabelText("Título").getAttribute("aria-invalid"), "true");
    assert.equal(screen.getByLabelText("Título").getAttribute("aria-describedby"), "title-error");
    assert.equal(screen.queryByRole("alert"), null);
  });

  test("envía los valores recortados y abre el detalle del ticket creado", async () => {
    stub = stubService(ticketsService, { create: async () => TICKET });
    render(createElement(NewTicketForm));
    fill("  No puedo conectarme a la VPN  ", "  Desde ayer la VPN no conecta desde casa.  ");
    submit();

    await waitFor(() => assert.deepEqual(router.calls, [["push", `/tickets/${TICKET.id}`]]));
    assert.deepEqual(stub.calls.create, [
      [{ title: TICKET.title, description: TICKET.description }],
    ]);
  });

  test("mientras se envía, el botón dice «Creando ticket…» y no permite un segundo envío", async () => {
    const pending = deferred();
    stub = stubService(ticketsService, { create: () => pending.promise });
    render(createElement(NewTicketForm));
    fill(TICKET.title, TICKET.description);
    submit();

    const button = await screen.findByRole("button", { name: "Creando ticket…" });
    assert.equal(button.disabled, true);
    assert.equal(screen.getByLabelText("Título").disabled, true);
    fireEvent.submit(button.closest("form"));
    assert.equal(stub.calls.create.length, 1);

    pending.resolve(TICKET);
    await waitFor(() => assert.equal(router.calls.length, 1));
  });

  test("422 con details: muestra el error en su campo y no repite el aviso general", async () => {
    stub = stubService(ticketsService, {
      create: async () => {
        throw apiError(422, "VALIDATION_ERROR", [
          { field: "title", message: "El título ya existe." },
        ]);
      },
    });
    render(createElement(NewTicketForm));
    fill(TICKET.title, TICKET.description);
    submit();

    const message = await screen.findByText("El título ya existe.");
    assert.equal(message.id, "title-error");
    assert.equal(screen.getByLabelText("Título").getAttribute("aria-invalid"), "true");
    assert.equal(screen.queryByRole("alert"), null);
    assert.equal(screen.getByRole("button", { name: "Crear ticket" }).disabled, false);
  });

  test("422 sin campos en details (campos no previstos): aviso general con código de referencia", async () => {
    stub = stubService(ticketsService, {
      create: async () => {
        throw apiError(422, "VALIDATION_ERROR", []);
      },
    });
    render(createElement(NewTicketForm));
    fill(TICKET.title, TICKET.description);
    submit();

    const alert = await screen.findByRole("alert");
    assert.match(alert.textContent, /Revisa los datos del ticket\./);
    assert.match(alert.textContent, new RegExp(`Código de referencia: ${REQUEST_ID}`));
  });

  test("401: pide iniciar sesión con un enlace al login", async () => {
    stub = stubService(ticketsService, {
      create: async () => {
        throw apiError(401, "AUTHENTICATION_REQUIRED");
      },
    });
    render(createElement(NewTicketForm));
    fill(TICKET.title, TICKET.description);
    submit();

    const alert = await screen.findByRole("alert");
    assert.match(alert.textContent, /Tu sesión expiró/);
    const link = screen.getByRole("link", { name: "Ir al inicio de sesión" });
    assert.equal(link.getAttribute("href"), "/login");
  });

  test("503: aviso general, sin reintento automático y con el formulario habilitado", async () => {
    stub = stubService(ticketsService, {
      create: async () => {
        throw apiError(503, "SERVICE_UNAVAILABLE");
      },
    });
    render(createElement(NewTicketForm));
    fill(TICKET.title, TICKET.description);
    submit();

    const alert = await screen.findByRole("alert");
    assert.match(alert.textContent, /No se pudo crear el ticket\. Intenta nuevamente\./);
    assert.match(alert.textContent, new RegExp(REQUEST_ID));
    assert.equal(stub.calls.create.length, 1);
    assert.equal(screen.getByRole("button", { name: "Crear ticket" }).disabled, false);
    assert.equal(screen.getByLabelText("Título").value, TICKET.title);
    assert.equal(router.calls.length, 0);
  });
});
