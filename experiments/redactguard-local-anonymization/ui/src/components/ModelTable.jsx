import { formatDate, formatMs, formatPercent, micro } from "../utils/formatters";
import { MiniBar } from "./MetricCard";

/**
 * Comparative matrix table presenting all models with key metrics, latency, and source evidence.
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
            {unified ? <th>Status</th> : null}
            {unified ? <th>Cases</th> : null}
            <th>Recall</th>
            <th>Leakage</th>
            <th>Precision</th>
            <th>Zero leak</th>
            <th>p50</th>
            <th>p95</th>
            {unified ? <th>Source run</th> : null}
          </tr>
        </thead>
        <tbody>
          {models.map((model) => {
            const summary = micro(detail.metrics?.[model]);
            const latency = micro(detail.latency?.metrics?.[model]);
            const evidence = detail.evidence?.[model];
            return (
              <tr key={model}>
                <td className="model-name">{model}</td>
                {unified ? (
                  <td className="status-cell">
                    <span
                      className={
                        evidence?.status === "complete"
                          ? "status-badge status-badge--complete"
                          : "status-badge status-badge--partial"
                      }
                    >
                      {evidence?.status === "complete" ? "complete" : "partial"}
                    </span>
                  </td>
                ) : null}
                {unified ? <td>{evidence?.cases ?? "—"}</td> : null}
                <td>
                  <span>{formatPercent(summary.pii_recall)}</span>
                  <MiniBar value={summary.pii_recall} />
                </td>
                <td>
                  <span>{formatPercent(summary.leakage_rate)}</span>
                  <MiniBar value={summary.leakage_rate} inverse />
                </td>
                <td>
                  <span>{formatPercent(summary.precision)}</span>
                  <MiniBar value={summary.precision} />
                </td>
                <td>{formatPercent(summary.zero_leak_document_rate)}</td>
                <td>{formatMs(latency.latency_p50_ms ?? summary.latency_p50_ms)}</td>
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
