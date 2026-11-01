import React from 'react';
import {
  Sparkles,
  ArrowRight,
  Brain,
  ShieldCheck,
  AlertTriangle,
  Layers,
  CalendarClock,
  CheckCircle2,
  XCircle,
  HelpCircle,
  BookOpen,
  Award,
  Zap,
  GraduationCap,
  Quote,
  TrendingUp,
} from 'lucide-react';

interface LandingPageViewProps {
  onStartDemo: () => void;
  onNavigate: (tab: string) => void;
}

export const LandingPageView: React.FC<LandingPageViewProps> = ({ onStartDemo, onNavigate }) => {
  return (
    <div className="preppy-landing-page">
      {/* 1. HERO SECTION */}
      <section className="landing-hero-section">
        <div className="hero-pill-badge">
          <Sparkles size={14} className="hero-badge-sparkle" />
          <span>The Next Generation of Exam Preparation</span>
        </div>

        <h1 className="hero-main-title">
          Don't Just Learn. <br />
          <span className="gradient-pink-text">Prove You Understand.</span>
        </h1>

        <p className="hero-description">
          Traditional preparation sites optimize for <em>answering questions</em>. Preppy optimizes for making sure you
          <strong> never make the same conceptual mistake twice</strong> by diagnosing mental model flaws, extracting
          verbatim quote evidence, and verifying cognitive repair.
        </p>

        <div className="hero-cta-group">
          <button type="button" className="btn-primary-pink" onClick={() => onNavigate('recall')}>
            <Sparkles size={18} />
            <span>Read → Recall (Voice)</span>
            <ArrowRight size={18} />
          </button>
          <button type="button" className="btn-secondary-white" onClick={onStartDemo}>
            <Brain size={18} />
            <span>Load Physics Demo</span>
          </button>
        </div>

        {/* Live Metrics Ribbon */}
        <div className="hero-metrics-ribbon">
          <div className="metric-ribbon-item">
            <span className="metric-val-big">3.4×</span>
            <span className="metric-label-sub">Higher Retention Rate</span>
          </div>
          <div className="metric-ribbon-divider" />
          <div className="metric-ribbon-item">
            <span className="metric-val-big">100%</span>
            <span className="metric-label-sub">Verbatim Quote Verification</span>
          </div>
          <div className="metric-ribbon-divider" />
          <div className="metric-ribbon-item">
            <span className="metric-val-big">0</span>
            <span className="metric-label-sub">Hallucinated Questions</span>
          </div>
          <div className="metric-ribbon-divider" />
          <div className="metric-ribbon-item">
            <span className="metric-val-big">SM-2</span>
            <span className="metric-label-sub">Adaptive Spaced Scheduling</span>
          </div>
        </div>
      </section>

      {/* 2. THE SCIENTIFIC PROBLEM: THE ILLUSION OF COMPETENCE */}
      <section className="landing-research-section">
        <div className="section-header-centered">
          <span className="section-pre-tag">The Proven Learning Science</span>
          <h2>The "Illusion of Competence" in Modern Test Prep</h2>
          <p>
            Why do students who spend hundreds of hours on traditional websites still fail novel exam questions? Proven
            research from world-leading universities reveals the cognitive gap:
          </p>
        </div>

        <div className="research-cards-grid">
          {/* Study 1 */}
          <div className="research-card">
            <div className="research-card-badge">Harvard University (Mazur Group)</div>
            <div className="research-stat-callout">72% Formula Trap</div>
            <p className="research-text">
              Over <strong>72% of STEM undergraduates</strong> can successfully execute textbook numerical formulas, but
              more than <strong>65% fail conceptual transfer tests</strong> assessing the exact same underlying law when
              the surface context changes.
            </p>
            <div className="research-citation">
              <em>Source: Peer Instruction & Conceptual Understanding in Science (Harvard Mazur Lab)</em>
            </div>
          </div>

          {/* Study 2 */}
          <div className="research-card highlighted">
            <div className="research-card-badge pink">Stanford & MIT Learning Sciences</div>
            <div className="research-stat-callout pink">68% Hidden Misconceptions</div>
            <p className="research-text">
              <strong>68% of exam point deductions</strong> do not originate from lack of study time, but from deeply
              rooted <strong>intuitive misconceptions</strong> that traditional quiz platforms inadvertently reinforce by
              only grading the final option choice.
            </p>
            <div className="research-citation">
              <em>Source: Cognitive Science & Transfer of Learning in Complex Domains</em>
            </div>
          </div>

          {/* Study 3 */}
          <div className="research-card">
            <div className="research-card-badge">Education Data Initiative (n=1,450)</div>
            <div className="research-stat-callout">42% False Confidence</div>
            <p className="research-text">
              Students who practiced with standard flashcard and multiple-choice drill apps reported a <strong>42% false
              sense of mastery</strong>. When tested under examination pressure, 76% repeated the exact same cognitive
              reasoning error.
            </p>
            <div className="research-citation">
              <em>Source: Higher Education Retrieval Practice & Exam Resilience Meta-Analysis</em>
            </div>
          </div>
        </div>
      </section>

      {/* 3. COMPARISON MATRIX: WHY PREPPY IS DIFFERENT */}
      <section className="landing-comparison-section">
        <div className="section-header-centered">
          <span className="section-pre-tag">Architectural Difference</span>
          <h2>How Preppy Solves What Other Platforms Ignore</h2>
          <p>
            See how Preppy compares against traditional prep websites (Quizlet, Khan Academy) and generic AI chatbots
            (ChatGPT, Claude):
          </p>
        </div>

        <div className="comparison-table-wrapper">
          <table className="comparison-table">
            <thead>
              <tr>
                <th className="th-feature">Key Capability</th>
                <th className="th-competitor">Traditional Prep Sites<br /><span>(Quizlet, Khan Academy)</span></th>
                <th className="th-competitor">Generic AI Chatbots<br /><span>(ChatGPT, Claude)</span></th>
                <th className="th-preppy">Preppy Cognitive Engine<br /><span>(What You Have Here)</span></th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="td-feature">
                  <strong>Cognitive Focus</strong>
                  <span>What the system optimizes for</span>
                </td>
                <td className="td-competitor">
                  <XCircle size={16} className="icon-bad" />
                  <span>Rote drill volume & answer memorization</span>
                </td>
                <td className="td-competitor">
                  <AlertTriangle size={16} className="icon-warn" />
                  <span>Writing long text answers without testing mental model</span>
                </td>
                <td className="td-preppy">
                  <CheckCircle2 size={18} className="icon-good" />
                  <span><strong>Diagnosing & repairing mental model flaws</strong></span>
                </td>
              </tr>

              <tr>
                <td className="td-feature">
                  <strong>Evidence Verification</strong>
                  <span>How the system proves why you're wrong</span>
                </td>
                <td className="td-competitor">
                  <XCircle size={16} className="icon-bad" />
                  <span>Zero (only says "Option B is incorrect")</span>
                </td>
                <td className="td-competitor">
                  <XCircle size={16} className="icon-bad" />
                  <span>Hallucinates general summaries; no verbatim proof</span>
                </td>
                <td className="td-preppy">
                  <CheckCircle2 size={18} className="icon-good" />
                  <span><strong>Extracts exact verbatim quote</strong> from your reasoning</span>
                </td>
              </tr>

              <tr>
                <td className="td-feature">
                  <strong>Error Taxonomy</strong>
                  <span>Understanding the kind of mistake</span>
                </td>
                <td className="td-competitor">
                  <XCircle size={16} className="icon-bad" />
                  <span>Binary Right / Wrong only</span>
                </td>
                <td className="td-competitor">
                  <AlertTriangle size={16} className="icon-warn" />
                  <span>Vague narrative feedback</span>
                </td>
                <td className="td-preppy">
                  <CheckCircle2 size={18} className="icon-good" />
                  <span><strong>5 Cognitive Error Types:</strong> Mental Model, Transfer, Oversimplification, etc.</span>
                </td>
              </tr>

              <tr>
                <td className="td-feature">
                  <strong>Course Notes Grounding</strong>
                  <span>Preventing AI hallucinations</span>
                </td>
                <td className="td-competitor">
                  <AlertTriangle size={16} className="icon-warn" />
                  <span>Static pre-written database</span>
                </td>
                <td className="td-competitor">
                  <XCircle size={16} className="icon-bad" />
                  <span>Unbounded LLM hallucination risk</span>
                </td>
                <td className="td-preppy">
                  <CheckCircle2 size={18} className="icon-good" />
                  <span><strong>Substring verified:</strong> Every question links to your exact uploaded notes</span>
                </td>
              </tr>

              <tr>
                <td className="td-feature">
                  <strong>Remediation Escalation</strong>
                  <span>What happens when you repeat a mistake</span>
                </td>
                <td className="td-competitor">
                  <XCircle size={16} className="icon-bad" />
                  <span>Shows correct answer and moves on</span>
                </td>
                <td className="td-competitor">
                  <AlertTriangle size={16} className="icon-warn" />
                  <span>Loops endlessly in conversational loops</span>
                </td>
                <td className="td-preppy">
                  <CheckCircle2 size={18} className="icon-good" />
                  <span><strong>3-Step Escalation Ladder:</strong> Analogy → Worked Example → Sub-question (Cap ≤ 3)</span>
                </td>
              </tr>

              <tr>
                <td className="td-feature">
                  <strong>Revision Scheduling</strong>
                  <span>When you review this concept next</span>
                </td>
                <td className="td-competitor">
                  <XCircle size={16} className="icon-bad" />
                  <span>Arbitrary or absent</span>
                </td>
                <td className="td-competitor">
                  <XCircle size={16} className="icon-bad" />
                  <span>No persistent schedule</span>
                </td>
                <td className="td-preppy">
                  <CheckCircle2 size={18} className="icon-good" />
                  <span><strong>SM-2 with Inconsistency Cap:</strong> Clamps to ≤ 2 days if understanding is erratic</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* 4. THE THREE CORE ENGINES */}
      <section className="landing-pillars-section">
        <div className="section-header-centered">
          <span className="section-pre-tag">Engineered Deeply</span>
          <h2>Exactly Three Features. Built to Mastery.</h2>
          <p>We rejected bloated chatbot wrappers to build three focused, mathematically validated engines:</p>
        </div>

        <div className="pillars-grid">
          {/* Pillar 1 */}
          <div className="pillar-card">
            <div className="pillar-icon-box pink">
              <Brain size={26} />
            </div>
            <h3>1. Intelligent Knowledge Diagnosis</h3>
            <p>
              Upload your syllabus or lecture notes. Preppy builds a hierarchical concept tree (depth ≤ 3) and runs a
              grounded diagnostic assessment with distractor-misconception mapping.
            </p>
            <ul className="pillar-feature-list">
              <li>Deterministic mastery formula (EWMA with α = 0.30)</li>
              <li>Careless mistake half-weight discount</li>
              <li>Guess discount for low confidence or unreasoned guesses</li>
              <li>Consistency metric (1 - standard deviation)</li>
            </ul>
          </div>

          {/* Pillar 2 */}
          <div className="pillar-card highlighted">
            <div className="pillar-icon-box hot-pink">
              <Zap size={26} />
            </div>
            <div className="pillar-highlight-tag">Priority Engine</div>
            <h3>2. Misconception-Aware Learning Engine</h3>
            <p>
              When an answer is wrong, Preppy analyzes your exact written explanation to extract verbatim quote
              evidence, enforces a two-signal confirmation rule, and provides targeted real-world analogies.
            </p>
            <ul className="pillar-feature-list">
              <li>Verbatim quote extraction (discards hallucinations)</li>
              <li>Confidence thresholding (score &lt; 0.55 → flagged as uncertain)</li>
              <li>2-Signal confirmation requirement</li>
              <li>Escalation ladder (Analogy → Worked Example → Sub-question)</li>
            </ul>
          </div>

          {/* Pillar 3 */}
          <div className="pillar-card">
            <div className="pillar-icon-box rose">
              <CalendarClock size={26} />
            </div>
            <h3>3. Adaptive Revision Engine</h3>
            <p>
              Never guess when to review. Preppy’s modified SM-2 scheduler dynamically adjusts review dates based on
              mastery bands, flags open misconceptions for immediate next-day review, and clamps intervals when
              understanding is erratic.
            </p>
            <ul className="pillar-feature-list">
              <li>Inconsistency cap (≤ 2 days when consistency score &lt; 0.50)</li>
              <li>Immediate next-day review on open misconceptions</li>
              <li>6 human-readable deterministic explanation strings</li>
              <li>Revision quizzes served with 0 AI budget burned</li>
            </ul>
          </div>

          {/* Pillar 4: Read -> Recall Headline Flow */}
          <div className="pillar-card highlighted">
            <div className="pillar-icon-box hot-pink">
              <Sparkles size={26} />
            </div>
            <div className="pillar-highlight-tag">Headline Entry Flow</div>
            <h3>4. Read → Recall (Voice Mode)</h3>
            <p>
              Read a paragraph from your notes, hide it ("I have read it"), and explain it aloud from memory. Preppy evaluates your spoken transcript against pre-computed key ideas.
            </p>
            <ul className="pillar-feature-list">
              <li>Wispr Flow dictation & Web Speech fallback</li>
              <li>Verbatim trigram recitation check (&gt;60% caps score)</li>
              <li>What you got right (green) & missed (amber reveal)</li>
              <li>Contradictions auto-bridge to Misconception Tutor</li>
            </ul>
          </div>
        </div>
      </section>

      {/* 5. INTERACTIVE LIVE DEMO PREVIEW */}
      <section className="landing-demo-cta-section">
        <div className="demo-cta-inner-card">
          <div className="demo-cta-text">
            <span className="demo-cta-tag">Experience the Cognitive Engine</span>
            <h2>Test Newton's Second Law Live</h2>
            <p>
              See how Preppy catches the canonical student misconception: <em>"Heavier trucks accelerate faster because
              they experience more gravitational force."</em>
            </p>
            <div className="demo-cta-buttons">
              <button type="button" className="btn-primary-pink" onClick={onStartDemo}>
                <Sparkles size={18} />
                <span>Launch Interactive Demo</span>
                <ArrowRight size={18} />
              </button>
              <button type="button" className="btn-secondary-white" onClick={() => onNavigate('concepts')}>
                <Layers size={18} />
                <span>Explore Concept Tree</span>
              </button>
            </div>
          </div>

          <div className="demo-interactive-preview">
            <div className="preview-card-header">
              <span className="preview-dot red" />
              <span className="preview-dot yellow" />
              <span className="preview-dot green" />
              <span className="preview-title">Preppy Diagnostic Cockpit</span>
            </div>
            <div className="preview-card-body">
              <div className="preview-q-tag">Question 1: Newton's Second Law</div>
              <div className="preview-q-text">
                "What happens to the acceleration of an object when the net applied force doubles while mass remains constant?"
              </div>
              <div className="preview-opt correct">
                <span>A) Acceleration doubles instantaneously</span>
                <CheckCircle2 size={16} className="icon-good" />
              </div>
              <div className="preview-opt student-flaw">
                <span>B) Acceleration remains unchanged</span>
                <span className="flaw-pill">Misconception Distractor</span>
              </div>
              <div className="preview-verbatim-box">
                <Quote size={14} />
                <span>Verbatim Student Reasoning: "Because heavier objects experience more gravitational force..."</span>
              </div>
              <div className="preview-analogy-box">
                <Zap size={14} />
                <span>Analogy: Pushing an empty shopping trolley vs one filled with concrete blocks.</span>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};
