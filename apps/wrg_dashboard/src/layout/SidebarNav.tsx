import { useLanguage } from "../i18n/useLanguage";

export type ControlPage = "overview" | "workers" | "governance" | "artifacts" | "signals" | "settings";

type Props = {
  active: ControlPage;
  onChange: (page: ControlPage) => void;
};

const ITEMS: Array<{ id: ControlPage; labelKey: string }> = [
  { id: "overview", labelKey: "nav.overview" },
  { id: "workers", labelKey: "nav.workers" },
  { id: "governance", labelKey: "nav.governance" },
  { id: "artifacts", labelKey: "nav.artifacts" },
  { id: "signals", labelKey: "nav.signals" },
  { id: "settings", labelKey: "nav.settings" }
];

export function SidebarNav({ active, onChange }: Props): JSX.Element {
  const { t } = useLanguage();

  return (
    <aside className="sidebar">
      {ITEMS.map((item) => (
        <button
          key={item.id}
          type="button"
          className={`sidebar-item${active === item.id ? " is-active" : ""}`}
          onClick={() => onChange(item.id)}
        >
          {t(item.labelKey)}
        </button>
      ))}
    </aside>
  );
}
