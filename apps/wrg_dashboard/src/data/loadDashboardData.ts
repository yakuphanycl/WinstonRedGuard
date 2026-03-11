import type { DashboardData } from "../types/dashboard";
import { ArtifactDashboardAdapter } from "./artifactAdapter";
import { DemoDashboardAdapter } from "./demoAdapter";

const artifactAdapter = new ArtifactDashboardAdapter();
const demoAdapter = new DemoDashboardAdapter();
const allowDemoFallback = String(import.meta.env.VITE_DASHBOARD_ALLOW_DEMO_FALLBACK ?? "").toLowerCase() === "true";

function anyArtifactAvailable(data: DashboardData): boolean {
  const state = data.sourceState;
  return state.companyHealth === "valid" || state.companyHealth === "partial" || state.policyCheck === "valid" || state.policyCheck === "partial" || state.governanceCheck === "valid" || state.governanceCheck === "partial" || state.registry === "valid" || state.registry === "partial";
}

function anyArtifactInvalid(data: DashboardData): boolean {
  const state = data.sourceState;
  return state.companyHealth === "invalid" || state.policyCheck === "invalid" || state.governanceCheck === "invalid" || state.registry === "invalid";
}

export async function loadDashboardData(): Promise<DashboardData> {
  const live = await artifactAdapter.load();
  if (anyArtifactAvailable(live) || anyArtifactInvalid(live)) {
    return live;
  }
  if (allowDemoFallback) {
    return demoAdapter.load();
  }
  return live;
}
