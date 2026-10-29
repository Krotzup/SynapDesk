import { User } from "@/types";

// Usuarios ficticios. Los identificadores siguen el formato UUID del contrato.
export const mockUsers: User[] = [
  {
    id: "3f1c2a9e-7b4d-4e8a-9c21-5d6f7a8b9c01",
    name: "Carlos Méndez",
    email: "carlos.mendez@synapdesk.local",
    role: "agent",
    isActive: true,
    createdAt: "2026-08-01T12:00:00Z",
    updatedAt: "2026-08-01T12:00:00Z",
  },
  {
    id: "8a2b4c6d-1e3f-4a5b-8c7d-9e0f1a2b3c02",
    name: "Ana Torres",
    email: "ana.torres@synapdesk.local",
    role: "agent",
    isActive: true,
    createdAt: "2026-08-01T12:00:00Z",
    updatedAt: "2026-08-01T12:00:00Z",
  },
  {
    id: "c4d5e6f7-a8b9-4c0d-9e1f-2a3b4c5d6e03",
    name: "Roberto Gómez",
    email: "roberto.gomez@synapdesk.local",
    role: "agent",
    isActive: true,
    createdAt: "2026-08-01T12:00:00Z",
    updatedAt: "2026-08-01T12:00:00Z",
  },
  {
    id: "e7f8a9b0-c1d2-4e3f-8a4b-5c6d7e8f9a04",
    name: "Laura Silva",
    email: "laura.silva@synapdesk.local",
    role: "admin",
    isActive: true,
    createdAt: "2026-08-01T12:00:00Z",
    updatedAt: "2026-08-01T12:00:00Z",
  },
];

// Usuario que se asocia a los tickets creados con datos de ejemplo,
// hasta que exista la sesión autenticada.
export const mockCurrentUser = mockUsers[0];
