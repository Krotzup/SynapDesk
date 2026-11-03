"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { notifyAuthChange, onAuthChange } from "@/lib/auth-sync";
import { isAuthenticationRequired } from "@/lib/errors";
import { authService } from "@/services/auth";
import { AuthUser } from "@/types";

type SessionState =
  { status: "checking" } | { status: "authenticated"; user: AuthUser } | { status: "unavailable" };

interface AuthContextValue {
  user: AuthUser;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/** Usuario de la sesión actual. Solo dentro de AuthProvider. */
export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth debe usarse dentro de AuthProvider");
  return value;
}

async function signOut() {
  // Si el backend no confirma el cierre (403, 503 o red), la sesión sigue abierta:
  // el error llega a quien llamó y no se redirige.
  await authService.logout();
  notifyAuthChange("logout");
}

/**
 * Verifica la sesión con /me antes de mostrar el panel.
 * - 401 AUTHENTICATION_REQUIRED: lleva al login.
 * - Error temporal (red, 5xx): muestra un aviso con Reintentar, sin cerrar la sesión.
 *
 * Es una protección de la interfaz, no de los datos: quien autoriza cada solicitud es el
 * backend. La verificación desde el servidor llegará con el proxy y el adaptador SSR.
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [state, setState] = useState<SessionState>({ status: "checking" });

  const verify = useCallback(
    () =>
      authService.me().then(
        ({ user }) => setState({ status: "authenticated", user }),
        (error: unknown) => {
          if (isAuthenticationRequired(error)) router.replace("/login");
          else setState({ status: "unavailable" });
        }
      ),
    [router]
  );

  useEffect(() => {
    void verify();
  }, [verify]);

  // Login o logout en esta u otra pestaña.
  useEffect(
    () =>
      onAuthChange((change) => {
        if (change === "logout") router.replace("/login");
        else void verify();
      }),
    [router, verify]
  );

  if (state.status === "authenticated") {
    return (
      <AuthContext.Provider value={{ user: state.user, signOut }}>{children}</AuthContext.Provider>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#F8FAFC] p-8">
      {state.status === "checking" ? (
        <p role="status" className="text-sm text-[#64748B]">
          Verificando sesión…
        </p>
      ) : (
        <div
          role="alert"
          className="max-w-md bg-white p-8 rounded-2xl border border-[#E2E8F0] shadow-sm text-center space-y-4"
        >
          <h1 className="text-lg font-bold text-[#0F172A]">No se pudo verificar tu sesión</h1>
          <p className="text-sm text-[#64748B]">
            El servicio no respondió. Puede ser algo temporal; tu sesión no se cerró.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-4 pt-2">
            <Button
              onClick={() => {
                setState({ status: "checking" });
                void verify();
              }}
            >
              Reintentar
            </Button>
            <Link href="/login" className="text-sm text-[#2563EB] font-medium hover:underline">
              Ir al inicio de sesión
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
