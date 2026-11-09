import { useEffect, useMemo, useState } from "react";

const EXAMPLES = [
  { label: "Photorealism", prompt: "Photorealistic editorial photograph of a small Italian café at sunrise, soft window light, a ceramic espresso cup, believable materials and natural reflections." },
  { label: "Composition", prompt: "Exactly three objects on a pale stone table: a red ceramic mug on the left, a green apple in the center, and a blue notebook on the right. No other objects." },
  { label: "Typography", prompt: 'A minimal modern poster displaying exactly the words "LOCAL AI, REAL CONTROL" in crisp, readable typography, with no other text.' },
];

const INITIAL_PROMPT = EXAMPLES[0].prompt;
const EDIT_PROMPT = "Change the color of the main object, preserving the composition, lighting and everything else.";
const EDIT_RESOLUTIONS = ["512x512", "768x768", "1024x1024", "1024x768", "768x1024"];
const MAX_PNG_BYTES = 8 * 1024 * 1024;

function timeLabel(ms) {
  if (!Number.isFinite(Number(ms))) return "—";
  const seconds = Number(ms) / 1000;
  return seconds >= 60
    ? `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`
    : `${seconds.toFixed(1)}s`;
}

export default function Playground() {
  const [models, setModels] = useState([]);
  const [modelKey, setModelKey] = useState("");
  const [prompt, setPrompt] = useState(INITIAL_PROMPT);
  const [mode, setMode] = useState("generate");
  const [sourceImage, setSourceImage] = useState(null);
  const [sourcePreview, setSourcePreview] = useState("");
  const [resolution, setResolution] = useState("512x512");
  const [isDragging, setDragging] = useState(false);
  const [seed, setSeed] = useState("42");
  const [loadingModels, setLoadingModels] = useState(true);
  const [working, setWorking] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  useEffect(() => {
    let active = true;
    fetch("/api/playground/models", { cache: "no-store" })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || "Could not load engines");
        return payload;
      })
      .then((payload) => {
        if (!active) return;
        setModels(payload.models || []);
        const preferred = payload.models?.find((model) => model.key === "qwen-image-2.1-turbo-gguf-q4km");
        setModelKey(preferred?.key || payload.models?.[0]?.key || "");
        setError("");
      })
      .catch((reason) => { if (active) setError(reason.message || String(reason)); })
      .finally(() => { if (active) setLoadingModels(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!sourceImage) {
      setSourcePreview("");
      return;
    }
    const url = URL.createObjectURL(sourceImage);
    setSourcePreview(url);
    return () => URL.revokeObjectURL(url);
  }, [sourceImage]);

  useEffect(() => {
    if (!working) return;
    const started = Date.now();
    const timer = window.setInterval(() => {
      setSeconds(Math.floor((Date.now() - started) / 1000));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [working]);

  const selected = useMemo(
    () => models.find((model) => model.key === modelKey),
    [models, modelKey],
  );
  const local = selected?.kind === "local";
  const editAvailable = Boolean(selected?.image_editing_available && local);
  const editing = mode === "edit";
  const canSubmit = selected?.configured && prompt.trim().length > 0 &&
    prompt.length <= 4000 && !working && (!editing || (editAvailable && sourceImage));

  function chooseSource(file) {
    if (!file) return;
    if (file.type !== "image/png" || !file.name.toLowerCase().endsWith(".png")) {
      setError("Choose a PNG image. JPEG and WebP are not supported yet.");
      return;
    }
    if (file.size > MAX_PNG_BYTES) {
      setError("The reference PNG must be smaller than 8 MiB.");
      return;
    }
    setSourceImage(file);
    setResult(null);
    setError("");
  }

  function changeMode(nextMode) {
    if (nextMode === "edit" && !editAvailable) return;
    setMode(nextMode);
    setResult(null);
    setError("");
    if (nextMode === "edit" && prompt === INITIAL_PROMPT) setPrompt(EDIT_PROMPT);
  }

  async function generate(event) {
    event.preventDefault();
    if (!canSubmit) return;
    setWorking(true);
    setSeconds(0);
    setError("");
    setResult(null);
    try {
      const payload = { model_key: modelKey, prompt: prompt.trim() };
      if (local && seed.trim() !== "") {
        const parsed = Number(seed);
        if (!Number.isInteger(parsed) || parsed < 0 || parsed > 2147483647) {
          throw new Error("Seed must be a positive integer up to 2147483647");
        }
        payload.seed = parsed;
      }
      let response;
      if (editing) {
        const form = new FormData();
        form.set("model_key", payload.model_key);
        form.set("prompt", payload.prompt);
        form.set("image", sourceImage, sourceImage.name);
        form.set("size", resolution);
        form.set("num_inference_steps", "8");
        if (payload.seed != null) form.set("seed", String(payload.seed));
        response = await fetch("/api/playground/edit", {
          method: "POST", body: form,
        });
      } else {
        response = await fetch("/api/playground/generate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      }
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || `Generation failed (${response.status})`);
      setResult(body);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setWorking(false);
    }
  }

  return (
    <div className="playground">
      <div className="playground-intro">
        <div>
          <span className="eyebrow">Experiment / Generate</span>
          <h2>Image Playground</h2>
          <p>One prompt, one engine, one output. Try an idea before building a benchmark.</p>
        </div>
        <span className="playground-intro-tag">Single generation</span>
      </div>
      <div className="playground-layout">
        <form className="playground-panel" onSubmit={generate}>
          <div className="pg-section-title">
            <span className="pg-step">01</span>
            <div>
              <h3>Select engine</h3>
              <p>Engines are loaded from Experiments’ model registry.</p>
            </div>
          </div>
          <label className="pg-field" htmlFor="pg-engine">
            <span>Model / engine</span>
            <select
              id="pg-engine"
              value={modelKey}
              onChange={(event) => { setModelKey(event.target.value); setError(""); }}
              disabled={working || loadingModels}
            >
              {!models.length ? <option value="">No engines loaded</option> : null}
              <optgroup label="Local / Korgis">
                {models.filter((model) => model.kind === "local").map((model) => (
                  <option value={model.key} key={model.key}>{model.name}</option>
                ))}
              </optgroup>
              <optgroup label="Cloud / API">
                {models.filter((model) => model.kind === "cloud").map((model) => (
                  <option value={model.key} key={model.key}>{model.name}</option>
                ))}
              </optgroup>
            </select>
          </label>
          {selected ? (
            <div className="pg-engine-detail">
              <span className={selected.configured ? "pg-config-status ready" : "pg-config-status"}>
                <span aria-hidden="true" className="pg-dot" />
                {selected.configured ? "Configured" : "Setup needed"}
              </span>
              <span>{local ? "On-device via Korgis" : "Cloud API · may incur charges"}</span>
              <small>{selected.model_id}</small>
              {!selected.configured ? <p>{selected.setup_hint}</p> : null}
            </div>
          ) : null}
          <div className="pg-divider" />
          <div className="pg-section-title">
            <span className="pg-step">02</span>
            <div>
              <h3>Write your prompt</h3>
              <p>Describe the image you want to generate.</p>
            </div>
          </div>
          <label className="pg-field" htmlFor="pg-prompt">
            <span>Prompt</span>
            <textarea
              id="pg-prompt"
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              disabled={working}
              maxLength={4000}
              rows={6}
              placeholder="A photorealistic scene of..."
            />
            <span className="pg-char-count">{prompt.length} / 4000 characters</span>
          </label>
          <div className="pg-examples">
            <span>Try an example</span>
            <div>
              {EXAMPLES.map((example) => (
                <button
                  key={example.label}
                  type="button"
                  disabled={working}
                  onClick={() => setPrompt(example.prompt)}
                >
                  {example.label}
                </button>
              ))}
            </div>
          </div>
          <div className="pg-settings">
            <div>
              <span>Generation settings</span>
              <small>Using the selected engine defaults</small>
            </div>
            <div className="pg-setting-chips">
              <span>{selected?.generation?.size || "Engine default"}</span>
              {selected?.generation?.num_inference_steps != null ? (
                <span>{selected.generation.num_inference_steps} steps</span>
              ) : null}
              {selected?.generation?.guidance_scale != null ? (
                <span>CFG {selected.generation.guidance_scale}</span>
              ) : null}
            </div>
            {local ? (
              <label className="pg-field pg-seed" htmlFor="pg-seed">
                <span>Seed <small>(optional)</small></span>
                <input
                  id="pg-seed"
                  type="number"
                  min={0}
                  max={2147483647}
                  step={1}
                  disabled={working}
                  value={seed}
                  onChange={(event) => setSeed(event.target.value)}
                />
              </label>
            ) : null}
          </div>
          <button className="pg-generate" type="submit" disabled={!canSubmit}>
            <span aria-hidden="true">{working ? "◌" : "✦"}</span>
            {working ? "Generating image…" : "Generate image"}
          </button>
          <p className="pg-submit-note">
            {local
              ? "The selected local model must be running in Korgis. No cloud generation charges."
              : "Cloud generation requires server-side API credentials and may incur provider charges."}
          </p>
        </form>

        <section className="playground-preview" aria-live="polite">
          <div className="pg-preview-heading">
            <div>
              <span className="eyebrow">03 / Output</span>
              <h3>Generated image</h3>
            </div>
            <span className={result ? "pg-output-state done" : "pg-output-state"}>
              {result ? "Complete" : working ? "Generating" : "Ready"}
            </span>
          </div>
          <div className={result ? "pg-canvas has-image" : "pg-canvas"}>
            {result ? (
              <img src={result.image_url} alt={`Generated by ${result.model_key}: ${result.prompt}`} />
            ) : working ? (
              <div className="pg-placeholder">
                <div className="pg-spinner" aria-hidden="true" />
                <strong>Creating your image</strong>
                <span>{Math.floor(seconds / 60)}m {seconds % 60}s elapsed</span>
                <small>On-device generation can take several minutes.</small>
              </div>
            ) : (
              <div className="pg-placeholder">
                <div className="pg-placeholder-art" aria-hidden="true">
                  <span className="pg-art-sun" />
                  <span className="pg-art-hill one" />
                  <span className="pg-art-hill two" />
                </div>
                <strong>Your canvas is ready</strong>
                <span>Choose an engine and enter a prompt to get started.</span>
              </div>
            )}
          </div>
          {error ? <div className="pg-error" role="alert">{error}</div> : null}
          {result ? (
            <div className="pg-result">
              <div className="pg-result-details">
                <span><strong>Engine</strong>{models.find((model) => model.key === result.model_key)?.name || result.model_key}</span>
                <span><strong>Duration</strong>{timeLabel(result.latency_ms)}</span>
                <span><strong>Seed</strong>{result.seed_effective ?? result.seed_requested ?? "—"}</span>
                <span><strong>Output</strong>{result.generation?.size || "Default"}</span>
              </div>
              <a
                className="pg-download"
                href={result.image_url}
                download={`${result.model_key}-${result.id}.${result.filename?.split(".").at(-1) || "png"}`}
              >
                Download image ↓
              </a>
              <small className="pg-output-caption">
                Saved locally with its engine configuration and SHA-256. Playground images are separate from benchmark runs.
              </small>
            </div>
          ) : (
            <div className="pg-preview-footer">
              <span>PNG, JPEG or WebP depending on engine</span>
              <span>One output at a time</span>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
