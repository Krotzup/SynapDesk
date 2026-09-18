"use client";

import { useState, useEffect } from "react";
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
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [notifications, setNotifications] = useState(mockNotifications);

  const unreadCount = notifications.filter((n) => n.unread).length;
  const router = useRouter();

  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [isDarkMode]);

  const toggleDarkMode = () => {
    setIsDarkMode(!isDarkMode);
  };

  const handleLogout = () => {
    setIsUserMenuOpen(false);
    router.push("/login");
  };

  const markAllAsRead = () => {
    setNotifications(notifications.map((n) => ({ ...n, unread: false })));
  };

  return (
    <header className="flex h-16 items-center justify-between border-b border-[#E2E8F0] dark:border-[#1E293B] bg-white dark:bg-[#0F172A] px-8 relative z-50 shrink-0 transition-colors">
      
      {/* Buscador sobre el panel principal */}
      <div className="flex items-center gap-2 rounded-full bg-[#F1F5F9] dark:bg-[#1E293B] px-4 py-2 w-full max-w-md border border-[#E2E8F0]/60 dark:border-transparent">
        <svg
          className="h-4 w-4 text-[#94A3B8] shrink-0"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z" />
        </svg>
        <input
          type="search"
          placeholder="Buscar tickets, usuarios, etc..."
          className="w-full bg-transparent text-sm text-[#0F172A] dark:text-white placeholder-[#94A3B8] outline-none"
        />
      </div>

      {/* Acciones e Perfil */}
      <div className="flex items-center gap-3 relative">
        <button
          onClick={toggleDarkMode}
          className="rounded-full p-2 text-[#64748B] dark:text-[#94A3B8] hover:bg-[#F1F5F9] dark:hover:bg-[#1E293B] transition-colors outline-none"
          aria-label="Cambiar Tema"
        >
          {isDarkMode ? (
            <svg className="h-5 w-5 text-[#F59E0B]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
          ) : (
            <svg className="h-5 w-5 text-[#64748B]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
            </svg>
          )}
        </button>

        {/* Notificaciones */}
        <div className="relative">
          <button
            onClick={() => {
              setIsNotifOpen(!isNotifOpen);
              setIsUserMenuOpen(false);
            }}
            className="relative rounded-full p-2 text-[#64748B] dark:text-[#94A3B8] hover:bg-[#F1F5F9] dark:hover:bg-[#1E293B] transition-colors outline-none"
            aria-label="Notificaciones"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6 6 0 10-12 0v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
            </svg>

            {unreadCount > 0 && (
              <span className="absolute top-1.5 right-1.5 flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#EF4444] opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-[#EF4444]"></span>
              </span>
            )}
          </button>

          {isNotifOpen && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setIsNotifOpen(false)} />
              <div className="absolute right-0 mt-2 w-80 sm:w-96 rounded-2xl bg-white dark:bg-[#0B132B] p-4 shadow-xl border border-[#E2E8F0] dark:border-[#1E293B] z-20 text-xs text-[#0F172A] dark:text-white">
                <div className="flex items-center justify-between border-b border-[#F1F5F9] dark:border-[#1E293B] pb-3 mb-2">
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold text-sm">Notificaciones</h3>
                    {unreadCount > 0 && (
                      <span className="bg-[#2563EB] text-white text-[10px] font-bold px-2 py-0.5 rounded-full">
                        {unreadCount} nuevas
                      </span>
                    )}
                  </div>
                  {unreadCount > 0 && (
                    <button onClick={markAllAsRead} className="text-[11px] font-semibold text-[#2563EB] hover:underline">
                      Marcar leídas
                    </button>
                  )}
                </div>
                <div className="divide-y divide-[#F1F5F9] dark:divide-[#1E293B] max-h-80 overflow-y-auto">
                  {notifications.map((item) => (
                    <div key={item.id} className={`py-3 px-2 rounded-xl ${item.unread ? "bg-[#EFF6FF]/60 dark:bg-[#1E3A8A]/30" : "hover:bg-[#F8FAFC] dark:hover:bg-[#1E293B]/50"}`}>
                      <div className="flex items-center justify-between font-bold mb-1">
                        <span>{item.title}</span>
                        <span className="text-[10px] font-normal text-[#94A3B8]">{item.time}</span>
                      </div>
                      <p className="text-[11px] text-[#64748B] dark:text-[#94A3B8] leading-relaxed">{item.desc}</p>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>

        {/* Perfil Usuario */}
        <div className="relative">
          <button
            onClick={() => {
              setIsUserMenuOpen(!isUserMenuOpen);
              setIsNotifOpen(false);
            }}
            className="flex items-center gap-2.5 cursor-pointer rounded-full px-2.5 py-1.5 hover:bg-[#F1F5F9] dark:hover:bg-[#1E293B] transition-colors select-none outline-none"
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#4F46E5] text-xs font-bold text-white">
              VG
            </div>
            <span className="text-sm font-semibold text-[#0F172A] dark:text-white">Valentina González</span>
            <svg className={`h-4 w-4 text-[#94A3B8] transition-transform duration-200 ${isUserMenuOpen ? "rotate-180" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {isUserMenuOpen && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setIsUserMenuOpen(false)} />
              <div className="absolute right-0 mt-2 w-56 rounded-2xl bg-white dark:bg-[#0B132B] p-2 shadow-xl border border-[#E2E8F0] dark:border-[#1E293B] z-20 text-xs font-medium text-[#0F172A] dark:text-white">
                <div className="px-3 py-2 border-b border-[#F1F5F9] dark:border-[#1E293B]">
                  <p className="font-bold text-sm">Valentina González</p>
                  <p className="text-[#94A3B8] text-[11px] mt-0.5">v.gonzalez@synapdesk.com</p>
                </div>
                <div className="py-1">
                  <Link href="/admin" onClick={() => setIsUserMenuOpen(false)} className="flex items-center gap-2.5 px-3 py-2 rounded-xl hover:bg-[#F1F5F9] dark:hover:bg-[#1E293B] text-[#475569] dark:text-[#94A3B8] hover:text-[#0F172A] dark:hover:text-white transition-colors">
                    ⚙️ Configuración
                  </Link>
                </div>
                <div className="border-t border-[#F1F5F9] dark:border-[#1E293B] pt-1">
                  <button onClick={handleLogout} className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl hover:bg-[#FEF2F2] dark:hover:bg-[#450A0A] text-[#EF4444] font-semibold transition-colors text-left">
                    🚪 Cerrar Sesión
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