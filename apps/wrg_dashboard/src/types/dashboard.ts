export type HealthStatus = "PASS" | "WARN" | "FAIL";
export type DataState = "valid" | "partial" | "missing" | "invalid";
export type SourceKind = "canonical" | "derived" | "demo";

export type SummaryCard = {
  key: string;
  label: string;
  value: string;
  status: HealthStatus;
};

export type LayerItem = {
  name: string;
  status: HealthStatus;
  detail: string;
  relatedSystems: string[];
  issueCount: number;
};

export type WorkerRow = {
  app: string;
  statusText: string;
  verified: string;
  score: string;
  lastVerifiedAt: string;
  appPath: string;
  appClass: string;
  productizationStage: string;
  status: HealthStatus;
};

export type PulseItem = {
  level: HealthStatus;
  message: string;
};

export type ActionItem = {
  priority: "high" | "medium" | "low";
  text: string;
};

export type SignalSeverity = "ERROR" | "WARNING" | "INFO";

export type CriticalSignal = {
  severity: SignalSeverity;
  code: string;
  label: string;
  value: string;
};

export type RelationshipEdge = {
  from: string;
  to: string;
  relation: string;
  status: HealthStatus;
};

export type DashboardData = {
  repoRoot: string;
  generatedAt: string;
  overall: HealthStatus;
  overallSource: "company_health" | "derived";
  sourceKind: SourceKind;
  refreshedAt: string;
  summaryCards: SummaryCard[];
  layers: LayerItem[];
  criticalSignals: CriticalSignal[];
  relationships: RelationshipEdge[];
  workers: WorkerRow[];
  pulse: PulseItem[];
  nextActions: ActionItem[];
  governance: {
    overall: HealthStatus;
    errorCount: number;
    warningCount: number;
    checks: Array<{ app: string; level: string; issueCount: number }>;
  };
  artifacts: Array<{
    key: "company_health" | "policy_check" | "governance_check" | "app_registry";
    path: string;
    sourceKind: SourceKind;
    dataState: DataState;
    updatedAt: string | null;
    message: string;
    rawJson: string | null;
  }>;
  sourceState: {
    companyHealth: DataState;
    policyCheck: DataState;
    governanceCheck: DataState;
    registry: DataState;
  };
};
