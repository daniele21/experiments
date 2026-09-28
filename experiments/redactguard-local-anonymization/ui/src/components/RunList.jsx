import { formatDate, shortDataset } from "../utils/formatters";

/**
 * Sidebar navigation list displaying all discoverable benchmark runs.
 * Supports legacy schema and partial execution badges.
 */
export function RunList({ runs, selectedKey, onSelect }) {
  if (!runs.length) {
    return (
      <div className="empty-state compact">
        <strong>No runs yet</strong>
        <span>Run the benchmark and this list will populate automatically.</span>
      </div>
    );
  }

  const uniqueModels = new Set(runs.flatMap((run) => run.models ?? [])).size;

  return (
    <div className="run-list">
      <button
        type="button"
        className={
          selectedKey === "__overview__"
            ? "run-item overview-item active"
            : "run-item overview-item"
        }
        onClick={() => onSelect("__overview__")}
      >
        <div className="run-item__top">
          <strong>All models</strong>
          <span className="pill pill--overview">overview</span>
        </div>
        <span>Unified latest evidence</span>
        <div className="run-item__meta">
          <span>cross-run</span>
          <span>
            {uniqueModels} model{uniqueModels === 1 ? "" : "s"}
          </span>
        </div>
      </button>
      <div className="run-list__divider" />
      {runs.map((run, index) => (
        <button
          type="button"
          key={run.key}
          className={selectedKey === run.key ? "run-item active" : "run-item"}
          onClick={() => onSelect(run.key)}
        >
          <div className="run-item__top">
            <strong>{run.suiteId || run.runId}</strong>
            <span className="run-badges">
              {run.legacy ? (
                <span className="pill pill--legacy">legacy</span>
              ) : null}
              {run.status === "incomplete" ? (
                <span className="pill pill--partial">partial</span>
              ) : null}
              {index === 0 ? <span className="pill">latest</span> : null}
            </span>
          </div>
          <span>{formatDate(run.createdAt)}</span>
          <div className="run-item__meta">
            <span>
              {run.evaluationSchema
                ? run.evaluationSchema.replace("redactguard-evaluation-", "")
                : shortDataset(run.dataset)}
            </span>
            <span>
              {run.models.length} model{run.models.length === 1 ? "" : "s"}
            </span>
          </div>
        </button>
      ))}
    </div>
  );
}

export default RunList;
