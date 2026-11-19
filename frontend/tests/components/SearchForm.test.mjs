import assert from "node:assert/strict";
import { afterEach, describe, test } from "node:test";
import { createElement } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { router } from "next/navigation";
import { SearchForm } from "@/components/search/SearchForm";
import { buildQuery } from "@/lib/params";
import { MAX_QUERY_LENGTH } from "@/lib/search-params";
import { resetEnvironment } from "./helpers.mjs";

afterEach(resetEnvironment);

function renderForm(query = "", limit = 5) {
  render(createElement(SearchForm, { query, limit }));
}

const queryField = () => screen.getByLabelText("Consulta en lenguaje natural");
const limitField = () => screen.getByLabelText("Cantidad de fragmentos");
const submit = () => fireEvent.click(screen.getByRole("button", { name: "Buscar" }));

describe("SearchForm", () => {
  test("es una región de búsqueda con nombre propio y respeta el largo máximo", () => {
    renderForm();
    assert.ok(screen.getByRole("search", { name: "Búsqueda semántica" }));
    assert.equal(queryField().maxLength, MAX_QUERY_LENGTH);
  });

  test("envía la consulta recortada y el límite elegido", async () => {
    renderForm();
    fireEvent.change(queryField(), { target: { value: "  no puedo conectarme a la red  " } });
    fireEvent.change(limitField(), { target: { value: "10" } });
    router.calls.length = 0; // el cambio de límite ya envía; aquí interesa el envío del formulario
    submit();
    await waitFor(() =>
      assert.deepEqual(router.calls, [
        ["push", `/busqueda${buildQuery({ q: "no puedo conectarme a la red", limit: "10" })}`],
      ])
    );
  });

  test("con la consulta vacía, el destino no lleva q", async () => {
    renderForm();
    fireEvent.change(queryField(), { target: { value: "   " } });
    submit();
    await waitFor(() =>
      assert.deepEqual(router.calls, [["push", `/busqueda${buildQuery({ q: "", limit: "5" })}`]])
    );
    assert.doesNotMatch(router.calls[0][1], /q=/);
  });

  test("cambiar la cantidad de fragmentos envía de inmediato con el nuevo límite", async () => {
    renderForm("vpn", 5);
    fireEvent.change(limitField(), { target: { value: "20" } });
    await waitFor(() =>
      assert.deepEqual(router.calls, [
        ["push", `/busqueda${buildQuery({ q: "vpn", limit: "20" })}`],
      ])
    );
  });

  test("«Limpiar» aparece solo cuando hay una consulta", () => {
    renderForm();
    assert.equal(screen.queryByRole("link", { name: "Limpiar" }), null);
    resetEnvironment();
    renderForm("vpn");
    assert.equal(screen.getByRole("link", { name: "Limpiar" }).getAttribute("href"), "/busqueda");
  });
});
