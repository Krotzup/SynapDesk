import { api } from "@/lib/api";
import { buildQuery } from "@/lib/params";
import { Document, PaginatedResponse, PaginationParams } from "@/types";

export const documentsService = {
  getAll: (params?: PaginationParams): Promise<PaginatedResponse<Document>> =>
    api.get(`/documents${buildQuery(params)}`),

  getById: (id: string): Promise<Document> => api.get(`/documents/${id}`),

  // La carga usa multipart/form-data.
  // Se implementa cuando el backend defina formatos, tamaños máximos y validaciones aceptadas.
  // No se incluye aquí para mantener consistencia con el manejo de errores del cliente HTTP.

  delete: (id: string): Promise<void> => api.delete(`/documents/${id}`),
};
