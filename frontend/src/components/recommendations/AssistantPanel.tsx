"use client";

import { ReactNode, useCallback, useRef, useState } from "react";
import { useDialog } from "@/lib/use-dialog";
import { useMediaQuery } from "@/lib/use-media-query";

/**
 * Panel del Asistente IA en el detalle del ticket. Desde 1280 px va a la derecha del detalle;
 * bajo 1280 px es un Drawer que se abre con un botón fijo en el borde derecho (en el teléfono,
 * a pantalla completa). El contenido se monta una sola vez, así no se pierde lo que se esté
 * editando al abrir o cerrar el Drawer.
 */
export function AssistantPanel({ children }: { children: ReactNode }) {
  const isInline = useMediaQuery("(min-width: 1280px)");
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const close = useCallback(() => setOpen(false), []);
  // Al pasar a 1280 px o más el panel deja de ser un Drawer: se cierra, para que no reaparezca
  // solo (y robe el foco) si la ventana vuelve a achicarse, por ejemplo al girar una tablet.
  if (isInline && open) setOpen(false);
  const modal = !isInline && open;
  useDialog({ active: modal, onClose: close, containerRef: panelRef, initialFocusRef: closeRef });

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-expanded={open}
        aria-controls="asistente-ia"
        className="fixed right-0 top-1/2 z-30 flex min-h-11 w-11 -translate-y-1/2 items-center justify-center rounded-l-xl bg-[#4338CA] px-2 py-4 text-sm font-semibold text-white shadow-lg [writing-mode:vertical-rl] hover:bg-[#3730A3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#2563EB] focus-visible:ring-offset-2 xl:hidden"
      >
        <span aria-hidden="true" className="mb-1">
          🤖
        </span>
        Asistente IA
      </button>

      {/* Fondo oscurecido del Drawer: tocar afuera lo cierra. */}
      {open && (
        <div
          className="fixed inset-0 z-[60] bg-[#0F172A]/50 xl:hidden"
          onClick={close}
          aria-hidden="true"
        />
      )}

      {/* div con rol explícito: role="dialog" no se admite en <aside>. El elemento no cambia al
          abrir o cerrar, así que el contenido no se vuelve a montar. */}
      <div
        id="asistente-ia"
        ref={panelRef}
        role={modal ? "dialog" : "complementary"}
        aria-modal={modal || undefined}
        aria-labelledby="asistente-ia-titulo"
        className={[
          "space-y-5 bg-[#EEF2FF] p-6 border-[#818CF8]",
          // Bajo 1280 px: Drawer desde la derecha; en el teléfono ocupa toda la pantalla.
          "fixed inset-y-0 right-0 z-[70] w-full overflow-y-auto border-l shadow-xl sm:w-[420px]",
          // Al abrir, visible de inmediato (para poder darle el foco); al cerrar, se oculta al
          // terminar el deslizamiento.
          open
            ? "visible translate-x-0 transition-transform duration-200"
            : "invisible translate-x-full transition-[transform,visibility] duration-200",
          // Desde 1280 px: columna derecha del detalle, como antes.
          "xl:visible xl:static xl:z-auto xl:w-auto xl:translate-x-0 xl:overflow-visible xl:rounded-2xl xl:border xl:shadow-sm",
        ].join(" ")}
      >
        <div className="flex items-center justify-between gap-2">
          <h2
            id="asistente-ia-titulo"
            className="flex items-center gap-2 text-lg font-bold text-[#4338CA]"
          >
            <span aria-hidden="true">🤖</span> Asistente IA
          </h2>
          <button
            ref={closeRef}
            type="button"
            onClick={close}
            aria-label="Cerrar Asistente IA"
            className="-mr-2 flex h-11 w-11 items-center justify-center rounded-xl text-[#4338CA] hover:bg-[#E0E7FF] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#2563EB] xl:hidden"
          >
            <svg
              className="h-5 w-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
        {children}
      </div>
    </>
  );
}
