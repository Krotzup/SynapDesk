// Registra los hooks de tests/proxy/hooks.mjs (se carga con --import desde "npm run test:proxy").
import { register } from "node:module";

register("./hooks.mjs", import.meta.url);
