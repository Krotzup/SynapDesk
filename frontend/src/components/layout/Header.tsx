"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const mockNotifications = [
  {
    id: 1,
    title: "Nuevo ticket asignado",
    desc: "Se te asignó el ticket #TCK-4827 de Base de Datos.",
    time: "Hace 5 min",
    unread: true,
  },
  {
    id: 2,
    title: "Respuesta del Asistente IA",
    desc: "El motor RAG generó una recomendación para #TCK-4826.",
    time: "Hace 20 min",
    unread: true,
  },
];

export function Header() {
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const [isNotifOpen, setIsNotifOpen] = useState(false);
  const [notifications, setNotifications] = useState(mockNotifications);

  const unreadCount = notifications.filter((n) => n.unread).length;
  const router = useRouter();

  const handleLogout = () => {
    setIsUserMenuOpen(false);
    router.push("/login");
  };

  const markAllAsRead = () => {
    setNotifications(notifications.map((n) => ({ ...n, unread: false })));
  };

  return (
    <header className="flex h-16 items-center justify-between border-b border-[#E2E8F0] bg-white px-8 relative z-50 shrink-0">
      {/* Buscador */}
      <div className="flex items-center gap-2 rounded-full bg-[#F1F5F9] px-4 py-2 w-full max-w-md border border-[#E2E8F0]/60">
        <svg
          className="h-4 w-4 text-[#94A3B8] shrink-0"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z"
          />
        </svg>
        <input
          type="search"
          placeholder="Buscar tickets, usuarios, etc..."
          className="w-full bg-transparent text-sm text-[#0F172A] placeholder-[#94A3B8] outline-none"
          aria-label="Buscar"
        />
      </div>

      {/* Acciones y perfil */}
      <div className="flex items-center gap-3 relative">
        {/* Notificaciones */}
        <div className="relative">
          <button
            onClick={() => {
              setIsNotifOpen(!isNotifOpen);
              setIsUserMenuOpen(false);
            }}
            className="relative rounded-full p-2 text-[#64748B] hover:bg-[#F1F5F9] transition-colors outline-none"
            aria-label="Notificaciones"
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
                d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6 6 0 10-12 0v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
              />
            </svg>
            {unreadCount > 0 && (
              <span className="absolute top-1.5 right-1.5 flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#EF4444] opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-[#EF4444]" />
              </span>
            )}
          </button>

          {isNotifOpen && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setIsNotifOpen(false)} />
              <div className="absolute right-0 mt-2 w-80 sm:w-96 rounded-2xl bg-white p-4 shadow-xl border border-[#E2E8F0] z-20 text-xs text-[#0F172A]">
                <div className="flex items-center justify-between border-b border-[#F1F5F9] pb-3 mb-2">
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold text-sm">Notificaciones</h3>
                    {unreadCount > 0 && (
                      <span className="bg-[#2563EB] text-white text-[10px] font-bold px-2 py-0.5 rounded-full">
                        {unreadCount} nuevas
                      </span>
                    )}
                  </div>
                  {unreadCount > 0 && (
                    <button
                      onClick={markAllAsRead}
                      className="text-[11px] font-semibold text-[#2563EB] hover:underline"
                    >
                      Marcar leídas
                    </button>
                  )}
                </div>
                <div className="divide-y divide-[#F1F5F9] max-h-80 overflow-y-auto">
                  {notifications.map((item) => (
                    <div
                      key={item.id}
                      className={`py-3 px-2 rounded-xl ${item.unread ? "bg-[#EFF6FF]/60" : "hover:bg-[#F8FAFC]"}`}
                    >
                      <div className="flex items-center justify-between font-bold mb-1">
                        <span>{item.title}</span>
                        <span className="text-[10px] font-normal text-[#94A3B8]">{item.time}</span>
                      </div>
                      <p className="text-[11px] text-[#64748B] leading-relaxed">{item.desc}</p>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>

        {/* Perfil de usuario */}
        <div className="relative">
          <button
            onClick={() => {
              setIsUserMenuOpen(!isUserMenuOpen);
              setIsNotifOpen(false);
            }}
            className="flex items-center gap-2.5 cursor-pointer rounded-full px-2.5 py-1.5 hover:bg-[#F1F5F9] transition-colors select-none outline-none"
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#6366F1] text-xs font-bold text-white">
              VG
            </div>
            <span className="text-sm font-semibold text-[#0F172A]">Valentina González</span>
            <svg
              className={`h-4 w-4 text-[#94A3B8] transition-transform duration-200 ${isUserMenuOpen ? "rotate-180" : ""}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 9l-7 7-7-7"
              />
            </svg>
          </button>

          {isUserMenuOpen && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setIsUserMenuOpen(false)} />
              <div className="absolute right-0 mt-2 w-56 rounded-2xl bg-white p-2 shadow-xl border border-[#E2E8F0] z-20 text-xs font-medium text-[#0F172A]">
                <div className="px-3 py-2 border-b border-[#F1F5F9]">
                  <p className="font-bold text-sm">Valentina González</p>
                  <p className="text-[#94A3B8] text-[11px] mt-0.5">v.gonzalez@synapdesk.com</p>
                </div>
                <div className="py-1">
                  <Link
                    href="/admin"
                    onClick={() => setIsUserMenuOpen(false)}
                    className="flex items-center gap-2.5 px-3 py-2 rounded-xl hover:bg-[#F1F5F9] text-[#475569] hover:text-[#0F172A] transition-colors"
                  >
                    ⚙️ Configuración
                  </Link>
                </div>
                <div className="border-t border-[#F1F5F9] pt-1">
                  <button
                    onClick={handleLogout}
                    className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl hover:bg-[#FEF2F2] text-[#EF4444] font-semibold transition-colors text-left"
                  >
                    🚪 Cerrar sesión
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
