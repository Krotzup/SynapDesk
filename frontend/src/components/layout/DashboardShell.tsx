"use client";

import { usePathname } from "next/navigation";
import { ReactNode, useCallback, useState } from "react";
import { Header } from "@/components/layout/Header";
import { Sidebar } from "@/components/layout/Sidebar";
import { useMediaQuery } from "@/lib/use-media-query";

interface DashboardShellProps {
  statusSummary: ReactNode;
  children: ReactNode;
}

/**
 * Estructura del panel: menú lateral, cabecera y contenido. Guarda si el menú lateral está
 * abierto (solo cuenta bajo 1024 px, donde es un Drawer que se abre con ☰ en la cabecera).
 */
export function DashboardShell({ statusSummary, children }: DashboardShellProps) {
  const pathname = usePathname();
  const [isNavOpen, setIsNavOpen] = useState(false);
  const [navPath, setNavPath] = useState(pathname);
  const openNav = useCallback(() => setIsNavOpen(true), []);
  const closeNav = useCallback(() => setIsNavOpen(false), []);

  // Al cambiar de página (también con Atrás del navegador) el Drawer se cierra.
  if (pathname !== navPath) {
    setNavPath(pathname);
    setIsNavOpen(false);
  }

  // Desde 1024 px el menú está siempre a la vista: el Drawer se cierra, para que no reaparezca
  // solo si la ventana vuelve a achicarse (por ejemplo, al girar una tablet).
  const isWide = useMediaQuery("(min-width: 1024px)");
  if (isWide && isNavOpen) setIsNavOpen(false);

  return (
    <div className="flex h-screen overflow-hidden bg-[#F8FAFC]">
      <Sidebar statusSummary={statusSummary} open={isNavOpen} onClose={closeNav} />
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <Header isNavOpen={isNavOpen} onOpenNav={openNav} />
        <main className="flex-1 overflow-y-auto bg-[#F8FAFC]">{children}</main>
      </div>
    </div>
  );
}
