"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { notifyAuthChange } from "@/lib/auth-sync";
import { isApiError } from "@/lib/errors";
import { authService } from "@/services/auth";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const inputClass =
  "w-full rounded-lg border border-[#E2E8F0] bg-white px-3 py-2.5 text-sm text-[#0F172A] placeholder-[#94A3B8] outline-none transition-colors focus:border-[#2563EB] focus:ring-2 focus:ring-[#2563EB]/20 disabled:bg-[#F8FAFC]";

// Mensajes según los códigos confirmados del contrato de autenticación V1.
function loginErrorMessage(error: unknown): string {
  const code = isApiError(error) ? error.error.code : null;
  switch (code) {
    case "INVALID_CREDENTIALS":
      return "Correo o contraseña incorrectos.";
    case "RATE_LIMITED":
      return "Demasiados intentos. Espera unos minutos antes de volver a intentar.";
    case "CSRF_INVALID":
    case "ORIGIN_INVALID":
      return "No se pudo validar la solicitud. Recarga la página e intenta de nuevo.";
    default:
      // SERVICE_UNAVAILABLE, otros 5xx y fallos de red.
      return "El servicio no está disponible en este momento. Intenta nuevamente.";
  }
}

export function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Con una sesión válida, el login no tiene sentido: se va al inicio.
  // Si /me falla por otro motivo (401 o error temporal), se muestra el formulario.
  useEffect(() => {
    authService.me().then(
      () => router.replace("/inicio"),
      () => undefined
    );
  }, [router]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email.trim() || !password) {
      setError("Ingresa tu correo y tu contraseña.");
      return;
    }
    if (!EMAIL_PATTERN.test(email.trim())) {
      setError("Ingresa un correo electrónico válido.");
      return;
    }

    setError(null);
    setIsSubmitting(true);
    try {
      // La contraseña se envía tal cual: el contrato prohíbe recortarla o normalizarla.
      await authService.login({ email: email.trim(), password });
      notifyAuthChange("login");
      router.replace("/inicio");
    } catch (loginError) {
      setError(loginErrorMessage(loginError));
      setIsSubmitting(false);
    }
  }

  return (
    <form className="space-y-5" onSubmit={handleSubmit} noValidate>
      <div className="space-y-1.5">
        <label htmlFor="email" className="block text-sm font-medium text-[#0F172A]">
          Correo electrónico
        </label>
        <input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          required
          placeholder="agente@synapdesk.local"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          disabled={isSubmitting}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? "login-error" : undefined}
          className={inputClass}
        />
      </div>

      <div className="space-y-1.5">
        <label htmlFor="password" className="block text-sm font-medium text-[#0F172A]">
          Contraseña
        </label>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          placeholder="••••••••"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          disabled={isSubmitting}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? "login-error" : undefined}
          className={inputClass}
        />
      </div>

      {error && (
        <p
          id="login-error"
          role="alert"
          className="text-sm text-[#B91C1C] bg-[#FEF2F2] border border-[#FECACA] rounded-lg px-3 py-2"
        >
          {error}
        </p>
      )}

      <Button type="submit" fullWidth disabled={isSubmitting}>
        {isSubmitting ? "Iniciando sesión…" : "Iniciar sesión"}
      </Button>
    </form>
  );
}
