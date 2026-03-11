import type { WorkerRow } from "../types/dashboard";
import { useLanguage } from "../i18n/useLanguage";
import { StatusBadge } from "./StatusBadge";

type Props = {
  workers: WorkerRow[];
};

export function WorkerTable({ workers }: Props): JSX.Element {
  const { t } = useLanguage();

  return (
    <section className="panel">
      <h2>{t("panel.workerTable")}</h2>
      <table className="worker-table">
        <thead>
          <tr>
            <th>{t("worker.col.app")}</th>
            <th>{t("worker.col.status")}</th>
            <th>{t("worker.col.verified")}</th>
            <th>{t("worker.col.score")}</th>
            <th>{t("worker.col.lastVerified")}</th>
            <th>{t("worker.col.class")}</th>
            <th>{t("worker.col.stage")}</th>
            <th>{t("worker.col.appPath")}</th>
            <th>{t("worker.col.health")}</th>
          </tr>
        </thead>
        <tbody>
          {workers.length === 0 ? (
            <tr>
              <td colSpan={9}>{t("worker.registryUnavailable")}</td>
            </tr>
          ) : (
            workers.map((row) => (
              <tr key={row.app}>
                <td>{row.app}</td>
                <td>{row.statusText}</td>
                <td>{row.verified}</td>
                <td>{row.score}</td>
                <td>{row.lastVerifiedAt}</td>
                <td>{row.appClass}</td>
                <td>{row.productizationStage}</td>
                <td>{row.appPath}</td>
                <td>
                  <StatusBadge value={row.status} />
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </section>
  );
}
