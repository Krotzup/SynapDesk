"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getAuthGeneration, onAuthChange } from "@/lib/auth-sync";
import { isApiError, isAuthenticationRequired } from "@/lib/errors";
import { emptySearchMessage, groupSearchResults } from "@/lib/search-contract";
import type { SearchResponse } from "@/lib/search-contract";
import type { SearchLimit } from "@/lib/search-params";
import { searchService } from "@/services/search";
import { Button } from "@/components/ui/Button";
import { SearchResultCard } from "./SearchResultCard";

type State =
  | { kind: "loading" }
  | { kind: "success"; response: SearchResponse }
  | { kind: "error"; message: string };

export function SearchResults({ query, limit }: { query: string; limit: SearchLimit }) {
  const router = useRouter();
  const [state, setState] = useState<State>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [spanishFirst, setSpanishFirst] = useState(false);
  useEffect(() => {
    let cancelled = false;
    const generation = getAuthGeneration();
    void searchService.semantic(query, limit).then(
      (response) => {
        if (!cancelled && generation === getAuthGeneration())
          setState({ kind: "success", response });
      },
      (error: unknown) => {
        if (cancelled || generation !== getAuthGeneration()) return;
        if (isAuthenticationRequired(error)) router.replace("/login");
        setState({
          kind: "error",
          message: isApiError(error)
            ? error.error.message
            : "No fue posible comunicarse con el servicio de búsqueda.",
        });
      }
    );
    const unsubscribe = onAuthChange(() =>
      setState({ kind: "error", message: "La sesión cambió. Vuelve a realizar la búsqueda." })
    );
    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, [query, limit, attempt, router]);

  if (state.kind === "loading")
    return (
      <div role="status" aria-live="polite" aria-busy="true" className="space-y-4 animate-pulse">
        {[0, 1, 2].map((index) => (
          <div key={index} className="h-32 bg-white border border-[#E2E8F0] rounded-2xl" />
        ))}
        <span className="sr-only">Buscando fragmentos…</span>
      </div>
    );
  if (state.kind === "error")
    return (
      <section
        role="alert"
        className="bg-white border border-[#E2E8F0] rounded-2xl p-8 text-center space-y-4"
      >
        <h2 className="text-lg font-bold text-[#0F172A]">No se pudo completar la búsqueda</h2>
        <p className="text-sm text-[#475569]">{state.message}</p>
        <Button
          type="button"
          variant="secondary"
          onClick={() => {
            setState({ kind: "loading" });
            setAttempt((value) => value + 1);
          }}
        >
          Reintentar
        </Button>
      </section>
    );
  if (state.response.status !== "results") {
    const notice = emptySearchMessage(state.response.status);
    return (
      <section
        role="status"
        className="bg-white border border-[#E2E8F0] rounded-2xl p-8 text-center space-y-3"
      >
        <h2 className="text-lg font-bold text-[#0F172A]">{notice.title}</h2>
        <p className="text-sm text-[#475569]">{notice.message}</p>
      </section>
    );
  }
  const groups = groupSearchResults(state.response.items, spanishFirst);
  return (
    <section className="space-y-4" aria-label="Resultados de la búsqueda">
      <p className="text-sm text-[#475569]">
        {state.response.items.length}{" "}
        {state.response.items.length === 1 ? "fragmento encontrado" : "fragmentos encontrados"} en{" "}
        {groups.length} {groups.length === 1 ? "documento" : "documentos"}.
      </p>
      <label className="flex items-center gap-2 text-sm text-[#475569]">
        <input
          type="checkbox"
          checked={spanishFirst}
          onChange={(event) => setSpanishFirst(event.target.checked)}
        />
        Mostrar primero los documentos en español
      </label>
      <p className="text-xs text-[#3730A3] bg-[#EEF2FF] border border-[#C7D2FE] rounded-xl px-4 py-2.5">
        La similitud mide la cercanía entre tu consulta y cada fragmento según el modelo. Un valor
        mayor indica más relación. Revisa los fragmentos y su fuente antes de aplicarlos.
      </p>
      {groups.map((group) => (
        <SearchResultCard key={group.document.documentId} group={group} />
      ))}
    </section>
  );
}
