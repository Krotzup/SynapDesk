import { RetryButton } from "@/components/ui/RetryButton";

/** Error de un bloque de Inicio: el resto de la página sigue disponible. */
export function SectionError({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl border border-[#FECACA] bg-[#FEF2F2] px-4 py-3"
    >
      <p className="text-xs text-[#991B1B]">{message}</p>
      <RetryButton />
    </div>
  );
}
