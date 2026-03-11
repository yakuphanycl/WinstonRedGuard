import type { ActionItem, CriticalSignal, HealthStatus, LayerItem, RelationshipEdge, SignalSeverity, WorkerRow } from "../types/dashboard";

type SourceState = "valid" | "partial" | "missing" | "invalid";

type BuildParams = {
  workers: WorkerRow[];
  companyOverall: HealthStatus;
  policyOverall: HealthStatus;
  governanceOverall: HealthStatus;
  sourceState: {
    companyHealth: SourceState;
    policyCheck: SourceState;
    governanceCheck: SourceState;
    registry: SourceState;
  };
};

type WorkerMetrics = {
  total: number;
  active: number;
  quarantine: number;
  retired: number;
  unverified: number;
  averageScore: number | null;
};

const severityOrder: Record<SignalSeverity, number> = {
  ERROR: 0,
  WARNING: 1,
  INFO: 2
};

function toLower(v: string): string {
  return v.trim().toLowerCase();
}

function statusFromSource(source: SourceState): HealthStatus {
  if (source === "valid") {
    return "PASS";
  }
  if (source === "partial") {
    return "WARN";
  }
  if (source === "invalid") {
    return "FAIL";
  }
  return "WARN";
}

export function computeWorkerMetrics(workers: WorkerRow[]): WorkerMetrics {
  const total = workers.length;
  const active = workers.filter((w) => toLower(w.statusText) === "active").length;
  const quarantine = workers.filter((w) => toLower(w.statusText) === "quarantine").length;
  const retired = workers.filter((w) => toLower(w.statusText) === "retired").length;
  const unverified = workers.filter((w) => w.verified !== "true").length;
  const scores = workers
    .map((w) => Number.parseFloat(w.score))
    .filter((n) => Number.isFinite(n));
  const averageScore = scores.length === 0 ? null : scores.reduce((a, b) => a + b, 0) / scores.length;

  return {
    total,
    active,
    quarantine,
    retired,
    unverified,
    averageScore
  };
}

export function buildCriticalSignals(params: BuildParams): CriticalSignal[] {
  const metrics = computeWorkerMetrics(params.workers);
  const signals: CriticalSignal[] = [];

  signals.push({
    severity: metrics.retired > 0 ? "WARNING" : "INFO",
    code: "retired_worker_count",
    label: "Retired workers",
    value: String(metrics.retired)
  });
  signals.push({
    severity: metrics.quarantine > 0 ? "ERROR" : "INFO",
    code: "quarantine_worker_count",
    label: "Quarantine workers",
    value: String(metrics.quarantine)
  });
  signals.push({
    severity: metrics.unverified > 0 ? "WARNING" : "INFO",
    code: "unverified_worker_count",
    label: "Unverified workers",
    value: String(metrics.unverified)
  });

  const avgLabel = metrics.averageScore === null ? "n/a" : metrics.averageScore.toFixed(2);
  const avgSeverity: SignalSeverity =
    metrics.averageScore === null ? "WARNING" : metrics.averageScore < 5 ? "WARNING" : "INFO";
  signals.push({
    severity: avgSeverity,
    code: "average_score_low",
    label: "Average score",
    value: avgLabel
  });

  signals.push({
    severity:
      params.governanceOverall === "FAIL" ? "ERROR" : params.governanceOverall === "WARN" ? "WARNING" : "INFO",
    code: "governance_status",
    label: "Governance status",
    value: params.governanceOverall
  });

  signals.push({
    severity: params.policyOverall === "FAIL" ? "ERROR" : params.policyOverall === "WARN" ? "WARNING" : "INFO",
    code: "policy_status",
    label: "Policy status",
    value: params.policyOverall
  });

  signals.push({
    severity: params.companyOverall === "FAIL" ? "ERROR" : params.companyOverall === "WARN" ? "WARNING" : "INFO",
    code: "company_overall_status",
    label: "Company overall",
    value: params.companyOverall
  });

  return signals.sort((a, b) => {
    const bySeverity = severityOrder[a.severity] - severityOrder[b.severity];
    if (bySeverity !== 0) {
      return bySeverity;
    }
    const byCode = a.code.localeCompare(b.code);
    if (byCode !== 0) {
      return byCode;
    }
    return a.label.localeCompare(b.label);
  });
}

export function buildLayerHealth(params: BuildParams): LayerItem[] {
  const metrics = computeWorkerMetrics(params.workers);

  const managementStatus = params.companyOverall;
  const managementIssues = managementStatus === "FAIL" ? 1 : managementStatus === "WARN" ? 1 : 0;

  const evaluationIssues = metrics.unverified + metrics.quarantine;
  const evaluationStatus: HealthStatus = evaluationIssues > 0 ? "WARN" : "PASS";

  const governanceIssues =
    (params.governanceOverall === "FAIL" ? 1 : 0) +
    (params.policyOverall === "FAIL" ? 1 : 0) +
    (params.governanceOverall === "WARN" ? 1 : 0) +
    (params.policyOverall === "WARN" ? 1 : 0);
  const governanceStatus: HealthStatus =
    params.governanceOverall === "FAIL" || params.policyOverall === "FAIL"
      ? "FAIL"
      : governanceIssues > 0
        ? "WARN"
        : "PASS";

  const factoryStatus = statusFromSource(params.sourceState.registry);
  const observationStatus: HealthStatus =
    params.sourceState.companyHealth === "missing" && params.sourceState.governanceCheck === "missing" ? "WARN" : "PASS";
  const pilotStatus: HealthStatus = metrics.quarantine > 0 ? "FAIL" : metrics.unverified > 0 ? "WARN" : "PASS";

  return [
    {
      name: "Management",
      relatedSystems: ["company_health", "wrg_dashboard"],
      status: managementStatus,
      detail: `overall=${params.companyOverall}`,
      issueCount: managementIssues
    },
    {
      name: "Evaluation",
      relatedSystems: ["app_registry", "app_evaluator"],
      status: evaluationStatus,
      detail: `unverified=${metrics.unverified}, quarantine=${metrics.quarantine}`,
      issueCount: evaluationIssues
    },
    {
      name: "Governance",
      relatedSystems: ["governance_check", "policy_check"],
      status: governanceStatus,
      detail: `governance=${params.governanceOverall}, policy=${params.policyOverall}`,
      issueCount: governanceIssues
    },
    {
      name: "Factory",
      relatedSystems: ["devtool_genome", "app_registry"],
      status: factoryStatus,
      detail: `registry=${params.sourceState.registry}`,
      issueCount: params.sourceState.registry === "valid" ? 0 : 1
    },
    {
      name: "Observation",
      relatedSystems: ["repo_analyzer", "wrg_dashboard"],
      status: observationStatus,
      detail: `company_health=${params.sourceState.companyHealth}, governance=${params.sourceState.governanceCheck}`,
      issueCount: observationStatus === "PASS" ? 0 : 1
    },
    {
      name: "Pilot Workers",
      relatedSystems: ["farmer", "refinery", "repo_doctor"],
      status: pilotStatus,
      detail: `active=${metrics.active}, quarantine=${metrics.quarantine}, retired=${metrics.retired}`,
      issueCount: metrics.quarantine + metrics.retired
    }
  ];
}

export function buildRelationshipMap(params: BuildParams): RelationshipEdge[] {
  return [
    {
      from: "app_registry",
      to: "app_evaluator",
      relation: "evaluation inventory",
      status: statusFromSource(params.sourceState.registry)
    },
    {
      from: "app_registry",
      to: "wrg_dashboard",
      relation: "worker table source",
      status: statusFromSource(params.sourceState.registry)
    },
    {
      from: "governance_check",
      to: "company_health",
      relation: "governance signal",
      status: statusFromSource(params.sourceState.governanceCheck)
    },
    {
      from: "policy_check",
      to: "company_health",
      relation: "policy signal",
      status: statusFromSource(params.sourceState.policyCheck)
    },
    {
      from: "devtool_genome",
      to: "app_registry",
      relation: "factory registration",
      status: statusFromSource(params.sourceState.registry)
    },
    {
      from: "repo_analyzer",
      to: "wrg_dashboard",
      relation: "observability input",
      status: statusFromSource(params.sourceState.companyHealth)
    }
  ];
}

export function buildActionItems(params: BuildParams): ActionItem[] {
  const metrics = computeWorkerMetrics(params.workers);
  const items = new Set<string>();

  if (metrics.quarantine > 0) {
    items.add("Run reevaluate flow for quarantine workers.");
  }
  if (metrics.unverified > 0) {
    items.add("Verify unverified workers and update registry metadata.");
  }
  if (params.governanceOverall === "FAIL") {
    items.add("Fix governance ERROR findings before release.");
  } else if (params.governanceOverall === "WARN") {
    items.add("Review governance warnings for class/stage drift.");
  }
  if (params.policyOverall !== "PASS") {
    items.add("Generate fresh policy_check artifact and clear policy warnings.");
  }
  if (params.sourceState.registry !== "valid") {
    items.add("Fix registry route/config so dashboard can read app_registry.");
  }
  if (params.companyOverall === "FAIL") {
    items.add("Stabilize company health totals before next gate run.");
  }

  const ordered = Array.from(items).sort((a, b) => a.localeCompare(b));
  const bounded = ordered.slice(0, 6);
  if (bounded.length < 3) {
    bounded.push("Keep release artifacts refreshed after each gate run.");
  }

  return bounded.map((text) => ({
    priority: text.toLowerCase().includes("fix") || text.toLowerCase().includes("error") ? "high" : text.toLowerCase().includes("review") ? "medium" : "low",
    text
  }));
}
