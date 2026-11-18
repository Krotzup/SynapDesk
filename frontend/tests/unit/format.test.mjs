import assert from "node:assert/strict";
import { describe, test } from "node:test";
import {
  formatContentType,
  formatDateTime,
  formatExcerpt,
  formatScore,
  shortId,
} from "@/lib/format";

// Intl usa espacios especiales (por ejemplo, antes de "a. m."); se comparan como espacios comunes.
const plain = (text) => text.replace(/\s/gu, " ");

describe("formatScore", () => {
  test("dos decimales con coma, sin porcentaje", () => {
    assert.equal(formatScore(0.5), "0,50");
    assert.equal(formatScore(0.731), "0,73");
    assert.equal(formatScore(1), "1,00");
  });

  test("la similitud coseno puede ser negativa", () => {
    assert.equal(formatScore(-0.2), "-0,20");
  });
});

describe("formatDateTime", () => {
  test("muestra la hora de Chile, no la del servidor", () => {
    // 13:26 UTC son las 10:26 en Santiago (UTC-3 en octubre).
    assert.equal(plain(formatDateTime("2026-10-28T13:26:00Z")), "28-10-2026, 10:26 a. m.");
    // En julio Chile está en UTC-4.
    assert.equal(plain(formatDateTime("2026-07-01T15:00:00Z")), "01-07-2026, 11:00 a. m.");
  });

  test("el cambio de día depende de la zona horaria de Chile", () => {
    assert.equal(plain(formatDateTime("2026-10-29T02:30:00Z")), "28-10-2026, 11:30 p. m.");
  });
});

describe("formatExcerpt, shortId y formatContentType", () => {
  test("un fragmento que empieza en minúscula lleva puntos suspensivos", () => {
    assert.equal(formatExcerpt("asignada en el switch."), "…asignada en el switch.");
    assert.equal(formatExcerpt("Verifique el servicio."), "Verifique el servicio.");
    assert.equal(formatExcerpt("ñandú de red"), "…ñandú de red");
  });

  test("shortId toma los primeros 8 caracteres del UUID", () => {
    assert.equal(shortId("5b0e7c3a-2f1d-4c8e-9a6b-1d2e3f4a5b01"), "5b0e7c3a");
  });

  test("tipos de archivo conocidos y desconocidos", () => {
    assert.equal(formatContentType("application/pdf"), "PDF");
    assert.equal(formatContentType("text/markdown; charset=utf-8"), "Markdown");
    assert.equal(
      formatContentType("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
      "Word"
    );
    assert.equal(formatContentType("image/png"), "image/png");
  });
});
