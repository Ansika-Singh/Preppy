import React, { useState, useEffect } from 'react';
import { Sparkles, AlertTriangle, Quote, CheckCircle2, RefreshCw, ArrowRight, Lightbulb, ShieldAlert } from 'lucide-react';
import { MisconceptionAnalysisResult, Question } from '../types';
import { callLearnRpc } from '../LearnApi';

interface TutorViewProps {
  initialAttempt: any | null;
  onNavigate: (tab: string) => void;
}

export const TutorView: React.FC<TutorViewProps> = ({ initialAttempt, onNavigate }) => {
  const [analyzing, setAnalyzing] = useState(false);
  const [analysis, setAnalysis] = useState<MisconceptionAnalysisResult | null>(null);
  const [loopCount, setLoopCount] = useState(1);

  // Follow-up interaction
  const [selectedFollowupOption, setSelectedFollowupOption] = useState<string>('');
  const [followupSubmitted, setFollowupSubmitted] = useState(false);
  const [followupCorrect, setFollowupCorrect] = useState(false);

  useEffect(() => {
    if (initialAttempt) {
      void runAnalysis(initialAttempt, 1);
    }
  }, [initialAttempt]);

  const runAnalysis = async (attemptData: any, loop: number) => {
    setAnalyzing(true);
    setFollowupSubmitted(false);
    setSelectedFollowupOption('');
    try {
      const res = await callLearnRpc('learn.misconception.analyze', {
        attempt_id: attemptData.attempt_id,
        question_id: attemptData.question_id,
        concept_id: attemptData.concept_id,
        answer_text: attemptData.answer_text,
        reasoning_text: attemptData.reasoning_text,
        confidence: attemptData.confidence,
        loop_count: loop,
      });

      if (res && res.success && res.analysis) {
        setAnalysis(res.analysis);
        setLoopCount(loop);
      }
    } finally {
      setAnalyzing(false);
    }
  };

  const handleFollowupSubmit = () => {
    if (!analysis || !analysis.followup_question) return;
    const isCorr =
      selectedFollowupOption.trim().toLowerCase() ===
      analysis.followup_question.correct_answer.trim().toLowerCase();
    setFollowupCorrect(isCorr);
    setFollowupSubmitted(true);
  };

  const handleNextLoop = () => {
    if (!initialAttempt) return;
    void runAnalysis(initialAttempt, loopCount + 1);
  };

  if (!initialAttempt && !analysis) {
    return (
      <div className="tutor-empty-card">
        <Sparkles size={40} className="text-accent" />
        <h3>Misconception Remediation Engine</h3>
        <p>
          Take a diagnostic assessment in the Diagnostic tab. When you answer a question incorrectly, Preppy will
          diagnose the exact mental model flaw, extract verbatim reasoning evidence, and verify you've mastered it.
        </p>
        <button type="button" className="panel-cta-btn" onClick={() => onNavigate('diagnostic')}>
          Go to Diagnostic Assessment →
        </button>
      </div>
    );
  }

  return (
    <div className="learn-tutor-view">
      <div className="view-header">
        <div>
          <h2>Cognitive Misconception Tutor</h2>
          <p>
            Understanding <em>why</em> an answer is wrong is more valuable than just reading the correct answer.
          </p>
        </div>
      </div>

      {analyzing && (
        <div className="tutor-analyzing-card">
          <Sparkles size={32} className="spin text-accent" />
          <h3>Analyzing Cognitive Flaw & Extracting Evidence...</h3>
          <p>Validating quoted substrings and synthesizing targeted analogy.</p>
        </div>
      )}

      {analysis && !analyzing && (
        <div className="tutor-content-stack">
          {/* Card 1: What Happened / Diagnosis */}
          <div className="tutor-card diagnosis-card">
            <div className="card-top-bar">
              <span className={`error-chip ${analysis.error_type}`}>{analysis.error_type.replace('_', ' ')}</span>
              <span className={`state-chip ${analysis.state}`}>{analysis.state.toUpperCase()}</span>
              <span className="confidence-chip">Confidence: {Math.round(analysis.confidence * 100)}%</span>
            </div>

            {analysis.needs_probe || analysis.error_type === 'uncertain' ? (
              <div className="uncertainty-box">
                <AlertTriangle size={20} className="text-warning" />
                <div>
                  <h4>I'm not completely certain why this went wrong.</h4>
                  <p>
                    Rather than asserting an ungrounded guess, let's explore your thinking. What prompted this answer?
                  </p>
                </div>
              </div>
            ) : (
              <div className="verdict-box">
                <h3>Likely Misconception Identified</h3>
                <p className="verdict-rationale">{analysis.rationale}</p>
                {analysis.evidence_quote && (
                  <div className="evidence-quote-box">
                    <Quote size={16} />
                    <span>
                      Verbatim Quote from Your Reasoning:{' '}
                      <strong>"{analysis.evidence_quote}"</strong>
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Card 2: Targeted Explanation & Analogy */}
          <div className="tutor-card explanation-card">
            <div className="explanation-section">
              <h4>Why the Intuition Fails</h4>
              <p>{analysis.why_wrong}</p>
            </div>

            <div className="core-idea-section">
              <div className="section-label-row">
                <h4>Governing Principle</h4>
                <span className="source-grounding-tag">{analysis.source_label}</span>
              </div>
              <p className="core-idea-text">{analysis.core_idea}</p>
              {analysis.grounded_source && (
                <blockquote className="notes-citation">
                  From notes: "{analysis.grounded_source}"
                </blockquote>
              )}
            </div>

            <div className="analogy-section">
              <div className="analogy-header">
                <Lightbulb size={18} className="text-accent" />
                <h4>Real-World Analogy</h4>
              </div>
              <p className="analogy-text">{analysis.analogy}</p>
            </div>
          </div>

          {/* Card 3: Verification Follow-Up Question */}
          {analysis.followup_question && (
            <div className="tutor-card followup-card">
              <div className="followup-header">
                <span className="verification-step-tag">Verification Check</span>
                <h3>Targeted Follow-Up Question</h3>
                <p className="followup-sub">
                  Same underlying principle tested with a <em>different surface form</em>.
                </p>
              </div>

              <div className="followup-stem">
                <h4>{analysis.followup_question.stem}</h4>
              </div>

              {!followupSubmitted && (
                <div className="options-container">
                  {analysis.followup_question.options.map((opt, i) => (
                    <div
                      key={i}
                      className={`option-row ${selectedFollowupOption === opt ? 'selected' : ''}`}
                      onClick={() => setSelectedFollowupOption(opt)}
                    >
                      <span className="option-letter">{String.fromCharCode(65 + i)}</span>
                      <span className="option-text">{opt}</span>
                    </div>
                  ))}
                </div>
              )}

              {!followupSubmitted && (
                <button
                  type="button"
                  className="submit-followup-btn"
                  onClick={handleFollowupSubmit}
                  disabled={!selectedFollowupOption}
                >
                  Verify Understanding
                </button>
              )}

              {followupSubmitted && (
                <div className={`followup-feedback-banner ${followupCorrect ? 'correct' : 'wrong'}`}>
                  {followupCorrect ? (
                    <div>
                      <div className="feedback-title-row">
                        <CheckCircle2 size={24} className="text-success" />
                        <h4>Verification Passed! Conceptual Flaw Corrected.</h4>
                      </div>
                      <p>
                        You successfully resolved this misconception on a transfer problem. It will be scheduled for
                        spaced revision to ensure long-term retention.
                      </p>
                      <button
                        type="button"
                        className="continue-btn"
                        onClick={() => onNavigate('revision')}
                      >
                        View Spaced Revision Queue →
                      </button>
                    </div>
                  ) : (
                    <div>
                      <div className="feedback-title-row">
                        <AlertTriangle size={24} className="text-danger" />
                        <h4>Still Struggling with this Concept</h4>
                      </div>
                      <p>
                        {analysis.exceeded_loop_cap
                          ? "We've reached the loop limit for today. Let's revisit this tomorrow during spaced review."
                          : 'Escalating explanation style to worked example...'}
                      </p>
                      {!analysis.exceeded_loop_cap ? (
                        <button type="button" className="retry-loop-btn" onClick={handleNextLoop}>
                          <RefreshCw size={14} />
                          <span>Try Worked Example (Escalation Step {loopCount + 1})</span>
                        </button>
                      ) : (
                        <button
                          type="button"
                          className="continue-btn"
                          onClick={() => onNavigate('revision')}
                        >
                          Schedule for Later Review →
                        </button>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

