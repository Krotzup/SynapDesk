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
  {
    id: "a3b4c5d6-e7f8-4a9b-8c0d-1e2f3a4b5c07",
    title: "VPN no conecta desde el hogar",
    description: "La VPN muestra un error de autenticación y no permite trabajar en remoto.",
    status: "open",
    priority: "medium",
    category: "Conectividad",
    area: "Infraestructura",
    createdBy: laura,
    assignedTo: null,
    createdAt: "2026-10-26T12:20:00Z",
    updatedAt: "2026-10-26T12:20:00Z",
    resolvedAt: null,
  },
  {
    id: "b8c9d0e1-f2a3-4b4c-9d5e-6f7a8b9c0d08",
    title: "Solicitud de notebook para nuevo integrante",
    description: "Se necesita un notebook configurado con acceso a correo y VPN para el lunes.",
    status: "in_progress",
    priority: "low",
    category: "Equipamiento",
    area: "Soporte",
    createdBy: ana,
    assignedTo: roberto,
    createdAt: "2026-10-25T15:00:00Z",
    updatedAt: "2026-10-26T10:15:00Z",
    resolvedAt: null,
  },
  {
    id: "c1d2e3f4-a5b6-4c7d-8e8f-9a0b1c2d3e09",
    title: "Impresora de recepción sin responder",
    description: "La impresora no imprime y muestra la cola de impresión detenida.",
    status: "resolved",
    priority: "medium",
    category: "Hardware",
    area: "Soporte",
    createdBy: carlos,
    assignedTo: roberto,
    createdAt: "2026-10-24T13:40:00Z",
    updatedAt: "2026-10-24T18:05:00Z",
    resolvedAt: "2026-10-24T18:05:00Z",
  },
  {
    id: "d4e5f6a7-b8c9-4d0e-9f1a-2b3c4d5e6f10",
    title: "Permisos de lectura en carpeta compartida",
    description: "El área de finanzas necesita acceso de lectura a la carpeta de reportes.",
    status: "closed",
    priority: "low",
    category: "Accesos",
    area: "Seguridad",
    createdBy: laura,
    assignedTo: laura,
    createdAt: "2026-10-23T14:10:00Z",
    updatedAt: "2026-10-24T09:00:00Z",
    resolvedAt: "2026-10-23T19:30:00Z",
  },
  {
    id: "e7f8a9b0-c1d2-4e3f-8a4b-5c6d7e8f9a11",
    title: "Error 500 al exportar reportes mensuales",
    description: "El cierre de mes falla al exportar reportes con el mismo mensaje de error.",
    status: "in_progress",
    priority: "high",
    category: "Aplicaciones",
    area: "Backend",
    createdBy: carlos,
    assignedTo: carlos,
    createdAt: "2026-10-22T16:25:00Z",
    updatedAt: "2026-10-23T11:00:00Z",
    resolvedAt: null,
  },
  {
    id: "f0a1b2c3-d4e5-4f6a-9b7c-8d9e0f1a2b12",
    title: "Restablecer contraseña de correo corporativo",
    description: "El usuario olvidó su contraseña y no puede ingresar al correo.",
    status: "resolved",
    priority: "low",
    category: "Accesos",
    area: "Soporte",
    createdBy: ana,
    assignedTo: ana,
    createdAt: "2026-10-21T12:00:00Z",
    updatedAt: "2026-10-21T12:45:00Z",
    resolvedAt: "2026-10-21T12:45:00Z",
  },
  {
    id: "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c13",
    title: "Servidor de archivos sin espacio disponible",
    description: "El disco del servidor de archivos está al 98 % y los usuarios no pueden guardar.",
    status: "open",
    priority: "critical",
    category: "Infraestructura",
    area: "Infraestructura",
    createdBy: roberto,
    assignedTo: null,
    createdAt: "2026-10-20T11:30:00Z",
    updatedAt: "2026-10-20T11:30:00Z",
    resolvedAt: null,
  },
  {
    id: "1b2c3d4e-5f6a-4b7c-9d8e-0f1a2b3c4d14",
    title: "Actualizar antivirus en equipos de bodega",
    description: "Tres equipos de bodega tienen el antivirus desactualizado.",
    status: "open",
    priority: "low",
    category: "Seguridad",
    area: "Seguridad",
    createdBy: laura,
    assignedTo: null,
    createdAt: "2026-10-19T14:50:00Z",
    updatedAt: "2026-10-19T14:50:00Z",
    resolvedAt: null,
  },
];

/** Tickets de ejemplo actuales, para calcular métricas coherentes con el listado. */
export function getMockTickets(): readonly Ticket[] {
  return tickets;
}

function notFound() {
  return rejectWithApiError("TICKET_NOT_FOUND", "El ticket solicitado no existe.");
}

// Minúsculas y sin tildes, para que "mendez" encuentre "Méndez".
function normalizeText(value: string): string {
  return value
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
}

// La búsqueda textual cubre los datos visibles en el listado: título, área,
// categoría, usuario que lo creó y el inicio del ID.
function matchesSearch(ticket: Ticket, search: string): boolean {
  const fields = [ticket.title, ticket.area, ticket.category, ticket.createdBy.name];
  return (
    ticket.id.startsWith(search) ||
    fields.some((field) => field && normalizeText(field).includes(search))
  );
}

export const ticketsMock: TicketsService = {
  // Filtros opcionales y combinables.
  getAll: (params) => {
    const search = params?.search ? normalizeText(params.search.trim()) : "";
    const filtered = tickets.filter(
      (ticket) =>
        (!params?.status || ticket.status === params.status) &&
        (!params?.priority || ticket.priority === params.priority) &&
        (!params?.area || ticket.area === params.area) &&
        (!search || matchesSearch(ticket, search))
    );
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
