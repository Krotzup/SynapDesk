// Sustituto de "next/navigation" para las pruebas de componentes. Registra las navegaciones en
// lugar de hacerlas; cada prueba lo revisa y lo limpia con resetRouter().
export const router = { calls: [] };

const record =
  (method) =>
  (...args) =>
    router.calls.push([method, ...args]);

const instance = {
  push: record("push"),
  replace: record("replace"),
  refresh: record("refresh"),
  back: record("back"),
  forward: record("forward"),
  prefetch: () => {},
};

export function useRouter() {
  return instance;
}

export function resetRouter() {
  router.calls.length = 0;
}

export function usePathname() {
  return "/";
}

export function useSearchParams() {
  return new URLSearchParams();
}
