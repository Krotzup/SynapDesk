import type { DocumentsService } from "@/services/documents";
import { Document } from "@/types";
import { mockUsers } from "./users";
import { paginate, rejectWithApiError, simulateLatency } from "./utils";

const [carlos, ana, roberto, laura] = mockUsers;

// Documentos ficticios de la base de conocimientos. Los procesados usan los mismos ID y
// títulos que las fuentes de la búsqueda semántica y del Asistente IA de ejemplo.
// Se conservan en memoria: los cambios se pierden al reiniciar el servidor de desarrollo.
const documents: Document[] = [
  {
    id: "3f6b2c1e-8a47-4d2b-9c5e-1a7f0d3e6b21",
    title: "Guía de acceso remoto por VPN",
    description: "Conexión desde casa, perfiles del cliente y desconexiones frecuentes.",
    originalFilename: "guia-acceso-remoto-vpn.pdf",
    contentType: "application/pdf",
    processingStatus: "processed",
    uploadedBy: roberto,
    createdAt: "2026-09-02T14:10:00Z",
    updatedAt: "2026-09-02T14:12:00Z",
  },
  {
    id: "a91d4e72-5b3c-4f8a-b6e1-2c9d7f04a358",
    title: "Procedimiento de restablecimiento de contraseña",
    description: "Portal de autoservicio, requisitos de la contraseña y desbloqueo de cuentas.",
    originalFilename: "restablecimiento-contrasena.pdf",
    contentType: "application/pdf",
    processingStatus: "processed",
    uploadedBy: laura,
    createdAt: "2026-09-05T13:00:00Z",
    updatedAt: "2026-09-05T13:03:00Z",
  },
  {
    id: "c47e19a3-2d6f-4b85-8e0c-9b3a1f52d764",
    title: "Solución de problemas de impresoras de red",
    description: null,
    originalFilename: "impresoras-red.docx",
    contentType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    processingStatus: "processed",
    uploadedBy: carlos,
    createdAt: "2026-09-10T15:45:00Z",
    updatedAt: "2026-09-10T15:47:00Z",
  },
  {
    id: "e25f8b06-7c1a-4e93-a4d2-6f0b3c81e957",
    title: "Configuración del correo corporativo en Outlook",
    description: "Alta de la cuenta, firma y solución de errores de sincronización.",
    originalFilename: "correo-outlook.pdf",
    contentType: "application/pdf",
    processingStatus: "processed",
    uploadedBy: ana,
    createdAt: "2026-09-18T12:20:00Z",
    updatedAt: "2026-09-18T12:22:00Z",
  },
  {
    id: "58c3a7d1-9e2b-4f60-bc84-d1e6a2079f3c",
    title: "Conectividad Wi-Fi en las oficinas",
    description: null,
    originalFilename: "conectividad-wifi.md",
    contentType: "text/markdown",
    processingStatus: "processed",
    uploadedBy: roberto,
    createdAt: "2026-09-25T16:30:00Z",
    updatedAt: "2026-09-25T16:31:00Z",
  },
  {
    id: "7d0e5f94-3b8c-4a17-9f26-8c4b1e3d05a2",
    title: "Solicitud e instalación de software autorizado",
    description: "Catálogo de software permitido y pasos para solicitar una instalación.",
    originalFilename: "software-autorizado.pdf",
    contentType: "application/pdf",
    processingStatus: "processed",
    uploadedBy: laura,
    createdAt: "2026-10-01T13:15:00Z",
    updatedAt: "2026-10-01T13:18:00Z",
  },
  {
    id: "5e923ab0-5cee-4c50-b0dc-35fa54ca54aa",
    title: "Manual de PostgreSQL",
    description: "Conexiones, usuarios y diagnóstico de errores frecuentes de la base de datos.",
    originalFilename: "manual-postgresql.pdf",
    contentType: "application/pdf",
    processingStatus: "processed",
    uploadedBy: carlos,
    createdAt: "2026-10-08T14:00:00Z",
    updatedAt: "2026-10-08T14:05:00Z",
  },
  {
    id: "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d",
    title: "Procedimiento de conectividad",
    description: null,
    originalFilename: "procedimiento-conectividad.pdf",
    contentType: "application/pdf",
    processingStatus: "processed",
    uploadedBy: roberto,
    createdAt: "2026-10-14T17:40:00Z",
    updatedAt: "2026-10-14T17:42:00Z",
  },
  {
    id: "2b3c4d5e-6f7a-4b8c-9d0e-1f2a3b4c5d6e",
    title: "Guía de rendimiento de aplicaciones",
    description: "Métricas de respuesta, tiempos de carga y ajustes del servidor.",
    originalFilename: "rendimiento-aplicaciones.pdf",
    contentType: "application/pdf",
    processingStatus: "processed",
    uploadedBy: ana,
    createdAt: "2026-10-20T13:30:00Z",
    updatedAt: "2026-10-20T13:36:00Z",
  },
  // Estados distintos de "procesado", para ver cómo se muestran.
  {
    id: "d8e9f0a1-b2c3-4d5e-8f6a-7b8c9d0e1f2a",
    title: "Política de respaldo de equipos",
    description: null,
    originalFilename: "politica-respaldo.pdf",
    contentType: "application/pdf",
    processingStatus: "failed",
    uploadedBy: laura,
    createdAt: "2026-10-27T12:05:00Z",
    updatedAt: "2026-10-27T12:09:00Z",
  },
  {
    id: "f1a2b3c4-d5e6-4f7a-9b8c-0d1e2f3a4b5c",
    title: "Manual de la central telefónica",
    description: "Desvíos de llamadas, buzón de voz y anexos.",
    originalFilename: "central-telefonica.pdf",
    contentType: "application/pdf",
    processingStatus: "processing",
    uploadedBy: carlos,
    createdAt: "2026-10-29T15:20:00Z",
    updatedAt: "2026-10-29T15:20:00Z",
  },
];

function notFound() {
  return rejectWithApiError("DOCUMENT_NOT_FOUND", "El documento solicitado no existe.");
}

export const documentsMock: DocumentsService = {
  // Más recientes primero, como el listado de tickets.
  getAll: (params) => {
    const sorted = [...documents].sort((a, b) => b.createdAt.localeCompare(a.createdAt));
    return simulateLatency(paginate(sorted, params));
  },

  getById: (id) => {
    const document = documents.find((item) => item.id === id);
    return document ? simulateLatency(document) : notFound();
  },

  delete: (id) => {
    const index = documents.findIndex((item) => item.id === id);
    if (index === -1) return notFound();
    documents.splice(index, 1);
    return simulateLatency(undefined);
  },
};
