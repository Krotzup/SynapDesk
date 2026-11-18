// Hooks de módulos compartidos por las pruebas unitarias, las del proxy y las de componentes: permiten
// ejecutar los .ts y .tsx de src/ con Node, sin Next. Resuelven el alias "@/" y los imports relativos
// sin extensión, sustituyen "next/headers" (la cookie la fija cada prueba) y "server-only" (vacío), y
// transpilan TypeScript y JSX con la versión del proyecto, que elimina los imports que solo son tipos.
import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const frontend = path.resolve(here, "../..");
const src = path.join(frontend, "src");
const ts = createRequire(path.join(frontend, "package.json"))("typescript");

const stub = (file) => ({ url: pathToFileURL(path.join(here, file)).href, shortCircuit: true });

export async function resolve(specifier, context, next) {
  if (specifier === "next/headers") return stub("next-headers-stub.mjs");
  if (specifier === "server-only") return stub("server-only-stub.mjs");
  if (specifier.startsWith("@/")) {
    const file = withExtension(path.join(src, specifier.slice(2)));
    return {
      url: pathToFileURL(file ?? `${path.join(src, specifier.slice(2))}.ts`).href,
      shortCircuit: true,
    };
  }
  if (
    specifier.startsWith(".") &&
    !path.extname(specifier) &&
    context.parentURL?.startsWith("file:")
  ) {
    const file = withExtension(
      path.resolve(path.dirname(fileURLToPath(context.parentURL)), specifier)
    );
    if (file) return { url: pathToFileURL(file).href, shortCircuit: true };
  }
  return next(specifier, context);
}

// Primero .ts y después .tsx (componentes).
function withExtension(base) {
  return [`${base}.ts`, `${base}.tsx`].find((file) => existsSync(file));
}

export async function load(url, context, next) {
  if (!url.endsWith(".ts") && !url.endsWith(".tsx")) return next(url, context);
  const file = fileURLToPath(url);
  const { outputText } = ts.transpileModule(await readFile(file, "utf8"), {
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2022,
      jsx: ts.JsxEmit.ReactJSX,
    },
    fileName: file,
  });
  return { format: "module", source: outputText, shortCircuit: true };
}
