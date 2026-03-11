import type { HealthStatus } from "../types/dashboard";

type Props = {
  value: HealthStatus;
};

const CLASS_MAP: Record<HealthStatus, string> = {
  PASS: "badge badge-pass",
  WARN: "badge badge-warn",
  FAIL: "badge badge-fail"
};

export function StatusBadge({ value }: Props): JSX.Element {
  return <span className={CLASS_MAP[value]}>{value}</span>;
}
