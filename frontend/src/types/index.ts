// ─── Usuarios y roles ────────────────────────────────────────────────────────

export type Role = "admin" | "agent";

export interface User {
  id: string;
  name: string;
  email: string;
  role: Role;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

// ─── Tickets ─────────────────────────────────────────────────────────────────

export type TicketStatus = "open" | "in_progress" | "resolved" | "closed";
export type TicketPriority = "low" | "medium" | "high" | "critical";

export interface Ticket {
  id: string;
  title: string;
  description: string;
  status: TicketStatus;
  priority: TicketPriority;
  category: string | null;
  area: string | null;
  createdBy: User;
  assignedTo: User | null;
  createdAt: string;
  updatedAt: string;
  resolvedAt: string | null;
}

// ─── Predicción de Machine Learning ──────────────────────────────────────────

export interface MlPrediction {
  id: string;
  ticketId: string;
  predictedCategory: string | null;
  predictedPriority: TicketPriority | null;
  predictedArea: string | null;
  confidence: number | null;
  modelName: string;
  modelVersion: string;
  createdAt: string;
}

// ─── Recomendación IA (Human-in-the-loop) ────────────────────────────────────

export type RecommendationStatus = "pending" | "accepted" | "modified" | "rejected";
export type ReviewDecision = "accepted" | "modified" | "rejected";

export interface RecommendationSource {
  documentId: string;
  documentChunkId: string;
  title: string;
  excerpt: string;
  score: number;
}

export interface Recommendation {
  id: string;
  ticketId: string;
  content: string;
  status: RecommendationStatus;
  sources: RecommendationSource[];
  createdAt: string;
}

export interface HumanReview {
  decision: ReviewDecision;
  modifiedContent?: string;
  feedback?: string;
}

// ─── Documentos técnicos ─────────────────────────────────────────────────────

export type DocumentProcessingStatus = "pending" | "processing" | "processed" | "failed";

export interface Document {
  id: string;
  title: string;
  description: string | null;
  originalFilename: string;
  contentType: string;
  processingStatus: DocumentProcessingStatus;
  uploadedBy: User;
  createdAt: string;
  updatedAt: string;
}

// ─── Búsqueda semántica ───────────────────────────────────────────────────────

export interface SearchResult {
  documentId: string;
  documentChunkId: string;
  title: string;
  excerpt: string;
  score: number;
}

// ─── Paginación ───────────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  page: number;
  pageSize: number;
  totalItems: number;
  totalPages: number;
}

export interface PaginationParams {
  page?: number;
  pageSize?: number;
  search?: string;
  sort?: string;
  order?: "asc" | "desc";
}

// ─── Métricas ─────────────────────────────────────────────────────────────────

export interface Metrics {
  totalTickets: number;
  resolvedTickets: number;
  avgResolutionTimeHours: number;
  recommendationsAccepted: number;
  recommendationsModified: number;
  recommendationsRejected: number;
}

// ─── Errores de API ───────────────────────────────────────────────────────────

export interface ApiErrorBody {
  code: string;
  message: string;
  details: unknown | null;
  requestId: string;
}

export interface ApiError {
  error: ApiErrorBody;
}
