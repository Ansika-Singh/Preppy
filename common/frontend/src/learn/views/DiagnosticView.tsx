import React, { useState, useEffect } from 'react';
import { HelpCircle, Send, CheckCircle2, AlertTriangle, ArrowRight, Sparkles, Clock, RefreshCw } from 'lucide-react';
import { Material, Question } from '../types';
import { MasteryBadge } from '../components/MasteryBadge';
import { callLearnRpc } from '../LearnApi';

interface DiagnosticViewProps {
  materials: Material[];
  onOpenTutorWithResult: (result: any) => void;
}

export const DiagnosticView: React.FC<DiagnosticViewProps> = ({ materials, onOpenTutorWithResult }) => {
  const [selectedMaterialId, setSelectedMaterialId] = useState<string>('');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [totalQuestions, setTotalQuestions] = useState(0);

  // Student inputs
  const [selectedOption, setSelectedOption] = useState<string>('');
  const [reasoningText, setReasoningText] = useState<string>('');
  const [confidence, setConfidence] = useState<number>(2); // Default medium (2)
  const [startTime, setStartTime] = useState<number>(Date.now());

  // Result state
  const [submitting, setSubmitting] = useState(false);
  const [lastResult, setLastResult] = useState<any | null>(null);
  const [sessionReport, setSessionReport] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);

  const startSessionWithMaterial = async (matId: string) => {
    setLoading(true);
    setSessionReport(null);
    setLastResult(null);
    try {
      const res = await callLearnRpc('learn.diagnostic.start', {
        material_id: matId,
        question_count: 10,
      });
      if (res && res.success) {
        setSessionId(res.session_id);
        setTotalQuestions(res.total_questions);
        setCurrentIndex(res.current_index);
        setCurrentQuestion(res.first_question);
        setSelectedOption('');
        setReasoningText('');
        setConfidence(2);
        setStartTime(Date.now());
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (materials.length > 0) {
      const notesMat = materials.find((m) => m.kind === 'notes') || materials[0];
      setSelectedMaterialId(notesMat.id);
      if (!sessionId) {
        void startSessionWithMaterial(notesMat.id);
      }
    }
  }, [materials]);

  const handleStartSession = async () => {
    if (!selectedMaterialId) return;
    await startSessionWithMaterial(selectedMaterialId);
  };

  const handleSubmitAnswer = async () => {
    if (!sessionId || !currentQuestion) return;
    if (currentQuestion.type === 'mcq' && !selectedOption) return;

    setSubmitting(true);
    const elapsed = Date.now() - startTime;
    try {
      const res = await callLearnRpc('learn.diagnostic.submit', {
        session_id: sessionId,
        answer_text: selectedOption || reasoningText,
        selected_option: selectedOption,
        reasoning_text: reasoningText,
        confidence: confidence,
        time_ms: elapsed,
      });

      if (res && res.success) {
        setLastResult(res.result);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleNextQuestion = async () => {
    if (!sessionId) return;
    setLastResult(null);
    setSelectedOption('');
    setReasoningText('');
    setConfidence(2);
    setStartTime(Date.now());

    setLoading(true);
    try {
      const res = await callLearnRpc('learn.diagnostic.get_question', {
        session_id: sessionId,
        index: currentIndex + 1,
      });

      if (res && res.completed) {
        // Load final report
        const rep = await callLearnRpc('learn.diagnostic.report', { session_id: sessionId });
        if (rep && rep.success) {
          setSessionReport(rep.report);
        }
      } else if (res && res.question) {
        setCurrentIndex(res.index);
        setCurrentQuestion(res.question);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="learn-diagnostic-view">
      <div className="view-header">
        <div>
          <h2>Intelligent Knowledge Diagnosis</h2>
          <p>
            Short 8–10 question targeted diagnostic. Every question tests a distinct concept and maps wrong answers
            to common misconceptions.
          </p>
        </div>
      </div>

      {!sessionId && !sessionReport && (
        <div className="diagnostic-start-card">
          <h3>Begin Diagnostic Assessment</h3>
          <p>Select which course material to diagnose:</p>

          <div className="material-picker-row">
            <select
              value={selectedMaterialId}
              onChange={(e) => setSelectedMaterialId(e.target.value)}
              className="material-dropdown"
            >
              {materials.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.title} ({m.kind})
                </option>
              ))}
            </select>
            <button
              type="button"
              className="start-assessment-btn"
              onClick={handleStartSession}
              disabled={loading || !selectedMaterialId}
            >
              {loading ? 'Generating Assessment...' : 'Start Diagnostic Quiz (8–10 Qs)'}
            </button>
          </div>
        </div>
      )}

      {/* Active Question Card */}
      {sessionId && currentQuestion && !sessionReport && (
        <div className="diagnostic-active-card">
          {/* Progress Header */}
          <div className="diagnostic-progress-bar-wrap">
            <div className="progress-info">
              <span>Question {currentIndex + 1} of {totalQuestions}</span>
              <span className="grounding-status-tag">
                {currentQuestion.grounded ? 'Verified Grounded Question' : 'Syllabus Scoped Question'}
              </span>
            </div>
            <div className="progress-track">
              <div
                className="progress-fill"
                style={{ width: `${Math.round(((currentIndex + 1) / totalQuestions) * 100)}%` }}
              />
            </div>
          </div>

          {/* Question Stem */}
          <div className="question-stem-box">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
              <span className="grounding-status-tag">Conceptual Diagnostic</span>
              {currentQuestion.difficulty && (
                <span style={{ fontSize: '0.74rem', color: '#64748b', fontWeight: 600 }}>
                  Difficulty: {Math.round(currentQuestion.difficulty * 10)}/10
                </span>
              )}
            </div>
            <h3>{currentQuestion.stem}</h3>
          </div>

          {/* Options */}
          {!lastResult && (
            <div className="options-container">
              {currentQuestion.options.map((opt, i) => (
                <div
                  key={i}
                  className={`option-row ${selectedOption === opt ? 'selected' : ''}`}
                  onClick={() => setSelectedOption(opt)}
                >
                  <span className="option-letter">{String.fromCharCode(65 + i)}</span>
                  <span className="option-text">{opt}</span>
                </div>
              ))}
            </div>
          )}

          {/* Reasoning & Confidence Box */}
          {!lastResult && (
            <div className="student-input-aux">
              <div className="confidence-selector">
                <label>
                  <span>Select Confidence Level:</span>
                  <span style={{ fontSize: '0.75rem', fontWeight: 500, color: '#64748b' }}>
                    (Calibrates mastery score &amp; avoids penalty for honest uncertainty)
                  </span>
                </label>
                <div className="confidence-pills">
                  <button
                    type="button"
                    className={`conf-pill ${confidence === 1 ? 'active' : ''}`}
                    onClick={() => setConfidence(1)}
                  >
                    1 - Low (Educated Guess)
                  </button>
                  <button
                    type="button"
                    className={`conf-pill ${confidence === 2 ? 'active' : ''}`}
                    onClick={() => setConfidence(2)}
                  >
                    2 - Moderate (Fairly Sure)
                  </button>
                  <button
                    type="button"
                    className={`conf-pill ${confidence === 3 ? 'active' : ''}`}
                    onClick={() => setConfidence(3)}
                  >
                    3 - High (100% Certain)
                  </button>
                </div>
              </div>

              <div className="reasoning-box">
                <label>
                  <span>Explain Your Reasoning:</span>
                  <span style={{ fontSize: '0.75rem', fontWeight: 500, color: '#64748b' }}>
                    (Preppy verifies verbatim quotes to pinpoint exact mental model flaws)
                  </span>
                </label>
                <textarea
                  rows={3}
                  placeholder="Why did you pick this option? State the core principle, mental model, or equation you applied..."
                  value={reasoningText}
                  onChange={(e) => setReasoningText(e.target.value)}
                />
              </div>

              <button
                type="button"
                className="submit-answer-btn"
                onClick={handleSubmitAnswer}
                disabled={submitting || (currentQuestion.type === 'mcq' && !selectedOption)}
              >
                <Send size={18} />
                <span>{submitting ? 'Analyzing Mental Model...' : 'Submit Answer for Diagnostic'}</span>
              </button>
            </div>
          )}

          {/* Answer Feedback Banner */}
          {lastResult && (
            <div className={`answer-feedback-banner ${lastResult.is_correct ? 'correct' : 'wrong'}`}>
              <div className="feedback-header">
                {lastResult.is_correct ? (
                  <CheckCircle2 size={24} className="text-success" />
                ) : (
                  <AlertTriangle size={24} className="text-danger" />
                )}
                <div>
                  <h4>{lastResult.is_correct ? 'Correct Answer!' : 'Conceptual Slip Detected'}</h4>
                  <p>
                    {lastResult.is_correct
                      ? 'Demonstrated understanding. Mastery updated.'
                      : 'Your answer triggered a candidate misconception pattern.'}
                  </p>
                </div>
                <MasteryBadge mastery={lastResult.new_mastery} band={lastResult.band} size="sm" />
              </div>

              <div className="feedback-actions">
                {!lastResult.is_correct && (
                  <button
                    type="button"
                    className="goto-tutor-btn"
                    onClick={() =>
                      onOpenTutorWithResult({
                        attempt_id: lastResult.attempt_id,
                        question_id: lastResult.question_id,
                        concept_id: lastResult.concept_id,
                        answer_text: selectedOption,
                        reasoning_text: reasoningText,
                        confidence: confidence,
                        distractor_misconception: lastResult.distractor_misconception,
                      })
                    }
                  >
                    <Sparkles size={16} />
                    <span>Explain Why in Misconception Tutor →</span>
                  </button>
                )}

                <button type="button" className="next-question-btn" onClick={handleNextQuestion}>
                  <span>Next Question</span>
                  <ArrowRight size={16} />
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Completed Session Report */}
      {sessionReport && (
        <div className="diagnostic-report-card">
          <div className="report-header">
            <CheckCircle2 size={36} className="text-success" />
            <div>
              <h3>Diagnostic Assessment Complete!</h3>
              <p>
                Answered {sessionReport.total_answered} questions with {Math.round(sessionReport.accuracy * 100)}% accuracy.
              </p>
            </div>
          </div>

          <div className="report-concept-table">
            <h4>Concept Mastery Breakdown</h4>
            {sessionReport.concept_results.map((c: any, idx: number) => (
              <div key={idx} className="report-concept-row">
                <span className="concept-name">{c.name}</span>
                <span className="attempts-count">{c.attempts} attempts</span>
                <MasteryBadge mastery={c.mastery} band={c.band} size="sm" />
              </div>
            ))}
          </div>

          <button
            type="button"
            className="restart-diagnostic-btn"
            onClick={() => {
              setSessionId(null);
              setSessionReport(null);
            }}
          >
            <RefreshCw size={16} />
            <span>Diagnose Another Topic</span>
          </button>
        </div>
      )}
    </div>
  );
};

