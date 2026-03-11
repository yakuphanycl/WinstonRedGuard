import { describe, expect, it } from "vitest";
import { buildActionItems, buildCriticalSignals, buildLayerHealth, buildRelationshipMap } from "../insights";
import { dashboardWith } from "./fixtures";
import type { WorkerRow } from "../../types/dashboard";

function baseParams(workers: WorkerRow[] = []) {
  const data = dashboardWith({ workers });
  return {
    workers: data.workers,
    companyOverall: data.overall,
    policyOverall: "PASS" as const,
    governanceOverall: "PASS" as const,
    sourceState: data.sourceState
  };
}

const workers: WorkerRow[] = [
  {
    app: "a",
    statusText: "active",
    verified: "true",
    score: "8",
    lastVerifiedAt: "x",
    appPath: "apps/a",
    appClass: "worker",
    productizationStage: "internal_mvp",
    status: "PASS"
  },
  {
    app: "b",
    statusText: "quarantine",
    verified: "false",
    score: "3",
    lastVerifiedAt: "x",
    appPath: "apps/b",
    appClass: "worker",
    productizationStage: "experimental_lab",
    status: "FAIL"
  }
];

describe("insights", () => {
  it("builds critical signals from worker status counts", () => {
    const signals = buildCriticalSignals(baseParams(workers));
    expect(signals.find((s) => s.code === "quarantine_worker_count")?.value).toBe("1");
    expect(signals.find((s) => s.code === "unverified_worker_count")?.value).toBe("1");
  });

  it("flags low average score when threshold is met", () => {
    const lowWorkers = [{ ...workers[0], score: "4" }, { ...workers[1], score: "3" }];
    const signals = buildCriticalSignals(baseParams(lowWorkers));
    expect(signals.find((s) => s.code === "average_score_low")?.severity).toBe("WARNING");
  });

  it("does not flag low average score when threshold is not met", () => {
    const strongWorkers = [{ ...workers[0] }, { ...workers[0], app: "c", score: "9" }];
    const signals = buildCriticalSignals(baseParams(strongWorkers));
    expect(signals.find((s) => s.code === "average_score_low")?.severity).toBe("INFO");
  });

  it("creates governance fail/warn signals correctly", () => {
    const failSignals = buildCriticalSignals({ ...baseParams(workers), governanceOverall: "FAIL" });
    expect(failSignals.find((s) => s.code === "governance_status")?.severity).toBe("ERROR");

    const warnSignals = buildCriticalSignals({ ...baseParams(workers), governanceOverall: "WARN" });
    expect(warnSignals.find((s) => s.code === "governance_status")?.severity).toBe("WARNING");
  });

  it("creates policy fail/warn signals correctly", () => {
    const failSignals = buildCriticalSignals({ ...baseParams(workers), policyOverall: "FAIL" });
    expect(failSignals.find((s) => s.code === "policy_status")?.severity).toBe("ERROR");

    const warnSignals = buildCriticalSignals({ ...baseParams(workers), policyOverall: "WARN" });
    expect(warnSignals.find((s) => s.code === "policy_status")?.severity).toBe("WARNING");
  });

  it("keeps deterministic ordering by severity/code/label", () => {
    const signals = buildCriticalSignals({ ...baseParams(workers), governanceOverall: "FAIL" });
    const sorted = [...signals].sort((a, b) => {
      const order = { ERROR: 0, WARNING: 1, INFO: 2 };
      const x = order[a.severity] - order[b.severity];
      if (x !== 0) {
        return x;
      }
      const y = a.code.localeCompare(b.code);
      if (y !== 0) {
        return y;
      }
      return a.label.localeCompare(b.label);
    });
    expect(signals).toEqual(sorted);
  });

  it("generates next actions deterministically and deduplicated within range", () => {
    const actions = buildActionItems({
      ...baseParams(workers),
      companyOverall: "FAIL",
      governanceOverall: "FAIL",
      policyOverall: "WARN",
      sourceState: { companyHealth: "valid", policyCheck: "missing", governanceCheck: "valid", registry: "missing" }
    });
    const texts = actions.map((a) => a.text);
    expect(actions.length).toBeGreaterThanOrEqual(3);
    expect(actions.length).toBeLessThanOrEqual(6);
    expect(new Set(texts).size).toBe(texts.length);
    expect(texts).toEqual([...texts].sort((a, b) => a.localeCompare(b)));
  });

  it("builds layer breakdown with issue counts and related systems", () => {
    const layers = buildLayerHealth({ ...baseParams(workers), governanceOverall: "FAIL" });
    expect(layers.length).toBe(6);
    expect(layers.every((l) => l.relatedSystems.length > 0)).toBe(true);
    expect(layers.every((l) => l.issueCount >= 0)).toBe(true);
  });

  it("returns stable relationship map with partial input", () => {
    const map = buildRelationshipMap({
      ...baseParams([]),
      sourceState: { companyHealth: "missing", policyCheck: "missing", governanceCheck: "invalid", registry: "missing" }
    });
    expect(map.length).toBe(6);
    expect(map[0]).toMatchObject({ from: "app_registry", to: "app_evaluator" });
  });

  it("handles empty input safely", () => {
    const params = baseParams([]);
    const signals = buildCriticalSignals(params);
    const actions = buildActionItems(params);
    const layers = buildLayerHealth(params);
    const map = buildRelationshipMap(params);
    expect(signals.length).toBeGreaterThan(0);
    expect(actions.length).toBeGreaterThan(0);
    expect(layers.length).toBe(6);
    expect(map.length).toBe(6);
  });
});
