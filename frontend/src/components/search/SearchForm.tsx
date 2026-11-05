"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { Button } from "@/components/ui/Button";
import { buildQuery } from "@/lib/params";
import { MAX_QUERY_LENGTH, SEARCH_LIMITS, SearchLimit } from "@/lib/search-params";

const fieldClass =
  "bg-[#F8FAFC] border border-[#E2E8F0] text-sm rounded-xl px-4 py-2.5 text-[#0F172A] outline-none focus:border-[#2563EB]";

interface SearchFormProps {
  query: string;
  limit: SearchLimit;
}

/**
 * Consulta en lenguaje natural. La consulta y la cantidad viven en la URL para que
 * una búsqueda se pueda recargar o compartir.
 */
export function SearchForm({ query, limit }: SearchFormProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  // Una consulta vacía vuelve al estado inicial en lugar de bloquear el envío.
  function apply(form: HTMLFormElement) {
    const data = new FormData(form);
    const q = String(data.get("q") ?? "").trim();
    startTransition(() => router.push(`/busqueda${buildQuery({ q, limit: data.get("limit") })}`));
  }

  return (
    <form
      role="search"
      aria-busy={isPending}
      onSubmit={(event) => {
        event.preventDefault();
        apply(event.currentTarget);
      }}
      className={`flex flex-col sm:flex-row gap-3 transition-opacity ${isPending ? "opacity-60" : ""}`}
    >
      <label htmlFor="semantic-query" className="sr-only">
        Consulta en lenguaje natural
      </label>
      <input
        id="semantic-query"
        name="q"
        type="search"
        maxLength={MAX_QUERY_LENGTH}
        defaultValue={query}
        placeholder="Describe un problema concreto, por ejemplo: no puedo conectarme a la red"
        className={`${fieldClass} flex-1 placeholder-[#94A3B8]`}
      />

      <label htmlFor="semantic-limit" className="sr-only">
        Cantidad de resultados
      </label>
      <select
        id="semantic-limit"
        name="limit"
        defaultValue={limit}
        onChange={(event) => apply(event.currentTarget.form!)}
        className={fieldClass}
      >
        {SEARCH_LIMITS.map((option) => (
          <option key={option} value={option}>
            {option} resultados
          </option>
        ))}
      </select>

      <Button type="submit" variant="primary">
        Buscar
      </Button>

      {query && (
        <Link
          href="/busqueda"
          className="self-center text-sm font-medium text-[#64748B] hover:text-[#0F172A]"
        >
          Limpiar
        </Link>
      )}
    </form>
  );
}
