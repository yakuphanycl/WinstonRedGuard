import type { ActionItem } from "../types/dashboard";
import { useLanguage } from "../i18n/useLanguage";

type Props = {
  actions: ActionItem[];
};

export function NextActions({ actions }: Props): JSX.Element {
  const { t } = useLanguage();
  return (
    <section className="panel">
      <h2>{t("panel.nextActions")}</h2>
      <ul className="action-list">
        {actions.map((item) => (
          <li key={`${item.priority}-${item.text}`}>
            <span className={`priority priority-${item.priority}`}>{t(`priority.${item.priority}`)}</span>
            <span>{item.text}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
