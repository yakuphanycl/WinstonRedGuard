import type { DashboardData } from "../types/dashboard";

export interface DashboardAdapter {
  load(): Promise<DashboardData>;
}
