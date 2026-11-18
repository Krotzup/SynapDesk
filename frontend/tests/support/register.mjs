// Registra tests/support/hooks.mjs. Se carga con --import desde "npm run test:unit" y
// "npm run test:proxy".
import { register } from "node:module";

register("./hooks.mjs", import.meta.url);
