"use client";

import { ErrorState } from "@/components/layout/ErrorState";

// Página de error de las vistas del panel: el menú lateral y la cabecera siguen visibles.
export default function DashboardError(props: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  return <ErrorState {...props} />;
}
