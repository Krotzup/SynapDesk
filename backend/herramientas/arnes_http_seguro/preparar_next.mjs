// Compila copias exactas del PR con TypeScript instalado; Next ejecuta sus imports reales.
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const [controlFile] = process.argv.slice(2);
const control = JSON.parse(fs.readFileSync(controlFile, "utf8"));
const require = createRequire(path.join(control.repo, "frontend/package.json"));
const ts = require("typescript");
const project = control.project;
function write(name, content) {
  const file = path.join(project, name);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, content);
}
for (const [source, target] of Object.entries(control.sources)) {
  const input = fs.readFileSync(source, "utf8");
  const output = ts.transpileModule(input, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
  });
  write(target, output.outputText);
}
write("package.json", JSON.stringify({ private: true, type: "module" }));
write("jsconfig.json", JSON.stringify({ compilerOptions: { baseUrl: ".", paths: { "@/*": ["./*"] } } }));
write("next.config.mjs", `export default {devIndicators:false, agentRules:false, webpack(config) {
  config.resolve.modules.unshift(${JSON.stringify(path.join(control.repo, "frontend/node_modules"))});
  return config;
}};`);
write("app/layout.jsx", "export default function Layout({children}){return <html><body>{children}</body></html>}");
write("app/page.jsx", `import {getTransport} from '@/lib/transport/server';
export const dynamic='force-dynamic';
export default async function Page(){const t=await getTransport();
const r=await t.fetch(t.baseUrl+'/api/v1/ensayo/eco',{headers:t.headers,cache:'no-store'});
return <pre id="observado">{JSON.stringify({status:r.status,body:await r.json()})}</pre>}`);
write("app/ssr-servicio/page.jsx", `import {getTransport} from '@/lib/transport/server';
export const dynamic='force-dynamic';
export default async function Page(){const t=await getTransport();
const r=await t.fetch(t.baseUrl+'/api/v1/ensayo/servicio',{headers:t.headers,cache:'no-store'});
return <pre id="observado">{JSON.stringify({status:r.status,body:await r.json()})}</pre>}`);
write("app/ensayo-listo/route.js", `export function GET(){return Response.json({harness:${JSON.stringify(control.identity)}})}`);
// SUSTITUTO DE ENSAYO: no es código del PR30. Destinos fijos, sin IP ni usuario.
write("app/ensayo-canal/[operation]/route.js", `import 'server-only';
import fs from 'node:fs';
export const dynamic='force-dynamic';
async function handler(request,{params}){
 const {operation}=await params;
 const paths={servicio:'/api/v1/ensayo/servicio',csrf:'/api/v1/auth/csrf',controles:'/api/v1/ensayo/controles'};
 if(!Object.hasOwn(paths,operation))return new Response(null,{status:404});
 if(request.method!==(operation==='controles'?'POST':'GET'))return new Response(null,{status:405});
 const c=JSON.parse(fs.readFileSync(process.env.HARNESS_PRIVATE_FILE,'utf8'));
 const h=new Headers();
 for(const name of ['origin','sec-fetch-site','cookie','x-csrf-token']){
   const v=request.headers.get(name);if(v!==null)h.set(name,v);
 }
 h.set('Authorization','Bearer '+c.tokens[0]);
 try{const r=await fetch(c.backend+paths[operation],{method:request.method,headers:h,redirect:'error',cache:'no-store',signal:AbortSignal.timeout(5000)});
 return new Response(await r.arrayBuffer(),{status:r.status,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
 }catch{return Response.json({error:{code:'SERVICE_UNAVAILABLE',message:'Fallo del canal de ensayo.',details:null,requestId:crypto.randomUUID()}},{status:503,headers:{'Cache-Control':'no-store'}})}
}
export {handler as GET,handler as POST};`);
console.log(JSON.stringify({ prepared: true, typescript: ts.version, sourceCount: Object.keys(control.sources).length }));
