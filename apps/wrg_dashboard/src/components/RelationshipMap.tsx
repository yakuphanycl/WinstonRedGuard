import { StatusBadge } from "./StatusBadge";
import type { RelationshipEdge } from "../types/dashboard";
import { useLanguage } from "../i18n/useLanguage";

type Props = {
  edges: RelationshipEdge[];
};

export function RelationshipMap({ edges }: Props): JSX.Element {
  const { t } = useLanguage();

  return (
    <section className="panel">
      <h2>{t("panel.relationshipMap")}</h2>
      <table className="worker-table">
        <thead>
          <tr>
            <th>{t("relationship.from")}</th>
            <th>{t("relationship.to")}</th>
            <th>{t("relationship.relation")}</th>
            <th>{t("relationship.status")}</th>
          </tr>
        </thead>
        <tbody>
          {edges.map((edge) => (
            <tr key={`${edge.from}-${edge.to}-${edge.relation}`}>
              <td>{edge.from}</td>
              <td>{edge.to}</td>
              <td>{edge.relation}</td>
              <td>
                <StatusBadge value={edge.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
