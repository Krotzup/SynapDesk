import Link from "next/link";

const navItems = [
  { href: "/tickets", label: "Tickets" },
  { href: "/documentos", label: "Documentos" },
  { href: "/busqueda", label: "Búsqueda" },
  { href: "/metricas", label: "Métricas" },
  { href: "/admin", label: "Administración" },
];

export function Sidebar() {
  return (
    <aside className="flex h-full w-56 flex-col border-r border-gray-200 bg-white px-4 py-6">
      <span className="mb-8 px-2 text-lg font-semibold tracking-tight">SynapDesk</span>
      <nav className="flex flex-col gap-1">
        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="rounded-md px-3 py-2 text-sm text-gray-700 transition-colors hover:bg-gray-100 hover:text-gray-900"
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
