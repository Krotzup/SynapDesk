// Hooks adicionales de las pruebas de componentes: fuera de Next no hay App Router, así que
// "next/navigation" y "next/link" se sustituyen por versiones mínimas (ver los stubs).
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const stub = (file) => ({ url: pathToFileURL(path.join(here, file)).href, shortCircuit: true });

export async function resolve(specifier, context, next) {
  if (specifier === "next/navigation") return stub("next-navigation-stub.mjs");
  if (specifier === "next/server") return stub("next-server-stub.mjs");
  if (specifier === "next/link") return stub("next-link-stub.mjs");
  return next(specifier, context);
}
