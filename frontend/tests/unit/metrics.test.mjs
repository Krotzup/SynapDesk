import assert from "node:assert/strict";
import { describe, test } from "node:test";
import { metricsMock } from "@/mocks/metrics";
import { getMockTickets } from "@/mocks/tickets";

describe("metricsMock.getSummary", () => {
  test("devuelve solo los cinco conteos aprobados para el MVP", async () => {
    const summary = await metricsMock.getSummary();
    assert.deepEqual(Object.keys(summary).sort(), [
      "closedTickets",
      "inProgressTickets",
      "openTickets",
      "resolvedTickets",
      "totalTickets",
    ]);
  });

  test("cada conteo coincide con los tickets de ejemplo de ese estado", async () => {
    const summary = await metricsMock.getSummary();
    const tickets = getMockTickets();
    const count = (status) => tickets.filter((ticket) => ticket.status === status).length;
    assert.equal(summary.totalTickets, tickets.length);
    assert.equal(summary.openTickets, count("open"));
    assert.equal(summary.inProgressTickets, count("in_progress"));
    assert.equal(summary.resolvedTickets, count("resolved"));
    assert.equal(summary.closedTickets, count("closed"));
  });

  test("los cuatro estados suman el total y los datos de ejemplo incluyen cerrados", async () => {
    const summary = await metricsMock.getSummary();
    const sum =
      summary.openTickets +
      summary.inProgressTickets +
      summary.resolvedTickets +
      summary.closedTickets;
    assert.equal(sum, summary.totalTickets);
    assert.ok(summary.closedTickets > 0);
  });
});
