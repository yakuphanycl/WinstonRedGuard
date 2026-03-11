import type { DashboardData } from "../types/dashboard";
import { CriticalSignalsPanel } from "../components/CriticalSignalsPanel";
import { NextActions } from "../components/NextActions";
import { PulseFeed } from "../components/PulseFeed";
import { RelationshipMap } from "../components/RelationshipMap";

type Props = {
  data: DashboardData;
};

export function SignalsPage({ data }: Props): JSX.Element {
  return (
    <>
      <div className="grid-two">
        <CriticalSignalsPanel signals={data.criticalSignals} />
        <PulseFeed pulse={data.pulse} />
      </div>
      <RelationshipMap edges={data.relationships} />
      <NextActions actions={data.nextActions} />
    </>
  );
}
