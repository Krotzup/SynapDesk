"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode, useRef } from "react";
import { Logo } from "@/components/layout/Logo";
import { useDialog } from "@/lib/use-dialog";
import { useMediaQuery } from "@/lib/use-media-query";

function IconHome() {
  return (
    <svg
      className="h-5 w-5 shrink-0"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.8}
        d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"
      />
    </svg>
  );
}

function IconTickets() {
  return (
    <svg
      className="h-5 w-5 shrink-0"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.8}
        d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
      />
    </svg>
  );
}

function IconSearch() {
  return (
    <svg
      className="h-5 w-5 shrink-0"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.8}
        d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
      />
    </svg>
  );
}

function IconBooks() {
  return (
    <svg
      className="h-5 w-5 shrink-0"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.8}
        d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
      />
    </svg>
  );
}

function IconChart() {
  return (
    <svg
      className="h-5 w-5 shrink-0"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.8}
        d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
      />
    </svg>
  );
}

const navItems = [
  { href: "/inicio", label: "Inicio", Icon: IconHome },
  { href: "/tickets", label: "Tickets", Icon: IconTickets },
  { href: "/busqueda", label: "Búsqueda semántica", Icon: IconSearch },
  { href: "/documentos", label: "Base de Conocimientos", Icon: IconBooks },
  { href: "/metricas", label: "Reportes", Icon: IconChart },
];

interface SidebarProps {
  // Conteos por estado; se reciben ya renderizados desde el servidor.
  statusSummary: ReactNode;
  /** Bajo 1024 px el menú es un Drawer: abierto o cerrado. Desde 1024 px siempre está a la vista. */
  open: boolean;
  onClose: () => void;
}

export function Sidebar({ statusSummary, open, onClose }: SidebarProps) {
  const pathname = usePathname();
  const isDrawer = !useMediaQuery("(min-width: 1024px)");
  const panelRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const modal = isDrawer && open;
  useDialog({ active: modal, onClose, containerRef: panelRef, initialFocusRef: closeRef });

  return (
    <>
      {/* Fondo oscurecido del Drawer: tocar afuera lo cierra. */}
      {open && (
        <div
          className="fixed inset-0 z-[60] bg-[#0F172A]/50 lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}
      <aside
        id="menu-principal"
        ref={panelRef}
        role={modal ? "dialog" : undefined}
        aria-modal={modal || undefined}
        aria-label={modal ? "Menú principal" : undefined}
        // Al elegir un enlace (también los del resumen por estado) el Drawer se cierra.
        onClick={(event) => {
          if ((event.target as HTMLElement).closest("a")) onClose();
        }}
        className={[
          "flex flex-col bg-[#0F172A] pt-4 pb-6 select-none",
          // Bajo 1024 px: Drawer desde la izquierda, 85 % del ancho y como máximo 300 px.
          "fixed inset-y-0 left-0 z-[70] w-[85%] max-w-[300px] overflow-y-auto",
          // Al abrir, visible de inmediato (para poder darle el foco); al cerrar, se oculta al
          // terminar el deslizamiento.
          open
            ? "visible translate-x-0 transition-transform duration-200"
            : "invisible -translate-x-full transition-[transform,visibility] duration-200",
          // Desde 1024 px: fijo en la columna izquierda, como siempre.
          "lg:visible lg:static lg:z-auto lg:h-full lg:w-[270px] lg:max-w-none lg:shrink-0 lg:translate-x-0",
        ].join(" ")}
      >
        <div className="flex items-center justify-between gap-2 pl-6 pr-3 py-2 mb-4">
          <Logo />
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label="Cerrar menú"
            className="flex h-11 w-11 items-center justify-center rounded-xl text-[#94A3B8] hover:bg-[#1E293B] hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#38BDF8] lg:hidden"
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

        <nav aria-label="Secciones" className="flex flex-col gap-1 px-3">
          {navItems.map(({ href, label, Icon }) => {
            const isActive = pathname === href || pathname.startsWith(href + "/");
            return (
              <Link
                key={href}
                href={href}
                aria-current={isActive ? "page" : undefined}
                className={[
                  "flex items-center gap-3 rounded-xl px-4 py-3 text-[14px] font-medium transition-all duration-150",
                  isActive
                    ? "bg-[#1E3A8A]/60 text-white font-semibold"
                    : "text-[#94A3B8] hover:bg-[#1E293B]/50 hover:text-white",
                ].join(" ")}
              >
                <span className={isActive ? "text-[#38BDF8]" : "text-[#94A3B8]"}>
                  <Icon />
                </span>
                {label}
              </Link>
            );
          })}
        </nav>

        <div className="mx-5 my-6 h-px bg-[#1E293B]/60" />

        <div className="px-6">
          <p className="mb-4 text-[10px] font-bold uppercase tracking-wider text-[#64748B]">
            ESTADO
          </p>
          {statusSummary}
        </div>
      </aside>
    </>
  );
}
