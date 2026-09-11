import { api } from "@/lib/api";
import { SearchResult } from "@/types";

export const searchService = {
  semantic: (query: string): Promise<SearchResult[]> => api.post("/search", { query }),
};
