import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
for (const args of [
  [path.join(root, "node_modules/typescript/bin/tsc"), "-p", "tsconfig.search-tests.json"],
  ["--test", path.join(__dirname, "search.mjs")],
]) {
  const result = spawnSync(process.execPath, args, { cwd: root, stdio: "inherit" });
  if (result.status !== 0) process.exit(result.status ?? 1);
}
