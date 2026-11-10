import { useEffect, useMemo, useRef, useState } from "react";
import { matchedOutputSize, prepareReferenceImage } from "./reference-resize.js";
import { appendHistory, makeHistoryEntry, outputChoices, resolveSeed } from "./playground-session.js";

const EXAMPLES = [
  { label: "Photorealism", prompt: "Photorealistic editorial photograph of a small Italian café at sunrise, soft window light, a ceramic espresso cup, believable materials and natural reflections." },
  { label: "Composition", prompt: "Exactly three objects on a pale stone table: a red ceramic mug on the left, a green apple in the center, and a blue notebook on the right. No other objects." },
  { label: "Typography", prompt: 'A minimal modern poster displaying exactly the words "LOCAL AI, REAL CONTROL" in crisp, readable typography, with no other text.' },
];

const INITIAL_PROMPT = EXAMPLES[0].prompt;
const EDIT_PROMPT = "Change the color of the main object, preserving the composition, lighting and everything else.";
const EDIT_RESOLUTIONS = ["512x512", "768x768", "1024x1024", "1024x768", "768x1024"];


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
  const [prepared, setPrepared] = useState(null);
  const [preparedPreview, setPreparedPreview] = useState("");
  const [preparingImage, setPreparingImage] = useState(false);
  const sourceSelection = useRef(0);
  const [resolution, setResolution] = useState("match");
  const [isDragging, setDragging] = useState(false);
  // Use distinct seed defaults: a fixed T2I seed is useful for comparison,
  // but replaying the reference's original noise can oversharpen Qwen edits.
  const [textSeed, setTextSeed] = useState("42");
  const [editSeed, setEditSeed] = useState("43");
  const [textSeedMode, setTextSeedMode] = useState("random");
  const [editSeedMode, setEditSeedMode] = useState("random");
  const [outputSize, setOutputSize] = useState("");
  const [outputEncoding, setOutputEncoding] = useState("");
  const [history, setHistory] = useState([]);
  const [historySelectionId, setHistorySelectionId] = useState(null);
  const historyRef = useRef([]);
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
    if (!prepared?.file) {
      setPreparedPreview("");
      return;
    }
    const url = URL.createObjectURL(prepared.file);
    setPreparedPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [prepared]);

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
  const seed = editing ? editSeed : textSeed;
  const setSeed = editing ? setEditSeed : setTextSeed;
  const seedMode = editing ? editSeedMode : textSeedMode;
  const setSeedMode = editing ? setEditSeedMode : setTextSeedMode;
  const choices = outputChoices(selected);
  const selectedOutputSize = choices.sizes.includes(outputSize) ? outputSize
    : choices.sizes.includes(selected?.generation?.size) ? selected.generation.size
      : (choices.sizes[0] || "");
  const defaultEncoding = selected?.generation?.output_format
    || selected?.generation?.response_format?.mime_type?.replace("image/", "") || "";
  const selectedOutputEncoding = choices.formats.includes(outputEncoding) ? outputEncoding
    : choices.formats.includes(defaultEncoding) ? defaultEncoding
      : (choices.formats[0] || "");
  const selectedHistory = history.find((entry) => entry.id === historySelectionId);
  const displayedResult = selectedHistory?.result || result;
  const displayedMode = selectedHistory?.mode || mode;
  const displayedSource = selectedHistory
    ? selectedHistory.sourceUrl : preparedPreview;
  const canSubmit = selected?.configured && prompt.trim().length > 0 &&
    prompt.length <= 4000 && !working && !preparingImage &&
    (!editing || (editAvailable && prepared?.file));

  // Retain reference image object URLs only while this Playground tab is open.
  // These are not written to the server or any browser storage.
  useEffect(() => () => {
    for (const entry of historyRef.current) {
      if (entry.sourceUrl) URL.revokeObjectURL(entry.sourceUrl);
      if (entry.originalUrl) URL.revokeObjectURL(entry.originalUrl);
    }
  }, []);

  function clearHistory() {
    for (const entry of historyRef.current) {
      if (entry.sourceUrl) URL.revokeObjectURL(entry.sourceUrl);
      if (entry.originalUrl) URL.revokeObjectURL(entry.originalUrl);
    }
    historyRef.current = [];
    setHistory([]);
    setHistorySelectionId(null);
    setResult(null);
  }

  function recordHistory(body, generationMode) {
    const sourceUrl = generationMode === "edit" && prepared?.file
      ? URL.createObjectURL(prepared.file) : null;
    const originalUrl = generationMode === "edit" && sourceImage
      ? URL.createObjectURL(sourceImage) : null;
    const item = makeHistoryEntry(body, {
      mode: generationMode,
      modelName: models.find((item) => item.key === body.model_key)?.name || body.model_key,
      sourceUrl,
      originalUrl,
      sourceName: generationMode === "edit" ? sourceImage?.name : null,
    });
    const updated = appendHistory(historyRef.current, item);
    for (const entry of updated.evicted) {
      if (entry.sourceUrl) URL.revokeObjectURL(entry.sourceUrl);
      if (entry.originalUrl) URL.revokeObjectURL(entry.originalUrl);
    }
    historyRef.current = updated.entries;
    setHistory(updated.entries);
    setHistorySelectionId(item.id);
  }

  async function chooseSource(file) {
    if (!file) return;
    const ticket = ++sourceSelection.current;
    setSourceImage(null);
    setPrepared(null);
    setResult(null);
    setPreparingImage(true);
    setError("");
    try {
      const converted = await prepareReferenceImage(file);
      if (ticket !== sourceSelection.current) return;
      setSourceImage(file);
      setPrepared(converted);
      setResolution("match");
      setResult(null);
    } catch (reason) {
      if (ticket !== sourceSelection.current) return;
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      if (ticket === sourceSelection.current) setPreparingImage(false);
    }
  }

  function changeMode(nextMode) {
    if (nextMode === "edit" && !editAvailable) return;
    setMode(nextMode);
    setHistorySelectionId(null);
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
    setHistorySelectionId(null);
    try {
      const payload = { model_key: modelKey, prompt: prompt.trim() };
      if (local) payload.seed = resolveSeed(seedMode, seed);
      if (!editing) {
        if (selectedOutputSize) payload.size = selectedOutputSize;
        if (selectedOutputEncoding) payload.output_format = selectedOutputEncoding;
      }
      let response;
      if (editing) {
        const form = new FormData();
        form.set("model_key", payload.model_key);
        form.set("prompt", payload.prompt);
        form.set("image", prepared.file, prepared.file.name);
        form.set("source_original_width", String(prepared.original.width));
        form.set("source_original_height", String(prepared.original.height));
        form.set("resize_policy", prepared.policy);
        form.set("size", resolution === "match"
          ? matchedOutputSize(prepared.processed.width, prepared.processed.height)
          : resolution);
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
      recordHistory(body, editing ? "edit" : "generate");
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
          <p>Generate a new image or edit a reference photo with a local model.</p>
        </div>
        <span className="playground-intro-tag">One image at a time</span>
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
              onChange={(event) => {
                setModelKey(event.target.value);
                setOutputSize("");
                setOutputEncoding("");
                setHistorySelectionId(null);
                setMode("generate");
                setResult(null);
                setError("");
              }}
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
              {selected.image_editing_supported && !editAvailable ? (
                <p>Editing unavailable. Start Korgis with <code>--image-editing-enabled</code> and refresh engines.</p>
              ) : null}
            </div>
          ) : null}
          <div className="pg-mode-wrapper">
            <div className="pg-mode-header">
              <span>Generation mode</span>
              <button type="button" className="pg-refresh" disabled={working || loadingModels}
                onClick={async () => {
                  try {
                    setLoadingModels(true);
                    const response = await fetch("/api/playground/models", { cache: "no-store" });
                    const payload = await response.json();
                    if (!response.ok) throw new Error(payload.error || "Engine refresh failed");
                    setModels(payload.models || []);
                    setError("");
                  } catch (reason) {
                    setError(reason?.message || String(reason));
                  } finally {
                    setLoadingModels(false);
                  }
                }}>↻ Refresh engines</button>
            </div>
            <div className="pg-modes" role="group" aria-label="Image operation">
              <button type="button" className={!editing ? "selected" : ""}
                aria-pressed={!editing} disabled={working}
                onClick={() => changeMode("generate")}>Text to Image</button>
              <button type="button" className={editing ? "selected" : ""}
                aria-pressed={editing} disabled={working || !editAvailable}
                title={!editAvailable ? "Requires Qwen Turbo running with image editing enabled" : "Edit an existing image"}
                onClick={() => changeMode("edit")}>Image to Image</button>
            </div>
            {!editAvailable ? <small className="pg-mode-hint">Image editing requires Qwen Turbo running with the vision projector enabled in Korgis.</small> : null}
          </div>
          <div className="pg-divider" />
          {editing ? (
            <section className="pg-source-section" aria-label="Reference image">
              <div className="pg-section-title">
                <span className="pg-step">02</span>
                <div><h3>Reference image</h3><p>PNG up to 8 MiB / 24 MP. Large images are fitted locally to 1 MP, without cropping.</p></div>
              </div>
              <div className={isDragging ? "pg-dropzone drag" : "pg-dropzone"}
                onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
                onDragLeave={(event) => { event.preventDefault(); setDragging(false); }}
                onDrop={(event) => {
                  event.preventDefault();
                  setDragging(false);
                  if (!working && !preparingImage) chooseSource(event.dataTransfer.files?.[0]);
                }}>
                {sourcePreview ? <img src={sourcePreview} alt="Source image selected for editing" /> : (
                  <span className="pg-dropzone-icon" aria-hidden="true">＋</span>
                )}
                <label htmlFor="pg-image-upload" className="pg-upload-action">
                  {sourceImage ? "Replace image" : "Choose a PNG or drop it here"}
                </label>
                <input id="pg-image-upload" type="file" accept="image/png" disabled={working || preparingImage}
                  onChange={(event) => {
                    chooseSource(event.target.files?.[0]);
                    event.target.value = "";
                  }} />
                {preparingImage ? <small>Preparing the image locally…</small> : sourceImage
                  ? <small>{sourceImage.name} · {(sourceImage.size / 1024 / 1024).toFixed(2)} MiB</small>
                  : <small>Local upload · no cloud processing</small>}
              </div>
              {prepared ? (
                <div className={prepared.resized ? "pg-resize-note resized" : "pg-resize-note"} role="status">
                  <strong>{prepared.resized ? "Automatically resized · no cropping" : "Original dimensions preserved"}</strong>
                  <span>{prepared.original.width} × {prepared.original.height} → {prepared.processed.width} × {prepared.processed.height} px sent to Qwen</span>
                  {prepared.resized ? <small>Image text can become less sharp. The before preview shows exactly what the model receives.</small> : null}
                </div>
              ) : null}
              <label className="pg-field" htmlFor="pg-resolution">
                <span>Output resolution</span>
                <select id="pg-resolution" value={resolution} disabled={working}
                  onChange={(event) => setResolution(event.target.value)}>
                  {prepared ? (
                    <option value="match">Match source proportions ({matchedOutputSize(prepared.processed.width, prepared.processed.height).replace("x", " × ")})</option>
                  ) : <option value="match">Match source proportions</option>}
                  {EDIT_RESOLUTIONS.map((value) => <option value={value} key={value}>{value.replace("x", " × ")}</option>)}
                </select>
              </label>
            </section>
          ) : null}
          <div className="pg-section-title">
            <span className="pg-step">{editing ? "03" : "02"}</span>
            <div>
              <h3>{editing ? "Describe the changes" : "Write your prompt"}</h3>
              <p>{editing ? "Specify what to modify and what should remain unchanged." : "Describe the image you want to generate."}</p>
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
              placeholder={editing ? "Change the wall to sage green, preserving the furniture and lighting..." : "A photorealistic scene of..."}
            />
            <span className="pg-char-count">{prompt.length} / 4000 characters</span>
          </label>
          {!editing ? (
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
          ) : null}
          <div className="pg-settings">
            <div>
              <span>Generation settings</span>
              <small>{editing ? "Editing uses eight Turbo steps" : "Using the selected engine defaults"}</small>
            </div>
            <div className="pg-setting-chips">
              <span>{editing ? (resolution === "match" && prepared
                ? matchedOutputSize(prepared.processed.width, prepared.processed.height)
                : resolution === "match" ? "Match source" : resolution)
                : selected?.generation?.size || "Engine default"}</span>
              {selected?.generation?.num_inference_steps != null ? (
                <span>{selected.generation.num_inference_steps} steps</span>
              ) : null}
              {selected?.generation?.guidance_scale != null ? (
                <span>CFG {selected.generation.guidance_scale}</span>
              ) : null}
            </div>
            {local ? (
              <label className="pg-field pg-seed" htmlFor="pg-seed">
                <span>Seed <small>{editing ? "(blank = new random seed)" : "(fixed for repeatability)"}</small></span>
                <input
                  id="pg-seed"
                  type="number"
                  min={0}
                  max={2147483647}
                  step={1}
                  disabled={working}
                  value={seed}
                  placeholder={editing ? "Auto · fresh seed" : "42"}
                  onChange={(event) => setSeed(event.target.value)}
                />
                {editing ? <small className="pg-seed-hint">Recommended: leave blank. Reusing the source image's generation seed can cause Qwen 2.1 noise-replay artifacts (excessive contrast, grain and sharpening).</small> : null}
              </label>
            ) : null}
          </div>
          <button className="pg-generate" type="submit" disabled={!canSubmit}>
            <span aria-hidden="true">{working ? "◌" : "✦"}</span>
            {working ? (editing ? "Editing image…" : "Generating image…") : (editing ? "Generate edited image" : "Generate image")}
          </button>
          <p className="pg-submit-note">
            {local
              ? (editing ? "Source image sent only to local Korgis. One operation at a time." : "The selected local model must be running in Korgis. No cloud generation charges.")
              : "Cloud generation requires server-side API credentials and may incur provider charges."}
          </p>
        </form>

        <section className="playground-preview" aria-live="polite">
          <div className="pg-preview-heading">
            <div>
              <span className="eyebrow">{editing ? "04 / Before & After" : "03 / Output"}</span>
              <h3>{editing ? "Compare the edit" : "Generated image"}</h3>
            </div>
            <span className={result ? "pg-output-state done" : "pg-output-state"}>
              {result ? "Complete" : working ? "Generating" : "Ready"}
            </span>
          </div>
          {editing && preparedPreview ? (
            <div className="pg-before-after" aria-label="Before and after comparison">
              <div className="pg-before-after-item">
                <span>Before · Sent to Qwen</span>
                <div className="pg-before-after-image">
                  <img src={preparedPreview} alt="Prepared reference image sent to Qwen" />
                </div>
              </div>
              <div className="pg-before-after-item">
                <span>After · Edited</span>
                <div className="pg-before-after-image">
                  {result ? (
                    <img src={result.image_url} alt="Image after AI editing" />
                  ) : (
                    <div className="pg-before-after-empty">
                      {working ? "Editing in progress…" : "Your edited image will appear here"}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : (
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
          )}
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
                {result.mode === "edit"
                  ? "Output and source SHA-256 saved locally. Your original upload is not retained by Experiments."
                  : "Saved locally with its engine configuration and SHA-256. Playground images are separate from benchmark runs."}
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
