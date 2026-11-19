import assert from "node:assert/strict";
import { describe, test } from "node:test";
import { describeError, errorRequestId, SESSION_CHANGED } from "@/lib/errors";
import {
  getMockTickets,
  MOCK_CONFLICT_TICKET_ID,
  MOCK_UNAVAILABLE_TICKET_ID,
  ticketsMock,
} from "@/mocks/tickets";

const TICKET_ID = "5b0e7c3a-2f1d-4c8e-9a6b-1d2e3f4a5b01";
const apiError = (code, { status, details = null, requestId = "req-123" } = {}) => ({
  error: { code, message: "Mensaje del backend", details, requestId },
  ...(status ? { status } : {}),
});

describe("ticketsMock.updateStatus", () => {
  test("resolver fija resolvedAt; reabrir la limpia sin alterar la prioridad", async () => {
    const before = getMockTickets().find((ticket) => ticket.id === TICKET_ID);
    const original = { ...before };
    const updated = await ticketsMock.updateStatus(TICKET_ID, { status: "resolved" });
    assert.equal(updated.status, "resolved");
    assert.ok(updated.updatedAt > original.updatedAt);
    assert.equal(updated.resolvedAt, updated.updatedAt);
    assert.equal(updated.title, original.title);
    assert.equal(updated.priority, original.priority);
    assert.deepEqual(updated.assignedTo, original.assignedTo);
    // Vuelve al estado original para no afectar otras pruebas.
    await ticketsMock.updateStatus(TICKET_ID, { status: "in_progress" });
    const reopened = await ticketsMock.updateStatus(TICKET_ID, { status: original.status });
    assert.equal(reopened.resolvedAt, null);
  });

  test("cerrar exige resolución y conserva la fecha; rechaza transiciones y estado obsoleto", async () => {
    const original = getMockTickets().find((ticket) => ticket.id === TICKET_ID).status;
    await assert.rejects(
      ticketsMock.updateStatus(TICKET_ID, { status: "closed" }),
      (e) => e.error.code === "TICKET_TRANSITION_INVALID"
    );
    await assert.rejects(
      ticketsMock.updateStatus(TICKET_ID, { status: "resolved", expectedStatus: "closed" }),
      (e) => e.error.code === "TICKET_STATE_CONFLICT"
    );
    const resolved = await ticketsMock.updateStatus(TICKET_ID, { status: "resolved" });
    const date = resolved.resolvedAt;
    assert.equal(
      (await ticketsMock.updateStatus(TICKET_ID, { status: "closed" })).resolvedAt,
      date
    );
    for (const status of ["in_progress", "open"]) {
      assert.equal((await ticketsMock.updateStatus(TICKET_ID, { status })).status, status);
    }
    await ticketsMock.updateStatus(TICKET_ID, { status: original });
  });

  test("ticket inexistente: 404 TICKET_NOT_FOUND con requestId", async () => {
    await assert.rejects(ticketsMock.updateStatus("no-existe", { status: "open" }), (error) => {
      assert.equal(error.status, 404);
      assert.equal(error.error.code, "TICKET_NOT_FOUND");
      assert.match(error.error.requestId, /^[0-9a-f-]{36}$/);
      return true;
    });
  });

  test("estado desconocido: 422 con details del campo status", async () => {
    await assert.rejects(ticketsMock.updateStatus(TICKET_ID, { status: "borrado" }), (error) => {
      assert.equal(error.status, 422);
      assert.deepEqual(
        error.error.details.map((detail) => detail.field),
        ["status"]
      );
      return true;
    });
  });

  test("errores simulados: 409 y 503 sin cambiar el ticket", async () => {
    for (const [id, status] of [
      [MOCK_CONFLICT_TICKET_ID, 409],
      [MOCK_UNAVAILABLE_TICKET_ID, 503],
    ]) {
      const before = getMockTickets().find((ticket) => ticket.id === id);
      const snapshot = { status: before.status, updatedAt: before.updatedAt };
      await assert.rejects(ticketsMock.updateStatus(id, { status: "closed" }), (error) => {
        assert.equal(error.status, status);
        return true;
      });
      const after = getMockTickets().find((ticket) => ticket.id === id);
      assert.deepEqual({ status: after.status, updatedAt: after.updatedAt }, snapshot);
    }
  });
});

describe("describeError", () => {
  test("409 por estado HTTP, con cualquier código", () => {
    const result = describeError(apiError("CUALQUIERA", { status: 409 }));
    assert.equal(result.kind, "conflict");
    assert.equal(
      result.message,
      "El ticket cambió mientras lo editabas. Recarga para ver la versión actual."
    );
    assert.equal(result.requestId, "req-123");
  });

  test("403: sin permiso (por código o por estado)", () => {
    for (const error of [apiError("FORBIDDEN"), apiError("OTRO", { status: 403 })]) {
      const result = describeError(error);
      assert.equal(result.kind, "forbidden");
      assert.equal(result.message, "No tienes permiso para esta acción.");
    }
  });

  test("404 TICKET_NOT_FOUND", () => {
    const result = describeError(apiError("TICKET_NOT_FOUND", { status: 404 }));
    assert.equal(result.kind, "notFound");
    assert.equal(result.message, "El ticket que buscas no existe o ya no está disponible.");
  });

  test("422: primer mensaje de details, o uno general", () => {
    const details = [
      { field: "status", message: "El estado no es válido." },
      { field: "otro", message: "Segundo" },
    ];
    assert.equal(
      describeError(apiError("VALIDATION_ERROR", { status: 422, details })).message,
      "El estado no es válido."
    );
    for (const sinDetalle of [null, [], [{ campo: "x" }], "texto"]) {
      assert.equal(
        describeError(apiError("VALIDATION_ERROR", { status: 422, details: sinDetalle })).message,
        "Los datos enviados no son válidos."
      );
    }
  });

  test("503 por estado HTTP, sin depender del código", () => {
    for (const code of ["SERVICE_UNAVAILABLE", "UNKNOWN_ERROR", "OTRO"]) {
      const result = describeError(apiError(code, { status: 503 }));
      assert.equal(result.kind, "unavailable");
      assert.equal(
        result.message,
        "El servicio no está disponible en este momento. Intenta de nuevo más tarde."
      );
    }
  });

  test("401 y sesión cambiada en otra pestaña", () => {
    assert.equal(
      describeError(apiError("AUTHENTICATION_REQUIRED", { status: 401 })).kind,
      "authentication"
    );
    assert.match(describeError(apiError(SESSION_CHANGED)).message, /otra pestaña/);
  });

  test("errores que no son del contrato: mensaje general y sin código de referencia", () => {
    for (const value of [new TypeError("fetch failed"), "texto", null, { error: "x" }]) {
      const result = describeError(value);
      assert.equal(result.kind, "other");
      assert.equal(result.message, "No se pudo completar la acción. Intenta de nuevo.");
      assert.equal(result.requestId, null);
    }
  });

  test("errorRequestId: solo con requestId no vacío", () => {
    assert.equal(errorRequestId(apiError("X")), "req-123");
    assert.equal(errorRequestId(apiError("X", { requestId: "" })), null);
    assert.equal(errorRequestId(new Error("x")), null);
  });
});
