import { TicketPriority, TicketStatus } from "@/types";

// ─── Badge de prioridad ───────────────────────────────────────────────────────

const priorityStyles: Record<TicketPriority, string> = {
  low: "bg-[#DCFCE7] text-[#16A34A]",
  medium: "bg-[#FEF9C3] text-[#D97706]",
  high: "bg-[#FEE2E2] text-[#991B1B]",
  critical: "bg-[#FEE2E2] text-[#991B1B]",
};

const priorityLabels: Record<TicketPriority, string> = {
  low: "Baja",
  medium: "Media",
  high: "Alta",
  critical: "Crítica",
};

interface PriorityBadgeProps {
  priority: TicketPriority;
}

export function PriorityBadge({ priority }: PriorityBadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${priorityStyles[priority]}`}
    >
      {(priority === "high" || priority === "critical") && <span aria-hidden="true">🔴</span>}
      {priorityLabels[priority]}
    </span>
  );
}

// ─── Badge de estado de ticket ────────────────────────────────────────────────

const statusStyles: Record<TicketStatus, string> = {
  open: "bg-[#DBEAFE] text-[#1D4ED8]",
  in_progress: "bg-[#FEF9C3] text-[#D97706]",
  resolved: "bg-[#DCFCE7] text-[#16A34A]",
  closed: "bg-[#F1F5F9] text-[#475569]",
};

const statusLabels: Record<TicketStatus, string> = {
  open: "Abierto",
  in_progress: "En Proceso",
  resolved: "Resuelto",
  closed: "Cerrado",
};

interface StatusBadgeProps {
  status: TicketStatus;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${statusStyles[status]}`}
    >
      {statusLabels[status]}
    </span>
  );
}

// ─── Badge de categoría IA ────────────────────────────────────────────────────

interface AiBadgeProps {
  label: string;
}

export function AiBadge({ label }: AiBadgeProps) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-[#E0E7FF] px-2.5 py-0.5 text-xs font-medium text-[#3730A3]">
      🏷️ {label}
    </span>
  );
}
