// Lanzador de "npm run test:proxy". Genera en una carpeta temporal una CA de prueba y certificados
// de servidor con openssl, ejecuta las pruebas con esa CA agregada solo a ese proceso de Node
// (NODE_EXTRA_CA_CERTS; no toca el almacén del equipo) y borra la carpeta al terminar.
// Requiere openssl en el PATH. No se guarda ninguna clave en el repositorio.
import { execFileSync, spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const frontend = path.resolve(here, "../..");
const dir = mkdtempSync(path.join(tmpdir(), "synapdesk-proxy-tls-"));
const file = (name) => path.join(dir, name);
const openssl = (...args) => execFileSync("openssl", args, { stdio: "pipe" });

const caConfig = [
  "[req]",
  "distinguished_name = dn",
  "x509_extensions = v3_ca",
  "[dn]",
  "[v3_ca]",
  "basicConstraints = critical, CA:TRUE",
  "keyUsage = critical, keyCertSign, cRLSign",
  "subjectKeyIdentifier = hash",
].join("\n");
writeFileSync(file("ca.cnf"), caConfig);

function createCa(name) {
  openssl(
    "req",
    "-x509",
    "-newkey",
    "rsa:2048",
    "-nodes",
    "-days",
    "2",
    "-keyout",
    file(`${name}.key`),
    "-out",
    file(`${name}.crt`),
    "-subj",
    `/CN=SynapDesk ${name} de prueba`,
    "-config",
    file("ca.cnf")
  );
}

// Certificado de servidor firmado por `ca` con el nombre alternativo indicado.
function createServerCert(name, ca, subjectAltName) {
  writeFileSync(
    file(`${name}.ext`),
    [
      `subjectAltName = ${subjectAltName}`,
      "basicConstraints = CA:FALSE",
      "keyUsage = digitalSignature, keyEncipherment",
      "extendedKeyUsage = serverAuth",
    ].join("\n")
  );
  openssl(
    "req",
    "-new",
    "-newkey",
    "rsa:2048",
    "-nodes",
    "-keyout",
    file(`${name}.key`),
    "-out",
    file(`${name}.csr`),
    "-subj",
    "/CN=backend de prueba"
  );
  openssl(
    "x509",
    "-req",
    "-in",
    file(`${name}.csr`),
    "-days",
    "2",
    "-CA",
    file(`${ca}.crt`),
    "-CAkey",
    file(`${ca}.key`),
    "-CAcreateserial",
    "-out",
    file(`${name}.crt`),
    "-extfile",
    file(`${name}.ext`)
  );
}

let status = 1;
try {
  createCa("ca");
  createCa("ca-ajena");
  createServerCert("servidor", "ca", "IP:127.0.0.1");
  createServerCert("servidor-otro-nombre", "ca", "DNS:otro-nombre.invalid");
  createServerCert("servidor-ca-ajena", "ca-ajena", "IP:127.0.0.1");

  const result = spawnSync(
    process.execPath,
    [
      "--conditions=react-server",
      "--import",
      "./tests/support/register.mjs",
      "--test",
      // Argumentos extra, por ejemplo: npm run test:proxy -- --test-name-pattern="SSR".
      ...process.argv.slice(2),
      "tests/proxy/proxy.test.mjs",
    ],
    {
      cwd: frontend,
      stdio: "inherit",
      env: { ...process.env, NODE_EXTRA_CA_CERTS: file("ca.crt"), PROXY_TEST_TLS_DIR: dir },
    }
  );
  status = result.status ?? 1;
} finally {
  rmSync(dir, { recursive: true, force: true });
}
process.exit(status);
