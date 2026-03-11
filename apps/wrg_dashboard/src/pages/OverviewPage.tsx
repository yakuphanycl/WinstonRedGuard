import type { DashboardData } from "../types/dashboard";
import { CriticalSignalsPanel } from "../components/CriticalSignalsPanel";
import { LayerView } from "../components/LayerView";
import { NextActions } from "../components/NextActions";
import { SummaryCards } from "../components/SummaryCards";

type Props = {
  data: DashboardData;
};

export function OverviewPage({ data }: Props): JSX.Element {
  return (
    <>
      <SummaryCards cards={data.summaryCards} />
      <div className="grid-two">
        <CriticalSignalsPanel signals={data.criticalSignals} />
        <LayerView layers={data.layers} />
      </div>
      <NextActions actions={data.nextActions} />
    </>
  );
}
