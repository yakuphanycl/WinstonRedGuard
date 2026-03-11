import { useMemo, useState } from "react";
import type { DashboardData } from "../types/dashboard";
import { buildDesktopActions } from "../data/desktopActions";
import { useLanguage } from "../i18n/useLanguage";
import type { BridgeActionId } from "../types/electron";

type Props = {
  data: DashboardData;
};

function toMessageKey(error: string | null): string {
  if (error === "missing_target") {
    return "action.result.missingTarget";
  }
  if (error === "open_failed") {
    return "action.result.openFailed";
  }
  return "action.result.notAllowed";
}

export function DesktopActionsPanel({ data }: Props): JSX.Element {
  const { t } = useLanguage();
  const [status, setStatus] = useState<{ type: "ok" | "error"; text: string } | null>(null);
  const hasBridge = Boolean(window.wrgControlCenter?.openLocation);
  const actions = useMemo(() => buildDesktopActions(data, hasBridge), [data, hasBridge]);

  async function run(actionId: BridgeActionId): Promise<void> {
    if (!window.wrgControlCenter?.openLocation) {
      setStatus({ type: "error", text: t("action.result.desktopOnly") });
      return;
    }
    const result = await window.wrgControlCenter.openLocation(actionId);
    if (result.ok) {
      setStatus({ type: "ok", text: t("action.result.opened") });
      return;
    }
    setStatus({ type: "error", text: t(toMessageKey(result.error)) });
  }

  return (
    <section className="panel">
      <h2>{t("panel.desktopActions")}</h2>
      <ul className="action-buttons">
        {actions.map((action) => (
          <li key={action.id}>
            <button
              type="button"
              className="desktop-action-btn"
              disabled={!action.enabled}
              onClick={() => void run(action.id)}
              title={action.disabledReasonKey ? t(action.disabledReasonKey) : ""}
            >
              {t(action.labelKey)}
            </button>
            {action.disabledReasonKey ? <p className="action-note">{t(action.disabledReasonKey)}</p> : null}
          </li>
        ))}
      </ul>
      {status ? <p className={`action-result action-result-${status.type}`}>{status.text}</p> : null}
    </section>
  );
}
