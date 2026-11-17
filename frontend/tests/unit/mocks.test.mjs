import assert from "node:assert/strict";
import { describe, test } from "node:test";
import { documentsMock } from "@/mocks/documents";
import { getMockRecommendations, recommendationsMock } from "@/mocks/recommendations";
import { getMockTickets, ticketsMock } from "@/mocks/tickets";
import { MOCK_ERROR_QUERY } from "@/mocks/utils";

// Error con la forma del contrato: { error: { code, message, details, requestId } }.
async function rejectsWithCode(promise, code) {
  await assert.rejects(promise, (error) => {
    assert.equal(error.error.code, code);
    assert.equal(typeof error.error.message, "string");
    assert.match(error.error.requestId, /^[0-9a-f-]{36}$/);
    return true;
  });
}

describe("ticketsMock.getAll", () => {
  test("sin filtros: todos los tickets, más recientes primero, paginados", async () => {
    const all = getMockTickets();
    const result = await ticketsMock.getAll({ page: 1, pageSize: 5 });
    assert.equal(result.totalItems, all.length);
    assert.equal(result.totalPages, Math.ceil(all.length / 5));
    assert.equal(result.items.length, 5);
    const dates = result.items.map((ticket) => ticket.createdAt);
    assert.deepEqual(dates, [...dates].sort().reverse());
  });

  test("filtra por estado y prioridad a la vez", async () => {
    const expected = getMockTickets().filter(
      (ticket) => ticket.status === "open" && ticket.priority === "high"
    ).length;
    const result = await ticketsMock.getAll({ status: "open", priority: "high", pageSize: 50 });
    assert.equal(result.totalItems, expected);
    assert.ok(
      result.items.every((ticket) => ticket.status === "open" && ticket.priority === "high")
    );
  });

  test("la búsqueda ignora mayúsculas y tildes, y encuentra por inicio del ID", async () => {
    const withAccent = await ticketsMock.getAll({ search: "AUTENTICACION", pageSize: 50 });
    assert.ok(withAccent.items.some((ticket) => ticket.title.includes("autenticación")));
    const [first] = getMockTickets();
    const byId = await ticketsMock.getAll({ search: first.id.slice(0, 8), pageSize: 50 });
    assert.ok(byId.items.some((ticket) => ticket.id === first.id));
  });

  test("una página fuera de rango no tiene tickets pero informa el total", async () => {
    const result = await ticketsMock.getAll({ page: 99, pageSize: 10 });
    assert.equal(result.items.length, 0);
    assert.equal(result.totalItems, getMockTickets().length);
  });

  test("el texto de error simulado devuelve SERVICE_UNAVAILABLE", async () => {
    await rejectsWithCode(ticketsMock.getAll({ search: MOCK_ERROR_QUERY }), "SERVICE_UNAVAILABLE");
  });
});

describe("ticketsMock: detalle y creación", () => {
  test("un ID inexistente devuelve TICKET_NOT_FOUND", async () => {
    await rejectsWithCode(ticketsMock.getById("no-existe"), "TICKET_NOT_FOUND");
  });

  test("valida como el backend: 422 con details por campo y sin crear el ticket", async () => {
    const before = getMockTickets().length;
    await assert.rejects(ticketsMock.create({ title: "  ab ", description: "corta" }), (error) => {
      assert.equal(error.error.code, "VALIDATION_ERROR");
      assert.deepEqual(
        error.error.details.map((detail) => detail.field),
        ["title", "description"]
      );
      return true;
    });
    assert.equal(getMockTickets().length, before);
  });
});

describe("documentsMock.getAll", () => {
  test("pagina y ordena de más reciente a más antiguo", async () => {
    const first = await documentsMock.getAll({ page: 1, pageSize: 10 });
    const second = await documentsMock.getAll({ page: 2, pageSize: 10 });
    assert.equal(first.items.length + second.items.length, first.totalItems);
    const dates = [...first.items, ...second.items].map((document) => document.createdAt);
    assert.deepEqual(dates, [...dates].sort().reverse());
  });

  test("un ID inexistente devuelve DOCUMENT_NOT_FOUND", async () => {
    await rejectsWithCode(documentsMock.getById("no-existe"), "DOCUMENT_NOT_FOUND");
  });
});

describe("recommendationsMock.getByTicket", () => {
  test("devuelve todas las recomendaciones del ticket, sin las de otros", async () => {
    const ticketId = "64f10aed-c41c-46a3-91dd-f2cbcd5eb79f";
    const expected = getMockRecommendations().filter((item) => item.ticketId === ticketId);
    const result = await recommendationsMock.getByTicket(ticketId);
    assert.equal(result.length, expected.length);
    assert.ok(result.length >= 2, "el ejemplo tiene historial");
    assert.ok(result.every((item) => item.ticketId === ticketId));
  });

  test("devuelve copias: modificar el resultado no cambia los datos de ejemplo", async () => {
    const ticketId = "64f10aed-c41c-46a3-91dd-f2cbcd5eb79f";
    const [first] = await recommendationsMock.getByTicket(ticketId);
    const original = first.content;
    first.content = "cambiado";
    const [again] = await recommendationsMock.getByTicket(ticketId);
    assert.equal(again.content, original);
  });
});
