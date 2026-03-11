const { contextBridge, shell } = require("electron");
const fs = require("node:fs");
const path = require("node:path");

const repoRoot = process.env.WRG_REPO_ROOT
  ? path.resolve(process.env.WRG_REPO_ROOT)
  : path.resolve(__dirname, "..", "..", "..");

const files = [
  { key: "company_health", relPath: path.join("artifacts", "company_health.json") },
  { key: "policy_check", relPath: path.join("artifacts", "policy_check.json") },
  { key: "governance_check", relPath: path.join("artifacts", "governance_check.json") },
  { key: "app_registry", relPath: path.join("apps", "app_registry", "data", "registry.json") }
];

const locationMap = {
  open_repo_root: () => repoRoot,
  open_artifacts_folder: () => path.join(repoRoot, "artifacts"),
  open_reports_folder: () => path.join(repoRoot, "artifacts", "reports"),
  open_registry_file: () => path.join(repoRoot, "apps", "app_registry", "data", "registry.json"),
  open_registry_folder: () => path.join(repoRoot, "apps", "app_registry", "data")
};

function readOne(spec) {
  const absPath = path.join(repoRoot, spec.relPath);
  try {
    if (!fs.existsSync(absPath)) {
      return {
        key: spec.key,
        path: absPath,
        dataState: "missing",
        rawJson: null,
        parsed: null,
        updatedAt: null,
        error: "missing"
      };
    }

    const raw = fs.readFileSync(absPath, "utf8");
    const stat = fs.statSync(absPath);
    try {
      const parsed = JSON.parse(raw);
      return {
        key: spec.key,
        path: absPath,
        dataState: "valid",
        rawJson: raw,
        parsed,
        updatedAt: stat.mtime.toISOString(),
        error: null
      };
    } catch {
      return {
        key: spec.key,
        path: absPath,
        dataState: "invalid",
        rawJson: raw,
        parsed: null,
        updatedAt: stat.mtime.toISOString(),
        error: "invalid_json"
      };
    }
  } catch {
    return {
      key: spec.key,
      path: absPath,
      dataState: "invalid",
      rawJson: null,
      parsed: null,
      updatedAt: null,
      error: "read_error"
    };
  }
}

async function openLocation(actionId) {
  const resolver = locationMap[actionId];
  if (!resolver) {
    return {
      ok: false,
      actionId,
      targetPath: null,
      error: "action_not_allowed"
    };
  }

  const targetPath = resolver();
  if (!fs.existsSync(targetPath)) {
    return {
      ok: false,
      actionId,
      targetPath,
      error: "missing_target"
    };
  }

  const err = await shell.openPath(targetPath);
  if (err) {
    return {
      ok: false,
      actionId,
      targetPath,
      error: "open_failed"
    };
  }

  return {
    ok: true,
    actionId,
    targetPath,
    error: null
  };
}

contextBridge.exposeInMainWorld("wrgControlCenter", {
  readSources() {
    return {
      repoRoot,
      readAt: new Date().toISOString(),
      sources: files.map(readOne)
    };
  },
  openLocation
});
