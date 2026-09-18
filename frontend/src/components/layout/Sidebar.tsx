"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const statusItems = [
  { label: "Todos", count: 24, color: "#38BDF8" },
  { label: "Abiertos", count: 12, color: "#38BDF8" },
  { label: "En Proceso", count: 7, color: "#F59E0B" },
  { label: "Resueltos", count: 5, color: "#10B981" },
];

function IconHome() {
  return (
    <svg className="h-5 w-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
    </svg>
  );
}

function IconTickets() {
  return (
    <svg className="h-5 w-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
    </svg>
  );
}

function IconBooks() {
  return (
    <svg className="h-5 w-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
    </svg>
  );
}

function IconChart() {
  return (
    <svg className="h-5 w-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
    </svg>
  );
}

function IconSettings() {
  return (
    <svg className="h-5 w-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  );
}

const navItems = [
  { href: "/inicio", label: "Inicio", Icon: IconHome },
  { href: "/tickets", label: "Tickets", Icon: IconTickets },
  { href: "/documentos", label: "Base de Conocimientos", Icon: IconBooks },
  { href: "/metricas", label: "Reportes", Icon: IconChart },
  { href: "/admin", label: "Configuración", Icon: IconSettings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-full w-[270px] shrink-0 flex-col bg-[#0F172A] dark:bg-[#090D16] pt-4 pb-6 select-none border-r border-transparent dark:border-[#1E293B]">
      
      {/* Logo dentro del Sidebar */}
      <div className="flex items-center gap-3 px-6 py-2 mb-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#2563EB] shrink-0 shadow-sm">
          <svg className="h-5 w-5 text-white" fill="currentColor" viewBox="0 0 24 24">
            <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
          </svg>
        </div>
        <span className="text-[19px] font-extrabold tracking-tight text-white">
          Synapdesk
        </span>
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
                  ? "bg-[#1E3A8A]/60 dark:bg-[#1E40AF] text-white font-semibold"
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
        <div className="flex flex-col gap-3">
          {statusItems.map((item) => (
            <div key={item.label} className="flex items-center justify-between text-[13px]">
              <div className="flex items-center gap-3">
                <span
                  className="h-2 w-2 rounded-full shrink-0"
                  style={{ backgroundColor: item.color }}
                  aria-hidden="true"
                />
                <span className="text-[#94A3B8]">{item.label}</span>
              </div>
              <span className="min-w-[24px] text-center text-[11px] font-bold text-[#94A3B8] bg-[#1E293B] rounded-full px-2 py-0.5">
                {item.count}
              </span>
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}