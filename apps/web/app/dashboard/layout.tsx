import { DashboardShell } from "@/components/dashboard-shell";
import { PushProvider } from "@/components/push-provider";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return <PushProvider><DashboardShell>{children}</DashboardShell></PushProvider>;
}
