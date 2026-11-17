"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";

function IconHome() {
  return (
    <svg className="h-5 w-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
    <svg className="h-5 w-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
    <svg className="h-5 w-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
    <svg className="h-5 w-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
    <svg className="h-5 w-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
}

export function Sidebar({ statusSummary }: SidebarProps) {
  const pathname = usePathname();

  return (
    <aside className="flex h-full w-[270px] shrink-0 flex-col bg-[#0F172A] pt-4 pb-6 select-none">
      {/* Logo dentro del Sidebar */}
      <div className="flex items-center gap-3 px-6 py-2 mb-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#2563EB] shrink-0 shadow-sm">
          <svg className="h-5 w-5 text-white" fill="currentColor" viewBox="0 0 24 24">
            <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
          </svg>
        </div>
        <span className="text-[19px] font-extrabold tracking-tight text-white">SynapDesk</span>
      </div>

      <nav className="flex flex-col gap-1 px-3">
        {navItems.map(({ href, label, Icon }) => {
          const isActive = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
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
        <p className="mb-4 text-[10px] font-bold uppercase tracking-wider text-[#64748B]">ESTADO</p>
        {statusSummary}
      </div>
    </aside>
  );
}
