import { api } from "@/lib/api";
import { USE_MOCKS } from "@/lib/config";
import { searchMock } from "@/mocks/search";
import { SearchResult } from "@/types";

interface SearchRequest {
  query: string;
  limit?: number;
}

export interface SearchResponse {
  items: SearchResult[];
}

const searchApi = {
  // Fragmentos de la base de conocimientos más cercanos a la consulta
  semantic: (query: string, limit = 5): Promise<SearchResponse> =>
    api.post<SearchResponse, SearchRequest>("/search", { query, limit }),
};

export type SearchService = typeof searchApi;

export const searchService: SearchService = USE_MOCKS ? searchMock : searchApi;
