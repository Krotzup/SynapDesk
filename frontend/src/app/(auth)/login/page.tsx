import { Button } from "@/components/ui/Button";

export default function LoginPage() {
  return (
    <div className="w-full max-w-sm space-y-8">
      {/* Logo y título */}
      <div className="text-center space-y-2">
        <div className="flex items-center justify-center gap-2 mb-4">
          <span className="text-[#2563EB] text-3xl font-bold">⚡</span>
          <span className="text-2xl font-semibold tracking-tight text-[#0F172A]">SynapDesk</span>
        </div>
        <p className="text-sm text-[#475569]">Iniciá sesión para continuar</p>
      </div>

      {/* Tarjeta */}
      <div className="rounded-xl border border-[#E2E8F0] bg-white p-8 shadow-sm">
        <form className="space-y-5">
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
              placeholder="agente@synapdesk.com"
              className="w-full rounded-lg border border-[#E2E8F0] bg-white px-3 py-2.5 text-sm text-[#0F172A] placeholder-[#94A3B8] outline-none transition-colors focus:border-[#2563EB] focus:ring-2 focus:ring-[#2563EB]/20"
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
              className="w-full rounded-lg border border-[#E2E8F0] bg-white px-3 py-2.5 text-sm text-[#0F172A] placeholder-[#94A3B8] outline-none transition-colors focus:border-[#2563EB] focus:ring-2 focus:ring-[#2563EB]/20"
            />
          </div>

          <Button type="submit" fullWidth>
            Iniciar sesión
          </Button>
        </form>
      </div>
    </div>
  );
}
