import type { DashboardData } from "../types/dashboard";
import type { DashboardAdapter } from "./adapter";

export class DemoDashboardAdapter implements DashboardAdapter {
  async load(): Promise<DashboardData> {
    return {
      repoRoot: "not available",
      generatedAt: "2026-03-08T00:00:00Z",
      refreshedAt: "2026-03-08T00:00:00Z",
      overall: "WARN",
      overallSource: "derived",
      sourceKind: "demo",
      summaryCards: [
        { key: "overall", label: "Overall", value: "WARN", status: "WARN" },
        { key: "errors", label: "Errors", value: "2", status: "FAIL" },
        { key: "warnings", label: "Warnings", value: "5", status: "WARN" },
        { key: "sources", label: "Sources", value: "2/3 ready", status: "WARN" },
        { key: "worker_total", label: "Total Workers", value: "4", status: "PASS" },
        { key: "worker_active", label: "Active", value: "2", status: "WARN" },
        { key: "worker_quarantine", label: "Quarantine", value: "1", status: "FAIL" },
        { key: "worker_retired", label: "Retired", value: "0", status: "PASS" },
        { key: "worker_unverified", label: "Unverified", value: "2", status: "WARN" },
        { key: "worker_avg_score", label: "Average Score", value: "5.50", status: "PASS" }
      ],
      layers: [
        { name: "Management", status: "WARN", detail: "overall=WARN", relatedSystems: ["company_health", "wrg_dashboard"], issueCount: 1 },
        { name: "Evaluation", status: "WARN", detail: "unverified=2, quarantine=1", relatedSystems: ["app_registry", "app_evaluator"], issueCount: 3 },
        { name: "Governance", status: "FAIL", detail: "governance=FAIL, policy=WARN", relatedSystems: ["governance_check", "policy_check"], issueCount: 2 },
        { name: "Factory", status: "WARN", detail: "registry=missing", relatedSystems: ["devtool_genome", "app_registry"], issueCount: 1 },
        { name: "Observation", status: "WARN", detail: "company_health=missing, governance=missing", relatedSystems: ["repo_analyzer", "wrg_dashboard"], issueCount: 1 },
        { name: "Pilot Workers", status: "FAIL", detail: "active=2, quarantine=1, retired=0", relatedSystems: ["farmer", "refinery", "repo_doctor"], issueCount: 1 }
      ],
      criticalSignals: [
        { severity: "ERROR", code: "quarantine_worker_count", label: "Quarantine workers", value: "1" },
        { severity: "WARNING", code: "company_overall_status", label: "Company overall", value: "WARN" },
        { severity: "WARNING", code: "average_score_low", label: "Average score", value: "5.50" },
        { severity: "WARNING", code: "unverified_worker_count", label: "Unverified workers", value: "2" },
        { severity: "INFO", code: "retired_worker_count", label: "Retired workers", value: "0" }
      ],
      relationships: [
        { from: "app_registry", to: "app_evaluator", relation: "evaluation inventory", status: "WARN" },
        { from: "app_registry", to: "wrg_dashboard", relation: "worker table source", status: "WARN" },
        { from: "governance_check", to: "company_health", relation: "governance signal", status: "WARN" },
        { from: "policy_check", to: "company_health", relation: "policy signal", status: "WARN" },
        { from: "devtool_genome", to: "app_registry", relation: "factory registration", status: "WARN" },
        { from: "repo_analyzer", to: "wrg_dashboard", relation: "observability input", status: "WARN" }
      ],
      workers: [
        {
          app: "app_registry",
          statusText: "active",
          verified: "true",
          score: "8",
          lastVerifiedAt: "2026-03-08T09:00:00Z",
          appPath: "apps/app_registry",
          appClass: "internal_infra",
          productizationStage: "internal_operational",
          status: "PASS"
        },
        {
          app: "governance_check",
          statusText: "active",
          verified: "false",
          score: "6",
          lastVerifiedAt: "2026-03-08T09:05:00Z",
          appPath: "apps/governance_check",
          appClass: "worker",
          productizationStage: "internal_mvp",
          status: "WARN"
        },
        {
          app: "farmer",
          statusText: "quarantine",
          verified: "false",
          score: "3",
          lastVerifiedAt: "2026-03-08T09:10:00Z",
          appPath: "apps/farmer",
          appClass: "worker",
          productizationStage: "experimental_lab",
          status: "FAIL"
        },
        {
          app: "repo_analyzer",
          statusText: "active",
          verified: "true",
          score: "5",
          lastVerifiedAt: "2026-03-08T09:15:00Z",
          appPath: "apps/repo_analyzer",
          appClass: "worker",
          productizationStage: "internal_mvp",
          status: "PASS"
        }
      ],
      pulse: [
        { level: "FAIL", message: "governance layer has critical findings" },
        { level: "WARN", message: "policy source missing in current snapshot" },
        { level: "WARN", message: "registry unavailable" },
        { level: "PASS", message: "worker operations remain stable" }
      ],
      nextActions: [
        { priority: "high", text: "Resolve governance FAIL findings before release gate." },
        { priority: "medium", text: "Generate fresh policy_check artifact." },
        { priority: "low", text: "Review worker ownership alignment." }
      ],
      governance: {
        overall: "WARN",
        errorCount: 2,
        warningCount: 3,
        checks: [
          { app: "governance_check", level: "WARNING", issueCount: 3 },
          { app: "app_registry", level: "ERROR", issueCount: 2 }
        ]
      },
      artifacts: [
        { key: "company_health", path: "artifacts/company_health.json", sourceKind: "demo", dataState: "missing", updatedAt: null, message: "missing", rawJson: null },
        { key: "policy_check", path: "artifacts/policy_check.json", sourceKind: "demo", dataState: "missing", updatedAt: null, message: "missing", rawJson: null },
        { key: "governance_check", path: "artifacts/governance_check.json", sourceKind: "demo", dataState: "missing", updatedAt: null, message: "missing", rawJson: null },
        { key: "app_registry", path: "apps/app_registry/data/registry.json", sourceKind: "demo", dataState: "missing", updatedAt: null, message: "missing", rawJson: null }
      ],
      sourceState: {
        companyHealth: "missing",
        policyCheck: "missing",
        governanceCheck: "missing",
        registry: "missing"
      }
    };
  }
}
