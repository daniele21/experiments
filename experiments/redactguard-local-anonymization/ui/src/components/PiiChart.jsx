import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { uiConfig } from "../config/uiConfig";
import { percentValue } from "../utils/formatters";

/**
 * Horizontal grouped bar chart breaking down Recall, Precision, and Leakage by PII entity type.
 */
export function PiiChart({ summary }) {
  const rows = useMemo(
    () =>
      Object.entries(summary?.by_type ?? {}).map(([type, metrics]) => ({
        type,
        recall: percentValue(metrics.pii_recall) ?? 0,
        precision: percentValue(metrics.precision) ?? 0,
        leakage: percentValue(metrics.leakage_rate) ?? 0,
      })),
    [summary],
  );

  if (!rows.length) {
    return <div className="chart-empty">No PII-type breakdown in this run.</div>;
  }

  const height = Math.max(
    uiConfig.charts.barMinHeight,
    rows.length * uiConfig.charts.barHeightPerItem,
  );

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart
        data={rows}
        layout="vertical"
        margin={{ top: 8, right: 12, bottom: 8, left: 16 }}
      >
        <CartesianGrid strokeDasharray="3 3" horizontal={false} opacity={0.25} />
        <XAxis type="number" domain={[0, 100]} unit="%" tickLine={false} axisLine={false} />
        <YAxis
          type="category"
          dataKey="type"
          width={110}
          tickLine={false}
          axisLine={false}
        />
        <Tooltip formatter={(value) => `${Number(value).toFixed(1)}%`} />
        <Legend />
        <Bar dataKey="recall" name="Recall" fill={uiConfig.theme.accent} radius={[0, 4, 4, 0]} />
        <Bar
          dataKey="precision"
          name="Precision"
          fill={uiConfig.theme.series2}
          radius={[0, 4, 4, 0]}
        />
        <Bar dataKey="leakage" name="Leakage" fill={uiConfig.theme.risk} radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export default PiiChart;
