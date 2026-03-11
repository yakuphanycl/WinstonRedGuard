import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { dashboardWith } from "../data/__tests__/fixtures";

vi.mock("../data/loadDashboardData", () => ({
  loadDashboardData: vi.fn()
}));

import App from "../App";
import { loadDashboardData } from "../data/loadDashboardData";

function mockLoad(payload: ReturnType<typeof dashboardWith>): void {
  vi.mocked(loadDashboardData).mockResolvedValue(payload);
}

describe("App desktop shell", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("renders default English shell and overview", async () => {
    mockLoad(
      dashboardWith({
        summaryCards: [{ key: "overall", label: "Overall", value: "PASS", status: "PASS" }]
      })
    );

    render(<App />);

    expect(await screen.findByText("WRG Control Center v0.1")).toBeTruthy();
    expect(screen.getByText("Overview")).toBeTruthy();
    expect(screen.getByText("System Summary")).toBeTruthy();
  });

  it("switching to Turkish updates visible labels", async () => {
    mockLoad(
      dashboardWith({
        summaryCards: [{ key: "overall", label: "Overall", value: "PASS", status: "PASS" }]
      })
    );

    render(<App />);

    expect(await screen.findByText("WRG Control Center v0.1")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Language"), { target: { value: "tr" } });

    expect(await screen.findByText("WRG Kontrol Merkezi v0.1")).toBeTruthy();
    expect(screen.getByText("Genel Bakis")).toBeTruthy();
    expect(screen.getByText("Sistem Ozeti")).toBeTruthy();
  });

  it("renders degraded state without crash for invalid/partial sources", async () => {
    mockLoad(
      dashboardWith({
        sourceState: {
          companyHealth: "missing",
          policyCheck: "partial",
          governanceCheck: "invalid",
          registry: "missing"
        }
      })
    );

    render(<App />);
    expect(await screen.findByText("WRG Control Center v0.1")).toBeTruthy();
    expect(screen.getByText("artifact parse error")).toBeTruthy();
    expect(screen.getByText(/policy_check: partial/i)).toBeTruthy();
    expect(screen.getByText(/governance_check: invalid/i)).toBeTruthy();
  });

  it("navigates to workers and artifacts pages", async () => {
    mockLoad(
      dashboardWith({
        workers: [
          {
            app: "app_registry",
            statusText: "active",
            verified: "true",
            score: "8",
            lastVerifiedAt: "2026-03-08T10:01:00Z",
            appPath: "apps/app_registry",
            appClass: "internal_infra",
            productizationStage: "internal_operational",
            status: "PASS"
          }
        ],
        artifacts: [
          {
            key: "company_health",
            path: "artifacts/company_health.json",
            sourceKind: "canonical",
            dataState: "valid",
            updatedAt: "2026-03-08T10:00:00Z",
            message: "valid",
            rawJson: "{\"overall\":\"PASS\"}"
          }
        ]
      })
    );

    render(<App />);
    expect(await screen.findByText("WRG Control Center v0.1")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Workers" }));
    expect(screen.getByText("Worker / App Table")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Artifacts" }));
    expect(screen.getByText("Artifact Sources")).toBeTruthy();
  });

  it("shows desktop actions as unavailable in browser mode", async () => {
    mockLoad(dashboardWith({}));

    render(<App />);
    expect(await screen.findByText("WRG Control Center v0.1")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Settings" }));
    expect(screen.getByText("Desktop Actions")).toBeTruthy();
    expect(screen.getAllByText("Available only in Electron desktop mode").length).toBeGreaterThan(0);
  });
});
