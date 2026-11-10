import type { SearchResult } from "../types";

export type SearchStatus = "results" | "no_documents" | "insufficient_information";
export interface SearchResponse {
  status: SearchStatus;
  items: SearchResult[];
}

export interface SearchResultGroup {
  document: SearchResult;
  fragments: SearchResult[];
}

export function groupSearchResults(
  items: SearchResult[],
  spanishFirst = false
): SearchResultGroup[] {
  const byDocument = new Map<string, SearchResultGroup>();
  for (const item of items) {
    const group = byDocument.get(item.documentId);
    if (group) group.fragments.push(item);
    else byDocument.set(item.documentId, { document: item, fragments: [item] });
  }
  const groups = [...byDocument.values()];
  if (spanishFirst) {
    const spanish = (group: SearchResultGroup) => /^es(?:-|$)/i.test(group.document.language ?? "");
    groups.sort((a, b) => Number(spanish(b)) - Number(spanish(a)));
  }
  return groups;
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function safeSourceUrl(value: unknown): string | null {
  if (typeof value !== "string" || value.length > 2000 || /\s/.test(value)) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password ? value : null;
  } catch {
    return null;
  }
}

export function parseSearchResponse(value: unknown): SearchResponse {
  if (!value || typeof value !== "object") throw new Error("Respuesta de búsqueda inválida.");
  const response = value as SearchResponse;
  if (
    !["results", "no_documents", "insufficient_information"].includes(response.status) ||
    !Array.isArray(response.items) ||
    response.items.length > 20 ||
    (response.status === "results") !== response.items.length > 0
  ) {
    throw new Error("Respuesta de búsqueda inválida.");
  }
  for (const item of response.items) {
    if (
      !item ||
      typeof item !== "object" ||
      !uuid.test(item.documentId) ||
      !uuid.test(item.documentChunkId) ||
      typeof item.title !== "string" ||
      typeof item.excerpt !== "string" ||
      typeof item.score !== "number" ||
      !Number.isFinite(item.score) ||
      item.score < -1.00001 ||
      item.score > 1.00001 ||
      (item.sourceUrl !== undefined && !safeSourceUrl(item.sourceUrl)) ||
      (item.language !== undefined && !/^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$/.test(item.language))
    ) {
      throw new Error("Respuesta de búsqueda inválida.");
    }
  }
  return response;
}

export function emptySearchMessage(status: Exclude<SearchStatus, "results">) {
  return status === "no_documents"
    ? {
        title: "La base de conocimientos está vacía",
        message: "Todavía no hay documentos disponibles para buscar.",
      }
    : {
        title: "Información insuficiente",
        message:
          "La búsqueda no encontró fragmentos con similitud suficiente. Agrega el sistema afectado, el mensaje de error o lo que ya intentaste y vuelve a buscar. También puedes solicitar apoyo a un especialista.",
      };
}
