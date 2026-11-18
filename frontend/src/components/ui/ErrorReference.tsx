/** Código de referencia de un error (requestId del contrato), seleccionable para copiarlo. */
export function ErrorReference({ requestId }: { requestId: string | null }) {
  if (!requestId) return null;
  return (
    <p className="mt-1 text-[11px] text-[#7F1D1D]">
      Código de referencia: <span className="font-mono select-all break-all">{requestId}</span>
    </p>
  );
}
