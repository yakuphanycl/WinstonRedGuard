import type { PulseItem } from "../types/dashboard";
import { useLanguage } from "../i18n/useLanguage";
import { StatusBadge } from "./StatusBadge";

type Props = {
  pulse: PulseItem[];
};

export function PulseFeed({ pulse }: Props): JSX.Element {
  const { t } = useLanguage();

  return (
    <section className="panel">
      <h2>{t("panel.companyPulse")}</h2>
      <ul className="list-block">
        {pulse.map((item, index) => (
          <li key={`${item.message}-${index}`} className="list-row">
            <span>{item.message}</span>
            <StatusBadge value={item.level} />
          </li>
        ))}
      </ul>
    </section>
  );
}
