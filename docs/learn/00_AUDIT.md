 # Preppy Phase 1 Audit Report: Blinky Codebase Reality Check

**Branch:** `feature/preppy`  
**Date:** October 31, 2026  
**Auditor:** Antigravity Pairing Agent  

---

## 1. Real Entry Points

### Application Startup Flow
1. **Developer Script (`scripts/dev.ts`):**
   - Launched via `bun run dev` (or `bun scripts/dev.ts`).
   - Detects Docker daemon status (optional SearXNG).
   - Restores native Windows system cursor via Win32 FFI (`user32.dll::SystemParametersInfoW`).
   - Kills stale processes on ports `5173`, `9001`, `9002`, `8081`.
   - Spawns `bun tauri dev` (`common/src-tauri`).
2. **Tauri Host Configuration (`common/src-tauri/tauri.conf.json`):**
   - Identifier: `app.blinky.tutor`
   - Dev URL: `http://localhost:5173`
   - Configures three managed desktop windows:
     - `command`: `/command`, width 760, height 720, transparent, undecorated, alwaysOnTop.
     - `overlay`: `/overlay`, transparent, undecorated, fullscreen capture/highlight overlay.
     - `notebook`: `/notebook`, title "Blinky Knowledge Hub", width 1280, height 820, decorated, resizable, initially hidden (`visible: false`).
3. **Rust Entry Point (`common/src-tauri/src/main.rs` & `lib.rs`):**
   - `main.rs` invokes `blinky_lib::run()`.
   - `lib.rs` initializes plugins (`tauri_plugin_shell`, `tauri_plugin_global_shortcut`), registers 30+ IPC commands via `tauri::generate_handler!`, and creates a system tray with options to toggle the command bar or quit.
   - `open_notebook_window` (`lib.rs:462-471`) unminimizes, shows, and focuses the `"notebook"` webview window.
4. **Frontend Routing (`common/frontend/src/main.tsx`):**
   - Pathname-based router:
     ```tsx
     const route = window.location.pathname;
     // /overlay   -> <Overlay />
     // /command   -> <CommandBar />
     // /notebook  -> <NotebookView onClose={() => void closeNotebookWindow()} isStandalone={true} />
     // default    -> <App />
     ```
   - Routes can be added simply by checking `window.location.pathname` or embedding within the Knowledge Hub window.

---

## 2. Exact Frontend ↔ Backend IPC Path for Python Features

Blinky supports two IPC paths from React to Python:

### Path A: One-Shot Worker (`run_tutor`)
This is the pattern used by `NotebookView.tsx` (`callNotebookRpc`):
1. **React:** Calls `runTutor("[NOTEBOOK_RPC:action] " + JSON.stringify(params))` in `NotebookView.tsx:34-46`.
2. **Tauri IPC (`common/src-tauri/src/lib.rs:88-145`):** `run_tutor` command receives `TutorRequest`.
3. **Worker Spawner (`lib.rs:672-736`):** `run_python_worker` executes `common/python/main.py` via Python child process, piping the request JSON into `stdin`.
4. **Python Dispatch (`common/python/main.py:321-331`):**
   ```python
   if question.startswith("[NOTEBOOK_RPC:"):
       match = re.match(r"^\[NOTEBOOK_RPC:([^\]]+)\]\s*(.*)$", question, flags=re.DOTALL)
       if match:
           rpc_action = match.group(1).strip()
           params_str = match.group(2).strip()
           rpc_params = json.loads(params_str) if params_str else {}
           res = handle_notebook_rpc(rpc_action, rpc_params)
           return {"summary": json.dumps(res), "steps": [], "warnings": warnings}
   ```
5. **Worker Return:** Python prints JSON to `stdout`. Rust parses stdout and returns it to the React promise.

### Path B: Persistent Agent Daemon (`run_agent_query`)
1. **React:** Invokes `run_agent_query` with `{ query: "..." }`.
2. **Rust (`websocket.rs:821-866`):** `run_agent_query` assigns a request ID and calls `forward_query_to_daemon_collect`.
3. **Daemon:** Sends a line of JSON to a persistent running `common/python/agent_router.py` process via stdin and collects stdout lines matching the `requestId`.

### Data Contract Types
- `common/frontend/src/lib/types.ts`: TypeScript interfaces (`TutorResult`, `TutorStep`, `OcrItem`, `ChatMessage`).
- `common/src-tauri/src/lib.rs`: Rust serde structs (`TutorRequest`, `AgentQueryRequest`, `BlinkySettings`).

---

## 3. Notebook Hub Reality Check

| Component | Path | Status | Verification Notes |
|---|---|---|---|
| `notebook_manager.py` | `common/python/notebooks/notebook_manager.py` | **Implemented** | 140 lines. JSON store in `tmp/notebooks/notebooks_store.json`. Handles CRUD for notebooks, sources, and source activation. |
| `document_parser.py` | `common/python/notebooks/document_parser.py` | **Implemented** | 143 lines. Parses PDF (PyMuPDF `fitz` or `pypdf`), TXT, Markdown, HTML. Emits OKF block: `### SOURCE: {clean_name}\nType: {ext.upper()}\n\n{compact_text}`. Preserves page markers `--- Page {n} ---`. Pure functional, safe to call. |
| `okf_context_builder.py` | `common/python/notebooks/okf_context_builder.py` | **Implemented** | 68 lines. Wraps source text in `<context_source name="...">` tags, enforces 9000-char TPM guard, constructs prompt. |
| `vector_store.py` | `common/python/notebooks/vector_store.py` | **Implemented** | 292 lines. SQLite database at `tmp/notebooks/vector_store.db`. Stores 384-d float32 embeddings via FastEmbed, with fallback to term-frequency cosine similarity. |
| `NotebookView.tsx` | `common/frontend/src/NotebookView.tsx` | **Implemented** | 497 lines. 3-column UI: Sources panel (upload/toggle), Chat stream, and Reference panel. Communicates via `[NOTEBOOK_RPC:...` over `runTutor`. |

**Citation & Grounding Ability:**
`document_parser.py` extracts page headers (`--- Page {idx + 1} ---`) and clean text. The text preserves line structure, allowing exact substring matching for verifiable grounding spans (`source_span`).

---

## 4. Persistence Analysis

### Current Persistence Architecture
- **`.brain/ARTIFACTS/recipes/*.json`**: Staged and active automation workflow recipes (`lib.rs:246`).
- **`.brain/logs/vision/`**: Runtime vision logs (`metrics.py:13`).
- **`.env` (root)**: User provider keys, voice settings, and shortcuts (`lib.rs:567`).
- **`tmp/notebooks/notebooks_store.json`**: Notebook metadata and sources (`notebook_manager.py:12`).
- **`tmp/notebooks/vector_store.db`**: SQLite database for document chunk embeddings (`vector_store.py:86`).

### Recommendation for `learn.db`
- **Location:** `.brain/learn/learn.db` (with `BLINKY_LEARN_DB_PATH` environment override).
- **Justification:**
  1. `tmp/` is ephemeral and commonly purged by build scripts (`cargo clean`, `dev:clean`). Student diagnostic records, mastery metrics, and revision schedules must survive restarts and cleans.
  2. `.brain` is already part of Blinky's persistent data model and is ignored by git (`.gitignore` line 3).
  3. Storing it in `.brain/learn/learn.db` keeps all learning data strictly local, isolated, private, and additive.
  4. A dedicated `learn.db` prevents schema conflicts with `vector_store.db` and avoids locking issues.

---

## 5. AI Provider Abstraction Analysis

### Dispatch Interface
- Central dispatcher: `common/python/ai/client.py`
  - `ask_text_model(prompt: str, max_tokens: int = 300) -> dict[str, Any]`
  - `ask_model(prompt: str, screenshot_path: Path) -> dict[str, Any]`
  - `get_provider_label() -> str`
- Provider resolution: `_resolve_provider()` checks `BLINKY_AI_PROVIDER` (`groq`, `gemini`, `mimo`, `deepseek`, `ollama`, `custom`).
- If no provider is configured, it falls back to `"ollama"`. If Ollama is unreachable, `requests` throws a connection/timeout exception.

### Capabilities Matrix
| Provider | System Prompts | Structured / JSON Mode | Streaming | Timeouts | Missing Key Behavior |
|---|---|---|---|---|---|
| **Ollama** (`ollama_client.py`) | Supported in prompt format | `format="json"` sent to `/api/generate` | Disabled (`stream: False`) | Configurable via `BLINKY_OLLAMA_TIMEOUT` (default 35s) | Fails with `RuntimeError` if Ollama is not running locally |
| **Groq** (`groq_client.py`) | Via system role in chat completions | `_ensure_json_in_prompt` + OpenAI JSON format | Disabled | Handled with rate-limit backoff | Raises `RuntimeError: GROQ_API_KEY is required` |
| **Gemini** (`gemini_client.py`) | Via `google-genai` client | Text extraction + `_parse_json` | Disabled | 20s timeout in `test_attached_image_safety.py` | Falls back to secondary or raises |
| **DeepSeek** (`deepseek_client.py`) | Via prompt | Text JSON parsing | Disabled | Default HTTP timeout | Raises if `DEEPSEEK_API_KEY` is missing |

### Preppy Requirements for `llm.py`
Preppy will implement a dedicated `llm.py` wrapper that:
1. Reuses `client._resolve_provider()` and existing provider endpoints.
2. Injects system instructions and versioned prompts from `learn/prompts/*.md`.
3. Validates outputs against Pydantic schemas with up to 2 retries on malformed JSON.
4. Enforces a per-session call budget (default 40 calls).
5. Provides a clean "no provider connected" status without crashing, allowing all deterministic features (mastery, revision schedules, question bank) to remain 100% operational.

---

## 6. Validation Libraries

- **Python:** `pydantic` 2.13.4 and `pydantic-settings` 2.14.1 are installed in Python 3.11. Pydantic models will serve as the single source of truth in `common/python/learn/schemas.py`.
- **TypeScript:** The project does not currently use `zod`. Typed contracts are defined as native TypeScript interfaces in `common/frontend/src/lib/types.ts`. Preppy will define mirrored types in `common/frontend/src/learn/types.ts` and include a Python unit test ensuring schema synchronization.

---

## 7. Existing Design System

- **Fonts:** `Space Grotesk` (headings/body) and `Unbounded` (display badges), imported via Google Fonts.
- **Color Tokens (`common/frontend/src/styles.css`):**
  - `--bg-0: #0b0a0d` (deep void background)
  - `--bg-1: #140f13` (subtle warm dark panel)
  - `--panel: rgba(16, 12, 15, 0.78)`
  - `--panel-strong: rgba(23, 16, 20, 0.92)`
  - `--panel-border: rgba(255, 255, 255, 0.08)`
  - `--text-strong: #f8f1f2`
  - `--text-muted: #b9aeb4`
  - `--accent: #ff6e5f` (Blinky orange/coral)
  - `--accent-strong: #ff8b6a`
  - `--accent-dim: rgba(255, 110, 95, 0.18)`
  - `--accent-glow: rgba(255, 110, 95, 0.45)`
- **Styling Architecture:** Plain CSS with glassmorphic backdrop filters (`backdrop-filter: blur(16px)`), subtle radial background gradients, and accessible high-contrast text.
- **Icons:** `lucide-react` (installed; `Zap`, `BookOpen`, `Sparkles`, `Brain`, `CheckCircle`, etc.).
- **Markdown:** `react-markdown` + `remark-gfm` (installed and used in `NotebookView.tsx`).

---

## 8. Existing Tests & Baseline Results (Measured Live)

The baseline test commands specified in §11 were executed directly on this machine:

1. **`bun run typecheck`**
   - Command: `bun run typecheck` (`tsc -p common/frontend/tsconfig.json --noEmit`)
   - **Result:** **PASS** (0 errors).
2. **`bun test common/frontend/tests`**
   - Command: `bun test common/frontend/tests`
   - **Result:** **65 passed, 1 failed** (66 tests in 6 files).
   - **Pre-existing Failure:** `(fail) getHighlightSteps > highlights only the next matched step in a workflow` in `common\frontend\tests\guidance.test.ts:136:38`.
3. **`python -m compileall -q common/python linux/python windows/python python`**
   - Command: `python -m compileall -q common/python linux/python windows/python python`
   - **Result:** **PASS** (0 compilation errors).
4. **`python -m pytest common/python/tests -q`**
   - Command: `python -m pytest common/python/tests -q`
   - **Result:** **479 passed, 30 failed, 22 skipped, 34 subtests passed** in 269.75s.
   - **Failure Analysis:** Pre-existing failures stem from environment differences documented in `local-docs/TESTING.md`:
     - Missing `fastembed` causing `test_semantic_synonym_search` to fail in `test_vector_store.py`.
     - `test_run_trim_execution` failing due to missing system `ffmpeg`.
     - `google.genai` mock structure mismatch in `test_attached_image_safety.py`.
     - Linux-specific actuator and CUA transport tests running on Windows.
5. **`cargo test --locked --manifest-path common/src-tauri/Cargo.toml`**
   - **Result:** Cargo is not installed on this host environment (`where.exe cargo` returned not found), and `common/python_runtime/Python313` is not bundled in the repo as documented in `local-docs/TESTING.md`.
6. **`bun test common/mobile/tests`**
   - Command: `bun test common/mobile/tests`
   - **Result:** **PASS** (55 passed, 0 failed in 10 files).

*All pre-existing test results are documented as the initial baseline; no new failures will be introduced.*

---

## 9. Discrepancies Between Docs and Code

1. **Rust `blinky-agent` vs Python Architecture:** The root `README.md` documents a pure-Rust multi-provider agent with an embedded SQLite vector store. In reality, `common/src-tauri/src/websocket.rs` gates the native agent behind `BLINKY_USE_NATIVE_AGENT=1` (which is unset by default), and the production app delegates all queries to Python via `run_python_worker` or the `agent_router.py` daemon.
2. **`sqlite-vec` Claim:** Documentation mentions `sqlite-vec` for embeddings. In reality, `common/python/notebooks/vector_store.py` uses standard library `sqlite3` storing raw float32 BLOBs and computes cosine similarity in Python numpy.
3. **Notebook Hub Status:** `docs/OKF.md` described an implementation plan, but the Notebook Hub is already fully implemented (`NotebookView.tsx`, `notebook_manager.py`, `document_parser.py`, and `okf_context_builder.py`).
4. **Dev Dependencies:** `windows/requirements.txt` excludes `pytest`, but `common/python/tests` requires `pytest` and `playwright`.

---

## 10. Concrete Integration Plan

### Non-Invasive Coupling Strategy
To maintain absolute stability and respect the coupling hotspots identified in §1 (`common/python/main.py::run`, `CommandBar.tsx`, `lib.rs`):
1. **Zero Logic in Hotspots:**
   - Add only a 6-line isolated dispatch intercept in `common/python/main.py` right beside `[NOTEBOOK_RPC:`:
     ```python
     if question.startswith("[LEARN_RPC:"):
         match = re.match(r"^\[LEARN_RPC:([^\]]+)\]\s*(.*)$", question, flags=re.DOTALL)
         if match:
             rpc_action = match.group(1).strip()
             rpc_params = json.loads(match.group(2).strip()) if match.group(2).strip() else {}
             from learn.api import handle_learn_rpc
             res = handle_learn_rpc(rpc_action, rpc_params)
             return {"summary": json.dumps(res), "steps": [], "warnings": warnings}
     ```
   - All Preppy logic lives strictly in `common/python/learn/`.
2. **Frontend Integration:**
   - In `NotebookView.tsx`, add a workspace tab in the header:
     `[ 📚 Knowledge Hub ] [ 🎓 Preppy ]`
   - When Preppy is active, render `<LearnView onClose={onClose} />`.
   - In `main.tsx`, support `/learn` route as an alternate direct entry point.
   - All IPC communication goes through `runTutor('[LEARN_RPC:<action>] ...')`, requiring zero new ports and zero changes to Rust IPC.

### New Package Structure (`common/python/learn/`)
- `schemas.py`: Pydantic models for Concept, Question, Attempt, Misconception, Mastery, and Revision.
- `config.py`: Deterministic algorithm parameters ($\alpha$, weights, bands, SM-2 constants, call budget).
- `db.py`: SQLite connection manager, additive idempotent migrations, WAL mode.
- `ingest.py`: Functional document ingestion wrapper around `document_parser.py`.
- `concepts.py`: Concept hierarchy extraction, validation, and tree bounds.
- `questions.py`: Grounded diagnostic question generator with distractor mapping and substring span verification.
- `diagnosis.py`: Diagnostic session manager and answer capture.
- `mastery.py`: Purely deterministic mastery update formula, guess discount, transfer check, consistency score.
- `misconception.py`: Priority engine — deterministic evidence gathering, heuristic classification, LLM structured analysis, strict verbatim quote validation, and targeted remediation.
- `revision.py`: Deterministic SM-2-inspired spaced repetition engine with template-generated explanation strings.
- `llm.py`: Schema-constrained LLM client wrapper with retry and call-budget tracking.
- `api.py`: Central RPC dispatcher mapping `learn.<action>` to engine handlers.
- `prompts/`: Versioned prompt templates (`concept_extraction.md`, `question_generation.md`, `misconception_analysis.md`, `remediation.md`).
- `tests/`: Complete unit and integration test suite.

### New Frontend Module (`common/frontend/src/learn/`)
- `types.ts`: TypeScript contracts mirroring `schemas.py`.
- `LearnApi.ts`: Type-safe RPC caller.
- `LearnView.tsx`: Main workspace container matching Blinky dark glassmorphism.
- Views: Dashboard, Materials, Concept Map, Diagnostic, Tutor (Misconception-Aware), Revision Queue.

---

## Gate Approval Request
The audit proves that Preppy can be integrated **without modifying any coupling hotspots beyond a minimal, 6-line isolated dispatch intercept in `common/python/main.py`**, reusing Blinky's existing `runTutor` IPC transport.

Ready for Phase 2 upon human approval.

