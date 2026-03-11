import type { DashboardData } from "../types/dashboard";
import { useLanguage } from "../i18n/useLanguage";
import { StatusBadge } from "../components/StatusBadge";

type Props = {
  data: DashboardData;
};

export function GovernancePage({ data }: Props): JSX.Element {
  const { t } = useLanguage();

  return (
    <div className="grid-two">
      <section className="panel">
        <h2>{t("panel.governanceSummary")}</h2>
        <p>{t("governance.overall")}: <strong>{data.governance.overall}</strong></p>
        <p>{t("governance.errors")}: <strong>{data.governance.errorCount}</strong></p>
        <p>{t("governance.warnings")}: <strong>{data.governance.warningCount}</strong></p>
      </section>
      <section className="panel">
        <h2>{t("panel.governanceChecks")}</h2>
        {data.governance.checks.length === 0 ? (
          <p>{t("governance.noChecks")}</p>
        ) : (
          <ul className="list-block">
            {data.governance.checks.map((check) => (
              <li key={`${check.app}-${check.level}`} className="list-row">
                <div>
                  <strong>{check.app}</strong>
                  <p>issues={check.issueCount}</p>
                </div>
                <StatusBadge value={check.level === "ERROR" ? "FAIL" : check.level === "WARNING" ? "WARN" : "PASS"} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
