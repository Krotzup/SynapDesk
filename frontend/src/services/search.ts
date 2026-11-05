import { api } from "@/lib/api";
import { USE_MOCKS } from "@/lib/config";
import { searchMock } from "@/mocks/search";
import { parseSearchResponse } from "@/lib/search-contract";
import type { SearchResponse } from "@/lib/search-contract";
export type { SearchResponse } from "@/lib/search-contract";

interface SearchRequest {
  query: string;
  limit?: number;
}

const searchApi = {
  // Fragmentos de la base de conocimientos más cercanos a la consulta
  semantic: (query: string, limit = 5): Promise<SearchResponse> =>
    api
      .postSameOrigin<SearchResponse, SearchRequest>("/search", { query, limit })
      .then(parseSearchResponse),
};

export type SearchService = typeof searchApi;

export const searchService: SearchService = USE_MOCKS ? searchMock : searchApi;
