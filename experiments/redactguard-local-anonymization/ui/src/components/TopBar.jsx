import { uiConfig } from "../config/uiConfig";
import { formatDate, shortDataset } from "../utils/formatters";
import ThemeToggle from "./ThemeToggle";

/**
 * TopBar component containing run title, metadata summary, and auto-refresh/manual-refresh controls.
 */
export function TopBar({
  selectedRun,
  lastRefresh,
  isRefreshing,
  refreshInterval,
  onIntervalChange,
  onManualRefresh,
}) {
  const isAutoEnabled = refreshInterval > 0;
  const currentIntervalOption = uiConfig.polling.intervalOptions.find(
    (opt) => opt.value === refreshInterval,
  );

  return (
    <header className="topbar">
      <div className="topbar-info">
        <div className="kicker">Benchmark results</div>
        <h1>
          {selectedRun?.source === "overview"
            ? "Unified model overview"
            : selectedRun?.suiteId || selectedRun?.runId || "No run selected"}
        </h1>
        <p>
          {selectedRun?.source === "overview"
            ? "Latest complete evidence per model, with partial evidence used only as fallback."
            : selectedRun
              ? `${shortDataset(selectedRun.dataset)} · ${formatDate(selectedRun.createdAt)}`
              : "Run a benchmark to populate the dashboard."}
        </p>
      </div>

      <div className="topbar-actions">
        {/* Color Theme Selector */}
        <ThemeToggle />

        {/* Cadence selector / pause toggle */}
        <div className="cadence-picker" title="Configure background auto-refresh">
          <span className={`live-dot ${isAutoEnabled ? "live-dot--active" : "live-dot--paused"}`}>
            <i />
            <span>{isAutoEnabled ? `Auto ${currentIntervalOption?.label ?? ""}` : "Paused"}</span>
          </span>
          <select
            value={refreshInterval}
            onChange={(e) => onIntervalChange(Number(e.target.value))}
            aria-label="Auto-refresh frequency"
          >
            {uiConfig.polling.intervalOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label === "Off" ? "Disable auto" : `Every ${opt.label}`}
              </option>
            ))}
          </select>
        </div>

        {/* Manual Refresh Button */}
        <button
          type="button"
          className={`refresh-button ${isRefreshing ? "refresh-button--busy" : ""}`}
          onClick={onManualRefresh}
          disabled={isRefreshing}
          title="Manually check for new benchmark results"
        >
          <span className="refresh-button__content">
            <span className={`refresh-icon ${isRefreshing ? "spin" : ""}`}>↻</span>
            <span>{isRefreshing ? "Updating…" : "Refresh"}</span>
          </span>
          <small>
            {lastRefresh ? `Last: ${lastRefresh.toLocaleTimeString()}` : "Never"}
          </small>
        </button>
      </div>
    </header>
  );
}

export default TopBar;
