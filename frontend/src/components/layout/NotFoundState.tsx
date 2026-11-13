import Link from "next/link";
import { buttonClassName } from "@/components/ui/Button";

interface NotFoundLink {
  href: string;
  label: string;
}

interface NotFoundStateProps {
  title: string;
  message: string;
  /** Acción principal, con aspecto de botón. */
  primaryLink: NotFoundLink;
  /** Acción secundaria opcional, como enlace de texto. */
  secondaryLink?: NotFoundLink;
}

/**
 * Contenido de las páginas "no encontrado" (404). Mismo formato que ErrorState, sin Reintentar:
 * volver a pedir la página no cambia el resultado.
 */
export function NotFoundState({ title, message, primaryLink, secondaryLink }: NotFoundStateProps) {
  return (
    <div className="p-8 bg-[#F8FAFC] min-h-full">
      <div className="max-w-xl mx-auto mt-16 bg-white p-8 rounded-2xl border border-[#E2E8F0] shadow-sm text-center space-y-4">
        <div
          aria-hidden="true"
          className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-[#E0E7FF] text-sm font-bold text-[#4338CA]"
        >
          404
        </div>
        <h1 className="text-lg font-bold text-[#0F172A]">{title}</h1>
        <p className="text-sm text-[#64748B]">{message}</p>
        <div className="flex flex-wrap items-center justify-center gap-4 pt-2">
          <Link href={primaryLink.href} className={buttonClassName()}>
            {primaryLink.label}
          </Link>
          {secondaryLink && (
            <Link
              href={secondaryLink.href}
              className="text-sm text-[#2563EB] font-medium hover:underline"
            >
              {secondaryLink.label}
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
