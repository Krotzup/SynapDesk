// Registra los hooks compartidos y los de componentes, y prepara un DOM de jsdom antes de que se
// cargue React. Se carga con --import desde "npm run test:components".
import { register } from "node:module";
import { JSDOM } from "jsdom";

register("./hooks.mjs", import.meta.url);
register("./component-hooks.mjs", import.meta.url);

const dom = new JSDOM("<!doctype html><html><body></body></html>", {
  url: "http://localhost:3000/",
  pretendToBeVisual: true,
});
const { window } = dom;

// Globales del navegador que usan React y Testing Library. Los que Node ya trae (fetch, URL,
// AbortController, etc.) se conservan.
const ASSIGNED = new Set(["window", "document", "navigator"]);
for (const key of Object.getOwnPropertyNames(window)) {
  if (ASSIGNED.has(key) || key in globalThis || key.startsWith("_")) continue;
  Object.defineProperty(globalThis, key, {
    configurable: true,
    get: () => window[key],
  });
}
for (const key of ASSIGNED) {
  Object.defineProperty(globalThis, key, { configurable: true, value: window[key] });
}

// auth-sync abre un BroadcastChannel que mantendría vivo el proceso de pruebas.
globalThis.BroadcastChannel = undefined;
// Indica a React que las pruebas envuelven las actualizaciones en act() (Testing Library lo hace).
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
