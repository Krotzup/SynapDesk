interface LogoProps {
  /** "dark": texto blanco, para el menú lateral; "light": texto oscuro, para la cabecera. */
  tone?: "dark" | "light";
}

/** Logo de SynapDesk: aparece en el menú lateral y, cuando este se oculta, en la cabecera. */
export function Logo({ tone = "dark" }: LogoProps) {
  return (
    <span className="flex items-center gap-3">
      <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#2563EB] shrink-0 shadow-sm">
        <svg
          className="h-5 w-5 text-white"
          fill="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
        </svg>
      </span>
      <span
        className={`text-[19px] font-extrabold tracking-tight ${tone === "dark" ? "text-white" : "text-[#0F172A]"}`}
      >
        SynapDesk
      </span>
    </span>
  );
}
