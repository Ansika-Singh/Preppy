import React, { useState, useEffect, useCallback } from 'react';
import {
  Brain,
  BookOpen,
  Layers,
  HelpCircle,
  Lightbulb,
  CalendarClock,
  RefreshCw,
  Sparkles,
  X,
  AlertCircle,
  Mic,
} from 'lucide-react';
import { Material, Concept, Mastery, LearnStatus } from './types';
import { StatusChip } from './components/StatusChip';
import { LandingPageView } from './views/LandingPageView';
import { DashboardView } from './views/DashboardView';
import { ReadRecallView } from './views/ReadRecallView';
import { MaterialsView } from './views/MaterialsView';
import { ConceptMapView } from './views/ConceptMapView';
import { DiagnosticView } from './views/DiagnosticView';
import { TutorView } from './views/TutorView';
import { RevisionView } from './views/RevisionView';
import { callLearnRpc } from './LearnApi';
import './learn.css';

export interface LearnViewProps {
  onClose?: () => void;
  isStandalone?: boolean;
}

export type LearnTab = 'overview' | 'dashboard' | 'recall' | 'materials' | 'concepts' | 'diagnostic' | 'tutor' | 'revision';

export const LearnView: React.FC<LearnViewProps> = ({ onClose, isStandalone = false }) => {
  const [activeTab, setActiveTab] = useState<LearnTab>('overview');
  const [loading, setLoading] = useState(false);
  const [loadingSample, setLoadingSample] = useState(false);
  const [extractingId, setExtractingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Status & Data State
  const [status, setStatus] = useState<LearnStatus | null>(null);
  const [dueRevisionCount, setDueRevisionCount] = useState<number>(0);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [conceptsWithMastery, setConceptsWithMastery] = useState<
    Array<{ concept: Concept; mastery: Mastery | null }>
  >([]);
  const [openMisconceptions, setOpenMisconceptions] = useState<any[]>([]);

  // Inter-view communication
  const [tutorAttempt, setTutorAttempt] = useState<any | null>(null);

  const refreshData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // 1. Fetch system status
      const statusRes = await callLearnRpc('learn.status', {});
      if (statusRes && statusRes.status) {
        setStatus(statusRes.status);
      }

      // 2. Fetch materials
      const materialsRes = await callLearnRpc('learn.material.list', {});
      if (materialsRes && materialsRes.materials) {
        setMaterials(materialsRes.materials);
      }

      // 3. Fetch concepts & masteries
      const conceptsRes = await callLearnRpc('learn.concepts.list', {});
      if (conceptsRes && conceptsRes.concepts) {
        if (conceptsRes.concepts.length > 0 && 'concept' in conceptsRes.concepts[0]) {
          setConceptsWithMastery(conceptsRes.concepts);
        } else {
          const cList: Concept[] = conceptsRes.concepts;
          const combined = cList.map((c) => ({
            concept: c,
            mastery: null,
          }));
          setConceptsWithMastery(combined);
        }
      }

      // 4. Fetch open misconceptions
      const miscRes = await callLearnRpc('learn.misconception.list_open', {});
      if (miscRes && miscRes.records) {
        setOpenMisconceptions(miscRes.records);
      }

      // 5. Fetch due revision count
      const revRes = await callLearnRpc('learn.revision.queue', { max_items: 50 });
      if (revRes && revRes.queue) {
        setDueRevisionCount(revRes.queue.length);
      }
    } catch (err: any) {
      console.error('Failed to refresh Preppy data:', err);
      setError(err?.message || 'Could not connect to Preppy engine daemon.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshData();
  }, [refreshData]);

  const handleLoadSample = async () => {
    setLoadingSample(true);
    setError(null);
    try {
      const res = await callLearnRpc('learn.sample.load', {});
      if (res && res.success) {
        await refreshData();
        setActiveTab('diagnostic');
      } else {
        setError(res?.error || 'Failed to load sample dataset.');
      }
    } catch (err: any) {
      setError(err?.message || 'Error executing sample loader RPC.');
    } finally {
      setLoadingSample(false);
    }
  };

  const handleUploadMaterial = async (title: string, content: string, kind: any) => {
    setError(null);
    try {
      const res = await callLearnRpc('learn.material.create', {
        title,
        content,
        kind,
      });
      if (res && res.material) {
        await refreshData();
      } else {
        setError(res?.error || 'Failed to save learning material.');
      }
    } catch (err: any) {
      setError(err?.message || 'Error uploading material.');
    }
  };

  const handleExtractConcepts = async (materialId: string) => {
    setExtractingId(materialId);
    setError(null);
    try {
      const res = await callLearnRpc('learn.material.extract_concepts', {
        material_id: materialId,
      });
      if (res && res.success) {
        await refreshData();
        setActiveTab('concepts');
      } else {
        setError(res?.error || 'Failed to extract concepts.');
      }
    } catch (err: any) {
      setError(err?.message || 'Error during concept extraction.');
    } finally {
      setExtractingId(null);
    }
  };

  const handleOpenTutorWithResult = (attemptResult: any) => {
    setTutorAttempt(attemptResult);
    setActiveTab('tutor');
  };

  const dashboardStats = {
    materials_count: materials.length,
    concepts_count: conceptsWithMastery.length,
    due_revision_count: dueRevisionCount,
    open_misconceptions_count: openMisconceptions.length,
  };

  return (
    <div className={`learn-view-root ${isStandalone ? 'standalone' : ''}`}>
      {/* Top Navigation Header */}
      <header className="learn-header">
        <div className="learn-brand-group">
          <div className="learn-brand-logo">
            <span role="img" aria-label="grad-cap">🎓</span>
            <span>Preppy</span>
          </div>
          <span className="learn-brand-badge">Learning Engine</span>
          <span className="learn-tagline-sub">Don't just learn. Prove you understand.</span>
        </div>

        {/* Navigation Tabs */}
        <nav className="learn-nav-tabs">
          <button
            className={`learn-tab-btn ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            <Sparkles size={15} />
            <span>Overview</span>
          </button>
          <button
            className={`learn-tab-btn ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => setActiveTab('dashboard')}
          >
            <Brain size={15} />
            <span>Dashboard</span>
          </button>
          <button
            className={`learn-tab-btn ${activeTab === 'recall' ? 'active' : ''}`}
            onClick={() => setActiveTab('recall')}
            title="Read -> Recall Voice Mode (Headline Flow)"
          >
            <Mic size={15} />
            <span>Read → Recall</span>
          </button>
          <button
            className={`learn-tab-btn ${activeTab === 'materials' ? 'active' : ''}`}
            onClick={() => setActiveTab('materials')}
          >
            <BookOpen size={15} />
            <span>Materials</span>
          </button>
          <button
            className={`learn-tab-btn ${activeTab === 'concepts' ? 'active' : ''}`}
            onClick={() => setActiveTab('concepts')}
          >
            <Layers size={15} />
            <span>Concept Map</span>
          </button>
          <button
            className={`learn-tab-btn ${activeTab === 'diagnostic' ? 'active' : ''}`}
            onClick={() => setActiveTab('diagnostic')}
          >
            <HelpCircle size={15} />
            <span>Diagnostic</span>
          </button>
          <button
            className={`learn-tab-btn ${activeTab === 'tutor' ? 'active' : ''}`}
            onClick={() => setActiveTab('tutor')}
          >
            <Lightbulb size={15} />
            <span>Tutor</span>
          </button>
          <button
            className={`learn-tab-btn ${activeTab === 'revision' ? 'active' : ''}`}
            onClick={() => setActiveTab('revision')}
          >
            <CalendarClock size={15} />
            <span>Revision</span>
          </button>
        </nav>

        {/* Right Header Actions */}
        <div className="learn-header-actions">
          <StatusChip status={status} />
          <button
            className="btn-sample-demo"
            onClick={handleLoadSample}
            disabled={loadingSample}
            title="Load the Engineering Physics sample syllabus & notes"
          >
            <Sparkles size={14} />
            <span>{loadingSample ? 'Loading Demo...' : 'Load Physics Demo'}</span>
          </button>
          <button
            className="btn-icon-action"
            onClick={() => void refreshData()}
            title="Refresh Preppy State"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
          {onClose && (
            <button className="btn-icon-action" onClick={onClose} title="Close Preppy">
              <X size={16} />
            </button>
          )}
        </div>
      </header>

      {/* Error Banner */}
      {error && (
        <div className="learn-error-banner">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
          <button
            onClick={() => setError(null)}
            style={{ background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer' }}
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* Main Tab Views */}
      <main className="learn-body-container">
        {activeTab === 'overview' && (
          <LandingPageView
            onStartDemo={handleLoadSample}
            onNavigate={(tab) => setActiveTab(tab as LearnTab)}
          />
        )}

        {activeTab === 'dashboard' && (
          <DashboardView
            stats={dashboardStats}
            conceptsWithMastery={conceptsWithMastery}
            openMisconceptions={openMisconceptions}
            onNavigate={(tab) => setActiveTab(tab as LearnTab)}
            onLoadSample={handleLoadSample}
            loadingSample={loadingSample}
          />
        )}

        {activeTab === 'recall' && (
          <ReadRecallView
            onNavigate={(tab) => setActiveTab(tab as LearnTab)}
            onOpenTutorWithResult={handleOpenTutorWithResult}
          />
        )}

        {activeTab === 'materials' && (
          <MaterialsView
            materials={materials}
            onUpload={handleUploadMaterial}
            onExtractConcepts={handleExtractConcepts}
            extractingId={extractingId}
          />
        )}

        {activeTab === 'concepts' && (
          <ConceptMapView
            conceptsWithMastery={conceptsWithMastery}
            onStartDiagnosticForConcept={() => setActiveTab('diagnostic')}
          />
        )}

        {activeTab === 'diagnostic' && (
          <DiagnosticView
            materials={materials}
            onOpenTutorWithResult={handleOpenTutorWithResult}
          />
        )}

        {activeTab === 'tutor' && (
          <TutorView
            initialAttempt={tutorAttempt}
            onNavigate={(tab) => setActiveTab(tab as LearnTab)}
          />
        )}

        {activeTab === 'revision' && (
          <RevisionView
            onNavigate={(tab) => setActiveTab(tab as LearnTab)}
          />
        )}
      </main>
    </div>
  );
};
