import React from 'react';
import { Database, Layers } from 'lucide-react';

export type DatasetFilterKey = string;

interface DatasetFilterBarProps {
  activeDataset: DatasetFilterKey;
  onSelectDataset: (key: DatasetFilterKey) => void;
  datasets: Array<{ id: string; label: string; count: number }>;
  total: number;
}

export const DatasetFilterBar: React.FC<DatasetFilterBarProps> = ({
  activeDataset,
  onSelectDataset,
  datasets,
  total,
}) => {
  return (
    <div className="dataset-filter-bar">
      <div className="dataset-filter-label">
        <span className="dataset-label-text">Latest runs · Dataset:</span>
      </div>
      <div className="dataset-filter-pills">
        <button
          type="button"
          className={`dataset-pill-btn ${activeDataset === 'all' ? 'active' : ''}`}
          onClick={() => onSelectDataset('all')}
          aria-pressed={activeDataset === 'all'}
          title="Aggregate the latest run of each model configuration across benchmark datasets"
        >
          <Layers size={13} className="pill-icon" />
          <span className="pill-title">Overall</span>
          <span className="pill-count">{total}</span>
        </button>
        {datasets.map((dataset) => (
          <button
            key={dataset.id}
            type="button"
            className={`dataset-pill-btn ${activeDataset === dataset.id ? 'active' : ''}`}
            onClick={() => onSelectDataset(dataset.id)}
            aria-pressed={activeDataset === dataset.id}
          >
            <Database size={13} className="pill-icon" />
            <span className="pill-title">{dataset.label}</span>
            <span className="pill-count">{dataset.count}</span>
          </button>
        ))}
      </div>
    </div>
  );
};
