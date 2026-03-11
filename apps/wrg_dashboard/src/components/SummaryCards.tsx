import type { SummaryCard } from "../types/dashboard";
import { summaryMessageKeys } from "../i18n/messages";
import { useLanguage } from "../i18n/useLanguage";
import { StatusBadge } from "./StatusBadge";

type Props = {
  cards: SummaryCard[];
};

export function SummaryCards({ cards }: Props): JSX.Element {
  const { t } = useLanguage();

  return (
    <section className="panel">
      <h2>{t("panel.systemSummary")}</h2>
      <div className="summary-grid">
        {cards.map((card) => {
          const key = summaryMessageKeys[card.key];
          const label = key ? t(key) : card.label;
          return (
            <article key={card.key} className="summary-card">
              <div className="summary-card-head">
                <span>{label}</span>
                <StatusBadge value={card.status} />
              </div>
              <strong>{card.value}</strong>
            </article>
          );
        })}
      </div>
    </section>
  );
}
