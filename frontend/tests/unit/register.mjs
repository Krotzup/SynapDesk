// Registra los hooks de tests/unit/hooks.mjs (se carga con --import desde "npm run test:unit").
import { register } from "node:module";

register("./hooks.mjs", import.meta.url);
