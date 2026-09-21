import React from 'react';
import type { LocalParametersInfo } from '../../types/benchmark';
import { Sliders, Maximize2, FileText, Compass, Sparkles, Cpu, Layers } from 'lucide-react';

interface LocalParametersGridProps {
  parameters?: LocalParametersInfo;
}

export const LocalParametersGrid: React.FC<LocalParametersGridProps> = ({ parameters }) => {
  const ctx = parameters?.context_window_tokens ? `${parameters.context_window_tokens.toLocaleString()} tokens` : '8,192 tokens';
  const maxOut = parameters?.max_output_tokens ? `${parameters.max_output_tokens} tokens` : '512 tokens';
  const temp = parameters?.temperature !== undefined ? `${parameters.temperature.toFixed(1)} (Greedy)` : '0.0 (Greedy)';
  const reasoning = parameters?.thinking_policy || 'Disabled (off)';
  const runtime = parameters?.inference_runtime || 'llama-server (Homebrew llama.cpp)';
  const slots = parameters?.batch_slots || '1 parallel slot · continuous batching · unified KV';

  return (
    <div className="local-params-container">
      <div className="local-params-header">
        <div className="local-params-kicker">
          <Sliders size={13} />
          <span>Local Model Inference &amp; Execution Bounds</span>
        </div>
        <span className="local-params-note">
          Standardized parameters applied across all local open-weights evaluations
        </span>
      </div>

      <div className="local-params-grid">
        <div className="param-card">
          <div className="param-card-header">
            <div className="param-card-icon">
              <Maximize2 size={16} />
            </div>
            <span className="param-card-label">Context Window</span>
          </div>
          <div className="param-card-value">{ctx}</div>
          <div className="param-card-detail">llama-server --ctx-size</div>
        </div>

        <div className="param-card">
          <div className="param-card-header">
            <div className="param-card-icon">
              <FileText size={16} />
            </div>
            <span className="param-card-label">Max Output Budget</span>
          </div>
          <div className="param-card-value">{maxOut}</div>
          <div className="param-card-detail">Bounded decision generation cap</div>
        </div>

        <div className="param-card">
          <div className="param-card-header">
            <div className="param-card-icon">
              <Compass size={16} />
            </div>
            <span className="param-card-label">Sampling Temperature</span>
          </div>
          <div className="param-card-value">{temp}</div>
          <div className="param-card-detail">Strictly deterministic greedy decoding</div>
        </div>

        <div className="param-card">
          <div className="param-card-header">
            <div className="param-card-icon">
              <Sparkles size={16} />
            </div>
            <span className="param-card-label">Reasoning / Thinking</span>
          </div>
          <div className="param-card-value" style={{ color: 'var(--accent)' }}>{reasoning}</div>
          <div className="param-card-detail">LLAMA_ARG_REASONING=off (Direct JSON)</div>
        </div>

        <div className="param-card">
          <div className="param-card-header">
            <div className="param-card-icon">
              <Cpu size={16} />
            </div>
            <span className="param-card-label">Inference Runtime</span>
          </div>
          <div className="param-card-value">{runtime}</div>
          <div className="param-card-detail">Metal GPU offload via Homebrew</div>
        </div>

        <div className="param-card">
          <div className="param-card-header">
            <div className="param-card-icon">
              <Layers size={16} />
            </div>
            <span className="param-card-label">Concurrency &amp; Batching</span>
          </div>
          <div className="param-card-value">{slots}</div>
          <div className="param-card-detail">Zero memory contention isolation</div>
        </div>
      </div>
    </div>
  );
};
