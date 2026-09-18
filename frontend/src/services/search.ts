import { api } from "@/lib/api";
import { SearchResult } from "@/types";

interface SearchRequest {
  query: string;
  limit?: number;
}

interface SearchResponse {
  items: SearchResult[];
}

export const searchService = {
  semantic: (query: string, limit = 5): Promise<SearchResponse> =>
    api.post<SearchResponse, SearchRequest>("/search", { query, limit }),
};
