import assert from "node:assert/strict";
import { afterEach, describe, test } from "node:test";
import { createElement } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { router } from "next/navigation";
import { LoginForm } from "@/components/auth/LoginForm";
import { authService } from "@/services/auth";
import { apiError, deferred, resetEnvironment, stubService } from "./helpers.mjs";

const USER = {
  user: {
    id: "5b0e2a47-3c1d-4f6e-9a8b-7c6d5e4f3a21",
    email: "agente@synapdesk.local",
    role: "agent",
  },
};

let stub;
afterEach(() => {
  stub?.restore();
  stub = undefined;
  resetEnvironment();
});

/** Sin sesión: /me responde 401 y se muestra el formulario. */
function withoutSession(login) {
  return stubService(authService, {
    me: async () => {
      throw apiError(401, "AUTHENTICATION_REQUIRED");
    },
    login,
  });
}

async function renderForm() {
  render(createElement(LoginForm));
  // Espera a que termine la consulta inicial de /me.
  await waitFor(() => assert.equal(stub.calls.me.length, 1));
}

function fill(email, password) {
  fireEvent.change(screen.getByLabelText("Correo electrónico"), { target: { value: email } });
  fireEvent.change(screen.getByLabelText("Contraseña"), { target: { value: password } });
}

const submit = () => fireEvent.click(screen.getByRole("button", { name: "Iniciar sesión" }));

describe("LoginForm", () => {
  test("con una sesión válida, va directo al inicio", async () => {
    stub = stubService(authService, { me: async () => USER, login: async () => USER });
    render(createElement(LoginForm));
    await waitFor(() => assert.deepEqual(router.calls, [["replace", "/inicio"]]));
    assert.equal(stub.calls.login.length, 0);
  });

  test("pide correo y contraseña antes de enviar", async () => {
    stub = withoutSession(async () => USER);
    await renderForm();
    submit();

    const alert = screen.getByRole("alert");
    assert.equal(alert.textContent, "Ingresa tu correo y tu contraseña.");
    assert.equal(alert.id, "login-error");
    assert.equal(
      screen.getByLabelText("Correo electrónico").getAttribute("aria-describedby"),
      "login-error"
    );
    assert.equal(stub.calls.login.length, 0);
  });

  test("rechaza un correo con formato inválido sin enviarlo", async () => {
    stub = withoutSession(async () => USER);
    await renderForm();
    fill("agente@synapdesk", "demo1234");
    submit();

    assert.equal(screen.getByRole("alert").textContent, "Ingresa un correo electrónico válido.");
    assert.equal(stub.calls.login.length, 0);
  });

  test("recorta el correo, envía la contraseña tal cual y va al inicio", async () => {
    stub = withoutSession(async () => USER);
    await renderForm();
    fill("  agente@synapdesk.local  ", " demo 1234 ");
    submit();

    await waitFor(() => assert.deepEqual(router.calls, [["replace", "/inicio"]]));
    assert.deepEqual(stub.calls.login, [
      [{ email: "agente@synapdesk.local", password: " demo 1234 " }],
    ]);
  });

  test("mientras se envía: «Iniciando sesión…» y campos deshabilitados", async () => {
    const pending = deferred();
    stub = withoutSession(() => pending.promise);
    await renderForm();
    fill("agente@synapdesk.local", "demo1234");
    submit();

    const button = await screen.findByRole("button", { name: "Iniciando sesión…" });
    assert.equal(button.disabled, true);
    assert.equal(screen.getByLabelText("Correo electrónico").disabled, true);
    assert.equal(screen.getByLabelText("Contraseña").disabled, true);
    pending.resolve(USER);
    await waitFor(() => assert.equal(router.calls.length, 1));
  });

  test("credenciales incorrectas: mensaje genérico y formulario habilitado de nuevo", async () => {
    stub = withoutSession(async () => {
      throw apiError(401, "INVALID_CREDENTIALS");
    });
    await renderForm();
    fill("agente@synapdesk.local", "incorrecta");
    submit();

    const alert = await screen.findByRole("alert");
    assert.equal(alert.textContent, "Correo o contraseña incorrectos.");
    assert.equal(screen.getByLabelText("Contraseña").getAttribute("aria-invalid"), "true");
    assert.equal(screen.getByRole("button", { name: "Iniciar sesión" }).disabled, false);
    assert.equal(router.calls.length, 0);
  });

  const cases = [
    [429, "RATE_LIMITED", "Demasiados intentos. Espera unos minutos antes de volver a intentar."],
    [403, "CSRF_INVALID", "No se pudo validar la solicitud. Recarga la página e intenta de nuevo."],
    [
      403,
      "ORIGIN_INVALID",
      "No se pudo validar la solicitud. Recarga la página e intenta de nuevo.",
    ],
    [
      503,
      "SERVICE_UNAVAILABLE",
      "El servicio no está disponible en este momento. Intenta nuevamente.",
    ],
  ];
  for (const [status, code, message] of cases) {
    test(`${status} ${code}: «${message}»`, async () => {
      stub = withoutSession(async () => {
        throw apiError(status, code);
      });
      await renderForm();
      fill("agente@synapdesk.local", "demo1234");
      submit();

      assert.equal((await screen.findByRole("alert")).textContent, message);
      assert.equal(stub.calls.login.length, 1);
    });
  }
});
