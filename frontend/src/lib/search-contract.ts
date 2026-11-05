import type { SearchResult } from "../types";

export type SearchStatus = "results" | "no_documents" | "insufficient_information";
export interface SearchResponse {
  status: SearchStatus;
  items: SearchResult[];
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
          "Los documentos disponibles no ofrecen una coincidencia suficiente. Describe el problema con otras palabras o solicita apoyo a un especialista.",
      };
}
