import type { CriticalSignal } from "../types/dashboard";
import { useLanguage } from "../i18n/useLanguage";

type Props = {
  signals: CriticalSignal[];
};

export function CriticalSignalsPanel({ signals }: Props): JSX.Element {
  const { t } = useLanguage();

  return (
    <section className="panel">
      <h2>{t("panel.criticalSignals")}</h2>
      <ul className="signal-list">
        {signals.map((signal) => (
          <li key={`${signal.code}-${signal.label}`} className="signal-row">
            <span className={`signal-severity signal-${signal.severity.toLowerCase()}`}>{t(`signal.severity.${signal.severity}`)}</span>
            <span className="signal-code">{signal.code}</span>
            <span>{signal.label}</span>
            <strong>{signal.value}</strong>
          </li>
        ))}
      </ul>
    </section>
  );
}
