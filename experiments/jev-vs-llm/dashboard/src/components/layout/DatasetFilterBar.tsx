import React from 'react';
import { Database, Zap, Layers } from 'lucide-react';

export type DatasetFilterKey = 'all' | 'public' | 'smoke';

interface DatasetFilterBarProps {
  activeDataset: DatasetFilterKey;
  onSelectDataset: (key: DatasetFilterKey) => void;
  counts: {
    all: number;
    public: number;
    smoke: number;
  };
}

export const DatasetFilterBar: React.FC<DatasetFilterBarProps> = ({
  activeDataset,
  onSelectDataset,
  counts,
}) => {
  return (
    <div className="dataset-filter-bar">
      <div className="dataset-filter-label">
        <span className="dataset-label-text">Dataset Tier:</span>
      </div>
      <div className="dataset-filter-pills">
        <button
          className={`dataset-pill-btn ${activeDataset === 'public' ? 'active' : ''}`}
          onClick={() => onSelectDataset('public')}
          title="Filter to standardized 77-class Banking77 benchmark runs (fair apples-to-apples comparison)"
        >
          <Database size={13} className="pill-icon" />
          <span className="pill-title">Public Benchmark (Banking77)</span>
          <span className="pill-count">{counts.public}</span>
        </button>

        <button
          className={`dataset-pill-btn ${activeDataset === 'smoke' ? 'active' : ''}`}
          onClick={() => onSelectDataset('smoke')}
          title="Filter to 24-case local synthetic test runs"
        >
          <Zap size={13} className="pill-icon" />
          <span className="pill-title">Smoke Test (24 cases)</span>
          <span className="pill-count">{counts.smoke}</span>
        </button>

        <button
          className={`dataset-pill-btn ${activeDataset === 'all' ? 'active' : ''}`}
          onClick={() => onSelectDataset('all')}
          title="Display all model configurations across all evaluated datasets"
        >
          <Layers size={13} className="pill-icon" />
          <span className="pill-title">All Runs</span>
          <span className="pill-count">{counts.all}</span>
        </button>
      </div>
    </div>
  );
};
