"use client";

import "./globals.css";
import { ErrorState } from "@/components/layout/ErrorState";

// Respaldo cuando falla el layout raíz o una vista sin página de error propia (como el
// login). Reemplaza al layout raíz, por eso define su propio <html> y <body>.
export default function GlobalError(props: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  return (
    <html lang="es" className="h-full antialiased">
      <body className="h-full bg-[#F8FAFC] font-sans">
        <title>Error | SynapDesk</title>
        <ErrorState {...props} />
      </body>
    </html>
  );
}
