import { useMemo, useState } from "react";
import type { DashboardData } from "../types/dashboard";
import { useLanguage } from "../i18n/useLanguage";

type Props = {
  data: DashboardData;
};

export function ArtifactsPage({ data }: Props): JSX.Element {
  const { t } = useLanguage();
  const [selected, setSelected] = useState<string | null>(null);

  const selectedRaw = useMemo(() => {
    const row = data.artifacts.find((a) => a.key === selected);
    if (!row) {
      return null;
    }
    return row.rawJson;
  }, [data.artifacts, selected]);

  return (
    <div className="grid-two">
      <section className="panel">
        <h2>{t("panel.artifactSources")}</h2>
        <table className="worker-table">
          <thead>
            <tr>
              <th>{t("artifacts.col.key")}</th>
              <th>{t("artifacts.col.path")}</th>
              <th>{t("artifacts.col.state")}</th>
              <th>{t("artifacts.col.updatedAt")}</th>
              <th>{t("artifacts.col.kind")}</th>
              <th>{t("artifacts.col.message")}</th>
            </tr>
          </thead>
          <tbody>
            {data.artifacts.map((row) => (
              <tr key={row.key} onClick={() => setSelected(row.key)} className="artifact-row">
                <td>{row.key}</td>
                <td>{row.path}</td>
                <td>{row.dataState}</td>
                <td>{row.updatedAt ?? "n/a"}</td>
                <td>{row.sourceKind}</td>
                <td>{row.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section className="panel">
        <h2>{t("panel.rawJson")}</h2>
        {selected === null ? (
          <p>{t("artifacts.raw.placeholder")}</p>
        ) : selectedRaw === null ? (
          <p>{t("artifacts.raw.unavailable")}</p>
        ) : (
          <pre className="raw-json">{selectedRaw}</pre>
        )}
      </section>
    </div>
  );
}
