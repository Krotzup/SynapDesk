// ─── Usuarios y roles ────────────────────────────────────────────────────────

export type Role = "admin" | "agent";

export interface User {
  id: string;
  name: string;
  email: string;
  role: Role;
  createdAt: string;
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
}

// ─── Recomendación IA (Human-in-the-loop) ────────────────────────────────────

export type RecommendationStatus = "pending" | "accepted" | "modified" | "rejected";

export interface RecommendationSource {
  title: string;
  excerpt: string;
  documentId: string;
}

export interface Recommendation {
  id: string;
  ticketId: string;
  content: string;
  sources: RecommendationSource[];
  status: RecommendationStatus;
  modifiedContent: string | null;
  createdAt: string;
}

// ─── Documentos técnicos ─────────────────────────────────────────────────────

export interface Document {
  id: string;
  title: string;
  description: string | null;
  fileUrl: string;
  uploadedBy: User;
  createdAt: string;
}

// ─── Búsqueda semántica ───────────────────────────────────────────────────────

export interface SearchResult {
  documentId: string;
  title: string;
  excerpt: string;
  score: number;
}

// ─── Métricas ─────────────────────────────────────────────────────────────────

export interface Metrics {
  totalTickets: number;
  resolvedTickets: number;
  avgResolutionTimeHours: number;
  recommendationsAccepted: number;
  recommendationsRejected: number;
  recommendationsModified: number;
}

// ─── API genérica ─────────────────────────────────────────────────────────────

export interface ApiError {
  message: string;
  statusCode: number;
}
