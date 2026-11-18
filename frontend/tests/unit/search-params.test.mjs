import assert from "node:assert/strict";
import { describe, test } from "node:test";
import {
  DEFAULT_SEARCH_LIMIT,
  MAX_QUERY_LENGTH,
  parseSemanticSearchParams,
} from "@/lib/search-params";

describe("parseSemanticSearchParams", () => {
  test("sin parámetros: consulta vacía y cantidad predeterminada", () => {
    assert.deepEqual(parseSemanticSearchParams({}), {
      query: "",
      limit: DEFAULT_SEARCH_LIMIT,
      tooLong: false,
    });
  });

  test("recorta la consulta y acepta las cantidades permitidas", () => {
    for (const limit of [5, 10, 20]) {
      const params = parseSemanticSearchParams({ q: "  vpn  ", limit: String(limit) });
      assert.equal(params.query, "vpn");
      assert.equal(params.limit, limit);
    }
  });

  test("una cantidad desconocida usa la predeterminada", () => {
    for (const limit of ["7", "0", "-5", "abc", "1000"]) {
      assert.equal(parseSemanticSearchParams({ limit }).limit, DEFAULT_SEARCH_LIMIT, limit);
    }
  });

  test("marca la consulta demasiado larga para no enviarla", () => {
    const justRight = "a".repeat(MAX_QUERY_LENGTH);
    assert.equal(parseSemanticSearchParams({ q: justRight }).tooLong, false);
    assert.equal(parseSemanticSearchParams({ q: `${justRight}a` }).tooLong, true);
  });
});
