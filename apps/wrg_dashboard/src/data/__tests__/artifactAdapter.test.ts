import { afterEach, describe, expect, it, vi } from "vitest";
import { ArtifactDashboardAdapter } from "../artifactAdapter";
import { validCompanyHealth, validGovernance, validPolicy, validRegistry } from "./fixtures";

type RouteMap = Record<string, { status?: number; body: unknown; raw?: boolean }>;

function mockFetch(routes: RouteMap): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string | URL) => {
      const path = String(input);
      const route = routes[path];
      if (!route) {
        return new Response("not found", { status: 404 });
      }
      const status = route.status ?? 200;
      if (route.raw) {
        return new Response(String(route.body), { status });
      }
      return new Response(JSON.stringify(route.body), { status });
    })
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ArtifactDashboardAdapter", () => {
  it("normalizes valid artifacts into stable model", async () => {
    mockFetch({
      "/artifacts/company_health.json": { body: validCompanyHealth },
      "/artifacts/policy_check.json": { body: validPolicy },
      "/artifacts/governance_check.json": { body: validGovernance },
      "/registry/app_registry.json": { body: validRegistry }
    });

    const adapter = new ArtifactDashboardAdapter();
    const result = await adapter.load();

    expect(result.overall).toBe("FAIL");
    expect(result.overallSource).toBe("company_health");
    expect(result.sourceState).toEqual({
      companyHealth: "valid",
      policyCheck: "valid",
      governanceCheck: "valid",
      registry: "valid"
    });
    expect(result.workers.map((w) => w.app)).toEqual(["app_registry", "farmer"]);
  });

  it("returns safe defaults when governance artifact is missing", async () => {
    mockFetch({
      "/artifacts/company_health.json": { body: validCompanyHealth },
      "/artifacts/policy_check.json": { body: validPolicy },
      "/registry/app_registry.json": { body: validRegistry }
    });

    const result = await new ArtifactDashboardAdapter().load();
    expect(result.sourceState.governanceCheck).toBe("missing");
    expect(result.layers.length).toBeGreaterThan(0);
  });

  it("returns safe defaults when policy artifact is missing", async () => {
    mockFetch({
      "/artifacts/company_health.json": { body: validCompanyHealth },
      "/artifacts/governance_check.json": { body: validGovernance },
      "/registry/app_registry.json": { body: validRegistry }
    });

    const result = await new ArtifactDashboardAdapter().load();
    expect(result.sourceState.policyCheck).toBe("missing");
    expect(result.criticalSignals.some((s) => s.code === "policy_status")).toBe(true);
  });

  it("returns safe defaults when company health artifact is missing", async () => {
    mockFetch({
      "/artifacts/policy_check.json": { body: validPolicy },
      "/artifacts/governance_check.json": { body: validGovernance },
      "/registry/app_registry.json": { body: validRegistry }
    });

    const result = await new ArtifactDashboardAdapter().load();
    expect(result.sourceState.companyHealth).toBe("missing");
    expect(result.overallSource).toBe("derived");
  });

  it("tolerates partial registry rows", async () => {
    mockFetch({
      "/artifacts/company_health.json": { body: validCompanyHealth },
      "/artifacts/policy_check.json": { body: validPolicy },
      "/artifacts/governance_check.json": { body: validGovernance },
      "/registry/app_registry.json": {
        body: {
          apps: [{ name: "minimal_worker" }]
        }
      }
    });

    const result = await new ArtifactDashboardAdapter().load();
    expect(result.workers[0]).toMatchObject({
      app: "minimal_worker",
      statusText: "unknown",
      verified: "unknown",
      score: "n/a"
    });
  });

  it("marks invalid artifact structures as invalid instead of throwing", async () => {
    mockFetch({
      "/artifacts/company_health.json": { body: "{invalid", raw: true },
      "/artifacts/policy_check.json": { body: validPolicy },
      "/artifacts/governance_check.json": { body: validGovernance },
      "/registry/app_registry.json": { body: validRegistry }
    });

    const result = await new ArtifactDashboardAdapter().load();
    expect(result.sourceState.companyHealth).toBe("invalid");
    expect(result.summaryCards.length).toBeGreaterThan(0);
  });
});
