import { Suspense } from "react";
import { Header } from "@/components/layout/Header";
import { Sidebar } from "@/components/layout/Sidebar";
import {
  SidebarStatusSummary,
  SidebarStatusSummaryFallback,
} from "@/components/layout/SidebarStatusSummary";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-[#F8FAFC]">
      <Sidebar
        statusSummary={
          <Suspense fallback={<SidebarStatusSummaryFallback />}>
            <SidebarStatusSummary />
          </Suspense>
        }
      />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto bg-[#F8FAFC]">{children}</main>
      </div>
    </div>
  );
}
