from __future__ import annotations

import os
from pathlib import Path

# Deterministic Mastery Update Parameters (§5.3)
ALPHA_BASE: float = 0.30
DIFFICULTY_WEIGHTS: dict[int, float] = {1: 0.8, 2: 1.0, 3: 1.2}
GUESS_DISCOUNT_CAP: float = 0.70
CARELESS_MISTAKE_WEIGHT: float = 0.50

# Mastery Bands
BAND_WEAK_MAX: float = 0.40
BAND_STRONG_MIN: float = 0.75
STRONG_MIN_ATTEMPTS: int = 2
STRONG_MIN_CONSISTENCY: float = 0.60

# Spaced Repetition (SM-2 Inspired) Parameters (§5.4)
SM2_INITIAL_EASE: float = 2.30
SM2_MIN_EASE: float = 1.30
SM2_MAX_EASE: float = 2.80

# Ingestion & Diagnostic Caps (§5.1)
DEFAULT_MAX_CONCEPTS_PER_MATERIAL: int = 25
DEFAULT_MAX_CONCEPT_DEPTH: int = 3
DEFAULT_DIAGNOSTIC_QUESTION_COUNT: int = 10
MAX_DIAGNOSTIC_QUESTION_COUNT: int = 20

# Misconception Remediation (§5.2)
MAX_REMEDIATION_LOOPS: int = 3
MIN_MISCONCEPTION_CONFIDENCE: float = 0.55
MAX_NO_REASONING_CONFIDENCE: float = 0.60

# Read -> Recall Voice Parameters (§5.2)
MIN_RECALL_WORDS: int = 15
MIN_RECALL_RATIO: float = 0.30
RECITATION_TRIGRAM_THRESHOLD: float = 0.60
PEEKED_COVERAGE_CAP: float = 0.70
RECITED_COVERAGE_CAP: float = 0.50
CHUNK_MIN_WORDS: int = 80
CHUNK_MAX_WORDS: int = 220

# AI Call Budget & Safety (§6.1)
DEFAULT_CALL_BUDGET: int = 40


def get_db_path() -> Path:
    """Returns the configured or default database path for Preppy SQLite."""
    custom_path = os.getenv("BLINKY_LEARN_DB_PATH", "").strip()
    if custom_path:
        return Path(custom_path)
    return Path(".brain") / "learn" / "learn.db"


def get_call_budget() -> int:
    """Returns the session call budget from environment or default."""
    try:
        val = int(os.getenv("BLINKY_LEARN_CALL_BUDGET", str(DEFAULT_CALL_BUDGET)).strip())
        return max(1, val)
    except Exception:
        return DEFAULT_CALL_BUDGET

