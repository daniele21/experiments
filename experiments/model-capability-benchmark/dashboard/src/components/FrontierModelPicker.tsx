import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { Check, ChevronDown, Search } from 'lucide-react';
import type { FrontierPoint } from '../types';

interface FrontierModelPickerProps {
  models: FrontierPoint[];
  selectedSignatures: string[] | null;
  onChange: (next: string[] | null) => void;
}

export function FrontierModelPicker({
  models,
  selectedSignatures,
  onChange,
}: FrontierModelPickerProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const rootRef = useRef<HTMLDivElement>(null);
  const panelId = useId();

  useEffect(() => {
    if (!open) return undefined;
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  const distinctModels = useMemo(
    () => [...new Map(models.map((model) => [model.model_signature, model])).values()]
      .sort((a, b) => a.model_key.localeCompare(b.model_key)
        || a.model_signature.localeCompare(b.model_signature)),
    [models],
  );
  const availableSignatures = useMemo(
    () => distinctModels.map((model) => model.model_signature),
    [distinctModels],
  );
  const selectedSet = useMemo(
    () => new Set(selectedSignatures ?? availableSignatures),
    [selectedSignatures, availableSignatures],
  );
  const selectedCount = distinctModels.filter((model) => selectedSet.has(model.model_signature)).length;
  const filtered = distinctModels.filter((model) => [
    model.model_key, model.family, model.quantization, model.parameters_b,
  ].some((value) => String(value ?? '').toLowerCase().includes(query.trim().toLowerCase())));

  const toggle = (signature: string) => {
    const next = new Set(selectedSet);
    if (next.has(signature)) next.delete(signature);
    else next.add(signature);
    onChange(next.size === availableSignatures.length ? null : availableSignatures.filter((id) => next.has(id)));
  };

  return (
    <div className="frontier-model-filter" ref={rootRef}>
      <span className="frontier-control-label">Models</span>
      <button
        type="button"
        className={`frontier-model-trigger${open ? ' open' : ''}`}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((current) => !current)}
      >
        <span>
          {selectedCount === distinctModels.length
            ? `All models (${distinctModels.length})`
            : `${selectedCount} of ${distinctModels.length} selected`}
        </span>
        <ChevronDown size={15} aria-hidden="true" />
      </button>
      {open ? (
        <div className="frontier-model-panel" id={panelId}>
          <div className="frontier-model-panel-top">
            <strong>Choose models</strong>
            <span>{selectedCount} / {distinctModels.length} selected</span>
          </div>
          <div className="frontier-model-bulk">
            <button type="button" onClick={() => onChange(null)}>Select all</button>
            <button type="button" onClick={() => onChange([])}>Clear</button>
          </div>
          <label className="frontier-model-search">
            <Search size={14} aria-hidden="true" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Find a model..."
              aria-label="Find a model to select"
            />
          </label>
          <div className="frontier-model-options" role="group" aria-label="Available models">
            {filtered.map((model) => (
              <label key={model.model_signature} className="frontier-model-option">
                <input
                  type="checkbox"
                  checked={selectedSet.has(model.model_signature)}
                  onChange={() => toggle(model.model_signature)}
                />
                <span className="frontier-model-check" aria-hidden="true">
                  {selectedSet.has(model.model_signature) ? <Check size={12} /> : null}
                </span>
                <span className="frontier-model-option-text">
                  <strong title={model.model_key}>{model.model_key}</strong>
                  <small>
                    {model.family ?? 'Other family'}
                    {model.parameters_b != null ? ` · ${model.parameters_b}B` : ''}
                    {model.quantization ? ` · ${model.quantization}` : ''}
                  </small>
                </span>
              </label>
            ))}
            {filtered.length === 0 ? <p className="frontier-model-no-results">No matching models.</p> : null}
          </div>
          <div className="frontier-model-panel-footer">
            <button type="button" onClick={() => setOpen(false)}>Done</button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
