# Preppy Cognitive Engine — Architectural & Engineering Report

**Tagline:** *Don't just learn. Prove you understand.*

---

## 1. Executive Summary

Preppy is a from-scratch web application designed to prove whether students truly understand what they study. Unlike standard drill platforms (which test surface memorization) or generic chatbot wrappers (which produce unverified conversational prose), Preppy is an explainable cognitive diagnostic system with three core engines and one headline voice-entry flow:

1. **Intelligent Knowledge Diagnosis**: Hierarchical concept map extraction from notes/syllabi with EWMA mastery scoring ($\alpha = 0.30 \times \text{difficulty}$), guess discounting for unreasoned or low-confidence answers, and careless mistake down-weighting.
2. **Misconception-Aware Learning Engine (*Highest Priority*)**: Dissects *why* a student's answer or explanation is flawed, extracts exact verbatim quote evidence from their words, enforces a 2-signal confirmation rule, presents grounded real-world analogies, and executes a 3-tier remediation escalation ladder with a loop cap of 3.
3. **Adaptive Spaced Revision Engine**: Modified SM-2 cognitive spaced repetition scheduling. Features an inconsistency clamp ($\le 2$ days when consistency $< 0.50$), immediate next-day scheduling for open misconceptions, and human-readable, deterministic explanation strings generated purely in code with zero AI budget burned.
4. **Read → Recall (Voice) Headline Flow**: Students read paragraph-sized chunks (~80–220 words) of their notes with a calm elapsed reading timer, click **"I have read it"** to hide the text, and explain the concept aloud from memory. Supports Wispr Flow system-wide dictation, browser Web Speech API, and typed input. Analyses the transcript against pre-computed key ideas, checks for word-trigram verbatim recitation ($> 60\%$ triggers a discount cap of $0.50$), strictly enforces verbatim substring quote matching, and automatically routes conceptual contradictions directly into the Misconception Engine.

---

## 2. Dependency Audit & Justification

All dependencies utilize permissive licenses (MIT, Apache 2.0, or BSD):

| Dependency | License | Architectural Justification |
| :--- | :--- | :--- |
| `better-sqlite3` / `sqlite3` | MIT / Public Domain | Embedded, ACID-compliant local database storing concepts, chunks, attempts, mastery history, and recall sessions across restarts. |
| `pydantic` | MIT | Strict type safety, input validation, and structured LLM JSON schema constraints. |
| `pytest` / `pytest-asyncio` | MIT | Deterministic test runner for unit, integration, and algorithmic verification suites. |
| `react` / `react-dom` (v19) | MIT | Declarative component UI rendering for desktop and browser environments. |
| `vite` | MIT | Sub-second HMR frontend bundling and production asset minification. |
| `lucide-react` | MIT | Accessible, lightweight icon primitives for UI statuses and navigation. |
| `tailwindcss` | MIT | Responsive design tokens and layout styling. |

---

## 3. Strict Safety & Deterministic Guarantees

1. **Audio Storage Privacy**: Audio is **never recorded or stored to disk**. Only text transcripts are persisted in SQLite.
2. **Deterministic Substring Quote Verification**:
   - Every `student_quote` displayed in the UI is verified in code using `verify_exact_substring(quote, transcript)`. Hallucinated quotes that do not appear verbatim in the student's text are discarded.
   - Every `notes_quote` is verified as an exact substring of the uploaded study material.
3. **Prompt Injection Hygiene**: All untrusted student inputs (notes, answers, reasoning, spoken transcripts) are isolated within explicit delimiters (`<student_recall>`, `"""`) with explicit system instructions to treat them strictly as data, never as executable instructions.
4. **Zero-Crash Offline Fallback**: If no AI provider is configured or reachable, all deterministic features (knowledge trees, diagnostic quizzes, mastery calculations, spaced repetition queues, Read → Recall keyword evaluation, and sample data) operate with zero errors.

---

## 4. Verification Suite & Exact Command Outputs

### 4.1 Python Unit Test Suite (8 Suites, 49 Tests)

```powershell
pytest common/python/tests/test_learn_phase2.py common/python/tests/test_learn_phase3.py common/python/tests/test_learn_phase4.py common/python/tests/test_learn_phase5.py common/python/tests/test_learn_phase6.py common/python/tests/test_learn_recall.py common/python/tests/test_learn_schema_drift.py common/python/tests/test_learn_stdout.py
```

**Exact Output:**
```
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.2.0, pluggy-1.7.0
rootdir: C:\Users\ansik\Desktop\Preppy
plugins: anyio-4.13.0, asyncio-1.4.1
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 49 items

common\python\tests\test_learn_phase2.py ...........                     [ 22%]
common\python\tests\test_learn_phase3.py .......                         [ 36%]
common\python\tests\test_learn_phase4.py .........                       [ 55%]
common\python\tests\test_learn_phase5.py .....                           [ 65%]
common\python\tests\test_learn_phase6.py ........                        [ 81%]
common\python\tests\test_learn_recall.py .......                         [ 95%]
common\python\tests\test_learn_schema_drift.py .                         [ 97%]
common\python\tests\test_learn_stdout.py .                               [100%]

======================== 49 passed, 1 warning in 6.16s ========================
```

### 4.2 TypeScript Typecheck

```powershell
bun run typecheck
```

**Exact Output:**
```
$ tsc -p common/frontend/tsconfig.json --noEmit
(Exited with code 0 - No TypeScript compilation errors)
```

### 4.3 Production Vite Build

```powershell
bun x vite build --config common/frontend/vite.config.ts
```

**Exact Output:**
```
vite v8.0.14 building client environment for production...
✓ 2049 modules transformed.
rendering chunks...
computing gzip size...
common/frontend/dist/index.html                   0.47 kB │ gzip:   0.30 kB
common/frontend/dist/assets/index-BvP0dPUH.css  127.10 kB │ gzip:  21.95 kB
common/frontend/dist/assets/index-Cb7CIA6X.js   618.71 kB │ gzip: 179.23 kB
✓ built in 1.67s
```

### 4.4 End-to-End Daemon & RPC Bridge Verification

```powershell
python -c "import urllib.request, json; res = urllib.request.urlopen('http://127.0.0.1:5174/health').read().decode(); print('Bridge Health:', res)"
```

**Exact Output:**
```
Bridge Health: {"status": "ok", "app": "Preppy"}
```

