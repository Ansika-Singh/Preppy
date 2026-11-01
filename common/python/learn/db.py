from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from utils.logging import get_logger
from .config import get_db_path
from .schemas import (
    Concept,
    Material,
    MaterialKind,
    MisconceptionCandidate,
    MisconceptionRecord,
    Question,
    Attempt,
    Mastery,
    RevisionItem,
    SourceSpan,
    Chunk,
    ChunkKeyIdea,
    RecallSession,
    RecallAnalysisResult,
)

LOGGER = get_logger("blinky.learn.db")

CURRENT_SCHEMA_VERSION = 2


class LearnDB:
    """Thread-safe SQLite connection and repository for Preppy."""

    def __init__(self, db_path: Optional[str | Path] = None):
        raw_path = str(db_path) if db_path else str(get_db_path())
        self.raw_path = raw_path
        if raw_path == ":memory:" or raw_path.startswith("file:"):
            self.db_path = raw_path
            self._is_mem = True
        else:
            self.db_path = Path(raw_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._is_mem = False
        self.migrate()

    def get_connection(self) -> sqlite3.Connection:
        is_uri = str(self.db_path).startswith("file:")
        conn = sqlite3.connect(str(self.db_path), timeout=10.0, uri=is_uri)
        conn.row_factory = sqlite3.Row
        if not self._is_mem:
            conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        return conn

    def migrate(self) -> None:
        """Applies versioned, additive, idempotent migrations."""
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS learn_schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at INTEGER NOT NULL
                );
            """)
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(version) FROM learn_schema_version;")
            row = cursor.fetchone()
            current_ver = row[0] if row and row[0] is not None else 0

            if current_ver < 1:
                self._apply_v1_migration(conn)
                conn.execute(
                    "INSERT INTO learn_schema_version (version, applied_at) VALUES (?, ?);",
                    (1, int(time.time())),
                )
                LOGGER.info("Applied Preppy DB schema v1 migration successfully.")

            if current_ver < 2:
                self._apply_v2_migration(conn)
                conn.execute(
                    "INSERT INTO learn_schema_version (version, applied_at) VALUES (?, ?);",
                    (2, int(time.time())),
                )
                LOGGER.info("Applied Preppy DB schema v2 migration successfully.")

    def _apply_v1_migration(self, conn: sqlite3.Connection) -> None:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS learn_student (
                id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );

            INSERT OR IGNORE INTO learn_student (id, display_name, created_at)
            VALUES ('local', 'Student', strftime('%s', 'now'));

            CREATE TABLE IF NOT EXISTS learn_material (
                id TEXT PRIMARY KEY,
                student_id TEXT NOT NULL,
                title TEXT NOT NULL,
                kind TEXT NOT NULL,
                source_ref TEXT,
                content_hash TEXT NOT NULL,
                okf_text TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                FOREIGN KEY (student_id) REFERENCES learn_student(id)
            );

            CREATE TABLE IF NOT EXISTS learn_concept (
                id TEXT PRIMARY KEY,
                material_id TEXT NOT NULL,
                parent_id TEXT,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                order_idx INTEGER NOT NULL DEFAULT 0,
                prerequisites_json TEXT NOT NULL DEFAULT '[]',
                source_spans_json TEXT NOT NULL DEFAULT '[]',
                FOREIGN KEY (material_id) REFERENCES learn_material(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS learn_misconception_candidate (
                id TEXT PRIMARY KEY,
                concept_id TEXT NOT NULL,
                label TEXT NOT NULL,
                description TEXT NOT NULL,
                typical_wrong_answer TEXT NOT NULL,
                origin TEXT NOT NULL DEFAULT 'ai_proposed',
                FOREIGN KEY (concept_id) REFERENCES learn_concept(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS learn_question (
                id TEXT PRIMARY KEY,
                concept_id TEXT NOT NULL,
                type TEXT NOT NULL,
                difficulty INTEGER NOT NULL DEFAULT 2,
                stem TEXT NOT NULL,
                options_json TEXT NOT NULL DEFAULT '[]',
                correct_answer TEXT NOT NULL,
                rubric_json TEXT,
                distractor_map_json TEXT NOT NULL DEFAULT '{}',
                source_span_json TEXT,
                grounded INTEGER NOT NULL DEFAULT 0,
                origin TEXT NOT NULL DEFAULT 'ai',
                created_at INTEGER NOT NULL,
                FOREIGN KEY (concept_id) REFERENCES learn_concept(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS learn_attempt (
                id TEXT PRIMARY KEY,
                student_id TEXT NOT NULL,
                question_id TEXT NOT NULL,
                concept_id TEXT NOT NULL,
                answer_text TEXT NOT NULL,
                selected_option TEXT,
                reasoning_text TEXT NOT NULL DEFAULT '',
                confidence INTEGER,
                is_correct INTEGER NOT NULL DEFAULT 0,
                score REAL NOT NULL DEFAULT 0.0,
                time_ms INTEGER NOT NULL DEFAULT 0,
                session_id TEXT NOT NULL DEFAULT 'default',
                created_at INTEGER NOT NULL,
                FOREIGN KEY (student_id) REFERENCES learn_student(id)
            );

            CREATE TABLE IF NOT EXISTS learn_misconception_record (
                id TEXT PRIMARY KEY,
                attempt_id TEXT NOT NULL,
                concept_id TEXT NOT NULL,
                error_type TEXT NOT NULL,
                misconception_id TEXT,
                state TEXT NOT NULL DEFAULT 'suspected',
                confidence REAL NOT NULL DEFAULT 0.0,
                evidence_quote TEXT,
                explanation_json TEXT NOT NULL DEFAULT '{}',
                created_at INTEGER NOT NULL,
                resolved_at INTEGER,
                FOREIGN KEY (attempt_id) REFERENCES learn_attempt(id) ON DELETE CASCADE,
                FOREIGN KEY (concept_id) REFERENCES learn_concept(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS learn_mastery (
                student_id TEXT NOT NULL,
                concept_id TEXT NOT NULL,
                mastery REAL NOT NULL DEFAULT 0.50,
                attempts INTEGER NOT NULL DEFAULT 0,
                correct INTEGER NOT NULL DEFAULT 0,
                consecutive_correct INTEGER NOT NULL DEFAULT 0,
                last_outcomes_json TEXT NOT NULL DEFAULT '[]',
                has_transfer_success INTEGER NOT NULL DEFAULT 0,
                consistency REAL NOT NULL DEFAULT 1.0,
                band TEXT NOT NULL DEFAULT 'insufficient_evidence',
                updated_at INTEGER NOT NULL,
                PRIMARY KEY (student_id, concept_id),
                FOREIGN KEY (student_id) REFERENCES learn_student(id),
                FOREIGN KEY (concept_id) REFERENCES learn_concept(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS learn_mastery_history (
                id TEXT PRIMARY KEY,
                student_id TEXT NOT NULL,
                concept_id TEXT NOT NULL,
                mastery REAL NOT NULL,
                attempt_id TEXT,
                snapshot_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS learn_revision (
                student_id TEXT NOT NULL,
                concept_id TEXT NOT NULL,
                due_at INTEGER NOT NULL,
                interval_days INTEGER NOT NULL DEFAULT 1,
                ease REAL NOT NULL DEFAULT 2.30,
                last_reviewed_at INTEGER NOT NULL DEFAULT 0,
                reason_code TEXT NOT NULL DEFAULT 'INITIAL',
                reason_text TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (student_id, concept_id),
                FOREIGN KEY (student_id) REFERENCES learn_student(id),
                FOREIGN KEY (concept_id) REFERENCES learn_concept(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_concept_material ON learn_concept(material_id);
            CREATE INDEX IF NOT EXISTS idx_question_concept ON learn_question(concept_id);
            CREATE INDEX IF NOT EXISTS idx_attempt_student_concept ON learn_attempt(student_id, concept_id);
            CREATE INDEX IF NOT EXISTS idx_revision_due ON learn_revision(due_at);
            CREATE INDEX IF NOT EXISTS idx_mastery_history_concept ON learn_mastery_history(student_id, concept_id, snapshot_at);
        """)

    def _apply_v2_migration(self, conn: sqlite3.Connection) -> None:
        """Applies schema v2 for Read -> Recall chunks and recall sessions (§5.2)."""
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS learn_chunk (
                id TEXT PRIMARY KEY,
                material_id TEXT NOT NULL,
                concept_id TEXT,
                idx INTEGER NOT NULL,
                text TEXT NOT NULL,
                word_count INTEGER NOT NULL,
                key_ideas_json TEXT NOT NULL DEFAULT '[]',
                key_ideas_status TEXT NOT NULL DEFAULT 'ready',
                FOREIGN KEY (material_id) REFERENCES learn_material(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS learn_recall_session (
                id TEXT PRIMARY KEY,
                student_id TEXT NOT NULL,
                chunk_id TEXT NOT NULL,
                concept_id TEXT,
                read_ms INTEGER NOT NULL DEFAULT 0,
                peeked INTEGER NOT NULL DEFAULT 0,
                input_method TEXT NOT NULL DEFAULT 'wispr_flow_dictation',
                transcript_raw TEXT NOT NULL,
                transcript_final TEXT NOT NULL,
                coverage REAL NOT NULL DEFAULT 0.0,
                recitation_ratio REAL NOT NULL DEFAULT 0.0,
                accuracy_flags_json TEXT NOT NULL DEFAULT '{}',
                analysis_json TEXT NOT NULL DEFAULT '{}',
                created_at INTEGER NOT NULL,
                FOREIGN KEY (student_id) REFERENCES learn_student(id),
                FOREIGN KEY (chunk_id) REFERENCES learn_chunk(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_chunk_material ON learn_chunk(material_id);
            CREATE INDEX IF NOT EXISTS idx_chunk_concept ON learn_chunk(concept_id);
            CREATE INDEX IF NOT EXISTS idx_recall_session_student_chunk ON learn_recall_session(student_id, chunk_id);
        """)

        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(learn_attempt);")
        columns = [row[1] for row in cursor.fetchall()]
        if "chunk_id" not in columns:
            conn.execute("ALTER TABLE learn_attempt ADD COLUMN chunk_id TEXT;")
        if "source" not in columns:
            conn.execute("ALTER TABLE learn_attempt ADD COLUMN source TEXT NOT NULL DEFAULT 'quiz';")

    # -------------------------------------------------------------------------
    # Material & Concept Operations
    # -------------------------------------------------------------------------
    def save_material(self, material: Material) -> None:
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO learn_material
                (id, student_id, title, kind, source_ref, content_hash, okf_text, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                material.id,
                material.student_id,
                material.title,
                material.kind.value,
                material.source_ref,
                material.content_hash,
                material.okf_text,
                material.created_at or int(time.time()),
            ))

    def list_materials(self, student_id: str = "local") -> List[Material]:
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM learn_material WHERE student_id = ? ORDER BY created_at DESC;",
                (student_id,)
            ).fetchall()
            return [
                Material(
                    id=row["id"],
                    student_id=row["student_id"],
                    title=row["title"],
                    kind=MaterialKind(row["kind"]),
                    source_ref=row["source_ref"],
                    content_hash=row["content_hash"],
                    okf_text=row["okf_text"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]

    def get_material(self, material_id: str) -> Optional[Material]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM learn_material WHERE id = ?;", (material_id,)).fetchone()
            if not row:
                return None
            return Material(
                id=row["id"],
                student_id=row["student_id"],
                title=row["title"],
                kind=MaterialKind(row["kind"]),
                source_ref=row["source_ref"],
                content_hash=row["content_hash"],
                okf_text=row["okf_text"],
                created_at=row["created_at"],
            )

    def save_concepts(self, concepts: List[Concept]) -> None:
        with self.get_connection() as conn:
            for c in concepts:
                spans_json = json.dumps([s.model_dump() for s in c.source_spans])
                conn.execute("""
                    INSERT OR REPLACE INTO learn_concept
                    (id, material_id, parent_id, name, description, order_idx, prerequisites_json, source_spans_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    c.id,
                    c.material_id,
                    c.parent_id,
                    c.name,
                    c.description,
                    c.order_idx,
                    json.dumps(c.prerequisites),
                    spans_json,
                ))

    def list_concepts(self, material_id: Optional[str] = None) -> List[Concept]:
        with self.get_connection() as conn:
            if material_id:
                rows = conn.execute(
                    "SELECT * FROM learn_concept WHERE material_id = ? ORDER BY order_idx ASC;",
                    (material_id,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM learn_concept ORDER BY order_idx ASC;").fetchall()

            result = []
            for row in rows:
                spans_raw = json.loads(row["source_spans_json"] or "[]")
                spans = [SourceSpan(**s) for s in spans_raw]
                result.append(
                    Concept(
                        id=row["id"],
                        material_id=row["material_id"],
                        parent_id=row["parent_id"],
                        name=row["name"],
                        description=row["description"],
                        order_idx=row["order_idx"],
                        prerequisites=json.loads(row["prerequisites_json"] or "[]"),
                        source_spans=spans,
                    )
                )
            return result

    def get_concept(self, concept_id: str) -> Optional[Concept]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM learn_concept WHERE id = ?;", (concept_id,)).fetchone()
            if not row:
                return None
            spans_raw = json.loads(row["source_spans_json"] or "[]")
            return Concept(
                id=row["id"],
                material_id=row["material_id"],
                parent_id=row["parent_id"],
                name=row["name"],
                description=row["description"],
                order_idx=row["order_idx"],
                prerequisites=json.loads(row["prerequisites_json"] or "[]"),
                source_spans=[SourceSpan(**s) for s in spans_raw],
            )

    # -------------------------------------------------------------------------
    # Questions & Candidates Operations
    # -------------------------------------------------------------------------
    def save_questions(self, questions: List[Question]) -> None:
        with self.get_connection() as conn:
            for q in questions:
                span_json = json.dumps(q.source_span.model_dump()) if q.source_span else None
                conn.execute("""
                    INSERT OR REPLACE INTO learn_question
                    (id, concept_id, type, difficulty, stem, options_json, correct_answer, rubric_json, distractor_map_json, source_span_json, grounded, origin, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    q.id,
                    q.concept_id,
                    q.type.value,
                    q.difficulty,
                    q.stem,
                    json.dumps(q.options),
                    q.correct_answer,
                    q.rubric,
                    json.dumps(q.distractor_map),
                    span_json,
                    1 if q.grounded else 0,
                    q.origin,
                    q.created_at or int(time.time()),
                ))

    def list_questions_for_concept(self, concept_id: str) -> List[Question]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM learn_question WHERE concept_id = ?;", (concept_id,)).fetchall()
            result = []
            for row in rows:
                span = SourceSpan(**json.loads(row["source_span_json"])) if row["source_span_json"] else None
                result.append(
                    Question(
                        id=row["id"],
                        concept_id=row["concept_id"],
                        type=row["type"],
                        difficulty=row["difficulty"],
                        stem=row["stem"],
                        options=json.loads(row["options_json"] or "[]"),
                        correct_answer=row["correct_answer"],
                        rubric=row["rubric_json"],
                        distractor_map=json.loads(row["distractor_map_json"] or "{}"),
                        source_span=span,
                        grounded=bool(row["grounded"]),
                        origin=row["origin"],
                        created_at=row["created_at"],
                    )
                )
            return result

    def get_question(self, question_id: str) -> Optional[Question]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM learn_question WHERE id = ?;", (question_id,)).fetchone()
            if not row:
                return None
            span = SourceSpan(**json.loads(row["source_span_json"])) if row["source_span_json"] else None
            return Question(
                id=row["id"],
                concept_id=row["concept_id"],
                type=row["type"],
                difficulty=row["difficulty"],
                stem=row["stem"],
                options=json.loads(row["options_json"] or "[]"),
                correct_answer=row["correct_answer"],
                rubric=row["rubric_json"],
                distractor_map=json.loads(row["distractor_map_json"] or "{}"),
                source_span=span,
                grounded=bool(row["grounded"]),
                origin=row["origin"],
                created_at=row["created_at"],
            )

    def save_misconception_candidates(self, candidates: List[MisconceptionCandidate]) -> None:
        with self.get_connection() as conn:
            for c in candidates:
                conn.execute("""
                    INSERT OR REPLACE INTO learn_misconception_candidate
                    (id, concept_id, label, description, typical_wrong_answer, origin)
                    VALUES (?, ?, ?, ?, ?, ?);
                """, (
                    c.id,
                    c.concept_id,
                    c.label,
                    c.description,
                    c.typical_wrong_answer,
                    c.origin,
                ))

    def list_misconception_candidates(self, concept_id: str) -> List[MisconceptionCandidate]:
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM learn_misconception_candidate WHERE concept_id = ?;",
                (concept_id,)
            ).fetchall()
            return [
                MisconceptionCandidate(
                    id=row["id"],
                    concept_id=row["concept_id"],
                    label=row["label"],
                    description=row["description"],
                    typical_wrong_answer=row["typical_wrong_answer"],
                    origin=row["origin"],
                )
                for row in rows
            ]

    # -------------------------------------------------------------------------
    # Attempts & Misconception Records Operations
    # -------------------------------------------------------------------------
    def save_attempt(self, attempt: Attempt) -> None:
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO learn_attempt
                (id, student_id, question_id, chunk_id, concept_id, source, answer_text, selected_option, reasoning_text, confidence, is_correct, score, time_ms, session_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                attempt.id,
                attempt.student_id,
                attempt.question_id,
                attempt.chunk_id,
                attempt.concept_id,
                attempt.source or "quiz",
                attempt.answer_text,
                attempt.selected_option,
                attempt.reasoning_text,
                attempt.confidence,
                1 if attempt.is_correct else 0,
                attempt.score,
                attempt.time_ms,
                attempt.session_id,
                attempt.created_at or int(time.time()),
            ))

    def list_attempts_for_concept(self, concept_id: str, student_id: str = "local") -> List[Attempt]:
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM learn_attempt
                WHERE concept_id = ? AND student_id = ?
                ORDER BY created_at ASC;
            """, (concept_id, student_id)).fetchall()
            return [
                Attempt(
                    id=row["id"],
                    student_id=row["student_id"],
                    question_id=row["question_id"] if "question_id" in row.keys() else None,
                    chunk_id=row["chunk_id"] if "chunk_id" in row.keys() else None,
                    concept_id=row["concept_id"],
                    source=row["source"] if "source" in row.keys() else "quiz",
                    answer_text=row["answer_text"],
                    selected_option=row["selected_option"],
                    reasoning_text=row["reasoning_text"] or "",
                    confidence=row["confidence"],
                    is_correct=bool(row["is_correct"]),
                    score=row["score"],
                    time_ms=row["time_ms"],
                    session_id=row["session_id"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]

    def save_misconception_record(self, record: MisconceptionRecord) -> None:
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO learn_misconception_record
                (id, attempt_id, concept_id, error_type, misconception_id, state, confidence, evidence_quote, explanation_json, created_at, resolved_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                record.id,
                record.attempt_id,
                record.concept_id,
                record.error_type.value,
                record.misconception_id,
                record.state.value,
                record.confidence,
                record.evidence_quote,
                json.dumps(record.explanation),
                record.created_at or int(time.time()),
                record.resolved_at,
            ))

    def list_open_misconceptions(self, student_id: str = "local") -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT r.*, c.name as concept_name, a.student_id
                FROM learn_misconception_record r
                JOIN learn_concept c ON r.concept_id = c.id
                JOIN learn_attempt a ON r.attempt_id = a.id
                WHERE a.student_id = ? AND r.state IN ('suspected', 'confirmed', 'uncertain')
                ORDER BY r.created_at DESC;
            """, (student_id,)).fetchall()
            return [dict(row) for row in rows]

    # -------------------------------------------------------------------------
    # Mastery & Revision Operations
    # -------------------------------------------------------------------------
    def save_mastery(self, m: Mastery, attempt_id: Optional[str] = None) -> None:
        with self.get_connection() as conn:
            now = int(time.time())
            conn.execute("""
                INSERT OR REPLACE INTO learn_mastery
                (student_id, concept_id, mastery, attempts, correct, consecutive_correct, last_outcomes_json, has_transfer_success, consistency, band, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                m.student_id,
                m.concept_id,
                m.mastery,
                m.attempts,
                m.correct,
                m.consecutive_correct,
                json.dumps(m.last_outcomes),
                1 if m.has_transfer_success else 0,
                m.consistency,
                m.band.value,
                now,
            ))
            # Record snapshot in history
            hist_id = f"hist_{m.concept_id}_{now}_{m.attempts}"
            conn.execute("""
                INSERT OR REPLACE INTO learn_mastery_history
                (id, student_id, concept_id, mastery, attempt_id, snapshot_at)
                VALUES (?, ?, ?, ?, ?, ?);
            """, (hist_id, m.student_id, m.concept_id, m.mastery, attempt_id, now))

    def get_mastery(self, concept_id: str, student_id: str = "local") -> Optional[Mastery]:
        with self.get_connection() as conn:
            row = conn.execute("""
                SELECT * FROM learn_mastery
                WHERE concept_id = ? AND student_id = ?;
            """, (concept_id, student_id)).fetchone()
            if not row:
                return None
            return Mastery(
                student_id=row["student_id"],
                concept_id=row["concept_id"],
                mastery=row["mastery"],
                attempts=row["attempts"],
                correct=row["correct"],
                consecutive_correct=row["consecutive_correct"],
                last_outcomes=json.loads(row["last_outcomes_json"] or "[]"),
                has_transfer_success=bool(row["has_transfer_success"]),
                consistency=row["consistency"],
                band=row["band"],
                updated_at=row["updated_at"],
            )

    def list_all_masteries(self, student_id: str = "local") -> List[Mastery]:
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM learn_mastery
                WHERE student_id = ?;
            """, (student_id,)).fetchall()
            return [
                Mastery(
                    student_id=row["student_id"],
                    concept_id=row["concept_id"],
                    mastery=row["mastery"],
                    attempts=row["attempts"],
                    correct=row["correct"],
                    consecutive_correct=row["consecutive_correct"],
                    last_outcomes=json.loads(row["last_outcomes_json"] or "[]"),
                    has_transfer_success=bool(row["has_transfer_success"]),
                    consistency=row["consistency"],
                    band=row["band"],
                    updated_at=row["updated_at"],
                )
                for row in rows
            ]

    def get_mastery_history(self, concept_id: str, student_id: str = "local") -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM learn_mastery_history
                WHERE concept_id = ? AND student_id = ?
                ORDER BY snapshot_at ASC;
            """, (concept_id, student_id)).fetchall()
            return [dict(row) for row in rows]

    def save_revision_item(self, item: RevisionItem) -> None:
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO learn_revision
                (student_id, concept_id, due_at, interval_days, ease, last_reviewed_at, reason_code, reason_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                item.student_id,
                item.concept_id,
                item.due_at,
                item.interval_days,
                item.ease,
                item.last_reviewed_at,
                item.reason_code,
                item.reason_text,
            ))

    def get_revision_item(self, concept_id: str, student_id: str = "local") -> Optional[RevisionItem]:
        with self.get_connection() as conn:
            row = conn.execute("""
                SELECT * FROM learn_revision
                WHERE concept_id = ? AND student_id = ?;
            """, (concept_id, student_id)).fetchone()
            if not row:
                return None
            return RevisionItem(
                student_id=row["student_id"],
                concept_id=row["concept_id"],
                due_at=row["due_at"],
                interval_days=row["interval_days"],
                ease=row["ease"],
                last_reviewed_at=row["last_reviewed_at"],
                reason_code=row["reason_code"],
                reason_text=row["reason_text"],
            )

    def list_revision_queue(self, student_id: str = "local", max_items: int = 20) -> List[RevisionItem]:
        """Returns due concepts ordered by overdue_days * (1 - mastery) descending."""
        now = int(time.time())
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT r.*, COALESCE(m.mastery, 0.5) as mastery,
                       (CASE WHEN open_misc.cnt > 0 THEN 1 ELSE 0 END) as has_open_misc
                FROM learn_revision r
                LEFT JOIN learn_mastery m ON r.concept_id = m.concept_id AND r.student_id = m.student_id
                LEFT JOIN (
                    SELECT concept_id, COUNT(*) as cnt
                    FROM learn_misconception_record
                    WHERE state IN ('suspected', 'confirmed', 'uncertain')
                    GROUP BY concept_id
                ) open_misc ON r.concept_id = open_misc.concept_id
                WHERE r.student_id = ? AND r.due_at <= ?
                ORDER BY has_open_misc DESC, ((? - r.due_at) * (1.0 - COALESCE(m.mastery, 0.5))) DESC
                LIMIT ?;
            """, (student_id, now, now, max_items)).fetchall()
            return [
                RevisionItem(
                    student_id=row["student_id"],
                    concept_id=row["concept_id"],
                    due_at=row["due_at"],
                    interval_days=row["interval_days"],
                    ease=row["ease"],
                    last_reviewed_at=row["last_reviewed_at"],
                    reason_code=row["reason_code"],
                    reason_text=row["reason_text"],
                )
                for row in rows
            ]

    # -------------------------------------------------------------------------
    # Read -> Recall Chunks & Sessions Operations (§5.2)
    # -------------------------------------------------------------------------
    def save_chunk(self, chunk: Chunk) -> None:
        self.save_chunks([chunk])

    def save_chunks(self, chunks: List[Chunk]) -> None:
        with self.get_connection() as conn:
            for c in chunks:
                conn.execute("""
                    INSERT OR REPLACE INTO learn_chunk
                    (id, material_id, concept_id, idx, text, word_count, key_ideas_json, key_ideas_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    c.id,
                    c.material_id,
                    c.concept_id,
                    c.idx,
                    c.text,
                    c.word_count,
                    json.dumps([ki.model_dump() for ki in c.key_ideas]),
                    c.key_ideas_status,
                ))

    def get_chunk(self, chunk_id: str) -> Optional[Chunk]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM learn_chunk WHERE id = ?;", (chunk_id,)).fetchone()
            if not row:
                return None
            key_ideas_data = json.loads(row["key_ideas_json"] or "[]")
            key_ideas = [ChunkKeyIdea(**ki) for ki in key_ideas_data]
            return Chunk(
                id=row["id"],
                material_id=row["material_id"],
                concept_id=row["concept_id"],
                idx=row["idx"],
                text=row["text"],
                word_count=row["word_count"],
                key_ideas=key_ideas,
                key_ideas_status=row["key_ideas_status"],
            )

    def list_chunks(self, material_id: Optional[str] = None, concept_id: Optional[str] = None) -> List[Chunk]:
        with self.get_connection() as conn:
            if concept_id:
                rows = conn.execute("SELECT * FROM learn_chunk WHERE concept_id = ? ORDER BY idx ASC;", (concept_id,)).fetchall()
            elif material_id:
                rows = conn.execute("SELECT * FROM learn_chunk WHERE material_id = ? ORDER BY idx ASC;", (material_id,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM learn_chunk ORDER BY idx ASC;").fetchall()
            
            result = []
            for row in rows:
                key_ideas_data = json.loads(row["key_ideas_json"] or "[]")
                key_ideas = [ChunkKeyIdea(**ki) for ki in key_ideas_data]
                result.append(
                    Chunk(
                        id=row["id"],
                        material_id=row["material_id"],
                        concept_id=row["concept_id"],
                        idx=row["idx"],
                        text=row["text"],
                        word_count=row["word_count"],
                        key_ideas=key_ideas,
                        key_ideas_status=row["key_ideas_status"],
                    )
                )
            return result

    def save_recall_session(self, session: RecallSession) -> None:
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO learn_recall_session
                (id, student_id, chunk_id, concept_id, read_ms, peeked, input_method, transcript_raw, transcript_final, coverage, recitation_ratio, accuracy_flags_json, analysis_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                session.id,
                session.student_id,
                session.chunk_id,
                session.concept_id,
                session.read_ms,
                1 if session.peeked else 0,
                session.input_method,
                session.transcript_raw,
                session.transcript_final,
                session.coverage,
                session.recitation_ratio,
                json.dumps(session.accuracy_flags),
                json.dumps(session.analysis.model_dump()),
                session.created_at or int(time.time()),
            ))

    def get_recall_session(self, session_id: str) -> Optional[RecallSession]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM learn_recall_session WHERE id = ?;", (session_id,)).fetchone()
            if not row:
                return None
            return RecallSession(
                id=row["id"],
                student_id=row["student_id"],
                chunk_id=row["chunk_id"],
                concept_id=row["concept_id"],
                read_ms=row["read_ms"],
                peeked=bool(row["peeked"]),
                input_method=row["input_method"],
                transcript_raw=row["transcript_raw"],
                transcript_final=row["transcript_final"],
                coverage=row["coverage"],
                recitation_ratio=row["recitation_ratio"],
                accuracy_flags=json.loads(row["accuracy_flags_json"] or "{}"),
                analysis=RecallAnalysisResult(**json.loads(row["analysis_json"] or "{}")),
                created_at=row["created_at"],
            )

    def list_recall_sessions(self, student_id: str = "local", chunk_id: Optional[str] = None) -> List[RecallSession]:
        with self.get_connection() as conn:
            if chunk_id:
                rows = conn.execute("""
                    SELECT * FROM learn_recall_session
                    WHERE student_id = ? AND chunk_id = ?
                    ORDER BY created_at DESC;
                """, (student_id, chunk_id)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM learn_recall_session
                    WHERE student_id = ?
                    ORDER BY created_at DESC;
                """, (student_id,)).fetchall()
            
            result = []
            for row in rows:
                result.append(
                    RecallSession(
                        id=row["id"],
                        student_id=row["student_id"],
                        chunk_id=row["chunk_id"],
                        concept_id=row["concept_id"],
                        read_ms=row["read_ms"],
                        peeked=bool(row["peeked"]),
                        input_method=row["input_method"],
                        transcript_raw=row["transcript_raw"],
                        transcript_final=row["transcript_final"],
                        coverage=row["coverage"],
                        recitation_ratio=row["recitation_ratio"],
                        accuracy_flags=json.loads(row["accuracy_flags_json"] or "{}"),
                        analysis=RecallAnalysisResult(**json.loads(row["analysis_json"] or "{}")),
                        created_at=row["created_at"],
                    )
                )
            return result

