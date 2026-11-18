// Hooks de módulos para las pruebas unitarias: permiten ejecutar los .ts de src/ con Node, sin
// Next ni dependencias nuevas. Resuelven el alias "@/" y los imports relativos sin extensión, y
// transpilan TypeScript con la versión del proyecto (elimina los imports que solo son tipos).
// Es el mismo enfoque que tests/proxy del PR #30; al integrarse ambos se pueden unificar.
import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const frontend = path.resolve(here, "../..");
const src = path.join(frontend, "src");
const ts = createRequire(path.join(frontend, "package.json"))("typescript");

export async function resolve(specifier, context, next) {
  if (specifier.startsWith("@/")) {
    return {
      url: pathToFileURL(path.join(src, `${specifier.slice(2)}.ts`)).href,
      shortCircuit: true,
    };
  }
  if (
    specifier.startsWith(".") &&
    !path.extname(specifier) &&
    context.parentURL?.startsWith("file:")
  ) {
    const file = path.resolve(path.dirname(fileURLToPath(context.parentURL)), `${specifier}.ts`);
    if (existsSync(file)) return { url: pathToFileURL(file).href, shortCircuit: true };
  }
  return next(specifier, context);
}

export async function load(url, context, next) {
  if (!url.endsWith(".ts")) return next(url, context);
  const file = fileURLToPath(url);
  const { outputText } = ts.transpileModule(await readFile(file, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
    fileName: file,
  });
  return { format: "module", source: outputText, shortCircuit: true };
}
