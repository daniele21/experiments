import { useMemo } from "react";
import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { uiConfig } from "../config/uiConfig";
import { formatMs, micro, percentValue } from "../utils/formatters";

/**
 * Scatter chart plotting PII Recall (%) against p95 Latency (ms).
 */
export function QualityLatencyChart({ detail }) {
  const data = useMemo(() => {
    if (!detail) return [];
    return Object.entries(detail.metrics ?? {})
      .map(([model, summary]) => {
        const quality = micro(summary);
        const dedicatedLatency = micro(detail.latency?.metrics?.[model]);
        const recall = percentValue(quality.pii_recall);
        const latency =
          dedicatedLatency.latency_p95_ms ??
          dedicatedLatency.p95_ms ??
          quality.latency_p95_ms ??
          null;

        if (recall === null || latency === null) return null;
        return { model, recall, latency: Number(latency) };
      })
      .filter(Boolean);
  }, [detail]);

  if (!data.length) {
    return <div className="chart-empty">No comparable recall/latency data for this run.</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={uiConfig.charts.scatterHeight}>
      <ScatterChart margin={{ top: 18, right: 20, bottom: 12, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.25} />
        <XAxis
          type="number"
          dataKey="latency"
          name="p95 latency"
          unit=" ms"
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          type="number"
          dataKey="recall"
          name="Recall"
          unit="%"
          domain={[0, 100]}
          tickLine={false}
          axisLine={false}
          width={48}
        />
        <Tooltip
          cursor={{ strokeDasharray: "3 3" }}
          formatter={(value, name) =>
            name === "Recall"
              ? [`${Number(value).toFixed(1)}%`, name]
              : [formatMs(value), "p95 latency"]
          }
          labelFormatter={(_, payload) => payload?.[0]?.payload?.model ?? ""}
        />
        <Scatter name="Models" data={data} fill={uiConfig.theme.accent} />
      </ScatterChart>
    </ResponsiveContainer>
  );
}

export default QualityLatencyChart;
