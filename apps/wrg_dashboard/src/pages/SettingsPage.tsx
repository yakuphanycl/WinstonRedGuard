import type { DashboardData } from "../types/dashboard";
import type { Language } from "../i18n/messages";
import { useLanguage } from "../i18n/useLanguage";
import { DesktopActionsPanel } from "../components/DesktopActionsPanel";

type Props = {
  data: DashboardData;
  language: Language;
  onLanguageChange: (next: Language) => void;
};

export function SettingsPage({ data, language, onLanguageChange }: Props): JSX.Element {
  const { t } = useLanguage();

  return (
    <div className="grid-two">
      <section className="panel">
        <h2>{t("panel.settings")}</h2>
        <p>{t("settings.readOnly")}</p>
        <p>
          {t("settings.repoRoot")}: {data.repoRoot}
        </p>
        <label htmlFor="settings-lang">{t("ui.language")}</label>
        <select id="settings-lang" value={language} onChange={(event) => onLanguageChange(event.target.value as Language)}>
          <option value="en">{t("ui.language.en")}</option>
          <option value="tr">{t("ui.language.tr")}</option>
        </select>
        <p>{t("settings.future")}</p>
      </section>
      <DesktopActionsPanel data={data} />
    </div>
  );
}
