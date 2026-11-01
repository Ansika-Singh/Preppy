import React, { useState, useEffect } from 'react';
import { Layers, ChevronRight, BookOpen, Quote, Clock, Check, X } from 'lucide-react';
import { Concept, Mastery } from '../types';
import { MasteryBadge } from '../components/MasteryBadge';
import { ProgressChart } from '../components/ProgressChart';
import { callLearnRpc } from '../LearnApi';

interface ConceptMapViewProps {
  conceptsWithMastery: Array<{ concept: Concept; mastery: Mastery | null }>;
  onStartDiagnosticForConcept?: (conceptId: string) => void;
}

export const ConceptMapView: React.FC<ConceptMapViewProps> = ({ conceptsWithMastery }) => {
  const [selectedConceptId, setSelectedConceptId] = useState<string | null>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  // Group into tree: roots (parent_id is null) and children
  const roots = conceptsWithMastery.filter(({ concept }) => !concept.parent_id);
  const getChildren = (parentId: string) =>
    conceptsWithMastery.filter(({ concept }) => concept.parent_id === parentId);

  const activeItem = conceptsWithMastery.find(({ concept }) => concept.id === selectedConceptId) || conceptsWithMastery[0];

  useEffect(() => {
    if (activeItem && activeItem.concept) {
      void loadHistory(activeItem.concept.id);
    }
  }, [selectedConceptId]);

  const loadHistory = async (cid: string) => {
    setLoadingHistory(true);
    try {
      const res = await callLearnRpc('learn.mastery.history', { concept_id: cid });
      if (res && res.success && res.history) {
        setHistory(res.history);
      } else {
        setHistory([]);
      }
    } catch {
      setHistory([]);
    } finally {
      setLoadingHistory(false);
    }
  };

  if (conceptsWithMastery.length === 0) {
    return (
      <div className="concept-map-empty">
        <Layers size={48} className="text-muted" />
        <h3>No Concepts Extracted Yet</h3>
        <p>Upload a course document in the Materials tab or load the demo dataset to view your knowledge tree.</p>
      </div>
    );
  }

  return (
    <div className="learn-concept-map-view">
      {/* Left Column: Concept Tree */}
      <div className="concept-tree-col">
        <div className="tree-header">
          <h3>Knowledge Graph</h3>
          <span className="concept-total-tag">{conceptsWithMastery.length} Concepts</span>
        </div>

        <div className="concept-nodes-list">
          {roots.map(({ concept, mastery }) => {
            const children = getChildren(concept.id);
            const isSelected = (activeItem && activeItem.concept.id === concept.id);

            return (
              <div key={concept.id} className="tree-group">
                <div
                  className={`concept-node-card root-node ${isSelected ? 'selected' : ''}`}
                  onClick={() => setSelectedConceptId(concept.id)}
                >
                  <div className="node-info">
                    <span className="node-name">{concept.name}</span>
                    <span className="node-desc">{concept.description}</span>
                  </div>
                  <MasteryBadge
                    mastery={mastery ? mastery.mastery : 0.5}
                    band={mastery ? mastery.band : 'insufficient_evidence'}
                    size="sm"
                  />
                </div>

                {/* Child Nodes */}
                {children.length > 0 && (
                  <div className="tree-children-container">
                    {children.map(({ concept: childConcept, mastery: childMastery }) => {
                      const isChildSelected = (activeItem && activeItem.concept.id === childConcept.id);
                      return (
                        <div
                          key={childConcept.id}
                          className={`concept-node-card child-node ${isChildSelected ? 'selected' : ''}`}
                          onClick={() => setSelectedConceptId(childConcept.id)}
                        >
                          <div className="node-info">
                            <span className="node-name">{childConcept.name}</span>
                          </div>
                          <MasteryBadge
                            mastery={childMastery ? childMastery.mastery : 0.5}
                            band={childMastery ? childMastery.band : 'insufficient_evidence'}
                            size="sm"
                          />
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Right Column: Detailed Inspector */}
      {activeItem && (
        <div className="concept-inspector-col">
          <div className="inspector-card">
            <div className="inspector-header">
              <div>
                <span className="inspector-tag">Concept Detail</span>
                <h2>{activeItem.concept.name}</h2>
              </div>
              <MasteryBadge
                mastery={activeItem.mastery ? activeItem.mastery.mastery : 0.5}
                band={activeItem.mastery ? activeItem.mastery.band : 'insufficient_evidence'}
                size="md"
              />
            </div>

            <p className="inspector-desc">{activeItem.concept.description}</p>

            {/* Metrics Breakdown */}
            <div className="inspector-metrics-grid">
              <div className="metric-box">
                <span className="metric-label">Attempts</span>
                <span className="metric-val">{activeItem.mastery ? activeItem.mastery.attempts : 0}</span>
              </div>
              <div className="metric-box">
                <span className="metric-label">Correct</span>
                <span className="metric-val">{activeItem.mastery ? activeItem.mastery.correct : 0}</span>
              </div>
              <div className="metric-box">
                <span className="metric-label">Consistency</span>
                <span className="metric-val">
                  {activeItem.mastery ? `${Math.round(activeItem.mastery.consistency * 100)}%` : '—'}
                </span>
              </div>
              <div className="metric-box">
                <span className="metric-label">Transfer Check</span>
                <span className="metric-val">
                  {activeItem.mastery?.has_transfer_success ? 'Verified' : 'Pending'}
                </span>
              </div>
            </div>

            {/* Grounding Source Span */}
            {activeItem.concept.source_spans && activeItem.concept.source_spans.length > 0 && (
              <div className="grounding-span-box">
                <div className="span-header">
                  <Quote size={14} />
                  <span>Verified Source Grounding (from notes)</span>
                </div>
                <blockquote className="span-quote">
                  "{activeItem.concept.source_spans[0].quote}"
                </blockquote>
              </div>
            )}

            {/* Real Data Progress Over Time */}
            <div className="inspector-chart-area">
              <ProgressChart history={history} title="Mastery Trajectory" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

