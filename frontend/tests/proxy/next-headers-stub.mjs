// Sustituto de next/headers para las pruebas: la cookie de la "petición" la fija cada prueba.
export async function headers() {
  return new Headers(globalThis.__requestCookie ? { cookie: globalThis.__requestCookie } : {});
}
