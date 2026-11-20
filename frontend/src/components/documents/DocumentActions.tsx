"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { Button } from "@/components/ui/Button";
import { ErrorReference } from "@/components/ui/ErrorReference";
import { USE_MOCKS } from "@/lib/config";
import { describeError, ErrorDescription } from "@/lib/errors";
import { documentsService } from "@/services/documents";

const field = "block w-full rounded-lg border border-[#CBD5E1] p-2 text-sm text-[#0F172A]";

function ActionError({ error }: { error: ErrorDescription | null }) {
  return (
    error && (
      <div role="alert" className="text-sm text-[#B91C1C]">
        <p>{error.message}</p>
        <ErrorReference requestId={error.requestId} />
      </div>
    )
  );
}

export function DocumentUpload() {
  const { user } = useAuth();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ErrorDescription | null>(null);
  if (user.role !== "admin") return null;
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const data = new FormData(event.currentTarget);
    const file = data.get("file");
    if (
      !(file instanceof File) ||
      file.size === 0 ||
      file.size > 65536 ||
      !/\.(txt|md)$/i.test(file.name)
    ) {
      setError({
        kind: "validation",
        message: "Elige un archivo .txt o .md en UTF-8, de hasta 64 KiB.",
        requestId: null,
      });
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const saved = await documentsService.upload(data);
      router.push(`/documentos/${saved.id}`);
      router.refresh();
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section
      className="bg-white border border-[#E2E8F0] rounded-2xl p-4 space-y-3"
      aria-labelledby="subir-documento"
    >
      <h2 id="subir-documento" className="font-bold text-[#0F172A]">
        Subir documento
      </h2>
      <p className="text-sm text-[#64748B]">
        Archivos .txt o .md en UTF-8, hasta 64 KiB. La carga procesa e indexa el texto.
      </p>
      {USE_MOCKS ? (
        <p className="text-sm text-[#92400E]">
          La carga requiere el backend real. Los datos de ejemplo no se indexan.
        </p>
      ) : (
        <form onSubmit={submit} className="space-y-3" aria-busy={busy}>
          <fieldset disabled={busy} className="space-y-3">
            <label className="block text-sm text-[#475569]">
              Título
              <input name="title" required maxLength={150} className={field} />
            </label>
            <label className="block text-sm text-[#475569]">
              Descripción (opcional)
              <textarea name="description" maxLength={2000} className={field} />
            </label>
            <label className="block text-sm text-[#475569]">
              Archivo
              <input
                name="file"
                type="file"
                required
                accept=".txt,.md,text/plain,text/markdown"
                className={field}
              />
            </label>
            <Button type="submit" disabled={busy}>
              {busy ? "Procesando documento…" : "Subir e indexar"}
            </Button>
          </fieldset>
          <ActionError error={error} />
        </form>
      )}
    </section>
  );
}

export function RetireDocument({ documentId }: { documentId: string }) {
  const { user } = useAuth();
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ErrorDescription | null>(null);
  if (user.role !== "admin" || USE_MOCKS) return null;
  async function retire() {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await documentsService.delete(documentId);
      router.push("/documentos");
      router.refresh();
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="space-y-3">
      {!confirming ? (
        <Button variant="secondary" onClick={() => setConfirming(true)}>
          Retirar documento
        </Button>
      ) : (
        <div className="space-y-2">
          <p className="text-sm text-[#475569]">
            El documento dejará de participar en búsquedas nuevas. Las recomendaciones anteriores
            conservarán sus fuentes. ¿Retirar este documento?
          </p>
          <div className="flex gap-3">
            <Button disabled={busy} onClick={retire}>
              {busy ? "Retirando…" : "Confirmar retiro"}
            </Button>
            <Button variant="secondary" disabled={busy} onClick={() => setConfirming(false)}>
              Cancelar
            </Button>
          </div>
        </div>
      )}
      <ActionError error={error} />
    </div>
  );
}
