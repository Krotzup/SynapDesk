import { api } from "@/lib/api";
import { Document, PaginatedResponse, PaginationParams } from "@/types";

export const documentsService = {
  getAll: (params?: PaginationParams): Promise<PaginatedResponse<Document>> => {
    const query = new URLSearchParams(params as Record<string, string>).toString();
    return api.get(`/documents${query ? `?${query}` : ""}`);
  },

  getById: (id: string): Promise<Document> => api.get(`/documents/${id}`),

  // La carga usa multipart/form-data, no JSON — se implementa cuando se defina el backend
  upload: (formData: FormData): Promise<Document> => {
    return fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/documents`, {
      method: "POST",
      body: formData,
    }).then((res) => res.json());
  },

  delete: (id: string): Promise<void> => api.delete(`/documents/${id}`),
};
