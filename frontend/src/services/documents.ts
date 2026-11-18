import { api } from "@/lib/api";
import { USE_MOCKS } from "@/lib/config";
import { buildQuery } from "@/lib/params";
import { documentsMock } from "@/mocks/documents";
import { Document, PaginatedResponse, PaginationParams } from "@/types";

const documentsApi = {
  getAll: (params?: PaginationParams): Promise<PaginatedResponse<Document>> =>
    api.get(`/documents${buildQuery(params)}`),

  getById: (id: string): Promise<Document> => api.get(`/documents/${id}`),

  // La carga usa multipart/form-data.
  // Se implementa cuando el backend defina formatos, tamaños máximos y validaciones aceptadas.
  // No se incluye aquí para mantener consistencia con el manejo de errores del cliente HTTP.

  delete: (id: string): Promise<void> => api.delete(`/documents/${id}`),
};

export type DocumentsService = typeof documentsApi;

export const documentsService: DocumentsService = USE_MOCKS ? documentsMock : documentsApi;
