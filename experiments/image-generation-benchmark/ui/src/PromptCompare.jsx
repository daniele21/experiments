import { useEffect, useMemo, useRef, useState } from "react";
import {
  DEFAULT_COMPARE_PROMPT, REVIEW_CRITERIA, MAX_COMPARE_ARMS,
  comparisonPlan, defaultCompareModels, emptyArm,
  exampleBenchmarkCommand, makeComparisonReceipt, shuffleForBlind,
} from "./prompt-compare.js";
import { resolveSeed } from "./playground-session.js";

function durationLabel(value) {
  if (!Number.isFinite(value)) return "—";
  return value >= 60_000 ? `${(value / 60_000).toFixed(1)} min` : `${(value / 1000).toFixed(1)} s`;
}

function errorDescription(message) {
  if (!message) return "The provider returned no image";
  return String(message).slice(0, 300);
}

function downloadJson(filename, data) {
  const json = JSON.stringify(data, null, 2);
  const blob = new Blob([json], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function PromptCompare({ models, onGeneration, singlePrompt = "" }) {
  const [selectedKeys, setSelectedKeys] = useState([]);
  const initialized = useRef(false);
  const [prompt, setPrompt] = useState(DEFAULT_COMPARE_PROMPT);
  const [arms, setArms] = useState([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [blind, setBlind] = useState(true);
  const [revealed, setRevealed] = useState(false);
  const [blindOrder, setBlindOrder] = useState([]);
  const [reviews, setReviews] = useState({});
  const [identity, setIdentity] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [lastPlan, setLastPlan] = useState(null);

  useEffect(() => {
    if (!models.length || initialized.current) return;
    initialized.current = true;
    setSelectedKeys(defaultCompareModels(models));
  }, [models]);

  useEffect(() => {
    if (!running) return;
    const began = Date.now();
    const timer = window.setInterval(() => setElapsed(Date.now() - began), 1000);
    return () => window.clearInterval(timer);
  }, [running]);

  const picked = useMemo(() => selectedKeys
    .map((key) => models.find((model) => model.key === key))
    .filter(Boolean), [models, selectedKeys]);
  const cloudCount = picked.filter((model) => model.kind === "cloud").length;
  const finished = arms.filter((arm) => arm.status === "success" || arm.status === "error").length;
  const successCount = arms.filter((arm) => arm.status === "success").length;
  const orderedArms = (blindOrder.length
    ? blindOrder.map((key) => arms.find((arm) => arm.key === key)).filter(Boolean)
    : arms);
  const canSubmit = !running && selectedKeys.length >= 2 &&
    selectedKeys.length <= MAX_COMPARE_ARMS && prompt.trim().length > 0 &&
    prompt.length <= 4000 && picked.every((model) => model.configured);

  function toggleModel(key, checked) {
    if (running) return;
    setError("");
    setSelectedKeys((previous) => {
      if (checked) return previous.includes(key) ? previous : [...previous, key].slice(0, MAX_COMPARE_ARMS);
      return previous.filter((value) => value !== key);
    });
  }

  async function run(event) {
    event.preventDefault();
    if (running) return;
    let plan;
    try {
      plan = comparisonPlan(models, selectedKeys, prompt);
    } catch (reason) {
      setError(reason.message || String(reason));
      return;
    }
    const startedAt = new Date().toISOString();
    setIdentity({ id: crypto.randomUUID(), startedAt, completedAt: null });
    setLastPlan(plan);
    setError("");
    setRunning(true);
    setElapsed(0);
    setRevealed(false);
    setReviews({});
    const reordered = shuffleForBlind(selectedKeys);
    setBlindOrder(reordered);
    setArms(plan.models.map(emptyArm));
    // Run sequentially. The existing Playground backend is single-flight and
    // a local GGUF model should not be loaded concurrently with cloud requests.
    // A failed provider must not discard successful images from other arms.
    for (const model of plan.models) {
      setArms((previous) => previous.map((arm) =>
        arm.key === model.key ? { ...arm, status: "running" } : arm));
      try {
        const request = { model_key: model.key, prompt: plan.prompt };
        if (model.kind === "local") {
          request.seed = resolveSeed("random", "");
        }
        const response = await fetch("/api/playground/generate", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify(request),
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || `Image generation failed (HTTP ${response.status})`);
        if (!payload?.image_url || !payload?.id) throw new Error("Provider did not return an image");
        setArms((previous) => previous.map((arm) =>
          arm.key === model.key ? { ...arm, status: "success", result: payload } : arm));
        // Reuse the existing 12-image session gallery as well as the compare grid.
        // History is best-effort; it must not discard a successful provider output.
        try { onGeneration?.(payload); } catch { /* comparison evidence remains available */ }
      } catch (reason) {
        setArms((previous) => previous.map((arm) =>
          arm.key === model.key
            ? { ...arm, status: "error", error: errorDescription(reason?.message || reason) }
            : arm));
      }
    }
    setIdentity((previous) => ({ ...previous, completedAt: new Date().toISOString() }));
    setRunning(false);
  }

  function downloadReceipt() {
    if (!identity || !lastPlan) return;
    const receipt = makeComparisonReceipt(lastPlan, arms, {
      comparisonId: identity.id,
      startedAt: identity.startedAt,
      completedAt: identity.completedAt,
      reviews,
      blindOrder,
    });
    downloadJson(`image-compare-${identity.id}.json`, receipt);
  }

  function updateScore(key, criterion, value) {
    if (running) return;
    setReviews((previous) => ({
      ...previous,
      [key]: { ...previous[key], [criterion]: value ? Number(value) : null },
    }));
  }

  let benchmarkCommand = "";
  try {
    if (selectedKeys.length >= 2) benchmarkCommand = exampleBenchmarkCommand(selectedKeys);
  } catch { /* The current model selection is incomplete. */ }

  return (
    <div className="pg-compare-page">
      <div className="pg-compare-intro">
        <div>
          <span className="eyebrow">Quick visual comparison</span>
          <h3>One prompt. Multiple models.</h3>
          <p>Generate with your selected engines, then inspect outputs side by side.
            Each call uses the existing local Playground provider integration.</p>
        </div>
        <span className="pg-compare-intro-pill">Exploratory · not a leaderboard</span>
      </div>
      <form className="pg-compare-form" onSubmit={run}>
        {singlePrompt.trim() && singlePrompt.trim() !== prompt.trim() ? (
          <button type="button" className="pg-compare-reuse-prompt" disabled={running}
            onClick={() => setPrompt(singlePrompt)}>Use prompt from Single image</button>
        ) : null}
        <label className="pg-field" htmlFor="pg-compare-prompt">
          <span>Shared prompt · identical text for every model</span>
          <textarea id="pg-compare-prompt" rows={5} maxLength={4000}
            value={prompt} disabled={running} onChange={(event) => setPrompt(event.target.value)} />
        </label>
        <div className="pg-compare-model-head">
          <strong>Select models ({selectedKeys.length}/{MAX_COMPARE_ARMS})</strong>
          <span>2 or more · checked engines only</span>
        </div>
        <div className="pg-compare-models">
          {models.map((model) => (
            <label key={model.key}
              className={selectedKeys.includes(model.key) ? "pg-compare-model selected" : "pg-compare-model"}>
              <input type="checkbox" checked={selectedKeys.includes(model.key)}
                disabled={running || !model.configured ||
                  (!selectedKeys.includes(model.key) && selectedKeys.length >= MAX_COMPARE_ARMS)}
                onChange={(event) => toggleModel(model.key, event.target.checked)} />
              <span>
                <strong>{model.name}</strong>
                <small>{model.kind === "local" ? "Local · Korgis" : "Cloud API"}
                  {model.configured ? " · Configured" : " · Setup needed"}</small>
                {!model.configured ? <small>{model.setup_hint}</small> : null}
              </span>
            </label>
          ))}
        </div>
        <div className="pg-compare-options">
          <label className="pg-compare-blind">
            <input type="checkbox" disabled={running} checked={blind}
              onChange={(event) => { setBlind(event.target.checked); setRevealed(false); }} />
            <span>Blind review <small>Hide model names and randomize image order before scoring.</small></span>
          </label>
          <p>Defaults aim for a 1K square image where configured. Each provider retains
            its own native quality settings. Seeds are randomly generated only for local engines;
            cloud models may not support a seed.</p>
          {cloudCount > 0 ? <p className="pg-compare-cost">
            {cloudCount} cloud provider{cloudCount > 1 ? "s" : ""} selected:
            generation may incur API charges. No call is made until you press Generate comparison.
          </p> : null}
        </div>
        {error ? <div className="pg-error" role="alert">{error}</div> : null}
        <button className="pg-generate" type="submit" disabled={!canSubmit}>
          <span aria-hidden="true">✦</span>
          {running ? `Generating ${finished}/${arms.length} · ${durationLabel(elapsed)}`
            : `Generate comparison · ${selectedKeys.length} models`}
        </button>
        {picked.some((item) => item.kind === "local") ? (
          <small className="pg-compare-footnote">
            Start the desired Qwen engine in Korgis before generating; configuration alone
            does not guarantee the model is resident.
          </small>
        ) : null}
      </form>

      {arms.length > 0 ? (
        <section className="pg-compare-results" aria-label="Side-by-side images">
          <div className="pg-compare-results-head">
            <div>
              <span className="eyebrow">Visual evidence</span>
              <h3>{finished}/{arms.length} completed · {successCount} images</h3>
              <p>Same prompt. No automatic winner from one prompt.</p>
            </div>
            <div className="pg-compare-result-actions">
              {blind && !revealed ? (
                <button type="button" disabled={running}
                  onClick={() => setRevealed(true)}>Reveal models</button>
              ) : null}
              <button type="button" disabled={running || !identity}
                onClick={downloadReceipt}>Export JSON evidence</button>
            </div>
          </div>
          <div className="pg-compare-cards">
            {orderedArms.map((arm, index) => {
              const hiddenIdentity = blind && !revealed;
              return (
                <article className="pg-compare-card" key={arm.key}>
                  <header>
                    <span className="pg-compare-letter">Image {String.fromCharCode(65 + index)}</span>
                    <strong>{hiddenIdentity ? "Model hidden" : arm.name}</strong>
                    <small>{arm.status === "running" ? "Generating…" :
                      arm.status === "waiting" ? "Queued" :
                      arm.status === "error" ? "Failed" : "Complete"}</small>
                  </header>
                  <div className="pg-compare-image">
                    {arm.result ? (
                      <img src={arm.result.image_url} alt={`Generated image ${index + 1}`} />
                    ) : arm.status === "running" ? (
                      <div className="pg-compare-placeholder"><span className="pg-spinner"/>
                        Generating image…</div>
                    ) : (
                      <div className="pg-compare-placeholder">
                        {arm.status === "error" ? (hiddenIdentity
                          ? "This engine failed. Reveal model identity for diagnosis."
                          : arm.error) : "Waiting for this model"}
                      </div>
                    )}
                  </div>
                  {arm.result ? (
                    <>
                      <div className="pg-compare-metrics">
                        <span><strong>Time</strong>{durationLabel(arm.result.latency_ms)}</span>
                        <span><strong>Size</strong>{arm.result.generation?.size || "Native"}</span>
                        <span><strong>Seed</strong>{arm.result.seed_effective ?? arm.result.seed_requested ?? "N/A"}</span>
                        <span><strong>Format</strong>{arm.result.mime_type?.replace("image/", "").toUpperCase() || "—"}</span>
                      </div>
                      <a href={arm.result.image_url} className="pg-compare-download"
                        download={`${arm.key}-${arm.result.id}.${arm.result.filename?.split(".").at(-1) || "png"}`}>
                        Download image
                      </a>
                      <div className="pg-compare-review">
                        <strong>Your review (optional · 1–5)</strong>
                        {REVIEW_CRITERIA.map((criterion) => (
                          <label key={criterion.id}>
                            <span>{criterion.label}</span>
                            <select disabled={running} value={reviews[arm.key]?.[criterion.id] || ""}
                              onChange={(event) => updateScore(arm.key, criterion.id, event.target.value)}>
                              <option value="">Not rated</option>
                              {[1,2,3,4,5].map((score) => (
                                <option key={score} value={score}>{score} / 5</option>
                              ))}
                            </select>
                          </label>
                        ))}
                      </div>
                    </>
                  ) : null}
                  {!hiddenIdentity && arm.status === "error" ? (
                    <small className="pg-compare-error">{arm.error}</small>
                  ) : null}
                </article>
              );
            })}
          </div>
          <div className="pg-compare-benchmark-next">
            <strong>Make it a benchmark</strong>
            <p>This view compares one sample per model. For evidence across multiple
              compositional and typography prompts, use the existing benchmark runner;
              then open Comparison and Blind review in the dashboard.</p>
            {benchmarkCommand ? <code>{benchmarkCommand}</code> : null}
            <small>The command above is dry-run only: remove --dry-run when ready.
              The benchmark uses its curated prompt suite, not just this text,
              and paid cloud calls require your provider API keys.</small>
          </div>
        </section>
      ) : null}
    </div>
  );
}
