"use client";

import Link from "next/link";
import { useEffect, useTransition } from "react";
import { Button } from "@/components/ui/Button";

interface ErrorStateProps {
  error: Error & { digest?: string };
  retry: () => void;
}

/**
 * Contenido de la página de error general. En producción, Next.js no envía al navegador
 * el detalle de los errores del servidor: solo un mensaje genérico y el `digest`, que
 * permite encontrar el error en los registros del servidor.
 */
export function ErrorState({ error, retry }: ErrorStateProps) {
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="p-8 bg-[#F8FAFC] min-h-full">
      <div
        role="alert"
        className="max-w-xl mx-auto mt-16 bg-white p-8 rounded-2xl border border-[#E2E8F0] shadow-sm text-center space-y-4"
      >
        <div
          aria-hidden="true"
          className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-[#FEE2E2] text-xl font-bold text-[#EF4444]"
        >
          !
        </div>
        <h1 className="text-lg font-bold text-[#0F172A]">No se pudo cargar esta página</h1>
        <p className="text-sm text-[#64748B]">
          Ocurrió un problema al obtener la información. Puede ser algo temporal; intenta de nuevo.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-4 pt-2">
          <Button disabled={isPending} onClick={() => startTransition(() => retry())}>
            {isPending ? "Reintentando…" : "Reintentar"}
          </Button>
          <Link href="/inicio" className="text-sm text-[#2563EB] font-medium hover:underline">
            Ir al inicio
          </Link>
        </div>
        {error.digest && (
          <p className="text-xs text-[#94A3B8]">
            Código de referencia: <span className="font-mono">{error.digest}</span>
          </p>
        )}
      </div>
    </div>
  );
}
