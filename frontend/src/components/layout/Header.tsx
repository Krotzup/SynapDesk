export function Header() {
  return (
    <header className="flex h-14 items-center justify-between border-b border-gray-200 bg-white px-6">
      <span className="text-sm text-gray-500">Plataforma inteligente de soporte TI</span>

      {/* Área de usuario — se implementa cuando se defina autenticación */}
      <div className="flex items-center gap-3">
        <span className="text-sm text-gray-700">Usuario</span>
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gray-200 text-xs font-medium text-gray-600">
          U
        </div>
      </div>
    </header>
  );
}
