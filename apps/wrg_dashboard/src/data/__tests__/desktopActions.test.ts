import { describe, expect, it } from "vitest";
import { buildDesktopActions } from "../desktopActions";
import { dashboardWith } from "./fixtures";

describe("desktopActions", () => {
  it("keeps allowlist deterministic and explicit", () => {
    const actions = buildDesktopActions(dashboardWith({ artifacts: [] }), true);
    expect(actions.map((a) => a.id)).toEqual([
      "open_repo_root",
      "open_artifacts_folder",
      "open_reports_folder",
      "open_registry_file",
      "open_registry_folder"
    ]);
  });

  it("returns disabled actions in non-desktop mode", () => {
    const actions = buildDesktopActions(dashboardWith({}), false);
    expect(actions.every((a) => a.enabled === false)).toBe(true);
    expect(actions.every((a) => a.disabledReasonKey === "action.reason.desktopOnly")).toBe(true);
  });

  it("enables allowlisted actions in desktop mode", () => {
    const actions = buildDesktopActions(
      dashboardWith({
        artifacts: [
          {
            key: "app_registry",
            path: "apps/app_registry/data/registry.json",
            sourceKind: "canonical",
            dataState: "valid",
            updatedAt: null,
            message: "valid",
            rawJson: null
          }
        ]
      }),
      true
    );
    expect(actions.find((a) => a.id === "open_repo_root")?.enabled).toBe(true);
    expect(actions.find((a) => a.id === "open_registry_file")?.enabled).toBe(true);
  });

  it("keeps registry actions disabled when registry metadata is unavailable", () => {
    const actions = buildDesktopActions(dashboardWith({ artifacts: [] }), true);
    expect(actions.find((a) => a.id === "open_registry_file")).toMatchObject({
      enabled: false,
      disabledReasonKey: "action.reason.registryUnavailable"
    });
  });
});
