import { LoginForm } from "@/components/auth/LoginForm";
import { USE_MOCKS } from "@/lib/config";
import { MOCK_PASSWORD, mockAuthAccounts } from "@/mocks/auth";

export default function LoginPage() {
  return (
    <div className="w-full max-w-sm space-y-8">
      {/* Logo y título */}
      <div className="text-center space-y-2">
        <div className="flex items-center justify-center gap-2 mb-4">
          <span className="text-[#2563EB] text-3xl font-bold">⚡</span>
          <span className="text-2xl font-semibold tracking-tight text-[#0F172A]">SynapDesk</span>
        </div>
        <p className="text-sm text-[#475569]">Inicia sesión para continuar</p>
      </div>

      {USE_MOCKS && (
        <p className="text-xs text-[#92400E] bg-[#FEF3C7] border border-[#FDE68A] rounded-xl px-4 py-2.5">
          <strong>Datos de ejemplo:</strong> el inicio de sesión es simulado y no protege la
          aplicación. Usa {mockAuthAccounts[0].email} o {mockAuthAccounts[1].email} con la
          contraseña {MOCK_PASSWORD}.
        </p>
      )}

      {/* Tarjeta */}
      <div className="rounded-xl border border-[#E2E8F0] bg-white p-8 shadow-sm">
        <LoginForm />
      </div>
    </div>
  );
}
