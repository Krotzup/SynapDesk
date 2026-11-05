"use client";

import { useAuth } from "@/components/auth/AuthProvider";

/** Saludo con el usuario de la sesión. AuthUser no tiene nombre, por eso se muestra el correo. */
export function WelcomeGreeting() {
  const { user } = useAuth();

  return (
    <div className="space-y-2">
      <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">¡Hola! 👋</h1>
      <p className="text-sm text-[#94A3B8] max-w-xl">
        Te damos la bienvenida a SynapDesk. Aquí tienes un resumen de las solicitudes y de la base
        de conocimientos.
      </p>
      <p className="text-xs text-[#CBD5E1]">
        Sesión iniciada como{" "}
        <span className="font-semibold text-white break-all">{user.email}</span>
      </p>
    </div>
  );
}
