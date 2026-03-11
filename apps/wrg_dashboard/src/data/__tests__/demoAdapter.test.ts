import { describe, expect, it } from "vitest";
import { DemoDashboardAdapter } from "../demoAdapter";

describe("DemoDashboardAdapter", () => {
  it("produces stable demo dashboard model", async () => {
    const result = await new DemoDashboardAdapter().load();
    expect(result.overall).toBe("WARN");
    expect(result.sourceState.registry).toBe("missing");
    expect(result.summaryCards.length).toBeGreaterThan(5);
    expect(result.layers.length).toBeGreaterThan(3);
    expect(result.criticalSignals.length).toBeGreaterThan(0);
    expect(result.relationships.length).toBeGreaterThan(0);
  });

  it("keeps worker rows deterministic", async () => {
    const result = await new DemoDashboardAdapter().load();
    expect(result.workers.map((w) => w.app)).toEqual([
      "app_registry",
      "governance_check",
      "farmer",
      "repo_analyzer"
    ]);
  });

  it("includes enough data to render major panels", async () => {
    const result = await new DemoDashboardAdapter().load();
    expect(result.summaryCards.length).toBeGreaterThan(0);
    expect(result.criticalSignals.length).toBeGreaterThan(0);
    expect(result.layers.length).toBeGreaterThan(0);
    expect(result.workers.length).toBeGreaterThan(0);
    expect(result.pulse.length).toBeGreaterThan(0);
    expect(result.nextActions.length).toBeGreaterThan(0);
  });
});
