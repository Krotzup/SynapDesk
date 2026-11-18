import assert from "node:assert/strict";
import { describe, test } from "node:test";
import { buildQuery, parsePage } from "@/lib/params";
import { DOCUMENT_PAGE_SIZE, parseDocumentListParams } from "@/lib/document-params";

describe("buildQuery", () => {
  test("sin parámetros devuelve una cadena vacía", () => {
    assert.equal(buildQuery(), "");
    assert.equal(buildQuery({}), "");
  });

  test("omite undefined, null y vacíos", () => {
    assert.equal(buildQuery({ a: undefined, b: null, c: "", d: "x" }), "?d=x");
  });

  test("conserva 0 y false, que no son vacíos", () => {
    assert.equal(buildQuery({ page: 0, flag: false }), "?page=0&flag=false");
  });

  test("codifica los caracteres especiales", () => {
    assert.equal(buildQuery({ search: "error de red & VPN" }), "?search=error+de+red+%26+VPN");
    assert.equal(new URLSearchParams(buildQuery({ q: "¿qué pasó?" })).get("q"), "¿qué pasó?");
  });
});

describe("parsePage", () => {
  test("acepta enteros mayores o iguales a 1", () => {
    assert.equal(parsePage("1"), 1);
    assert.equal(parsePage("7"), 7);
    assert.equal(parsePage(" 3 "), 3);
  });

  test("cualquier otro valor es la primera página", () => {
    for (const value of [undefined, "", "   ", "0", "-2", "1.5", "abc", "2x", "Infinity", "+3"]) {
      assert.equal(parsePage(value), 1, `valor ${JSON.stringify(value)}`);
    }
  });

  test("rechaza notación científica, hexadecimal y números fuera del rango seguro", () => {
    for (const value of ["1e2", "0x10", "1e308", "9007199254740993"]) {
      assert.equal(parsePage(value), 1, `valor ${JSON.stringify(value)}`);
    }
    assert.equal(parsePage("007"), 7);
  });

  test("con el parámetro repetido usa el primero", () => {
    assert.equal(parsePage(["4", "9"]), 4);
    assert.equal(parsePage([]), 1);
  });
});

describe("parseDocumentListParams", () => {
  test("solo lee la página; el tamaño es fijo", () => {
    assert.deepEqual(parseDocumentListParams({ page: "2" }), {
      page: 2,
      pageSize: DOCUMENT_PAGE_SIZE,
    });
  });

  test("ignora los parámetros que el contrato no define", () => {
    assert.deepEqual(parseDocumentListParams({ search: "vpn", pageSize: "500", status: "x" }), {
      page: 1,
      pageSize: DOCUMENT_PAGE_SIZE,
    });
  });
});
