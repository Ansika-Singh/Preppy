import React from 'react';
import { Brain, AlertTriangle, CalendarClock, BookOpen, Sparkles, CheckCircle2 } from 'lucide-react';
import { Mastery, MasteryBand } from '../types';
import { MasteryBadge } from '../components/MasteryBadge';
import { ProgressChart } from '../components/ProgressChart';

interface DashboardViewProps {
  stats: {
    materials_count: number;
    concepts_count: number;
    due_revision_count: number;
    open_misconceptions_count: number;
  };
  conceptsWithMastery: Array<{ concept: any; mastery: Mastery | null }>;
  openMisconceptions: any[];
  onNavigate: (tab: string) => void;
  onLoadSample: () => void;
  loadingSample: boolean;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  stats,
  conceptsWithMastery,
  openMisconceptions,
  onNavigate,
  onLoadSample,
  loadingSample,
}) => {
  const masteries = conceptsWithMastery.map((item) => item.mastery).filter(Boolean) as Mastery[];

  const countByBand = (b: MasteryBand) => masteries.filter((m) => m.band === b).length;
  const strongCount = countByBand('strong');
  const moderateCount = countByBand('moderate');
  const weakCount = countByBand('weak');
  const insufficientCount = countByBand('insufficient_evidence');

  return (
    <div className="learn-dashboard-view">
      {/* Top Banner / Philosophy */}
      <div className="dashboard-hero">
        <div className="hero-text">
          <span className="hero-tag">Preppy Engine</span>
          <h2>Don't just learn. Prove you understand.</h2>
          <p>
            Unlike traditional tutors that just answer questions, Preppy discovers your hidden misconceptions,
            verifies that you’ve corrected them, and schedules deterministic spaced review so you never make the same
            conceptual mistake twice.
          </p>
        </div>
        <div className="hero-actions" style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <button
            type="button"
            className="sample-load-btn"
            onClick={onLoadSample}
            disabled={loadingSample}
          >
            <Sparkles size={16} />
            <span>{loadingSample ? 'Loading Demo Data...' : 'Load Physics Demo'}</span>
          </button>
          <button
            type="button"
            className="panel-cta-btn"
            style={{ padding: '12px 20px', borderRadius: '12px', fontSize: '0.92rem' }}
            onClick={() => onNavigate('diagnostic')}
          >
            Start Diagnostic →
          </button>
        </div>
      </div>

      {/* Demo Ready Banner */}
      {stats.materials_count > 0 && (
        <div style={{
          background: 'linear-gradient(135deg, #fff5f7 0%, #ffffff 100%)',
          border: '1px solid rgba(244, 63, 94, 0.25)',
          borderRadius: '16px',
          padding: '18px 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '16px',
          boxShadow: '0 4px 20px -2px rgba(244, 63, 94, 0.08)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <div style={{
              width: '42px',
              height: '42px',
              borderRadius: '11px',
              background: 'rgba(244, 63, 94, 0.1)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#e11d48',
              flexShrink: 0,
            }}>
              <Sparkles size={20} />
            </div>
            <div>
              <h4 style={{ margin: '0 0 3px 0', color: '#0f172a', fontSize: '1rem', fontWeight: 700 }}>
                Demo Ready: 20 Concepts &amp; Diagnostic Assessment Loaded
              </h4>
              <p style={{ margin: 0, color: '#475569', fontSize: '0.85rem' }}>
                Engineering Physics notes and pre-authored questions are active. Test Question 1 on Newton's Second Law.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => onNavigate('diagnostic')}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '10px 20px',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, #f43f5e 0%, #ec4899 100%)',
              color: '#fff',
              fontWeight: 700,
              fontSize: '0.88rem',
              border: 'none',
              cursor: 'pointer',
              boxShadow: '0 4px 16px rgba(244, 63, 94, 0.35)',
              whiteSpace: 'nowrap',
            }}
          >
            Open Diagnostic Quiz →
          </button>
        </div>
      )}

      {/* Metric Cards Grid */}
      <div className="dashboard-grid">
        <div className="stat-card" onClick={() => onNavigate('concepts')}>
          <div className="stat-icon-wrap accent">
            <Brain size={22} />
          </div>
          <div className="stat-details">
            <span className="stat-title">Active Concepts</span>
            <div className="stat-value">{stats.concepts_count}</div>
            <span className="stat-sub">{strongCount} Strong · {moderateCount} Moderate · {weakCount} Weak</span>
          </div>
        </div>

        <div className="stat-card" onClick={() => onNavigate('revision')}>
          <div className="stat-icon-wrap warning">
            <CalendarClock size={22} />
          </div>
          <div className="stat-details">
            <span className="stat-title">Due for Revision</span>
            <div className="stat-value">{stats.due_revision_count}</div>
            <span className="stat-sub">Deterministic spaced review</span>
          </div>
        </div>

        <div className="stat-card" onClick={() => onNavigate('diagnostic')}>
          <div className="stat-icon-wrap danger">
            <AlertTriangle size={22} />
          </div>
          <div className="stat-details">
            <span className="stat-title">Open Misconceptions</span>
            <div className="stat-value">{stats.open_misconceptions_count}</div>
            <span className="stat-sub">Targeted verification active</span>
          </div>
        </div>

        <div className="stat-card" onClick={() => onNavigate('materials')}>
          <div className="stat-icon-wrap info">
            <BookOpen size={22} />
          </div>
          <div className="stat-details">
            <span className="stat-title">Uploaded Materials</span>
            <div className="stat-value">{stats.materials_count}</div>
            <span className="stat-sub">Syllabus & Lecture Notes</span>
          </div>
        </div>
      </div>

      {/* Main Dual Columns */}
      <div className="dashboard-dual-columns">
        {/* Left Column: Open Misconceptions & Alerts */}
        <div className="dashboard-panel">
          <div className="panel-title-bar">
            <h3>Diagnostic Focus Areas</h3>
            <span className="badge-count">{openMisconceptions.length}</span>
          </div>

          {openMisconceptions.length === 0 ? (
            <div className="panel-empty-state">
              <CheckCircle2 size={32} className="text-success" />
              <p>No unresolved conceptual flaws detected! Take a diagnostic quiz to assess new topics.</p>
              <button
                type="button"
                className="panel-cta-btn"
                onClick={() => onNavigate('diagnostic')}
              >
                Start Knowledge Diagnostic
              </button>
            </div>
          ) : (
            <div className="misconception-list">
              {openMisconceptions.map((item, idx) => (
                <div key={idx} className="misconception-card-item">
                  <div className="misc-header">
                    <span className="misc-concept">{item.concept_name}</span>
                    <span className={`misc-state-chip ${item.state}`}>{item.state}</span>
                  </div>
                  <p className="misc-evidence">
                    <strong>Evidence Quote:</strong> "{item.evidence_quote || item.error_type}"
                  </p>
                  <button
                    type="button"
                    className="misc-remediate-btn"
                    onClick={() => onNavigate('tutor')}
                  >
                    Open Misconception Tutor →
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right Column: Concept Mastery Breakdown */}
        <div className="dashboard-panel">
          <div className="panel-title-bar">
            <h3>Knowledge Mastery</h3>
            <button
              type="button"
              className="view-all-link"
              onClick={() => onNavigate('concepts')}
            >
              View Concept Tree →
            </button>
          </div>

          {conceptsWithMastery.length === 0 ? (
            <div className="panel-empty-state">
              <BookOpen size={32} className="text-muted" />
              <p>No materials uploaded yet. Upload your syllabus or notes to build your knowledge map.</p>
              <button
                type="button"
                className="panel-cta-btn"
                onClick={() => onNavigate('materials')}
              >
                Upload Course Notes
              </button>
            </div>
          ) : (
            <div className="concept-mastery-list">
              {conceptsWithMastery.slice(0, 6).map(({ concept, mastery }, i) => (
                <div key={i} className="concept-mastery-row">
                  <div className="concept-info">
                    <span className="concept-row-name">{concept.name}</span>
                    <span className="concept-row-attempts">
                      {mastery ? `${mastery.attempts} attempts` : 'No attempts'}
                    </span>
                  </div>
                  <MasteryBadge
                    mastery={mastery ? mastery.mastery : 0.5}
                    band={mastery ? mastery.band : 'insufficient_evidence'}
                    size="sm"
                  />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

