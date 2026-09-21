import React, { useState } from 'react';
import type { ExperimentStatus } from '../../types/benchmark';
import { Terminal, Copy, Check, Info } from 'lucide-react';

interface UnrunExperimentViewProps {
  status: ExperimentStatus;
}

export const UnrunExperimentView: React.FC<UnrunExperimentViewProps> = ({ status }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (status.cli_command) {
      navigator.clipboard.writeText(status.cli_command);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="empty-state-card">
      <div className="empty-state-icon">
        <Info size={24} />
      </div>
      <h2 className="empty-state-title">{status.full_title}</h2>
      <p className="empty-state-desc">
        {status.description}
      </p>
      {status.id === 'calibration' && (
        <div style={{ margin: '8px 0', fontSize: '13px', color: 'var(--text-muted)' }}>
          Evaluates <strong>Probability calibration</strong> and records <strong>Calibration predictions</strong> with expected vs observed outcomes.
        </div>
      )}

      <div style={{ margin: '16px 0 24px' }}>
        <span
          style={{
            display: 'inline-block',
            fontSize: '12px',
            fontWeight: 600,
            color: 'var(--text-muted)',
            marginBottom: '8px',
          }}
        >
          To evaluate this experiment across your local models, run:
        </span>
        <br />
        <div className="cli-command-box">
          <Terminal size={14} style={{ color: 'var(--accent)' }} />
          <span>{status.cli_command}</span>
          <button
            onClick={handleCopy}
            style={{
              background: 'transparent',
              border: 'none',
              color: copied ? 'var(--success)' : '#94a3b8',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              marginLeft: '8px',
            }}
            title="Copy command"
          >
            {copied ? <Check size={14} /> : <Copy size={14} />}
          </button>
        </div>
      </div>
    </div>
  );
};
