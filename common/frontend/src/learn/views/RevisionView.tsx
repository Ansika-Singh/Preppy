import React, { useState, useEffect } from 'react';
import { CalendarClock, CheckCircle2, Play, BookOpen, Clock, AlertTriangle } from 'lucide-react';
import { RevisionItem } from '../types';
import { MasteryBadge } from '../components/MasteryBadge';
import { callLearnRpc } from '../LearnApi';

interface RevisionViewProps {
  onNavigate: (tab: string) => void;
}

export const RevisionView: React.FC<RevisionViewProps> = ({ onNavigate }) => {
  const [queue, setQueue] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  // Active quiz state
  const [quizActive, setQuizActive] = useState(false);
  const [quizItems, setQuizItems] = useState<any[]>([]);
  const [currentQuizIdx, setCurrentQuizIdx] = useState(0);
  const [selectedOpt, setSelectedOpt] = useState('');
  const [quizScore, setQuizScore] = useState(0);
  const [quizDone, setQuizDone] = useState(false);

  useEffect(() => {
    void loadQueue();
  }, []);

  const loadQueue = async () => {
    setLoading(true);
    try {
      const res = await callLearnRpc('learn.revision.queue', { max_items: 20 });
      if (res && res.success && res.queue) {
        setQueue(res.queue);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleStartQuiz = async () => {
    setLoading(true);
    try {
      const res = await callLearnRpc('learn.revision.start_quiz', { max_concepts: 5 });
      if (res && res.success && res.quiz && res.quiz.items && res.quiz.items.length > 0) {
        setQuizItems(res.quiz.items);
        setCurrentQuizIdx(0);
        setSelectedOpt('');
        setQuizScore(0);
        setQuizDone(false);
        setQuizActive(true);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleQuizSubmit = () => {
    const item = quizItems[currentQuizIdx];
    const isCorrect = selectedOpt.trim().toLowerCase() === item.question.correct_answer.trim().toLowerCase();
    if (isCorrect) {
      setQuizScore((prev) => prev + 1);
    }

    if (currentQuizIdx + 1 < quizItems.length) {
      setCurrentQuizIdx((prev) => prev + 1);
      setSelectedOpt('');
    } else {
      setQuizDone(true);
    }
  };

  const currentItem = quizItems[currentQuizIdx];

  return (
    <div className="learn-revision-view">
      <div className="view-header">
        <div>
          <h2>Adaptive Spaced Revision</h2>
          <p>
            Deterministic, explainable review scheduling based on the cognitive SM-2 algorithm. Every scheduled item
            shows you the exact mathematical and cognitive rule that scheduled it.
          </p>
        </div>
        {queue.length > 0 && !quizActive && (
          <button type="button" className="start-revision-btn" onClick={handleStartQuiz} disabled={loading}>
            <Play size={16} />
            <span>Start Revision Quiz ({queue.length} due)</span>
          </button>
        )}
      </div>

      {/* Active Revision Quiz Mode */}
      {quizActive && !quizDone && currentItem && (
        <div className="revision-quiz-card">
          <div className="quiz-top-bar">
            <span>Revision Item {currentQuizIdx + 1} of {quizItems.length}</span>
            <span className="quiz-concept-name">{currentItem.concept_name}</span>
          </div>

          <div className="quiz-reason-banner">
            <CalendarClock size={16} />
            <span>{currentItem.reason_text}</span>
          </div>

          <div className="quiz-stem">
            <h3>{currentItem.question.stem}</h3>
          </div>

          <div className="options-container">
            {currentItem.question.options.map((opt: string, i: number) => (
              <div
                key={i}
                className={`option-row ${selectedOpt === opt ? 'selected' : ''}`}
                onClick={() => setSelectedOpt(opt)}
              >
                <span className="option-letter">{String.fromCharCode(65 + i)}</span>
                <span className="option-text">{opt}</span>
              </div>
            ))}
          </div>

          <button
            type="button"
            className="submit-quiz-opt-btn"
            onClick={handleQuizSubmit}
            disabled={!selectedOpt}
          >
            {currentQuizIdx + 1 === quizItems.length ? 'Finish Quiz' : 'Next Question'}
          </button>
        </div>
      )}

      {/* Quiz Completed */}
      {quizActive && quizDone && (
        <div className="quiz-done-card">
          <CheckCircle2 size={40} className="text-success" />
          <h3>Revision Quiz Completed!</h3>
          <p>
            Score: {quizScore} / {quizItems.length} correct. Spaced repetition intervals have been recalculated.
          </p>
          <button
            type="button"
            className="panel-cta-btn"
            onClick={() => {
              setQuizActive(false);
              void loadQueue();
            }}
          >
            Return to Revision Queue
          </button>
        </div>
      )}

      {/* Due Queue List */}
      {!quizActive && (
        <div className="revision-queue-container">
          <h3>Due Concepts ({queue.length})</h3>

          {queue.length === 0 ? (
            <div className="queue-empty">
              <CheckCircle2 size={36} className="text-success" />
              <h4>All Caught Up!</h4>
              <p>No revision items are due right now. Take a diagnostic to test your knowledge on new chapters.</p>
              <button
                type="button"
                className="panel-cta-btn"
                onClick={() => onNavigate('diagnostic')}
              >
                Start Diagnostic Quiz
              </button>
            </div>
          ) : (
            <div className="queue-items-list">
              {queue.map(({ item, concept, mastery }: any, idx: number) => (
                <div key={idx} className="revision-row-card">
                  <div className="revision-row-main">
                    <div className="revision-concept-meta">
                      <span className="rev-name">{concept ? concept.name : item.concept_id}</span>
                      <span className="rev-interval">Next Interval: {item.interval_days} day(s) · Ease: {item.ease}</span>
                    </div>
                    <p className="rev-reason-text">"{item.reason_text}"</p>
                  </div>
                  <div className="revision-row-badge">
                    <MasteryBadge
                      mastery={mastery ? mastery.mastery : 0.5}
                      band={mastery ? mastery.band : 'insufficient_evidence'}
                      size="sm"
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

