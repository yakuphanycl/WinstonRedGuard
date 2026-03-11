import type { ActionItem, DashboardData, DataState, HealthStatus, LayerItem, PulseItem, SummaryCard, WorkerRow } from "../types/dashboard";
import type { DashboardAdapter } from "./adapter";
import { buildActionItems, buildCriticalSignals, buildLayerHealth, buildRelationshipMap, computeWorkerMetrics } from "./insights";

type SourceState = DataState;

type LoadResult = {
  key: "company_health" | "policy_check" | "governance_check" | "app_registry";
  path: string;
  state: SourceState;
  rawJson: string | null;
  parsed: unknown | null;
  updatedAt: string | null;
  sourceKind: "canonical";
};

const COMPANY_HEALTH_PATH = "/artifacts/company_health.json";
const POLICY_CHECK_PATH = "/artifacts/policy_check.json";
const GOVERNANCE_CHECK_PATH = "/artifacts/governance_check.json";
const REGISTRY_PATH = "/registry/app_registry.json";

function normalizeStatus(value: unknown): HealthStatus {
  const text = String(value ?? "").toUpperCase();
  if (text === "PASS" || text === "OK" || text === "ACTIVE") {
    return "PASS";
  }
  if (text === "WARN" || text === "WARNING" || text === "RETIRED") {
    return "WARN";
  }
  return "FAIL";
}

function asRecord(value: unknown): Record<string, unknown> {
  if (typeof value === "object" && value !== null) {
    return value as Record<string, unknown>;
  }
  return {};
}

function asString(value: unknown, fallback = "not available"): string {
  if (typeof value === "string" && value.trim()) {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return fallback;
}

function pickNumber(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function pickOptionalNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function deriveOverall(
  companyOverall: unknown,
  policyOverall: unknown,
  governanceOverall: unknown,
  errors: number,
  warnings: number,
  availableSources: number
): HealthStatus {
  if (companyOverall !== undefined && companyOverall !== null && String(companyOverall).trim()) {
    return normalizeStatus(companyOverall);
  }
  const policy = normalizeStatus(policyOverall);
  const governance = normalizeStatus(governanceOverall);
  if (policy === "FAIL" || governance === "FAIL" || errors > 0) {
    return "FAIL";
  }
  if (policy === "WARN" || governance === "WARN" || warnings > 0) {
    return "WARN";
  }
  if (availableSources === 0) {
    return "WARN";
  }
  return "PASS";
}

function hasDirectOverall(value: unknown): boolean {
  return value !== undefined && value !== null && String(value).trim().length > 0;
}

function mapRegistryWorkers(registryPayload: unknown): WorkerRow[] {
  const root = asRecord(registryPayload);
  const rows = Array.isArray(root["apps"]) ? root["apps"] : [];
  return rows
    .map((item, index) => {
      const row = asRecord(item);
      const statusText = asString(row["status"], "unknown");
      const verifiedValue = row["verified"];
      const verifiedText = typeof verifiedValue === "boolean" ? (verifiedValue ? "true" : "false") : "unknown";
      const scoreNum = pickOptionalNumber(row["score"]);
      return {
        app: asString(row["name"], `worker_${index + 1}`),
        statusText,
        verified: verifiedText,
        score: scoreNum === null ? "n/a" : String(scoreNum),
        lastVerifiedAt: asString(row["last_verified_at"], "n/a"),
        appPath: asString(row["app_path"], "n/a"),
        appClass: asString(row["class"], "n/a"),
        productizationStage: asString(row["productization_stage"], "n/a"),
        status: normalizeStatus(statusText)
      } as WorkerRow;
    })
    .sort((a, b) => a.app.localeCompare(b.app));
}

function buildWorkerSummaryCards(workers: WorkerRow[]): SummaryCard[] {
  const metrics = computeWorkerMetrics(workers);
  const avg = metrics.averageScore === null ? "n/a" : metrics.averageScore.toFixed(2);

  return [
    { key: "worker_total", label: "Total Workers", value: String(metrics.total), status: metrics.total > 0 ? "PASS" : "WARN" },
    { key: "worker_active", label: "Active", value: String(metrics.active), status: metrics.quarantine > 0 ? "WARN" : "PASS" },
    { key: "worker_quarantine", label: "Quarantine", value: String(metrics.quarantine), status: metrics.quarantine > 0 ? "FAIL" : "PASS" },
    { key: "worker_retired", label: "Retired", value: String(metrics.retired), status: metrics.retired > 0 ? "WARN" : "PASS" },
    { key: "worker_unverified", label: "Unverified", value: String(metrics.unverified), status: metrics.unverified > 0 ? "WARN" : "PASS" },
    { key: "worker_avg_score", label: "Average Score", value: avg, status: avg === "n/a" ? "WARN" : "PASS" }
  ];
}

function validateState(key: LoadResult["key"], parsed: unknown, current: SourceState): SourceState {
  if (current !== "valid") {
    return current;
  }
  const obj = asRecord(parsed);
  if (key === "company_health") {
    return obj["overall"] === undefined || !obj["totals"] ? "partial" : "valid";
  }
  if (key === "policy_check") {
    return obj["overall"] === undefined ? "partial" : "valid";
  }
  if (key === "governance_check") {
    return obj["overall"] === undefined || obj["summary"] === undefined ? "partial" : "valid";
  }
  if (key === "app_registry") {
    return Array.isArray(obj["apps"]) ? "valid" : "partial";
  }
  return current;
}

async function loadJson(path: string, key: LoadResult["key"]): Promise<LoadResult> {
  try {
    const response = await fetch(path, { cache: "no-store" });
    if (!response.ok) {
      return { key, path, state: "missing", rawJson: null, parsed: null, updatedAt: null, sourceKind: "canonical" };
    }
    const text = await response.text();
    try {
      const parsed = JSON.parse(text) as unknown;
      const state = validateState(key, parsed, "valid");
      return { key, path, state, rawJson: text, parsed, updatedAt: null, sourceKind: "canonical" };
    } catch {
      return { key, path, state: "invalid", rawJson: text, parsed: null, updatedAt: null, sourceKind: "canonical" };
    }
  } catch {
    return { key, path, state: "missing", rawJson: null, parsed: null, updatedAt: null, sourceKind: "canonical" };
  }
}

async function loadAllSources(): Promise<{ readAt: string; repoRoot: string; sources: LoadResult[] }> {
  if (window.wrgControlCenter?.readSources) {
    const bridge = await Promise.resolve(window.wrgControlCenter.readSources());
    const sources: LoadResult[] = bridge.sources.map((item) => {
      const nextState = validateState(item.key, item.parsed, item.dataState);
      return {
        key: item.key,
        path: item.path,
        state: nextState,
        rawJson: item.rawJson,
        parsed: item.parsed,
        updatedAt: item.updatedAt,
        sourceKind: "canonical"
      };
    });
    return { readAt: bridge.readAt, repoRoot: bridge.repoRoot, sources };
  }

  const sources = await Promise.all([
    loadJson(COMPANY_HEALTH_PATH, "company_health"),
    loadJson(POLICY_CHECK_PATH, "policy_check"),
    loadJson(GOVERNANCE_CHECK_PATH, "governance_check"),
    loadJson(REGISTRY_PATH, "app_registry")
  ]);

  return { readAt: new Date().toISOString(), repoRoot: "not available", sources };
}

function pickSource(list: LoadResult[], key: LoadResult["key"]): LoadResult {
  return (
    list.find((item) => item.key === key) ??
    {
      key,
      path: key,
      state: "missing",
      rawJson: null,
      parsed: null,
      updatedAt: null,
      sourceKind: "canonical"
    }
  );
}

function artifactMessage(state: SourceState): string {
  if (state === "valid") {
    return "valid";
  }
  if (state === "partial") {
    return "partial";
  }
  if (state === "invalid") {
    return "invalid";
  }
  return "missing";
}

export class ArtifactDashboardAdapter implements DashboardAdapter {
  async load(): Promise<DashboardData> {
    const loaded = await loadAllSources();
    const companyHealth = pickSource(loaded.sources, "company_health");
    const policyCheck = pickSource(loaded.sources, "policy_check");
    const governanceCheck = pickSource(loaded.sources, "governance_check");
    const registry = pickSource(loaded.sources, "app_registry");

    const ch = asRecord(companyHealth.parsed);
    const summary = asRecord(ch["totals"]);

    const policy = asRecord(policyCheck.parsed);
    const governance = asRecord(governanceCheck.parsed);
    const governanceSummary = asRecord(governance["summary"]);

    const errors = pickNumber(summary["errors"]) || pickNumber(governanceSummary["error"]);
    const warnings = pickNumber(summary["warnings"]) || pickNumber(governanceSummary["warning"]);
    const availableSources = [companyHealth, policyCheck, governanceCheck].filter((s) => s.state === "valid" || s.state === "partial").length;
    const directOverall = hasDirectOverall(ch["overall"]);
    const overall = deriveOverall(ch["overall"], policy["overall"], governance["overall"], errors, warnings, availableSources);

    const workers = registry.state === "valid" || registry.state === "partial" ? mapRegistryWorkers(registry.parsed) : [];
    const sourceState = {
      companyHealth: companyHealth.state,
      policyCheck: policyCheck.state,
      governanceCheck: governanceCheck.state,
      registry: registry.state
    };

    const summaryCards: SummaryCard[] = [
      { key: "overall", label: "Overall", value: overall, status: overall },
      { key: "errors", label: "Errors", value: String(errors), status: errors > 0 ? "FAIL" : "PASS" },
      { key: "warnings", label: "Warnings", value: String(warnings), status: warnings > 0 ? "WARN" : "PASS" },
      {
        key: "sources",
        label: "Sources",
        value: `${availableSources}/3 available`,
        status: availableSources === 3 ? "PASS" : "WARN"
      },
      ...buildWorkerSummaryCards(workers)
    ];

    const policyOverall = normalizeStatus(policy["overall"]);
    const governanceOverall = normalizeStatus(governance["overall"]);
    const layers: LayerItem[] = buildLayerHealth({ workers, companyOverall: overall, policyOverall, governanceOverall, sourceState });
    const criticalSignals = buildCriticalSignals({ workers, companyOverall: overall, policyOverall, governanceOverall, sourceState });
    const relationships = buildRelationshipMap({ workers, companyOverall: overall, policyOverall, governanceOverall, sourceState });

    const pulse: PulseItem[] = [];
    if (overall === "FAIL") {
      pulse.push({ level: "FAIL", message: "critical company health signal detected" });
    } else if (overall === "WARN") {
      pulse.push({ level: "WARN", message: "company health has warnings requiring follow-up" });
    } else {
      pulse.push({ level: "PASS", message: "company health baseline is stable" });
    }

    if (registry.state !== "valid") {
      pulse.push({ level: registry.state === "invalid" ? "FAIL" : "WARN", message: "registry unavailable" });
    }

    const highlights = Array.isArray(ch["highlights"]) ? ch["highlights"] : [];
    for (const item of highlights) {
      const msg = asString(item);
      const lower = msg.toLowerCase();
      const level: HealthStatus = lower.includes("error") || lower.includes("fail") ? "FAIL" : lower.includes("warn") ? "WARN" : overall;
      pulse.push({ level, message: msg });
    }

    const nextActions: ActionItem[] = buildActionItems({ workers, companyOverall: overall, policyOverall, governanceOverall, sourceState });

    const checks = Array.isArray(governance["checks"])
      ? governance["checks"].slice(0, 20).map((item, idx) => {
          const row = asRecord(item);
          const issues = Array.isArray(row["issues"]) ? row["issues"] : [];
          return {
            app: asString(row["app"], `app_${idx + 1}`),
            level: asString(row["level"], "UNKNOWN"),
            issueCount: issues.length
          };
        })
      : [];

    const artifacts: DashboardData["artifacts"] = [companyHealth, policyCheck, governanceCheck, registry].map((item) => ({
      key: item.key,
      path: item.path,
      sourceKind: item.sourceKind,
      dataState: item.state,
      updatedAt: item.updatedAt,
      message: artifactMessage(item.state),
      rawJson: item.rawJson
    }));

    return {
      repoRoot: loaded.repoRoot,
      generatedAt: asString(ch["generated_at"], loaded.readAt),
      refreshedAt: loaded.readAt,
      overall,
      overallSource: directOverall ? "company_health" : "derived",
      sourceKind: "canonical",
      summaryCards,
      layers,
      criticalSignals,
      relationships,
      workers,
      pulse,
      nextActions,
      governance: {
        overall: governanceOverall,
        errorCount: pickNumber(governanceSummary["error"]),
        warningCount: pickNumber(governanceSummary["warning"]),
        checks
      },
      artifacts,
      sourceState
    };
  }
}
