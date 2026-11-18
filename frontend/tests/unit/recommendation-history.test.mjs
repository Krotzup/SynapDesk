import assert from "node:assert/strict";
import { describe, test } from "node:test";
import { splitRecommendations } from "@/lib/recommendation-history";

const rec = (id, createdAt, status = "pending") => ({
  id,
  ticketId: "t1",
  content: `Contenido ${id}`,
  status,
  sources: [],
  createdAt,
});

describe("splitRecommendations", () => {
  test("sin recomendaciones", () => {
    assert.deepEqual(splitRecommendations([]), { latest: null, previous: [] });
  });

  test("la más reciente es la vigente; las anteriores van de la más nueva a la más antigua", () => {
    const list = [
      rec("b", "2026-10-28T12:10:00Z", "modified"),
      rec("c", "2026-10-28T13:26:00Z"),
      rec("a", "2026-10-28T11:05:00Z", "rejected"),
    ];
    const { latest, previous } = splitRecommendations(list);
    assert.equal(latest.id, "c");
    assert.deepEqual(
      previous.map((item) => item.id),
      ["b", "a"]
    );
  });

  test("compara instantes, no textos: fracción de segundo y desfase horario", () => {
    // Mismo día: 18:35:00Z < 18:35:00.5Z < 15:36:00-03:00 (= 18:36:00Z). Por texto quedaría al revés.
    const list = [
      rec("z", "2026-09-11T18:35:00Z"),
      rec("fraccion", "2026-09-11T18:35:00.5Z"),
      rec("desfase", "2026-09-11T15:36:00-03:00"),
    ];
    const { latest, previous } = splitRecommendations(list);
    assert.equal(latest.id, "desfase");
    assert.deepEqual(
      previous.map((item) => item.id),
      ["fraccion", "z"]
    );
  });

  test("con fechas iguales el orden es estable (desempata el id)", () => {
    const at = "2026-10-28T13:00:00Z";
    const forward = splitRecommendations([rec("a", at), rec("b", at), rec("c", at)]);
    const backward = splitRecommendations([rec("c", at), rec("b", at), rec("a", at)]);
    assert.equal(forward.latest.id, "c");
    assert.deepEqual(forward, backward);
  });

  test("no modifica la lista recibida ni el contenido original", () => {
    const list = [rec("a", "2026-10-28T13:00:00Z"), rec("b", "2026-10-28T11:00:00Z")];
    const copy = structuredClone(list);
    splitRecommendations(list);
    assert.deepEqual(list, copy);
  });
});
