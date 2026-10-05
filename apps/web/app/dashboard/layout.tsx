import { DashboardShell } from "@/components/dashboard-shell";
import { PushProvider } from "@/components/push-provider";
import { TaskDataProvider } from "@/components/task-data-provider";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return <TaskDataProvider><PushProvider><DashboardShell>{children}</DashboardShell></PushProvider></TaskDataProvider>;
}
