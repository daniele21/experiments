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


function sizeLabel(size) {
  const [w, h] = String(size).split("x").map(Number);
  const orientation = w === h ? "Square" : w > h ? "Landscape" : "Portrait";
  return `${orientation} · ${w} × ${h}`;
}

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
              <small>{editing ? "Editing uses eight Turbo steps" : "Choose supported model formats; benchmark defaults stay unchanged"}</small>
            </div>
            <div className="pg-setting-chips">
              <span>{editing ? (resolution === "match" && prepared
                ? matchedOutputSize(prepared.processed.width, prepared.processed.height)
                : resolution === "match" ? "Match source" : resolution)
                : selectedOutputSize || "Engine default"}</span>
              {selected?.generation?.num_inference_steps != null ? (
                <span>{selected.generation.num_inference_steps} steps</span>
              ) : null}
              {selected?.generation?.guidance_scale != null ? (
                <span>CFG {selected.generation.guidance_scale}</span>
              ) : null}
            </div>
            {!editing && choices.sizes.length > 0 ? (
              <label className="pg-field" htmlFor="pg-t2i-size">
                <span>Image shape & resolution</span>
                <select id="pg-t2i-size" value={selectedOutputSize}
                  disabled={working} onChange={(event) => setOutputSize(event.target.value)}>
                  {choices.sizes.map((size) => (
                    <option value={size} key={size}>{sizeLabel(size)}</option>
                  ))}
                </select>
              </label>
            ) : null}
            {!editing && choices.formats.length > 0 ? (
              <label className="pg-field" htmlFor="pg-t2i-format">
                <span>Output file format</span>
                <select id="pg-t2i-format" value={selectedOutputEncoding}
                  disabled={working || choices.formats.length === 1}
                  onChange={(event) => setOutputEncoding(event.target.value)}>
                  {choices.formats.map((format) => (
                    <option value={format} key={format}>{format.toUpperCase()}</option>
                  ))}
                </select>
                {choices.formats.length === 1 ? <small>Only this encoding is configured for the selected engine.</small> : null}
              </label>
            ) : null}
            {local ? (
              <div className="pg-field pg-seed">
                <span>Seed</span>
                <div className="pg-seed-mode" role="group" aria-label="Seed mode">
                  <button type="button" className={seedMode === "random" ? "selected" : ""}
                    aria-pressed={seedMode === "random"} disabled={working}
                    onClick={() => setSeedMode("random")}>Random each time</button>
                  <button type="button" className={seedMode === "fixed" ? "selected" : ""}
                    aria-pressed={seedMode === "fixed"} disabled={working}
                    onClick={() => setSeedMode("fixed")}>Fixed seed</button>
                </div>
                {seedMode === "fixed" ? (
                  <label htmlFor="pg-seed">
                    <span className="pg-seed-field-label">Seed value</span>
                    <input id="pg-seed" type="number" min={0} max={2147483647} step={1}
                      disabled={working} value={seed}
                      onChange={(event) => setSeed(event.target.value)} />
                  </label>
                ) : <small className="pg-seed-hint">A new random seed is generated on your device and saved with the result.</small>}
                {editing ? <small className="pg-seed-hint">For Qwen 2.1, reusing the reference generation's noise/seed can amplify grain and sharpening.</small> : null}
              </div>
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
              <span className="eyebrow">{displayedMode === "edit" ? "04 / Before & After" : "03 / Output"}</span>
              <h3>{displayedMode === "edit" ? "Compare the edit" : "Generated image"}</h3>
            </div>
            <span className={displayedResult ? "pg-output-state done" : "pg-output-state"}>
              {displayedResult ? "Complete" : working ? "Generating" : "Ready"}
            </span>
          </div>
          {displayedMode === "edit" && displayedSource ? (
            <div className="pg-before-after" aria-label="Before and after comparison">
              <div className="pg-before-after-item">
                <span>Before · Sent to model</span>
                <div className="pg-before-after-image">
                  <img src={displayedSource} alt="Image used as the editing reference" />
                </div>
              </div>
              <div className="pg-before-after-item">
                <span>After · Edited</span>
                <div className="pg-before-after-image">
                  {displayedResult ? (
                    <img src={displayedResult.image_url} alt="Image after AI editing" />
                  ) : (
                    <div className="pg-before-after-empty">
                      {working ? "Editing in progress…" : "Your edited image will appear here"}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className={displayedResult ? "pg-canvas has-image" : "pg-canvas"}>
              {displayedResult ? (
                <img src={displayedResult.image_url}
                  alt={`Generated by ${displayedResult.model_key}: ${displayedResult.prompt}`} />
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
          {displayedResult ? (
            <div className="pg-result">
              <div className="pg-result-details">
                <span><strong>Engine</strong>{selectedHistory?.modelName
                  || models.find((model) => model.key === displayedResult.model_key)?.name
                  || displayedResult.model_key}</span>
                <span><strong>Duration</strong>{timeLabel(displayedResult.latency_ms)}</span>
                <span><strong>Seed</strong>{displayedResult.seed_effective ?? displayedResult.seed_requested ?? "—"}</span>
                <span><strong>Output</strong>{displayedResult.generation?.size || "Default"}</span>
                <span><strong>File type</strong>{(displayedResult.mime_type || "image/png").replace("image/", "").toUpperCase()}</span>
                <span><strong>Mode</strong>{displayedMode === "edit" ? "Image to Image" : "Text to Image"}</span>
              </div>
              <div className="pg-source-provenance">
                <strong>Source prompt</strong>
                <p>{displayedResult.prompt}</p>
                {displayedMode === "edit" && selectedHistory?.originalUrl ? (
                  <div className="pg-history-source">
                    <img src={selectedHistory.originalUrl} alt="Original uploaded source photo" />
                    <span>Original upload: {selectedHistory.sourceName || "reference.png"}.
                      The Before panel shows the prepared reference actually sent to the model.</span>
                  </div>
                ) : null}
              </div>
              <a className="pg-download" href={displayedResult.image_url}
                download={`${displayedResult.model_key}-${displayedResult.id}.${displayedResult.filename?.split(".").at(-1) || "png"}`}>
                Download image ↓
              </a>
              <small className="pg-output-caption">
                {displayedMode === "edit"
                  ? "Only the generated output and the source checksum are saved by Experiments. Uploaded source images remain in this browser session."
                  : "Output saved locally with model and prompt metadata, separately from benchmark runs."}
              </small>
            </div>
          ) : (
            <div className="pg-preview-footer">
              <span>Formats depend on the selected model</span>
              <span>One output at a time</span>
            </div>
          )}
          <section className="pg-history-section" aria-label="Temporary generation history">
            <div className="pg-history-heading">
              <div>
                <span className="eyebrow">Session history</span>
                <h3>Recent generations <span>({history.length}/12)</span></h3>
              </div>
              {history.length ? (
                <button type="button" className="pg-history-clear"
                  onClick={clearHistory} disabled={working}>Clear history</button>
              ) : null}
            </div>
            <p className="pg-history-explainer">
              Temporary list for this tab; cleared on reload. Generated files are still saved locally by the existing Playground.
            </p>
            {history.length ? (
              <div className="pg-history-grid">
                {history.map((entry) => (
                  <button type="button" key={entry.id}
                    className={entry.id === (selectedHistory?.id || result?.id) ? "pg-history-item active" : "pg-history-item"}
                    aria-pressed={entry.id === (selectedHistory?.id || result?.id)}
                    onClick={() => setHistorySelectionId(entry.id)}>
                    <img src={entry.result.image_url} alt={`History: ${entry.prompt}`} loading="lazy" />
                    <span className="pg-history-item-detail">
                      <strong>{entry.mode === "edit" ? "Image edit" : "Text to Image"} · {new Date(entry.createdAt).toLocaleTimeString()}</strong>
                      <span title={entry.prompt}>{entry.prompt}</span>
                      <small>{entry.size || "Default"} · {entry.format.toUpperCase()} · seed {entry.seed ?? "—"}</small>
                      {entry.mode === "edit" ? <small>Source: {entry.sourceName || "uploaded image"}</small> : null}
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <div className="pg-history-empty">Generated images will appear here while this tab stays open.</div>
            )}
          </section>
        </section>
      </div>
    </div>
  );
}
