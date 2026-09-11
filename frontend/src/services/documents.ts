import { api } from "@/lib/api";
import { Document } from "@/types";

export const documentsService = {
  getAll: (): Promise<Document[]> => api.get("/documents"),

  getById: (id: string): Promise<Document> => api.get(`/documents/${id}`),

  delete: (id: string): Promise<void> => api.delete(`/documents/${id}`),
};
