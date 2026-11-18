"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/auth/AuthProvider";
import { Logo } from "@/components/layout/Logo";
import { Button } from "@/components/ui/Button";
import { buildQuery } from "@/lib/params";
import { TICKET_FILTERS_ENABLED } from "@/lib/ticket-filters";
import { Role } from "@/types";

// Límite provisional del texto de búsqueda; el contrato aún no define uno para GET /tickets.
const SEARCH_MAX_LENGTH = 200;

const roleLabels: Record<Role, string> = {
  admin: "Administrador",
  agent: "Agente",
};

// AuthUser no incluye el nombre: las iniciales salen del correo ("laura.silva@…" → "LS").
function initialsFromEmail(email: string): string {
  const parts = email
    .split("@")[0]
    .split(/[._-]+/)
    .filter(Boolean);
  const letters = parts.length > 1 ? parts[0][0] + parts[1][0] : (parts[0] ?? "").slice(0, 2);
  return letters.toUpperCase();
}

interface HeaderProps {
  /** Si el menú lateral (Drawer bajo 1024 px) está abierto, y cómo abrirlo. */
  isNavOpen: boolean;
  onOpenNav: () => void;
}

export function Header({ isNavOpen, onOpenNav }: HeaderProps) {
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const userTriggerRef = useRef<HTMLButtonElement>(null);

  const router = useRouter();
  const [search, setSearch] = useState("");
  // En el teléfono el buscador es un ícono que despliega el campo a todo el ancho.
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const searchToggleRef = useRef<HTMLButtonElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const { user, signOut } = useAuth();
  const [isSigningOut, setIsSigningOut] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);

  useEffect(() => {
    if (isSearchOpen) searchInputRef.current?.focus();
  }, [isSearchOpen]);

  // La redirección al login la hace AuthProvider cuando se confirma el cierre.
  const handleLogout = async () => {
    setLogoutError(null);
    setIsSigningOut(true);
    try {
      await signOut();
    } catch {
      setLogoutError("No se pudo cerrar la sesión. Intenta de nuevo.");
      setIsSigningOut(false);
    }
  };

  const closeSearch = () => {
    setIsSearchOpen(false);
    searchToggleRef.current?.focus();
  };

  // Búsqueda general: empieza en la página 1 y sin otros filtros. El campo se vacía porque la
  // búsqueda queda a la vista en el campo de búsqueda del listado ("Limpiar filtros" la quita).
  // Vacío no hace nada, para no perder los filtros que ya estén aplicados.
  const handleSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const term = search.trim();
    if (!TICKET_FILTERS_ENABLED || !term) return;
    router.push(`/tickets${buildQuery({ search: term })}`);
    setSearch("");
    setIsSearchOpen(false);
  };

  return (
    <header className="relative z-50 flex h-16 shrink-0 items-center gap-2 border-b border-[#E2E8F0] bg-white px-4 sm:px-6 lg:px-8">
      {/* Bajo 1024 px el menú lateral se oculta: ☰ lo abre y el logo pasa a la cabecera. */}
      <div className="flex shrink-0 items-center gap-1 lg:hidden">
        <button
          type="button"
          onClick={onOpenNav}
          aria-label="Abrir menú"
          aria-expanded={isNavOpen}
          aria-controls="menu-principal"
          className="-ml-2 flex h-11 w-11 items-center justify-center rounded-xl text-[#475569] hover:bg-[#F1F5F9] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#2563EB]"
        >
          <svg
            className="h-6 w-6"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 6h16M4 12h16M4 18h16"
            />
          </svg>
        </button>
        <Logo tone="light" />
      </div>

      {/* Buscador: lleva al listado de tickets con la búsqueda textual */}
      <form
        id="busqueda-cabecera"
        role="search"
        // Nombre propio para distinguirlo de otras búsquedas de la página (p. ej. los filtros).
        aria-label="Búsqueda de la cabecera"
        onSubmit={handleSearch}
        onKeyDown={(event) => {
          if (event.key === "Escape" && isSearchOpen) closeSearch();
        }}
        className={[
          // Teléfono: oculto, o desplegado sobre la cabecera a todo el ancho.
          isSearchOpen ? "absolute inset-0 z-10 flex items-center gap-2 bg-white px-4" : "hidden",
          // Desde 640 px: siempre a la vista, ocupando el espacio libre.
          "sm:static sm:z-auto sm:flex sm:flex-1 sm:bg-transparent sm:px-0",
        ].join(" ")}
      >
        <div className="flex w-full max-w-md items-center gap-2 rounded-full border border-[#E2E8F0]/60 bg-[#F1F5F9] px-4 sm:py-2 focus-within:border-[#2563EB] focus-within:ring-2 focus-within:ring-[#2563EB]/20">
          {/* La lupa también envía la búsqueda, para quien usa clic o toque en vez de Enter. Gris
              #64748B: contraste 4,34:1 sobre el fondo (WCAG 2.2, contraste no textual ≥ 3:1). */}
          <button
            type="submit"
            aria-label="Buscar tickets"
            disabled={!TICKET_FILTERS_ENABLED}
            className="-ml-3 flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-[#64748B] transition-colors hover:text-[#2563EB] focus-visible:text-[#2563EB] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#2563EB] sm:-m-1 sm:h-auto sm:w-auto sm:p-1"
          >
            <svg
              className="h-4 w-4"
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
          </button>
          <input
            ref={searchInputRef}
            type="search"
            name="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            maxLength={SEARCH_MAX_LENGTH}
            // Desactivada junto con los filtros del listado, que es adonde lleva la búsqueda.
            disabled={!TICKET_FILTERS_ENABLED}
            placeholder={
              TICKET_FILTERS_ENABLED
                ? "Buscar tickets por título, área, usuario o ID..."
                : "Búsqueda de tickets: disponible próximamente"
            }
            className="w-full min-w-0 bg-transparent text-sm text-[#0F172A] placeholder-[#94A3B8] outline-none"
            // El botón se llama «Buscar tickets»; el campo, por su contenido.
            aria-label="Texto de búsqueda"
          />
        </div>
        <button
          type="button"
          onClick={closeSearch}
          aria-label="Cerrar búsqueda"
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-[#475569] hover:bg-[#F1F5F9] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#2563EB] sm:hidden"
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
      </form>

      {/* Teléfono: la lupa sola despliega el buscador (oculta mientras esté desactivado). */}
      <button
        ref={searchToggleRef}
        type="button"
        onClick={() => setIsSearchOpen(true)}
        aria-label="Abrir búsqueda"
        aria-expanded={isSearchOpen}
        aria-controls="busqueda-cabecera"
        className={`${TICKET_FILTERS_ENABLED ? "flex" : "hidden"} ml-auto h-11 w-11 items-center justify-center rounded-xl text-[#475569] hover:bg-[#F1F5F9] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#2563EB] sm:hidden`}
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
            d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z"
          />
        </svg>
      </button>

      {/* Perfil de usuario: el disparador abre un panel con el correo, el rol y Cerrar sesión */}
      <div
        className="relative ml-auto shrink-0"
        onKeyDown={(event) => {
          if (event.key === "Escape" && isUserMenuOpen) {
            setIsUserMenuOpen(false);
            userTriggerRef.current?.focus();
          }
        }}
      >
        <button
          ref={userTriggerRef}
          type="button"
          onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
          // El nombre incluye el correo visible (WCAG 2.5.3, etiqueta en el nombre).
          aria-label={`Menú de usuario: ${user.email}`}
          aria-expanded={isUserMenuOpen}
          aria-controls="menu-usuario"
          className="flex items-center gap-2.5 cursor-pointer rounded-full px-2.5 py-1.5 hover:bg-[#F1F5F9] transition-colors select-none outline-none focus-visible:ring-2 focus-visible:ring-[#2563EB]"
        >
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#6366F1] text-xs font-bold text-white">
            {initialsFromEmail(user.email)}
          </div>
          {/* Bajo 768 px solo el avatar: el correo y el rol están dentro del menú. */}
          <span className="hidden text-sm font-semibold text-[#0F172A] md:inline">
            {user.email}
          </span>
          <svg
            className={`h-4 w-4 text-[#94A3B8] transition-transform duration-200 ${isUserMenuOpen ? "rotate-180" : ""}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {isUserMenuOpen && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setIsUserMenuOpen(false)} />
            <div
              id="menu-usuario"
              className="absolute right-0 mt-2 w-56 rounded-2xl bg-white p-2 shadow-xl border border-[#E2E8F0] z-20 text-xs font-medium text-[#0F172A]"
            >
              <div className="px-3 py-2 border-b border-[#F1F5F9]">
                <p className="font-bold text-sm break-all">{user.email}</p>
                <p className="text-[#94A3B8] text-[11px] mt-0.5">{roleLabels[user.role]}</p>
              </div>
              <div className="pt-2">
                <Button
                  type="button"
                  variant="danger"
                  fullWidth
                  onClick={handleLogout}
                  disabled={isSigningOut}
                >
                  {isSigningOut ? "Cerrando sesión…" : "Cerrar sesión"}
                </Button>
                {logoutError && (
                  <p role="alert" className="px-3 py-1.5 text-[11px] text-[#B91C1C]">
                    {logoutError}
                  </p>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </header>
  );
}
