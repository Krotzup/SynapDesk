export default function LoginPage() {
  return (
    <div className="w-full max-w-sm space-y-6">
      <div className="space-y-2 text-center">
        <h1 className="text-2xl font-semibold tracking-tight">SynapDesk</h1>
        <p className="text-sm text-gray-500">Iniciá sesión para continuar</p>
      </div>

      {/* Formulario — se implementa cuando el backend defina autenticación */}
      <form className="space-y-4">
        <div className="space-y-1">
          <label htmlFor="email" className="text-sm font-medium">
            Correo electrónico
          </label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            required
            placeholder="agente@synapdesk.com"
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm outline-none focus:border-gray-900 focus:ring-1 focus:ring-gray-900"
          />
        </div>

        <div className="space-y-1">
          <label htmlFor="password" className="text-sm font-medium">
            Contraseña
          </label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            placeholder="••••••••"
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm outline-none focus:border-gray-900 focus:ring-1 focus:ring-gray-900"
          />
        </div>

        <button
          type="submit"
          className="w-full rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700"
        >
          Iniciar sesión
        </button>
      </form>
    </div>
  );
}
