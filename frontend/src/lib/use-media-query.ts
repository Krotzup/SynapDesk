import { useCallback, useSyncExternalStore } from "react";

/**
 * Indica si la consulta de medios se cumple (por ejemplo, "(min-width: 1024px)"). En el servidor
 * devuelve false; el cliente la corrige al hidratar. Se usa solo para la semántica de los
 * Drawers: la visibilidad la deciden las clases responsivas, así no hay saltos al cargar.
 */
export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (onChange: () => void) => {
      const media = window.matchMedia(query);
      media.addEventListener("change", onChange);
      return () => media.removeEventListener("change", onChange);
    },
    [query]
  );
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(query).matches,
    () => false
  );
}
