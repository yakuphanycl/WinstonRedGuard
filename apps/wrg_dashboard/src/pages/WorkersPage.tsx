import { useMemo, useState } from "react";
import type { DashboardData } from "../types/dashboard";
import { useLanguage } from "../i18n/useLanguage";
import { WorkerTable } from "../components/WorkerTable";

type Props = {
  data: DashboardData;
};

export function WorkersPage({ data }: Props): JSX.Element {
  const { t } = useLanguage();
  const [filter, setFilter] = useState<string>("all");

  const statuses = useMemo(() => {
    const set = new Set<string>();
    for (const row of data.workers) {
      set.add(row.statusText);
    }
    return ["all", ...Array.from(set).sort((a, b) => a.localeCompare(b))];
  }, [data.workers]);

  const filtered = useMemo(() => {
    const rows = filter === "all" ? data.workers : data.workers.filter((row) => row.statusText === filter);
    return [...rows].sort((a, b) => a.app.localeCompare(b.app));
  }, [data.workers, filter]);

  return (
    <>
      <section className="panel filter-bar">
        <label htmlFor="worker-status-filter">{t("worker.filter.status")}</label>
        <select id="worker-status-filter" value={filter} onChange={(event) => setFilter(event.target.value)}>
          {statuses.map((value) => (
            <option key={value} value={value}>
              {value === "all" ? t("worker.filter.all") : value}
            </option>
          ))}
        </select>
      </section>
      <WorkerTable workers={filtered} />
    </>
  );
}
