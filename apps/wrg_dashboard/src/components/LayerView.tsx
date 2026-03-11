import type { LayerItem } from "../types/dashboard";
import { useLanguage } from "../i18n/useLanguage";
import { StatusBadge } from "./StatusBadge";

type Props = {
  layers: LayerItem[];
};

export function LayerView({ layers }: Props): JSX.Element {
  const { t } = useLanguage();

  return (
    <section className="panel">
      <h2>{t("panel.layerHealth")}</h2>
      <ul className="list-block">
        {layers.map((layer) => (
          <li key={layer.name} className="list-row">
            <div>
              <strong>{layer.name}</strong>
              <p>{layer.detail}</p>
              <p>{t("layer.related")}: {layer.relatedSystems.join(", ")}</p>
            </div>
            <div className="layer-meta">
              <span className="issue-count">{t("layer.issues")}={layer.issueCount}</span>
              <StatusBadge value={layer.status} />
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
