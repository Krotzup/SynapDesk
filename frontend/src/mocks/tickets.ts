import type { TicketsService } from "@/services/tickets";
import { Ticket } from "@/types";
import { mockCurrentUser, mockUsers } from "./users";
import { paginate, rejectWithApiError, simulateLatency } from "./utils";

const [carlos, ana, roberto, laura] = mockUsers;

// Tickets ficticios con la forma de la respuesta del contrato frontend-backend.
// Se conservan en memoria: los cambios se pierden al reiniciar el servidor de desarrollo.
const tickets: Ticket[] = [
  {
    id: "5b0e7c3a-2f1d-4c8e-9a6b-1d2e3f4a5b01",
    title: "Caída total del servicio de correo",
    description:
      "Ningún usuario de la oficina central puede enviar ni recibir correos desde las 08:00.",
    status: "open",
    priority: "critical",
    category: null,
    area: null,
    createdBy: roberto,
    assignedTo: null,
    createdAt: "2026-10-29T11:05:00Z",
    updatedAt: "2026-10-29T11:05:00Z",
    resolvedAt: null,
  },
  {
    id: "64f10aed-c41c-46a3-91dd-f2cbcd5eb79f",
    title: "Error al conectar con la base de datos",
    description:
      "No se puede conectar al servidor de base de datos desde la aplicación. El error aparece al intentar realizar la consulta.",
    status: "open",
    priority: "high",
    category: "Base de datos",
    area: "Backend",
    createdBy: carlos,
    assignedTo: null,
    createdAt: "2026-10-28T13:24:00Z",
    updatedAt: "2026-10-28T13:24:00Z",
    resolvedAt: null,
  },
  {
    id: "9c8d7e6f-5a4b-4c3d-8e2f-1a0b9c8d7e03",
    title: "Lentitud en el proceso de checkout",
    description: "El paso de pago tarda más de 20 segundos en responder en horario punta.",
    status: "in_progress",
    priority: "medium",
    category: "Rendimiento",
    area: "Frontend",
    createdBy: ana,
    assignedTo: carlos,
    createdAt: "2026-10-28T12:15:00Z",
    updatedAt: "2026-10-28T15:40:00Z",
    resolvedAt: null,
  },
  {
    id: "2e3f4a5b-6c7d-4e8f-9a0b-1c2d3e4f5a04",
    title: "Fallo en la autenticación mediante Google SSO",
    description: "Los usuarios reciben un error de redirección al iniciar sesión con Google.",
    status: "open",
    priority: "high",
    category: "Autenticación",
    area: "Seguridad",
    createdBy: roberto,
    assignedTo: null,
    createdAt: "2026-10-27T21:30:00Z",
    updatedAt: "2026-10-27T21:30:00Z",
    resolvedAt: null,
  },
  {
    id: "7a8b9c0d-1e2f-4a3b-8c4d-5e6f7a8b9c05",
    title: "Actualizar documentación de API v2",
    description: "La documentación no incluye los nuevos parámetros de paginación.",
    status: "resolved",
    priority: "low",
    category: "Documentación",
    area: "DevOps",
    createdBy: laura,
    assignedTo: laura,
    createdAt: "2026-10-27T17:10:00Z",
    updatedAt: "2026-10-28T10:00:00Z",
    resolvedAt: "2026-10-28T10:00:00Z",
  },
  {
    id: "d1e2f3a4-b5c6-4d7e-8f9a-0b1c2d3e4f06",
    title: "Error de renderizado en panel de métricas",
    description: "Los gráficos del panel de métricas no se muestran en pantallas pequeñas.",
    status: "resolved",
    priority: "medium",
    category: "Interfaz",
    area: "Frontend",
    createdBy: ana,
    assignedTo: ana,
    createdAt: "2026-10-26T14:45:00Z",
    updatedAt: "2026-10-27T09:30:00Z",
    resolvedAt: "2026-10-27T09:30:00Z",
  },
];

function notFound() {
  return rejectWithApiError("TICKET_NOT_FOUND", "El ticket solicitado no existe.");
}

export const ticketsMock: TicketsService = {
  getAll: (params) => {
    const search = params?.search?.trim().toLowerCase();
    const filtered = search
      ? tickets.filter((ticket) => ticket.title.toLowerCase().includes(search))
      : tickets;
    const sorted = [...filtered].sort((a, b) => b.createdAt.localeCompare(a.createdAt));
    return simulateLatency(paginate(sorted, params));
  },

  getById: (id) => {
    const ticket = tickets.find((item) => item.id === id);
    return ticket ? simulateLatency(ticket) : notFound();
  },

  create: (data) => {
    const now = new Date().toISOString();
    const ticket: Ticket = {
      id: crypto.randomUUID(),
      title: data.title,
      description: data.description,
      status: "open",
      priority: "medium",
      category: null,
      area: null,
      createdBy: mockCurrentUser,
      assignedTo: null,
      createdAt: now,
      updatedAt: now,
      resolvedAt: null,
    };
    tickets.unshift(ticket);
    return simulateLatency(ticket);
  },

  update: (id, data) => {
    const ticket = tickets.find((item) => item.id === id);
    if (!ticket) return notFound();

    const { assignedToId, ...fields } = data;
    Object.assign(ticket, fields, { updatedAt: new Date().toISOString() });
    if (assignedToId !== undefined) {
      ticket.assignedTo = mockUsers.find((user) => user.id === assignedToId) ?? null;
    }
    if (fields.status === "resolved" && !ticket.resolvedAt) {
      ticket.resolvedAt = ticket.updatedAt;
    }
    return simulateLatency(ticket);
  },

  // Cierre lógico, como indica el contrato para DELETE /tickets/{id}.
  delete: (id) => {
    const ticket = tickets.find((item) => item.id === id);
    if (!ticket) return notFound();

    ticket.status = "closed";
    ticket.updatedAt = new Date().toISOString();
    return simulateLatency(undefined);
  },
};
