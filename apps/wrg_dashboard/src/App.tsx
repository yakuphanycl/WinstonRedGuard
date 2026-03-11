import { useCallback, useEffect, useState } from "react";
import { loadDashboardData } from "./data/loadDashboardData";
import { LanguageProvider } from "./i18n/LanguageContext";
import { useLanguage } from "./i18n/useLanguage";
import type { DashboardData } from "./types/dashboard";
import { SidebarNav } from "./layout/SidebarNav";
import type { ControlPage } from "./layout/SidebarNav";
import { ArtifactsPage } from "./pages/ArtifactsPage";
import { GovernancePage } from "./pages/GovernancePage";
import { OverviewPage } from "./pages/OverviewPage";
import { SettingsPage } from "./pages/SettingsPage";
import { SignalsPage } from "./pages/SignalsPage";
import { WorkersPage } from "./pages/WorkersPage";

function sourceLabel(state: DashboardData["sourceState"]["companyHealth"], t: ReturnType<typeof useLanguage>["t"]): string {
  return t(`source.${state}`);
}

function sourceKindLabel(kind: DashboardData["sourceKind"], t: ReturnType<typeof useLanguage>["t"]): string {
  return t(`sourceKind.${kind}`);
}

function renderPage(
  page: ControlPage,
  data: DashboardData,
  language: "en" | "tr",
  setLanguage: (next: "en" | "tr") => void
): JSX.Element {
  if (page === "workers") {
    return <WorkersPage data={data} />;
  }
  if (page === "governance") {
    return <GovernancePage data={data} />;
  }
  if (page === "artifacts") {
    return <ArtifactsPage data={data} />;
  }
  if (page === "signals") {
    return <SignalsPage data={data} />;
  }
  if (page === "settings") {
    return <SettingsPage data={data} language={language} onLanguageChange={setLanguage} />;
  }
  return <OverviewPage data={data} />;
}

function AppContent(): JSX.Element {
  const { language, setLanguage, t } = useLanguage();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activePage, setActivePage] = useState<ControlPage>("overview");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await loadDashboardData();
      setData(result);
    } catch {
      setError("failed to load dashboard data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <main className="app-shell">
        <p>{t("app.loading")}</p>
      </main>
    );
  }

  if (error || data === null) {
    return (
      <main className="app-shell">
        <section className="panel error-panel">
          <h1>{t("app.title")}</h1>
          <p>{t("app.notAvailable")}</p>
          <p>{error ?? t("app.error.unknown")}</p>
        </section>
      </main>
    );
  }

  const hasInvalidSource =
    data.sourceState.companyHealth === "invalid" ||
    data.sourceState.policyCheck === "invalid" ||
    data.sourceState.governanceCheck === "invalid" ||
    data.sourceState.registry === "invalid";

  return (
    <main className="app-shell control-shell">
      <header className="topbar control-topbar">
        <div className="title-block">
          <h1>{t("app.title")}</h1>
          <p>{t("app.subtitle")}</p>
        </div>
        <div className="meta-block">
          <div className="toolbar">
            <button type="button" className="refresh-btn" onClick={load}>
              {t("header.refresh")}
            </button>
            <label htmlFor="lang-select" className="lang-label">
              {t("ui.language")}
            </label>
            <select
              id="lang-select"
              aria-label={t("ui.language")}
              value={language}
              onChange={(event) => setLanguage(event.target.value as "en" | "tr")}
              className="lang-select"
            >
              <option value="en">{t("ui.language.en")}</option>
              <option value="tr">{t("ui.language.tr")}</option>
            </select>
          </div>
          <span>
            {t("meta.generatedAt")}: {data.generatedAt}
          </span>
          <span>
            {t("meta.refreshedAt")}: {data.refreshedAt}
          </span>
          <span>
            {t("meta.sourceKind")}: {sourceKindLabel(data.sourceKind, t)}
          </span>
          <span>
            {t("meta.overallSource")}: {t(`overallSource.${data.overallSource}`)}
          </span>
          <span>
            {t("meta.companyHealth")}: {sourceLabel(data.sourceState.companyHealth, t)}
          </span>
          <span>
            {t("meta.policyCheck")}: {sourceLabel(data.sourceState.policyCheck, t)}
          </span>
          <span>
            {t("meta.governanceCheck")}: {sourceLabel(data.sourceState.governanceCheck, t)}
          </span>
          <span>
            {t("meta.appRegistry")}: {sourceLabel(data.sourceState.registry, t)}
          </span>
        </div>
      </header>

      {hasInvalidSource ? (
        <section className="panel error-panel">
          <strong>{t("app.error.artifactParseTitle")}</strong>
          <p>{t("app.error.artifactParseDetail")}</p>
        </section>
      ) : null}

      <div className="control-body">
        <SidebarNav active={activePage} onChange={setActivePage} />
        <section className="content-area">{renderPage(activePage, data, language, setLanguage)}</section>
      </div>
    </main>
  );
}

export default function App(): JSX.Element {
  return (
    <LanguageProvider>
      <AppContent />
    </LanguageProvider>
  );
}
