import type { DashboardData } from "../../types/dashboard";

export const validCompanyHealth = {
  generated_at: "2026-03-08T13:27:10Z",
  overall: "FAIL",
  totals: {
    errors: 2,
    warnings: 1
  },
  highlights: ["governance_check reports 2 errors"],
  sources: {
    policy_check: { present: true, overall: "WARN" },
    governance_check: { present: true, overall: "FAIL" }
  }
};

export const validPolicy = {
  overall: "WARN",
  summary: {
    checks_failed: 1
  }
};

export const validGovernance = {
  overall: "FAIL",
  summary: {
    error: 2,
    warning: 1
  },
  checks: [
    {
      app: "farmer",
      level: "ERROR"
    }
  ]
};

export const validRegistry = {
  apps: [
    {
      name: "farmer",
      status: "quarantine",
      verified: false,
      score: 3,
      last_verified_at: "2026-03-08T10:00:00Z",
      app_path: "apps/farmer",
      class: "worker",
      productization_stage: "experimental_lab"
    },
    {
      name: "app_registry",
      status: "active",
      verified: true,
      score: 8,
      last_verified_at: "2026-03-08T10:01:00Z",
      app_path: "apps/app_registry",
      class: "internal_infra",
      productization_stage: "internal_operational"
    }
  ]
};

export function dashboardWith(overrides: Partial<DashboardData>): DashboardData {
  return {
    repoRoot: "c:\\dev\\WinstonRedGuard",
    generatedAt: "2026-03-08T00:00:00Z",
    refreshedAt: "2026-03-08T00:00:00Z",
    overall: "PASS",
    overallSource: "derived",
    sourceKind: "canonical",
    summaryCards: [],
    layers: [],
    criticalSignals: [],
    relationships: [],
    workers: [],
    pulse: [],
    nextActions: [],
    governance: {
      overall: "PASS",
      errorCount: 0,
      warningCount: 0,
      checks: []
    },
    artifacts: [],
    sourceState: {
      companyHealth: "missing",
      policyCheck: "missing",
      governanceCheck: "missing",
      registry: "missing"
    },
    ...overrides
  };
}
