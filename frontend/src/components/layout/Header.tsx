"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/auth/AuthProvider";
import { Button } from "@/components/ui/Button";
import { buildQuery } from "@/lib/params";
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

export function Header() {
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);

  const router = useRouter();
  const [search, setSearch] = useState("");

  const { user, signOut } = useAuth();
  const [isSigningOut, setIsSigningOut] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);

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

  // Búsqueda general: empieza en la página 1 y sin otros filtros. El campo se vacía porque la
  // búsqueda queda a la vista en el campo de búsqueda del listado ("Limpiar filtros" la quita).
  // Vacío no hace nada, para no perder los filtros que ya estén aplicados.
  const handleSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const term = search.trim();
    if (!term) return;
    router.push(`/tickets${buildQuery({ search: term })}`);
    setSearch("");
  };

  return (
    <header className="flex h-16 items-center justify-between border-b border-[#E2E8F0] bg-white px-8 relative z-50 shrink-0">
      {/* Buscador: lleva al listado de tickets con la búsqueda textual */}
      <form
        role="search"
        // Nombre propio para distinguirlo de otras búsquedas de la página (p. ej. los filtros).
        aria-label="Búsqueda de la cabecera"
        onSubmit={handleSearch}
        className="flex items-center gap-2 rounded-full bg-[#F1F5F9] px-4 py-2 w-full max-w-md border border-[#E2E8F0]/60 focus-within:border-[#2563EB] focus-within:ring-2 focus-within:ring-[#2563EB]/20"
      >
        {/* La lupa también envía la búsqueda, para quien usa clic o toque en vez de Enter. Gris
            #64748B: contraste 4,34:1 sobre el fondo (WCAG 2.2, contraste no textual ≥ 3:1). */}
        <button
          type="submit"
          aria-label="Buscar tickets"
          className="-m-1 shrink-0 rounded-full p-1 text-[#64748B] transition-colors hover:text-[#2563EB] focus-visible:text-[#2563EB] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#2563EB]"
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
          type="search"
          name="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          maxLength={SEARCH_MAX_LENGTH}
          placeholder="Buscar tickets por título, área, usuario o ID..."
          className="w-full bg-transparent text-sm text-[#0F172A] placeholder-[#94A3B8] outline-none"
          // El botón se llama «Buscar tickets»; el campo, por su contenido.
          aria-label="Texto de búsqueda"
        />
      </form>

      {/* Perfil de usuario: el disparador abre un panel con el correo, el rol y Cerrar sesión */}
      <div className="relative">
        <button
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
          <span className="text-sm font-semibold text-[#0F172A]">{user.email}</span>
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
