// Utilidades comunes de las pruebas de componentes.
import { cleanup } from "@testing-library/react";
import { resetRouter } from "next/navigation";

export const REQUEST_ID = "8d1f3c52-7a4e-4b9a-9c2d-5e6f7a8b9c0d";

/** Error con la forma de ApiError (lib/api.ts), como lo entrega el cliente HTTP. */
export function apiError(status, code, details = null) {
  return {
    status,
    error: { code, message: "Mensaje del backend.", details, requestId: REQUEST_ID },
  };
}

/** Promesa que la prueba resuelve o rechaza cuando quiere, para revisar el estado intermedio. */
export function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

/**
 * Reemplaza métodos de un servicio durante una prueba y registra sus llamadas.
 * Devuelve las llamadas y una función para restaurar los métodos originales.
 */
export function stubService(service, methods) {
  const original = {};
  const calls = {};
  for (const [name, implementation] of Object.entries(methods)) {
    original[name] = service[name];
    calls[name] = [];
    service[name] = (...args) => {
      calls[name].push(args);
      return implementation(...args);
    };
  }
  return {
    calls,
    restore: () => Object.assign(service, original),
  };
}

/** Limpia el DOM y el registro del router entre pruebas. */
export function resetEnvironment() {
  cleanup();
  resetRouter();
}
