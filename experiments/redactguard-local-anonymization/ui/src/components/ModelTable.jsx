import { formatDate, formatMs, formatPercent, micro } from "../utils/formatters";
import { MiniBar } from "./MetricCard";

function contractState(metrics, evidence, summary) {
  if (evidence?.contractStatus) return evidence.contractStatus;
  if (metrics?.status === "contract_failed") return "failed";
  if (summary?.legacy || evidence?.legacy) return "legacy";
  return "passed";
}

function StatusBadge({ state }) {
  if (state === "failed") {
    return <span className="status-badge status-badge--failed">contract failed</span>;
  }
  if (state === "legacy") {
    return <span className="status-badge status-badge--legacy">legacy schema</span>;
  }
  return <span className="status-badge status-badge--passed">contract ok</span>;
}

/**
 * Comparative matrix table presenting all models with key metrics, latency, and source evidence.
 * Supports RedactGuard v3 contract verification and separated system/quality leakage metrics.
 */
export function ModelTable({ detail }) {
  const models = detail?.summary?.models ?? [];
  const unified = Boolean(detail?.evidence);

  return (
    <div className="table-scroll">
      <table className="comparison-table">
        <thead>
          <tr>
            <th>Model</th>
            <th>Evidence</th>
            <th>Contract</th>
            <th>Evaluated</th>
            <th>Recall</th>
            <th>Quality leak</th>
            <th>System leak</th>
            <th>Precision</th>
            <th>Success</th>
            <th>Trunc.</th>
            <th>Resolution</th>
            <th>p95</th>
            {unified ? <th>Source run</th> : null}
          </tr>
        </thead>
        <tbody>
          {models.map((model) => {
            const summary = micro(detail.metrics?.[model]);
            const latency = micro(detail.latency?.metrics?.[model]);
            const evidence = detail.evidence?.[model];
            const state = contractState(detail.metrics?.[model], evidence, detail.summary);
            const totalCases = summary.cases ?? evidence?.cases ?? "—";
            const evaluatedCases =
              summary.evaluated_cases ??
              evidence?.evaluatedCases ??
              (summary.quality_available ? totalCases : 0);

            return (
              <tr key={model}>
                <td className="model-name">{model}</td>
                <td className="status-cell">
                  <span
                    className={
                      (evidence?.status ?? detail.summary?.status) === "incomplete"
                        ? "status-badge status-badge--partial"
                        : "status-badge status-badge--complete"
                    }
                  >
                    {(evidence?.status ?? detail.summary?.status) === "incomplete"
                      ? "partial"
                      : "complete"}
                  </span>
                </td>
                <td className="status-cell">
                  <StatusBadge state={state} />
                </td>
                <td>
                  {evaluatedCases}/{totalCases}
                </td>
                <td>
                  <span>{formatPercent(summary.pii_recall)}</span>
                  <MiniBar value={summary.pii_recall} />
                </td>
                <td>
                  <span>{formatPercent(summary.leakage_rate)}</span>
                  <MiniBar value={summary.leakage_rate} inverse />
                </td>
                <td>
                  <span>{formatPercent(summary.system_leakage_rate ?? summary.leakage_rate)}</span>
                  <MiniBar value={summary.system_leakage_rate ?? summary.leakage_rate} inverse />
                </td>
                <td>{formatPercent(summary.precision)}</td>
                <td>{formatPercent(summary.inference_success_rate ?? summary.valid_output_rate)}</td>
                <td>{formatPercent(summary.truncation_rate)}</td>
                <td>{formatPercent(summary.span_resolution_rate)}</td>
                <td>{formatMs(latency.latency_p95_ms ?? summary.latency_p95_ms)}</td>
                {unified ? (
                  <td className="source-run-cell">
                    <strong>{evidence?.suiteId || evidence?.runId || "—"}</strong>
                    <small>{formatDate(evidence?.createdAt)}</small>
                  </td>
                ) : null}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default ModelTable;
