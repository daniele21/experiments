import React from 'react';
import type { ExperimentStatus } from '../../types/benchmark';
import { LayoutDashboard, Compass, Gauge, Zap, GitFork, Bot, Info } from 'lucide-react';

export type TabKey = 'overview' | 'routing' | 'calibration' | 'scaling' | 'workflow' | 'agent' | 'details';

interface NavigationTabsProps {
  activeTab: TabKey;
  onSelectTab: (tab: TabKey) => void;
  experiments: Record<string, ExperimentStatus>;
}

export const NavigationTabs: React.FC<NavigationTabsProps> = ({
  activeTab,
  onSelectTab,
  experiments,
}) => {
  const tabs: Array<{ key: TabKey; label: string; icon: React.ReactNode; badge?: { text: string; hasData: boolean } }> = [
    {
      key: 'overview',
      label: 'Overview',
      icon: <LayoutDashboard size={15} />,
    },
    {
      key: 'routing',
      label: 'Routing',
      icon: <Compass size={15} />,
      badge: experiments.routing
        ? { text: experiments.routing.badge_text, hasData: experiments.routing.has_data }
        : undefined,
    },
    {
      key: 'calibration',
      label: 'Calibration',
      icon: <Gauge size={15} />,
      badge: experiments.calibration
        ? { text: experiments.calibration.badge_text, hasData: experiments.calibration.has_data }
        : undefined,
    },
    {
      key: 'scaling',
      label: 'Scaling',
      icon: <Zap size={15} />,
      badge: experiments.scaling
        ? { text: experiments.scaling.badge_text, hasData: experiments.scaling.has_data }
        : undefined,
    },
    {
      key: 'workflow',
      label: 'Workflow',
      icon: <GitFork size={15} />,
      badge: experiments.workflow
        ? { text: experiments.workflow.badge_text, hasData: experiments.workflow.has_data }
        : undefined,
    },
    {
      key: 'agent',
      label: 'Agent',
      icon: <Bot size={15} />,
      badge: experiments.agent
        ? { text: experiments.agent.badge_text, hasData: experiments.agent.has_data }
        : undefined,
    },
    {
      key: 'details',
      label: 'Run details',
      icon: <Info size={15} />,
    },
  ];

  return (
    <nav className="tabs-nav" role="tablist">
      {tabs.map((tab) => {
        const isActive = activeTab === tab.key;
        return (
          <button
            key={tab.key}
            role="tab"
            aria-selected={isActive}
            className={`tab-btn ${isActive ? 'active' : ''}`}
            onClick={() => onSelectTab(tab.key)}
          >
            {tab.icon}
            <span>{tab.label}</span>
            {tab.badge && (
              <span
                className={`tab-badge ${
                  tab.badge.hasData ? 'badge-has-data' : 'badge-empty'
                }`}
              >
                {tab.badge.text}
              </span>
            )}
          </button>
        );
      })}
    </nav>
  );
};
