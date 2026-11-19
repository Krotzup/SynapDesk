import { Suspense } from "react";
import { AuthProvider } from "@/components/auth/AuthProvider";
import { DashboardShell } from "@/components/layout/DashboardShell";
import {
  SidebarServiceStatus,
  SidebarServiceStatusFallback,
} from "@/components/layout/SidebarServiceStatus";
import {
  SidebarStatusSummary,
  SidebarStatusSummaryFallback,
} from "@/components/layout/SidebarStatusSummary";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    // El panel se muestra solo después de que /me confirme la sesión.
    <AuthProvider>
      <DashboardShell
        statusSummary={
          <>
            <Suspense fallback={<SidebarStatusSummaryFallback />}>
              <SidebarStatusSummary />
            </Suspense>
            {/* Estado del backend (GET /ready), con su propio Suspense. */}
            <Suspense fallback={<SidebarServiceStatusFallback />}>
              <SidebarServiceStatus />
            </Suspense>
          </>
        }
      >
        {children}
      </DashboardShell>
    </AuthProvider>
  );
}
