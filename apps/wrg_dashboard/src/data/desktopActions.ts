import type { DashboardData } from "../types/dashboard";
import type { BridgeActionId } from "../types/electron";

export type DesktopAction = {
  id: BridgeActionId;
  labelKey: string;
  enabled: boolean;
  disabledReasonKey: string | null;
};

const BASE_ACTIONS: Array<{ id: BridgeActionId; labelKey: string }> = [
  { id: "open_repo_root", labelKey: "action.openRepoRoot" },
  { id: "open_artifacts_folder", labelKey: "action.openArtifactsFolder" },
  { id: "open_reports_folder", labelKey: "action.openReportsFolder" },
  { id: "open_registry_file", labelKey: "action.openRegistryFile" },
  { id: "open_registry_folder", labelKey: "action.openRegistryFolder" }
];

function hasArtifact(data: DashboardData, key: DashboardData["artifacts"][number]["key"]): boolean {
  return data.artifacts.some((item) => item.key === key);
}

export function buildDesktopActions(data: DashboardData, hasBridge: boolean): DesktopAction[] {
  return BASE_ACTIONS.map((action) => {
    if (!hasBridge) {
      return {
        id: action.id,
        labelKey: action.labelKey,
        enabled: false,
        disabledReasonKey: "action.reason.desktopOnly"
      };
    }

    if (action.id === "open_registry_file" || action.id === "open_registry_folder") {
      if (!hasArtifact(data, "app_registry")) {
        return {
          id: action.id,
          labelKey: action.labelKey,
          enabled: false,
          disabledReasonKey: "action.reason.registryUnavailable"
        };
      }
    }

    return {
      id: action.id,
      labelKey: action.labelKey,
      enabled: true,
      disabledReasonKey: null
    };
  });
}
