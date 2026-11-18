import assert from "node:assert/strict";
import { describe, test } from "node:test";
import {
  filtersForUrl,
  hasActiveFilters,
  parseTicketListParams,
  TICKET_PAGE_SIZE,
} from "@/lib/ticket-filters";

describe("parseTicketListParams", () => {
  test("sin parámetros: primera página y sin filtros", () => {
    assert.deepEqual(parseTicketListParams({}), {
      status: undefined,
      priority: undefined,
      area: undefined,
      search: undefined,
      page: 1,
      pageSize: TICKET_PAGE_SIZE,
    });
  });

  test("lee los filtros válidos y recorta los textos", () => {
    const params = parseTicketListParams({
      status: "in_progress",
      priority: "high",
      area: " Soporte ",
      search: "  vpn  ",
      page: "3",
    });
    assert.equal(params.status, "in_progress");
    assert.equal(params.priority, "high");
    assert.equal(params.area, "Soporte");
    assert.equal(params.search, "vpn");
    assert.equal(params.page, 3);
  });

  test("ignora estados y prioridades desconocidos en lugar de enviarlos", () => {
    const params = parseTicketListParams({ status: "borrado", priority: "critical" });
    assert.equal(params.status, undefined);
    assert.equal(params.priority, undefined);
  });

  test("un texto solo con espacios no es filtro", () => {
    assert.equal(parseTicketListParams({ search: "   " }).search, undefined);
  });

  test("el tamaño de página no se puede cambiar desde la URL", () => {
    assert.equal(parseTicketListParams({ pageSize: "1000" }).pageSize, TICKET_PAGE_SIZE);
  });
});

describe("hasActiveFilters y filtersForUrl", () => {
  test("la paginación no cuenta como filtro", () => {
    assert.equal(hasActiveFilters({ page: 4, pageSize: 10 }), false);
    assert.equal(hasActiveFilters({ status: "open" }), true);
    assert.equal(hasActiveFilters({ search: "vpn" }), true);
  });

  test("filtersForUrl conserva los filtros y quita page y pageSize", () => {
    assert.deepEqual(
      filtersForUrl({ status: "open", area: "Soporte", search: "vpn", page: 2, pageSize: 10 }),
      { status: "open", priority: undefined, area: "Soporte", search: "vpn" }
    );
  });
});
