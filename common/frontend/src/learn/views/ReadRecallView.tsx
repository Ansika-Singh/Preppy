import React, { useState, useEffect, useRef } from 'react';
import {
  Mic,
  MicOff,
  Eye,
  EyeOff,
  Clock,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  ArrowRight,
  RotateCcw,
  BookOpen,
  Volume2,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
} from 'lucide-react';
import { Chunk, RecallAnalysisResult, RecallSession } from '../types';
import { callLearnRpc } from '../LearnApi';

interface ReadRecallViewProps {
  onNavigate: (tab: string) => void;
  onOpenTutorWithResult?: (attemptResult: any) => void;
}

export const ReadRecallView: React.FC<ReadRecallViewProps> = ({
  onNavigate,
  onOpenTutorWithResult,
}) => {
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [currentChunkIdx, setCurrentChunkIdx] = useState<number>(0);
  const [currentChunk, setCurrentChunk] = useState<Chunk | null>(null);
  const [conceptName, setConceptName] = useState<string>('');
  const [loadingChunks, setLoadingChunks] = useState<boolean>(true);

  // Flow Phases: 'read' | 'recall' | 'result'
  const [phase, setPhase] = useState<'read' | 'recall' | 'result'>('read');

  // Reading Timer
  const [readSeconds, setReadSeconds] = useState<number>(0);
  const [isReadingTimerActive, setIsReadingTimerActive] = useState<boolean>(false);

  // Recall Phase State
  const [transcript, setTranscript] = useState<string>('');
  const [peeked, setPeeked] = useState<boolean>(false);
  const [isPeekingOpen, setIsPeekingOpen] = useState<boolean>(false);
  const [inputMethod, setInputMethod] = useState<string>('wispr_flow_dictation');

  // Speech Recognition (Fallback)
  const [isListening, setIsListening] = useState<boolean>(false);
  const recognitionRef = useRef<any>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Analysis Result
  const [analyzing, setAnalyzing] = useState<boolean>(false);
  const [analysisResult, setAnalysisResult] = useState<RecallAnalysisResult | null>(null);
  const [activeSession, setActiveSession] = useState<RecallSession | null>(null);

  // Revealed missed quotes toggle
  const [revealedQuotes, setRevealedQuotes] = useState<Record<string, boolean>>({});

  // 1. Load Chunks
  useEffect(() => {
    void loadChunks();
  }, []);

  const loadChunks = async (preferredChunkId?: string) => {
    setLoadingChunks(true);
    try {
      const res = await callLearnRpc('learn.recall.chunks_list', {});
      if (res && res.success && res.chunks && res.chunks.length > 0) {
        setChunks(res.chunks);
        const idx = preferredChunkId
          ? res.chunks.findIndex((c: Chunk) => c.id === preferredChunkId)
          : 0;
        const validIdx = idx >= 0 ? idx : 0;
        setCurrentChunkIdx(validIdx);
        await selectChunk(res.chunks[validIdx].id);
      } else {
        setChunks([]);
        setCurrentChunk(null);
      }
    } catch (err) {
      console.error('Error loading recall chunks:', err);
    } finally {
      setLoadingChunks(false);
    }
  };

  const selectChunk = async (chunkId: string) => {
    try {
      const res = await callLearnRpc('learn.recall.chunk_get', { chunk_id: chunkId });
      if (res && res.success && res.chunk) {
        setCurrentChunk(res.chunk);
        setConceptName(res.concept?.name || 'Core Mechanics');
        resetFlow();
      }
    } catch (err) {
      console.error('Error selecting chunk:', err);
    }
  };

  const resetFlow = () => {
    setPhase('read');
    setReadSeconds(0);
    setIsReadingTimerActive(true);
    setTranscript('');
    setPeeked(false);
    setIsPeekingOpen(false);
    setInputMethod('wispr_flow_dictation');
    setAnalysisResult(null);
    setActiveSession(null);
    setRevealedQuotes({});
    stopSpeechRecognition();
  };

  // 2. Reading Timer
  useEffect(() => {
    let timer: any = null;
    if (isReadingTimerActive && phase === 'read') {
      timer = setInterval(() => {
        setReadSeconds((s) => s + 1);
      }, 1000);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [isReadingTimerActive, phase]);

  const formatTimer = (totalSeconds: number) => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // 3. Flow Transitions
  const handleFinishedReading = () => {
    setIsReadingTimerActive(false);
    setPhase('recall');
    setTimeout(() => {
      textareaRef.current?.focus();
    }, 150);
  };

  const handleTogglePeek = () => {
    setPeeked(true);
    setIsPeekingOpen((prev) => !prev);
  };

  // 4. Web Speech API (Fallback)
  const toggleSpeechRecognition = () => {
    if (isListening) {
      stopSpeechRecognition();
    } else {
      startSpeechRecognition();
    }
  };

  const startSpeechRecognition = () => {
    const SpeechRec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRec) {
      alert('Browser speech recognition is not supported in this browser. Please use Wispr Flow dictation or type your explanation.');
      return;
    }

    try {
      const recognition = new SpeechRec();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'en-US';

      recognition.onstart = () => {
        setIsListening(true);
        setInputMethod('browser_speech');
      };

      recognition.onresult = (event: any) => {
        let interimText = '';
        let finalText = '';

        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            finalText += event.results[i][0].transcript;
          } else {
            interimText += event.results[i][0].transcript;
          }
        }

        const combined = finalText || interimText;
        if (combined) {
          setTranscript((prev) => {
            const separator = prev && !prev.endsWith(' ') ? ' ' : '';
            return prev + separator + combined;
          });
        }
      };

      recognition.onerror = (event: any) => {
        console.warn('Speech recognition error:', event.error);
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (e) {
      console.error('Failed to start speech recognition:', e);
      setIsListening(false);
    }
  };

  const stopSpeechRecognition = () => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // ignore
      }
      recognitionRef.current = null;
    }
    setIsListening(false);
  };

  // 5. Submit for Analysis
  const handleAnalyzeRecall = async () => {
    if (!currentChunk || !transcript.trim()) return;
    stopSpeechRecognition();
    setAnalyzing(true);
    try {
      const res = await callLearnRpc('learn.recall.analyze', {
        chunk_id: currentChunk.id,
        transcript_raw: transcript,
        transcript_final: transcript,
        peeked,
        read_ms: readSeconds * 1000,
        input_method: inputMethod,
      });

      if (res && res.success && res.analysis) {
        setAnalysisResult(res.analysis);
        setActiveSession(res.session);
        setPhase('result');
      } else {
        alert(res?.error || 'Analysis failed. Please try again.');
      }
    } catch (err: any) {
      alert(err?.message || 'Error communicating with analysis engine.');
    } finally {
      setAnalyzing(false);
    }
  };

  const wordCount = transcript.trim().split(/\s+/).filter(Boolean).length;
  const isTooShort = wordCount < 15;

  // 6. Navigation between paragraphs
  const handlePrevChunk = () => {
    if (currentChunkIdx > 0) {
      const nextIdx = currentChunkIdx - 1;
      setCurrentChunkIdx(nextIdx);
      void selectChunk(chunks[nextIdx].id);
    }
  };

  const handleNextChunk = () => {
    if (currentChunkIdx < chunks.length - 1) {
      const nextIdx = currentChunkIdx + 1;
      setCurrentChunkIdx(nextIdx);
      void selectChunk(chunks[nextIdx].id);
    }
  };

  const toggleRevealQuote = (kiId: string) => {
    setRevealedQuotes((prev) => ({ ...prev, [kiId]: !prev[kiId] }));
  };

  // Empty state when no notes or chunks are loaded
  if (loadingChunks) {
    return (
      <div className="recall-view-container">
        <div className="recall-loading-card">
          <Sparkles className="animate-spin text-pink-500" size={32} />
          <h3>Preparing Reading Chunks...</h3>
          <p>Extracting atomic paragraph units and verifying factual grounding.</p>
        </div>
      </div>
    );
  }

  if (!currentChunk || chunks.length === 0) {
    return (
      <div className="recall-view-container">
        <div className="recall-empty-card">
          <BookOpen size={48} className="text-pink-400 mb-3" />
          <h2 className="text-xl font-bold mb-2">No Study Paragraphs Available</h2>
          <p className="text-slate-600 mb-4 max-w-md">
            Read → Recall analyzes paragraphs from your notes. Click below to load the Engineering Physics sample notes or upload your own textbook excerpts.
          </p>
          <div className="flex gap-3">
            <button
              className="btn-primary"
              onClick={async () => {
                setLoadingChunks(true);
                await callLearnRpc('learn.sample.load', {});
                await loadChunks();
              }}
            >
              <Sparkles size={16} />
              <span>Load Physics Demo</span>
            </button>
            <button className="btn-secondary" onClick={() => onNavigate('materials')}>
              <span>Upload Notes</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="recall-view-container">
      {/* Top Header & Paragraph Navigator */}
      <div className="recall-header-banner">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="recall-headline-badge">Headline Flow</span>
            <span className="recall-concept-pill">{conceptName}</span>
          </div>
          <h1 className="recall-main-title">Read → Recall (Voice)</h1>
          <p className="recall-subtitle">
            Read a paragraph from your notes, hide it, and explain it aloud in your own words. Preppy proves whether you truly understand.
          </p>
        </div>

        {/* Chunk Selector */}
        <div className="recall-chunk-nav">
          <button
            className="btn-icon-nav"
            onClick={handlePrevChunk}
            disabled={currentChunkIdx === 0}
            title="Previous paragraph"
          >
            <ChevronLeft size={18} />
          </button>
          <span className="recall-chunk-counter">
            Paragraph <strong>{currentChunkIdx + 1}</strong> of {chunks.length}
          </span>
          <button
            className="btn-icon-nav"
            onClick={handleNextChunk}
            disabled={currentChunkIdx === chunks.length - 1}
            title="Next paragraph"
          >
            <ChevronRight size={18} />
          </button>
        </div>
      </div>

      {/* ===================================================================== */}
      {/* PHASE 1: READ PHASE                                                   */}
      {/* ===================================================================== */}
      {phase === 'read' && (
        <div className="recall-read-card">
          <div className="recall-card-header">
            <div className="flex items-center gap-2">
              <span className="recall-phase-step">Step 1</span>
              <h2 className="recall-card-title">Study Paragraph</h2>
            </div>
            <div className="recall-timer-pill" title="Elapsed reading time">
              <Clock size={14} />
              <span>{formatTimer(readSeconds)} elapsed</span>
            </div>
          </div>

          <div className="recall-paragraph-box">
            <p>{currentChunk.text}</p>
          </div>

          <div className="recall-read-footer">
            <div className="recall-footer-hint">
              <ShieldCheck size={16} className="text-pink-500" />
              <span>Key ideas are pre-computed in the background. Take your time to understand the core mechanism.</span>
            </div>
            <button className="btn-read-finish" onClick={handleFinishedReading}>
              <span>I have read it</span>
              <ArrowRight size={18} />
            </button>
          </div>
        </div>
      )}

      {/* ===================================================================== */}
      {/* PHASE 2: RECALL (VOICE / DICTATION) PHASE                             */}
      {/* ===================================================================== */}
      {phase === 'recall' && (
        <div className="recall-box-card">
          <div className="recall-card-header">
            <div className="flex items-center gap-2">
              <span className="recall-phase-step">Step 2</span>
              <h2 className="recall-card-title">Explain From Memory</h2>
            </div>
            <div className="flex items-center gap-2">
              <button
                className={`btn-peek ${peeked ? 'peeked' : ''}`}
                onClick={handleTogglePeek}
                title="Revealing the paragraph discounts coverage score to max 70%"
              >
                {isPeekingOpen ? <EyeOff size={14} /> : <Eye size={14} />}
                <span>{isPeekingOpen ? 'Hide Text' : 'Peek at paragraph'}</span>
              </button>
            </div>
          </div>

          {/* Peek Dropdown Banner */}
          {isPeekingOpen && (
            <div className="recall-peek-container">
              <div className="recall-peek-warning">
                <AlertTriangle size={14} />
                <span>Peeked session: coverage score credit is capped at 70%.</span>
              </div>
              <p className="recall-peek-text">{currentChunk.text}</p>
            </div>
          )}

          {/* Prompt banner */}
          <div className="recall-prompt-banner">
            <p>
              <em>“Explain what you just read, in your own words, as if teaching a friend.”</em>
            </p>
          </div>

          {/* Wispr Flow & Voice Integration Banner */}
          <div className="recall-wispr-instruction">
            <div className="flex items-center gap-2">
              <span className="wispr-indicator-dot" />
              <strong className="text-slate-800">Wispr Flow Dictation:</strong>
              <span className="text-slate-600">Click the box below, hold your Wispr Flow hotkey, and speak freely.</span>
            </div>
            <button
              className={`btn-mic-toggle ${isListening ? 'listening' : ''}`}
              onClick={toggleSpeechRecognition}
              title="Browser Web Speech fallback"
            >
              {isListening ? <MicOff size={14} /> : <Mic size={14} />}
              <span>{isListening ? 'Stop Mic' : 'Browser Mic'}</span>
            </button>
          </div>

          {/* The Large, Accessible Recall Textarea */}
          <div className="recall-textarea-wrapper">
            <textarea
              ref={textareaRef}
              className="recall-textarea"
              rows={7}
              placeholder="Start speaking or typing your explanation here..."
              value={transcript}
              onChange={(e) => {
                setTranscript(e.target.value);
                if (!isListening) {
                  setInputMethod('wispr_flow_dictation');
                }
              }}
              spellCheck={false}
              autoFocus
            />
          </div>

          {/* Bottom Bar with word counter and submit */}
          <div className="recall-submit-row">
            <div className="recall-word-counter">
              <span className={isTooShort ? 'text-amber-600 font-semibold' : 'text-slate-600'}>
                {wordCount} words
              </span>
              {isTooShort && (
                <span className="text-xs text-amber-600 ml-2">(minimum 15 words to evaluate)</span>
              )}
            </div>

            <div className="flex items-center gap-3">
              <button
                className="btn-secondary"
                onClick={() => {
                  setPhase('read');
                  setIsReadingTimerActive(true);
                }}
              >
                <RotateCcw size={14} />
                <span>Re-read</span>
              </button>
              <button
                className="btn-analyze-submit"
                onClick={handleAnalyzeRecall}
                disabled={isTooShort || analyzing}
              >
                {analyzing ? (
                  <>
                    <Sparkles size={16} className="animate-spin" />
                    <span>Analyzing explanation...</span>
                  </>
                ) : (
                  <>
                    <CheckCircle2 size={16} />
                    <span>Analyze my explanation</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ===================================================================== */}
      {/* PHASE 3: ANALYSIS RESULTS PHASE                                       */}
      {/* ===================================================================== */}
      {phase === 'result' && analysisResult && (
        <div className="recall-result-container">
          {/* Top Score Banner */}
          <div className="recall-score-card">
            <div className="recall-score-header">
              <div>
                <span className="recall-score-label">Coverage Score</span>
                <div className="flex items-baseline gap-2">
                  <span className="recall-score-number">
                    {Math.round(analysisResult.coverage_score * 100)}%
                  </span>
                  <span className="text-slate-500 text-sm">understanding verified</span>
                </div>
              </div>

              {/* Status Badges */}
              <div className="flex flex-col gap-1 items-end">
                {analysisResult.peeked && (
                  <span className="badge-discount peeked" title="Capped at 70% due to peek">
                    Peeked (Discounted cap: 70%)
                  </span>
                )}
                {analysisResult.is_recited && (
                  <span className="badge-discount recited" title="Capped at 50% due to verbatim recitation">
                    Mostly recited verbatim (Discounted cap: 50%)
                  </span>
                )}
                {analysisResult.coverage_score >= 0.70 && !analysisResult.is_recited && (
                  <span className="badge-success">
                    <CheckCircle2 size={12} /> Solid Conceptual Mastery
                  </span>
                )}
              </div>
            </div>

            {/* Cognitive Summary */}
            <p className="recall-summary-quote">{analysisResult.summary}</p>
          </div>

          {/* Three Categorized Concept Cards (§5.2) */}
          <div className="recall-breakdown-grid">
            {/* 1. What You Got Right (Green) */}
            <div className="recall-card-section right">
              <div className="recall-section-header">
                <CheckCircle2 size={18} className="text-emerald-600" />
                <h3>What You Got Right</h3>
              </div>
              <div className="recall-items-list">
                {analysisResult.evaluations
                  .filter((e) => e.status === 'covered' || e.status === 'partially_covered')
                  .map((ev) => (
                    <div key={ev.key_idea_id} className="recall-item covered">
                      <div className="flex items-start justify-between gap-2">
                        <strong className="text-sm text-slate-800">{ev.claim}</strong>
                        <span className={`pill-status ${ev.status}`}>
                          {ev.status === 'covered' ? 'Full Match' : 'Partial Match'}
                        </span>
                      </div>
                      {ev.student_quote && (
                        <div className="recall-quote-box">
                          <span className="quote-label">Your words:</span>
                          <span className="quote-text">“{ev.student_quote}”</span>
                        </div>
                      )}
                      {ev.feedback && <p className="text-xs text-slate-600 mt-1">{ev.feedback}</p>}
                    </div>
                  ))}
                {analysisResult.evaluations.filter((e) => e.status === 'covered' || e.status === 'partially_covered').length === 0 && (
                  <p className="text-xs text-slate-500 italic p-2">None of the core claims were clearly identified in this recall.</p>
                )}
              </div>
            </div>

            {/* 2. What You Missed (Amber) */}
            <div className="recall-card-section missed">
              <div className="recall-section-header">
                <AlertTriangle size={18} className="text-amber-600" />
                <h3>What You Missed</h3>
              </div>
              <div className="recall-items-list">
                {analysisResult.evaluations
                  .filter((e) => e.status === 'missed')
                  .map((ev) => (
                    <div key={ev.key_idea_id} className="recall-item missed">
                      <div className="flex items-start justify-between gap-2">
                        <strong className="text-sm text-slate-800">{ev.claim}</strong>
                        <button
                          className="btn-reveal-notes"
                          onClick={() => toggleRevealQuote(ev.key_idea_id)}
                        >
                          {revealedQuotes[ev.key_idea_id] ? 'Hide' : 'Reveal Notes'}
                        </button>
                      </div>
                      {revealedQuotes[ev.key_idea_id] && ev.notes_quote && (
                        <div className="recall-reveal-notes-box">
                          <span className="notes-label">From your notes:</span>
                          <span className="notes-text">“{ev.notes_quote}”</span>
                        </div>
                      )}
                    </div>
                  ))}
                {analysisResult.evaluations.filter((e) => e.status === 'missed').length === 0 && (
                  <p className="text-xs text-emerald-600 italic p-2">Excellent! You didn't miss any major ideas.</p>
                )}
              </div>
            </div>

            {/* 3. Misconceptions Detected (Purple / Red) */}
            <div className="recall-card-section misconception">
              <div className="recall-section-header">
                <HelpCircle size={18} className="text-purple-600" />
                <h3>Misconceptions Detected</h3>
              </div>
              <div className="recall-items-list">
                {analysisResult.evaluations
                  .filter((e) => e.status === 'contradicted')
                  .map((ev) => (
                    <div key={ev.key_idea_id} className="recall-item contradicted">
                      <strong className="text-sm text-purple-900 block mb-1">
                        Contradicted: {ev.claim}
                      </strong>
                      {ev.student_quote && (
                        <div className="recall-quote-box error">
                          <span className="quote-label">Your words contradicted notes:</span>
                          <span className="quote-text">“{ev.student_quote}”</span>
                        </div>
                      )}
                      <p className="text-xs text-purple-800 mt-2">
                        This conceptual discrepancy has been routed to the Misconception Engine for targeted remediation.
                      </p>
                      <button
                        className="btn-goto-tutor"
                        onClick={() => {
                          if (onOpenTutorWithResult && activeSession) {
                            onOpenTutorWithResult(activeSession);
                          } else {
                            onNavigate('tutor');
                          }
                        }}
                      >
                        <span>Fix in Misconception Tutor →</span>
                      </button>
                    </div>
                  ))}
                {analysisResult.evaluations.filter((e) => e.status === 'contradicted').length === 0 && (
                  <p className="text-xs text-slate-500 italic p-2">No direct conceptual contradictions detected in your recall.</p>
                )}
              </div>
            </div>
          </div>

          {/* Action Footer */}
          <div className="recall-result-actions">
            <button className="btn-secondary" onClick={resetFlow}>
              <RotateCcw size={16} />
              <span>Retry this Paragraph</span>
            </button>
            {currentChunkIdx < chunks.length - 1 && (
              <button className="btn-primary" onClick={handleNextChunk}>
                <span>Next Paragraph</span>
                <ArrowRight size={16} />
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

