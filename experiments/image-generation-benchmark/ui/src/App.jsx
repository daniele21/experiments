import { useCallback, useEffect, useMemo, useState } from "react";

const REFRESH_MS = 4000;
const CRITERIA = ["prompt_adherence", "visual_preference", "text_quality"];

function formatDate(value) {
  if (!value) return "Unknown";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(date);
}

function formatMs(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  return numeric >= 1000 ? `${(numeric / 1000).toFixed(2)} s` : `${numeric.toFixed(0)} ms`;
}

function provenance(row) {
  const metadata = row?.provider_metadata ?? {};
  const korgis = metadata.korgis ?? {};
  const generation = korgis.generation ?? {};
  return [
    row?.provider_id ? `provider=${row.provider_id}` : null,
    korgis.runtime_key ? `runtime=${korgis.runtime_key}` : null,
    korgis.backend ? `backend=${korgis.backend}` : null,
    generation.quantization
      ? `quantization=${generation.quantization}`
      : generation.quantization_bits != null
        ? `quantization=Q${generation.quantization_bits}`
        : null,
  ].filter(Boolean);
}

function runtimeArtifacts(row) {
  const artifacts =
    row?.provider_metadata?.korgis?.generation?.artifacts ?? {};
  return Object.entries(artifacts)
    .filter(([, value]) => value && typeof value === "object")
    .map(([role, value]) => ({
      role,
      filename: value.filename ?? "unknown",
      repo: value.repo ?? null,
      revision: value.revision ?? null,
      sha256: value.sha256 ?? null,
    }));
}

function downloadJson(filename, payload) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function RunSidebar({ runs, selectedRun, onSelect }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark">IG</span>
        <div>
          <strong>Image Bench</strong>
          <small>dynamic explorer</small>
        </div>
      </div>
      <div className="sidebar-heading">
        <span>Runs</span>
        <span className="count">{runs.length}</span>
      </div>
      <div className="run-list">
        {runs.map((run, index) => (
          <button
            type="button"
            key={run.runId}
            className={selectedRun === run.runId ? "run-card active" : "run-card"}
            onClick={() => onSelect(run.runId)}
          >
            <div className="run-card-top">
              <strong>{run.profile || run.suite || run.runId.slice(0, 8)}</strong>
              {index === 0 ? <span className="pill">latest</span> : null}
            </div>
            <span>{formatDate(run.createdAt)}</span>
            <div className="run-card-meta">
              <span>{run.models.length} models</span>
              <span>{run.prompts} prompts</span>
              <span>{run.valid}/{run.total} valid</span>
            </div>
          </button>
        ))}
        {!runs.length ? (
          <div className="empty compact">
            <strong>No runs yet</strong>
            <span>Run the benchmark and they appear here automatically.</span>
          </div>
        ) : null}
      </div>
    </aside>
  );
}

function RunHeader({ run, summary, activeTab, setActiveTab, lastRefresh }) {
  return (
    <header className="topbar">
      <div>
        <span className="eyebrow">Image generation benchmark</span>
        <h1>{run?.manifest?.parameters?.profile || run?.manifest?.suite || "Run explorer"}</h1>
        <p>
          {run?.runId ? `${run.runId} · ` : ""}
          refreshed {lastRefresh ? lastRefresh.toLocaleTimeString() : "—"}
        </p>
      </div>
      <div className="tab-switcher" role="tablist">
        <button
          type="button"
          className={activeTab === "comparison" ? "active" : ""}
          onClick={() => setActiveTab("comparison")}
        >
          Comparison
        </button>
        <button
          type="button"
          className={activeTab === "blind" ? "active" : ""}
          onClick={() => setActiveTab("blind")}
        >
          Blind review
        </button>
      </div>
      <div className="header-stat">
        <strong>{summary.valid}/{summary.total}</strong>
        <span>valid outputs</span>
      </div>
    </header>
  );
}

function Filters({
  categories,
  category,
  setCategory,
  models,
  enabledModels,
  toggleModel,
}) {
  return (
    <div className="filters">
      <label>
        Category
        <select value={category} onChange={(event) => setCategory(event.target.value)}>
          <option value="all">All categories</option>
          {categories.map((value) => (
            <option key={value} value={value}>{value}</option>
          ))}
        </select>
      </label>
      <div className="model-filter">
        <span>Models</span>
        <div>
          {models.map((model) => (
            <button
              key={model}
              type="button"
              className={enabledModels.has(model) ? "model-chip active" : "model-chip"}
              onClick={() => toggleModel(model)}
            >
              {model}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function OutputCard({ row }) {
  const badges = provenance(row);
  const artifacts = runtimeArtifacts(row);
  return (
    <article className={row.valid ? "output-card" : "output-card invalid"}>
      <div className="image-stage">
        {row.artifact_url ? (
          <img src={row.artifact_url} alt={`${row.model_key} output`} loading="lazy" />
        ) : (
          <div className="missing">No artifact</div>
        )}
      </div>
      <div className="output-meta">
        <div className="output-title">
          <div>
            <strong>{row.model_key}</strong>
            <span>{row.model_id}</span>
          </div>
          <span className={row.valid ? "status ok" : "status bad"}>
            {row.valid ? "valid" : "failed"}
          </span>
        </div>
        <div className="badge-row">
          <span className="badge">{formatMs(row.latency_ms)}</span>
          {badges.map((badge) => <span className="badge" key={badge}>{badge}</span>)}
        </div>
        {artifacts.length ? (
          <details className="artifact-provenance">
            <summary>Runtime artifacts</summary>
            <div className="artifact-provenance-list">
              {artifacts.map((artifact) => (
                <div className="artifact-provenance-row" key={artifact.role}>
                  <span>{artifact.role.replaceAll("_", " ")}</span>
                  <strong>{artifact.filename}</strong>
                  {artifact.repo ? <small>{artifact.repo}</small> : null}
                </div>
              ))}
            </div>
          </details>
        ) : null}
        {!row.valid ? (
          <p className="error-text">{row.error_kind}: {row.error_message}</p>
        ) : null}
      </div>
    </article>
  );
}

function ComparisonView({ run }) {
  const rows = run?.rows ?? [];
  const categories = useMemo(
    () => [...new Set(rows.map((row) => row.category))].sort(),
    [rows],
  );
  const models = useMemo(
    () => [...new Set(rows.map((row) => row.model_key))],
    [rows],
  );
  const [category, setCategory] = useState("all");
  const [enabledModels, setEnabledModels] = useState(new Set());

  useEffect(() => {
    setEnabledModels(new Set(models));
    setCategory("all");
  }, [run?.runId, models.join("|")]);

  const toggleModel = (model) => {
    setEnabledModels((current) => {
      const next = new Set(current);
      if (next.has(model)) {
        if (next.size > 1) next.delete(model);
      } else next.add(model);
      return next;
    });
  };

  const groups = useMemo(() => {
    const byPrompt = new Map();
    for (const row of rows) {
      if (category !== "all" && row.category !== category) continue;
      if (!enabledModels.has(row.model_key)) continue;
      if (!byPrompt.has(row.prompt_id)) byPrompt.set(row.prompt_id, []);
      byPrompt.get(row.prompt_id).push(row);
    }
    return [...byPrompt.entries()].map(([promptId, promptRows]) => ({
      promptId,
      prompt: promptRows[0]?.prompt ?? "",
      category: promptRows[0]?.category ?? "",
      rows: promptRows.sort((a, b) => a.model_key.localeCompare(b.model_key)),
    }));
  }, [rows, category, enabledModels]);

  return (
    <>
      <Filters
        categories={categories}
        category={category}
        setCategory={setCategory}
        models={models}
        enabledModels={enabledModels}
        toggleModel={toggleModel}
      />
      <div className="prompt-list">
        {groups.map((group) => (
          <section className="prompt-panel" key={group.promptId}>
            <div className="prompt-head">
              <div>
                <span className="eyebrow">{group.category}</span>
                <h2>{group.promptId}</h2>
              </div>
              <span className="model-count">{group.rows.length} outputs</span>
            </div>
            <p className="prompt-copy">{group.prompt}</p>
            <div
              className="output-grid"
              style={{ "--columns": Math.min(group.rows.length, 3) }}
            >
              {group.rows.map((row) => (
                <OutputCard key={`${row.model_key}-${row.prompt_id}`} row={row} />
              ))}
            </div>
          </section>
        ))}
      </div>
    </>
  );
}

function BlindReview({ runId }) {
  const [pairs, setPairs] = useState([]);
  const [votes, setVotes] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!runId) return;
    setLoading(true);
    fetch(`/api/blind?run=${encodeURIComponent(runId)}`, { cache: "no-store" })
      .then((response) => response.json())
      .then((payload) => {
        setPairs(payload.pairs ?? []);
        const stored = localStorage.getItem(`imagegen-votes:${runId}`);
        setVotes(stored ? JSON.parse(stored) : {});
      })
      .finally(() => setLoading(false));
  }, [runId]);

  const vote = (pairId, criterion, choice) => {
    setVotes((current) => {
      const next = { ...current, [`${pairId}:${criterion}`]: choice };
      localStorage.setItem(`imagegen-votes:${runId}`, JSON.stringify(next));
      return next;
    });
  };

  const voteCount = Object.keys(votes).length;
  const expectedVotes = pairs.length * CRITERIA.length;

  if (loading) return <div className="empty">Loading blind pairs…</div>;

  return (
    <>
      <div className="blind-toolbar">
        <div>
          <strong>{pairs.length} pairwise comparisons</strong>
          <span>{voteCount}/{expectedVotes} criterion votes completed</span>
        </div>
        <button
          type="button"
          className="primary"
          onClick={() =>
            downloadJson(`blind_votes-${runId}.json`, {
              run_id: runId,
              votes: Object.entries(votes).map(([key, choice]) => {
                const separator = key.lastIndexOf(":");
                const pairId = key.slice(0, separator);
                return {
                  pair_id: pairId,
                  prompt_id: pairs.find((pair) => pair.pair_id === pairId)?.prompt_id ?? null,
                  criterion: key.slice(separator + 1),
                  choice,
                };
              }),
            })
          }
        >
          Export votes
        </button>
      </div>
      <div className="prompt-list">
        {pairs.map((pair) => (
          <section className="prompt-panel blind-panel" key={pair.pair_id}>
            <div className="prompt-head">
              <div>
                <span className="eyebrow">{pair.category}</span>
                <h2>{pair.prompt_id}</h2>
              </div>
              <span className="pill">blind</span>
            </div>
            <p className="prompt-copy">{pair.prompt}</p>
            <div className="blind-grid">
              <article className="output-card">
                <div className="image-stage">
                  <img src={pair.image_a} alt="Blind output A" loading="lazy" />
                </div>
                <div className="blind-label">Image A</div>
              </article>
              <article className="output-card">
                <div className="image-stage">
                  <img src={pair.image_b} alt="Blind output B" loading="lazy" />
                </div>
                <div className="blind-label">Image B</div>
              </article>
            </div>
            <div className="criteria">
              {CRITERIA.map((criterion) => (
                <div className="criterion" key={criterion}>
                  <strong>{criterion.replaceAll("_", " ")}</strong>
                  <div>
                    {["A", "B", "tie"].map((choice) => (
                      <button
                        key={choice}
                        type="button"
                        className={
                          votes[`${pair.pair_id}:${criterion}`] === choice
                            ? "vote active"
                            : "vote"
                        }
                        onClick={() => vote(pair.pair_id, criterion, choice)}
                      >
                        {choice}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>
    </>
  );
}

export default function App() {
  const [runs, setRuns] = useState([]);
  const [selectedRun, setSelectedRun] = useState(null);
  const [run, setRun] = useState(null);
  const [activeTab, setActiveTab] = useState("comparison");
  const [error, setError] = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);

  const loadRuns = useCallback(async () => {
    try {
      const response = await fetch("/api/runs", { cache: "no-store" });
      if (!response.ok) throw new Error(`runs request failed: ${response.status}`);
      const payload = await response.json();
      setRuns(payload.runs ?? []);
      setSelectedRun((current) =>
        current && payload.runs?.some((item) => item.runId === current)
          ? current
          : payload.runs?.[0]?.runId ?? null,
      );
      setLastRefresh(new Date());
      setError(null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : String(requestError));
    }
  }, []);

  useEffect(() => {
    loadRuns();
    const timer = window.setInterval(loadRuns, REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [loadRuns]);

  useEffect(() => {
    if (!selectedRun) {
      setRun(null);
      return;
    }
    const controller = new AbortController();
    fetch(`/api/run?run=${encodeURIComponent(selectedRun)}`, {
      cache: "no-store",
      signal: controller.signal,
    })
      .then((response) => {
        if (!response.ok) throw new Error(`run request failed: ${response.status}`);
        return response.json();
      })
      .then((payload) => {
        setRun(payload);
        setError(null);
      })
      .catch((requestError) => {
        if (requestError.name !== "AbortError") {
          setError(requestError instanceof Error ? requestError.message : String(requestError));
        }
      });
    return () => controller.abort();
  }, [selectedRun, lastRefresh]);

  const summary = useMemo(() => {
    const rows = run?.rows ?? [];
    return {
      total: rows.length,
      valid: rows.filter((row) => row.valid).length,
    };
  }, [run]);

  return (
    <div className="app-shell">
      <RunSidebar runs={runs} selectedRun={selectedRun} onSelect={setSelectedRun} />
      <main className="workspace">
        <RunHeader
          run={run}
          summary={summary}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          lastRefresh={lastRefresh}
        />
        {error ? <div className="error-banner">{error}</div> : null}
        {!run ? (
          <div className="empty">
            <strong>No benchmark run selected</strong>
            <span>Run the benchmark; this React UI refreshes automatically.</span>
          </div>
        ) : activeTab === "comparison" ? (
          <ComparisonView run={run} />
        ) : (
          <BlindReview runId={run.runId} />
        )}
      </main>
    </div>
  );
}
