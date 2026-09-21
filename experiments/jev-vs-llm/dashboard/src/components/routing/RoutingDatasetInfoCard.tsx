/**
 * RoutingDatasetInfoCard.tsx
 *
 * Premium UI component displaying an in-depth, structured description
 * of the BANKING77 Intent Routing benchmark.
 *
 * Features:
 * - Clear explanation of Intent Routing (customer service triage vs network routing)
 * - Concrete query-to-intent examples
 * - Why BANKING77 is a prime benchmark for JEV vs small LLMs
 * - Side-by-side comparison: Closed-Set Routing (77 doors) vs Open-Set Calibration (77 doors + OOS)
 * - Evaluation profiles (budget, quick, standard, full)
 * - Interactive collapsible view with view tabs
 */

import React, { useState } from 'react';
import { ROUTING_INFO_CONFIG } from '../../config/routingInfo';
import {
  Compass,
  ArrowRight,
  HelpCircle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Layers,
  Sparkles,
  ShieldCheck,
} from 'lucide-react';

export const RoutingDatasetInfoCard: React.FC = () => {
  const [isExpanded, setIsExpanded] = useState<boolean>(true);
  const [activeSubTab, setActiveSubTab] = useState<'concept' | 'comparison' | 'profiles'>('concept');
  const config = ROUTING_INFO_CONFIG;

  return (
    <div className="card routing-info-card">
      {/* Top Banner Header */}
      <div className="card-header" style={{ marginBottom: isExpanded ? '16px' : '0' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div
              style={{
                width: '38px',
                height: '38px',
                borderRadius: 'var(--radius-md)',
                background: 'linear-gradient(135deg, rgba(79, 70, 229, 0.15) 0%, rgba(168, 85, 247, 0.15) 100%)',
                color: 'var(--accent)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                border: '1px solid var(--accent-light)',
              }}
            >
              <Compass size={20} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <h3 className="card-title" style={{ margin: 0 }}>
                  {config.overview.title}
                </h3>
                <span className="section-pill" style={{ color: 'var(--accent-text)', background: 'var(--accent-light)' }}>
                  {config.overview.badge}
                </span>
                <span className="section-pill">
                  {config.dataset.totalClasses} Classes
                </span>
                <span className="section-pill" style={{ color: 'var(--success-text)', background: 'var(--success-bg)' }}>
                  {config.dataset.citation}
                </span>
              </div>
              <p className="card-subtitle" style={{ marginTop: '4px' }}>
                {config.overview.conceptSummary}
              </p>
            </div>
          </div>

          <button
            type="button"
            className="tab-btn"
            style={{
              padding: '6px 12px',
              fontSize: '12px',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              cursor: 'pointer',
            }}
            onClick={() => setIsExpanded((prev) => !prev)}
            aria-expanded={isExpanded}
          >
            <span>{isExpanded ? 'Collapse Overview' : 'Dataset Deep-Dive'}</span>
            {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        </div>
      </div>

      {isExpanded && (
        <div style={{ marginTop: '8px' }}>
          {/* Sub Navigation Bar */}
          <div
            style={{
              display: 'flex',
              gap: '6px',
              borderBottom: '1px solid var(--border)',
              paddingBottom: '10px',
              marginBottom: '16px',
              flexWrap: 'wrap',
            }}
          >
            <button
              type="button"
              className={`tab-btn ${activeSubTab === 'concept' ? 'active' : ''}`}
              style={{ padding: '6px 14px', fontSize: '13px' }}
              onClick={() => setActiveSubTab('concept')}
            >
              <Layers size={14} style={{ marginRight: '6px' }} />
              Intent Routing Concept &amp; Examples
            </button>
            <button
              type="button"
              className={`tab-btn ${activeSubTab === 'comparison' ? 'active' : ''}`}
              style={{ padding: '6px 14px', fontSize: '13px' }}
              onClick={() => setActiveSubTab('comparison')}
            >
              <HelpCircle size={14} style={{ marginRight: '6px' }} />
              Routing vs Calibration (77 Doors)
            </button>
            <button
              type="button"
              className={`tab-btn ${activeSubTab === 'profiles' ? 'active' : ''}`}
              style={{ padding: '6px 14px', fontSize: '13px' }}
              onClick={() => setActiveSubTab('profiles')}
            >
              <CheckCircle2 size={14} style={{ marginRight: '6px' }} />
              Benchmark Profiles &amp; Ground Truth
            </button>
          </div>

          {/* TAB 1: Concept & Examples */}
          {activeSubTab === 'concept' && (
            <div>
              {/* Visual Flow Architecture */}
              <div
                style={{
                  background: 'var(--surface-alt)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-md)',
                  padding: '16px',
                  marginBottom: '16px',
                }}
              >
                <div style={{ fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Sparkles size={14} style={{ color: 'var(--accent)' }} />
                  Customer Support Routing Architecture
                </div>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '12px',
                    flexWrap: 'wrap',
                    padding: '8px 0',
                  }}
                >
                  <div
                    style={{
                      background: 'var(--surface)',
                      border: '1px solid var(--border)',
                      borderRadius: 'var(--radius-sm)',
                      padding: '10px 16px',
                      textAlign: 'center',
                      minWidth: '180px',
                      boxShadow: 'var(--shadow-sm)',
                    }}
                  >
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>INPUT</div>
                    <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text)' }}>User Message String</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Conversational support query</div>
                  </div>

                  <ArrowRight size={18} style={{ color: 'var(--accent)' }} />

                  <div
                    style={{
                      background: 'linear-gradient(135deg, rgba(79, 70, 229, 0.08) 0%, rgba(168, 85, 247, 0.08) 100%)',
                      border: '1px solid var(--accent-light)',
                      borderRadius: 'var(--radius-sm)',
                      padding: '10px 16px',
                      textAlign: 'center',
                      minWidth: '200px',
                      boxShadow: 'var(--shadow-sm)',
                    }}
                  >
                    <div style={{ fontSize: '11px', color: 'var(--accent-text)', fontWeight: 700 }}>EVALUATION ENGINE</div>
                    <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text)' }}>JEV or LLM Classifier</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Choice dist vs JSON Schema</div>
                  </div>

                  <ArrowRight size={18} style={{ color: 'var(--accent)' }} />

                  <div
                    style={{
                      background: 'var(--surface)',
                      border: '1px solid var(--border)',
                      borderRadius: 'var(--radius-sm)',
                      padding: '10px 16px',
                      textAlign: 'center',
                      minWidth: '200px',
                      boxShadow: 'var(--shadow-sm)',
                    }}
                  >
                    <div style={{ fontSize: '11px', color: 'var(--success-text)', fontWeight: 600 }}>OUTCOME</div>
                    <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text)' }}>1 of 77 Banking Intents</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Exact action destination</div>
                  </div>
                </div>
              </div>

              {/* Concrete Examples Cards */}
              <div style={{ marginBottom: '16px' }}>
                <div style={{ fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '8px' }}>
                  Real BANKING77 Query Examples
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '10px' }}>
                  {config.examples.map((ex, idx) => (
                    <div
                      key={idx}
                      style={{
                        background: 'var(--surface)',
                        border: '1px solid var(--border)',
                        borderRadius: 'var(--radius-sm)',
                        padding: '12px 14px',
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'space-between',
                      }}
                    >
                      <div style={{ fontSize: '13px', fontStyle: 'italic', color: 'var(--text)', marginBottom: '10px', lineHeight: 1.4 }}>
                        {ex.query}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '8px', borderTop: '1px dashed var(--border)' }}>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{ex.category}</span>
                        <code style={{ fontSize: '12px', color: 'var(--accent-text)', background: 'var(--accent-light)', padding: '2px 8px', borderRadius: '4px', fontWeight: 600 }}>
                          {ex.intent}
                        </code>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Why BANKING77 Matters Grid */}
              <div>
                <div style={{ fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '8px' }}>
                  {config.whyBanking77.title}
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '10px' }}>
                  {config.whyBanking77.points.map((pt, idx) => (
                    <div
                      key={idx}
                      style={{
                        background: 'var(--surface)',
                        border: '1px solid var(--border)',
                        borderRadius: 'var(--radius-sm)',
                        padding: '12px',
                      }}
                    >
                      <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text)', marginBottom: '4px' }}>
                        {pt.headline}
                      </div>
                      <p style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: 1.45 }}>
                        {pt.description}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: Routing vs Calibration (The 77 Doors) */}
          {activeSubTab === 'comparison' && (
            <div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px', marginBottom: '12px' }}>
                {/* Routing Card */}
                <div
                  style={{
                    background: 'var(--surface)',
                    border: '1px solid var(--border)',
                    borderTop: '3px solid var(--accent)',
                    borderRadius: 'var(--radius-md)',
                    padding: '16px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                    <h4 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text)', margin: 0 }}>
                      {config.routingVsCalibration.routing.title}
                    </h4>
                    <span className="section-pill" style={{ color: 'var(--accent-text)', background: 'var(--accent-light)' }}>
                      {config.routingVsCalibration.routing.type}
                    </span>
                  </div>
                  <div
                    style={{
                      background: 'var(--surface-alt)',
                      padding: '8px 12px',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: '13px',
                      fontWeight: 600,
                      color: 'var(--accent)',
                      marginBottom: '10px',
                    }}
                  >
                    🚪 Analogy: &ldquo;{config.routingVsCalibration.routing.analogy}&rdquo;
                  </div>
                  <p style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: 1.5, marginBottom: '12px' }}>
                    {config.routingVsCalibration.routing.description}
                  </p>
                  <div style={{ fontSize: '12px', background: 'var(--surface-alt)', padding: '10px', borderRadius: 'var(--radius-sm)', fontFamily: 'var(--font-mono)' }}>
                    BANKING77 query &rarr; &#123;intent_1, ... intent_77&#125; &rarr; Exact match
                  </div>
                </div>

                {/* Calibration Card */}
                <div
                  style={{
                    background: 'var(--surface)',
                    border: '1px solid var(--border)',
                    borderTop: '3px solid var(--warning)',
                    borderRadius: 'var(--radius-md)',
                    padding: '16px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                    <h4 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text)', margin: 0 }}>
                      {config.routingVsCalibration.calibration.title}
                    </h4>
                    <span className="section-pill" style={{ color: 'var(--warning-text)', background: 'var(--warning-bg)' }}>
                      {config.routingVsCalibration.calibration.type}
                    </span>
                  </div>
                  <div
                    style={{
                      background: 'var(--surface-alt)',
                      padding: '8px 12px',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: '13px',
                      fontWeight: 600,
                      color: 'var(--warning)',
                      marginBottom: '10px',
                    }}
                  >
                    🛑 Analogy: &ldquo;{config.routingVsCalibration.calibration.analogy}&rdquo;
                  </div>
                  <p style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: 1.5, marginBottom: '12px' }}>
                    {config.routingVsCalibration.calibration.description}
                  </p>
                  <div style={{ fontSize: '12px', background: 'var(--surface-alt)', padding: '10px', borderRadius: 'var(--radius-sm)', fontFamily: 'var(--font-mono)' }}>
                    Query &rarr; &#123;77 banking intents&#125; + &quot;other&quot; &rarr; Intent or Rejection
                  </div>
                </div>
              </div>

              <div
                style={{
                  background: 'var(--surface-alt)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '12px 16px',
                  fontSize: '13px',
                  color: 'var(--text-muted)',
                  lineHeight: 1.5,
                }}
              >
                <strong>Operational Takeaway:</strong> Routing measures accuracy across 77 supported choices. Calibration additionally measures risk control: whether confidence drops and whether the model rejects out-of-domain requests instead of hallucinating a banking intent.
              </div>
            </div>
          )}

          {/* TAB 3: Profiles & Ground Truth */}
          {activeSubTab === 'profiles' && (
            <div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px', marginBottom: '16px' }}>
                {config.profiles.map((prof) => (
                  <div
                    key={prof.name}
                    style={{
                      background: 'var(--surface)',
                      border: prof.recommended ? '2px solid var(--accent)' : '1px solid var(--border)',
                      borderRadius: 'var(--radius-md)',
                      padding: '14px',
                      position: 'relative',
                    }}
                  >
                    {prof.recommended && (
                      <span
                        style={{
                          position: 'absolute',
                          top: '-9px',
                          right: '12px',
                          background: 'var(--accent)',
                          color: '#fff',
                          fontSize: '10px',
                          fontWeight: 700,
                          padding: '2px 8px',
                          borderRadius: 'var(--radius-full)',
                          textTransform: 'uppercase',
                        }}
                      >
                        Default Local Profile
                      </span>
                    )}
                    <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text)', marginBottom: '4px' }}>
                      <code>--profile {prof.name}</code>
                    </div>
                    <div style={{ fontSize: '20px', fontWeight: 800, color: 'var(--text)', margin: '6px 0' }}>
                      {prof.cases.toLocaleString()}{' '}
                      <span style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text-muted)' }}>
                        cases ({prof.casesPerClass})
                      </span>
                    </div>
                    <p style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: 1.4 }}>
                      {prof.description}
                    </p>
                  </div>
                ))}
              </div>

              {/* Ground truth purity notice */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '10px',
                  background: 'var(--surface-alt)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '12px 16px',
                  fontSize: '13px',
                }}
              >
                <ShieldCheck size={18} style={{ color: 'var(--success)', marginTop: '2px', flexShrink: 0 }} />
                <div style={{ color: 'var(--text-muted)', lineHeight: 1.45 }}>
                  <strong style={{ color: 'var(--text)' }}>Upstream Ground Truth Fidelity:</strong> All evaluation labels are sourced directly from PolyAI&apos;s human-annotated test split ({config.dataset.totalTestCases} examples). No synthetic labels are generated by JEV or tested LLMs, ensuring objective, bias-free metrics.
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
