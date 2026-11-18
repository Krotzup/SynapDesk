import { RefObject, useEffect } from "react";

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

function focusables(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
    (element) => element.getClientRects().length > 0
  );
}

interface DialogOptions {
  /** true mientras el Drawer está abierto y se comporta como diálogo modal. */
  active: boolean;
  /** Debe ser estable (useCallback): si cambia, el foco volvería al disparador. */
  onClose: () => void;
  containerRef: RefObject<HTMLElement | null>;
  /** Elemento que recibe el foco al abrir; si falta, el primero enfocable. */
  initialFocusRef?: RefObject<HTMLElement | null>;
}

/**
 * Comportamiento de teclado de un Drawer modal: al abrir mueve el foco adentro, Tab y Shift+Tab
 * no salen de él, Esc lo cierra y, al cerrar, el foco vuelve al elemento que lo abrió.
 */
export function useDialog({ active, onClose, containerRef, initialFocusRef }: DialogOptions) {
  useEffect(() => {
    if (!active) return;
    const container = containerRef.current;
    if (!container) return;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    (initialFocusRef?.current ?? focusables(container)[0] ?? container).focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !container) return;
      const items = focusables(container);
      if (items.length === 0) {
        event.preventDefault();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const current = document.activeElement;
      if (!container.contains(current)) {
        event.preventDefault();
        first.focus();
      } else if (event.shiftKey && current === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && current === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      // Si el disparador ya no está en la página (por ejemplo, tras navegar), no se mueve el foco.
      if (opener?.isConnected) opener.focus();
    };
  }, [active, onClose, containerRef, initialFocusRef]);
}
