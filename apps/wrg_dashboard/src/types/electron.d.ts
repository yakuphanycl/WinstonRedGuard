export type BridgeSourceState = "valid" | "missing" | "invalid";
export type BridgeActionId =
  | "open_repo_root"
  | "open_artifacts_folder"
  | "open_reports_folder"
  | "open_registry_file"
  | "open_registry_folder";

type BridgeSource = {
  key: "company_health" | "policy_check" | "governance_check" | "app_registry";
  path: string;
  dataState: BridgeSourceState;
  rawJson: string | null;
  parsed: unknown | null;
  updatedAt: string | null;
  error: string | null;
};

type BridgeResult = {
  repoRoot: string;
  readAt: string;
  sources: BridgeSource[];
};

type BridgeActionResult = {
  ok: boolean;
  actionId: BridgeActionId | string;
  targetPath: string | null;
  error: "action_not_allowed" | "missing_target" | "open_failed" | null;
};

declare global {
  interface Window {
    wrgControlCenter?: {
      readSources: () => BridgeResult;
      openLocation: (actionId: BridgeActionId) => Promise<BridgeActionResult>;
    };
  }
}

export {};
